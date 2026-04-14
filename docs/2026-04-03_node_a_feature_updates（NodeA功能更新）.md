# 2026-04-03 Node A 功能更新

## 1. 今日推进方向

今天继续推进的是工具链和本地展示链，不改 `ESP32` 固件主链。

本次重点增强的文件有：

- `tools/vision_bridge_视觉桥接.py`
- `tools/vision_web_server_视觉网页服务.py`
- `tools/vision_dashboard.html`
- `tools/node_a_serial_bridge_NodeA串口桥接.py`
- `tools/track_injector_轨迹注入器.py`

今天的目标，是把页面从“能看抓拍”继续推进成“能看实时状态、测试上下文和本轮结果”的联调面板。

---

## 2. 视觉桥接脚本当前能力

`tools/vision_bridge_视觉桥接.py` 当前已经具备这些能力：

- 打开摄像头或视频源
- 手动框选目标
- 使用 `CSRT` 或 `KCF` 跟踪器
- 输出视觉状态：
  - `VISION_IDLE`
  - `VISION_SEARCHING`
  - `VISION_LOCKED`
  - `VISION_LOST`
- 手动抓拍
- 新锁定时自动抓拍
- 抓拍冷却，避免短时间重复刷图
- 持续输出抓拍记录和实时状态

当前核心输出文件：

```text
captures/capture_records.csv
captures/latest_status.json
```

---

## 3. Node A 串口桥接当前能力

`tools/node_a_serial_bridge_NodeA串口桥接.py` 当前负责持续读取 `Node A` 串口输出，并整理成网页可直接消费的结构化数据。

当前主要产出：

```text
captures/latest_node_status.json
captures/latest_node_events.json
captures/latest_test_result.json
```

### 3.1 Node A 实时状态

`latest_node_status.json` 当前会整理这些核心字段：

- `node_id`
- `main_state`
- `hunter_state`
- `gimbal_state`
- `rid_status`
- `risk_score`
- `risk_level`
- `event_active`
- `event_id`
- `track_id`
- `track_active`
- `track_confirmed`
- `x_mm`
- `y_mm`
- `handover_last_result`
- `handover_last_target`
- `last_event_id`
- `last_reason`
- `online`
- `stale_age_ms`

### 3.2 Node A 最近事件

`latest_node_events.json` 当前用于保存最近几条关键事件，来源主要包括：

- `UPLINK,EVENT`
- `LASTEVENT`

每条事件记录当前会整理：

- 时间
- 事件号
- 原因
- 事件等级
- 事件状态
- 轨迹号
- 风险分数
- 接力目标

### 3.3 测试结果简报

这是今天新增的重要能力。

串口桥接脚本现在会结合：

- `track_injector_轨迹注入器.py` 当前场景信息
- `Node A` 实时状态
- `SUMMARY` 累计计数

自动生成一份本轮测试简报：

```text
captures/latest_test_result.json
```

当前简报至少包含：

- `result_label`
- `scenario_name`
- `rid_mode`
- `final_main_state`
- `final_risk_level`
- `final_event_id`
- `had_event`
- `had_handover`
- `track_active_delta`
- `track_lost_delta`
- `event_opened_delta`
- `event_closed_delta`
- `handover_queued_delta`
- `handover_emitted_delta`
- `handover_ignored_delta`
- `max_risk_score`
- `started_ms`
- `finished_ms`

当前结果标签规则先保持简单：

- `FAIL`：本轮没有形成有效轨迹
- `WARN`：出现事件、接力、接力忽略，或最终停在较高风险等级
- `PASS`：流程跑完且没有明显异常升级

这套规则当前定位是“联调简报规则”，不是最终评分算法。

---

## 4. 测试场景注入器当前能力

`tools/track_injector_轨迹注入器.py` 现在除了负责向串口注入标准场景，还会持续写出当前测试会话：

```text
captures/latest_test_session.json
```

当前会话里会带：

- 当前场景名
- 场景描述
- 场景序号
- RID 模式
- 当前进度
- 已发送点数
- 当前注入坐标
- 开始时间
- 结束时间
- 当前状态

这让网页不只是看状态，还能知道“现在到底在测哪一组场景”。

---

## 5. 本地网页服务当前能力

