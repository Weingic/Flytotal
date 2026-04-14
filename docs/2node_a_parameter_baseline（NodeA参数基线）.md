# Node A 首测稳定参数表

（功能：
这不是程序功能，而是“调参基线功能”。后面你接雷达、接舵机时，能明确知道自己是基于哪一版参数在测。

目的：
给 2026-04-03 和 2026-04-04 的硬件联调提前铺路
避免后面调参时忘记原始值
让周报、PPT、执行书里有一张现成的“参数表”）


本文档用于固定当前 `Node A` 首轮联调前的默认参数，便于后续硬件测试、问题复盘和材料整理。

参数来源：  
[AppConfig.h](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/include/AppConfig.h)

说明：
- 本表记录的是当前代码中的默认值。
- 本表不代表“最终最优参数”，而是当前可作为首测起点的稳定参数。
- 后续硬件联调时，应优先在本表基础上小步调整，不建议同时大幅改多个参数。

## 一、串口与节点参数

| 参数名 | 当前值 | 作用 | 当前建议 |
| --- | --- | --- | --- |
| `MonitorBaudRate` | `115200` | USB 串口监视器波特率 | 保持不动 |
| `RadarBaudRate` | `256000` | 雷达串口通信波特率 | 与雷达默认值一致，先不要改 |
| `RadarRxPin` | `18` | 雷达串口 RX 引脚 | 按当前接线使用 |
| `RadarTxPin` | `17` | 雷达串口 TX 引脚 | 按当前接线使用 |
| `StartupDelayMs` | `2000` | 启动后等待外设稳定的延时 | 首测保持不动 |
| `NodeId` | `A1` | 节点编号 | 当前固定 |
| `NodeRole` | `EDGE` | 节点角色 | 当前固定 |

## 二、云台预测与姿态参数

| 参数名 | 当前值 | 作用 | 当前建议 |
| --- | --- | --- | --- |
| `PredictorKp` | `0.45` | 云台预测器比例项 | 后续可小步调 |
| `PredictorKd` | `0.05` | 云台预测器微分项 | 当前先保守使用 |
| `PredictorFallbackDtSeconds` | `0.02` | 预测器回退时间步长 | 先不要改 |
| `PredictorLeadTimeSeconds` | `0.00` | 预测提前量 | 当前保持关闭 |
| `CenterPanDeg` | `90.0` | 水平舵机中心位 | 接云台时重点确认 |
| `CenterTiltDeg` | `90.0` | 俯仰舵机中心位 | 接云台时重点确认 |
| `MinPanDeg` | `10.0` | 水平最小角度限制 | 接舵机后再核实是否要收紧 |
| `MaxPanDeg` | `170.0` | 水平最大角度限制 | 接舵机后再核实是否要收紧 |
| `ScanningAmplitudeDeg` | `15.0` | 扫描模式左右摆动幅度 | 首测保持较小更安全 |
| `ScanningPeriodDivisor` | `900.0` | 扫描速度控制因子 | 当前不建议改 |
| `MinTiltMapInputMm` | `0` | 俯仰映射最小输入距离 | 保持不动 |
| `MaxTiltMapInputMm` | `6000` | 俯仰映射最大输入距离 | 保持不动 |
| `MinTiltDeg` | `60` | 俯仰最小角度 | 接舵机后检查是否超机械范围 |
| `MaxTiltDeg` | `120` | 俯仰最大角度 | 接舵机后检查是否超机械范围 |

## 三、舵机输出参数

| 参数名 | 当前值 | 作用 | 当前建议 |
| --- | --- | --- | --- |
| `PanPin` | `4` | 水平舵机 PWM 引脚 | 按当前接线使用 |
| `TiltPin` | `5` | 俯仰舵机 PWM 引脚 | 按当前接线使用 |
| `PwmFrequencyHz` | `50` | 舵机 PWM 频率 | 标准值，先不要改 |
| `PulseMinUs` | `500` | 舵机最小脉宽 | 接实物后如打角异常再调 |
| `PulseMaxUs` | `2500` | 舵机最大脉宽 | 接实物后如打角异常再调 |

## 四、雷达输入参数

| 参数名 | 当前值 | 作用 | 当前建议 |
| --- | --- | --- | --- |
| `LockDistanceThresholdMm` | `500.0` | 目标锁定距离阈值 | 接雷达后重点验证 |
| `PollDelayMs` | `10` | 雷达任务轮询周期 | 当前约 100Hz，先保持 |

