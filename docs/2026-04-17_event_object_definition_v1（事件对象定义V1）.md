# 2026-04-17 事件对象定义 V1

## 目标
统一事件对象字段，保证“事件判断 -> 抓拍 -> 网页 -> 导出证据”使用同一对象。

## 标准字段（冻结）
| 字段 | 类型 | 说明 |
|---|---|---|
| `event_id` | string | 事件唯一编号 |
| `node_id` | string | 节点编号（如 `A1`） |
| `track_id` | int | 轨迹编号 |
| `risk_score` | float | 风险分值 |
| `risk_level` | string | 风险等级（`NONE/NORMAL/HIGH_RISK/EVENT`） |
| `hunter_state` | string | Hunter 子状态 |
| `rid_status` | string | 身份状态 |
| `whitelist_status` | string | 白名单状态（`WL_*`） |
| `vision_state` | string | 视觉状态（`VISION_*`） |
| `trigger_flags` | string | 触发标志集合 |
| `start_time` | int(ms) | 事件开始时间 |
| `update_time` | int(ms) | 最近更新时间 |
| `x` | float | 目标 x 坐标（mm） |
| `y` | float | 目标 y 坐标（mm） |
| `capture_path` | string | 抓拍图路径，未命中为 `NONE` |
| `event_state` | string | 事件状态（`OPEN/CLOSED/NONE`） |

## 当前实现落点
1. `tools/vision_web_server_视觉网页服务.py`
   - `build_event_object_v1()` 输出上述冻结字段。
   - `build_node_event_detail_payload()` 新增 `event_object_v1`。
2. `tools/node_a_serial_bridge_NodeA串口桥接.py`
   - 事件记录新增 `event_state/whitelist_status/capture_path/start_time_ms/update_time_ms/trigger_flags` 等字段。
