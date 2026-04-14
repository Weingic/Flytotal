# 2026-04-17 事件去重规则 V1

## 目标
防止同一目标持续存在时重复刷出大量同义事件。

## 规则（冻结）
1. `event_active=1` 时不重复新建不同 `event_id`。
2. 相同语义键在冷却窗口内不重复入仓。
3. 同一 `event_id` 先 `CLOSED` 后短时 `OPEN` 记为 reopen，不新建新对象。

## 语义键定义
`source_type + event_id + event_status + event_level + reason + track_id`

## 参数
1. `EVENT_STORE_DEDUP_COOLDOWN_MS = 1500`
2. `EVENT_REOPEN_MARK_WINDOW_MS = 10000`

## 当前实现落点
1. `tools/node_a_serial_bridge_NodeA串口桥接.py`
   - `append_event_store_record()` 增加冷却与 reopen 标记。
   - 记录新增：`event_cooldown_ms`、`event_reopen`、`event_reopen_gap_ms`。

## 验收要点
1. 同一目标 10 秒停留不应产生高频重复语义事件。
2. 关闭后短时重开应标记 `event_reopen=1`。
