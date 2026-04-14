# 2026-04-17 抓拍触发规则 V1

## 目标
抓拍只在关键时点触发，避免无意义高频抓图。

## 触发策略（冻结）
1. `HIGH_RISK` 首次进入时触发：`AUTO_HIGH_RISK_ENTER`。
2. 事件从非活动变为活动时触发：`AUTO_EVENT_OPENED`。
3. 事件关闭时可补抓：`AUTO_EVENT_CLOSED`。
4. 视觉新锁定仍保留基础抓拍：`AUTO_LOCK`。
5. 手动抓拍：`MANUAL`。

## 抑制策略
1. 统一冷却：`capture_cooldown`（默认 2.5s）。
2. 队列窗口：`policy_capture_pending_window_s`（默认 8s），超时丢弃。
3. 同一 `capture_reason + event_id` 队列去重，避免重复入队。

## 当前实现落点
1. `tools/vision_bridge_视觉桥接.py`
   - 新增策略开关：
     - `--policy-capture-enable`
     - `--policy-capture-high-risk-enter`
     - `--policy-capture-event-open`
     - `--policy-capture-event-close`
     - `--policy-capture-pending-window-s`
   - 新增会话日志事件：`capture_policy_queued`。

## 建议实机验证
1. 先触发 `HIGH_RISK` 并保持目标锁定，确认产生 `AUTO_HIGH_RISK_ENTER`。
2. 再触发事件打开/关闭，确认策略抓拍按规则出现。
3. 检查 `captures/capture_records.csv` 的 `capture_reason` 分布。
