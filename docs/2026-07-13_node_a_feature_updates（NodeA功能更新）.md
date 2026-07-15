# 2026-07-13 NodeA 功能更新

## 计划位置

2026-07-13 / 三天国一冲刺 / 第 3 步：V4b 困难负样本训练、独立评测与 ONNX 运行链验收。

## 本轮完成

1. 查明 V1 数据映射错误：来源数据集的类别 `0` 和 `1` 都是无人机，但 V1 只把类别 `1` 当作无人机，类别 `0` 被错误当成背景。
2. 生成修正类别后的 V3 数据集，并加入 COCO128、官方 COCO train2017 困难负样本与本地背景，形成 V4b 数据集。
3. 完成 V4b 训练并选定 `best.pt`，导出候选模型 `models/yolov8n_drone_v4b_candidate.onnx`。
4. 修复视觉桥把非方形画面强行拉伸到 `640x640` 的问题，改为保持宽高比缩放、用 114 灰色填充，再按缩放和填充量还原检测框。
5. 增加 `1280x720` 非方形画面的回归检查，防止以后再次出现训练评测正常、实际运行漏检的问题。

## 为什么要改

训练和 Ultralytics ONNX 在同一批 103 张图上都是 `TP=85`，旧 Sidecar 只有 `TP=74`。模型导出本身没有损失，真正问题是 Sidecar 把宽屏画面直接拉成正方形，目标外形被压扁，造成 11 个真目标漏检。

修复后，Sidecar 与 PyTorch、Ultralytics ONNX 完全一致：

```text
TP=85, FP=4, FN=24
P=95.506%, R=77.982%, F1=85.859%
```

## V4b 候选模型证据

- 候选 ONNX SHA256：`c33aba9e6e24ce24ae6147a538b46b0c1080093242f0ad1c59100c738121ac74`
- 独立 5000 张 COCO val2017：阈值 `0.45` 时误触 `120/5000 = 2.40%`。
- 103 张无人机运行时样本：召回率 `77.982%`，比旧拉伸链路提高 `10.092` 个百分点。
- 同一批 333 张重点 COCO 负样本：误触由 `22/333` 降为 `17/333`。
- 39 张本地实拍背景：`0/39` 误触。
- 475 张 CPU 运行时：平均 `30.555 ms`，中位 `30.169 ms`，P95 `34.816 ms`，最大 `46.124 ms`。

详细报告：

- `runs/drone/v4b_hardneg_acceptance_comparison.json`
- `runs/drone/v4b_runtime_parity.json`
- `runs/drone/v4b_onnx_runtime_acceptance.json`

## 验收结果

```text
python py_compile: PASS
vision_regression_checks: PASS (11/11)
Sidecar/PyTorch/Ultralytics parity: PASS
detector_state=READY_ONNX
runtime_provider=CPUExecutionProvider
```

## 诚实边界

1. V4b 已于 2026-07-13 通过授权晋级为正式运行模型；原 V1 已备份为 `models/yolov8n_drone_v1_backup_2026-07-13.onnx`，可按哈希回滚。
2. 这些结果不能代替外场真无人机距离测试；真实无人机、人、车、鸟和不同距离数据仍属于 2026-07-13 第 4 步。
3. COM4 已恢复且板端健康检查通过，但同一真实事件的严格 `15/15` 闭环证据仍未完成。

## 正式晋级记录

- 正式模型：`models/yolov8n_drone.onnx`
- 正式 SHA256：`c33aba9e6e24ce24ae6147a538b46b0c1080093242f0ad1c59100c738121ac74`
- V1 回滚 SHA256：`fae760436377ce66713be5cd5717cb945960c9f5878296923219af05a0a5ff45`
- 默认检测阈值：`0.45`
- ONNX 单次推理线程：`8`
- 预处理：`letterbox_640_pad114`

晋级只改变 PC 视觉模型与默认检测参数，不改变 ESP32 固件和 `TrackManager -> HunterAction -> GimbalController -> UPLINK` 主链。

## 持续延迟问题与修复

默认 ONNX Runtime 线程池与 OpenCV 的 24 线程在本机长跑时发生争用。短测约 `31 ms`，但两次 475 张默认线程压力测试的 P95 分别升到 `621.208 ms` 和 `570.933 ms`，因此没有隐去失败数据。

修复方式是把 ONNX 单次推理线程明确设为 `8`，跨推理并行线程设为 `1`，使用顺序执行模式。线程数增大通常能降低单次耗时，但过大会争抢 CPU；线程数减小会降低争用，但推理变慢。本机 4 线程测试 P95 为 `116.696 ms`，8 线程诊断 P95 为 `34.184 ms`，正式代码路径最终 P95 为 `34.816 ms`。

## 2026-07-12 第 2 步补充：COM4 单一入口与统一命令调度

### 本轮完成

1. `tools/node_a_serial_bridge_NodeA串口桥接.py` 增加唯一串口发送调度器。状态轮询、重复注入、视觉转发和外部临时命令不再在同一轮直接连续写 COM4，而是先进入同一个队列，每次只发送一条。
2. 状态类命令按键去重，只保留最新的 `TRACK`、`VISION`、`RID` 和查询命令；`CLOUD,TEST` 等动作命令不去重，避免漏执行。
3. `TRACK,CLEAR`、`VISION,LOST`、`CLOUD,ENABLE,0` 等安全命令具有最高优先级。待发送的安全清除不会被低优先级旧轨迹覆盖。
4. 队列增加容量上限和过期时间。外部命令默认 `30 s` 过期，过期文件直接丢弃，避免桥接重启后重放旧动作。
5. 新增 `tools/node_a_serial_command_NodeA串口命令.py`。该工具只向 `captures/serial_command_inbox/` 原子写入请求文件，绝不打开 COM4。

常用命令：

```powershell
python tools\node_a_serial_command_NodeA串口命令.py "CLOUD,STATUS"
python tools\node_a_serial_command_NodeA串口命令.py "TRACK,CLEAR" "VISION,LOST"
```

### 参数说明

- `--serial-min-send-interval`：控制任意两条串口命令的最小间隔，默认 `0.10 s`。增大后更稳但响应稍慢；减小后响应更快，但短命令集中时更容易堵塞。
- `--serial-command-queue-limit`：控制待发送命令上限，默认 `64`。增大可容纳更多突发命令，但会增加旧命令积压风险；减小能更快暴露异常洪峰，但更容易拒绝低优先级请求。
- 命令请求 `ttl_ms`：控制请求允许等待的时间，默认 `30000 ms`。增大可容忍桥接短暂停顿，但旧命令存活更久；减小可减少重放风险，但繁忙时更容易过期。

### 验收证据

```text
python py_compile: PASS
vision_regression_checks: PASS (12/12)
COM4 live dispatcher PID: 41904
serial bridge connected count: 1
external inbox accepted: 11
pending request files: 0
serial stderr bytes: 0
NodeA uptime: 761943 ms and continuing
```

真实 COM4 联调在同一个桥接进程内连续提交 `CLOUD,STATUS`、`RID,STATUS`、`FUSION,STATUS`、`REALINPUT,STATUS`、`CONFIG,STATUS`、`RISK,STATUS`、`EVENT,STATUS`、`SUMMARY` 和 `SELFTEST`，均得到设备响应。连接次数保持为 1，开发板 uptime 连续增长，证明提交临时命令没有重开串口或触发复位。

### 诚实边界

1. 统一入口已经覆盖常驻串口桥接内部和新临时命令工具，但 `track_injector`、单板测试、RID 模拟器仍是专用串口所有者模式；运行这些工具前仍必须先停止常驻桥接，下一轮再评估是否迁移到同一命令入口。
2. Windows 下 `vision_bridge` 写 `latest_status.json` 时仍发现一次文件替换占用异常，该问题与串口冲突不同，尚待单独授权修复。
3. 本轮只修改 PC 工具，没有修改或重刷 ESP32 固件。

## 2026-07-12 第 2 步补充：视觉状态写入并发稳定性

### 本轮完成

1. `tools/vision_bridge_视觉桥接.py` 写入 `captures/latest_status.json` 时，临时文件内容仍只写一次；如果 Windows 在替换瞬间返回 `PermissionError`，则等待后重试替换，不重复生成或改写状态内容。
2. 默认最多尝试 `10` 次，每次间隔 `0.05 s`，最坏额外等待约 `0.45 s`。次数增大可容忍更长的短暂占用，但真正异常时退出更晚；次数减小能更快暴露持续占用，但更容易把短暂杀毒扫描或读取锁误判为故障。间隔增大会降低连续碰撞概率但更新变慢，间隔减小响应更快但可能连续撞上同一次占用。
3. 回归检查模拟第一次替换失败、第二次成功，确认目录只创建一次、临时 JSON 只写一次、替换执行两次，并且最终载荷不变。

### 验收证据

```text
python py_compile: PASS
vision_regression_checks: PASS (13/13)
20 s high-contention test: vision process alive / serial process alive
vision_state=VISION_LOCKED
detector_state=READY_ONNX
lock_source=YOLO_AUTO
status_age_ms=133
vision stderr bytes=0
serial stderr bytes=0
```

压力测试中，读取端持续短时占用状态文件并同时请求网页接口。视觉写入进程没有再因文件替换占用退出，状态仍持续刷新，说明本轮写入端修复有效。

### 诚实边界

1. 本轮只修复视觉写入端，没有修改检测、跟踪、抓拍、事件和串口主链，也没有修改 ESP32 固件。
2. 压力测试同时暴露网页服务读取端的独立问题：`vision_web_server` 直接读取状态文件时没有处理 `PermissionError`，20 秒内出现 HTTP 连接中断和请求线程异常。写入端已经通过，但整条“写入 + 网页读取”并发链路尚不能记为全通过。
3. 当前联调画面来自保留数据集视频，只能作为集成稳定性证据，不能代替外场真实无人机证据，也不能代替同一真实事件严格 `15/15`。

## 2026-07-12 第 2 步补充：网页读取视觉状态并发稳定性