`tools/vision_web_server_视觉网页服务.py` 当前提供这些接口：

- `/api/health`
- `/api/status`
- `/api/node-status`
- `/api/node-events`
- `/api/test-session`
- `/api/test-result`
- `/api/captures`
- `/captures/...`

其中：

- `/api/status`
  读取视觉实时状态
- `/api/node-status`
  读取 Node A 主链实时状态
- `/api/node-events`
  读取 Node A 最近事件历史
- `/api/test-session`
  读取当前测试场景会话
- `/api/test-result`
  读取最近一轮测试结果简报
- `/api/captures`
  读取抓拍记录

---

## 6. 网页面板当前能力

`tools/vision_dashboard.html` 当前已经具备这些区域：

### 6.1 视觉实时状态卡片

用于显示：

- 当前视觉状态
- 是否锁定
- 跟踪器类型
- 当前框信息
- 当前中心点
- 最近更新时间

### 6.2 Node A 主链状态卡片

用于显示：

- 在线 / 离线
- `main_state`
- `hunter_state`
- `gimbal_state`
- `rid_status`
- `risk_level`
- `event_id`
- 最近事件
- 最近接力结果
- 当前轨迹
- 关键累计计数

### 6.3 测试场景卡片

用于显示：

- 当前场景名
- RID 模式
- 场景进度
- 已发送点数
- 当前注入坐标
- 开始时间
- 结束时间
- 场景运行状态

### 6.4 测试结果简报卡片

这是今天继续补强的部分。

当前会显示：

- 结果标签 `PASS / WARN / FAIL`
- 场景名
- RID 模式
- 最终主状态 / 风险等级
- 最后事件号
- 是否发生事件 / 接力
- 轨迹变化
- 事件变化
- 接力变化
- 最大风险
- 开始时间
- 结束时间

### 6.5 Node A 最近事件表

用于快速回看最近几条关键事件，而不用回串口窗口里翻。

### 6.6 抓拍证据区

用于显示：

- 最新抓拍图
- 最近抓拍记录
- 抓拍原因
- 事件号
- 目标框
- 图片入口

---

## 7. 状态高亮与展示语义

今天网页还继续做了展示语义增强：

- `ONLINE / OFFLINE` 有不同颜色
- `main_state / risk_level / event_status` 有语义标签色
- `HANDOVER / WARN / CRITICAL / EVENT` 在事件表中会高亮
- `Node A` 离线时，卡片会有更明显的过期提示

这一步没有增加新业务逻辑，但显著提升了联调时的可读性。

---

## 8. 建议运行方式

### 8.1 运行视觉桥接

```text
python tools/vision_bridge_视觉桥接.py --source 0 --tracker csrt
```

### 8.2 运行 Node A 串口桥接

```text
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --echo --summary-interval 3
```

说明：

- `COM4` 只是示例，请替换成你实际串口号
- `--summary-interval 3` 可以让桥接脚本定期拉一次 `SUMMARY`

### 8.3 运行测试场景注入器

```text
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all
```

### 8.4 运行本地网页服务

```text
python tools/vision_web_server_视觉网页服务.py
```

打开：

```text
http://127.0.0.1:8765
```

---

## 9. 当前这一步解决了什么问题

到今天这一步，本地联调页面已经不再只是“看抓拍图”，而是开始具备三层信息：

1. 当前系统状态
2. 当前测试上下文
3. 本轮测试结论

这意味着后面你做标准场景验证时，不用再一边盯串口、一边自己手工总结这一轮到底发生了什么。

---

## 10. 当前明确还没有做什么

当前仍然没有做：

- YOLO 自动检测接入
- 串口反向控制板子
- MQTT
- 数据库
- 真正云端部署
- 完整后台权限系统
- 固件主链和视觉抓拍的自动强联动

所以当前阶段仍然是：

- 工具链增强
- 本地展示链增强
- 测试链标准化增强
- 不破坏固件主链

---

## 11. 测试结果历史面板

今天继续在“测试结果简报”基础上补了一层“测试结果历史”。

### 11.1 新增历史文件

串口桥接脚本现在除了写：

```text
captures/latest_test_result.json
```

还会额外维护：

```text
captures/latest_test_results.json
```

