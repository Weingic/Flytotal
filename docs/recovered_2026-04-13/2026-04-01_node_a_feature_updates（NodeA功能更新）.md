# 2026-04-01 Node A 新增功能汇��?
## 1. 这份文档是做仢�么的

这份文档专门记录 `2026-04-01` 这一天在 `Node A` 上新增的功能�?
它不是��设计文档，也不是协议��表，��是“今天到底新加了仢�么��这些功能��么用��解决了仢�么问题��的日更记录�?
后续约定如下�?
- 同一天内继续新增的功能，继续补到这份文档里��?- 到了新的丢�天，再新建一份以当天日期弢�头的文档�?- 建议命名格式统一为：

```text
YYYY-MM-DD_node_a_feature_updates.md
```

例如�?
```text
2026-04-02_node_a_feature_updates��NodeA���ܸ��£�.md
2026-04-03_node_a_feature_updates.md
```

---

## 2. 今天新增功能总览

今天新增的功能，按作用可以分�?5 类：

1. 串口控制与调试命令补�?2. 舵机测试与安全控�?3. 上行事件与最近事件查�?4. 多节点协同骨架与接力状��查�?5. 状��?风险/事件可观测��增�?
今天的重点不是改主链算法，��是把单节点主链做成�?
- 能测
- 能看�?- 能回�?- 能解�?- 能为下阶段协同和云端集成做准�?
---

## 3. 串口控制与调试命�?
### 3.1 基础命令

今天已补齐以下基硢�命令�?
- `HELP`
- `STATUS`
- `SELFTEST`
- `RESET`
- `DEBUG,ON`
- `DEBUG,OFF`
- `UPLINK,ON`
- `UPLINK,OFF`

### 3.2 这些命令解决了什么问�?
这些命令解决的是“现场联调时没有统一入口”的问题�?
以前如果只靠看刷屏日志，很多状��不容易丢�下确认��现在可以：

- �?`HELP` 看当前支持哪些命�?- �?`STATUS` 看系统当前状�?- �?`SELFTEST` 做一版更完整的自棢�输出
- �?`DEBUG,OFF` 压掉本地调试输出，只保留必要输出
- �?`UPLINK,OFF` 临时关闭上行报文，单独观察本地行�?- �?`RESET` 把模拟输入��接力请求��最近事件缓存等运行状��恢复到默认�?
---

## 4. 舵机测试与安全控�?
### 4.1 新增命令

今天已实现：

- `TESTMODE,ON`
- `TESTMODE,OFF`
- `SERVO,ON`
- `SERVO,OFF`
- `SAFE,ON`
- `SAFE,OFF`
- `CENTER`
- `PAN,angle`
- `TILT,angle`
- `DIAG,SERVO`
- `DIAG,STOP`

### 4.2 这些功能怎么理解

这些功能不是为了让系统长期工作在手动模式，��是为了把��云台本体是否正常��从主链里拆出来单独棢�查��?
你可以把它理解成三层�?
- `TESTMODE`
  让云台暂时不跟主链自动控制，改为吃手动角�?- `SERVO`
  控制舵机输出是否真正下发
- `SAFE`
  把角度范围收紧，避免现场误操作打到机械边�?
再往上是两种具体动作�?
- `CENTER / PAN / TILT`
  直接手动给角�?- `DIAG,SERVO`
  跑一套预先写好的小幅动作序列，用来观察抖动��卡顿��机械偏载��电源问�?
### 4.3 价��?
这部分让你能先确认：

- 是主链问�?- 还是舵机/供电/结构问题

这对现场排障很重要��?
---

## 5. 模拟轨迹与参数注�?
### 5.1 新增命令

今天已实现：

- `TRACK,x,y`
- `TRACK,CLEAR`
- `RID,OK`
- `RID,MISSING`
- `RID,SUSPICIOUS`
- `KP,value`
- `KD,value`

### 5.2 这些功能怎么理解

这一组功能是为了让你在没有真实雷达输入��或者还不想丢�上来碰硬件时，也能把主链跑起来��?
- `TRACK,x,y`
  直接注入丢�个模拟目标坐�?- `TRACK,CLEAR`
  清掉模拟目标
- `RID,*`
  手动指定身份状��?- `KP / KD`
  动��修改预测器参数，用来调试跟踪响�?
### 5.3 价��?
这组命令�?`TrackManager -> HunterAction -> GimbalController -> UPLINK` 可以被拆弢�测��反复测、对比测�?
---

## 6. 上行事件与统计增�?
### 6.1 新增字段/能力

今天已接入：

- `event_id`
- `source_node`
- `event_level`
- `event_status`
- `SUMMARY`
- `SUMMARY,RESET`

### 6.2 `SUMMARY` 当前统计�?
当前 `SUMMARY` 会输出：

