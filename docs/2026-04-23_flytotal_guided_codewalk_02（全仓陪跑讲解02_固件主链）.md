# Flytotal 全仓陪跑讲解 02：固件主链

这一讲只讲板端和紧贴固件的代码。  
目标不是逐行翻译，而是把你带到一个状态：看到某个文件时，你知道它属于哪一层、为什么会存在、它解决的是什么问题。

---

## 1. 固件主链先看总图

先把固件部分压成一句话：

```text
串口/模拟输入
    ->
RadarParser 解析坐标
    ->
TrackManager 维护轨迹
    ->
HunterAction 计算风险与触发
    ->
GimbalController 输出云台状态与角度
    ->
main.cpp 管理事件、RID、handover、调试输出、上行输出
```

这条主链里，真正“做单一专业工作”的是 `lib/` 下的模块。  
真正“把系统编成一整条故事”的，是 `src/main.cpp`。

---

## 2. `include/AppConfig.h`：系统的总调音台

### 代码事实

这个文件集中定义了几乎所有关键常量：

- 串口参数：`AppSerialConfig`
- 节点信息：`NodeConfig`
- 云台参数：`GimbalConfig`
- 舵机硬件参数：`ServoConfig`
- 雷达锁定距离：`RadarConfig`
- 轨迹确认/丢失参数：`TrackConfig`
- 风险评分和阈值：`HunterConfig`
- RID 时间窗：`RidConfig`
- 跟踪保持时间：`TrackingConfig`
- 音频占位配置：`AudioConfig`
- 云端上报节奏：`CloudConfig`
- 事件开启/保持/关闭/冷却/抓拍节流：`EventConfig`

### 设计理解

为什么不把这些数散在各个 `.cpp` 里？

因为这套系统的很多行为都不是“逻辑写错了”，而是“阈值不合适”。  
一旦进入联调阶段，最常改的往往不是算法结构，而是：

- 确认需要几帧
- 丢失后等多久
- 风险多少分进入哪个等级
- 事件需要保持多久
- 抓拍多久允许一次

把它们集中起来，带来的好处是：

- 可调参
- 可复盘
- 可冻结版本
- 可写文档和验收基线

### 设计推断

`AppConfig.h` 体现的是“参数面和逻辑面分离”的思路。  
也就是说，项目作者已经意识到：这个系统后期会频繁联调，所以参数必须被放到一个一眼能找到的地方。

---

## 3. `include/SharedData.h`：系统共享真相源

### 代码事实

这个文件定义了整个固件主链最关键的公共对象：

- 状态枚举：
  `GimbalState`、`RidStatus`、`WhitelistStatus`、`VisionState`、`AudioState`、`UplinkState`、`HunterState`、`MainState`、`RiskLevel`、`RiskTransitionMode`、`EventState`
- 共享结构：
  `RadarTrack`
- 系统总状态：
  `SystemData`
- 归一化输出：
  `UnifiedOutputSnapshot`
- 事件实体：
  `EventObject`

### 设计理解

为什么这个文件这么重要？

因为它定义了整个系统“用什么语言交流”。

例如：

- 雷达层看的是 `RadarTrack`
- 决策层写的是 `hunter_state`、`risk_score`
- 视觉层看的是 `vision_state`
- 上报层发的是 `event_id`、`trigger_flags`
- 网页桥接和验收工具最终依赖的也是这些字段语义

所以 `SharedData.h` 不是一个普通头文件，它更像是：

- 固件内部的数据契约
- 主机工具的语义来源
- 文档和验收标准的字段母本

### 设计推断

`SystemData` 之所以很长，不是因为“写乱了”，而是因为它承担了共享状态中心的角色。  
这是一种典型的多任务嵌入式设计：不同任务各做一段，但必须围绕同一份系统真相协作。

同时，枚举非常多，说明作者在主动把系统从“连续噪声世界”变成“有限状态世界”。  
这对联调和讲解都非常重要。

---

