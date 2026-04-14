# 2026-04-01 Node A 新增功能汇总

## 1. 这份文档是做什么的

这份文档专门记录 `2026-04-01` 这一天在 `Node A` 上新增的功能。  
它不是总设计文档，也不是协议总表，而是“今天到底新加了什么、这些功能怎么用、解决了什么问题”的日更记录。

后续约定如下：
- 同一天内继续新增的功能，继续补到这份文档里。
- 到了新的一天，再新建一份以当天日期开头的文档。
- 建议命名格式统一为：

```text
YYYY-MM-DD_node_a_feature_updates.md
```

例如：

```text
2026-04-02_node_a_feature_updates（NodeA功能更新）.md
2026-04-03_node_a_feature_updates.md
```

---

## 2. 今天新增功能总览

今天新增能力可以分为 5 类：
1. 串口控制与调试命令补齐
2. 舵机测试与安全控制
3. 模拟轨迹与身份注入
4. 事件链与统计能力增强
5. 多节点协同骨架（HANDOVER）与可观测性增强

今天的重点不是“把算法改复杂”，而是把单节点链路做成可联调、可解释、可复盘、可验收的形态。

---

## 3. 串口控制与调试命令

### 3.1 基础命令

- `HELP`
- `STATUS`
- `SELFTEST`
- `RESET`
- `DEBUG,ON`
- `DEBUG,OFF`
- `UPLINK,ON`
- `UPLINK,OFF`

### 3.2 这组命令解决了什么问题

这组命令解决的是“现场联调没有统一入口”的问题。  
通过这些命令，可以快速回答：
- 当前支持哪些命令（`HELP`）
- 当前系统状态是什么（`STATUS`）
- 设备自检是否正常（`SELFTEST`）
- 是否需要降低本地日志噪声（`DEBUG,OFF`）
- 是否需要临时关闭上行报文（`UPLINK,OFF`）
- 是否需要把模拟运行状态恢复默认（`RESET`）

---

## 4. 舵机测试与安全控制

### 4.1 新增命令

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

### 4.2 怎么理解这组能力

- `TESTMODE`：让云台暂时脱离主链自动控制，进入手动测试模式。
- `SERVO`：控制舵机输出是否真正下发。
- `SAFE`：收紧角度范围，避免误操作触碰机械边界。
- `CENTER / PAN / TILT`：用于直接验证姿态动作是否正常。
- `DIAG,SERVO`：用于伺服联动诊断。

### 4.3 价值

可以把“主链问题”和“执行机构问题”分离排查，减少联调盲区。

---

## 5. 模拟轨迹与参数注入

### 5.1 新增命令

- `TRACK,x,y`
- `TRACK,CLEAR`
- `RID,OK`
- `RID,MISSING`
- `RID,SUSPICIOUS`
- `KP,value`
- `KD,value`

### 5.2 怎么理解这组能力

- `TRACK,x,y`：注入模拟目标坐标，验证主链闭环。
- `TRACK,CLEAR`：清除目标，验证回落逻辑。
- `RID,*`：切换身份状态，验证风险分级与事件策略。
- `KP/KD`：现场快速调参，验证云台控制响应。

### 5.3 价值

把 `TrackManager -> HunterAction -> GimbalController -> UPLINK` 这条链路做成可重复、可对比、可回归测试。

---

## 6. 上行事件与统计增强

### 6.1 新增字段与能力

- `event_id`
- `source_node`
- `event_level`
- `event_status`
- `SUMMARY`
- `SUMMARY,RESET`

### 6.2 `SUMMARY` 当前统计项

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

### 6.3 价值

让现场联调不再只靠“看滚动日志”，而是有明确统计面板用于阶段性判断。

---

## 7. 节点固定字段

### 7.1 今日固定配置

在 `include/AppConfig.h` 固定：
- `NodeId = "A1"`
- `NodeRole = "EDGE"`
- `NodeZone = "ZONE_NORTH"`

### 7.2 已接入输出