### 本轮改动

1. `tools/vision_web_server_视觉网页服务.py` 的 `load_json_file` 在 Windows 短暂拒绝读取时不再让请求线程直接异常退出，而是有限重试；连续失败后返回结构化 `read_denied`，HTTP 连接仍能正常完成。
2. 默认最多读取 `6` 次、间隔 `0.03 s`，最坏额外等待约 `0.15 s`。次数或间隔增大可以容忍更长占用，但接口最坏响应更慢；减小可缩短等待，但更容易把瞬时占用暴露给页面。
3. 回归检查同时覆盖“第一次失败后恢复”和“达到上限后稳定返回错误”，不允许无限等待。

### 验收证据

```text
python py_compile: PASS
vision_regression_checks: PASS (14/14)
active vision writer PID: 42740
web server PID: 26940
COM4 serial bridge PID: 7744
20 s direct file reads: 477 success / 10 transient conflicts
20 s HTTP reads: 487 success / 0 disconnects
vision_state=VISION_LOCKED
detector_state=READY_ONNX
lock_source=YOLO_AUTO
frame_content_ready=1
status_age_ms=84
vision/web/serial stderr bytes: 0 / 0 / 0
```

直接文件读取器故意不带重试并把文件保持打开 `25 ms`，因此它出现 `10` 次瞬时冲突，证明测试期间确实发生了 Windows 文件占用；网页接口依靠有限重试仍完成 `487/487` 次请求。视觉写入端、网页读取端和 COM4 桥接均未退出，整条状态文件并发链路通过本轮验收。

本轮仍只修改 PC 工具和验证文档，不修改 ESP32 固件及 `TrackManager -> HunterAction -> GimbalController -> UPLINK` 主链。

## 2026-07-12 第 2 步补充：统一命令入口的定时序列

### 改动原因

统一串口调度会主动合并尚未发送的重复状态命令，这是防止串口洪峰所必需的；但事件确认需要同一 `TRACK` 在不同时间点多次到达。如果把多个相同 `TRACK` 一次性写入收件箱，它们可能在桥接发送前被合并，无法形成板端连续确认。

### 本轮完成

`tools/node_a_serial_command_NodeA串口命令.py` 新增 `--interval-s`，按指定间隔逐个生成原子请求文件，仍然不打开 COM4。默认值为 `0`，原有单命令和批量命令行为保持不变。

现场有人看守时的重复确认示例：

```powershell
python tools\node_a_serial_command_NodeA串口命令.py --interval-s 0.20 "TRACK,320,1000" "TRACK,320,1000" "TRACK,320,1000" "EVENT,STATUS"
```

`--interval-s` 控制两个请求进入桥接收件箱的时间差。增大后重复状态更容易逐条发出，但整段序列更慢；减小后更快，但过小时仍可能在调度器中被合并。当前串口最小发送间隔为 `0.10 s`，现场重复确认建议使用 `0.20 s`。

### 验收证据

```text
python py_compile: PASS
vision_regression_checks: PASS (15/15)
temporary inbox requests: 3/3
command order: TRACK -> TRACK -> EVENT,STATUS
partial request files: 0
COM4 motion commands executed: 0
```

用户上课且硬件无人看守期间只做临时收件箱离线测试，没有向 COM4 下发任何运动命令。真实事件序列必须在用户回到设备旁后执行。

## 2026-07-12 第 2 步补充：视觉心跳与状态轮询共存

### 根因

压力验收把视觉转发间隔设为 `0.25 s`。旧逻辑每次都重复 `VISION,CONF` 和 `VISION,LOCKED`，约占 `8 条/s`；再加 `STATUS`、`EVENT,STATUS` 和 `LASTEVENT` 约 `3.75 条/s`，超过串口最小发送间隔 `0.10 s` 对应的约 `10 条/s` 容量。板端仍在回复视觉命令，但低优先级轮询长期排不到发送机会，网页因此把 NodeA 标记为离线。

这不是 COM4 断线，也不需要拔插开发板。

### 修复

首次锁定或置信度/稳定度变化时仍发送完整的 `VISION,CONF + VISION,LOCKED`；锁定内容不变的周期心跳只发送 `VISION,LOCKED`。安全清锁、状态变化和首次置信度同步保持原逻辑。

### 验收证据

```text
python py_compile: PASS
vision_regression_checks: PASS (15/15)
live bridge PID: 29824
vision forward interval: 0.25 s
serial min send interval: 0.10 s
20 s sustained check: PASS
NodeA online: 1
status stale age: 146 ms
bridge stderr bytes: 0
STATUS / EVENT,STATUS / LASTEVENT responses: continuing
unchanged-window VISION confidence responses: 1
VISION lock heartbeats: continuing
```

`--vision-forward-interval` 增大时串口占用更低，但视觉状态变化传到板端稍慢；减小时响应更快，但占用更多串口带宽。本次节流使压力值 `0.25 s` 也能与轮询共存，正式默认值 `0.75 s` 仍更宽松。

本轮只修改 PC 串口桥和回归，不修改 ESP32 固件或主链算法。

## 2026-07-13 第 4 步：真实轨迹采集防污染门禁

### 问题与修复

1. `tools/collect_drone_dataset.py` 原来默认读取 `captures/e2e_node_status.json`，该文件停留在旧测试阶段；现在统一读取桥接当前默认文件 `captures/latest_node_status.json`。
2. 原逻辑只相信 JSON 内已经冻结的 `stale_age_ms`。现在联合检查状态自报延迟、`last_update_ms`、状态文件更新时间和 `online`；桥接停止后，文件年龄会继续增加并自动拒绝采集。
3. `--active-only` 原来在“活动或确认任一成立”时就会写入。现在必须 `track_active=1` 且 `track_confirmed=1`，防止尚未稳定确认的瞬时轨迹污染真实训练集。
4. 更新原有 `docs/2026-06-08_real_data_collection_sop_v1.md`，明确 LD2450 只负责现场验证有效的近距二维轨迹，10/30/50 米分别作为 V4b 视觉和 LD2451 远距预警实测点，三类原始能力不再混写。

### 参数影响

`--max-stale-ms` 默认 `3000 ms`。增大可容忍更慢的状态轮询，但更容易接收旧数据；减小会更严格，但电脑繁忙时可能漏采。`--allow-stale` 仅保留给人工调试，正式数据不得使用。

### 验收证据

```text
python py_compile: PASS
vision_regression_checks: PASS (16/16)
fresh current status CLI: OK, 4/4 rows, effective age 108 ms
retired e2e status CLI: NO_ROWS, 4/4 rejected, reason OFFLINE
retired e2e effective age: 1552407574 ms
COM4 commands sent: 0
firmware changed: no
```

本轮只读取现有状态文件并把命令行验证结果写到系统临时目录，没有占用 COM4、没有驱动舵机，也没有把测试行写入正式 `real_tracks.csv`。

## 2026-07-13 第 4 步：重复采集会话保护

### 根因与修复

分类器按 `track_id` 把 CSV 行分组。同一 `session-id` 重跑时，采集时间会再次从 `0 ms` 开始；旧采集器仍会追加相同 `track_id`，两段轨迹随后被错误合并，持续时间和速度特征会失真。

采集器现在会在启动前用 `csv.DictReader` 检查既有文件：

1. 同标签、同 `session-id` 已存在时，默认返回 `SESSION_ID_EXISTS`，在任何写入前中止。
2. 相似前缀或其他标签不会被误判为同一会话。
3. 既有 CSV 列结构不等于正式 7 列时返回 `OUTPUT_SCHEMA_MISMATCH`，不再向坏文件中间追加第二个表头。
4. `--allow-session-reuse` 只作为明确调试覆盖。开启后可能合并时间轴，正式现场数据不得使用。
5. 旧 `2026-05-16_field_collection_runbook_v1.md` 已收口为当前 SOP 的短入口，旧 e2e 状态路径、固定摄像头编号/CSRT 和错误距离表不再作为现场命令。

### 验收证据

```text
python py_compile: PASS
vision_regression_checks: PASS (16/16)
first live-status CLI run: OK, 4 rows
second identical session CLI run: SESSION_ID_EXISTS
CSV rows after rejected rerun: 4
schema mismatch guard: PASS
similar-prefix / different-label checks: PASS
COM4 commands sent: 0
```

本轮命令行输出仍位于系统临时目录，没有修改正式真实数据集。

## 2026-07-13 第 4 步：干净真实数据基线与 mock 隔离

### 旧基线审计

原 `datasets/drone_recognition/real_tracks.csv` 只有 50 行、1 条 `clutter_20260516_125842_t0`，四个运动字段全部为 0。它形成于当前在线、新鲜度、确认轨迹和重复会话门禁之前，且没有距离或参考视频元数据。分类器只得到 1 个负样本，`recall=0`、验收失败，不能作为本轮国赛真实数据证据。

原文件已无损归档到本地忽略目录：

```text
datasets/drone_recognition/raw/archive/2026-05-16_unverified_clutter_tracks.csv
SHA256 c574ae68e53833e9ebdeb6c0a7a126970387e26eedece2a81391ee363a4686b3
rows=50
hash_match=true
```

同目录保存结构化审计 JSON。活动 `real_tracks.csv` 现在只保留正式 7 列表头、数据行为 0，等待现场新数据；旧数据未删除，可按哈希恢复。

### 分类器真实输入守门

定位到旧分类器在显式 `--input` 没有轨迹时会自动切换到 12 条 mock，并输出 `source=:fallback_mock`。现在：

1. `--input` 与 `--mock` 必须显式二选一。
2. 真实输入为空时输出 `ok=false`、`error=no_real_tracks`、`acceptance.passed=false` 并返回非零。
3. 空输入不会生成合成 CSV、图表或新模型；同一输出目录中的旧分类器图表会被清除，避免残留结果误导。
4. 显式 `--mock` 仍保留 12 条算法基线；有效样例 CSV 的原流程与指标不变。
5. `datasets/drone_recognition/README.md` 已收口为当前 SOP 的数据入口，明确干净 0 行基线、唯一会话编号和 mock/真实来源隔离。

