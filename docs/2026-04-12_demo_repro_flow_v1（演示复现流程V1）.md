# 2026-04-12 演示复现流程 V1（严格固化版）

## 1. 目的与边界
今天只做一件事：**固化可复现流程**。  
不加新功能，不重构，不边测边改。

固定流程目标：

`上电 -> 自检 -> 心跳正常 -> 空场扫描 -> 目标进入 -> 轨迹建立 -> 风险变化 -> 云台转向 -> 视觉锁定/抓拍 -> 事件创建 -> 事件上云/展示 -> 目标离开 -> 状态恢复`

---

## 2. 开测前规则（必须执行）
1. 本轮测试开始后，不改任何代码和参数。  
2. 若中途失败，只记录现象与日志，不现场修代码。  
3. 本轮只允许“重启流程重测”，不允许“边测边改”。  
4. 全流程留痕：硬件画面 + 终端日志 + 网页大屏同屏或分段可对齐。

---

## 3. 固定终端启动顺序
工作目录：

```powershell
cd C:\Users\WZwai\Documents\PlatformIO\Projects\Flytotal
```

### 终端 1：Node A 串口桥接
```powershell
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200

```

### 终端 2：视觉桥接
```powershell
python tools/vision_bridge_视觉桥接.py --backend auto --source 0 --tracker csrt --tracker-fallback auto --source-warmup-frames 12
```
python tools/vision_bridge_视觉桥接.py --backend auto --source 1 --tracker csrt --tracker-fallback auto --source-warmup-frames 12




### 终端 3：网页服务
```powershell
python tools/vision_web_server_视觉网页服务.py
```

### 终端 4：自动验收（先快检后全检）
```powershell
python tools/acceptance_auto_411_快检全检自动验收.py --port COM4 --suite risk_event_vision_chain_v1 --base-url http://127.0.0.1:8765
```

网页地址：

`http://127.0.0.1:8765`

---

## 4. 全流程演示检查点（按时间顺序口播/记录）
1. 上电与自检：Node A 上电，串口桥接出现状态输出。  
2. 心跳正常：网页与接口 `api/health` 可读。  
3. 空场扫描：`main/hunter/gimbal/vision` 处于空场扫描口径。  
4. 目标进入：注入目标后出现 `track_active=1`。  
5. 轨迹建立：出现 `track_confirmed=1`。  
6. 风险变化：`risk_score/risk_level` 按场景变化。  
7. 云台转向：云台进入获取/跟踪状态。  
8. 视觉锁定/抓拍：视觉锁定或 `capture_ready`，并产生抓拍记录。  
9. 事件创建：出现 `event_id != NONE`，事件列表可见。  
10. 事件展示/导出：网页可查看事件详情，证据 JSON 可导出。  
11. 目标离开：执行丢轨后事件关闭。  
12. 状态恢复：系统回到空场或稳定状态。

---

## 5. 视频录制要求（一次完整）
必须覆盖三部分：

1. 硬件现场（Node A + 云台 + 摄像头画面）。  
2. 终端日志（至少显示自动验收结果与关键步骤）。  
3. 网页大屏（状态区、事件列表、事件详情/抓拍区）。

建议录制顺序：

1. 先拍硬件上电与空场。  
2. 切到终端展示自动验收启动。  
3. 切到网页展示事件变化与回放区域。  
4. 回到终端展示最终 PASS。  

---

## 6. 固定产物清单（本轮结束必须存在）
1. `captures/latest_411_acceptance_auto_report.json`  
2. `captures/latest_411_acceptance_quick_report.json`  
3. `captures/latest_411_acceptance_full_report.json`  
4. `captures/latest_411_acceptance_flow_report.json`  
5. `captures/latest_single_node_evidence_closure_report.json`  
6. `captures/latest_uplink_contract_report.json`  
7. 一条完整视频（硬件 + 终端 + 网页）

---

## 7. 当天收尾判定
判定为“4.12 固化完成”的条件：

1. 自动验收 `result=PASS`。  
2. 全量验收 `closure_result=PASS`。  
3. 视频三部分均可对齐到同一轮流程。  
4. 冻结清单和周报已填写。

按“从零重启、真机测试”的最稳顺序来。你现在照这个做就行。

**总原则**
1. 先接好硬件，再上电。
2. 先烧录，再开终端。
3. 先主链，再视觉，再网页，最后验收。
4. 同一时间，一个串口只能被一个程序占用。

