# 2026-07-12 NodeA 功能更新

## 计划位置

2026-07-12 / 三天国一冲刺 / Day 1 自动视觉闭环与有效证据守门

## 今日目标

把视觉链从“YOLO 只画检测框、人工按键选择 ROI”升级为“YOLO 连续确认后自动启动跟踪”，同时阻止黑帧、过曝帧、无内容帧和过期事件号进入最终证据链。

## 根因确认

1. 专用无人机模型输出为 `[1, 5, 8400]`。旧代码只在特征维至少为 6 时转置，导致单类别模型的 8400 个候选框被错误解析。
2. 旧 `SidecarDetector` 只负责在画面上显示红框，没有调用跟踪器初始化；真正进入 `VISION_LOCKED` 的唯一入口是人工按 `s` 后选择 ROI。
3. 2026-07-08 的三张 `FRAME_BIND` 抓拍平均亮度约为 `0.02`，属于黑帧。原摄像头预检只判断 `cap.read()` 成功，原抓拍函数也会无条件写入任意帧。
4. NodeA 离线时，视觉桥接仍会直接读取旧 `latest_node_status.json` 中的事件号，可能把新抓拍错绑到历史事件。

## 完成内容

### 1. 单类别 YOLO 正确解码

- 同时支持 `[1, 5, 8400]` 和 `[1, 8400, 5]` 两种输出方向。
- 保留置信度筛选、坐标映射和 NMS 去重。
- 检测结果保留 `class_name=drone` 和真实分数。

### 2. YOLO 自动起锁

- 只使用 `READY_ONNX` 的真实模型结果，不使用光流 fallback 自动起锁。
- 同一类别目标需连续两次检测且框重叠达到阈值，才允许启动跟踪器。
- 默认自动起锁分数门槛为 `0.45`，检测框会增加少量上下文。
- 自动框始终保留 1 像素画面边界，避免 MIL 在贴边框上初始化失败。
- 自动锁定后输出 `lock_source=YOLO_AUTO`、`auto_lock_score`、`auto_lock_class_name`；人工选框保留为 `MANUAL_ROI` 兜底。

### 3. 有效画面守门

- 增加平均亮度、亮度标准差检查。
- 默认拒绝：平均亮度低于 `5`、高于 `250`，或亮度标准差低于 `2` 的画面。
- 摄像头启动预检、运行状态和抓拍入口使用同一判断口径。
- 无效画面会输出 `CAPTURE_REJECTED`，不会生成 JPG，也不会写入抓拍记录。

### 4. 过期事件绑定防护

- `latest_node_status.json` 只有在更新时间不超过 `event_bind_max_age_ms` 时才能提供事件号。
- NodeA 离线或状态过期时，新抓拍使用 `event_id=NONE`，不会冒充历史事件证据。

### 5. 摄像头预检升级

当前推荐命令会自动加入本地无人机模型和自动起锁参数：

```powershell
python tools/vision_bridge_视觉桥接.py --backend dshow --source 0 --tracker mil --tracker-fallback auto --source-warmup-frames 12 --yolo-enabled --yolo-model models/yolov8n_drone.onnx --yolo-class-ids 0 --yolo-class-names 0:drone --yolo-model-label drone-yolov8n --yolo-auto-lock
```

## 验收结果

### 离线回归

```powershell
python tools/vision_regression_checks_视觉回归检查.py
```

结果：

```text
vision_regression_checks: PASS (10/10)
```

覆盖：黑/白/平坦帧拒绝、单类别 YOLO 解码、自动目标连续确认、MIL 初始化、黑帧抓拍拒绝、检测器版本更新、过期事件号拒绝、视觉状态串口转发、网页状态新鲜度合并、15 项国一证据门槛。

### 真实摄像头预检

```text
result=PASS
camera_ready_count=1
trackers_available=MIL
drone_model_ready=1
frame_mean_luma=126.788
frame_luma_stddev=21.510
frame_quality_reason=OK
```

### 真实模型样本检查

- 5 张保留测试集无人机图片中，修复后的运行时解析检出 2 张高置信目标，最高分 `0.821`。
- 3 张本地人物背景图片均为 0 检测。
- 这是运行时解析抽查，不替代模型卡中的完整验证集指标。

### 自动闭环复测

使用保留测试集无人机图片生成临时视频，实际启动 ONNX 与 MIL：

```text
detector_state=READY_ONNX
vision_state=VISION_LOCKED
vision_locked=1
lock_source=YOLO_AUTO
auto_lock_score=0.81
auto_lock_class_name=drone
tracker_state=TRACKING
frame_quality=OK
last_capture_reason=AUTO_LOCK
capture_bytes=41666
event_id=NONE
```