### 验收证据

```text
red test before fix: FAIL, resolve_input_rows missing
python py_compile: PASS
vision_regression_checks: PASS (17/17)
empty real input: no_real_tracks, ok=false, row_count=0
empty output cleanup failures: 0
empty output remaining files: summary JSON only
explicit mock: 12 rows, warning retained
sample_tracks.csv: PASS, source unchanged, accuracy=1.0, recall=1.0
active real_tracks.csv: 0 rows, valid header
COM4 commands sent: 0
```

本轮没有删除旧样本、没有改分类公式，也没有覆盖现有 `models/multirotor_tree.pkl`。

## 物联网竞赛材料：官方要求映射与一页摘要收口

### 官方要求核对

2026-07-13 重新核对乐鑫官方命题页，硬要求仍为：指定 ESP32 芯片作为核心主控、至少一种传感器融合、至少一个云端大模型，以及设备下行响应或非音视频感知数据上行。当前项目逐项映射为 ESP32-S3 NodeA、多源传感融合、火山方舟豆包和结构化上行/受控下行。

官方来源：`https://www.espressif.com/zh-hans/ecosystem/education/competition/iot`

### 材料修正

1. 重写 `docs/2026-05-09_exec_summary_v1.md`，第一屏改为物联网主链和官方四项映射，不再以反无人机算法参数开场。
2. 删除把 `5-100 m` 设计目标写成检测指标、把估算 `16 ms` 写成实测、把旧 CSRT 链写成当前实现的口径。
3. 摘要只保留有来源的 V4b 独立测试指标和 ONNX 延迟，并把真实距离、真实轨迹与同事件严格 `15/15` 标为 `PENDING`。
4. 明确视觉推理运行在现场 PC 网关，ESP32-S3 是融合、事件、云端通信和指令响应核心，不冒充 MCU 端视觉推理。
5. 修正 V4b 模型卡中“V1 仍部署”的过期句子，当前正式模型与备份关系一致。
6. 原场景矩阵明确标注 2026-04-14 是台架命令场景，新增无人机/人物/车辆/鸟类、10/30/50 米、LD2450、LD2451 和同事件 15/15 的真实矩阵，所有未测格保持 `PENDING`。

### 当前材料边界

软件回归 `21/21`、V4b 离线指标和历史云端告警分别有证据，但不能拼接成一条同场真实闭环。最终摘要只有在外场和 W-iPhone 验收后，才允许把对应 `PENDING` 改成实测结果。

## 物联网竞赛材料：答辩日运行入口 V2

1. 原 `2026-05-16_demo_submission_runbook_v1.md` 已按当前链路原位更新，不再启动旧 e2e 状态文件、固定 `source 1` 或强制 CSRT。
2. 启动前固定要求 W-iPhone 最大兼容性、COM4 单一桥接所有者、摄像头 readiness 和正式 V4b 模型。
3. 真实目标模式禁止发送 `TRACK`；台架模式保留定时收件箱命令，但必须明确标注模拟且只在有人看守时执行。
4. 常驻硬件模式的验收固定使用 `--no-run-suite --skip-usb`，避免验收程序与桥接/视觉争抢串口和摄像头。
5. 视频脚本以 ESP32-S3 多源融合、豆包结构化上行、下行执行和同事件严格 `15/15` 为主线，并明确不展示任何密钥。
6. 直播失败时，V4b、历史云端和当前严格失败只能分开呈现，不能剪成同一事件成功。

当前 runbook 已可用于回来后的操作顺序，但其中 `cloud_online=1`、真实目标和 `15/15 PASS` 仍需当场取得，不是本轮文档修改产生的证据。

### 当前基线复核

```text
PlatformIO firmware build: SUCCESS
RAM: 51336 / 327680 bytes (15.7%)
Flash: 1004381 / 3342336 bytes (30.1%)
vision_regression_checks: PASS (17/17)
board flash performed: no
```

编译只生成本地 `.pio` 构建产物，没有刷写或重启开发板。

## 物联网竞赛材料：误报漏报记录 V2

1. 原记录中“当前回归未发现明确误报/漏报”只来自台架状态机场景，容易被误读为真实识别结果；现已拆成台架、V4b 离线和外场三层。
2. 写入 V4b 独立集 `TP=85 / FP=4 / FN=24`，明确当前仍有漏检。
3. 写入 COCO val2017 在阈值 `0.45` 下的 5000 张压力结果：总触发 `120`，人物 `58/2693`、车辆 `18/535`、飞机 `15/97`、鸟 `4/125`、风筝 `4/91`。
4. 这些数值统一称为“图片触发”，不冒充现场连续误锁率；飞机 `15.464%` 被明确列为重点弱项。
5. 新增真实 10/30/50 米误报漏报矩阵和两项 20 分钟长稳，所有未测格保持 `PENDING`。
6. 在外场结果出来前保持 V4b 正式阈值 `0.45`，不通过临时调阈值美化结果。

本轮只更新证据口径，不重新训练或修改模型，符合先完成原计划现场实测、再决定是否扩展训练的顺序。

## 物联网竞赛材料：答辩 Q&A V2

1. Q&A 从算法宣传改为 ESP32-S3、多源融合、豆包上行/下行、边缘安全执行和同事件证据主线。
2. 删除无实测来源的雾天/弱光置信度区间、3/5/7 帧误报率和 30 米内完全不受影响等数字。
3. 修正轨迹确认参数：当前 `TrackConfig::ConfirmFrames=3`，不是旧材料写的 5；V4b 自动起锁另需两次稳定检测。
4. 明确 V4b 在 PC 网关运行、NodeB RID 可为模拟身份链、handoff 是单节点距离推导预留、降落伞硬件未集成。
5. 增加云断网本地降级、云端命令白名单和来源事件号校验、密钥不入仓库/视频等物联网答辩问题。
6. “能否保证国一”的标准回答改为不能保证奖项，只能用同场实证、真实统计、稳定演示和物理完成度提高竞争力。

所有 Q&A 数值均能回到当前代码、V4b 模型卡或压力 JSON；外场和严格 15/15 仍明确未完成。

### 答辩 runbook 云端启用补充

`CloudConfig::AiEnabledByDefault=false`，因此 runbook 已补成：先通过统一收件箱发送 `CLOUD,ENABLE,1`，再执行独立 `CLOUD,TEST`，等待完成后查询 `CLOUD,STATUS`。测试事件只用于网络/API 预检，随后必须创建新的真实主事件。

排障现在分为 `enabled`、`configured`、`wifi` 和 `cloud_online/error` 四层，避免把默认关闭、密钥缺失、热点连接和 API 请求失败混为一个问题。当前公共网络期间没有实际发送这些命令。

## 当前运行入口：正式 V4b 命令冻结

1. USB readiness 推荐命令显式包含正式模型、`drone-v4b-hardneg-deployed`、阈值 `0.45`、ONNX intra-op 线程 `8` 和自动锁定，不再依赖隐藏默认值。
2. 启动助手在 readiness 报告存在时只读取结构化的 source/backend/tracker 字段，再用当前模板重建命令；旧报告中的过期命令字符串不会被原样复用。
3. 用户指定的 `--python-cmd` 会进入重建命令；本轮用旧 readiness 报告和 `py -3` 验证，输出保持 `dshow/source 0/MIL` 且升级为正式 V4b 标签和参数。
4. readiness 报告缺失时，fallback 也带完整 V4b 参数，并通过 tracker 自动回退避免 CSRT 不可用导致启动失败。

### 验收证据

```text
python py_compile: PASS
vision_regression_checks: PASS (18/18)
deployed_v4b_startup_commands: PASS
old readiness report rebuild: PASS
selected python command preserved: py -3
rebuilt camera selection: dshow / source 0 / MIL
fallback model/label/threshold/threads: PASS
COM4 opened by tests: no
```

阈值或线程增减的影响没有改变：阈值增大通常减少误触发但增加漏检；线程增大可能降低推理时间但加重 CPU 争用。正式值继续固定为已验收的 `0.45/8`。

## 离线总验收与严格门槛反向验证

1. 答辩 runbook 的正式视觉命令已显式固定 `--source-warmup-frames 12` 和 `--yolo-auto-lock`，与 readiness、启动助手一致。
2. 当前无新主事件时，以 `--require-national-first-evidence` 读取真实本地 API；门槛正确返回 `FAIL (3/15)` 和退出码 `2`，没有把历史事件、旧导出或离线模型结果误判为完整闭环。
3. 失败项明确覆盖同事件抓拍、严格绑定、V4b 自动锁定、有效画面、证据哈希、云端命令执行和来源事件一致性；本次反向验证没有自动导出，也没有修改正式证据。
4. A1 串口桥和本地网页继续健康运行；视觉运行时为 `OFFLINE`，原因是有限测试录像已经播放结束，返校后需使用真实摄像头重新执行 readiness。

### 验收证据

```text
Python py_compile: PASS
vision_regression_checks: PASS (18/18)
firmware_safety_checks: PASS (critical sections 102/102)
PlatformIO build: SUCCESS
RAM: 51336 / 327680 bytes (15.7%)
Flash: 1004381 / 3342336 bytes (30.1%)
web health/data source: live / OK
NodeA: online=1, IDLE, COM4 bridge PID 29824
strict negative gate: expected FAIL (3/15), exit=2
strict auto export attempted: false
COM4 commands sent: 0
camera started: no
board flash performed: no
```

这个 `FAIL` 是防伪验收结果，不是新故障。只有用户回来切回 W-iPhone、刷新真实摄像头、通过云端预检并产生同一条新主事件后，才允许重新运行并争取 `15/15 PASS`。

## 严格 15/15 正向可达性回归

