# 2026-06-08 Real Data Collection SOP V1

本 SOP 属于 2026-06-08「视觉模型 + 多旋翼真分类器 + 真数据 SOP」计划的 D 路，并在 2026-07-13 第 4 步按当前运行链更新。目标是采到可追溯、不过期、不混淆传感器能力边界的真实现场证据。

## 三条证据线不能混用

| 证据线 | 原始输入 | 能证明什么 | 不能证明什么 |
| --- | --- | --- | --- |
| LD2450 近距轨迹 | `x_mm/y_mm/vx_mm_s/vy_mm_s` | 已确认目标的近距二维运动轨迹 | 不能预设能在 10/30/50 米稳定输出轨迹 |
| V4b 视觉识别 | 摄像头画面、YOLO、MIL 跟踪 | 无人机视觉识别、自动锁定、误报和距离表现 | 不能代替雷达距离测量 |
| LD2451 远距预警 | `range_m/speed_mps/approach` | 远距运动、距离和接近趋势预警 | 不是无人机专用雷达，也不输出 LD2450 的二维轨迹 |

同一真实事件可以融合三条证据，但 `real_tracks.csv` 只接收 LD2450 已确认的二维轨迹。10/30/50 米视觉测试和 LD2451 预警不得因为“检测到了目标”就伪装成 LD2450 轨迹样本。

## 采集红线

写入真实轨迹 CSV 前，Dashboard 必须同时满足：

```text
online=1
track_active=1
track_confirmed=1
x_mm/y_mm/vx_mm_s/vy_mm_s 随真实目标连续变化
```

任何一项不满足就停止该段采集。不要使用 `--allow-stale` 制作正式数据；它只用于人工调试旧文件。

采集器默认读取：

```text
captures/latest_node_status.json
```

默认新鲜度上限是 `3000 ms`。采集器会同时检查状态自报延迟、`last_update_ms`、文件更新时间和 `online`，桥接停止后的冻结 JSON 不会继续进入训练集。

## 启动顺序

### 1. 保证 COM4 只有一个拥有者

先确认没有第二个串口监视器、PlatformIO Monitor 或另一份桥接进程占用 COM4。已有桥接正常运行时直接复用，不要重复启动。

需要重新启动时：

```powershell
python tools\node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200 --vision-forward-status
```

该命令默认写入：

```text
captures/latest_node_status.json
captures/latest_node_events.json
captures/latest_node_event_store.json
```

现场配置命令统一通过收件箱入口提交，不再由第二个程序直接打开 COM4：

```powershell
python tools\node_a_serial_command_NodeA串口命令.py "REALINPUT,ON" "TESTMODE,OFF" "FUSION,ENABLE,1" "CLOUD,ENABLE,1" "FUSION,STATUS" "CLOUD,STATUS" "STATUS" --interval-s 0.25
```

数据采集阶段不要发送 `TRACK` 模拟指令。涉及舵机或真实无人机动作时，必须有人在设备旁看守。

固件在上电和 `RESET` 后默认回到 `fusion_enabled=0` 的基础兼容模式，所以每次正式外场任务都必须重新发送 `FUSION,ENABLE,1`。开启后，系统使用 FAR/MID/NEAR 增强融合并检查视觉、近距雷达、远距雷达与身份来源的一致性；关闭后只保留旧的来源计数兼容逻辑，不能用于最终实机融合证据。

2026-07-14 起，`STATUS` 同时输出 `boot_id`、`boot_count`、`reset_reason`、`reset_reason_raw` 和 `uptime_ms`。`boot_id` 是本次启动的唯一编号；一旦变化，就表示开发板已重新启动。`reset_reason` 用于区分 USB 下载复位、软件复位、看门狗、掉电或电压异常。每次重启后至少等待 15 秒，再重新发送上面的现场配置命令和运行预检。重启前的已完成试验可以保留，但正在记录的那一段必须作废并使用新 `session-id` 重采。

### 2. 启动 V4b 视觉链

当前正式模型：

```text
models/yolov8n_drone.onnx
SHA256 c33aba9e6e24ce24ae6147a538b46b0c1080093242f0ad1c59100c738121ac74
```

先在有人能查看摄像头画面时运行就绪检查：

```powershell
python tools\usb_camera_readiness_check_USB摄像头就绪核对.py --backend auto --drone-model models\yolov8n_drone.onnx
```