## 4. `lib/RadarParser`：把原始字节流变成坐标

对应文件：

- `lib/RadarParser/RadarParser.h`
- `lib/RadarParser/RadarParser.cpp`

### 代码事实

`RadarParser` 内部是一个串口帧状态机。

它做的事情是：

1. 等待固定帧头。
2. 收满数据字节。
3. 从字节里提取 `x`、`y`。
4. 用 Kalman 滤波做平滑。
5. 对外暴露 `getParsedX()`、`getParsedY()`。

### 设计理解

为什么这里必须先做一层 parser？

因为原始串口流不能直接拿去做业务判断。  
业务层需要的是“结构化坐标”，而不是一串二进制字节。

所以这个模块的存在意义，就是完成第一道抽象：

```text
原始雷达字节
    ->
可计算的坐标值
```

### 设计推断

这里用了状态机 + 滤波，说明作者一开始就知道雷达输入不是稳定完美数据。  
Parser 不只是“解包”，还是第一层抗噪。

这体现的工程思路是：

- 底层脏数据先在靠近输入处被清洗。
- 不要把原始协议细节传播到后续所有模块。

---

## 5. `lib/TrackManager`：把点变成轨迹

对应文件：

- `lib/TrackManager/TrackManager.h`
- `lib/TrackManager/TrackManager.cpp`

### 代码事实

这个模块维护 `RadarTrack`，主要做 4 件事：

1. 建轨：`resetTrack()`
2. 更新轨迹：`updateTrack()`
3. 计算速度：`vx_mm_s`、`vy_mm_s`
4. 丢失管理：`refresh()`

它还负责：

- `track_id`
- `is_active`
- `is_confirmed`
- `seen_count`
- `lost_count`
- `first_seen_ms`
- `last_seen_ms`

### 设计理解

为什么不能直接把最新 `x,y` 传给后面？

因为“一个点”不等于“一个稳定目标”。

后面的风险判断和云台控制真正关心的是：

- 目标是不是持续存在
- 它是不是已经稳定 enough
- 它的速度是多少
- 现在算不算已经丢了

所以 `TrackManager` 的核心价值，是把瞬时观测升级成“带生命周期的目标对象”。

### 设计推断

`ConfirmFrames`、`LostTimeoutMs`、`RebuildGapMs` 这些参数说明作者在主动对抗两件事：

1. 一闪而过的噪声点
2. 旧轨迹和新轨迹混淆

这体现的思路是：

- 先确认，再信任
- 先定义生命周期，再做复杂业务

这一步是整个系统走向稳定的关键。

---

## 6. `lib/HunterAction`：风险不是真假，而是渐进升级

对应文件：

- `lib/HunterAction/HunterAction.h`
- `lib/HunterAction/HunterAction.cpp`

### 代码事实

`HunterAction` 有两个层面：

1. `computeRiskAssessment()`
   计算风险分及组成项。
2. `update()`
   根据分数、RID、白名单、视觉、音频状态，决定 `HunterState` 和触发标志。

它输出的关键信息有：

- `risk_score`
- `risk_reason_flags`
- 分项得分
- `state`
- `pending_state`
- `trigger_alert`
- `trigger_capture`
- `trigger_guardian`

风险分来源包括：

- 基础跟踪分
- 持续出现分
- 已确认加分
- RID/白名单修正
- 距离修正
- 运动异常修正
- 视觉加减分
- 音频占位加分

### 设计理解

为什么不用“if 满足条件就危险，否则不危险”？

因为现实目标判断通常不是二元的，而是逐步升级的：

- 先看到
- 再确认
- 再怀疑
- 再高风险
- 再锁成事件

如果直接二元判断，会有两个问题：

1. 太容易跳变
2. 不方便解释“为什么现在危险”

所以这里采用的是：

```text
分数系统
    +
状态机
```

分数负责表达连续趋势。  
状态机负责把趋势收敛成明确阶段。

### 设计推断

这个模块很像整个项目从“会动”走向“会判断”的分水岭。

