# 2026-04-02 Node A 功能更新

## 1. 今日目标

今天的工作目标，不是把完整视觉模块和完整网页大屏一次做完。

今天真正要完成的是，把三条链之间的边界先固定下来：

1. `Node A` 主链
2. 视觉增强链
3. 上云 / 网页展示链

核心思路很简单：

- 雷达、轨迹、风险、事件这些主逻辑继续放在 `ESP32-S3`
- 视觉锁定放在外部视觉计算端
- 网页端不再依赖临时调试文本，而是吃统一数据对象

---

## 2. 本周范围冻结

### 2.1 Node A 主链本周必须完成

- 雷达发现
- 轨迹确认
- 风险分级
- 事件生成
- 本地联动 / 本地反馈
- 事件上云

### 2.2 视觉链本周只做到

- 雷达先发现目标
- 云台根据雷达坐标做粗对准
- 相机转向目标区域
- 视觉模块在画面内完成近距锁定或目标框跟踪
- 在高风险 / 事件态提供抓拍输出能力

### 2.3 视觉链本周明确不做

- 纯视觉远距离发现
- 复杂目标分类
- 从零训练完整无人机检测模型

### 2.4 网页端本周只做到

- 节点在线状态显示
- 实时目标位置与状态显示
- 风险等级显示
- 事件记录显示
- 抓拍图显示入口

### 2.5 网页端本周明确不做

- 复杂权限系统
- 完整后台管理系统
- 没有真实数据支撑的空壳炫酷页面

---

## 3. 三条链及其边界

### 3.1 主链

`LD2450 -> TrackManager -> HunterAction -> GimbalController -> Event/Uplink`

这条链仍然是当前系统核心。

它负责：

- 判断目标是否存在
- 维护轨迹
- 做风险研判
- 创建事件
- 驱动云台粗跟踪
- 输出统一数据字段

### 3.2 视觉增强链

`主链粗对准 -> 相机进入目标区域 -> 视觉锁定 -> 抓拍`

这条链不是替代雷达，而是在雷达之后补强近距视觉能力。

它负责：

- 接收雷达和云台给出的粗方向
- 在相机画面里继续搜索
- 在图像坐标系里锁定目标
- 在高风险 / 事件态支持抓拍

### 3.3 上云 / 网页展示链

`Node A 统一数据 -> 后端桥接 -> 网页端展示`

它负责：

- 对外暴露稳定字段
- 显示当前状态
- 显示事件记录
- 显示抓拍入口

网页端以后要吃的是稳定对象，不应该直接解析临时调试日志。

---

## 4. 今天冻结下来的状态集合

### 4.1 主链状态

主链对外统一状态仍然使用：

- `IDLE`
- `DETECTING`
- `TRACKING`
- `SUSPICIOUS`
- `HIGH_RISK`
- `EVENT`
- `LOST`

### 4.2 视觉状态

今天新增的视觉子状态为：

- `VISION_IDLE`
- `VISION_SEARCHING`
- `VISION_LOCKED`
- `VISION_LOST`

当前含义如下：

- `VISION_IDLE`
  视觉链当前没有主动锁定目标
- `VISION_SEARCHING`
  雷达和云台已经把相机大致转过去，视觉端开始在画面内搜索
- `VISION_LOCKED`
  视觉端已经在图像空间里锁定目标
- `VISION_LOST`
  之前正在搜索或已经锁定，但当前暂时丢失

### 4.3 上云状态

今天新增的上云 / 展示子状态为：

- `UPLINK_IDLE`
- `UPLINK_READY`
- `UPLINK_SENDING`
- `UPLINK_OK`
- `UPLINK_FAIL`

当前含义如下：

- `UPLINK_IDLE`
  上行关闭或当前未激活
- `UPLINK_READY`
  上行已开启，处于可发送状态
- `UPLINK_SENDING`
  当前正在发送一帧数据
- `UPLINK_OK`
  最近一次本地发送流程已完成
- `UPLINK_FAIL`
  预留给后续真实传输失败状态

目前 `UPLINK_FAIL` 还只是一个预留状态，后面接入真实网络传输后再细化。

---

## 5. 今天冻结下来的统一数据字段

今天已经明确的统一字段包括：

- `node_id`
- `track_id`
- `track_active`
- `confirmed`
- `x`
- `y`
- `hunter_state`
- `risk_score`
- `risk_level`
- `rid_status`
- `event_active`
- `event_id`
- `trigger_flags`
- `vision_state`
- `vision_locked`
- `capture_ready`
- `uplink_state`
- `timestamp`

这些字段现在已经进入当前输出骨架，后面视觉端、后端、网页端都可以围绕这一套对象来接。

---

## 6. 网页端统一对象草案

推荐的对象草案如下：

```json
{
  "node_id": "A1",
  "track_id": 3,
  "track_active": true,
  "confirmed": true,
  "x": 320.0,
  "y": 1800.0,
  "hunter_state": "SUSPICIOUS",
  "risk_score": 63.0,
  "risk_level": "SUSPICIOUS",
  "rid_status": "MISSING",
  "event_active": true,
  "event_id": "A1-0000123456-0001",
  "trigger_flags": "ALERT|RID_MISSING|EVENT_ACTIVE",
  "vision_state": "VISION_SEARCHING",
  "vision_locked": false,
  "capture_ready": false,
  "uplink_state": "UPLINK_OK",
  "timestamp": 123456
}
```

这份对象设计的目的，是后面能比较平顺地用于：

- MQTT 消息体
- Flask / FastAPI 接口返回
- WebSocket 推送
- 基于 ECharts 的网页渲染