就绪检查通过后，按它给出的摄像头编号和后端启动。当前正式模型配置示例：

```powershell
python tools\vision_bridge_视觉桥接.py --source 0 --backend dshow --tracker mil --tracker-fallback auto --width 1280 --height 720 --yolo-enabled --yolo-model models\yolov8n_drone.onnx --yolo-class-ids 0 --yolo-class-names 0:drone --yolo-model-label drone-v4b-hardneg-deployed --yolo-score-threshold 0.45 --yolo-intra-op-threads 8
```

`--yolo-score-threshold` 控制最低识别置信度。增大时误报通常减少、漏检增加；减小时召回提高、误报也会增加。V4b 当前验收值固定为 `0.45`，现场不要为了得到好看结果临时调低。

`--yolo-intra-op-threads` 控制一次 ONNX 推理使用的 CPU 线程数。增大可能加快推理但会增加 CPU 争用；减小会降低占用但可能增加延迟。当前机器持续验收值为 `8`。

### 3. 启动本地 Dashboard

```powershell
python tools\vision_web_server_视觉网页服务.py --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765/vision_dashboard.html
```

## 出发前 GO/NO-GO

真实无人机距离采集前运行：

```powershell
python tools\field_collection_preflight.py --mode distance
```

必须得到 `GO 17/17` 才进入场地。预检要求视觉来源是数字摄像头编号，例如 source `0`；MP4、AVI 或其他文件回放即使实时识别成功也会因 `physical_camera_source` 返回 `NO-GO`。它还核对正式模型 SHA256、有效画面、NodeA 在线与新鲜、启动编号和复位原因可追溯、当前启动已稳定至少 15 秒、空闲轨迹/事件、测试模式关闭、增强融合开启、舵机关闭、无云请求、V2 合同、记录器存在、输出可写和至少 2 GiB 可用空间。

需要同时采同一事件云端闭环时运行：

```powershell
python tools\field_collection_preflight.py --mode same-event
```

该模式在上述条件之外增加当前 `CLOUD,TEST 32/32` 汇总门槛，完整结果应为 `GO 18/18`。两种预检均只读取本机 API，不发送串口命令、不调用云 API；`NO-GO` 时先处理列出的失败项，不能带着红项开始正式试验。

当前冻结固件在上电和 `RESET` 后均保持 `servo_enabled=0 / servo_attached=0`。真实数据采集全程维持该状态；只有明确需要有人监护的机械跟踪演示时才通过统一串口收件箱发送 `SERVO,ON`，演示结束立即 `SERVO,OFF`。不要把“云台状态仍在计算”误解为 PWM 必须开启。

一次完整外场任务从这里开始时必须使用 `same-event` 模式，不要随后再用 distance 模式覆盖 `captures/latest_field_collection_preflight_report.json`。它将作为最终 8 小时同场时间窗的起点。

## A. LD2450 近距轨迹采集

### 先标定真实可用范围

1. 先让一个人在 LD2450 正前方约 1.5 到 3 米慢走。
2. 确认 `track_active=1`、`track_confirmed=1`，并观察四个位置/速度字段连续变化。
3. 在安全条件下逐点增加距离，每个点保持 8 到 12 秒。
4. 第一个无法连续确认的位置立即停止，不把它写成有效轨迹。
5. 最终只陈述现场实际测得的可用范围，不引用未经本机验证的距离宣传值。

无人机、行人、车辆、自然鸟类和杂波都遵守同一门禁。鸟类只能自然观察，不能人为驱赶；车辆必须在安全区域内测试。

### 采集命令

每次只采一个标签、一个实测距离和一个动作。`session-id` 中写入真实距离与动作，例如：

```powershell
python tools\collect_drone_dataset.py --label drone --duration-s 12 --interval-ms 200 --active-only --session-id drone_near_03m_hover_01
python tools\collect_drone_dataset.py --label person --duration-s 12 --interval-ms 200 --active-only --session-id person_near_03m_cross_01
python tools\collect_drone_dataset.py --label ebike --duration-s 12 --interval-ms 200 --active-only --session-id ebike_near_verified_cross_01
python tools\collect_drone_dataset.py --label car --duration-s 12 --interval-ms 200 --active-only --session-id car_near_verified_pass_01
python tools\collect_drone_dataset.py --label bird --duration-s 12 --interval-ms 200 --active-only --session-id bird_near_natural_01
```

