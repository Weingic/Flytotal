# Node A 状态机说明

本文档用于说明当前 `Node A` 中两个最核心的状态机：

- 云台状态机 `GimbalController`
- 风险研判状态机 `HunterAction`

（功能：
这一步不是新增程序能力，而是把“状态切换逻辑”显式整理出来。）

（目的：
让你后面接硬件时知道状态为什么切换
方便你自己讲解项目逻辑
为后面的比赛材料、执行书、答辩图做准备）


说明：
- 本文档只描述当前代码中已经实现的状态与转移关系。
- 所有描述均基于当前 `lib/GimbalController/GimbalController.cpp` 与 `lib/HunterAction/HunterAction.cpp` 的实际逻辑。

## 一、云台状态机

当前云台状态机共有 4 个状态：

- `SCANNING`
- `ACQUIRING`
- `TRACKING`
- `LOST`

### 1. SCANNING

含义：
- 默认待机扫描状态
- 云台左右巡航，等待可确认目标出现

当前输出行为：
- `pan_angle` 在中心角附近做周期性摆动
- `tilt_angle` 保持在中心位

进入条件：
- 上电初始化默认进入
- `LOST` 状态超时后回到该状态
- `ACQUIRING` 状态下目标丢失后回到该状态

退出条件：
- 当 `track.is_confirmed == true` 时，进入 `ACQUIRING`

### 2. ACQUIRING

含义：
- 已经发现确认目标，准备正式进入跟踪

当前输出行为：
- 保持当前预测器输出角度

进入条件：
- `SCANNING` 状态中检测到 `has_target == true`

退出条件：
- 如果目标继续存在，且停留时间超过 `AcquireConfirmMs`，进入 `TRACKING`
- 如果目标消失，则返回 `SCANNING`

### 3. TRACKING

含义：
- 正式跟踪状态

当前输出行为：
- `pan_angle` 由预测器根据目标坐标计算
- `tilt_angle` 根据目标距离映射得到
- 若目标存在，则持续刷新 `last_target_seen_ms`

进入条件：
- `ACQUIRING` 状态下目标连续保持超过确认时间
- `LOST` 状态下重新找回目标

退出条件：
- 如果目标消失，则进入 `LOST`

### 4. LOST

含义：
- 目标刚刚丢失，但系统仍尝试短时恢复

当前输出行为：
- 保持当前预测器角度，不立即回到扫描

进入条件：
- `TRACKING` 状态下目标消失

退出条件：
- 如果目标重新出现，则回到 `TRACKING`
- 如果超出 `LostRecoveryTimeoutMs` 仍未恢复，则回到 `SCANNING`

## 二、云台状态机转移图

```text
SCANNING
  | 目标已确认
  v
ACQUIRING
  | 保持确认超过 AcquireConfirmMs
  v
TRACKING
  | 目标丢失
  v
LOST
  | 目标恢复 ----------------------> TRACKING
  | 超过 LostRecoveryTimeoutMs ----> SCANNING

ACQUIRING
  | 目标丢失
  v
SCANNING
```

## 三、云台状态机关键判断条件

当前 `GimbalController` 使用的核心判断量是：

- `has_target = track.is_confirmed`

这意味着：
- 不是“只要看到目标就跟踪”
- 而是“轨迹经过确认后才进入真正的跟踪流程”

这对降低误报和避免云台乱动是有帮助的。

## 四、Hunter 风险研判状态机

当前 Hunter 状态机共有 6 个状态：

- `IDLE`
- `TRACKING`
- `RID_MATCHED`
- `SUSPICIOUS`
- `HIGH_RISK`
- `EVENT_LOCKED`

### 1. IDLE

含义：
- 当前没有活跃目标

进入条件：
- `track.is_active == false`

输出特征：
- `risk_score` 为 0 或接近 0
- 不触发告警、不触发抓拍

### 2. TRACKING

含义：
- 当前有目标，但还处于普通跟踪阶段

进入条件：
- `track.is_active == true` 且 `track.is_confirmed == false`
- 或已确认目标但风险分未达到可疑阈值

输出特征：
- 表示系统正在关注目标，但尚未升级风险

### 3. RID_MATCHED