你会看到很多 hold 逻辑：

- `SuspiciousEnterHoldMs`
- `HighRiskEnterHoldMs`
- `EventEnterHoldMs`
- 各种 exit hold

这说明作者非常在意风险链的稳定性，而不是追求瞬时灵敏。

换句话说，这段设计在防的是：

- 误报
- 状态抖动
- 一会升一会降的难看行为

这也是工程项目和课堂 demo 的一个典型区别。

---

## 7. `lib/GimbalPredictor`：控制计算层

对应文件：

- `lib/GimbalPredictor/GimbalPredictor.h`
- `lib/GimbalPredictor/GimbalPredictor.cpp`

### 代码事实

它负责：

- 根据目标位置估算速度
- 根据速度做简单前瞻预测
- 计算目标方位角
- 用 `Kp`、`Kd` 调整当前角度
- 输出当前云台 pan 角

### 设计理解

为什么要把“预测”单独拆成一个类，而不是直接写进云台状态机？

因为“怎么计算角度”和“什么时候该跟踪”是两种完全不同的问题。

- `GimbalPredictor` 回答的是：角度怎么算。
- `GimbalController` 回答的是：什么时候进入扫描/获取/跟踪/丢失。

### 设计推断

这体现了一个很好的分层习惯：

- 算法层只负责连续控制量。
- 状态层只负责离散行为阶段。

即使当前 `Kd` 还没有深度发挥作用，这种拆法也给未来调参和换算法留了空间。

---

## 8. `lib/GimbalController`：行为阶段层

对应文件：

- `lib/GimbalController/GimbalController.h`
- `lib/GimbalController/GimbalController.cpp`

### 代码事实

这是一个明确的 4 态状态机：

- `STATE_SCANNING`
- `STATE_ACQUIRING`
- `STATE_TRACKING`
- `STATE_LOST`

行为大意：

- `SCANNING`
  左右扫描，等目标确认。
- `ACQUIRING`
  已经发现目标，但先做一个短确认。
- `TRACKING`
  正式跟踪，输出预测角度和距离映射的 tilt。
- `LOST`
  目标刚丢时不立刻回扫描，留一个恢复窗口。

### 设计理解

为什么不是“看见目标就 TRACKING，丢失就立刻 SCANNING”？

因为那样云台会很神经质。

作者显然在追求两个体验：

1. 不要乱动
2. 丢了也不要立刻抽风回扫

所以这里加了：

- `AcquireConfirmMs`
- `LostRecoveryTimeoutMs`

### 设计推断

这个状态机的核心灵感不是复杂控制理论，而是“观感稳定”。  
尤其在演示场景里，云台动作是否平顺，往往比算法术语更重要。

---

## 9. `lib/Safetylink`：旁路线能力

对应文件：

- `lib/Safetylink/Safetylink.h`
- `lib/Safetylink/Safetylink.cpp`

### 代码事实

这个模块封装了基于 ESP-NOW 的应急发送逻辑，用于向目标 MAC 地址发送紧急指令，例如 `fireParachute()`。

### 设计理解

它现在不是当前主链最常用的模块，但它代表了一种很重要的设计方向：

- 主链负责观测和判断
- 旁路线可以负责“紧急动作输出”

### 设计推断

它更像是项目早期或扩展方向里“安全干预链”的痕迹。  
即使当前大系统重点已经转到事件、证据和双节点，这个模块仍然说明项目最初并不是只想做可视化，而是想做“观测后可采取动作”的系统。

---

## 10. `include/gimbal_gcs_云台地面站.py`：早期调参与观察工具

### 代码事实

这个脚本通过串口读取 `DATA` 输出，并用 matplotlib：

- 画目标横向位置
- 画舵机角度
- 提供 `Kp` / `Kd` 滑块

### 设计理解

为什么这个文件会放在 `include/` 而不是 `tools/`？

从当前项目结构看，它更像是早期实验脚本或历史遗留的开发辅助工具。  
它不影响主链，但能帮助理解一个事实：

