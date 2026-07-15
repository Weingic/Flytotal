# 2026-05-16 Demo Submission Runbook V2

更新：2026-07-13。适用于全国大学生物联网设计竞赛乐鑫命题演示、录屏和提交前复核。

## 当前演示目标

主演示只讲一条物联网闭环：

```text
真实目标进入
-> ESP32-S3 融合雷达、RID 与视觉状态
-> 创建唯一风险事件
-> 结构化非音视频感知数据上传豆包
-> 云端返回带来源事件号的 JSON 指令
-> ESP32-S3 校验并执行或安全拒绝
-> Dashboard 展示有效抓拍、命令效果和证据哈希
```

只有同一新事件严格 `15/15 PASS`、事件新鲜度通过且同事件实机融合留证完成，才能称为本次完整主证据。软件回归 `25/25`、历史云端事件和离线 V4b 视频不能拼成同场闭环。

## 开始前红线

1. 用户、设备和真实目标都在合法安全场地；舵机和无人机有人看守。
2. 切回 **W-iPhone**，打开“最大兼容性”，确认 PC 和 NodeA 使用同一可访问网络。
3. COM4 只允许一份 `node_a_serial_bridge` 占用；关闭 PlatformIO Monitor、其他串口终端和第二份桥接。
4. 摄像头只允许一份 `vision_bridge` 占用；不要在视觉运行时重复探测 USB。
5. 正式演示不使用 `--allow-stale`、`--allow-session-reuse` 或调低 V4b 阈值。

## 1. 编译与静态状态

```powershell
git status --short
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run
python tools\firmware_safety_checks.py --require-compiled-secrets
python -m py_compile tools\node_a_serial_bridge_NodeA串口桥接.py tools\vision_bridge_视觉桥接.py tools\vision_web_server_视觉网页服务.py
python tools\vision_regression_checks_视觉回归检查.py
```

允许工作树含本地证据和当前开发改动，但必须知道每项来源。目标结果是固件编译通过、`compiled_secrets: PASS (3/3)`、Python 编译通过、完整回归 `25/25 PASS`。编译密钥检查只输出三项是否进入二进制，不显示 Wi-Fi 或 API Key 的真实值；它必须在每次重新构建后、停止旧服务和刷写前执行。

2026-07-13 新增的云端 `event_id` 回显核验、安全拒绝、测试不执行和云证据单次组行逻辑已经刷入当前 NodeA，并完成逐段读回校验。以后重新构建仍必须先正常停止唯一串口桥、确认 COM4 已释放，再执行下列命令；成功后只重启一份串口桥。不要让上传工具和桥接同时占用 COM4。

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run --target upload --upload-port COM4
```

当前这块 ESP32-S3 在普通上传中可识别芯片并启动 RAM stub，但随后稳定报 `Unable to verify flash chip connection (No serial data received.)`。先用 `flash_id --no-stub` 证明 ROM 下载器与 Flash 正常，再沿用项目地址和参数使用 ROM 原生模式写入；不得把普通上传失败误记为已刷写：

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\python.exe" "$env:USERPROFILE\.platformio\packages\tool-esptoolpy\esptool.py" --chip esp32s3 --port COM4 --baud 115200 --before default_reset --after hard_reset --no-stub write_flash --flash_mode qio --flash_freq 80m --flash_size 8MB --verify 0x0 ".pio\build\esp32-s3-devkitc-1\bootloader.bin" 0x8000 ".pio\build\esp32-s3-devkitc-1\partitions.bin" 0xe000 "$env:USERPROFILE\.platformio\packages\framework-arduinoespressif32\tools\partitions\boot_app0.bin" 0x10000 ".pio\build\esp32-s3-devkitc-1\firmware.bin"
```

只有 bootloader、分区表、boot_app0 和 firmware 四段都显示 `verify OK (digest matched)`，才算刷写成功。该备用路径解决的是本板的 stub 交接问题，不是通用要求；若普通 PlatformIO 上传成功，不必改走备用路径。

## 2. 摄像头就绪检查

此时先不要启动视觉桥：

