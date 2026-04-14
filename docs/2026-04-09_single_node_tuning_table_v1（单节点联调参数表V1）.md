# 2026-04-09 单节点联调参数表 V1

## 目标
用于 2026-04-09（周四）“单节点主链 + 网页实时显示”联调，保证每次联调都有统一参数口径。

## 固件基线参数（当前默认）

| 类别 | 参数 | 当前值 | 作用 | 联调建议 |
|---|---|---:|---|---|
| 云台预测 | `PredictorKp` | `0.45` | 跟随强度 | 若抖动明显，先降到 `0.35~0.40` |
| 云台预测 | `PredictorKd` | `0.05` | 阻尼项 | 先保持，避免和 Kp 同时大改 |
| 云台中心 | `CenterPanDeg` | `90` | 水平中心 | 机械中心不准时再改 |
| 云台中心 | `CenterTiltDeg` | `90` | 俯仰中心 | 机械中心不准时再改 |
| 扫描 | `ScanningAmplitudeDeg` | `15` | 扫描幅度 | 室内联调可先不改 |
| 跟踪确认 | `ConfirmFrames` | `5` | 轨迹确认帧数 | 抖动多时可升到 `6~7` |
| 丢轨判定 | `LostTimeoutMs` | `250` | 丢轨超时 | 过敏可升到 `300~350` |
| 风险阈值 | `SuspiciousThreshold` | `40` | 可疑阈值 | 先固定不改 |
| 风险阈值 | `HighRiskThreshold` | `60` | 高风险阈值 | 先固定不改 |
| 风险阈值 | `EventThreshold` | `80` | 事件阈值 | 先固定不改 |
| 云上报 | `HeartbeatMs` | `1000` | 心跳周期 | 联调期建议 `1000` |
| 云上报 | `EventReportMs` | `250` | 事件上报周期 | 联调期建议 `250` |

## 运行期可调参数（串口命令）

| 命令 | 示例 | 用途 |
|---|---|---|
| `KP,value` | `KP,0.40` | 在线调整 Kp |
| `KD,value` | `KD,0.05` | 在线调整 Kd |
| `SAFE,ON/OFF` | `SAFE,ON` | 安全角度限制开关 |
| `TESTMODE,ON/OFF` | `TESTMODE,ON` | 手动云台测试模式 |
| `PAN,angle` | `PAN,95` | 手动水平角 |
| `TILT,angle` | `TILT,88` | 手动俯仰角 |
| `COARSEAIM,x,y` | `COARSEAIM,320,1800` | 按雷达坐标做粗转向（4.9 新增） |

## 4.9 当天建议联调顺序（最小闭环）

1. 启动 `bridge`，确认 `node_status` 在线。
2. 跑 `standard_acceptance` 一轮，确认主链基线不回退。
3. 用真实雷达目标跑两种场景（至少“目标持续存在”“目标丢失”）。
4. 对照网页“链路一致性”字段，确保 `main_state/risk/event/track` 映射不偏移。
5. 用 `COARSEAIM,x,y` 验证“雷达坐标 -> 云台粗转向”入口。
6. 用实机场景核对脚本留档两场景（`sustained_target` / `track_lost`）。
7. 用汇总脚本生成当日实机结论（`latest_real_radar_summary.json`）。

建议命令：

```powershell
python tools/real_radar_scenario_checker_实机场景核对.py --scenario sustained_target --duration-s 20 --warmup-s 2
python tools/real_radar_scenario_checker_实机场景核对.py --scenario track_lost --duration-s 20 --warmup-s 2 --track-lost-phase1-ratio 0.5 --min-phase1-active-hits 2 --min-lost-hits 2
python tools/real_radar_report_summary_实机报告汇总.py --max-age-hours 24
```

## 本表更新规则

- 本表按“有参数改动才更新”执行。
- 下一次周计划窗口建议更新时间：`2026-04-13（周一）`。
