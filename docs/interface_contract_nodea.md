# Node A 接口契约文档

日期：`2026-04-15`
版本：`v1.0`

---

## 1. 概述

本文档定义 Node A 各软件模块之间传递的核心字段契约，用于指导：

- `vision_bridge` 输出的视觉状态字段规范
- `node_a_serial_bridge` 解析与落盘的字段规范
- `vision_web_server` HTTP API 提供给前端的字段规范
- `vision_dashboard` 网页展示层的字段来源

**不修改任何固件代码。** 本文档仅约束 Python 工具层与前端的字段契约。

---

## 2. 系统数据流

```
ESP32 (main.cpp)
  │  串口 UART 115200，文本行，逗号分隔 key=value
  ▼
node_a_serial_bridge_NodeA串口桥接.py
  │  落盘 JSON 到 captures/
  │    captures/latest_node_status.json
  │    captures/latest_node_events.json
  │    captures/latest_node_event_store.json
  │    captures/latest_active_event.json
  ▼
vision_web_server_视觉网页服务.py
  │  HTTP GET /api/*
  ▼
vision_dashboard.html（浏览器）

vision_bridge_视觉桥接.py（OpenCV 追踪进程）
  │  落盘 JSON 到 captures/
  │    captures/latest_status.json
  │    captures/capture_records.csv
  ▼
vision_web_server_视觉网页服务.py
```

---

## 3. 串口帧类型速览

| 帧前缀 | 用途 |
|---|---|
| `STATUS` | 周期性节点全量状态快照 |
| `UPLINK,HB` | 云端心跳帧，含 hunter/gimbal/rid/risk |
| `UPLINK,TRACK` | 活跃轨迹帧，含坐标与确认状态 |
| `UPLINK,EVENT` | 状态变化事件帧，立即触发 |
| `EVENT,STATUS` | 当前事件状态（event_state/event_id） |
| `LASTEVENT` | 最近一次事件快照 |
| `RISK,STATUS` | 风险分数与标志位快照 |

---

## 4. 字段契约

### 4.1 `vision_state`

| 属性 | 内容 |
|---|---|
| **类型** | `string`（枚举） |
| **正式字段名** | `vision_state` |
| **串口别名** | `vision_state`（来自 `printNormalizedStateFields()`） |
| **产生方** | `vision_bridge_视觉桥接.py`（OpenCV 追踪循环） |
| **消费方** | `vision_web_server`（`/api/status`）、`vision_dashboard`（看板展示）、`node_a_serial_bridge`（一致性校验） |
| **落盘路径** | `captures/latest_status.json` → `vision_state` |

**枚举值：**

| 值 | 含义 |
|---|---|
| `VISION_IDLE` | 视觉链未进入工作态，无目标 |
| `VISION_SEARCHING` | 目标区域已启动搜索，尚未锁定 |
| `VISION_LOCKED` | OpenCV 追踪器成功锁定目标 |
| `VISION_LOST` | 曾锁定，当前追踪器更新失败，目标丢失 |

**状态转移：**
```
无目标/复位 → VISION_IDLE
目标出现    → VISION_SEARCHING
锁定成功    → VISION_LOCKED
追踪失败    → VISION_LOST → VISION_SEARCHING（重搜索）
```

---

### 4.2 `rid_status`

| 属性 | 内容 |
|---|---|
| **类型** | `string`（枚举） |
| **正式字段名** | `rid_status` |
| **串口字段名** | `rid`（UPLINK 帧）；`rid_status`（STATUS 帧） |
| **串口别名** | `rid` → `rid_status`（alias_map） |
| **产生方** | `main.cpp`（`refreshRidRuntime()`，ESP32 固件） |
| **消费方** | `node_a_serial_bridge`（解析落盘）、`vision_web_server`（事件对象构造）、`vision_dashboard` |
| **落盘路径** | `captures/latest_node_status.json` → `rid_status`；事件对象 `event_object_v1.rid_status` |

**枚举值（当前固件 v1）：**

