# 2026-07-08 NodeA 功能更新

## 计划位置

2026-07-08 / 云端 LLM 闭环联调 / 比赛证据固化

今天的核心目标是把乐鑫命题里要求的“设备侧感知数据 -> 云端大模型研判 -> 云端指令下发 -> 边缘侧执行或安全记录”真正跑通，并留下可以给比赛材料引用的实测证据。

## 本轮完成内容

### 1. 云端 API 与 WiFi 条件确认

已经确认 Ark API Key、模型和火山方接口在电脑端可用；API Key 只保存在本地 `include/secrets.h`，该文件已被 `.gitignore` 忽略，不进入仓库。

iPhone 热点开启“最大兼容性”后，热点切到 2.4 GHz / WPA2，NodeA 能够进入：

```text
wifi=CONNECTED
```

这说明本轮问题已经不是热点不可见，而是 ESP32 联网后的 HTTPS 连接问题。

### 2. HTTPS 失败根因定位

串口中原始云端失败表现为：

```text
error=http_request_failed
esp_error=28674
```

查 ESP HTTP 客户端定义后确认：

```text
28674 = 0x7002 = ESP_ERR_HTTP_CONNECT
```

含义是 HTTP/HTTPS 连接打开失败。继续排查后发现，原代码在 `CloudClient` 中使用了 `esp_crt_bundle_attach`，但当前 Arduino + PlatformIO 环境下并没有把证书 bundle 数据嵌入并初始化进去。结果就是“配置了证书 bundle 函数，但 ESP32 端实际没有可用根证书表”，HTTPS 握手容易在连接阶段失败。

同时，电脑端解析 Ark 域名曾出现 `198.18.x.x`，这是本机隧道网卡路径；因此电脑 `curl` 能通不能直接证明 ESP32 也能通。后续用 HTTPS DNS 和真实公网 IP 验证后，Ark 当前证书链为：

```text
Leaf: ark.cn-beijing.volces.com
Issuer: RapidSSL TLS RSA CA G1
Root: DigiCert Global Root G2
```

### 3. 修复方式

本轮没有关闭证书校验，也没有使用不安全 HTTPS。

实际修复是：在 `lib/CloudClient/CloudClient.cpp` 中内置 Ark 当前证书链对应的根证书 `DigiCert Global Root G2`，并让 `esp_http_client` 使用：

```cpp
config.cert_pem = kArkRootCaPem;
config.cert_len = sizeof(kArkRootCaPem);
```

这样 ESP32 仍然会验证服务器证书，只是不再依赖未初始化的 Arduino 证书 bundle。

同步更新了 `tools/firmware_safety_checks.py`，让本地安全检查从“必须看到 `esp_crt_bundle_attach`”改为检查明确的根证书 PEM 配置。

### 4. 云端闭环实测结果

固件上传到 COM4 后，串口发送：

```text
QUIET,ON
CLOUD,ENABLE,1
CLOUD,TEST
CLOUD,STATUS
```

关键实测输出：

```text
CLOUD,QUEUED,source=TEST
CLOUD,CMD,TRIGGER_PARACHUTE,effect=PARACHUTE_INTENT_LOGGED,status=NOT_INTEGRATED
CLOUD,STATUS,enabled=1,configured=1,wifi=CONNECTED,request_in_flight=0,dropped_total=0,cloud_online=1,threat_level=HIGH,alert_text=高风险无人机入侵,action=触发降落伞处置非合作高风险无人机,command_type=TRIGGER_PARACHUTE,runtime_event_threshold=0.0,effective_event_threshold=76.0,cloud_command_applied=1,cloud_command_effect=PARACHUTE_INTENT_LOGGED,cloud_command_source_event_id=A1-CLOUD-TEST,cloud_command_reason=NONE,cloud_command_applied_ms=27911,last_update_ms=27911,error=NONE
```

这条证据说明：

1. NodeA 已经把测试事件送入云端队列。
2. 云端大模型返回了高风险判断。
3. 云端下发了 `TRIGGER_PARACHUTE` 类型处置建议。
4. 边缘端没有假装已经接入降落伞硬件，而是诚实记录为 `PARACHUTE_INTENT_LOGGED` 和 `NOT_INTEGRATED`。
5. 最终云端状态为 `cloud_online=1`，错误为 `error=NONE`。

### 5. 真实事件触发云端闭环实测结果

在 `CLOUD,TEST` 跑通后，又继续验证了“真实风险事件触发云端请求”，不再只依赖测试事件。

本轮串口输入的核心组合是：

```text
RESET
REALINPUT,OFF
TESTMODE,OFF
FUSION,ENABLE,1
CLOUD,ENABLE,1
LD2451,range_m=20.0,speed_mps=2.0,approach=1,valid=1
RID,MISSING
VISION,CONF,confidence=0.82,stability=0.91,state=TRACKING
TRACK,320,1000
```

这组输入模拟的是：有持续靠近目标、无合法 RID 身份、近距离雷达确认、视觉侧处于跟踪状态。它符合当前风险链的真实事件触发逻辑。

关键实测输出：

```text
RISK,STATUS,...main_state=EVENT,current_risk_state=EVENT_LOCKED,risk_score=84.0,risk_level=EVENT,...event_active=1,event_id=A1-0000456030-0001
CLOUD,STATUS,enabled=1,configured=1,wifi=CONNECTED,request_in_flight=1,...
CLOUD,CMD,GENERATE_ALERT,effect=ALERT_GENERATED
CLOUD,STATUS,enabled=1,configured=1,wifi=CONNECTED,request_in_flight=0,dropped_total=0,cloud_online=1,threat_level=HIGH,alert_text=发现非合作无人机！,action=加强监测，准备采取反制措施,command_type=GENERATE_ALERT,...cloud_command_applied=1,cloud_command_effect=ALERT_GENERATED,cloud_command_source_event_id=A1-0000456030-0001,...error=NONE
SUMMARY,...risk_high_risk=1,risk_event=1,event_opened=1,event_closed=1,max_risk=84.0,last_event_id=A1-0000456030-0001
```