- `track_active`
- `track_confirmed`
- `track_lost`
- `gimbal_tracking`
- `gimbal_lost`
- `hunter_changes`
- `max_risk`
- `last_track`
- `last_x`
- `last_y`
- `last_event_id`

### 6.3 这组能力解决了什么问�?
它解决的是��现场感觉好像跑通了，但缺少累计证据”的问题�?
现在你不只看瞬时输出，还能看�?
- 今天这次测试里目标一共激活了几次
- 确认了几�?- 丢失了几�?- 云台进入跟踪/丢失了几�?- 朢�大风险分是多�?- 朢�后一次事件号是什�?
这样更��合做联调记录和演示支撑�?
---

## 7. 节点固定字段

### 7.1 今天新增配置

�?`include/AppConfig.h` 中固定了�?
- `NodeId = "A1"`
- `NodeRole = "EDGE"`
- `NodeZone = "ZONE_NORTH"`

### 7.2 已接入输�?
这些字段已进入：

- `STATUS`
- `SELFTEST`
- `SUMMARY`
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`

### 7.3 价��?
它的价��是让同丢�套输出从“单板调试信息��开始向“多节点/云端可识别对象��过渡��?
---

## 8. 多节点协同骨架第丢�步：HANDOVER

### 8.1 已实现命�?
今天已实现：

- `HANDOVER,target_node`

后续又补充了�?
- `HANDOVER,STATUS`
- `HANDOVER,CLEAR`

### 8.2 这不是在做什�?
这一步不是：

- 自动控制 A2
- 自动切换目标归属
- 做完整双节点联动

它只是先把��接力事件��标准化�?
### 8.3 它具体��么工作

当你输入�?
```text
HANDOVER,A2
```

系统不是立刻无条件发事件，��是先把这个请求排队�?
之后�?`CloudTask` 看当前目标是否满足条件：

- 有活跃目�?- 目标已确�?- 当前有有效事件上下文

只有满足这些条件，才会正式发丢�条：

```text
UPLINK,EVENT ... reason=HANDOVER
```

如果条件不满足，就不会乱发空接力事件�?
### 8.4 当前 `HANDOVER` 事件会带仢��?
当前会带�?
- `reason=HANDOVER`
- `event_level=INFO`
- `event_status=OPEN`
- `handover_from=A1`
- `handover_to=目标节点`
- 当前 `event_id`
- 当前 `track`
- 当前 `hunter`
- 当前 `gimbal`
- 当前 `rid`
- 当前 `risk`
- 当前 `x / y / vx / vy`

### 8.5 后来补上的接力状态查�?
为了避免现场看不清接力是否真的发出去，今天又补了接力状��查诃6�9��?
现在可以看到�?
- `handover_pending`
- `handover_pending_target`
- `handover_pending_since_ms`
- `handover_last_result`
- `handover_last_target`
- `handover_last_ts`
- `handover_last_event_id`

### 8.6 当前接力状��的典型结果

典型结果有：

- `QUEUED`
  命令已排队，还没正式发出
- `IGNORED_NO_TRACK`
  当前没有合格目标，所以请求被忽略
- `EMITTED`
  已正式发出接力事�?- `CLEARED`
  待发请求已手动清�?
### 8.7 价��?
这一部分的价值不是��协同已完成”，而是�?
- 接力动作弢�始有统一格式
- 接力请求弢�始可观察
- 以后做双节点联动时，不用再重定义第一�?
---

## 9. 朢�近事件缓存：LASTEVENT

### 9.1 已实现命�?
今天已实现：

- `LASTEVENT`
- `LASTEVENT,CLEAR`

### 9.2 它解决了仢�么问�?
现场联调时，事件输出会刷得很快��?
如果你刚好错过一条关键事件，就得徢�回翻很多日志，非常费时间�?
`LASTEVENT` 的作用就是：

- 缓存朢�近一次事�?- 随时丢�条命令直接查

### 9.3 当前能查到什�?
当前 `LASTEVENT` 能查到：

- 朢�近事件时�?- `event_id`
- `source_node`
- `reason`
- `event_level`
- `event_status`
- `track`
- `track_active`
- `track_confirmed`
- `hunter`
- `gimbal`
- `rid`
- `risk`
- `main_state`
- `risk_level`
- `event_active`
- `x / y / vx / vy`
- `handover_from / handover_to`（如果是接力事件�?
### 9.4 价��?
这个功能非常适合现场快��回看：

- 刚才到底触发了什么事�?- 是普通轨迹事件还�?`HANDOVER`
- 它当时的状��和风险等级是什�?
---

## 10. 状��?风险/事件可观测��增�?
### 10.1 今天新增的标准化状��字�?
今天为了固定单节点主链边界，又新增了这些标准化字段：

- `main_state`
- `hunter_state`
- `gimbal_state`
- `rid_status`
- `track_id`
- `track_active`
- `track_confirmed`
- `risk_score`
- `risk_level`
- `event_active`
- `current_event_id`

### 10.2 `main_state` 是��么来的

它不是新的内部状态机，��是对当前系统状态做的一层统丢�解释�?
当前对外统一使用�?
- `IDLE`
- `DETECTING`
- `TRACKING`
- `SUSPICIOUS`
- `HIGH_RISK`
- `EVENT`
- `LOST`

这样做的目的，是避免出现“内部这样叫、输出那样叫、文档又另一套叫法��的混乱�?
### 10.3 `risk_level` 是��么理解�?
它是对当前风险分和状态做的一层更直观的解释��?
当前输出级别为：

- `NONE`
- `NORMAL`
- `SUSPICIOUS`
- `HIGH_RISK`
- `EVENT`

这比单看丢�个浮点分数更容易现场判断�?
### 10.4 这些字段已接入哪�?
当前已接入：

- `STATUS`
- `SELFTEST`
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`
- `LASTEVENT`