```powershell
python tools\usb_camera_readiness_check_USB摄像头就绪核对.py --backend auto --drone-model models\yolov8n_drone.onnx
```

记录工具给出的摄像头编号、后端、画面亮度、可用 tracker 和推荐命令。若画面黑、过曝、过平或模型哈希不对，停止录屏并修复。

## 3. 启动三个常驻服务

本次返场不能只看“进程健康”就复用：2026-07-13 公共网络期间启动的串口桥和网页服务都早于最新云端字段代码。刷写前正常停止旧串口桥；启动三终端前还要正常停止旧网页服务并确认 `8765` 已释放，然后分别只启动一份新进程。当前记录的 PID `29824/26940` 仅用于定位本轮旧进程，返场时必须按实际进程和端口确认，不能盲目结束复用后的新 PID。以后若进程确定由当前源码启动且版本未再变化，才可以直接复用。

### 终端 A：NodeA 串口桥

```powershell
python tools\node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200 --vision-forward-status
```

新桥接启动时必须先输出 `SERIAL_OWNER_ACQUIRED,port=COM4,pid=...`。第二份桥会在打开 COM4 和写任何正式状态文件之前输出 `SERIAL_OWNER_CONFLICT` 并退出；若只是看到 `Failed to open COM4`，先关闭不遵守该锁的 PlatformIO Monitor 或旧桥接。2026-07-13 公共网络期间仍在运行的老桥进程没有加载新锁，返场刷写前停止并随后重启一次，保护才正式生效。

默认活动文件必须是：

```text
captures/latest_node_status.json
captures/latest_node_events.json
captures/latest_node_event_store.json
```

### 终端 B：V4b 视觉桥

优先复制 readiness 输出的推荐命令。当前正式配置示例：

```powershell
python tools\vision_bridge_视觉桥接.py --source 0 --backend dshow --tracker mil --tracker-fallback auto --source-warmup-frames 12 --width 1280 --height 720 --yolo-enabled --yolo-model models\yolov8n_drone.onnx --yolo-class-ids 0 --yolo-class-names 0:drone --yolo-model-label drone-v4b-hardneg-deployed --yolo-score-threshold 0.45 --yolo-intra-op-threads 8 --yolo-auto-lock
```

如果 readiness 推荐的 source 或 backend 不同，以当次实测为准，不固定猜测 `source 1`，也不强制不可用的 CSRT。

### 终端 C：本地 Dashboard

```powershell
python tools\vision_web_server_视觉网页服务.py --host 127.0.0.1 --port 8765
```

启动前可用 `Get-NetTCPConnection -LocalPort 8765 -State Listen` 检查是否仍有旧网页进程占口。新网页服务必须在串口桥已开始写入新状态后启动或刷新；否则 `/api/node-status` 看不到 `CLOUD,TEST/CLOUD,RESULT` 原始字段，严格预检会正确失败。

打开：

```text
http://127.0.0.1:8765/vision_dashboard.html
```

## 4. 录屏前预检

Dashboard 或状态 JSON 至少确认：

```text
NodeA online=1
status age < 3000 ms
track_active=0
event_active=0
event_id=NONE
detector_state=READY_ONNX
frame_content_ready=1
frame_quality_reason=OK
fusion_enabled=1
```

以上是云端默认关闭、真实目标尚未进场时的本地基础检查。测试前把目标移出雷达范围，必须保持轨迹和主事件为空；否则自动主事件请求可能与 `CLOUD,TEST` 交叉并覆盖原始结果。`cloud_online=1` 和 `cloud_error=NONE` 只能在下面的 `CLOUD,TEST` 成功后要求，不能放在启用云端之前。

先通过统一收件箱开启增强融合，再启用默认关闭的云端 AI，不打开第二个 COM4：

