# 2026-04-16 视觉状态定义 V1

## 1. 状态集合
1. `VISION_IDLE`：视觉链未进入工作态。
2. `VISION_SEARCHING`：正在搜索目标区域。
3. `VISION_LOCKED`：已锁定目标。
4. `VISION_LOST`：曾锁定但当前丢失。

## 2. 对外输出字段
1. `vision_state`
2. `vision_locked`
3. `capture_ready`
4. `capture_path`（预留）

## 3. 最小闭环要求
1. 目标出现 -> `SEARCHING`
2. 锁定成功 -> `LOCKED`
3. 丢失 -> `LOST`
4. 无目标/复位 -> `IDLE`

## 4. 网页显示要求
Node 看板至少显示：
- `vision_state`
- `vision_locked`
- `capture_ready`
