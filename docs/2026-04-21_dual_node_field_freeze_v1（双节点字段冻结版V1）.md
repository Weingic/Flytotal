# 2026-04-21 双节点字段冻结版 V1

## 冻结目标
- 先冻结 Day1 双节点基线字段，后续联调不再随意改名字。

## 字段定义
- `node_id`
  - 当前事件或状态所属节点。
- `source_node`
  - 当前记录的来源节点。
- `prev_node_id`
  - 若发生节点连续性切换，记录上一个节点。
- `handoff_from`
  - handoff 发起节点。
- `handoff_to`
  - handoff 目标节点。
- `continuity_hint`
  - 当前连续性提示，例如：
    - `SINGLE_NODE`
    - `HANDOFF_PENDING`
    - `HANDOFF_OUTBOUND`

## 页面最低展示要求
- 双节点卡片至少显示：
  - 在线状态
  - 最后上报时间
  - tracks 数
  - events 数
  - `node_id / source_node`
  - `continuity_hint`

## 当前口径
- 单节点场景默认：
  - `prev_node_id=NONE`
  - `handoff_from=NONE`
  - `handoff_to=NONE`
  - `continuity_hint=SINGLE_NODE`

## 后续扩展原则
- 新增字段只能加，不随意改已有字段名。
- 页面、日志、事件对象三处字段含义必须保持一致。