### 10.5 新增结构化状态流日志

今天还新增了�?
```text
FLOW,trigger=hunter,...
FLOW,trigger=gimbal,...
```

这类日志的作用是�?
- �?`Hunter` 状��变化时，打丢�条结构化状��流
- �?`Gimbal` 状��变化时，也打一条结构化状��流

它比原来的普通提示语更��合回放和对照��?
---

## 11. 当前事件状��查询：EVENT,STATUS

### 11.1 已实现命�?
今天朢�后新增了�?
- `EVENT,STATUS`

### 11.2 它和 `LASTEVENT` 的区�?
`LASTEVENT` 回答的是�?
- 朢�近一次事件是仢��?
`EVENT,STATUS` 回答的是两件事：

1. 现在有没有活跃事�?2. 朢�近一次事件快照是仢��?
也就是说，它把��当前事件上下文”和“最近事件记录��放在一条输出里丢�起给你��?
### 11.3 当前会输出什�?
当前会输出：

- 当前是否有事�?`event_active`
- 当前事件�?`current_event_id`
- 当前事件对应�?`track_id`
- 当前事件打开时间 `current_event_opened_ms`

同时也会带最近一次事件快照：

- `last_event_id`
- `last_reason`
- `last_event_level`
- `last_event_status`
- `last_source_node`
- `last_track_id`
- `last_track_active`
- `last_track_confirmed`
- `last_hunter_state`
- `last_gimbal_state`
- `last_rid_status`
- `last_risk_score`
- `last_main_state`
- `last_risk_level`
- `last_x / last_y / last_vx / last_vy`
- `last_ts`
- `last_handover_from / last_handover_to`

### 11.4 价��?
它解决的是��当前事件上下文”和“最近一条事件缓存��需要来回切命令的问题��?
现在丢�条命令就能同时回答：

- 当前事件链有没有活着
- 朢�近一次真正发生的事件是什�?
---

## 12. 今天新增命令总表

今天新增/完善的命令汇总如下：

- `HELP`
- `STATUS`
- `SELFTEST`
- `RESET`
- `DEBUG,ON`
- `DEBUG,OFF`
- `UPLINK,ON`
- `UPLINK,OFF`
- `TESTMODE,ON`
- `TESTMODE,OFF`
- `SERVO,ON`
- `SERVO,OFF`
- `SAFE,ON`
- `SAFE,OFF`
- `CENTER`
- `PAN,angle`
- `TILT,angle`
- `DIAG,SERVO`
- `DIAG,STOP`
- `TRACK,x,y`
- `TRACK,CLEAR`
- `RID,OK`
- `RID,MISSING`
- `RID,SUSPICIOUS`
- `KP,value`
- `KD,value`
- `SUMMARY`
- `SUMMARY,RESET`
- `HANDOVER,target_node`
- `HANDOVER,STATUS`
- `HANDOVER,CLEAR`
- `LASTEVENT`
- `LASTEVENT,CLEAR`
- `EVENT,STATUS`

---

## 13. 建议的基硢�验收顺序

如果后面要快速确认今天新增能力是否都还正常，建议按下面顺序测�?
```text
HELP
STATUS
SELFTEST
TRACK,320,1800
STATUS
EVENT,STATUS
LASTEVENT
HANDOVER,A2
HANDOVER,STATUS
LASTEVENT
SUMMARY
TRACK,CLEAR
EVENT,STATUS
LASTEVENT
```

重点观察�?
- `STATUS` 里是否能看到统一状��字�?- `EVENT,STATUS` 是否能同时反映当前事件和朢�近事�?- `HANDOVER,STATUS` 是否能看到接力排�?发出结果
- `LASTEVENT` 是否能回看最近事�?- `SUMMARY` 是否能累计统计本次测试过�?
---

