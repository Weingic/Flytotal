# 2026-04-21 第三周现场恢复检查单

## 页面空白 / 数据不刷新
- 检查 web server 是否仍在运行。
- 检查 dashboard 是否误切到 mock 模式。
- 检查 `captures/latest_status.json` 与 `captures/latest_node_status.json` 更新时间。

## 串口链路异常
- 重新确认串口号。
- 重启 `node_a_serial_bridge`。
- 发送 `STATUS`、`EVENT,STATUS`、`CONFIG,STATUS` 检查主链是否仍响应。

## 视觉链异常
- 确认 vision bridge 正在写入 `latest_status.json`。
- 若无图片，先确认 `capture_records.csv` 是否仍有新记录。
- 若无抓拍但事件存在，允许用 `capture_evidence_state=MISSING_TOLERATED` 解释当前状态。

## 事件详情缺字段
- 先检查 `latest_node_event_store.json` 是否存在对应 `event_id`。
- 再检查 `event_exports/` 是否已有导出 JSON。
- 若 `ts_close` 缺失，说明事件仍可能处于 OPEN。

## 冷却 / 重开行为异常
- 发送 `EVENT,STATUS` 查看：
  - `event_cooldown_until_ms`
  - `event_close_pending`
  - `capture_evidence_state`
- 必要时发送 `LASTEVENT` 与 `SUMMARY` 辅助判断。