说明：
- 当前代码中 `is_locked` 会基于 `track.is_confirmed` 和 `y` 距离阈值共同判定。
- 后续接雷达后，这个阈值需要结合真实场地距离感受再调。

## 五、轨迹管理参数

| 参数名 | 当前值 | 作用 | 当前建议 |
| --- | --- | --- | --- |
| `ConfirmFrames` | `5` | 连续出现多少帧后确认轨迹 | 首测合理，先不要降太低 |
| `LostTimeoutMs` | `250` | 超过多久没更新就判丢失 | 首测保持 |
| `RebuildGapMs` | `400` | 多久没见到目标就重建新轨迹 | 首测保持 |

说明：
- 这组参数直接影响 `track_active`、`confirmed`、`track_id` 的表现。
- 后续如果误报多或轨迹容易断，再微调这组参数。

## 六、Hunter 风险判定参数

| 参数名 | 当前值 | 作用 | 当前建议 |
| --- | --- | --- | --- |
| `TrackingBaseScore` | `20.0` | 目标存在时的基础分 | 当前先不改 |
| `SuspiciousThreshold` | `40.0` | 可疑目标阈值 | 首测保持 |
| `HighRiskThreshold` | `60.0` | 高风险阈值 | 首测保持 |
| `EventThreshold` | `80.0` | 事件目标阈值 | 首测保持 |
| `EventLockHoldMs` | `500` | 事件锁定保持时间 | 首测保持 |

说明：
- 当前阶段先验证状态切换通路是否正确。
- 不建议在没有真实联调数据前频繁修改风险阈值。

## 七、控制循环参数

| 参数名 | 当前值 | 作用 | 当前建议 |
| --- | --- | --- | --- |
| `AcquireConfirmMs` | `150` | 从捕获到正式跟踪的确认时间 | 接云台时重点观察 |
| `LostRecoveryTimeoutMs` | `3000` | 丢目标后回到扫描的超时 | 当前保持 |
| `LoopDelayMs` | `20` | 跟踪主循环周期 | 与舵机控制节奏匹配，先不要改 |

说明：
- 这组参数主要影响 `SCANNING -> ACQUIRING -> TRACKING -> LOST` 状态切换的观感。

## 八、上行与心跳参数

| 参数名 | 当前值 | 作用 | 当前建议 |
| --- | --- | --- | --- |
| `HeartbeatMs` | `1000` | 心跳上报周期 | 当前适合调试 |
| `EventReportMs` | `250` | 活跃轨迹上报周期 | 当前适合调试 |

说明：
- 如果后续串口输出过密或云端接入后流量过多，再考虑调整。
- 当前单板测试阶段保留这个频率有利于观察状态。

## 九、当前阶段建议重点关注的参数

### 今天单板测试阶段

优先关注：
- `MonitorBaudRate`
- `HeartbeatMs`
- `EventReportMs`
- `PredictorKp`
- `PredictorKd`

原因：
- 今天主要验证串口通信、日志输出和运行时命令生效。

### 4 月 3 日云台联调阶段

优先关注：
- `CenterPanDeg`
- `CenterTiltDeg`
- `MinPanDeg`
- `MaxPanDeg`
- `MinTiltDeg`
- `MaxTiltDeg`
- `PredictorKp`
- `PredictorKd`
- `AcquireConfirmMs`

### 4 月 4 日雷达联调阶段

优先关注：
- `LockDistanceThresholdMm`
- `ConfirmFrames`
- `LostTimeoutMs`
- `RebuildGapMs`
- `HeartbeatMs`
- `EventReportMs`

## 十、当前阶段不建议随意改动的参数

当前先不要随意改：

- `RadarBaudRate`
- `RadarRxPin`
- `RadarTxPin`
- `PwmFrequencyHz`
- `LoopDelayMs`
- `TrackingBaseScore`
- `SuspiciousThreshold`
- `HighRiskThreshold`
- `EventThreshold`

原因：
- 这些参数要么属于基础通信配置，要么属于整体行为基线。
- 过早改动容易让问题来源变得不清楚。

## 十一、结论

当前这版参数更适合作为：

- 单板自检的稳定起点
- 首轮硬件联调的基线参数
- 后续测试记录与问题复盘的对照版本

后续如果进入硬件调参阶段，建议每次只改 1 到 2 个参数，并记录修改前后现象。
