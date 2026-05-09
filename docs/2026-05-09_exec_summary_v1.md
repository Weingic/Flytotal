# Flytotal 一页执行摘要 V1

更新：2026-05-09 · 答辩 30 秒一页版

## 项目定位

低成本边缘端反无人机感知系统，基于 ESP32 双节点（S3 主感知 + C3 身份链）+ LD2450/LD2451 双雷达 + 视觉摄像头 + 协同上报，目标 100 m 范围内**远距广搜、中距确认、近距固证**。

## 系统拓扑

```
[LD2450 短距 2D]───┐
[LD2451 长距运动]──┤
                   ├── NodeA (ESP32-S3) ──UART──> 上位机/Dashboard
[摄像头 + YOLO/CSRT]┤                  ↑
                   │                 [Fusion + 多旋翼筛选 + 云台预测]
[NodeB (ESP32-C3)]─┘                   │
   Wi-Fi/BLE RID                       │
                                  [事件 + 证据链]
```

## 三大创新点（每条配 1 张图）

| # | 创新点 | 技术核心 | 证据图 |
|---|---|---|---|
| 1 | **多模态融合分阶段** | FAR/MID/NEAR 三阶段 + 距离/速度一致性矩阵 + 浮点置信度 | `outputs/fusion_compare_far_mid_near.png` |
| 2 | **多旋翼特征抗干扰** | 速度区间 + 悬停容忍 + 轨迹曲率 + 持续时长 4 维筛选 | `outputs/multirotor_features.png` + `multirotor_confusion_matrix.png` |
| 3 | **ESP32 边缘协同感知** | NodeA + NodeB UART 双节点 + handoff 4 态机 | `outputs/co_sensing_timeline.png` |

辅助创新：**云台二阶预测**（Lead 0.18s + Kd + 加速度 clamp + 低通滤波），见 `outputs/gimbal_prediction.png`。

## 关键指标

| 指标 | 数值 | 来源 |
|---|---|---|
| 检测距离 | 5 m – 100 m | 设计目标 + 现场协议 |
| FAR 阶段 | >30 m，LD2451+RID 双源 | `Fusion.cpp:117` |
| MID 阶段 | 10–30 m，2 源一致 | 同上 |
| NEAR 阶段 | <10 m，必有视觉或 RID_MATCHED | 同上 |
| 多旋翼确认延迟 | 5 帧 ≈ 0.5 s | `TrackConfig::ConfirmFrames=5` |
| 云台预测 lead | 0.18 s 二阶外推 | `GimbalConfig::PredictorLeadTimeSeconds` |
| Watchdog 时限 | 8 s（5 任务全注册） | `WatchdogConfig::TimeoutSeconds` |
| NodeB 重连冷却 | 3 s（快阶段 5 次后切 15 s） | `NodeBConfig::ReconnectIntervalMs` |

## 核心字段（数据契约）

- 雷达：`x_mm / y_mm / vx_mm_s / vy_mm_s`、`lr_range_mm / lr_speed_mm_s`、`is_multirotor_like / multirotor_score`
- 视觉：`vision_confidence (0-1) / bbox_stability_score / tracker_state`
- 融合：`fusion_stage (FAR/MID/NEAR) / fusion_confidence (0-1) / fusion_level / fusion_reason`
- 协同：`nodeb_online / handoff_from / handoff_to / continuity_hint`

## 端到端延迟（典型场景，单位 ms）

```
雷达帧到达       ─┐
LD2450 解析+卡尔曼 │  ~5
轨迹更新+多旋翼判定│  ~3
融合评估           │  ~2  →  Fusion 决策
风险评分+事件状态机│  ~4
云台目标计算+二阶外推│  ~1
PWM 输出           ─┘  ~1     总计 ≈ 16 ms（雷达→云台）

视觉支链：摄像头帧 → YOLO 旁路 (10 帧 1 次) → CSRT 实时 → 写 latest_status.json → host command 注入主链 → Fusion 加权
延迟 ≈ 30-100 ms（独立线程，不阻塞主链）
```

详见 `docs/2026-05-09_latency_budget_v1.md`。

## 设计 vs 实装回归保护

- **FusionConfig::Enabled = false 默认** → 烧固件不影响 v1.0 六基线
- 运行时 `FUSION,ENABLE,1/0` host command 切换，无需重烧
- `release/v1.0` tag 保留，30s 内可回退（见 `runbook_v1.md`）

## 答辩素材清单（产物路径）

```
outputs/
├── fusion_compare_far_mid_near.png    ← 创新 1
├── gimbal_prediction.png              ← 云台二阶预测
├── multirotor_features.png            ← 创新 2 特征分布
├── multirotor_confusion_matrix.png    ← 创新 2 分类性能
└── co_sensing_timeline.png            ← 创新 3 状态切换

docs/
├── 2026-05-08_v5_2_overall_upgrade_v1.md      ← 总纲
├── 2026-05-08_algorithm_formula_book_v1.md    ← 公式书
├── 2026-05-08_hardware_bom_wiring_v1.md       ← 硬件 BOM
├── 2026-05-08_v5_2_runbook_v1.md              ← 部署+回退
├── 2026-04-30_v5_2_defense_qa_v1.md           ← 12 项 Q&A
└── 2026-05-09_exec_summary_v1.md              ← 本文档
```

## 给小白的解释

这是什么：答辩前 30 秒可以让评委看完的一页摘要。
有什么用：评委没时间读 10 份长文档，看完这页能立刻问到点子上。
你现在该怎么做：打印一份贴在演示桌前；做 PPT 时第二页直接抄这个结构。
