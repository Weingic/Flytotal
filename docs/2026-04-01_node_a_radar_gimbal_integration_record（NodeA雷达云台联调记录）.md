# Node A 雷达云台联调记录

适用日期：`2026-04-01`

## 一、结论

截至 `2026-04-01`，`Node A + 雷达 + 云台` 这一套硬件的核心功能已经完成闭环验证，达到“可联调、可演示、可继续集成”的阶段。

本次已经确认：

- 真实雷达数据可以进入 Node A 主链
- 轨迹可以从激活进入确认
- 云台状态可以出现 `ACQUIRING / TRACKING / LOST`
- Hunter 风险状态可以从 `IDLE` 升级到 `TRACKING / SUSPICIOUS / HIGH_RISK`
- `UPLINK,TRACK` 与 `UPLINK,EVENT` 可以正常输出
- `event_id` 可以生成并随事件上报
- 舵机手动测试、引导诊断、安全模式可以正常使用
- 模拟轨迹链路与真实雷达链路均已跑通

## 二、本次测试范围

本次测试覆盖以下两类路径：

1. 模拟轨迹注入路径
   `TRACK,x,y -> TrackManager -> HunterAction -> GimbalController -> UPLINK`
2. 真实雷达输入路径
   `RadarParser -> TrackManager -> HunterAction -> GimbalController -> UPLINK`

## 三、关键现象

### 1. 模拟轨迹闭环正常

在注入 `TRACK,320,1800` 后，观察到：

- `Hunter state changed to TRACKING`
- `Hunter state changed to SUSPICIOUS`
- `Hunter state changed to HIGH_RISK`
- `Gimbal state changed to ACQUIRING`
- `Gimbal state changed to TRACKING`
- `Gimbal state changed to LOST`

对应摘要统计：

```text
SUMMARY,node=A1,...,track_active=1,track_confirmed=1,track_lost=1,gimbal_tracking=1,gimbal_lost=1,hunter_changes=4,max_risk=65.0,...,last_event_id=A1-0000183517-0001
```

### 2. 真实雷达闭环正常

真实雷达测试中，观察到：

- `UPLINK,EVENT,...reason=TRACK_ACTIVE...`
- `Hunter state changed to TRACKING`
- `Hunter state changed to SUSPICIOUS`
- `Hunter state changed to HIGH_RISK`
- `gimbal=TRACKING`
- `capture=1`

对应摘要统计：

```text
SUMMARY,node=A1,...,track_active=4,track_confirmed=4,track_lost=4,gimbal_tracking=4,gimbal_lost=4,hunter_changes=14,max_risk=75.0,last_track=5,...,last_event_id=A1-0000653777-0005
```

这说明真实目标经过时，系统已能多次完成：

- 目标发现
- 轨迹确认
- 风险升级
- 云台跟踪
- 事件上报
- 目标丢失退出

## 四、当前状态判断

当前最准确的判断是：

- 单节点硬件功能已完整
- 当前成果适合继续作为后续云端接入、多节点协同、长期稳定性测试的基础版本
- 当前不建议在现场继续大改 `HunterAction`、`GimbalController` 或协议命名

## 五、仍需后续验证的内容

以下内容不影响“核心功能已通”的结论，但仍属于后续工程化验证项：

- 长时间连续运行稳定性
- 更复杂目标方位和进出视场场景
- 供电波动和线束扰动下的可靠性
- 冷启动后的重复一致性
- 多节点协同链路
- 云端正式接入闭环

## 六、建议后续策略

本周建议优先做“稳定性复测”，而不是继续扩硬件：

- 保持当前硬件组合不变
- 反复跑真实雷达目标进出场
- 保留 `SUMMARY` 和关键 `UPLINK,EVENT` 日志作为阶段证据
- 如非必要，不再新增主链功能