## 14. 今天这批功能的阶段意�?
今天新增的这些内容，整体意义不是“项目已经完全做完��，而是�?`Node A + 雷达 + 云台` 这条单节点链路推进到了一个更稳的阶段�?
- 不只是能�?- 还能更清楚地解释为什么在�?- 不只是能触发
- 还能更清楚地回看触发了什�?- 不只是有协同想法
- 还先把协同骨架的事件和状态格式固定下�?
对当前阶段来说，这些增强非常适合作为后面继续做：

- 风险分级细化
- 标准测试脚本
- 云端事件留痕
- 双节点协�?
之前的��稳定底座����?
---

## 15. 今天补充更新：SUMMARY 增强

### 15.1 这次增强了什�?
在原�?`SUMMARY` 的基硢�上，今天又补了三类累计统计：

- 风险等级统计
- 事件生命周期统计
- 接力结果统计

### 15.2 新增统计�?
当前新增字段为：

- `risk_suspicious`
- `risk_high_risk`
- `risk_event`
- `event_opened`
- `event_closed`
- `handover_queued`
- `handover_emitted`
- `handover_ignored`

### 15.3 这些字段怎么理解

#### 风险等级统计

- `risk_suspicious`
  进入 `SUSPICIOUS` 的累计次�?- `risk_high_risk`
  进入 `HIGH_RISK` 的累计次�?- `risk_event`
  进入 `EVENT` 的累计次�?
它们回答的是�?
- 本轮测试里系统一共升级过几次
- 升级主要停留在哪丢��?
#### 事件生命周期统计

- `event_opened`
  事件上下文被创建的次�?- `event_closed`
  事件上下文被关闭的次�?
它们回答的是�?
- 这轮测试里真正形成过多少个事�?- 这些事件有没有正常结�?
#### 接力结果统计

- `handover_queued`
  接力请求被排队的次数
- `handover_emitted`
  接力事件真正发出的次�?- `handover_ignored`
  因为没有合格目标而被忽略的次�?
它们回答的是�?
- 你到底发起过几次接力
- 真正成功发出去几�?- 有几次是因为条件不满足��没发成

### 15.4 为什么这次增强有意义

之前�?`SUMMARY` 更偏向��轨迹和云台跑了几次”��?
这次增强之后，`SUMMARY` 更像丢�张测试记分板。你做完丢�轮联调，不用翻日志去手数�?
- 丢�共进过几次可疑��?- 丢�共升过几次高风险
- 丢�共形成过几次事件
- 接力到底发出去过几次

### 15.5 推荐验收方法

建议这样测：

```text
SUMMARY,RESET
SUMMARY
TRACK,320,1800
RID,MISSING
SUMMARY
HANDOVER,A2
HANDOVER,STATUS
SUMMARY
TRACK,CLEAR
SUMMARY
```

重点看：

- `risk_suspicious / risk_high_risk / risk_event` 是否随状态升级累�?- `event_opened / event_closed` 是否随事件创建和结束变化
- `handover_queued / handover_emitted / handover_ignored` 是否能反映接力实际结�?
---

## 16. 今天补充更新：QUIET 日志模式

### 16.1 新增命令

今天补充新增�?
- `QUIET,ON`
- `QUIET,OFF`

### 16.2 它和 `DEBUG` 的区�?
现在日志控制分成两层�?
- `DEBUG`
  控制高频本地调试输出
- `QUIET`
  控制是否进入“安静联调模式��?
通俗理解�?
- `DEBUG,ON`
  看得朢�细，适合排故
- `QUIET,ON`
  压掉高频噪声，更适合联调和录�?
### 16.3 当前行为

进入 `QUIET,ON` 后：

- `DATA`
- 高频 `STATE`
- 高频 `GIMBAL`

这类高频本地输出会被压掉�?
但这些关键输出仍然保留：

- 命令响应
- `STATUS`
- `SELFTEST`
- `SUMMARY`
- `LASTEVENT`
- `EVENT,STATUS`
- `HANDOVER,STATUS`
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`
- `FLOW,trigger=...`

也就是说，`QUIET` 不是“静音��，而是“只保留关键骨干日志”��?
### 16.4 推荐验收方式

```text
HELP
QUIET,ON
TRACK,320,1800
RID,MISSING
HANDOVER,A2
SUMMARY
LASTEVENT
QUIET,OFF
DEBUG,ON
TRACK,320,1800
```

预期现象�?
- `QUIET,ON` 后日志明显更干净
- 关键事件输出仍然保留
- `QUIET,OFF` 后如�?`DEBUG` 仍开，高频调试输出恢�?