1. 新增 `strict_closure_cli_positive`，在系统临时目录构造唯一事件号、有效纹理抓拍、`YOLO_AUTO`、正式 drone 类别、有效画面元数据、云端回令来源事件号和 USB 就绪证据。
2. 测试短暂启动随机 localhost 端口，通过正式网页 API 和正式 `single_node_evidence_closure_check` CLI 运行，不直接绕过命令入口调用判定函数。
3. 主事件门槛达到 `15/15 PASS`；工具随后创建严格导出，导出快照再次达到 `15/15 PASS`，回放详情、事件证据哈希和视觉证据哈希均一致。
4. 临时服务、图片、JSON、CSV、报告和导出在测试结束后全部随临时目录清理；正式 `captures/`、COM4、摄像头和公网没有被触碰。
5. 再次读取当前正式证据仍为预期 `FAIL (3/15)`，证明临时正向夹具没有污染真实结果。

### 验收证据

```text
python py_compile: PASS
strict_closure_cli_positive: PASS
national-first live fixture gate: PASS (15/15)
strict export snapshot gate: PASS (15/15)
strict export replay/hash checks: PASS
vision_regression_checks: PASS (19/19)
current formal evidence gate: expected FAIL (3/15), exit=2
COM4 commands sent: 0
camera/public network used: no
```

这里的临时正向结果只证明验收程序具备完整通路，不是比赛现场证据。国一主证据仍必须由用户在场时产生的新真实事件取得。

## 新主事件时间防伪门槛

1. 严格模式新增主机记录时间校验，默认 `national_first_max_event_age_ms=900000`，只接受最近 15 分钟内记录的事件。
2. 时间优先读取事件记录的 `host_logged_ms`；缺失主机时间、超过允许年龄或明显来自未来都会使总体严格验收失败。
3. 新鲜度作为 `15/15` 内容检查之外的前置门槛，保持原有 15 项含义不变；只有内容和时间均通过，工具才会创建严格导出。
4. 新增 `strict_closure_cli_stale_guard`：完整内容仍为 `15/15`，人为改成 16 分钟前后，CLI 正确返回 `event_stale` 且不尝试导出。
5. 当前正式历史事件实测年龄约 `10.19e6 ms`，因此除了原有缺失项外，也被新鲜度门槛正确拒绝。

### 验收证据

```text
fresh strict CLI fixture: PASS 15/15 + freshness PASS
stale strict CLI fixture content: PASS 15/15
stale strict CLI fixture overall: FAIL (event_stale)
stale strict auto export attempted: false
vision_regression_checks: PASS (20/20)
current formal event freshness: FAIL, age about 10190536 ms > 900000 ms
COM4/camera/public network used: no
```

最大年龄增大时允许更旧的事件进入验收，操作更宽松但防伪能力下降；减小时更严格，但录屏准备稍慢就可能超时。正式值保持 15 分钟，不用放宽参数掩盖现场问题。

## 答辩 Dashboard 第一屏收口

1. 页面名称改为 `Flytotal 低空安全 AIoT`，首屏直接呈现 ESP32-S3、雷达/RID/视觉融合、V4b、豆包回令和严格证据，不再以 Day5-Day7 冻结管理开场。
2. 新增四段实时主链总览和统一判定；模拟模式、Node A 离线、V4b 未就绪、豆包离线或严格证据未通过都会明确阻止“可作为完整现场证据”的绿色结论。
3. 修复旧摘要只统计构建包失败数而显示“0 个失败项”的歧义。历史套件、字段契约、证据文件和严格闭环现在分开命名，闭环 `FAIL` 不会被“证据文件 READY”掩盖。
4. 双节点与协同感知移到页面末端，并明确标注“非计划必要内容，推荐扩展方向”，不再抢占 Node A 物联网主链的第一屏。
5. 最新图片增加时间和事件绑定标签；当前录像抓拍显示为“历史抓拍、约 1.9 小时前、未绑定事件”，不会冒充实时外场证据。
6. 页面主色改为中性工作台配色，去除装饰渐变，主要面板圆角收紧为 8 px，桌面和手机保持稳定尺寸。

### 浏览器验收

```text
Playwright / Microsoft Edge: PASS
desktop viewport: 1440 x 900
mobile viewport: 390 x 844
desktop horizontal overflow: false
mobile horizontal overflow: false
overview fields present: true
console errors: 0
page errors: 0
request failures: 0
current live verdict: danger (expected)
current blockers: V4b offline / cloud offline / strict evidence fail
historical capture warning visible: yes
```

当前红色总判定是公共网络和有限录像结束后的真实状态，不是页面故障。用户回来后需要让 Node A、V4b、豆包和新事件严格证据逐项转为通过，再录制最终状态。

## 2026-07-12 第 2 步补充：豆包同事件回显与边缘安全离线收口

### 根因与改动

1. 原实现虽然把请求 `event_id` 上传给豆包，但返回 JSON 不要求携带该字段；成功后又直接把本地队列事件号写入 `cloud_command_source_event_id`。因此历史“来源事件号一致”只能证明本地绑定，不能证明豆包真实回显。
2. 返回契约现要求豆包原样回显输入 `event_id`。固件解析后拒绝缺失号 `response_event_id_missing` 和错号 `response_event_id_mismatch`，真实请求还会拒绝已关闭或已切换事件 `active_event_mismatch`。
3. `CLOUD,RESULT` 现在同时输出 `expected_event_id` 与 `response_event_id`；真实成功指令只使用云端回显号写入审计字段，不再用队列号代填。
4. `CLOUD,TEST` 只验证网络、API、JSON 和事件号契约，即使模型建议动作也不执行，固定记录 `TEST_RESPONSE_VALIDATED`、`cloud_test_no_apply` 和 `no_apply=1`。
5. 降落伞硬件未集成，提示词不再允许模型建议该动作；防御分支收到旧/异常 `TRIGGER_PARACHUTE` 时记录 `PARACHUTE_REJECTED_NOT_INTEGRATED`、`applied=false`、`edge_veto=1`。
6. 高威胁状态下拒绝切换 `ECONOMY` 时，旧代码错误标记 `applied=true`；现已改为 `false`，与 `DOWNGRADE_REJECTED_THREAT_ACTIVE` 和 `edge_veto=1` 一致。

### 离线验收证据

```text
firmware_safety_checks: PASS
critical sections: 104/104
PlatformIO build: SUCCESS
RAM: 15.7% (51336 / 327680 bytes)
Flash: 30.1% (1005269 / 3342336 bytes)
vision_regression_checks: PASS (21/21)
git diff --check: no whitespace errors
real API calls: 0
COM4 commands sent: 0
board flash performed: no
```

### 当前边界与返场顺序

本轮只证明新逻辑可以编译、静态守门能抓住旧危险调用、现有回归没有被破坏；没有证明豆包真实按新 JSON 契约返回。当前 COM4 上运行的开发板仍是刷写前固件。用户回来后必须先切回 W-iPhone 并打开最大兼容性，再停止唯一串口桥、释放 COM4、刷写新固件、重启唯一桥接，随后运行 `CLOUD,TEST`。预检必须看到 `validated=1,no_apply=1` 且 expected/response 均为 `A1-CLOUD-TEST`；之后再创建新的真实活动事件，取得三方事件号一致和严格 `15/15 PASS`。

## 2026-07-12 第 2 步补充：COM4 进程级唯一所有者

1. 根因确认：桥接原来先写初始状态、事件和结果 JSON，最后才打开 COM4；第二桥或串口监视器即使打开失败，也可能先污染正式文件。
2. 新桥接按端口取得操作系统跨进程锁，锁文件与可读 PID 元数据都位于系统临时目录。第二份新桥在碰串口和正式证据前返回 `SERIAL_OWNER_CONFLICT`，并报告当前持有者 PID。
3. 主入口顺序固定为“取得进程锁 -> 成功独占打开串口 -> 才允许读取或写入正式状态文件”。不遵守锁的旧桥或 PlatformIO Monitor 占用端口时，也会在证据零写入的情况下失败。
4. 跨进程回归证明互斥、PID 可读、释放后可重获；假串口占用执行真实 `main()`，五类临时正式输出均未创建，失败后锁可再次取得。
5. 完整回归增至 `21/21 PASS`；测试只使用系统临时目录和假串口，没有打开 COM4。

当前 PID `29824` 的桥接是在代码更新前启动的，内存中没有新锁。不要为了离线测试打断它；用户返场后按“停止旧桥 -> 刷写 -> 启动唯一新桥”的顺序启用保护，并确认首行出现 `SERIAL_OWNER_ACQUIRED`。

## 2026-07-12 第 2 步补充：云契约 V2 与严格门槛防旧固件

1. 新固件在普通 `STATUS` 和 `CLOUD,STATUS` 输出 `cloud_contract_version=2`、`cloud_event_echo_required=1`、`cloud_test_no_apply=1` 和运行态 `cloud_test_validated`。
2. `cloud_test_validated` 开机为 0；重新发起测试、断网或关闭云端时清零；只有豆包返回事件号完整且与测试请求一致后才置 1。
3. 桥接、网页节点状态、事件对象、`cloud_llm` 和严格导出已贯通四字段。事件详情与 Dashboard 第一屏会显示 V2 能力和预检状态。
4. 严格 15 项总数不变；原第 15 项 `cloud_event_match` 现在同时要求来源事件号等于主事件、契约版本至少为 2、回显和测试不执行能力为 1、本次启动预检为 1。
5. 新增反向用例删除四字段后，旧固件夹具必须失败；V2 正向夹具、严格导出快照、回放与双哈希继续通过。

### 离线验收

```text
legacy cloud contract fixture: expected FAIL
V2 strict fixture: PASS 15/15
strict export snapshot/hash replay: PASS
firmware_safety_checks: PASS (critical sections 105/105)
vision_regression_checks: PASS (21/21)
PlatformIO: SUCCESS
RAM: 15.7% (51336 / 327680 bytes)
Flash: 30.1% (1005677 / 3342336 bytes)
current formal evidence: expected FAIL 3/15 + event_stale
board flash / API / COM4 command: no
```

### Dashboard 浏览器验收