- 在项目早期，作者很重视“先把控制链肉眼看明白”

### 设计推断

它代表了这个项目早期的灵感来源：

- 先让开发者直观看到控制效果
- 再把参数暴露成滑块，快速试调

也就是说，这个项目从一开始就不是“只写代码不看表现”的风格。

---

## 11. `include/README` 和 `lib/README`：模板骨架

### 代码事实

这两个文件是 PlatformIO 默认说明，主要解释：

- `include/` 用来放头文件
- `lib/` 用来放私有库

### 设计理解

虽然它们不属于业务逻辑，但它们提醒你一个重要背景：

- 当前仓库是从标准 PlatformIO 工程骨架逐步长出来的

这也是为什么今天你会看到：

- 固件库化
- 头文件集中
- `src/main.cpp` 负责调度

这是一个比较正统的嵌入式工程长相。

---

## 12. `src/main.cpp`：系统编排层

这是整个仓库里最容易把人看晕的文件，也是最值得换一种角度理解的文件。

### 12.1 不要把它当成“一个大函数集合”

更好的理解方式是把它分成 7 层。

#### 第一层：运行时上下文和缓存

文件最前面定义了大量结构：

- `SimTrackInput`
- `RidIdentityPacket`
- `WhitelistEntry`
- `EventContext`
- `RuntimeEventStatus`
- `EventLifecycleState`
- `EventPolicySnapshot`
- `NodeRiskContext`
- `NodeRuntimeCache`
- `ManualServoControl`
- `VisionOverrideControl`
- `DebugOutputControl`
- `UplinkOutputControl`
- `SafetyControl`
- `ServoDiagnosticControl`
- `HandoverRequest`
- `HandoverStatus`
- `LastEventSnapshot`
- `SummaryStats`

代码事实：

- 它们不是算法库，而是“系统运行时需要记住的上下文”。

设计理解：

- 随着功能越来越多，单靠 `globalData` 已经不够表达完整过程。
- 所以 `main.cpp` 内部又维护了一批更偏“流程管理”和“调试留痕”的局部状态。

设计推断：

- `main.cpp` 已经从“简单调度器”长成了“系统编排器”。

#### 第二层：RID 与白名单链

你会看到一整段函数围绕：

- `parseRidStatus`
- `parseRidMessagePayload`
- `resolveWhitelistDecision`
- `refreshRidRuntime`

代码事实：

- 支持简单 RID 命令和结构化 `RID,MSG,...`
- 支持白名单命中、过期、拒绝
- 支持接收超时、合法保持、重确认窗口

设计理解：

- 作者不满足于“设备发个 MATCHED 就完事”
- 而是把身份链做成了持续运行的状态系统

设计推断：

- 这表明项目已经从“演示型标记”升级到“更像真实身份运行时”

#### 第三层：状态归一化与调试输出

中间有很多名字转换和输出函数：

- `hunterStateName`
- `gimbalStateName`
- `ridStateName`
- `deriveMainState`
- `deriveRiskLevel`
- `computeTriggerFlags`
- `print*Flags`

代码事实：

- 这些函数把内部状态翻译成统一可输出文本

设计理解：

- 这不是重复劳动，而是在建设“系统解释层”
- 没有这层，后续桥接、网页、验收工具都会各说各话

#### 第四层：事件生命周期

这一层是 `main.cpp` 最有“工程味”的部分。

关键函数包括：

- `isEventEligible`
- `shouldKeepEventOpen`
- `canOpenEventContext`
- `ensureEventContext`
- `closeEventContext`
- `emitEventLifecycleLog`
- `syncRuntimeEventStatus`

代码事实：

- 事件不是风险一高就直接开，也不是一低就直接关
- 中间存在 open/hold/close/cooldown/reopen 机制

设计理解：

- 作者在对抗事件抖动
- 作者也在为后续抓拍、导出、回放准备“稳定事件实体”

设计推断：

- 这是项目从“风险链”走向“证据链”的关键转折