这证明“模型检测 -> 连续确认 -> 自动起锁 -> MIL 跟踪 -> 自动抓拍”代码链已跑通，同时证明 NodeA 离线时不会错绑旧事件。

### 网页事件证据闭环

- 网页服务只在抓拍路径与事件号一致时，把当前视觉状态并入事件详情，避免最新画面覆盖历史事件。
- 事件详情与导出对象新增自动锁定方式、模型类别与分数、检测器状态、画面亮度质量、抓拍文件 SHA256 和独立视觉证据 SHA256。
- `vision_evidence_v1` 会区分 `VALID`、`CAPTURE_ONLY`、`INVALID_FRAME_METADATA` 等质量状态；旧黑帧不能再被包装成有效视觉证据。
- Dashboard 已显示 `YOLO_AUTO`、`drone / score`、画面有效性与视觉证据 Hash，叠加框使用实际 tracker 名称。
- 修复了真实/模拟模式切换与 2 秒自动刷新并发时，旧模式响应覆盖新页面的竞态。
- mock 数据在网页服务启动时固定，同一演示会话中的事件时间、抓拍哈希和视觉证据哈希不会随请求漂移。
- `.panel` 增加最小宽度约束，手机端宽表格保留局部横向滚动，不再把整页撑宽。

### 网页与 API 验收

两次连续请求同一 mock 事件详情：

```text
event_id=A1-0000000001-MOCK
evidence_quality=VALID
capture_timestamp_stable=True
capture_hash_stable=True
vision_hash_stable=True
vision_hash_length=64
```

Playwright 使用本机 Chrome 完成桌面 `1440x1000` 与手机 `390x844` 真浏览器点击验收：

```text
page_errors=0
console_errors=0
failed_responses=0
lock_source=YOLO_AUTO
auto_decision=drone / 0.88
frame_quality=VALID
hash_stable_across_auto_refresh=true
canvas_non_blank=true
document_horizontal_overflow=false
```

截图：

- `outputs/e2e/2026-07-12_dashboard_vision_evidence_desktop.png`
- `outputs/e2e/2026-07-12_dashboard_vision_evidence_mobile.png`

以上 mock 验收只证明网页字段、绑定规则、哈希和响应式展示正确，不替代真实无人机与 NodeA 证据。

## 诚实边界

1. 本轮自动闭环使用保留测试集无人机图片生成的临时视频，不是当天外场真无人机视频。
2. 当天真实摄像头画面已验证可读且不是黑帧，但画面内没有无人机，因此保持 `VISION_IDLE` 属于正确行为。
3. 当前系统未识别到 NodeA 串口，尚未采集“真实 NodeA 事件 + 自动视觉锁定 + 云端指令 + 网页导出”的同场新证据。
4. 国一最终证据仍必须用合法、安全场地的真实无人机或可被清楚说明的受控目标完成，不能把本轮离线视频包装成外场实测。

## 下一步

1. 接回 NodeA 后采集一条全新的同场事件，不再引用 7 月 8 日黑帧证据。
2. 在同一次录屏中展示 NodeA 新事件、YOLO 自动起锁、云端同事件指令、网页详情与导出 JSON。
3. 完成真实无人机与人、车、鸟干扰测试，生成独立误报、召回和距离分档结果。

## 物联网竞赛口径校正

本项目对应的是 **2026 全国大学生物联网设计竞赛乐鑫命题**，不是嵌入式芯片与系统设计竞赛。后续评估和材料全部按物联网赛口径执行。

官方乐鑫命题的硬要求是：

1. 以 `ESP32-S3 / ESP32-C5 / ESP32-P4` 之一作为核心控制器。
2. 至少完成一种传感器数据融合。
3. 至少接入一个云端大语言模型。
4. 设备需要响应大模型下发，或把非音视频传感器数据上传给大模型处理。

官方创新评价还关注场景、边缘 AI/多源融合/低功耗、交互、物理形态和实际价值。作品提交截止时间为 **2026-07-27 24:00**。

- 乐鑫命题页：`https://www.espressif.com/en/ecosystem/education/competition/iot`
- 赛程通知：`https://iot.sjtu.edu.cn/ueditor/net/upload/file/20260709/6391915428633249995089276.pdf`

## 同一事件国一证据门槛

### 代码链已完成