```powershell
python tools\node_a_serial_command_NodeA串口命令.py "FUSION,ENABLE,1" "FUSION,STATUS"
python tools\node_a_serial_command_NodeA串口命令.py "CLOUD,STATUS"
python tools\single_node_evidence_closure_check_单节点证据闭环核对.py --base-url http://127.0.0.1:8765 --cloud-preflight-only --cloud-preflight-stage contract
python tools\node_a_serial_command_NodeA串口命令.py "CLOUD,ENABLE,1"
python tools\node_a_serial_command_NodeA串口命令.py "CLOUD,TEST"
python tools\node_a_serial_command_NodeA串口命令.py "CLOUD,STATUS"
python tools\single_node_evidence_closure_check_单节点证据闭环核对.py --base-url http://127.0.0.1:8765 --cloud-preflight-only --cloud-preflight-stage test --cloud-preflight-wait-s 30
```

第一条 `CLOUD,STATUS` 必须在任何 API 测试之前确认新固件能力：

```text
cloud_contract_version=2
cloud_event_echo_required=1
cloud_test_no_apply=1
cloud_test_validated=0
```

缺少任一字段都说明开发板仍是旧固件或状态尚未刷新，禁止继续执行 `CLOUD,TEST`。此时 `contract` 预检还会要求 `serial_bridge_contract_version>=2`、`web_evidence_contract_version>=2`、轨迹和事件为空、云端默认关闭、测试尚未验证、原始测试/结果字段为空；必须看到 `16/16 PASS` 才能继续。两个 PC 版本项分别证明串口桥和网页服务都已重启到最新代码，不接受新旧进程混搭。版本确认不访问公网，也不执行模型动作。

`CLOUD,TEST` 是网络/API 预检事件，不是最终主证据。新固件下必须先看到：

```text
CLOUD,TEST,validated=1,no_apply=1,response_event_id=A1-CLOUD-TEST
CLOUD,RESULT,ok=1,...expected_event_id=A1-CLOUD-TEST,response_event_id=A1-CLOUD-TEST,...error=NONE
```

随后确认 `enabled=1`、`configured=1`、`wifi=CONNECTED`、`cloud_online=1`、`cloud_test_validated=1`、`cloud_command_applied=0`、`cloud_command_effect=TEST_RESPONSE_VALIDATED`、`error=NONE`。`test` 预检必须显示 `32/32 PASS`；它会继续核对两项 PC 版本、轨迹和事件仍为空、原始测试回显、请求/期望/返回三个 `A1-CLOUD-TEST` 事件号、HTTP 2xx、ESP 错误 0、边缘未执行结果，以及豆包测试返回必须为 `HIGH/CRITICAL + GENERATE_ALERT`。这证明网络和 API 响应可用、测试结果没有被执行，并提前证明模型遵守高风险告警策略。任一事件号缺失、不一致，或返回 `LOW/NONE` 等不合格策略，都不能进入正式主事件。

若板端已显示 `cloud_test_validated=1` 和 `TEST_RESPONSE_VALIDATED`，但 `cloud_test_result_no_apply/cloud_result_*` 仍为空，说明原始云串口行没有完整进入 PC 证据层，不能把它当作 `32/32`。当前固件会先在内存中组装 `CLOUD,TEST/CLOUD,RESULT/CLOUD,DEGRADED`，再连同换行一次写出，避免 AI 云任务与状态轮询并发时把证据串进长状态行；安全守门禁止这些记录恢复成分段输出。

两次预检都只读取 `http://127.0.0.1:8765/api/node-status`，不会发送串口命令，也不会自行访问豆包 API。结果单独写入 `captures/latest_cloud_preflight_report.json`，不会覆盖正式严格 `15/15` 报告。`contract` 阶段在启用云端前运行；`test` 阶段必须在 `CLOUD,TEST` 完成并再次执行 `CLOUD,STATUS` 后、创建主事件前运行。

`--cloud-preflight-wait-s 30` 控制只读预检最多等待 30 秒。增大后可容忍较慢的 Wi-Fi、时间同步和模型响应，但现场失败反馈更慢；减小后反馈更快，但可能在真实返回到达前误判超时。工具每 `0.5 s` 轮询本机状态，全部 `32/32` 条件满足时立即结束；超时、旧进程、目标提前进场、事件已经打开或豆包测试策略不合格都返回 `FAIL`，不会重复发送 `CLOUD,TEST`。

