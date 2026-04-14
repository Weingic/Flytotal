# Node A 数据流与主链说明

（功能：
这一步不是加新功能，而是把你当前系统“怎么工作”画清楚。

目的：
让你自己后面讲项目时更顺
给后续硬件联调定位问题用
为后面的状态机图和架构图打基础）


本文档用于说明当前 `Node A` 的三任务结构、共享数据流转方式，以及串口命令和上行日志分别作用在哪一段链路上。

说明：
- 本文档只描述当前代码中已经实现的链路。
- 本文档不扩展新功能，不假设尚未接入的模块。

## 一、当前主链目标

当前 `Node A` 的主链可以概括为：

`雷达输入 -> 轨迹管理 -> 风险研判 -> 云台控制 -> 本地调试输出 -> 上行帧输出`

在没有接入真实雷达时，系统仍可完成：

- 程序启动自检
- 状态查询
- RID 命令注入
- 运行时参数调整
- 心跳与事件上行输出

## 二、当前任务结构

`main.cpp` 当前创建了三个 FreeRTOS 任务：

### 1. RadarTask

职责：
- 初始化 `Serial1`
- 接收雷达串口字节流
- 调用 `RadarParser` 解析雷达坐标
- 调用 `TrackManager` 更新轨迹
- 将轨迹结果写入 `globalData`

核心输入：
- `Serial1` 雷达数据

核心输出：
- `globalData.x_pos`
- `globalData.y_pos`
- `globalData.is_locked`
- `globalData.radar_track`

### 2. TrackingTask

职责：
- 轮询 USB 串口命令
- 读取 `globalData.radar_track` 和 `globalData.rid_status`
- 调用 `HunterAction` 完成风险研判
- 调用 `GimbalController` 计算云台控制输出
- 更新 `globalData.hunter_state`
- 更新 `globalData.gimbal_state`
- 输出本地调试日志

核心输入：
- `globalData.radar_track`
- `globalData.rid_status`
- 主机串口命令

核心输出：
- `globalData.hunter_state`
- `globalData.risk_score`
- `globalData.trigger_alert`
- `globalData.trigger_capture`
- `globalData.trigger_guardian`
- `globalData.gimbal_state`
- 舵机角度写入
- `GIMBAL / DATA / STATE` 调试输出

### 3. CloudTask

职责：
- 周期性读取 `globalData`
- 输出心跳帧
- 输出轨迹帧
- 在关键状态变化时输出事件帧

核心输入：
- `globalData` 全量快照

核心输出：
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`

## 三、共享数据结构

当前三任务通过 [SharedData.h](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/include/SharedData.h) 中的 `SystemData globalData` 交换信息，并使用 `dataMutex` 做临界区保护。

### 关键字段说明

- `is_locked`
  - 当前是否满足锁定条件
- `x_pos / y_pos`
  - 当前目标位置
- `gimbal_state`
  - 云台状态机当前状态
- `hunter_state`
  - Hunter 状态机当前状态
- `rid_status`
  - 当前 RID 判定状态
- `radar_track`
  - 当前轨迹对象
- `risk_score`
  - 当前风险分数
- `trigger_alert`
  - 是否触发本地告警
- `trigger_capture`
  - 是否触发抓拍
- `trigger_guardian`
  - 是否触发合作终端保障链路

### `RadarTrack` 关键字段

- `track_id`
- `is_active`
- `is_confirmed`
- `x_mm / y_mm`
- `vx_mm_s / vy_mm_s`
- `seen_count`
- `lost_count`
- `first_seen_ms`
- `last_seen_ms`

## 四、主链数据流

下面是当前主链的文字流程图：

```text
Serial1 雷达字节流
    ->
RadarParser
    ->
解析得到 x / y
    ->
TrackManager.updateTrack()
    ->
更新 RadarTrack
    ->
写入 globalData.radar_track / x_pos / y_pos / is_locked
    ->
TrackingTask 读取 globalData
    ->
HunterAction.update()
    ->
更新 hunter_state / risk_score / trigger_alert / trigger_capture / trigger_guardian
    ->
GimbalController.update()
    ->
更新 gimbal_state / pan_angle / tilt_angle
    ->
本地输出 GIMBAL / DATA / STATE
    ->