---

## 7. 今天的代码骨架更新

### 7.1 新增了状态枚举

今天代码中新增了：

- `VisionState`
- `UplinkState`

### 7.2 新增了共享运行字段

共享系统对象里已经加入：

- `trigger_flags`
- `vision_state`
- `vision_locked`
- `capture_ready`
- `uplink_state`
- `event_active`
- `event_id`
- `timestamp_ms`

### 7.3 新增了占位运行逻辑

今天的视觉链还只是占位逻辑，不是真正的视觉算法。

当前占位行为：

- 没有活跃目标时 -> `VISION_IDLE`
- 有已确认活跃目标时 -> `VISION_SEARCHING`
- 达到抓拍触发条件时 -> `VISION_LOCKED`
- 搜索或锁定后目标丢失时 -> 临时 `VISION_LOST`

当前上云占位行为：

- 上行关闭 -> `UPLINK_IDLE`
- 已开启但空闲 -> `UPLINK_READY`
- 发送一帧时 -> `UPLINK_SENDING`
- 本地串口发送完成后 -> `UPLINK_OK`

这样做的意义，是先把接口和字段冻结下来，但不假装完整模块已经全部落地。

---

## 8. 目前还没有真正实现的内容

今天这些改动，并不代表视觉链已经做完。

目前仍然还没有真正实现：

- 真实的 OpenCV 自动检测
- 从相机帧驱动的完整跟踪器生命周期
- 真实抓拍图片文件输出
- 真实 MQTT 传输
- 真实 Flask / FastAPI 后端
- 真实 HTML 数据大屏

今天真正完成的是：

- 边界冻结
- 状态冻结
- 字段冻结
- 输出骨架冻结

---

## 9. 推荐的视觉实现路线

比较稳的工程路线是：

1. `ESP32-S3` 继续负责雷达、轨迹、风险、事件和云台粗对准
2. 外部视觉计算端接收当前目标大致区域
3. 相机画面上使用：
   - 检测器负责重新找回目标
   - 跟踪器负责连续帧保持目标框
4. 视觉端输出：
   - `vision_state`
   - `vision_locked`
   - 可选的图像框或抓拍元数据

如果按比赛稳定性来考虑，推荐路线是：

- 检测器：`YOLOv8n`
- 跟踪器：`OpenCV CSRT` 或 `KCF`
- 工作方式：
  - 先检测一次
  - 再连续跟踪
  - 跟踪置信度下降后，再回到检测

---

## 10. 推荐的网页端路线

推荐技术栈：

- 前端：`HTML + CSS + JavaScript`
- 图表库：`ECharts`
- 后端：`Flask` 或 `FastAPI`
- 设备通信：`MQTT`
- 实时更新：`WebSocket` 或轮询
- 存储：前期 `SQLite`

推荐搭建顺序：

1. 后端先接收统一节点对象
2. 后端保存最新节点状态和事件记录
3. 前端先渲染：
   - 节点在线卡片
   - 目标位置
   - 风险等级
   - 事件列表
   - 抓拍入口

---

## 11. 为什么今天这一步很重要

如果今天不先做这一步冻结，后面几天很容易进入混乱状态：

- 前端要某个字段，但固件没有输出
- 视觉端想读某个状态，但主链没有定义
- 事件创建成功和上云成功被混成一件事

今天冻结完成后：

- 主链知道自己该输出什么
- 视觉链知道自己该消费什么
- 网页端知道自己该渲染什么

这就是今天这一步最核心的价值。

---

## 12. 今天新增的最小视觉桥接工具

### 12.1 新工具

今天新增了一个最小视觉桥接工具：

- `tools/vision_bridge_视觉桥接.py`

### 12.2 它当前做什么

这个工具刻意做得很小、很实用。

它现在还不是最终完整视觉链，只做最小可运行版本：

1. 打开摄像头或视频源
2. 让用户手动框选目标 ROI
3. 启动 OpenCV 跟踪器
4. 输出视觉状态变化
5. 在视频帧上叠加状态和目标框
6. 可选记录 CSV 日志

### 12.3 当前状态流

当前最小状态流为：

- `VISION_IDLE`
- `VISION_SEARCHING`
- `VISION_LOCKED`
- `VISION_LOST`

这已经足够先验证“近距视觉锁定”这条链。

### 12.4 为什么先做手动框选

手动框选是目前最稳的第一步。

它优先帮我们回答这些问题：

- 摄像头能不能正常打开
- 目标能不能稳定保留在跟踪框里
- 系统能不能干净地报告锁定和丢失

这样可以避免一开始就把太多问题搅在一起，例如：

- 模型加载
- 检测阈值
- 小目标检测质量
- 检测器和跟踪器切换逻辑

### 12.5 推荐运行命令

常用运行方式：

```text
python tools/vision_bridge_视觉桥接.py --source 0 --tracker csrt
```

可选 CSV 日志：

```text
python tools/vision_bridge_视觉桥接.py --source 0 --tracker csrt --log-file logs/vision_bridge.csv
```

### 12.6 按键说明

- `s` 或 `SPACE`
  选择目标 ROI
- `r`
  重置跟踪器并回到空闲态
- `h`
  显示或隐藏帮助叠加层
- `q` 或 `ESC`
  退出工具

### 12.7 后续升级路线

这个工具的升级路线已经想清楚了：

1. 当前版本：
   手动框选 + OpenCV 跟踪器
2. 下一版本：
   YOLO 检测一次，跟踪器持续维持
3. 再往后：
   把视觉状态和抓拍元数据桥接进后端或节点统一数据流

