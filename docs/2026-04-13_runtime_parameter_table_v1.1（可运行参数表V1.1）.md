# 2026-04-13 可运行参数表 V1.1（Node A Base Demo）

## 1. 版本口径
- 基线版本：`Node_A_Base_Demo_V1.1`
- 固件配置来源：`include/AppConfig.h`

## 2. 参数冻结表

| 类别 | 参数 | 冻结值 | 说明 |
|---|---|---:|---|
| 轨迹确认 | `TrackConfig::ConfirmFrames` | `5` | 连续 5 帧确认轨迹 |
| 丢轨超时 | `TrackConfig::LostTimeoutMs` | `250` | 超过 250ms 未更新判丢轨 |
| 重建间隔 | `TrackConfig::RebuildGapMs` | `400` | 间隔过大重建新轨迹 |
| 风险阈值 | `HunterConfig::SuspiciousThreshold` | `40` | 可疑阈值 |
| 风险阈值 | `HunterConfig::HighRiskThreshold` | `60` | 高风险阈值 |
| 风险阈值 | `HunterConfig::EventThreshold` | `80` | 事件阈值 |
| 云台扫描幅度 | `GimbalConfig::ScanningAmplitudeDeg` | `15.0` | 扫描范围口径 |
| 云台扫描节奏 | `GimbalConfig::ScanningPeriodDivisor` | `900.0` | 扫描速度口径（当前未单独暴露 step 参数） |
| 跟踪平滑 | `GimbalConfig::PredictorKp` | `0.45` | 跟随力度 |
| 跟踪平滑 | `GimbalConfig::PredictorKd` | `0.05` | 阻尼项 |
| 事件触发门槛 | `EventConfig::MissingRidEventMinDurationMs` | `800` | 无身份短时进入不立刻事件化 |
| 身份匹配窗口 | `RidConfig::MatchWindowMs` | `1200` | 轨迹与身份匹配时间窗 |
| 身份超时 | `RidConfig::ReceiveTimeoutMs` | `3000` | 超时后进入 `RID_EXPIRED` |
| 抓拍触发条件 | `vision_locked && trigger_capture` | 逻辑条件 | 需进入风险触发链并锁定 |
| 上行心跳频率 | `CloudConfig::HeartbeatMs` | `1000` | `UPLINK,HB` 周期 |
| 事件上报频率 | `CloudConfig::EventReportMs` | `250` | `UPLINK,TRACK/EVENT` 节奏 |

## 3. RID 风险评分口径（V1.1）

| RID 状态 | 评分参数 |
|---|---:|
| `RID_MATCHED` | `-25` |
| `RID_RECEIVED` | `+8` |
| `RID_NONE` | `+24` |
| `RID_EXPIRED` | `+28` |
| `RID_INVALID` | `+34` |

## 4. 调参规则（本周）
1. 本周只允许微调 `RidConfig` 两个时间参数和 `PredictorKp/Kd`。
2. 其余参数保持冻结，避免身份链接入阶段引入额外变量。