live 旧板状态在桌面和手机均显示 `V0 · LEGACY/UNKNOWN`、`preflight WAIT`，总判定阻止作为完整证据；临时 8766 mock 正向数据能显示 `CLOUD READY`、`V2 · ECHO · NO-APPLY` 和 `PASS`，但总判定仍明确“模拟链路不可作为比赛现场证据”。两种桌面/手机视口均无横向溢出，控制台错误、页面错误和失败请求为 0。临时 8766 已关闭，原 8765 未中断。

返场必须先刷写并重启新桥，再只发送 `CLOUD,STATUS` 核对 V2 三项能力和 `validated=0`；版本确认后才允许执行 `CLOUD,ENABLE,1` 与 `CLOUD,TEST`，成功后必须看到 `validated=1`，再开始真实主事件。

## 2026-07-12 第 2 步补充：云端原始回显进入严格证据

### 发现的缺口

固件已经输出 `CLOUD,RESULT` 的请求事件号、期望事件号和豆包返回事件号，但旧桥接只保存普通 `STATUS`，原始返回会在终端中一闪而过。原第 15 项主要依赖 `cloud_command_source_event_id`，能证明边缘执行绑定，却不能在导出里直接展示豆包原始回显。

### 本轮改动

1. 唯一串口桥新增 `CLOUD,STATUS`、`CLOUD,TEST`、`CLOUD,RESULT` 和 `CLOUD,DEGRADED` 持久化。
2. 请求、期望、返回事件号分别保存为 `cloud_request_event_id`、`cloud_expected_event_id`、`cloud_response_event_id`，并同时保存来源、HTTP 状态、ESP 错误、延迟、结果错误和主机接收时间。
3. 测试事件单独保存为 `cloud_test_response_event_id` 和 `cloud_test_result_no_apply`；回归明确证明 `A1-CLOUD-TEST` 与正式返回均不会覆盖当前主事件号。
4. 网页状态、事件对象、嵌套云端对象、严格导出和 Dashboard 事件详情全部透传原始字段，事件证据哈希会覆盖这些内容。
5. 严格门槛仍为 15 项；第 15 项现在还要求测试原始无动作返回、正式来源为 `EVENT_OPENED`、请求/期望/返回三事件号等于当前主事件、HTTP 为 2xx、ESP 错误为 0、结果错误为 `NONE`。

### 离线验收

```text
python py_compile: PASS
dashboard JavaScript syntax: PASS
firmware_safety_checks: PASS
critical sections: 105/105
vision_regression_checks: PASS (21/21)
PlatformIO build: SUCCESS
RAM: 15.7% (51336 / 327680 bytes)
Flash: 30.1% (1005677 / 3342336 bytes)
strict V2 + raw result fixture: 15/15 PASS
missing raw result fixture: cloud_event_match FAIL (expected)
cloud test/main event overwrite guard: PASS
```

浏览器使用更新后的网页服务和 mock V2 数据完成桌面、手机双尺寸检查：云端显示 `V2 · ECHO · NO-APPLY`、预检 `PASS`、请求/期望/返回均为同一 mock 事件、原始结果为 `EVENT_OPENED / HTTP 200`；桌面 `1440` 和手机 `390` 的页面宽度均无横向溢出，页面错误为 0。临时 `8766` 服务与无头浏览器随后均已关闭，原 `8765` 未中断。

对当前正式旧事件重新运行新严格检查，结果仍为预期 `FAIL 3/15`，同时命中 `event_stale`、`cloud_event_match` 和双哈希缺口；没有生成严格导出。这个反向结果证明新门槛没有把旧证据错误染绿。

本轮没有打开 COM4、没有调用真实 API、没有刷写开发板。当前 PID `29824` 的老桥和 PID `26940` 的老网页进程仍连续运行，但它们尚未加载本轮 Python 逻辑；用户返场刷写后必须各自正常重启一次，新的原始回显持久化才生效。

## 2026-07-12 第 2 步补充：Dashboard 云预检同口径

原 Dashboard 的“安全预检 PASS”只看固件 `cloud_test_validated=1`。如果仍运行旧桥或原始 `CLOUD,TEST` 行丢失，页面会先显示就绪，但严格第 15 项会在最后失败。

现在页面只有同时满足以下条件才显示 `CLOUD READY / PASS`：云契约 V2、事件回显能力、测试不执行能力、固件本次启动验证成功、桥接观察到 `no_apply=1`、原始测试返回号为 `A1-CLOUD-TEST`。固件已验证但缺原始证明时显示 `CLOUD UNSAFE / RAW WAIT`，总判定明确写出“CLOUD,TEST 原始无动作回显未持久化”。事件详情使用相同口径。

浏览器正向 mock 显示 `CLOUD READY / PASS`；在浏览器内临时删除两个原始测试字段后显示 `CLOUD UNSAFE / RAW WAIT`。桌面宽度 `1440`、手机宽度 `390` 均无横向溢出，手机云端卡片右边界为 `380`，页面错误为 0。JavaScript 语法和完整回归 `21/21 PASS`。临时 `8766` 与无头浏览器已关闭，未修改证据文件、未访问 API、未打开 COM4。

## 2026-07-12 第 2 步补充：返场只读云端预检

1. 现有严格核对工具新增 `contract` 和 `test` 两个只读预检阶段，统一读取本机 `/api/node-status`，不发送串口命令、不调用豆包 API，也不覆盖正式 `15/15` 报告。
2. `contract` 阶段用于刷写并重启新桥后拦截旧固件、旧桥和残留测试状态；要求 V2、事件回显、测试不执行能力、配置就绪、默认关闭且原始测试/结果字段为空。
3. `test` 阶段用于 `CLOUD,TEST` 后核对 Wi-Fi/云端在线、原始 `no_apply`、三个 `A1-CLOUD-TEST` 事件号、HTTP/ESP 状态和 `TEST_RESPONSE_VALIDATED` 未执行结果。
4. 回归覆盖两个阶段的正向、残留状态、缺原始无动作证明、事件号错配和真实 CLI 报告分支；返场命令已写入既有演示手册。
5. Python 语法、固件安全守门 `105/105` 和完整回归 `21/21` 通过；测试阶段正向夹具为 `26/26 PASS`。当前旧 `8765` 的 `contract` 只读实测按预期为 `7/12 FAIL`，明确缺少新状态/V2/回显/测试不执行/配置证明；独立报告已写入 `captures/latest_cloud_preflight_report.json`。
6. 原桥 PID `29824`、原网页 PID `26940` 和 `8765` HTTP 200 均保持运行；本轮未重启进程、未打开 COM4、未调用真实 API、未刷写开发板。因本轮没有改 C++，未重复编译固件；当前源码最近一次 PlatformIO 构建仍为 `SUCCESS`，RAM `15.7%`、Flash `30.1%`。

## 2026-07-12 第 2 步补充：高风险云端动作稳定策略

1. 审计发现真实模型即使正确回显事件号，若对高风险主事件返回 `NONE`、`ECONOMY` 或其他被边缘拒绝的动作，严格第 14 项仍会失败并停在 `14/15`。
2. 豆包系统提示词现在把策略写成确定规则：`A1-CLOUD-TEST` 返回 `HIGH + GENERATE_ALERT` 但 NodeA 只验证不执行；非合作 `HIGH_RISK/EVENT` 或视觉确认无人机的主事件必须返回 `HIGH/CRITICAL + GENERATE_ALERT`；高风险禁止 `NONE` 和 `ECONOMY`。
3. Chat 请求增加 `temperature=0.1` 以降低同输入输出波动；提示词约 `1626` 字节，与最大事件 JSON 及请求外壳仍能放入现有 `4096` 字节请求缓冲区。
4. 该策略没有绕过 ESP32-S3 的本地安全校验。测试分支仍禁止调用动作执行函数，降落伞仍明确禁止，主事件返回仍需通过事件号、参数范围、威胁状态和硬件集成检查。
5. 固件安全守门 `105/105 PASS`，完整回归 `21/21 PASS`，测试预检正向夹具 `26/26 PASS`；PlatformIO 构建 `SUCCESS`，RAM `51336/327680`（`15.7%`），Flash `1006129/3342336`（`30.1%`）。
6. 本轮未调用真实 API、未打开 COM4、未刷写开发板。提示词稳定策略是否被真实豆包严格遵守仍是返场必测项，不能用本地构建结果代替。
7. 答辩 Q&A、执行摘要和演示手册已同步当前安全事实：模型协议不允许 `TRIGGER_PARACHUTE`，NodeA 只保留 `applied=false + edge_veto=1` 的防御性拒绝；主材料旧回归数已更新为 `21/21`。

## 2026-07-12 第 2 步补充：返场服务版本与预检顺序纠错

1. 返场手册原来写“服务健康可复用”，但 PID `29824` 的旧桥和 PID `26940` 的旧网页均未加载最新 Python 逻辑；现已明确本次返场必须正常停止并分别只启动一份新进程，PID 只作当前定位参考，实际按 COM4/8765 所有者确认。
2. 初始本地检查原来在云端默认关闭、尚未执行 `CLOUD,TEST` 前就要求 `cloud_online=1`，顺序自相矛盾；现已改为先只检查 NodeA 与 V4b，云在线和无错误只在测试成功后要求。
3. 本轮只修改操作文档，没有停止当前进程、没有打开 COM4、没有调用 API。

## 2026-07-12 第 2 步补充：`CLOUD,TEST` 异步预检有界等待

1. 豆包请求由固件异步执行。原来的 `test` 只读预检只读取一次本机状态，如果命令刚入队而响应尚未返回，会把正常等待过程误判为失败。
2. 预检工具新增 `--cloud-preflight-wait-s` 和 `--cloud-preflight-poll-interval-s`。默认等待为 `0`，保持原有单次读取；返场手册显式使用 `30` 秒上限。
3. 等待期间只轮询本机 `http://127.0.0.1:8765/api/node-status`，不会发送串口命令、不会重复执行 `CLOUD,TEST`，也不会自行访问豆包 API。全部 `26/26` 条件满足时立即提前成功，超过上限仍不完整则诚实失败。
4. 独立预检报告新增尝试次数、等待上限、轮询间隔和实际等待时间，便于判断是云端尚未返回还是返回内容不合格。
5. 回归夹具覆盖“先返回请求中状态，随后返回完整结果”和“始终不完整直至超时”两条路径；Python 语法和完整回归均通过。