这个文件用于保存最近几轮场景的结果历史，默认保留最近 16 条。

### 11.2 新增网页接口

本地网页服务新增：

```text
/api/test-results
```

这个接口用于返回最近几轮测试结果列表，页面可以直接拿来渲染表格。

### 11.3 页面新增内容

网页中新增了“测试结果历史”表格，当前每条历史记录至少显示：

- 开始时间
- 场景名
- RID
- 结果标签
- 最终风险等级
- 是否发生事件 / 接力
- 最后事件号
- 轨迹变化
- 结束时间

### 11.4 这一步的价值

到这一步，页面已经不只是能回答：

- 现在在测什么
- 这一轮刚测完结果是什么

还开始能回答：

- 最近几轮整体测得怎么样

这对后面做标准场景验证、周报整理和答辩复盘都会更省力。

---

## 12. 测试结果摘要与筛选

今天继续在“测试结果历史”上面补了一层更轻的总览和筛选。

### 12.1 摘要条

网页现在会基于最近几轮结果历史，自动统计：

- `PASS` 有几轮
- `WARN` 有几轮
- `FAIL` 有几轮
- 出现事件的有几轮
- 发生接力的有几轮

这样打开页面后，不用先逐行看表格，先扫一眼摘要就能知道最近整体测试情况。

### 12.2 轻量筛选

网页当前增加了 4 个前端筛选按钮：

- `全部`
- `WARN/FAIL`
- `有事件`
- `有接力`

它们不会改动后端数据，只是在前端对已有历史记录做轻量过滤，方便快速聚焦到最值得看的几轮。

### 12.3 当前价值

到这一步，测试结果这一层已经不只是“有历史表”，而是具备了：

- 一眼看总览
- 一键筛高风险结果
- 一键筛事件相关结果
- 一键筛接力相关结果

这会让后面连续跑多轮场景时，页面更接近真正的联调结果板。

---

## 13. 测试结果详情展开

今天继续把“测试结果历史”从纯列表往“可复盘”推进了一步。

### 13.1 详情展开方式

网页现在在测试结果历史表的每一行后面增加了一个：

- `展开`
- `收起`

按钮。

点开之后，会直接在当前这一行下面展开详情，不跳新页面，也不弹窗。

### 13.2 当前可展开的字段

展开后，当前会显示这一轮更完整的解释字段：

- `final_main_state`
- `final_risk_level`
- `max_risk_score`
- `scenario_description`
- `event_opened_delta / event_closed_delta`
- `handover_queued_delta / handover_emitted_delta / handover_ignored_delta`
- `final_event_id`

### 13.3 这一步的价值

到这一步，页面已经不只是告诉你：

- 哪一轮是 `WARN`
- 哪一轮有事件

还开始能直接回答：

- 这一轮为什么是 `WARN`
- 这一轮最终停在哪个状态
- 这一轮到底是事件升级，还是接力忽略，还是风险分数偏高

这会让后面做单轮复盘时，不用总回串口窗口里翻上下文。

---

## 14. 联调会话归档

今天继续把工具链往“可回放、可复盘”推进了一步，新增了联调会话归档。

### 14.1 新增归档目录

当前会话日志默认会落到：

```text
captures/session_logs/
```

每一轮测试会生成一份按场景时间命名的 `jsonl` 文件。

### 14.2 当前会写入日志的工具

这次接入了 3 条工具链：

- `tools/track_injector_轨迹注入器.py`
- `tools/node_a_serial_bridge_NodeA串口桥接.py`
- `tools/vision_bridge_视觉桥接.py`

### 14.3 当前记录的事件类型

当前会话日志中已经开始记录这些关键时间点：

- `session_started`
- `track_point_sent`
- `session_settling`
- `session_finished`
- `all_done`
- `node_status_changed`
- `node_event`
- `test_result`
- `vision_status_changed`
- `capture_saved`

### 14.4 这一步的意义

到这一步，联调结束后不再只剩网页截图和几个最新 JSON 快照，而是开始有一份按时间线排列的原始过程记录。

这会更方便你后面做：

- 周报整理
- 单轮复盘
- 问题追踪
- 交接总结

可以把它理解成当前这套联调系统的“飞行记录仪”。

