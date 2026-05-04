# Flytotal v5.2 Fusion Stage V1

Last updated: 2026-05-01

## 2026-05-03 P0 默认策略补充

- 固件默认 `FusionConfig::Enabled=false`，基础验收先走旧三源计数逻辑，避免六个基线场景被高级融合规则影响。
- 答辩或 v5.2 demo 前，通过串口发送 `FUSION,ENABLE,1` 开启 FAR / MID / NEAR 三阶段融合。
- 需要回到基础稳定模式时，发送 `FUSION,ENABLE,0`。
- `FUSION,STATUS` 会输出 `fusion_enabled=0/1`，`FUSION,DEBUG` 会输出视觉置信度、一致性和投票过程。
- 视觉投票不再只看 `vision_locked`，还会接受 `VISION,CONF,confidence=0.82,stability=0.91,state=TRACKING` 注入的 `vision_confidence >= 0.5`。

## 目标

v5.2 直接把主线升级为多模态融合版本。普通 `pio run` 构建的就是 v5.2：LD2450、LD2451、NodeB 身份链、视觉状态一起参与判断。

本版本不再追求“100 m 精确识别小型无人机”。100 m 只承诺远距运动预警触发；真正的目标确认仍依赖近距离雷达、视觉证据和 RID 身份链。

## 三阶段融合

| 阶段 | 距离 | 主要来源 | 规则 |
| --- | --- | --- | --- |
| FAR | `>30 m` | LD2451 + RID | LD2451 单源只到 LOW；LD2451 + RID 可到 MID |
| MID | `10-30 m` | LD2450 / LD2451 / RID | 任意 2 源一致可到 HIGH |
| NEAR | `<10 m` | LD2450 + 视觉/RID | 必须有视觉确认或 RID matched 才允许 HIGH |

## 一致性规则

- 距离一致性：LD2451 距离与 LD2450 `hypot(x,y)` 的相对误差默认不超过 `20%`。
- 速度一致性：LD2451 速度与 LD2450 径向速度方向一致，且差值默认不超过 `1500 mm/s`。
- 视觉一致性：视觉锁定且质量可用时，为融合增加确认票。
- 时间窗：HIGH 需要在 `800 ms` 滑窗内维持至少 2 源命中，避免瞬时误触发。

## 主状态字段

主状态只保留答辩能讲清楚的核心字段：

- `fusion_level`: `NONE / LOW / MID / HIGH`
- `fusion_stage`: `NONE / FAR / MID / NEAR`
- `fusion_confidence`: `0.0-1.0`
- `fusion_reason`: 当前融合原因
- `ld2451_range_m`, `ld2451_speed_mps`, `far_motion_trigger`
- `vision_quality`
- `nodeb_online`
- `is_multirotor_like`, `multirotor_score`

更细的距离/速度/视觉一致性票放在 `FUSION,DEBUG` 中，不塞进主状态。

## 答辩表述

可以这样讲：

> 系统按距离分成 FAR、MID、NEAR 三个融合阶段。远距离只做预警，中距离做多源确认，近距离必须结合视觉或身份链，避免把普通运动目标直接判成事件。这样能把 LD2451 的远距触发能力和 LD2450、视觉、NodeB 身份链各自的优势分开使用。

## 给小白的解释

这是什么：把“发现远处有东西动”和“确认这是可疑无人机”分成不同阶段。

有什么用：远处雷达先提醒，近处再用更多证据确认，这样不会把 100 m 的远距触发吹成精确识别。

你现在该怎么做：联调时先看 `FUSION,STATUS` 的 `fusion_stage` 和 `fusion_level`，再用 `FUSION,DEBUG` 看为什么升高或没升高。
