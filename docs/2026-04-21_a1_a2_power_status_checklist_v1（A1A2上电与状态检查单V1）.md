# 2026-04-21 A1/A2 上电与状态检查单 V1

## 上电前
- 确认 A1、A2 两套硬件都能独立启动。
- 确认串口号已识别，例如 `COM4 / COM5`。
- 确认两套桥接输出文件不冲突。

## A1 单跑检查
1. 固件启动正常。
2. `latest_node_status.json` 有刷新。
3. dashboard 的双节点区里 A1 显示在线。
4. A1 的 `tracks / events` 能变化。

## A2 单跑检查
1. 固件启动正常。
2. `latest_node_status_A2.json` 有刷新。
3. dashboard 的双节点区里 A2 显示在线。
4. A2 的 `tracks / events` 能变化。

## A1 + A2 同时在线检查
1. dashboard 不报错。
2. A1 / A2 两张卡片都出现。
3. 两张卡片的 `最后上报时间` 都变化。
4. 两张卡片的 `node_id / source_node` 不串。
5. 两张卡片的 `tracks / events` 能独立显示。

## 最低通过标准
- A1 单跑通过
- A2 单跑通过
- 两节点同时在线时 dashboard 不报错