---

## 15. 联调时间线面板

今天继续把“联调会话归档”从文件层推进到了网页层。

### 15.1 新增网页接口

本地网页服务新增：

```text
/api/session-timeline
```

这个接口会默认读取最近一轮会话日志文件，并返回其中最近一段关键时间线事件。

### 15.2 页面新增内容

网页中新增了“联调时间线”区域，当前会按时间顺序显示：

- 时间
- 来源
- 事件类型
- 场景
- 摘要

### 15.3 当前能看到的关键过程

时间线里当前已经能看到这些事件：

- `session_started`
- `track_point_sent`
- `session_settling`
- `session_finished`
- `all_done`
- `node_status_changed`
- `node_event`
- `vision_status_changed`
- `capture_saved`
- `test_result`

### 15.4 这一步的价值

到这一步，联调结束后你不只是有：

- 最新状态
- 结果简报
- 结果历史
- 原始 `jsonl`

还开始有了一个能直接在网页里复盘过程的“时间线面板”。

这会让后面做问题复现、过程解释和答辩演示更顺手。

---

## 16. 历史会话切换器

今天继续把“联调时间线”从“只看最近一轮”推进到了“可切换最近几轮”。

### 16.1 新增网页接口

本地网页服务新增：

```text
/api/session-timeline-sessions
```

这个接口会返回最近几轮会话日志的简要列表，供网页做切换器使用。

同时原有：

```text
/api/session-timeline
```

现在也支持通过会话文件名读取指定那一轮的时间线。

### 16.2 页面新增能力

网页中的“联调时间线”区域上方，现在会显示最近几轮会话按钮。

每个按钮当前至少包含：

- 场景名
- 开始时间

点击不同按钮后，下面的时间线会切换到对应那一轮。

### 16.3 这一步的价值

到这一步，网页已经不只是能回看“最后一轮怎么跑的”，还开始能直接切换回看前几轮。

这会更适合：

- 连续跑多轮标准场景
- 对比两轮差异
- 回看前一轮为什么出现异常
- 做多轮联调复盘

---

## 17. 会话总览卡片

今天继续在“历史会话切换器”上面补了一层“会话总览卡片”。

### 17.1 总览卡片显示内容

当你切换到某一轮会话时，页面现在会先给出一块简短总览，当前至少包括：

- 场景名
- 开始时间
- 事件总数
- 是否有抓拍
- 是否有主链事件
- 是否有最终结果
- 最终结果标签
- 最终风险等级

### 17.2 数据来源

这些字段来自会话日志文件本身的摘要统计，由网页服务在读取会话列表时同步给出，不需要页面自己再次完整扫描整条时间线。

### 17.3 这一步的价值

到这一步，切换不同会话时已经不是“直接掉进一大串时间线”了，而是会先看到一张很短的“封面摘要”。

这会让你在多轮联调复盘时更快判断：

- 这轮值不值得点进去细看
- 这轮有没有抓拍
- 这轮有没有主链事件
- 这轮最终是 `PASS / WARN / FAIL`

---

## 18. 时间线事件高亮与来源筛选

今天继续把“联调时间线”从“能看”推进到了“更容易扫、更容易挑重点看”。

### 18.1 页面新增能力

在“联调时间线”区域，新增了 4 个轻量筛选按钮：

- `全部`
- `只看主链`
- `只看视觉`
- `只看抓拍/结果`

同时，时间线中的关键事件现在会带上更明显的视觉区分：

- 主链事件会突出显示
- 视觉状态变化会单独着色
- `capture_saved` 会作为抓拍重点行显示
- `test_result` 会作为结果重点行显示

### 18.2 这一步具体解决什么问题

之前时间线虽然已经能看完整过程，但当一轮里的事件变多之后，还是容易出现“都混在一起”的感觉。

补完这一步之后，联调复盘会顺很多：

- 想只看主链怎么变化，可以直接切到 `只看主链`
- 想只看视觉锁定和抓拍，可以切到 `只看视觉` 或 `只看抓拍/结果`
- 想讲解关键过程时，不用从长表里一条条找重点

### 18.3 当前定位

这一步仍然只是展示层增强：

- 不改固件
- 不改主链协议
- 不改 Python 工具主逻辑