CloudTask 读取 globalData
    ->
输出 UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT
```

## 五、各模块在主链中的作用

### 1. RadarParser

作用：
- 从串口字节流中提取可用的 `x / y` 坐标

位置：
- 在 `RadarTask` 中被调用

### 2. TrackManager

作用：
- 管理目标轨迹生命周期
- 负责轨迹创建、确认、速度估计、丢失判定、轨迹重建

主要行为：
- 连续出现一定帧数后 `is_confirmed = true`
- 一段时间无更新后将轨迹置为非活跃

### 3. HunterAction

作用：
- 根据轨迹状态和 RID 状态计算风险分数
- 输出 Hunter 状态与动作触发标志

主要输入：
- `RadarTrack`
- `RidStatus`

主要输出：
- `HunterState`
- `risk_score`
- `trigger_alert`
- `trigger_capture`
- `trigger_guardian`

### 4. GimbalController

作用：
- 根据轨迹状态切换云台状态机
- 输出云台角度

主要状态：
- `SCANNING`
- `ACQUIRING`
- `TRACKING`
- `LOST`

### 5. CloudTask

作用：
- 将 `globalData` 中的当前状态转换为串口上行帧

输出类型：
- 心跳帧
- 轨迹帧
- 事件帧

## 六、主机命令在系统中的作用位置

当前主机命令全部在 `TrackingTask` 中通过 `pollHostCommands()` 进入系统。

### HELP

作用：
- 打印命令列表

影响范围：
- 仅影响串口交互

### STATUS

作用：
- 读取 `globalData` 当前快照并打印

影响范围：
- 不修改系统状态

### RID,OK / RID,MISSING / RID,SUSPICIOUS

作用：
- 修改 `globalData.rid_status`

影响范围：
- 直接影响 `HunterAction` 的风险判定与状态切换
- 间接影响 `UPLINK,HB` 和 `UPLINK,EVENT`

### KP,value / KD,value

作用：
- 修改 `GimbalPredictor` 运行时参数

影响范围：
- 影响云台预测行为
- 不直接修改 Hunter 状态

### RESET

作用：
- 将 `rid_status` 恢复为 `UNKNOWN`
- 将 `Kp / Kd` 恢复默认值

影响范围：
- 恢复当前运行时测试环境

## 七、本地输出与上行输出分别来自哪里

### 本地调试输出

`TrackingTask` 输出：
- `GIMBAL`
- `DATA`
- `STATE`

辅助命令输出：
- `HELP`
- `STATUS`
- `RID simulation updated`
- `Predictor Kp updated`
- `Predictor Kd stored`
- `Simulation state reset`

### 上行输出

`CloudTask` 输出：
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`

## 八、状态变化最关键的触发点

### 轨迹层

- 雷达成功解析出目标坐标
- `TrackManager.updateTrack()` 更新轨迹
- 达到确认帧数后，轨迹进入确认状态
- 超时未更新后，轨迹转为丢失

### Hunter 层

- `rid_status` 改变
- `risk_score` 超过阈值
- 轨迹从未确认变为确认

### 云台层

- `track.is_confirmed == true` 时，从 `SCANNING` 进入 `ACQUIRING`
- 达到确认保持时间后进入 `TRACKING`
- 丢失目标后进入 `LOST`
- 超时未恢复后回到 `SCANNING`

## 九、当前阶段调试建议

### 单板测试时

重点看：
- 程序是否能稳定启动
- `HELP / STATUS` 是否正常
- `RID` 命令是否能改变 `hunter_state`
- `UPLINK,HB` 是否稳定输出

### 接云台时

重点看：
- `gimbal_state` 切换是否符合预期
- 舵机中心位和角度范围是否合理

### 接雷达时

重点看：
- `track_active`
- `confirmed`
- `track_id`
- `x / y`
- `lost_count`

## 十、结论

当前 `Node A` 已具备一个比较清晰的三段式主链：

- `RadarTask` 负责感知输入
- `TrackingTask` 负责业务判定与控制计算
- `CloudTask` 负责对外输出

这意味着后续不管是接雷达、接云台、接云端，还是做双节点扩展，都可以围绕这三段链路逐步推进，而不需要推翻现有结构。