| 值 | 语义 | 风险方向 |
|---|---|---|
| `RID_NONE` | 未收到可用身份包 | 可疑链（配合轨迹） |
| `RID_RECEIVED` | 已收到身份包，但不在匹配窗口或条件未满足 | 观察态 |
| `RID_MATCHED` | 鉴权通过、白名单通过、在匹配窗口内 | 低风险链 |
| `RID_EXPIRED` | 之前有身份，但超时未更新 | 回可疑链 |
| `RID_INVALID` | 鉴权失败或白名单不通过 | 高风险链 |

**废弃别名（兼容旧固件输出，不在新代码中生成）：**

| 废弃值 | 映射到 |
|---|---|
| `UNKNOWN` | `RID_NONE` |
| `MISSING` | `RID_EXPIRED` |
| `SUSPICIOUS` | `RID_INVALID` |

---

### 4.3 `wl_status`

| 属性 | 内容 |
|---|---|
| **类型** | `string`（枚举） |
| **正式字段名** | `wl_status` |
| **串口字段名** | `wl_status` |
| **产生方** | `main.cpp`（`resolveWhitelistDecision()`，ESP32 固件） |
| **消费方** | `node_a_serial_bridge`（解析落盘）、`vision_web_server`（`normalize_whitelist_status()`，事件对象 `whitelist_status` 字段） |
| **落盘路径** | `captures/latest_node_status.json` → `wl_status`；事件对象 `event_object_v1.whitelist_status` |

**枚举值：**

| 值 | 含义 |
|---|---|
| `WL_UNKNOWN` | 尚未查询白名单，或无轨迹上下文 |
| `WL_ALLOWED` | 当前目标在白名单内，身份已授权 |
| `WL_DENIED` | 白名单查询明确拒绝 |
| `WL_EXPIRED` | 之前白名单通过，但已超时失效 |

**备注：** `vision_web_server` 在读取时优先取 `wl_status`，若缺失则回退到 `rid_whitelist_hit` 字段做兼容推断（`normalize_whitelist_status()`）。

---

### 4.4 `reason_flags`

本字段在实现层分为两个独立的位掩码字段，含义不同，统一在此节说明。

#### 4.4.1 `risk_reason_flags`（风险成因标志）

| 属性 | 内容 |
|---|---|
| **类型** | `int`（位掩码）；串口以管道分隔字符串形式输出 |
| **正式字段名** | `risk_reason_flags` |
| **串口字段名** | `risk_reasons`（管道分隔的标志名字符串，如 `TrackPersistent\|RidMissing`） |
| **产生方** | `main.cpp`（`SystemData.risk_reason_flags`，HunterAction 风险计算） |
| **消费方** | `node_a_serial_bridge`（解析为字符串存入事件记录）、`vision_web_server`（透传到事件对象） |
| **落盘路径** | 事件记录 `trigger_flags` 字段（含义：本次触发时的风险成因集合） |

**位掩码定义：**

| 位 | 常量名 | 含义 |
|---|---|---|
| bit 0 | `RiskReasonTrackPersistent` | 轨迹持续活跃帧数达阈值 |
| bit 1 | `RiskReasonTrackConfirmed` | 轨迹已被 TrackManager 确认 |
| bit 2 | `RiskReasonRidMatched` | 当前 RID 已匹配合法身份 |
| bit 3 | `RiskReasonRidUnknown` | 当前 RID 状态为未知/无 |
| bit 4 | `RiskReasonRidMissing` | 当前 RID 已过期或缺失 |
| bit 5 | `RiskReasonRidSuspicious` | 当前 RID 无效或可疑 |
| bit 6 | `RiskReasonProximity` | 目标距离低于接近警戒阈值 |
| bit 7 | `RiskReasonMotionAnomaly` | 检测到运动异常 |

#### 4.4.2 `trigger_flags`（触发动作标志）

| 属性 | 内容 |
|---|---|
| **类型** | `int`（位掩码）；串口以逗号/管道分隔字符串输出 |
| **正式字段名** | `trigger_flags` |
| **串口字段名** | `trigger_flags` |
| **产生方** | `main.cpp`（`computeTriggerFlags()`，`SystemData.trigger_flags`） |
| **消费方** | `node_a_serial_bridge`（解析为字符串存入事件记录）、`vision_web_server`（事件对象 `trigger_flags` 字段） |
| **落盘路径** | `captures/latest_node_status.json` → `trigger_flags`；事件对象 `event_object_v1.trigger_flags` |