1. NodeA 串口桥新增 `--vision-forward-status`，在拥有串口的同一进程内把视觉状态发给 ESP32，避免视觉桥和串口桥争抢 COM 口。
2. 新鲜且画面有效的自动锁定会依次发送 `VISION,CONF,...` 与 `VISION,LOCKED`。
3. 状态过期、视觉链未就绪或锁定画面无效时会发送 `VISION,LOST` 或 `VISION,SEARCHING`，不允许旧锁定继续生效。
4. 网页只合并新鲜的视觉运行状态；过期的主机状态不再覆盖 NodeA 自身的 `vision_state/vision_locked`。
5. `full` 验收默认启用 15 项严格门槛，要求当前同一事件同时具备：事件精确匹配、严格截图绑定、有效 YOLO 自动锁定、真实 ONNX、有效画面、两类 SHA256、云端在线/下行生效和云端来源事件匹配。
6. 只有 15/15 通过后才为当前事件强制生成严格导出；导出还要再次核对事件证据哈希与视觉证据哈希。
7. 导出接口会重新形成一次瞬时快照；验收先确认该快照仍是 15/15，再用它的视觉哈希核对落盘文件，避免实时目标框正常变化造成假失败。
8. `track_injector` 只有在串口成功打开后才初始化会话和事件快照；COM 不存在或被占用时会保留上一份有效证据。

启动命令：

```powershell
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200 --vision-forward-status
```

严格验收命令：

```powershell
python tools/single_node_evidence_closure_check_单节点证据闭环核对.py --require-national-first-evidence
```

### 已验证结果

1. Python 语法检查通过。
2. 视觉回归通过 `10/10`，其中严格成功路径已真实完成临时图片写入、严格绑定、15/15、导出落盘和双层哈希回放。
3. 普通闭环验收保持 `PASS`，证明原有低门槛调试流程未被破坏。
4. `full` 模式确认自动启用 `closure_require_national_first_evidence=true`。
5. 本机网页服务重启后，过期视觉状态显示 `vision_runtime_online=0`、`detector_state=OFFLINE`，不再覆盖 NodeA 状态。
6. 历史事件 `A1-0000003139-0001` 的严格结果为 `FAIL 8/15`；失败项包括视觉质量、状态/截图匹配、YOLO 自动锁定、分数、类别、模型就绪、画面有效性和导出视觉哈希。
7. 使用 `COM999` 与临时哨兵文件复测失败路径：进程正确返回失败，测试会话和事件文件 SHA256 均保持不变。

这个 `8/15 FAIL` 是预期的诚实结果：历史黑帧事件只能证明部分云端与结构化导出能力，不能作为国一主视觉证据。

### 当前未完成

截至本轮验证，Windows 仍未枚举到 NodeA 串口。因此以下内容还不能标为完成：

1. 视觉状态通过真实 COM 口回传 ESP32 的实机验证。
2. 新 NodeA 事件、真实自动视觉、云端同事件下行和严格导出的同场 `15/15` 证据。
3. 真实无人机、人、车、鸟的召回率、误报率、距离和延迟数据。

## 三终端资源所有权收口

### 问题

旧启动顺序让 `node_a_serial_bridge` 常驻占用 COM，同时让 `acceptance_flow` 再启动 `track_injector` 打开同一 COM；视觉桥常驻占用摄像头时，验收又会重复运行 USB 探测。Windows 下这会造成串口或摄像头争抢，现场流程并不可靠。

### 现在的两种明确模式

**真实现场常驻模式**：

1. `node_a_serial_bridge` 独占串口并负责视觉状态回传、状态采集和事件落盘。
2. `vision_bridge` 独占摄像头。
3. 验收使用 `--no-run-suite --skip-usb`，只读取已经形成的真实证据，不重新打开硬件资源。

```powershell
python tools/acceptance_auto_411_快检全检自动验收.py --port COM4 --suite risk_event_vision_chain_v1 --no-run-suite --skip-usb --base-url http://127.0.0.1:8765
```

**台架模拟套件模式**：

先停止常驻 NodeA 串口桥，让验收程序临时独占 COM；不传 `--no-run-suite` 时，`quick/full` 仍默认执行原有轨迹注入套件。

```powershell
python tools/acceptance_auto_411_快检全检自动验收.py --port COM4 --suite risk_event_vision_chain_v1 --run-suite --skip-usb --base-url http://127.0.0.1:8765
```

### 验证结果

```text
live full: run_suite=false
live full serial_owner=node_a_serial_bridge
live full step_names=single_node_evidence_closure
live auto quick/full: track_injector steps=0/0
bench quick default: run_suite=true
bench quick serial_owner=acceptance_flow
event/session SHA256 unchanged in all invalid-COM checks
```

启动助手生成的 quick、full、auto 命令现在全部使用真实现场常驻模式。显式选择不运行预检时，助手会显示 `preflight_result=SKIPPED`，不会再引用旧预检报告误判当前环境。