### 离线验收

```text
python py_compile: PASS
async cloud test preflight: PASS (2 polls, 26/26)
bounded timeout path: PASS (expected FAIL, no unbounded wait)
vision_regression_checks: PASS (21/21)
real API / COM4 / board flash: 0
```

## 2026-07-12 第 2 步补充：正式高风险云返回硬门槛

1. 返场前审计发现，云提示词虽然要求高风险返回 `HIGH/CRITICAL + GENERATE_ALERT`，但固件在 JSON 和事件号通过后会直接把结果置为成功，没有在代码中执行同一语义校验。
2. 严格 15 项中的第 14 项原先也只要求云在线、命令已执行且效果非空，因此 `MEDIUM + ADJUST_THRESHOLD + THRESHOLD_UPDATED` 会被错误接受；新增反例在修复前稳定失败并证明这个漏洞真实存在。
3. `CloudClient` 现在对测试事件、`HIGH_RISK/EVENT` 和视觉确认无人机强制执行策略校验。威胁等级不是 `HIGH/CRITICAL` 或命令不是 `GENERATE_ALERT` 时，分别记录 `test_policy_mismatch` 或 `high_risk_policy_mismatch`，结果不得进入执行成功分支。
4. 严格第 14 项总数不变，但现在只接受 `HIGH/CRITICAL + GENERATE_ALERT + ALERT_GENERATED`。错误风险等级、非告警命令或未形成告警效果都会明确命中 `cloud_command_applied` 失败。
5. 安全守门新增代码顺序检查：策略校验必须位于事件号回显校验之后、`result.ok=true` 之前，并覆盖测试、两种高风险等级和视觉确认无人机四类触发条件。
6. 完整回归首次运行时发现严格导出正向夹具缺少 `cloud_threat_level`，说明新门槛确实生效；只补齐夹具的 `HIGH` 字段后，未放宽生产门槛，完整回归恢复通过。

```text
W-iPhone SSID: connected
ark.cn-beijing.volces.com TCP 443: PASS
PlatformIO: SUCCESS
RAM: 51336 / 327680 bytes (15.7%)
Flash: 1006565 / 3342336 bytes (30.1%)
firmware_safety_checks: PASS (108/108)
compiled_secrets: PASS (3/3)
vision_regression_checks: PASS (22/22)
non-alert strict fixture: expected FAIL before fix / rejected after fix
firmware SHA256: cf4ea802108a02db52951c93bb5763adce7f6e64ea19c18dfff68df2e9402774
real API / board flash / same-event strict 15/15: pending
```

当前 `COM4` 仍由旧桥 PID `29824` 占用，网页 `8765` 仍由旧服务 PID `26940` 提供；两者没有加载本轮新代码。下一步必须停止这两个已核实的旧进程、刷入上述哈希固件并启动唯一新桥和新网页，再按 `16/16 -> 一次 CLOUD,TEST -> 32/32 -> 新真实事件 15/15` 顺序取得现场证据。

该结果只证明返场核对工具能适配异步时序，不能证明豆包已经真实返回。用户回来后仍需切回 W-iPhone、打开最大兼容性，并按返场手册只发送一次 `CLOUD,TEST`，再运行带 `--cloud-preflight-wait-s 30` 的只读核对。

## 2026-07-12 第 2 步补充：云预检空场基线

1. 审计发现原两阶段预检没有直接要求 `track_active=0`、`event_active=0` 和 `event_id=NONE`。如果真实目标过早进入雷达范围，自动主事件请求可能与测试请求交叉，覆盖刚取得的原始 `TEST` 结果。
2. `contract` 和 `test` 共用的基础条件新增 `track_idle` 与 `event_idle`。后者同时要求主事件未活动且当前事件号为空；字段缺失同样失败，避免旧桥或不完整状态默认为空场。
3. contract 条件由 `12` 项增至 `14` 项，test 条件由 `26` 项增至 `28` 项。活动轨迹和活动事件分别有反向夹具，都会给出明确失败项。
4. 返场时先让真实目标离开雷达范围，完成 `14/14` 契约预检和 `28/28` 测试预检后，才让目标进入并创建唯一新主事件。

### 离线验收

```text
python py_compile: PASS
empty-field contract fixture: PASS (14/14)
empty-field async test fixture: PASS (28/28, 2 polls)
active track guard: PASS (expected track_idle FAIL)
active event guard: PASS (expected event_idle FAIL)
vision_regression_checks: PASS (21/21)
current old 8765 contract: expected FAIL (9/14)
current old 8765 idle baseline: track_idle PASS, event_idle PASS
```

当前旧运行态的五个失败项为云状态未观察到、V2 缺失、回显能力缺失、测试不执行能力缺失和配置证明缺失。它没有被新检查误判为活动事件，但仍必须刷写并重启新桥与新网页后才能进入真实 API 测试。

## 2026-07-12 第 2 步补充：`CLOUD,TEST` 板端防重复

1. 根因是测试请求使用 `force=true`，会绕过普通事件的同事件和 10 秒间隔保护；云队列容量为 `3`，所以重复命令原本可能形成多次真实请求。
2. 固件现在分别记录测试是否已排队、云请求是否正在执行，并检查队列是否还有待处理请求。任一忙碌条件成立时返回 `reason=request_busy`，不追加第二个测试。
3. 本次启动已经完成有效测试时，再次发送返回 `reason=already_validated`，保持已有成功状态和原始证据，不重新调用 API。
4. 测试从队列取出时，状态由“测试待处理”切换为“云请求执行中”；入队失败会清除待处理标记，避免永久误报忙碌。
5. 正式 `EVENT_OPENED` 请求、云端返回校验、边缘动作和 `TrackManager -> HunterAction -> GimbalController -> UPLINK` 主链没有改动。

### 离线验收

```text
firmware_safety_checks: PASS
critical sections: 108/108
PlatformIO build: SUCCESS
RAM: 15.7% (51336 / 327680 bytes)
Flash: 30.1% (1006353 / 3342336 bytes)
vision_regression_checks: PASS (21/21)
firmware.bin SHA256: 7f8dc3d26486069b1cd8aa9c3db02dbb2e35a7e7851004ea63aeff645581d110
real API / COM4 / board flash: 0
```

第一次编译准确暴露聚合初始化少一个布尔值，补齐 `test_request_pending=false` 后重新完整编译成功。当前 COM4 上仍是旧固件，只有返场刷写上述新构建后，板端防重复才会生效。

同时修正固件安全守门的取块位置：测试不执行检查现在明确定位到 `AiCloudTask -> if (ok) -> if (isTestRequest)` 的真实成功分支，并要求其中存在 `TEST_RESPONSE_VALIDATED` 且不存在 `applyCloudCommand`，不再误检查前面的状态清零小分支。

桥接解析同步隔离跳过日志：只有同时带 `validated/no_apply/response_event_id` 的真实 `CLOUD,TEST` 结果才刷新 `cloud_test_result_received_ms`。回归先写入有效证明，再依次解析 `already_validated` 和 `request_busy`，验证三项证明字段及原始接收时间完全不变；完整回归继续 `21/21 PASS`。

## 2026-07-12 第 2 步补充：桥接与网页服务版本硬门槛

1. 新桥初始化状态固定写入 `serial_bridge_contract_version=2`；新网页的 live 和 mock `/api/node-status` 固定写入 `web_evidence_contract_version=2`。
2. `contract` 和 `test` 预检都要求两个版本至少为 2，因此“新固件 + 旧桥”“新桥 + 旧网页”会在 API 测试前直接失败。
3. contract/test 条件分别由 `14/28` 增至 `16/30`。两个独立反向夹具把桥版本或网页版本改为 0，均命中对应失败项。
4. 当前仍运行的旧 `8765` 只读实测为预期 `9/16 FAIL`；除了五项 V2 云能力缺失，还明确缺少两个 PC 进程版本。

### 离线验收

```text
python py_compile: PASS
new bridge + new web contract fixture: PASS (16/16)
version-gate checkpoint fixture: PASS (30/30; superseded below by 32/32)
legacy bridge fixture: expected serial_bridge_contract_v2 FAIL
legacy web fixture: expected web_evidence_contract_v2 FAIL
current old 8765 contract: expected FAIL (9/16)
vision_regression_checks: PASS (21/21)
API / COM4 / board flash: 0
```

另在隔离端口 `8876` 临时启动当前网页服务，通过真实 HTTP `/api/node-status?mode=mock` 读取到 bridge/web 均为版本 2；进程随后关闭，`8876` 已释放，原 `8765` 继续返回 HTTP 200。回归还直接绑定桥初始状态和网页常量，避免只更新夹具而漏改实际输出。

## 2026-07-12 第 2 步补充：豆包测试语义策略预检

1. `test` 预检新增两项模型语义门槛：`cloud_result_threat_level` 必须为 `HIGH/CRITICAL`，`cloud_result_command_type` 必须为 `GENERATE_ALERT`。测试条件由 `30/30` 增至 `32/32`，`contract` 仍为 `16/16`。
2. 这次测试依旧是 `no_apply=1`：只验证豆包是否按高风险策略返回，不执行告警、模式或硬件动作。这样能在真实目标进场前发现 `LOW + NONE` 等不合格模型响应，降低正式主事件停在 `14/15` 的风险。
3. Dashboard 比赛总览和云端详情统一使用四态显示：尚未验证为 `WAIT`、缺原始证明为 `RAW WAIT`、策略不合格为 `POLICY WAIT`、全部符合才为 `PASS`。修复了总览拦截但详情误显示 `PASS` 的不一致。
4. 负向夹具把返回改为 `LOW + NONE`，必须同时命中两项策略失败；正向夹具继续为 `HIGH + GENERATE_ALERT`。

