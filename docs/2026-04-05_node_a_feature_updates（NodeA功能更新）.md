# 2026-04-05 NodeA 功能更新

## 1. 本次推进位置（对齐计划）
本次属于 `2026-04-07` 计划中的“风险分级可解释性增强”收尾项。  
目标是让系统不只输出总分，还能直接说明总分由哪些分项组成。

## 2. 本次代码改动
涉及文件：
- `lib/HunterAction/HunterAction.h`
- `lib/HunterAction/HunterAction.cpp`
- `include/SharedData.h`
- `src/main.cpp`

本次新增风险分项字段：
- `risk_base`
- `risk_persistence`
- `risk_confirmed`
- `risk_rid`
- `risk_proximity`
- `risk_motion`

并将这些字段贯通到：
- `SystemData`
- `UnifiedOutputSnapshot`
- 串口统一输出（`FLOW`、`EVENT,STATUS` 等通过统一打印函数自动带出）

## 3. 功能意义（通俗版）
以前我们只能看到“风险总分=xx”，但不容易第一时间判断是“身份问题导致”还是“距离太近导致”。  
现在每次输出都会带上分项，现场就能马上看出是哪一类因素在抬分，便于调阈值和解释误报。

## 4. 影响范围
- 不改状态机阈值和主链动作逻辑。
- 不改事件创建/关闭语义。
- 仅增强可观测性和可解释性。

## 5. 验收方式
1. 编译通过：`platformio run`  
2. 串口查看：执行 `EVENT,STATUS`，确认出现上述分项字段。  
3. 注入不同场景（例如 `RID,MISSING`）时，观察 `risk_rid` 与总分联动变化是否符合预期。

## 6. 本轮新增命令：RISK,STATUS
为了让现场联调更快定位“分数为什么变化”，新增命令：
- `RISK,STATUS`

输出重点：
- 当前风险态：`current_risk_state`
- 待切换风险态：`pending_risk_state`
- 过渡模式：`risk_transition_mode`
- 保持窗口：`risk_hold_ms / risk_hold_elapsed_ms`
- 风险总分：`risk_score`
- 风险分项：`risk_base / risk_persistence / risk_confirmed / risk_rid / risk_proximity / risk_motion`
- 当前原因位：`risk_reasons`

这条命令不改变任何控制行为，只提供快速风险诊断视图。

## 7. 4.7 收尾：参数冻结（V1）
为避免后续联调过程中频繁改口径，`2026-04-07` 阶段参数先冻结为以下版本（来源：`include/AppConfig.h`）：

风险评分参数：
- `TrackingBaseScore = 10.0`
- `PersistenceScorePerSeen = 3.0`
- `PersistenceScoreMax = 24.0`
- `ConfirmedBonusScore = 8.0`
- `RidMatchedScore = -25.0`
- `RidUnknownScore = 10.0`
- `RidMissingScore = 24.0`
- `RidSuspiciousScore = 34.0`
- `ProximityScore = 12.0`
- `MotionAnomalyScore = 12.0`
- `ProximityThresholdMm = 1500.0`
- `MotionAnomalySpeedThresholdMmS = 350.0`

风险等级阈值：
- `SuspiciousThreshold = 40.0`
- `HighRiskThreshold = 60.0`
- `EventThreshold = 80.0`

升降级保持参数：
- `SuspiciousEnterHoldMs = 120`
- `HighRiskEnterHoldMs = 250`
- `EventEnterHoldMs = 500`
- `SuspiciousExitHoldMs = 500`
- `HighRiskExitHoldMs = 700`
- `EventExitHoldMs = 900`

说明：
- 这一版作为 `4.7` 冻结基线，后续进入 `4.8` 测试日之前不再随意修改。
- 若要调整，必须先记录“改前值、改后值、原因、影响场景”。

## 8. 4.7 收尾：统一验收命令序列（现场直接执行）
建议按下面顺序执行并截图留证：

基础状态确认：
1. `RESET`
2. `STATUS`
3. `EVENT,STATUS`
4. `RISK,STATUS`

风险升级链验证（RID 缺失）：
1. `TRACK,320,1800`
2. `RID,MISSING`
3. 连续执行 `RISK,STATUS`（观察 `risk_rid`、`current/pending/transition`）
4. `EVENT,STATUS`（观察事件是否进入 `OPEN` 语义）

风险回落链验证：
1. `RID,OK`
2. 连续执行 `RISK,STATUS`（观察保持窗口后回落）
3. `EVENT,STATUS`（观察是否出现 `current_event_close_reason=RISK_DOWNGRADE`）

丢失关闭验证：
1. `TRACK,CLEAR`
2. `EVENT,STATUS`
3. `LASTEVENT`（观察 `event_close_reason=TRACK_LOST`）

重置关闭验证：
1. `TRACK,320,1800`
2. `RID,MISSING`
3. 等待进入事件态后执行 `RESET`
4. `EVENT,STATUS`
5. `LASTEVENT`（观察 `event_close_reason=RESET`）

## 9. 4.7 完成判定标准
当下面 4 条都成立时，`4.7` 判定为完成：
- 风险分级可解释：`RISK,STATUS` 可稳定输出分项与过渡状态。
- 生命周期可解释：`EVENT_OPENED / EVENT_CLOSED` 路径可观察。
- 触发与关闭原因统一：`EVENT,STATUS`、`LASTEVENT`、`UPLINK,EVENT` 语义一致。
- 参数口径冻结：使用本文件第 7 节作为联调基线。

当前状态结论：
- 代码实现：已完成
- 编译状态：已通过
- 现场验证：待按第 8 节执行并留证
