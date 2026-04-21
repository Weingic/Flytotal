# 2026-04-21 双节点联调参数表 V1

## 目标
- 先建立 A1 / A2 的真实双节点基线。
- 不追求复杂接力算法，先固定最低契约与页面显示结构。

## 最低契约字段
- `node_id`
- `source_node`
- `prev_node_id`
- `handoff_from`
- `handoff_to`
- `continuity_hint`

## 当前节点配置
- A1
  - `node_id=A1`
  - `node_zone=ZONE_NORTH`
  - 默认状态文件：`captures/latest_node_status.json`
  - 默认事件文件：`captures/latest_node_events.json`
- A2
  - `node_id=A2`
  - 推荐 `node_zone=ZONE_SOUTH`
  - 默认状态文件：`captures/latest_node_status_A2.json`
  - 默认事件文件：`captures/latest_node_events_A2.json`

## 双桥接推荐启动方式
- A1
  - `python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --output-file captures/latest_node_status.json --events-file captures/latest_node_events.json`
- A2
  - `python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM5 --output-file captures/latest_node_status_A2.json --events-file captures/latest_node_events_A2.json`

## 页面验收观察点
- A1 / A2 在线状态
- 最后上报时间
- 当前 `tracks / events`
- `node_id / source_node`
- `prev_node_id / handoff_from / handoff_to / continuity_hint`

## 说明
- 当前 `NodeConfig::NodeId` 在 [include/AppConfig.h](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/include/AppConfig.h:10) 默认是 `A1`。
- A2 真机联调时，需要 A2 固件或构建配置明确输出 `A2`。
