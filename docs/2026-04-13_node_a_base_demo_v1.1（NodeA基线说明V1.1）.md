# 2026-04-13 Node A Base Demo V1.1 说明

## 1. 冻结版本
- 版本号：`Node A Base Demo V1.1`
- 基线字段：`baseline_version=Node_A_Base_Demo_V1.1`

## 2. 本基线包含的能力
1. 单节点主链：`TrackManager -> HunterAction -> GimbalController -> CloudTask`。
2. 风险分级与事件对象：支持 `OPEN/CLOSED` 与关闭原因留痕。
3. 网页可视化联动：主链状态、事件、抓拍、RID 状态可同屏查看。
4. RID 身份链预铺：支持 `RID,MSG` / `RID,STATUS` / `rid_whitelist_hit` / `rid_last_update_ms`。

## 3. 本基线不包含的能力
1. 双节点协同完整闭环。
2. Guardian 完整自动闭环。
3. 自动检测驱动起锁（当前仍保留手动起锁兜底）。

## 4. 基线复测场景（4.13 固定）

### 场景 A：正常目标进入 -> 跟踪 -> 离开
执行建议：
1. 注入连续轨迹（或真实目标进入），并发送合法身份：
```text
RID,MSG,SIM-RID-001,UAV,RID_SIM,1712880000000,VALID,WL_OK,-48
```
2. 观察 `BRIEF` / `RISK,STATUS` / `EVENT,STATUS`：
   - `track_active=1`
   - `track_confirmed=1`
   - `rid_status=MATCHED`
   - 风险维持低位或可回落
3. 目标离开后观察：
   - `track_active=0`
   - 若事件已开则应可见 `TRACK_LOST` 或 `RISK_DOWNGRADE` 关闭语义。

### 场景 B：高风险目标进入 -> 告警 -> 事件生成 -> 网页显示
执行建议：
1. 注入连续轨迹，同时发送异常身份：
```text
RID,MSG,SIM-RID-999,UAV,RID_SIM,1712880000000,INVALID,DENY,-45
```
2. 观察 `RISK,STATUS`：
   - `rid_status=INVALID`
   - 风险进入 `SUSPICIOUS/HIGH_RISK`
3. 观察 `EVENT,STATUS`：
   - `event_active=1`
   - `current_event_state=OPEN`
4. 网页检查：
   - `RID` 状态显示为 `INVALID`
   - `RID 白名单` 显示 `MISS`
   - `RID 最近更新` 有刷新值

## 5. 复测固定命令
```powershell
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200
python tools/vision_bridge_视觉桥接.py --backend dshow --source 1 --tracker csrt --tracker-fallback auto --source-warmup-frames 20
python tools/vision_web_server_视觉网页服务.py --host 127.0.0.1 --port 8765
```

## 6. 结论
`Node A Base Demo V1.1` 可以作为 4.14 身份链接入的稳定出发版本。