但它会明显提升网页面板在联调和演示时的可读性。

---

## 19. 会话抓拍证据区

今天继续把“历史会话复盘”往前推进了一步，补上了“本轮抓拍证据”区域。

### 19.1 新增能力

当你在网页里切换到某一轮会话时，页面现在不只显示：

- 这轮的时间线
- 这轮的结果摘要

还会同步显示：

- 这轮留下了几张抓拍
- 每张抓拍的时间
- 抓拍原因
- 对应事件号
- 对应图片链接

### 19.2 它是怎么接出来的

这一步没有改视觉桥接脚本的主逻辑，也没有增加新的日志格式。

实现方式是：

- 网页服务直接读取当前会话日志里的 `capture_saved`
- 把其中的 `file_path / capture_reason / event_id / vision_state` 整理成接口数据
- 页面跟随当前选中的会话同步显示这一轮的抓拍证据

### 19.3 这一步的价值

到这一步，单轮复盘已经开始具备完整闭环：

- 能看过程
- 能看结果
- 能看这一轮实际留下的视觉证据

这会让你后面回答这些问题时更直接：

- 这一轮到底有没有抓到图
- 抓拍发生在什么时刻
- 抓拍对应的是哪个事件
- 不同轮之间为什么有的有图、有的没图

---

## 20. 测试结果历史与会话回放联动

今天继续把“结果历史”和“会话回放”真正打通了。

### 20.1 新增能力

在“测试结果历史”表里，每一条结果现在都会尝试匹配对应的历史会话。

如果匹配成功，这一行会多一个：

- `查看会话`

点下去之后，页面会自动：

- 切到对应那一轮会话
- 刷新对应会话的联调时间线
- 刷新对应会话的抓拍证据
- 自动滚动到时间线区域

### 20.2 它是怎么匹配的

这一步没有新增复杂索引，也没有改后端数据结构。

当前使用的是一套很克制的匹配方式：

- 先按 `scenario_name + started_ms` 精确匹配
- 如果精确匹配不到，再按 `scenario_name` 做回退匹配

这样已经足够覆盖当前这套本地测试和会话日志流程。

### 20.3 这一步的价值

补完以后，你复盘一条 `WARN / FAIL` 不需要再手工：

- 先记住场景名
- 再去上面会话按钮里找
- 再切到那一轮看时间线和抓拍

现在可以直接从“结果”跳到“过程 + 证据”。

这会让整套本地联调页面更像一个真正完整的复盘工具，而不是几块强功能面板并排摆放。

---

## 21. 参数观察卡片

今天开始把页面从“看状态、看结果、看证据”继续往“看调参上下文”推进。

### 21.1 这一步做了什么

网页新增了一块“参数观察”卡片，当前先展示已经能从 `SELFTEST` 里稳定拿到的参数和值，包括：

- `predictor_kp / predictor_kd`
- `heartbeat_ms / event_report_ms`
- `sim_hold_ms`
- `monitor_baud / radar_baud`
- `test_mode / servo_enabled / servo_attached`
- `safe_mode / diag_running`
- `debug / quiet / uplink`
- 当前 `main_state / gimbal_state / risk_score`
- `idle_ready`

### 21.2 它是怎么接进来的

这一步没有改固件逻辑，只是在串口桥接层增加了对 `SELFTEST` 输出的解析，并让桥接脚本定时主动发一次：

- `SELFTEST`

然后把其中的参数字段并入原来的 `latest_node_status.json`，网页继续从同一个状态文件里读取。

### 21.3 当前边界

这一步我没有硬做假字段。

像下面这些参数，当前固件输出里还没有稳定给出来，所以卡片里先明确说明“暂未输出”：

- `ConfirmFrames`
- `LostTimeoutMs`

等后面固件真正把这些参数打印出来，再自然补进来会更稳。

### 21.4 这一步的价值

到这一步，页面开始不仅能看“系统现在怎样”，还开始能看“系统现在是用什么参数在这样跑”。

这对后面真实联调和参数微调很重要，因为你会更容易对照：

- 现在用的是哪组 `KP / KD`
- 当前风险变化是不是和这组参数对应得上
- 现在是不是开着 `debug / quiet / uplink`