### 离线验收

```text
cloud contract fixture: PASS (16/16)
cloud test policy fixture: PASS (32/32)
LOW + NONE policy fixture: expected FAIL (2 policy checks)
mobile viewport: 390 / client 390 / scroll 390, no overflow
positive dashboard: CLOUD READY / overview PASS / detail PASS
negative dashboard: CLOUD UNSAFE / overview POLICY WAIT / detail POLICY WAIT
browser runtime exceptions / log errors: 0 / 0
real API / COM4 / board flash: 0
```

隔离测试使用临时 `8878/8879` 网页端口和 `9225/9226` 浏览器调试端口；验收后均已释放，临时夹具已删除。原桥 PID `29824`、原网页 PID `26940` 和 `8765` HTTP 200 未中断，但旧进程仍没有加载新代码。返场必须切回 W-iPhone、打开最大兼容性，并按“空场 -> 停旧桥和旧网页 -> 刷写 -> 启动唯一新桥和新网页 -> `16/16` -> 一次 `CLOUD,TEST` -> `32/32` -> 目标进场”的顺序操作。

## 2026-07-12 第 2 步补充：本地密钥 Git 防泄露守门

1. 已确认 Wi-Fi 名称、Wi-Fi 密码和豆包 API Key 三项均存在于本地 `include/secrets.h`；该文件未被 Git 跟踪且命中 `.gitignore`。检查只读取是否存在和长度，不输出真实值。
2. 固件安全守门不再只检查 `.gitignore` 文本，而是调用 Git 获取全部受跟踪文件：若 `include/secrets.h` 曾被强制加入索引，即使后来增加忽略规则也会立即失败。
3. 安全守门扫描全部 `403` 个当前受跟踪文件，并分别检查工作区内容和 Git 待提交索引。它拒绝 Ark Key 形态，也会把本地 Wi-Fi 密码或 API Key 的真实字节与两层内容比较；错误只报告符号名和文件路径，不报告值。
4. 完整回归新增四种系统临时仓库：安全正例通过；强制跟踪 `secrets.h` 被拒绝；假 Key 先写入并暂存、随后只清理工作区但不更新索引时仍被拒绝；历史提交残留 Key 也被拒绝。索引反例在修复前可稳定错误放行，修复后明确报告 `Git index`。临时仓库自动删除，完整回归由 `21/21` 增至 `22/22 PASS`。
5. 答辩 Q&A、执行摘要和演示手册当前数字已同步为固件安全守门 `108/108`、PC 完整回归 `22/22`。这些仍是离线软件证据，不替代返场真实 API 和新事件严格 `15/15`。
6. `firmware_safety_checks.py` 新增显式参数 `--require-compiled-secrets`。它要求 Wi-Fi 名称、密码和 API Key 均已配置且存在于指定 `firmware.bin`，成功只输出 `compiled_secrets: PASS (3/3)`；缺任一项只报告符号名，不显示值。普通不带参数的安全检查仍可在编译前运行。
7. 回归同时构造完整和缺 API Key 的临时二进制：完整 `3/3 PASS`，缺项按预期失败且错误文本不含假值。演示手册已把带参数检查固定在“构建完成后、停服务和刷写前”。
8. 守门再检查全部可达 Git 历史的 Ark Key 形态。当前仓库历史命中 `0`；回归仓库先提交假 Key、再提交干净版本，当前工作区和索引均干净时仍会因 `reachable Git history` 失败，且不输出历史补丁或 Key。
9. 全工作区审计发现旧模式会把第三方库中的 `mark-...` 等普通文本截取成 `ark-...`，根因是缺少左边界。工作区、Git索引和Git历史三处模式现统一要求前一字符不是字母、数字或下划线；`mark-normal_identifier` 正例通过，真实假 Key 反例仍失败。修复后全工作区只命中预期的本地 `include/secrets.h` 一处。

```text
git secret hygiene: PASS (403 tracked files)
safe temporary repository: PASS
forced tracked secrets.h: expected FAIL
tracked copied API key: expected FAIL
staged key with clean worktree: expected Git index FAIL
clean HEAD with key in reachable history: expected FAIL
current reachable Git history Ark-key matches: 0
normal mark-* text: PASS (not a key)
workspace Ark-key matches: 1 expected local-only file / 0 unexpected
error output contains secret values: no
latest firmware contains all 3 configured values: yes (boolean-only check)
compiled secret guard CLI: PASS (3/3)
incomplete firmware fixture: expected FAIL, value not disclosed
firmware_safety_checks: PASS (108/108)
vision_regression_checks: PASS (22/22)
real API / COM4 / board flash: 0
```

## 2026-07-12 第 2 步返场：真实刷写、云证据组行与 32/32

1. 已确认 `W-iPhone`、互联网、豆包主机 TCP 443 和 `COM4` 可用。普通 PlatformIO 上传能识别 ESP32-S3 并运行 stub，但在验证 Flash 连接时稳定断流；低速复现与 `--no-stub flash_id` 对照证明根因是 RAM stub 交接，不是端口、Flash 芯片或固件大小。
2. 使用 ROM 原生 `--no-stub --verify` 按项目四段地址写入，bootloader、分区表、boot_app0 和 firmware 全部 `digest matched`。新桥和新网页随后唯一启动，版本均为 2，空场云契约达到真实 `16/16 PASS`。
3. 第一次真实 `CLOUD,TEST` 在板端成功：云在线、测试已验证、`HIGH + GENERATE_ALERT`、效果 `TEST_RESPONSE_VALIDATED`，但 PC 原始测试/结果字段为空，预检只有 `20/32`。这次不能算完整证据，也没有伪造字段补绿。
4. 根因是 AI 云任务用多次 `Serial.print` 拼装结果，期间主循环的长状态输出可能插入，导致桥接无法按行识别。三类关键记录现在先用 `snprintf` 组装，并把内容与换行通过一次 `Serial.write` 发出；缓冲异常会明确记录 `serial_line_overflow`。
5. 安全守门新增永久限制：AI 云任务必须调用三类单行函数，关键记录不得恢复成分段 `Serial.print`。修复后 PlatformIO、`108/108`、编译配置 `3/3` 和完整回归 `22/22` 全部通过。
6. 修复固件再次逐段刷写校验。在与失败时相同的状态轮询和视觉转发并发压力下，第二次且仅一次补测于约 10.9 秒后达到真实 `32/32 PASS`，原始测试号、请求/期望/返回事件号、HTTP 200、ESP 0、`HIGH + GENERATE_ALERT`、结果时间和 `no_apply` 全部落盘。

```text
current firmware SHA256: 89e4e7b7915a58e5f04a526eb4d4c4399beceed8af542bd1d4dc70e5d29b7752
PlatformIO: SUCCESS
RAM: 51336 / 327680 bytes (15.7%)
Flash: 1006985 / 3342336 bytes (30.1%)
firmware_safety_checks: PASS (108/108)
compiled_secrets: PASS (3/3)
vision_regression_checks: PASS (22/22)
board flash: PASS, four regions digest matched
cloud contract preflight: PASS (16/16)
real CLOUD,TEST preflight: PASS (32/32), attempts=22, waited_ms=10905
```

当前唯一桥 PID `26120`、网页 PID `26812`、真实视觉桥 PID `3436` 均在线。USB 摄像头 source 0、1280x720画面、亮度和 V4b `READY_ONNX` 已通过，但连续 60 秒仍为 `VISION_IDLE / none`，说明真实无人机尚未进入镜头；同一新主事件严格 `15/15` 仍未完成，不能用旧视频或历史抓拍替代。

## 2026-07-12 第 2 步旁证：归档画面回放闭环

`非计划必要内容，推荐扩展项`。用户在图书馆且没有无人机，本轮不再尝试采集真实无人机事件。为继续核对软件集成链，使用已有真实无人机抓拍生成明确标记的回放源 `captures/replay_sources/2026-07-13_archived_real_drone_replay.mp4`，SHA256 为 `f2ae8e463894f954d7159129eb50a43a51c54d5174e7ba3700ea179b09630031`。该素材只作回放联调，不属于现场真实无人机证据。

回放视觉重新达到 `YOLO_AUTO + drone + 0.89 + frame quality OK`。事件 `A1-0000555062-0001` 的正式云请求因 `HTTP -1 / ESP 28676` 失败，事件 `A1-0000578257-0002` 没有取得自身匹配的成功云结果，两者均未拼接或计入通过证据。第三个全新事件 `A1-0000817702-0003` 自身取得三个精确绑定抓拍，云请求、期望、返回和边缘执行事件号全部一致，`HTTP 200 / ESP 0 / CRITICAL / GENERATE_ALERT / ALERT_GENERATED`。

严格核对结果为 `15/15 PASS`，事件新鲜度 `PASS`，严格导出快照再次 `15/15 PASS`，事件证据哈希和视觉证据哈希均可回放。报告为 `captures/2026-07-13_replay_event_A1-0000817702-0003_strict_closure_report.json`，导出为 `captures/event_exports/event_evidence_A1-0000817702-0003_1783945665025.json`。全过程 `servo_enabled=0`，结束时 `track_active=0`、`event_active=0`。

这只证明同一事件的软件闭环已经可达，不能把当前计划项改成“真实事件已完成”。真实无人机严格 `15/15` 仍待带无人机返场后重新生成全新事件；随后才进入 2026-07-13 第 4 步外场类别、距离和长稳实测。

## 2026-07-13 第 4 步返场前准备：外场单次试验自动留证

审计发现原 SOP 要求人工记录距离、目标、动作、环境和视频，但现有 `collect_drone_dataset.py` 只保存 LD2450 七列轨迹；视觉/LD2451 试验失败时也可能只剩终端输出。这会造成现场成功却无法把原视频、距离和状态证明绑定到同一次试验。