只有无人机使用正样本标签 `drone`。人物、车辆、鸟类是负样本。没有真实确认航迹时不要为了凑数量删除 `--active-only`。

杂波基线可以不要求活动航迹，但必须单独标注：

```powershell
python tools\collect_drone_dataset.py --label clutter --duration-s 20 --interval-ms 200 --session-id clutter_site_idle_01
```

正式输出保持为：

```text
datasets/drone_recognition/real_tracks.csv
```

列结构保持不变：

```text
timestamp_ms,track_id,x_mm,y_mm,vx_mm_s,vy_mm_s,label
```

### 采集参数含义

- `--duration-s` 控制一段采集持续时间。增大可得到更长轨迹，但容易把多个动作混在一起；减小更容易保持单一动作，但低于稳定确认时间会形成短轨迹。建议每段 8 到 12 秒。
- `--interval-ms` 控制采样间隔。增大会减少重复行但降低时间分辨率；减小会增加采样密度，也会放大抖动和重复。当前建议 `200 ms`。
- `--max-stale-ms` 控制可接受的状态年龄。增大更能容忍慢轮询，但更容易接收旧状态；减小更严格，也可能在电脑繁忙时漏采。默认 `3000 ms`。
- `--active-only` 现在要求 `track_active` 和 `track_confirmed` 同时为 1，任一为 0 都不写入。

## B. V4b 视觉距离测试

10/30/50 米属于视觉实测点，不是预先承诺的有效距离。每个距离分别测试无人机、人物、车辆、鸟类或鸟类视频/自然目标，并保存以下证据：

```text
原始或连续录制视频
实际测量距离
detector_state
auto_lock_class_name
auto_lock_score
lock_source
VISION_LOCKED 持续时间
误报次数与漏检次数
对应截图及 capture_records.csv
```

目标在画面中不可辨认、自动锁定失败或光照不合格时，结果记为失败或不可测，不通过降低阈值伪造成功。50 米若受镜头焦距、场地或安全条件限制，要如实记录限制。

### 单次试验自动留证

每次10/30/50米试验使用只读记录器。它只读取 Dashboard 的 `/api/status` 和 `/api/node-status`，不会打开 COM4、发送串口命令或控制舵机：

```powershell
python tools\field_trial_recorder.py --session-id drone_10m_hover_01 --target drone --distance-m 10 --distance-source laser --action hover --site field_a --weather clear --lighting daylight --video-ref phone_drone_10m_hover_01 --duration-s 12 --interval-ms 200
```

正式试验只接受数字摄像头 source；文件回放会使每个采样无效，不能形成 `trial_valid=true`。

人物、车辆和鸟类分别把 `--target` 改为 `person`、`car` 和 `bird`。飞机、风筝等困难负样本可用 `airplane`、`kite`。每次必须更换 `session-id`；同名目录一旦存在，即使上一次失败或中断也会被拒绝复用，防止两次试验混成一条证据。

记录器为每个会话保存：

```text
captures/session_logs/field_trials/<session_id>/samples.jsonl
captures/session_logs/field_trials/<session_id>/trial_report.json
```

逐点记录包含 V4b 自动锁定、最高无人机分数、画面质量、NodeA 在线状态、启动编号、复位原因、运行时长、近距轨迹、事件号、测试模式、增强融合状态和 LD2451 远距字段。报告把结论分开：

- `trial_valid`：状态与画面是否足够完整，模型标签是否为正式 V4b。
- `performance_pass`：无人机是否检出，或负样本是否保持无误锁。
- `outcome`：`DETECTED/MISSED/CLEAR/FALSE_LOCK/INVALID_TRIAL`。
- `evidence_complete`：状态原始记录和对应视频哈希是否都存在。
- `physical_fusion_sample_count`：同一采样时刻同时满足物理摄像头自动锁定、LD2450 真实轨迹已确认、测试模式关闭、增强融合开启、融合级别达到 MID/HIGH 且真实事件活动的样本数。
- `physical_fusion_event_ids`：上述实机融合样本绑定的事件号；最终门要求其中包含严格 `15/15` 的同一个事件号。
- `node_boot_session_valid`：本段全部有效采样是否属于同一个启动编号，且运行时长没有倒退。
- `node_reset_observed`：本段是否观察到启动编号变化或运行时长回退；为 `true` 时整段固定为 `INVALID_TRIAL`，不能进入矩阵。