**一、硬件顺序**
1. 接好 Node A 主板到电脑，确认是 `COM4`。
2. 接好雷达到 Node A。
3. 接好舵机到 Node A。
4. 如果舵机需要独立 `5V` 供电，先接好供电。
5. 确认舵机电源地 `GND` 和 Node A 的 `GND` 共地。
6. 接上 USB 摄像头到电脑。
7. 摆好目标物，让摄像头能看到。

**二、软件前清场**
你刚才已经让我结束过相关进程了，现在默认是干净状态。  
如果你怀疑还有残留，可以再执行一次：

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*Flytotal*' -or $_.CommandLine -like '*node_a_serial_bridge*' -or $_.CommandLine -like '*vision_bridge*' -or $_.CommandLine -like '*vision_web_server*' -or $_.CommandLine -like '*acceptance_*') } | Select-Object ProcessId,CommandLine
```

如果没有输出，就说明没有残留。

**三、如果要烧录固件**
先烧录，再开下面所有终端。  
不要先开桥接再烧录。

**四、正式启动顺序**
开 4 个终端，按这个顺序。



清场：Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*vision_web_server*' -or $_.CommandLine -like '*vision_bridge*' -or $_.CommandLine -like '*node_a_serial_bridge*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

查端口：netstat -ano | findstr :8765


1. 终端1：Node A 串口桥接
```powershell
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200
```

2. 终端2：视觉桥接  
如果 USB 摄像头是 `source 1`，用这个：
```powershell
python tools/vision_bridge_视觉桥接.py --backend auto --source 1 --tracker csrt --tracker-fallback auto --source-warmup-frames 12
```
如果 USB 摄像头是 `source 0`，就把 `1` 改成 `0`。

3. 终端3：网页服务
```powershell
python tools/vision_web_server_视觉网页服务.py
```

4. 终端4：自动验收
```powershell
python tools/acceptance_auto_411_快检全检自动验收.py --port COM4 --suite risk_event_vision_chain_v1 --base-url http://127.0.0.1:8765
```

**五、网页打开**
浏览器打开：

```text
http://127.0.0.1:8765
```

**六、测试动作顺序**
按 4.12 固化日流程，不边测边改。

1. 上电，看 Node A 自检、心跳是否正常。
2. 看网页是否出现在线状态。
3. 看视觉窗口是否有实时画面。
4. 让目标物进入画面。
5. 在视觉窗口按 `s`，框住目标物。
6. 锁定后观察：
- 视觉状态变化
- 是否自动抓拍
- 网页事件列表是否出现事件
- 事件详情里是否出现抓拍证据
7. 目标离开后，看状态是否恢复。

**七、你要重点观察的几个点**
1. 串口桥接终端有没有持续输出，且不报错。
2. 视觉窗口有没有正常画面。
3. 网页里 Node A 是否在线。
4. 事件列表里是否出现新事件。
5. 抓拍图或抓拍路径是否挂到事件上。
6. 自动验收最后是否：
- `result=PASS`
- `quick_result=PASS`
- `full_result=PASS`

**八、如果要单独测舵机**
这个和正式联调分开做，避免抢串口。

1. 先停掉终端1 的桥接，在桥接窗口按：
```text
Ctrl + C
```

2. 然后进串口交互：
```powershell
python -m serial.tools.miniterm COM4 115200
```

3. 输入这些命令：
```text
SERVO,ON
DIAG,SERVO
```

4. 测完退出 `miniterm`，再重新启动终端1桥接。

**九、全部停止的顺序**
结束时建议这样停：
1. 先停自动验收终端
2. 再停网页服务终端
3. 再停视觉桥接终端
4. 最后停串口桥接终端

每个终端都按：
```text
Ctrl + C
```

**十、如果某一步失败，先看这个**
1. `COM4 拒绝访问`
说明串口被别的程序占了。
2. 网页打不开
说明网页服务没起来，先看终端3。
3. 没有事件
说明桥接没写入、目标没真正进入链路，或视觉没锁定。
4. 没有抓拍
说明还没锁定成功，或者当前事件没挂上抓拍。
5. 舵机不动
先分清是“联调里没触发”，还是“`DIAG,SERVO` 也不动”。

**给小白的解释**
你现在可以把这套流程想成 4 个岗位同时上班：

1. 串口桥接：负责把 Node A 的话翻译成电脑能看的状态。
2. 视觉桥接：负责看摄像头、选目标、抓拍。
3. 网页服务：负责把状态和事件展示出来。
4. 自动验收：负责最后给整套流程打分。

顺序不能乱，因为前一个岗位没上班，后一个岗位就拿不到数据。  
如果你愿意，我下一条可以直接给你一份“照着念就能操作”的超简版清单，只保留最少步骤。