- `STATUS`
- `SELFTEST`
- `SUMMARY`
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`

### 7.3 价值

统一节点身份，方便后续多节点协同与云端归集。

---

## 8. 多节点协同骨架第一步：HANDOVER

### 8.1 已实现命令

- `HANDOVER,target_node`
- `HANDOVER,STATUS`
- `HANDOVER,CLEAR`

### 8.2 这一步不做什么

当前不是做完整双节点自动协同，不会自动控制其他节点，只先固定“接力请求的协议形态与可观测状态”。

### 8.3 当前工作方式

1. 接收 `HANDOVER,target_node` 请求  
2. 校验是否具备接力条件（活跃目标、确认状态、事件上下文）  
3. 满足条件则输出标准事件并记录接力状态

### 8.4 HANDOVER 事件关键字段

- `reason=HANDOVER`
- `event_level=INFO`
- `event_status=OPEN`
- `handover_from=A1`
- `handover_to=<target_node>`
- 以及当前 `event_id / track / hunter / gimbal / rid / risk / x / y / vx / vy`

### 8.5 接力状态查询字段

- `handover_pending`
- `handover_pending_target`
- `handover_pending_since_ms`
- `handover_last_result`
- `handover_last_target`
- `handover_last_ts`
- `handover_last_event_id`

### 8.6 典型结果

- `QUEUED`
- `IGNORED_NO_TRACK`
- `EMITTED`
- `CLEARED`

### 8.7 价值

把“接力”从概念变成可验证、可追踪、可扩展的真实接口骨架。

---

## 9. 最近事件缓存：LASTEVENT

### 9.1 已实现命令

- `LASTEVENT`
- `LASTEVENT,CLEAR`

### 9.2 解决了什么问题

`LASTEVENT` 用于快速回看“最近一次事件发生了什么”，不用翻长日志。

### 9.3 当前可查询字段

- 时间戳、`event_id`、`source_node`
- `reason`、`event_level`、`event_status`
- `track / track_active / track_confirmed`
- `hunter / gimbal / rid / risk / main_state / risk_level`
- `event_active`
- `x / y / vx / vy`
- `handover_from / handover_to`（如有）

### 9.4 价值

支持现场快速复盘和演示解释。

---

## 10. 状态/风险/事件可观测性增强

### 10.1 标准化状态字段

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

### 10.2 `main_state` 枚举

- `IDLE`
- `DETECTING`
- `TRACKING`
- `SUSPICIOUS`
- `HIGH_RISK`
- `EVENT`
- `LOST`

### 10.3 `risk_level` 枚举

- `NONE`
- `NORMAL`
- `SUSPICIOUS`
- `HIGH_RISK`
- `EVENT`

### 10.4 接入范围

- `STATUS`
- `SELFTEST`
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`
- `LASTEVENT`

### 10.5 结构化状态流日志

状态变化时输出结构化 `FLOW` 记录，便于联调定位和自动化验收。

---

## 11. 当前事件状态查询：EVENT,STATUS

### 11.1 已实现命令

- `EVENT,STATUS`

### 11.2 与 `LASTEVENT` 的区别

- `LASTEVENT`：看“最近一次事件”
- `EVENT,STATUS`：看“当前事件 + 最近事件”

### 11.3 关键输出

当前事件：
- `event_active`
- `current_event_id`
- `track_id`
- `current_event_opened_ms`

最近事件：
- `last_event_id`
- `last_reason`
- `last_event_level`
- `last_event_status`
- `last_source_node`
- `last_track_id / last_track_active / last_track_confirmed`
- `last_hunter_state / last_gimbal_state / last_rid_status`
- `last_risk_score / last_main_state / last_risk_level`
- `last_x / last_y / last_vx / last_vy`
- `last_ts`
- `last_handover_from / last_handover_to`

### 11.4 价值

让“当前态”和“最近历史态”同屏可见，支持闭环解释。

---

## 12. 今日新增命令总表

