# 2026-04-04 NodeA 功能更新

## 1. 测试结果绑定参数快照

这一步把“测试结果”和“当时使用的关键参数”绑到了一起，便于后面做真实联调时复盘。

当前每轮结果里已经会固化这些关键字段：

- `predictor_kp`
- `predictor_kd`
- `heartbeat_ms`
- `event_report_ms`
- `sim_hold_ms`
- `debug_enabled`
- `quiet_enabled`
- `uplink_enabled`
- `final_gimbal_state`
- `final_risk_score`

对应网页侧，测试结果详情里也已经可以直接看到这一轮使用的参数快照和运行开关。

## 2. 对齐 2026-04-06：统一主链状态与输出字段

这一块是按你 `2026-04-06` 的计划提前落的代码地基，目标是把主链边界、状态命名和长期保留字段固定下来。

### 2.1 正式固定的主状态

- `IDLE`
- `DETECTING`
- `TRACKING`
- `SUSPICIOUS`
- `HIGH_RISK`
- `EVENT`
- `LOST`

### 2.2 正式固定的风险等级

- `NONE`
- `NORMAL`
- `SUSPICIOUS`
- `HIGH_RISK`
- `EVENT`

### 2.3 新增统一输出快照

代码里已经增加 `UnifiedOutputSnapshot`，把当前输出统一围绕同一套字段组织，包括：

- `main_state`
- `risk_level`
- `hunter_state`
- `gimbal_state`
- `rid_status`
- `track_id`
- `track_active`
- `track_confirmed`
- `x / y / vx / vy`
- `risk_score`
- `trigger_flags`
- `vision_state`
- `vision_locked`
- `capture_ready`
- `uplink_state`
- `event_active`
- `event_id`
- `timestamp`

### 2.4 已接入的输出口

这套统一快照已经接进：