新固件还会在板端阻止重复测试：已经验证成功时返回 `CLOUD,TEST,queued=0,reason=already_validated`；已有云请求正在执行、测试已经排队或队列中有待处理请求时返回 `reason=request_busy`。这两种返回都表示没有新增 API 请求，不要继续连发；只看现有请求结果和预检报告。真正需要重测时，先查清失败原因并确认请求已结束，不能靠重复命令碰运气。

更新后的唯一串口桥会把 `CLOUD,TEST` 和 `CLOUD,RESULT` 原始返回持久化到状态、网页事件详情和严格导出。正式主事件结束前必须核对：

```text
cloud_test_result_no_apply=1
cloud_test_response_event_id=A1-CLOUD-TEST
cloud_result_ok=1
cloud_result_source=EVENT_OPENED
cloud_request_event_id=<当前新事件号>
cloud_expected_event_id=<当前新事件号>
cloud_response_event_id=<当前新事件号>
cloud_result_http_status=200
cloud_result_esp_error=0
cloud_result_error=NONE
```

请求、期望、返回、边缘执行绑定和当前主事件五个事件号必须一致。桥接会把测试事件号单独保存，不得让 `A1-CLOUD-TEST` 覆盖当前主事件号。

四层状态要分开排查：

```text
enabled=0       -> 云端流程尚未启用
configured=0    -> 本地配置或密钥缺失
wifi!=CONNECTED -> 热点/最大兼容性/连接问题
cloud_online=0  -> 尚未成功完成 API 请求，继续看 error
```

演示结束后如需关闭云端请求：

```powershell
python tools\node_a_serial_command_NodeA串口命令.py "CLOUD,ENABLE,0"
```

任一项失败都先排查，不把离线、旧状态或黑帧带入正式视频。

Dashboard 第一屏现在固定展示 ESP32-S3、融合、V4b、豆包和严格证据四段主链。开始主事件前，Node A、V4b 和豆包三项必须就绪；严格证据可以暂时为 `WAIT/FAIL`，因为它只能由随后产生的新主事件刷新。正式视频结束前，第一屏总判定必须转为可展示状态，最新图片必须标为“实时抓拍、已绑定事件”，不能仍显示“历史抓拍”或“未绑定事件”。

## 5. 真实目标模式

真实模式不发送 `TRACK` 模拟命令。

1. 录到目标和实测距离标记。
2. 目标进入后观察真实 `track_active/track_confirmed`、V4b 检测和 `YOLO_AUTO`。
3. 等待风险升级、新事件号和 Ark 返回。
4. 保持目标和事件处于活动状态直到云端返回；同时确认 `CLOUD,RESULT` 的 `expected_event_id`、`response_event_id` 和当前新事件号三者一致。
5. 确认 `cloud_command_source_event_id` 来自该云端回显号，且执行结果与 `cloud_command_applied/cloud_command_effect` 语义一致；出现 `active_event_mismatch` 表示响应迟到或事件已关闭，必须重新创建新事件，不能沿用旧结果。
6. 打开事件详情，展示有效抓拍、模型类别/分数、命令效果和哈希。
7. 保存原视频、状态、事件导出和对应距离记录。

合作目标与非合作目标必须明确说明 RID 来源。NodeB 模拟身份只能证明身份链逻辑，不能包装成真实无人机 Remote ID 接收。

## 6. 明确标注的台架模式

只有真实目标暂不可用、且用户在设备旁确认安全时才使用。视频角标或口头必须说“台架模拟轨迹”，不能说外场真机。

重复状态命令仍由统一入口按时间提交：

```powershell
python tools\node_a_serial_command_NodeA串口命令.py --interval-s 0.20 "TRACK,320,1000" "TRACK,320,1000" "TRACK,320,1000" "EVENT,STATUS"
```

`0.20 s` 控制两个请求进入收件箱的间隔。增大后更容易逐条确认，但整段更慢；减小后更快，过小时重复状态可能被调度器合并。该命令可能触发云台动作，只能有人看守时执行。

## 7. 严格验收