**位掩码定义：**

| 位 | 常量名 | 含义 |
|---|---|---|
| bit 0 | `TriggerFlagAlert` | 本地告警已触发 |
| bit 1 | `TriggerFlagCapture` | 抓拍动作已触发 |
| bit 2 | `TriggerFlagGuardian` | 合作终端保障链路已触发 |
| bit 3 | `TriggerFlagRidMissing` | 因 RID 缺失触发响应 |
| bit 4 | `TriggerFlagRidSuspicious` | 因 RID 可疑触发响应 |
| bit 5 | `TriggerFlagEventActive` | 当前处于活跃事件状态 |
| bit 6 | `TriggerFlagVisionLocked` | 视觉已锁定目标 |
| bit 7 | `TriggerFlagCaptureReady` | 抓拍就绪（图像可用） |
| bit 8 | `TriggerFlagProximity` | 距离接近告警 |
| bit 9 | `TriggerFlagMotionAnomaly` | 运动异常告警 |

---

### 4.5 `event_state`

| 属性 | 内容 |
|---|---|
| **类型** | `string`（枚举） |
| **正式字段名** | `event_state` |
| **串口字段名** | `current_event_state`（`EVENT,STATUS` 帧）；`event_status`（`UPLINK,EVENT` 帧） |
| **串口别名** | `current_event_state` → `event_state`；`event_status` → `event_state`（bridge 回退读取） |
| **产生方** | `main.cpp`（`EventObject.event_state`，ESP32 固件） |
| **消费方** | `node_a_serial_bridge`（`build_event_record()`）、`vision_web_server`（`build_event_object_v1()`，优先读 `event_state`，回退到 `event_status`） |
| **落盘路径** | `captures/latest_node_events.json` → `event_state`；事件对象 `event_object_v1.event_state` |

**枚举值：**

| 值 | 含义 |
|---|---|
| `NONE` | 当前无活跃事件 |
| `OPEN` | 事件已建立，目标仍在跟踪中 |
| `CLOSED` | 事件已结束（目标丢失或解除） |

---

### 4.6 `capture_path`

| 属性 | 内容 |
|---|---|
| **类型** | `string`（文件路径或 `"NONE"`） |
| **正式字段名** | `capture_path` |
| **串口字段名** | `capture_path`（`LASTEVENT` / `EVENT,STATUS` 帧，可选） |
| **产生方（图像路径）** | `vision_bridge_视觉桥接.py`（`build_capture_file_path()` 生成带时间戳的 `.jpg` 路径，写入 `capture_records.csv`） |
| **产生方（串口回报）** | `main.cpp`（`LASTEVENT` 帧中携带上一次抓拍路径，可选字段） |
| **消费方** | `node_a_serial_bridge`（`build_event_record()` 优先取串口值，回退 `"NONE"`）、`vision_web_server`（`pick_capture_path()` 读事件记录） |
| **落盘路径** | 事件记录 `capture_path` 字段；事件对象 `event_object_v1.capture_path` |

**取值规则：**
- 有效路径：相对或绝对路径，如 `captures/20260415_143022_A1_ev001.jpg`
- 无图像：固定值 `"NONE"`
- `vision_bridge` 层文档标注该字段为"预留"——视觉层本身不主动写入事件路径，路径由串口桥接层从 ESP32 上报或 CSV 记录中读取。

---

### 4.7 `x_mm` / `y_mm`

| 属性 | 内容 |
|---|---|
| **类型** | `float`（单位：mm） |
| **正式字段名** | `x_mm`、`y_mm` |
| **串口字段名** | `x`、`y`（STATUS / UPLINK,TRACK / UPLINK,EVENT / LASTEVENT 帧） |
| **串口别名** | `x` / `x_mm` → `x_mm`；`y` / `y_mm` → `y_mm`（alias_map） |
| **产生方** | `main.cpp`（`RadarParser` 解析雷达串流，填入 `RadarTrack.x_mm` / `RadarTrack.y_mm`） |
| **消费方** | `node_a_serial_bridge`（`build_event_record()` lines 408-409）、`vision_web_server`（`build_event_object_v1()` 优先读 `x_mm`，回退 `x`） |
| **落盘路径** | `captures/latest_node_status.json` → `x_mm` / `y_mm`；事件对象 `event_object_v1.x` / `event_object_v1.y` |