#### 第五层：handover 与双节点上下文

关键函数包括：

- `findNodeRuntimeCacheLocked`
- `ensureNodeRuntimeCacheLocked`
- `populateCurrentEventContinuityFieldsLocked`
- `setHandoverQueued`
- `setHandoverOutcome`
- `emitHandoverStatus`
- `queueHandoverRequest`

代码事实：

- 系统显式记录节点切换相关字段
- 还专门维护 handover 状态和结果

设计理解：

- 双节点问题最怕“接力存在，但讲不清”
- 所以这里优先记录显式交接字段，而不是只靠推理

设计推断：

- 作者把“接力可解释性”看得比“炫算法”更重要

#### 第六层：主机命令入口

关键入口：

- `printHostCommandHelp()`
- `handleHostCommand()`
- `pollHostCommands()`

支持的命令已经很多，包括：

- `STATUS`
- `CONFIG,STATUS`
- `RISK,STATUS`
- `EVENT,STATUS`
- `SUMMARY`
- `SELFTEST`
- `TRACK,x,y`
- `RID,...`
- `WL,...`
- `VISION,...`
- `AUDIO,...`
- `KP,value`
- `KD,value`
- `HANDOVER,target_node`
- `RESET`

代码事实：

- 固件已经不只是被动跑任务，还暴露了一个主机驱动调试接口

设计理解：

- 当系统越来越复杂，开发者必须能从主机侧“拨动状态”
- 否则很多链路根本无法独立验证

设计推断：

- 这是整套工具链能成立的基础
- 没有这些命令，后面的桥接、验收、自动化脚本都无从谈起

#### 第七层：三个任务

##### `RadarTask`

代码事实：

- 从 `Serial1` 或模拟输入拿数据
- 调用 `RadarParser`
- 调用 `TrackManager`
- 更新 `globalData.radar_track`

设计理解：

- 它只负责“拿输入并形成轨迹”
- 不碰风险、不碰上报，职责清晰

##### `TrackingTask`

代码事实：

- 轮询主机命令
- 刷新 RID、视觉、音频输入
- 调用 `HunterAction`
- 调用 `GimbalController`
- 管理抓拍触发条件和捕获节流
- 更新大量 `globalData` 字段
- 输出本地调试信息

设计理解：

- 这是整条业务主脑
- 真正负责“决定系统此刻怎么理解目标”

##### `CloudTask`

代码事实：

- 周期发送心跳
- 输出轨迹帧
- 输出状态变化事件
- 维护事件上下文开关
- 处理 handover 事件发射

设计理解：

- 它负责把内部状态翻译成外部世界可消费的上行协议

### 12.2 为什么 `main.cpp` 会越来越大

这是初学者很容易困惑的一点。

原因不是单纯“没拆好”，而是它承担的是编排责任：

- 事件链要同时看风险、RID、视觉、抓拍、handover
- 上报链要同时看轨迹、状态变化、事件上下文
- 主机命令要能拨动多个子系统

这些跨模块规则，天然就会在编排层汇总。

设计推断：

- 如果未来继续演进，`main.cpp` 最值得拆分的方向不是基础库，而是把事件编排、命令路由、上报组织再模块化
- 但在当前阶段，把复杂规则集中在一个编排层，也有利于快速联调和整体观察

---

## 13. 这一讲最值得你自己复述的内容

如果你读完这一讲，建议你自己试着复述下面这段话：

“板端先把原始雷达数据解析成坐标，再把坐标维护成轨迹；轨迹进入风险判断模块后，系统不直接二元判定，而是先算风险分，再进入状态机；云台控制也不是看到目标就动，而是先扫描、再获取、再跟踪、再短时丢失恢复；最后 `main.cpp` 把 RID、白名单、事件生命周期、抓拍、handover、命令、上行输出这些跨模块能力编排成一个完整系统。”

如果这段你能讲顺，说明你已经不再是“只会看函数”，而是开始看到系统层次了。
