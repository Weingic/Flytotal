# 2026-04-18 重复事件处理结果 V1

## 目标
验证同一目标持续存在时不会持续新建重复事件。

## 验证项
1. 单目标持续 10-20 秒：`event_id` 应保持稳定。
2. `event_store` 不应按秒刷同义 `OPEN` 记录。
3. 关闭后短时重开：标记 `event_reopen=1`，不新增杂乱事件号。

## 结果记录
| 时间 | 轨迹ID | 观察窗口(s) | event_id 变化次数 | reopen 标记 | 结论 |
|---|---|---:|---:|---:|---|
|  |  |  |  |  |  |

## 关联实现
1. `tools/node_a_serial_bridge_NodeA串口桥接.py`
   - `EVENT_STORE_DEDUP_COOLDOWN_MS`
   - `EVENT_REOPEN_MARK_WINDOW_MS`