**坐标系说明：**

| 字段 | 方向 | 含义 |
|---|---|---|
| `x_mm` | 横向（左右） | 目标相对雷达正前方的横向偏移，正值为右 |
| `y_mm` | 纵向（前后） | 目标距雷达的径向距离，正值为前方 |

**备注：** 当无活跃轨迹时，两个字段通常输出 `0.0`，但不代表目标在原点，需结合 `track_confirmed` 与 `is_active` 联合判断。

---

### 4.8 `gimbal_state`

| 属性 | 内容 |
|---|---|
| **类型** | `string`（枚举） |
| **正式字段名** | `gimbal_state` |
| **串口字段名** | `gimbal`（UPLINK 帧、LASTEVENT 帧）；`gimbal_state`（STATUS 帧 `printNormalizedStateFields()`） |
| **串口别名** | `gimbal` / `gimbal_state` → `gimbal_state`（alias_map） |
| **产生方** | `main.cpp`（`GimbalController`，ESP32 固件） |
| **消费方** | `node_a_serial_bridge`（解析落盘 `latest_node_status.json`）、`vision_web_server`（事件对象 `hunter_state` 相关字段）、`vision_dashboard` |
| **落盘路径** | `captures/latest_node_status.json` → `gimbal_state`；事件记录 `gimbal_state` |

**枚举值：**

| 值 | 含义 |
|---|---|
| `SCANNING` | 云台处于扫描待机状态，无目标或等待指向 |
| `ACQUIRING` | 正在转向目标方位，尚未完成指向锁定 |
| `TRACKING` | 已指向目标，正式跟踪状态 |
| `LOST` | 目标丢失，云台暂时停止跟踪 |

---

### 4.9 `risk_score`

| 属性 | 内容 |
|---|---|
| **类型** | `float`（≥ 0.0） |
| **正式字段名** | `risk_score` |
| **串口字段名** | `risk`（UPLINK 帧）；`risk_score`（STATUS 帧） |
| **串口别名** | `risk` / `risk_score` → `risk_score`（alias_map） |
| **产生方** | `main.cpp`（HunterAction 风险分数累计，`SystemData.risk_score`） |
| **消费方** | `node_a_serial_bridge`（`build_event_record()` line 405）、`vision_web_server`（`build_event_object_v1()` 四舍五入保留两位小数） |
| **落盘路径** | `captures/latest_node_status.json` → `risk_score`；事件对象 `event_object_v1.risk_score` |

**数值阈值（来自 `include/AppConfig.h` HunterConfig）：**

| 阈值 | 值 | 含义 |
|---|---|---|
| `SuspiciousScore` | 40.0 | 进入 `HUNTER_SUSPICIOUS` 状态 |
| `HighRiskScore` | 60.0 | 进入 `HUNTER_HIGH_RISK` 状态 |
| `EventScore` | 80.0 | 触发事件建立（`EVENT_LOCKED`） |

**备注：** `risk_score` 会随目标丢失逐渐衰减，不会立即清零，衰减速率由 `AppConfig.h` 中 `RiskDecayRate` 配置。

---

### 4.10 `track_confirmed`

| 属性 | 内容 |
|---|---|
| **类型** | `int`（布尔值，0 或 1） |
| **正式字段名** | `track_confirmed` |
| **串口字段名** | `confirmed`（UPLINK,TRACK 帧、LASTEVENT 帧）；`track_confirmed`（STATUS 帧） |
| **串口别名** | `confirmed` / `track_confirmed` → `track_confirmed`（alias_map） |
| **产生方** | `main.cpp`（`TrackManager`，累计 `TrackConfig::ConfirmFrames`（默认 5 帧）后置 1） |
| **消费方** | `node_a_serial_bridge`（normalize 后存入 `latest_node_status.json`）、`vision_web_server`（`evaluate_status_consistency()` 一致性检查） |
| **落盘路径** | `captures/latest_node_status.json` → `track_confirmed`；归一化字段中可用 |