常驻桥接拥有 COM4、视觉桥拥有摄像头时，验收只能读取现有证据：

```powershell
python tools\acceptance_auto_411_快检全检自动验收.py --port COM4 --suite risk_event_vision_chain_v1 --no-run-suite --skip-usb --base-url http://127.0.0.1:8765
```

再直接核对国一严格门槛：

```powershell
python tools\single_node_evidence_closure_check_单节点证据闭环核对.py --base-url http://127.0.0.1:8765 --require-national-first-evidence
```

必须同时看到同一事件 `15/15 PASS`、`national_first_event_freshness=PASS`，并确认严格导出中的事件证据哈希和视觉证据哈希可回放。第 14 项 `cloud_command_applied` 只接受 `cloud_online=1`、`cloud_command_applied=1`、`cloud_threat_level=HIGH/CRITICAL`、`cloud_command_type=GENERATE_ALERT`、`cloud_command_effect=ALERT_GENERATED` 同时成立；仅有非空执行效果，或返回 `MEDIUM + ADJUST_THRESHOLD` 等非告警语义，必须停在 `14/15`，不得作为正式高风险闭环。第 15 项 `cloud_event_match` 不再只比较边缘执行事件号，还要求云契约版本至少为 2、事件号回显必需、测试不执行能力、本次启动的安全预检、`CLOUD,TEST` 原始无动作返回，以及正式 `CLOUD,RESULT` 的请求/期望/返回三事件号、`EVENT_OPENED` 来源、HTTP 成功和无错误状态全部通过。严格模式默认只接受主机在最近 `900000 ms`（15 分钟）内记录的事件，旧固件、旧桥接、缺原始回显或历史事件即使其他字段完整也会被拒绝。

`--national-first-max-event-age-ms` 控制允许的事件最大年龄。增大后现场操作时间更宽裕，但旧证据混入风险上升；减小后防伪更严格，但录屏和讲解稍慢就可能超时。正式演示保持默认 15 分钟，不临时放宽。普通 quick PASS 或软件回归 PASS 不能替代这一步。

## 8. 90 秒视频脚本

| 时间 | 画面 | 解说重点 |
| --- | --- | --- |
| 0-10 s | ESP32-S3、双雷达、NodeB、摄像头和云台 | 一句话说明校园低空安全 AIoT 场景 |
| 10-25 s | Dashboard 基线 | NodeA 在线、V4b 就绪、豆包在线、唯一事件号 |
| 25-45 s | 真实目标和距离标记 | 雷达/RID/视觉多源状态进入 ESP32-S3 |
| 45-65 s | 风险事件和云端字段 | 结构化数据上行、云端 JSON 指令、边缘执行/拒绝 |
| 65-80 s | 事件详情与抓拍 | `YOLO_AUTO`、drone 分数、有效画面、来源事件一致 |
| 80-90 s | 严格结果 | `15/15 PASS`、导出与哈希，回扣乐鑫四条要求 |

视频中不要展示 API key、Wi-Fi 密码或 `include/secrets.h`。

## 9. 失败时的诚实回退

如果直播失败，可以分别展示：

1. V4b 模型卡、离线评测和自动锁定浏览器截图，证明视觉软件链。
2. 2026-07-08 云端事件导出，证明 Ark API 和下行执行链。
3. 当前严格验收失败项，说明还缺哪一段同场证据。

三者必须标成不同时间和不同证据包，不得剪辑成同一事件成功。只要严格门槛没有通过，主结论就是“各子链已验证，同场闭环待补”，不能写“国一证据已完成”。

## 10. 答辩边界

1. 100 米只讲 LD2451 远距运动预警设计，不讲稳定无人机识别。
2. V4b 推理在 PC 网关，不讲 ESP32-S3 端部署 YOLO。
3. `TRIGGER_PARACHUTE` 不在模型允许输出中；NodeA 只保留防御性拒绝，真实硬件未集成。
4. NodeB 当前身份链可使用模拟 RID，不讲已接收真实无人机 Remote ID。
5. 真实距离、召回和误报只引用当前外场原始记录。