- `FLOW`
- `HANDOVER,STATUS`
- `EVENT,STATUS`
- `STATUS`
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`
- `LASTEVENT`

这样后面继续推进时，主链、视觉、网页端都会围绕同一套稳定字段走，不再到处各叫各的。

## 3. 对齐 2026-04-06：主链日志清理

这一块对应你 `2026-04-06` 里“清理串口打印、让日志能看懂、能回放、能解释”的要求。

### 3.1 当前日志角色收口

- `FLOW`
  继续作为主链过程回放日志保留
- `STATE`
  以状态变化优先，必要时才打脉冲日志
- `GIMBAL`
  以云台状态变化优先，必要时才打脉冲日志
- `DATA`
  只在目标活跃且输出有意义时打印

### 3.2 新增解释字段

`STATE` 和 `GIMBAL` 日志里已经加上：

- `reason=STATE_CHANGE`
- `reason=STATE_PULSE`

这样后面回看串口时，不只是看到一堆打印，还能直接看出这条日志是“发生了真实变化”，还是“定期保活补打一条”。

## 4. 对齐 2026-04-07：事件对象结构正式化

这一块是按你 `2026-04-07` 的计划先落的第一层地基。目标不是先重写风险公式，而是先把“事件对象”正式建立起来。

### 4.1 新增正式事件对象

代码里已经新增：

- `EventState`
- `EventObject`

当前事件对象至少包含这些正式字段：

- `event_id`
- `node_id`
- `track_id`
- `risk_score`
- `risk_level`
- `risk_reason_flags`
- `trigger_flags`
- `rid_status`
- `start_time_ms`
- `last_x_mm`
- `last_y_mm`
- `last_vx_mm_s`
- `last_vy_mm_s`
- `event_state`

### 4.2 当前作用

现在系统里的“事件”不再只是几个零散状态，而是开始有一个真正的当前事件对象。

这意味着后面继续推进：

- 风险升级
- 风险回落
- 事件上云
- 网页事件展示
- 抓拍与事件绑定

时，都可以围绕这一个正式对象读写。

## 5. 对齐 2026-04-07：风险分级规则与升降级保持机制

这一块是 `2026-04-07` 计划里的第二层主体，本次已经完成第一版可运行实现，并且编译通过。

### 5.1 当前风险评分来源

现在 `HunterAction` 里的风险分数不再只是粗略阈值，而是由几项可解释规则叠加得到：

- 轨迹持续时间
- 轨迹已确认
- RID 状态
- 近距接近
- 速度异常

对应的风险原因会通过 `risk_reason_flags` 保存下来。

### 5.2 当前已支持的风险原因

- `TRACK_PERSISTENT`
- `TRACK_CONFIRMED`
- `RID_MATCHED`
- `RID_UNKNOWN`
- `RID_MISSING`
- `RID_SUSPICIOUS`
- `PROXIMITY`
- `MOTION_ANOMALY`

### 5.3 当前升降级机制

现在 `HunterAction` 里已经增加了显式的进入保持和退出保持：

- `SuspiciousEnterHoldMs`
- `HighRiskEnterHoldMs`
- `EventEnterHoldMs`
- `SuspiciousExitHoldMs`
- `HighRiskExitHoldMs`
- `EventExitHoldMs`

作用是：

- 不让风险等级刚碰阈值就瞬间乱跳
- 不让事件态一掉一点点分数就立刻回落
- 给后面真实联调留出更稳定的观察窗口

### 5.4 当前输出侧同步

这次不仅把风险规则做进了 `HunterAction`，也把解释结果一路带到了输出层：

- `SystemData.risk_reason_flags`
- `UnifiedOutputSnapshot.risk_reason_flags`
- `EventObject.risk_reason_flags`
- `EVENT,STATUS` 的 `current_event_risk_reasons`

也就是说，后面你查状态时，不只知道“分数是多少”，还开始能看到“为什么会到这个分数”。

## 6. 当前结论

截至今天这份文档更新时，已经完成了：

- 参数快照绑定测试结果
- 对齐 `2026-04-06` 的主状态/字段统一
- 对齐 `2026-04-06` 的主链日志清理
- 对齐 `2026-04-07` 的事件对象正式化
- 对齐 `2026-04-07` 的第一版可解释风险评分与升降级保持机制

而且主工程已再次通过编译。

## 7. 对齐 2026-04-07：事件对象生命周期

这一小步继续补的是 `2026-04-07` 里“事件对象真正建立起来”的后半部分。

之前事件对象虽然已经有结构了，但在事件关闭后会直接被清空。现在已经改成：

- 事件存在时：`event_state=OPEN`
- 事件关闭后：保留最后一份对象快照，并转成 `event_state=CLOSED`

这意味着后面你查 `EVENT,STATUS` 时，不只知道当前有没有活跃事件，还能看到刚刚关闭的那一个事件对象最后停在什么状态。

当前同步补上的字段包括：

- `current_event_object_id`
- `current_event_state`
- 关闭时最后一次的
  - `risk_score`
  - `risk_level`
  - `risk_reasons`
  - `rid_status`
  - `last_x / last_y / last_vx / last_vy`

这样事件链就开始更像真正的“对象生命周期”，而不是一关闭就只剩一个布尔值。

## 8. 对齐 2026-04-07：事件按风险态创建与关闭

这一小步继续把 `2026-04-07` 的“系统从检测器走向研判器”往前推了一层。

之前事件创建条件还是偏宽，只要轨迹 `confirmed + active` 就会创建事件上下文。现在已经收紧成：

- 轨迹必须 `active`
- 轨迹必须 `confirmed`
- 风险等级必须已经进入
  - `SUSPICIOUS`
  - `HIGH_RISK`
  - `EVENT`

也就是说，普通已确认目标不再自动被当作事件对象。

### 8.1 新增的事件语义

当前事件生命周期里已经补上了两类更明确的语义事件：

- `EVENT_OPENED`
- `EVENT_CLOSED`

其中：

- 当目标第一次进入风险态时，会创建事件并输出 `EVENT_OPENED`
- 当目标仍然活跃，但已经从风险态回落到正常态时，会输出 `EVENT_CLOSED`
- 如果目标直接丢失，则仍然由原来的 `TRACK_LOST` 路径收口

### 8.2 这一小步的意义

这一步很关键，因为它把“事件对象存在”这件事和“风险已经达到值得立案的程度”真正绑定起来了。

这样后面继续推进：

- 风险升级链
- 事件链
- 上云事件记录
- 网页事件留痕

时，事件不再是“只要有 confirmed 目标就开”，而是开始更像真正的研判结果。

## 9. 对齐 2026-04-07：风险过渡可观测性（确认/保持/缓降）

这一步继续落 `2026-04-07` 里“确认、保持、缓降”的可解释能力。逻辑本身之前已经有了，这次补的是可观测输出。

### 9.1 Hunter 输出新增字段

`HunterOutput` 现在会额外输出：

- `pending_state`
- `state_since_ms`
- `pending_since_ms`
- `transition_mode`（`STABLE / ENTER_HOLD / EXIT_HOLD`）
- `transition_hold_ms`
- `transition_elapsed_ms`

### 9.2 主链统一快照已接线

这些字段已经接进 `SystemData` 和 `UnifiedOutputSnapshot`，并进入统一输出：

- `pending_risk_state`
- `risk_transition_mode`
- `risk_state_since_ms`
- `risk_pending_since_ms`
- `risk_hold_ms`
- `risk_hold_elapsed_ms`

### 9.3 EVENT,STATUS 增强调试语义

`EVENT,STATUS` 里新增了更直白的别名字段，便于现场判断：

- `current_risk_state`
- `current_pending_risk_state`
- `current_risk_transition_mode`

这样你后面看到“分数已到但状态未切换”时，可以直接判断它是不是还在 `ENTER_HOLD`，而不是靠猜。

## 10. 对齐 2026-04-07：事件触发原因语义统一

这一步是把事件解释口径继续收口，重点解决“`EVENT,STATUS`、`UPLINK,EVENT`、`LASTEVENT` 看起来像三套解释”的风险。

### 10.1 触发标志补齐

在原有触发标志基础上新增了两项：

- `PROXIMITY`
- `MOTION_ANOMALY`

这两项由风险原因位 `risk_reason_flags` 驱动，和 `ALERT / CAPTURE / RID_MISSING / RID_SUSPICIOUS` 一起组成统一触发语义。

### 10.2 新增标准化触发原因输出

新增了统一的 `event_trigger_reasons` 输出字段，当前会按同一顺序输出：

- `RID_MISSING`
- `RID_SUSPICIOUS`
- `PROXIMITY`
- `MOTION_ANOMALY`
- `ALERT`
- `CAPTURE`

并且已经接进：

- `UPLINK,EVENT`
- `EVENT,STATUS`（`current_event_trigger_reasons`）
- `LASTEVENT`（`event_trigger_reasons`）

### 10.3 事件对象触发标志来源统一

`EventObject.trigger_flags` 现在统一由 `computeTriggerFlags(snapshot)` 生成，不再混用快照里可能未更新的中间值。

这样后面上云、网页和本地串口在解释“为什么触发事件”时，语义来源是一致的。

## 11. 对齐 2026-04-07：事件关闭原因语义统一

这一步继续补齐“可解释事件对象”的最后一块：不仅解释“为什么触发”，还要解释“为什么关闭”。

### 11.1 关闭原因字段

新增并打通了 `event_close_reason` 语义，当前至少覆盖：

- `RISK_DOWNGRADE`
- `TRACK_LOST`
- `RESET`

### 11.2 输出链路统一

关闭原因已经接进三条主要输出：

- `UPLINK,EVENT`（事件消息里带 `event_close_reason`）
- `EVENT,STATUS`（`current_event_close_reason`）
- `LASTEVENT`（`event_close_reason`）

### 11.3 运行时对象同步

`EventObject` 增加了 `close_reason`，并在关闭路径上同步：

- 风险回落关闭：`RISK_DOWNGRADE`
- 轨迹丢失关闭：`TRACK_LOST`
- 手动重置关闭：`RESET`

这样后面无论你看串口、网页还是上云事件，关闭原因都可以对得上同一套语义。