**取值说明：**

| 值 | 含义 |
|---|---|
| `0` | 轨迹存在但尚未累计足够帧数，处于候选态 |
| `1` | 轨迹已被 TrackManager 确认，为真实目标 |

**备注：** `track_confirmed=1` 是事件上下文建立的必要条件之一（配合 `is_active=1`）。在 `track_confirmed=0` 期间不触发 `event_id` 生成。

---

## 5. 枚举值速查表

### `vision_state`
`VISION_IDLE` | `VISION_SEARCHING` | `VISION_LOCKED` | `VISION_LOST`

### `rid_status`
`RID_NONE` | `RID_RECEIVED` | `RID_MATCHED` | `RID_EXPIRED` | `RID_INVALID`
> 废弃别名：`UNKNOWN`→`RID_NONE`，`MISSING`→`RID_EXPIRED`，`SUSPICIOUS`→`RID_INVALID`

### `wl_status`
`WL_UNKNOWN` | `WL_ALLOWED` | `WL_DENIED` | `WL_EXPIRED`

### `event_state`
`NONE` | `OPEN` | `CLOSED`

### `gimbal_state`
`SCANNING` | `ACQUIRING` | `TRACKING` | `LOST`

### `risk_score` 阈值
`0.0` → `40.0`（SUSPICIOUS）→ `60.0`（HIGH_RISK）→ `80.0`（EVENT）

---

## 6. 别名映射表（alias_map）

`node_a_serial_bridge` 在解析串口字段时统一规范字段名，以下为完整别名到正式字段名的映射：

| 串口原始字段名 | 正式字段名 |
|---|---|
| `gimbal` | `gimbal_state` |
| `gimbal_state` | `gimbal_state` |
| `rid` | `rid_status` |
| `rid_status` | `rid_status` |
| `wl_status` | `wl_status` |
| `hunter` | `hunter_state` |
| `hunter_state` | `hunter_state` |
| `risk` | `risk_score` |
| `risk_score` | `risk_score` |
| `confirmed` | `track_confirmed` |
| `track_confirmed` | `track_confirmed` |
| `x` | `x_mm` |
| `x_mm` | `x_mm` |
| `y` | `y_mm` |
| `y_mm` | `y_mm` |
| `current_event_state` | `event_state` |
| `event_status` | `event_state`（bridge 回退） |

---

## 7. 落盘 JSON 文件说明

| 文件路径 | 写入方 | 读取方 | 内容 |
|---|---|---|---|
| `captures/latest_node_status.json` | `node_a_serial_bridge` | `vision_web_server` `/api/status` | 最新一帧全量节点状态 |
| `captures/latest_node_events.json` | `node_a_serial_bridge` | `vision_web_server` `/api/events` | 最近一次事件记录 |
| `captures/latest_node_event_store.json` | `node_a_serial_bridge` | `vision_web_server` `/api/event_store` | 多事件历史列表 |
| `captures/latest_active_event.json` | `node_a_serial_bridge` | `vision_web_server` | 当前活跃事件（`event_state=OPEN`） |
| `captures/latest_status.json` | `vision_bridge` | `vision_web_server` `/api/status` | 视觉层当前状态（`vision_state` 等） |
| `captures/capture_records.csv` | `vision_bridge` | `node_a_serial_bridge`（间接） | 抓拍记录，含 `file_path` |

---

## 8. HTTP API 字段来源

| API 端点 | 核心字段来源 |
|---|---|
| `GET /api/status` | `latest_node_status.json` + `latest_status.json` 合并 |
| `GET /api/events` | `latest_node_events.json` |
| `GET /api/event_store` | `latest_node_event_store.json` |

事件对象在 `vision_web_server` 的 `build_event_object_v1()` 中构造，schema_version 为 `"event_object_v1"`，包含本文档第 4 节所有字段。

---

## 9. 变更历史

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-04-15 | v1.0 | 初版，整理 vision_bridge / node_a_serial_bridge / vision_web_server / dashboard 所需核心字段契约 |