新增 `tools/field_trial_recorder.py`。它只读本机 `/api/status` 与 `/api/node-status`，不打开 COM4、不发送命令、不改变模型、阈值或固件。每个唯一会话持续写 `samples.jsonl`，结束后生成 `trial_report.json`，同时绑定目标、实测距离来源、动作、场地、天气、光照和视频引用。重复会话直接拒绝；状态中断、黑帧、旧模型和误锁不会被隐藏。

报告明确拆分记录有效性 `trial_valid`、识别表现 `performance_pass/outcome` 和证据完整性 `evidence_complete`。无人机为 `DETECTED/MISSED`，负样本为 `CLEAR/FALSE_LOCK`；即使记录过程正常，负样本误锁也不会被写成性能通过。原视频存在时计算 SHA256；尚未转入电脑时报告保持不完整，后续只能用同一会话号执行 finalize 补哈希，不能重跑覆盖失败试验。

TDD 先确认模块缺失导致完整回归红灯，再实现正向无人机检出、负样本误锁、黑帧拒绝、状态全断、重复会话、样本哈希和视频哈希夹具。物理来源与出发预检加入时回归为 `24/24 PASS`，后续外场总门扩充后当前为 `25/25 PASS`。这只证明记录工具可用，不代表任何真实距离格已经实测；矩阵继续保持 `PENDING`。

第一次用真实 `8765` API 做回放烟测时，记录器取得 `12/12` 有效采样，这反而暴露“实时文件回放可能被当成外场来源”的漏洞。现已把数字摄像头 source 加入记录器和出发预检双层硬门槛：回放源即使 `YOLO_AUTO + drone + 0.89` 也为无效外场采样，并在预检得到 `NO-GO 15/16`，唯一失败项为 `physical_camera_source`。

新增 `tools/field_collection_preflight.py`，只读核对正式模型哈希、视觉实时性、物理摄像头、画面质量、NodeA 在线、空闲轨迹/事件、测试模式、舵机安全、云请求、V2 合同、记录器、输出可写和磁盘空间。当前 USB 摄像头 source `0`、正式 V4b 和板端安全基线真实达到 `GO 16/16`，报告为 `captures/2026-07-13_field_collection_preflight_physical_camera_go.json`。停止摄像头后最新报告重新为 `NO-GO 15/16 / vision_runtime_fresh`，没有保留假在线状态；板端为 `VISION_LOST`、`servo_enabled=0`、`track_active=0`、`event_active=0`。

## 2026-07-13 第 4 步返场前准备：一次外场任务总门

为把“采一次”落实为一次外场出行内完成全部证据，而不是每格只赌一条样本，新增 `tools/field_evidence_gate.py`。核心矩阵固定为 `drone/person/car x 10/30/50 m x 3`，共 27 条独立距离报告；另要求静态杂波和正常人车环境各 20 分钟。每条报告必须绑定独立原视频 SHA256、物理摄像头采样、正式 V4b 标签与哈希，失败和误锁不会被删除或覆盖。

记录器同步增加试验前模型文件 SHA256 硬核对，错误模型不会创建会话目录；长稳写盘改为逐条刷新、每秒强制同步并在结束时再次同步，同时保存真实经过时长。总门还会拒绝损坏 JSON、重复视频、配置 20 分钟但实际不足、旧模型和缺格，并直接给出剩余距离与长稳次数。

TDD 先使旧完整夹具因缺模型哈希与真实时长红灯，再补齐正例和错模型、实际 1199 秒、损坏报告等反例。Python 编译与完整回归为 `25/25 PASS`。当前真实目录没有任何外场报告，实际总门为 `NO-GO 3/22`、距离剩余 27、长稳剩余 2；这是诚实待采状态，不是工具故障。旧 `2026-05-25_field_test_complete_guide_v1.md` 已加停用警告，唯一权威入口仍为 `2026-06-08_real_data_collection_sop_v1.md`。

## 2026-07-12 第 2 步补漏：严格事件物理来源入哈希

审计历史回放 `15/15` 报告时确认：旧严格门可以看到当前视觉 source 是 MP4，但事件视觉证据对象没有把 source 写入自身哈希，15 项也未硬拒绝回放。因此旧报告只能靠文档声明区分“软件回放”和“真实现场”，不适合作为最终自动总门输入。

网页事件证据现增加 `source`、`physical_camera_source` 和 `capture_backend`，三项随视觉证据一起计算 SHA256。严格 15 项总数保持不变，但 `vision_evidence_valid` 现在同时要求数字物理摄像头，`detector_ready` 同时要求正式 `drone-v4b-hardneg-deployed` 标签。物理 source `0` 正例继续 `15/15`，MP4 在其他字段全绿时仍因视觉证据有效性失败；严格导出保存和回放后的视觉哈希保持一致。

## 2026-07-13 第 4 步返场前准备：最终同场收工门

`field_evidence_gate.py` 新增 `--mode mission-final`。普通无参数模式仍用于采集中途检查矩阵 `22/22`；最终模式再要求本次 `same-event` 预检、物理摄像头真实事件主快照与严格导出均 `15/15`，并强制所有 29 条有效外场报告和真实事件位于预检后的同一 8 小时窗口。完整物理同场夹具为 `GO 25/25`，回放事件、distance-only 预检和窗口外旧报告分别稳定 `NO-GO`。

当前运行中的网页 PID `26812` 启动于本次代码变更之前，尚未加载物理来源入哈希逻辑；出发前必须停止并按正式启动助手启动唯一新网页服务。真实无人机报告路径固定为 `captures/latest_real_drone_strict_closure_report.json`，最终报告固定为 `captures/latest_field_mission_final_report.json`。当前没有真实外场数据，因此不能生成最终 GO。

## 2026-07-13 第 4 步返场前安全修复：重启默认关闭舵机

新版网页加载后运行真实预检，除摄像头状态过期外意外出现 `servo_disabled` 失败。板端状态新鲜且设备运行时间只有约 3 分钟，确认开发板近期重启；固件全局 `ManualServoControl` 初值原为开启，运行时 `RESET` 也会重新执行 `setServoEnabled(true)`。经统一收件箱发送 `SERVO,OFF` 后，当前风险先消除。

第一轮根因修复把上电初值和 `RESET` 都改为关闭并加入静态守门。刷入后真实状态为 `servo_enabled=0`，但 `servo_attached=1`，进一步证明 `TrackingTask` 启动时仍直接调用两次 `.attach()` 绕过统一开关。安全守门随后新增“TrackingTask 禁止直接 attach，必须调用单一输出门”，并以 `setServoEnabled(manualServo.servo_enabled)` 替代该初始化。

最终固件构建 `SUCCESS`，RAM `15.7%`、Flash `30.1%`，编译配置 `3/3 PASS`，SHA256 为 `c5f7e0529b385d322a35578bf1febed329104829d23567820889f7f6ea7fb2e0`。ROM `--no-stub --verify` 四段刷写完成后，新桥 PID `36268`、新网页 PID `29592` 唯一运行。真实上电状态为 `servo_enabled=0 / servo_attached=0`；再通过统一收件箱执行 `RESET` 后仍为 `0/0`，轨迹和事件均为空。

当前 distance 预检为 `NO-GO 15/16`，唯一失败项 `vision_runtime_fresh`，原因是没有运行真实摄像头。舵机项已真实通过。`RESET` 同时清除了云测试状态，所以返场启动物理摄像头后仍需重新完成一次 `CLOUD,TEST 32/32`，再运行 `same-event` 预检。

## 2026-07-13 第 4 步补漏：实机传感器融合进入最终证据门

按乐鑫 2026 赛题必备项重新审计后发现：严格 `15/15` 能证明物理视觉与云端同事件，旧 `mission-final 25/25` 能证明距离、长稳和同场时间窗，但两者都没有硬性要求同一采样时刻出现真实雷达轨迹与物理视觉融合。因此旧门可能放过一份“视觉和云端完整、实机融合却未发生”的证据包，无法单靠最终报告回答官方“至少一种传感器数据融合”。

`field_trial_recorder.py` 现在逐点保存 `test_mode_enabled`、`fusion_enabled`、融合级别/阶段/置信度/原因，并只在以下条件同时成立时记录 `physical_fusion=1`：数字物理摄像头通过 V4b 自动锁定、LD2450 轨迹活动且确认、测试模式明确关闭、增强融合开启、融合级别为 MID/HIGH、融合阶段与原因有效、真实事件正在活动。摘要同时保存实机融合样本数和事件号。

`field_evidence_gate.py --mode mission-final` 新增 `real_sensor_fusion_evidence`：至少一条正式无人机距离报告必须含实机融合样本，且其事件号必须等于严格 `15/15` 的同一个事件号。最终报告升级为 `field_mission_final_v2` 和 `26/26`；没有融合、融合发生在别的事件、回放视觉或模拟轨迹都不能通过。

为了避免完成29段后才发现漏开融合，`field_collection_preflight.py` 同步升级为 V2，并在开拍前要求 `fusion_enabled=1`。距离预检由 `16/16` 变为 `17/17`，同事件预检由 `17/17` 变为 `18/18`。固件仍保留上电/RESET 默认基础兼容模式，不改主链；每次正式任务必须先通过统一收件箱发送 `FUSION,ENABLE,1`，再运行预检。

TDD 红灯先证明旧门只有25项且会放过无融合任务；生产逻辑完成后，完整物理同场夹具为 `GO 26/26`，无融合反例稳定因 `real_sensor_fusion_evidence` 失败，融合关闭预检反例稳定因 `advanced_fusion_enabled` 失败。Python 语法和完整回归均通过，回归套件总数仍为 `25/25`；套件数量不等于最终证据门数量。

当前真实运行基线为 distance `NO-GO 15/17`，失败项恰为 `vision_runtime_fresh` 和 `advanced_fusion_enabled`；矩阵仍为 `NO-GO 3/22`，最终任务门为 `NO-GO 3/26`。这是相机未启动、增强融合尚未为本次任务开启且真实报告为0时的正确防伪状态。