```text
HELP
STATUS
SELFTEST
RESET
DEBUG,ON / DEBUG,OFF
UPLINK,ON / UPLINK,OFF
TESTMODE,ON / TESTMODE,OFF
SERVO,ON / SERVO,OFF
SAFE,ON / SAFE,OFF
CENTER
PAN,angle
TILT,angle
DIAG,SERVO / DIAG,STOP
TRACK,x,y / TRACK,CLEAR
RID,OK / RID,MISSING / RID,SUSPICIOUS
KP,value / KD,value
SUMMARY / SUMMARY,RESET
HANDOVER,target_node / HANDOVER,STATUS / HANDOVER,CLEAR
LASTEVENT / LASTEVENT,CLEAR
EVENT,STATUS
```

---

## 13. 建议的基础验收顺序

```text
1) HELP
2) STATUS
3) SELFTEST
4) TESTMODE,ON + SERVO,ON + CENTER/PAN/TILT
5) TRACK,x,y + RID,OK/RID,SUSPICIOUS
6) EVENT,STATUS + LASTEVENT
7) HANDOVER,target_node + HANDOVER,STATUS
8) SUMMARY
9) QUIET,ON（如需低噪声演示）
```

验收关注点：
- 状态字段是否完整
- 事件是否可创建、可关闭、可回看
- 接力状态是否有明确结果
- 统计是否持续累加

---

## 14. 这批功能的阶段意义

这批更新的意义不是“项目已完成”，而是单节点链路进入了“可运行、可观测、可说明、可验收”的稳定阶段，为后续双节点协同和云端对接打基础。

---

## 15. 今日补充更新：SUMMARY 增强

### 15.1 增强内容

在原有 `SUMMARY` 基础上，增加三类累计统计：
- 风险等级统计
- 事件生命周期统计
- 接力结果统计

### 15.2 新增字段

- `risk_suspicious`
- `risk_high_risk`
- `risk_event`
- `event_opened`
- `event_closed`
- `handover_queued`
- `handover_emitted`
- `handover_ignored`

### 15.3 字段解释

风险等级统计：
- `risk_suspicious`：进入 `SUSPICIOUS` 的累计次数
- `risk_high_risk`：进入 `HIGH_RISK` 的累计次数
- `risk_event`：进入 `EVENT` 的累计次数

事件生命周期统计：
- `event_opened`：事件创建次数
- `event_closed`：事件关闭次数

接力结果统计：
- `handover_queued`：接力进入队列次数
- `handover_emitted`：接力真正发出次数
- `handover_ignored`：接力被忽略次数

### 15.4 价值

`SUMMARY` 从“运行计数”升级为“联调记分板”，支持更快验收和复盘。

### 15.5 推荐验收方式

```text
SUMMARY,RESET
TRACK,x,y
RID,SUSPICIOUS
RID,OK
HANDOVER,target_node
SUMMARY
```

观察统计字段是否随状态变化而正确累加。

---

## 16. 今日补充更新：QUIET 日志模式

### 16.1 新增命令

- `QUIET,ON`
- `QUIET,OFF`

### 16.2 与 `DEBUG` 的区别

- `DEBUG`：控制调试细节输出量
- `QUIET`：控制整体日志噪声，保留骨干日志

### 16.3 `QUIET,ON` 当前行为

默认抑制高频噪声日志（如高频 `DATA/STATE/GIMBAL`），保留关键输出：
- 命令响应
- `STATUS`
- `SELFTEST`
- `SUMMARY`
- `LASTEVENT`
- `EVENT,STATUS`
- `HANDOVER,STATUS`
- `UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT`
- `FLOW,trigger=...`

### 16.4 推荐验收方式

```text
DEBUG,ON
QUIET,ON
TRACK,x,y
RID,SUSPICIOUS
EVENT,STATUS
QUIET,OFF
```

验证要点：
- `QUIET,ON` 后日志显著更干净
- 关键事件和状态输出仍保留
- `QUIET,OFF` 后高频日志恢复