`result=PASS` 只表示记录过程有效，不能覆盖 `performance_pass=false` 或 `outcome=FALSE_LOCK/MISSED`。没有本地视频文件时，记录器仍保留完整状态，但返回非零且 `evidence_complete=0`，不得把该次写入正式矩阵。把手机或录屏原视频转入电脑后，用同一个会话号补哈希：

```powershell
python tools\field_trial_recorder.py --finalize-session drone_10m_hover_01 --video-file captures\field_videos\drone_10m_hover_01.mp4
```

若独立录制程序能在状态采样结束前停止写入本地视频，可在首次命令中直接增加 `--video-file <路径>`。原视频内容仍在变化时不要提前定稿哈希；使用手机录像时，先完成状态采样，转入原视频后再执行 finalize。

记录器会在创建会话目录前重新计算正式 V4b 文件 SHA256。模型不是冻结版本时直接返回 `MODEL_NOT_VERIFIED`，且不会占用本次 `session-id`。每条状态仍立即刷新到操作系统，磁盘强制同步改为每秒一次并在结束时再同步，降低 20 分钟记录期间由记录器自身造成的抖动；最终报告同时保存配置时长和真实经过时长。

## B.1 一次外场任务固定矩阵

“一次采集”指一次完整外场任务，不是每个条件只拍一条。正式核心矩阵固定为：

```text
目标：drone、person、car
距离：10 m、30 m、50 m
重复：每个目标和距离各 3 次独立试验
距离试验合计：3 x 3 x 3 = 27 次
长稳：静态杂波 20 分钟 + 正常人车环境 20 分钟
```

每次使用不同 `session-id` 和不同原视频。连续长视频可以留作全景旁证，但进入正式矩阵的 29 条报告必须分别绑定可独立核对的视频文件和 SHA256；不得复制同一视频充当多次试验。

建议按 `10 m -> 30 m -> 50 m` 顺序完成无人机，再按同样顺序完成人物和车辆。每完成一组就运行：

```powershell
python tools\field_evidence_gate.py
```

未采完时返回码 `2` 和 `NO-GO` 是正常结果。报告会列出剩余距离次数和长稳次数，不要凭纸面记忆判断是否已经采齐。当前尚无真实外场报告，基线必须是：

```text
NO-GO 3/22
remaining distance: 27
remaining stability: 2
```

两段长稳使用：

```powershell
python tools\field_trial_recorder.py --trial-kind long_stability --session-id stability_static_20m_01 --target clutter --distance-m 0 --distance-source not_measured --action static_site --site field_a --weather clear --lighting daylight --video-ref phone_stability_static_20m_01 --duration-s 1200 --interval-ms 200
python tools\field_trial_recorder.py --trial-kind long_stability --session-id stability_traffic_20m_01 --target person --distance-m 0 --distance-source not_measured --action normal_traffic --site field_a --weather clear --lighting daylight --video-ref phone_stability_traffic_20m_01 --duration-s 1200 --interval-ms 200
```

手机视频转入电脑后分别执行 `--finalize-session`。长稳只有配置时长和真实经过时长都不少于 1200 秒、全程状态中断为 0、负样本无误锁时才通过。

全部视频补哈希后再次运行 `field_evidence_gate.py`。同时出现以下结果只表示距离与长稳矩阵齐全，还必须继续通过后面的最终收工门：

```text
result=GO
checks=22/22
remaining=distance:0,stability:0
reports=eligible:29 或更多
```

核心表现门槛为：10 米无人机 3/3 检出；30 米无人机至少 2/3 检出；50 米如实记录挑战结果，不伪造通过；人物和车辆各距离均不得出现误锁。损坏报告、旧模型、文件回放、实际长稳不足和重复视频都会使总门保持 `NO-GO`。

上述比例按全部有效正式试验计算。10 米出现一条有效漏检后，后补三条成功不会伪装成“3/3”；30 米按全部有效试验的检出率判断。状态中断、黑帧等无效试验可以保留并用新会话补采，但有效漏检和误锁不能靠删除报告或追加好看样本隐藏。正式距离只接受激光、卷尺或已标定场地，`estimate` 不进入核心矩阵；视频引用或文件路径必须包含对应 `session-id`。