这条证据比 `CLOUD,TEST` 更关键，因为它证明云端请求来源已经从手动测试事件推进到真实风险链路：

1. `HunterAction` 根据持续轨迹、RID 缺失、近距离等因素把风险推到 `84.0`。
2. 事件对象真实打开，事件号为 `A1-0000456030-0001`。
3. NodeA 在事件打开后把结构化感知摘要送入云端 LLM 研判。
4. 云端返回 `GENERATE_ALERT`，边缘侧记录为 `ALERT_GENERATED`。
5. `cloud_command_source_event_id=A1-0000456030-0001`，说明云端命令绑定的是这次真实事件，不是 `A1-CLOUD-TEST`。

同时也记录一个诚实边界：本轮事件后来因为模拟轨迹停止刷新而以 `TRACK_LOST` 关闭，这属于当前测试脚本没有持续喂轨迹导致的自然关闭，不影响“事件打开 -> 云端请求 -> 云端命令回写”的闭环结论。

### 6. 网页事件详情与导出证据接入云端字段

为了让比赛材料更容易看懂，已把云端 LLM 研判字段接入网页侧事件详情和事件证据导出：

1. 后端 `event_object_v1` 新增 `cloud_online`、`cloud_threat_level`、`cloud_alert_text`、`cloud_action`、`cloud_command_type`、`cloud_command_effect`、`cloud_command_source_event_id` 等字段。
2. 事件详情接口会读取当前 `latest_node_status.json`，只有当 `cloud_command_source_event_id` 与当前事件号一致时，才把云端命令合并到该事件对象里，避免把上一条云端结果错挂到别的事件上。
3. Dashboard 的“事件详情（最小回放）”新增云端在线、云端威胁、云端命令、边缘执行、云端来源事件、云端建议六个证据栏。
4. “导出当前事件证据 JSON”会自动带上这些云端字段，评委可以直接从导出包看到“真实事件 -> 云端研判 -> 下行命令 -> 边缘记录”。

### 7. 国一材料优先引用的两条证据

后续答辩材料建议把两条证据组合使用，分别证明“云端处置能力”和“图像绑定的完整证据链”：

1. 云端告警执行证据：`captures/event_exports/event_evidence_A1-0000307059-0003_1783518461715.json`。事件号 `A1-0000307059-0003`，风险分 `84.0`，`cloud_online=1`，云端返回 `GENERATE_ALERT`，边端记录 `ALERT_GENERATED`，`cloud_command_source_event_id=A1-0000307059-0003`。证据哈希为 `105044217ebc9673f664d513d2ab3804d400292b0a3b7f7c4be86420269b6ef1`。诚实边界：该包 `capture_count=0`，主要用于证明云端告警和边端执行闭环。
2. 图像绑定完整导出证据：`captures/event_exports/event_evidence_A1-0000003139-0001_1783521642679.json`。事件号 `A1-0000003139-0001`，风险分 `84.0`，`capture_count=1`，`capture_binding_mode=event_id_exact`，抓拍文件为 `captures/2026-07-08_22-40-31_616ms_f631616_cap001_cloud_threshold_bind_A1-0000003139-0001.jpg`。云端返回 `ADJUST_THRESHOLD`，边端执行为 `EVENT_THRESHOLD_70`，`cloud_command_source_event_id=A1-0000003139-0001`。证据哈希为 `227e1b5a9fbe4907f45c4fb4cec0ca47eac82d5708ae627afe196cf824ce8da6`。

## 验收命令与结果

固件编译：

```powershell
pio run
```

结果：

```text
SUCCESS
```

固件上传：

```powershell
pio run -t upload --upload-port COM4
```

结果：

```text
SUCCESS
Hard resetting via RTS pin
```

安全检查：

```powershell
python tools\firmware_safety_checks.py
```

结果：

```text
critical_sections: enter=102 exit=102
firmware_safety_checks: PASS
```

## 比赛表达口径

可以这样说：

```text
NodeA 是 ESP32-S3 边缘感知节点，负责毫米波雷达、身份链、视觉确认状态和风险上下文的本地融合。事件触发后，NodeA 将结构化感知摘要上传到火山方 Ark 大模型接口，由云端给出处置建议；边缘端再对云端指令进行安全执行或安全记录。今天的实测中，系统先完成了 CLOUD,TEST 测试事件闭环，又完成了真实风险事件 A1-0000456030-0001 的云端研判闭环：风险链将目标推到 EVENT，云端返回 HIGH 判断和 GENERATE_ALERT 指令，NodeA 侧完成 ALERT_GENERATED 安全记录。
```

必须诚实说明：

```text
TRIGGER_PARACHUTE 目前是处置意图记录，不代表已经接入真实降落伞执行机构。系统保留 NOT_INTEGRATED 标记，避免把未接硬件的能力包装成已完成能力。
```

这对乐鑫命题是有价值的，因为它证明项目不是只做本地串口演示，而是形成了“边缘设备 + 云端 LLM + 下行指令 + 边缘安全策略”的端云闭环。

## 后续建议

下一步优先补三类证据：

1. 录一段完整视频：从真实目标进入、事件打开、云端返回命令，到 `cloud_online=1`。
2. 截图保存 Dashboard 或串口终端中的真实事件 `CLOUD,STATUS`，重点保留 `cloud_command_source_event_id=A1-0000456030-0001`。
3. 下一轮重点录制一段网页侧视频：事件详情页能同时看到风险分、事件号、云端命令和边缘执行结果。