含义：
- 当前目标已经被认定为合法合作目标

进入条件：
- `track.is_confirmed == true`
- 且 `rid_status == RID_MATCHED`

输出特征：
- `trigger_guardian = true`
- 不进入可疑、高风险、事件态

说明：
- 在当前逻辑中，`RID_MATCHED` 的优先级高于后续风险升级逻辑。

### 4. SUSPICIOUS

含义：
- 当前目标被判为可疑目标

进入条件：
- 风险分 `risk_score >= SuspiciousThreshold`
- 但未达到 `HighRiskThreshold`

输出特征：
- `trigger_alert = true`
- 不一定抓拍

### 5. HIGH_RISK

含义：
- 当前目标已进入高风险态

进入条件：
- 风险分 `risk_score >= HighRiskThreshold`
- 或达到事件阈值但尚未满足事件锁定保持条件

输出特征：
- `trigger_alert = true`
- `trigger_capture = true`

### 6. EVENT_LOCKED

含义：
- 当前目标已进入事件锁定态

进入条件：
- 风险分达到 `EventThreshold`
- 且当前已处于 `HIGH_RISK`
- 且保持时间达到 `EventLockHoldMs`

输出特征：
- 告警保持
- 抓拍保持
- 事件级状态锁定

## 五、Hunter 状态机转移图

```text
无活跃目标
  |
  v
IDLE

有目标但未确认
  |
  v
TRACKING

已确认且 RID 匹配
  |
  v
RID_MATCHED

已确认且风险分 >= SuspiciousThreshold
  |
  v
SUSPICIOUS

风险分 >= HighRiskThreshold
  |
  v
HIGH_RISK

风险分 >= EventThreshold
且 HIGH_RISK 持续达到 EventLockHoldMs
  |
  v
EVENT_LOCKED
```

## 六、Hunter 风险分是怎么来的

当前 `computeRiskScore()` 的组成方式如下：

### 1. 基础分

- 有活跃目标时先给 `TrackingBaseScore`

### 2. 持续性加分

- `seen_count * 4.0`
- 最高加到 `30`

### 3. RID 状态修正

- `RID_MATCHED`：减分
- `RID_MISSING`：加分
- `RID_SUSPICIOUS`：加更多分
- `RID_UNKNOWN`：默认加分

### 4. 距离修正

- 若目标距离小于 `LockDistanceThresholdMm`
- 再额外加分

### 5. 分值截断

- 最低不低于 `0`
- 最高不高于 `100`

## 七、为什么 `RID_MATCHED` 会压住风险升级

当前代码逻辑顺序是：

1. 先判断是否没有目标
2. 再判断是否未确认
3. 再判断是否 `RID_MATCHED`
4. 最后才判断事件、高风险、可疑

这意味着：
- 只要目标已确认且 `RID_MATCHED`
- 就会直接进入 `RID_MATCHED`
- 不再继续进入后面的风险升级判断

这个设计符合你当前项目“合法目标通行监管”的叙事方向。

## 八、为什么云台不是一看到目标就进入 TRACKING

当前云台状态机使用 `track.is_confirmed` 作为关键入口条件。

这意味着：
- 目标必须先经过 `TrackManager` 的确认
- 然后进入 `ACQUIRING`
- 保持一定时间后才正式进入 `TRACKING`

这样做的作用：
- 减少噪声点触发云台乱动
- 增强系统观感稳定性

## 九、当前调试时最应该观察的状态

### 单板测试阶段

重点看：
- `hunter_state`
- `rid_status`
- `risk_score`
- `UPLINK,HB`
- `STATUS`

### 接云台阶段

重点看：
- `gimbal_state`
- `SCANNING -> ACQUIRING -> TRACKING -> LOST` 是否合理

### 接雷达阶段

重点看：
- `track_active`
- `confirmed`
- `seen_count`
- `lost_count`
- `track_id`

## 十、结论

当前 `Node A` 的两个核心状态机已经具备较清晰的工程结构：

- 云台状态机负责“是否跟、何时跟、丢了怎么办”
- Hunter 状态机负责“是不是合法、风险多高、是否进入事件态”

后续不管是接硬件联调，还是做比赛答辩，这两个状态机都可以直接作为核心讲解内容。