## B.2 真实事件与最终收工门

在同一个物理摄像头场景创建全新真实无人机事件后，立即运行严格闭环并保存到最终门固定路径：

```powershell
python tools\single_node_evidence_closure_check_单节点证据闭环核对.py --base-url http://127.0.0.1:8765 --require-national-first-evidence --report-file captures\latest_real_drone_strict_closure_report.json
```

升级后的严格 15 项总数不变，但“视觉证据有效”同时要求事件证据哈希内的 source 是数字物理摄像头、`physical_camera_source=1`，并且模型标签为正式 V4b。MP4 即使识别、抓拍和云返回全部成功也会失败；旧回放报告不能进入最终门。

完成 27 条距离试验、两条长稳、全部视频 finalize 和真实事件严格 15/15 后，运行唯一最终收工命令：

```powershell
python tools\field_evidence_gate.py --mode mission-final --preflight-report captures\latest_field_collection_preflight_report.json --strict-closure-report captures\latest_real_drone_strict_closure_report.json
```

它把矩阵 22 项再加上 `same-event` 预检、真实事件严格 15/15、同一严格事件的实机传感器融合和单次外场 8 小时时间窗，共 26 项。实机融合要求物理 V4b 锁定、LD2450 确认轨迹、测试模式关闭和增强融合开启出现在同一个采样点，不能用分散的历史记录拼接。只有以下结果才能结束外场：

```text
mode=mission-final
result=GO
checks=26/26
remaining=distance:0,stability:0
```

最终报告保存为 `captures/latest_field_mission_final_report.json`。任何一条正式报告早于本次预检、晚于 8 小时截止时间、真实事件不是物理摄像头来源，或实机融合事件号与严格事件号不同，都会阻止历史证据拼接。

## C. LD2451 远距预警测试

在 10/30/50 米安全测试点记录：

```text
ld2451_valid
ld2451_range_m
ld2451_speed_mps
ld2451_approach
far_motion_trigger
实际测量距离
目标类型与动作
```

LD2451 数据用于证明远距运动预警和融合阶段变化，不写入 `real_tracks.csv`，也不能单独证明“识别出无人机”。只有视觉类别、近距轨迹、身份链和云端结果在同一事件中一致时，才能陈述完整识别闭环。

## 每段现场记录

每次采集都记录：

```text
session_id
日期和时间
传感器证据线
目标真实标签
实测距离
动作
天气、风和光照
遮挡与金属/玻璃反射环境
track_active/track_confirmed
视觉置信度与锁定结果
成功、失败或不可测
备注
```

不要只保留成功样本。失败、误报和不可测条件同样是国赛答辩需要的真实性证据。

上述元数据必须直接作为 `field_trial_recorder.py` 参数输入，不再只写在纸上或依赖文件名猜测。状态中断、黑帧、旧模型、重复会话和视频缺失都会保留明确结果，不允许手工把失败目录改成成功目录。

## 训练与验收

采完后运行：

```powershell
python tools\multirotor_classifier_验证.py --input datasets\drone_recognition\real_tracks.csv --train --output-dir outputs\drone_recognition_real
```

如果真实 CSV 还没有有效轨迹，工具必须返回：

```text
ERROR,no_real_tracks
ok=false
acceptance.passed=false
```

此时不会自动生成合成样本、图表或新模型。`--mock` 只用于明确的算法演示，不能和真实数据验收混用；不带 `--input` 或 `--mock` 也会直接拒绝运行。

重点查看无人机召回率、人物/车辆/鸟类误报、混淆矩阵和按真实 `session_id` 分组后的泛化结果，不能只看总准确率。如果真实数据不达标，保留原始记录并分析雷达航迹质量、类别数量、动作覆盖和环境反射，不能修改标签掩盖问题。

## 与联网闭环的关系

本 SOP 的近距轨迹、视觉距离和远距预警可在无公网时完成。云端 API、W-iPhone 热点和“同一真实事件严格 15/15”必须在网络恢复后单独验收；PC 完整回归 `25/25`、距离预检 `17/17`、同事件预检 `18/18`、矩阵总门 `22/22` 和最终任务门 `26/26` 各自证明不同边界，均不能相互代替。
