# 2026-04-22 双节点事件导出样例 V1

## 目标
- 固定一份“双节点接力事件导出样例”，用于 5.1 前讲解、对照和答辩。
- 这份样例是“讲解模板”，不是声称当前已经拿到全部真实场地证据。

## 推荐样例结构
```json
{
  "event_id": "DUAL-DEMO-001",
  "node_id": "A2",
  "source_node": "A2",
  "prev_node_id": "A1",
  "handoff_from": "A1",
  "handoff_to": "A2",
  "continuity_hint": "HANDOFF_PENDING",
  "risk_level": "SUSPICIOUS",
  "rid_status": "NONE",
  "reason_flags": [
    "RID_MISSING",
    "TRACK_CONFIRMED"
  ],
  "event_status": "OPEN",
  "capture_path": "captures/event_exports/DUAL-DEMO-001_capture.jpg",
  "evidence_hash": "PLACEHOLDER_HASH",
  "timeline": [
    {
      "step": "open",
      "node_id": "A1",
      "summary": "A1 first opened the event."
    },
    {
      "step": "handoff",
      "node_id": "A1",
      "summary": "A1 handed off target ownership to A2."
    },
    {
      "step": "continue",
      "node_id": "A2",
      "summary": "A2 continued tracking and evidence presentation."
    }
  ]
}
```

## 这份样例要讲什么
### 1. 当前节点是谁
- `node_id=A2`
- 表示当前事件记录归 A2 展示和继续处理。

### 2. 上一个节点是谁
- `prev_node_id=A1`
- 表示这不是凭空在 A2 新开的一条独立事件。

### 3. 接力方向是什么
- `handoff_from=A1`
- `handoff_to=A2`
- 说明真实业务语义是 `A1 -> A2`。

### 4. 当前连续性处于什么状态
- `continuity_hint=HANDOFF_PENDING`
- 表示系统认为当前记录属于双节点连续性过程，不是普通单节点样例。

## 导出讲解模板
- “当前事件展示在 A2 上，但它不是 A2 独立生成的一条全新记录。这里能看到上一节点是 A1，handoff 方向也是 A1 到 A2，因此这是一条可解释的双节点连续事件。”

## 5.1 现场替换规则
- 若拿到真实导出文件：
  - 用真实 `event_id`
  - 用真实 `capture_path`
  - 用真实 `evidence_hash`
  - 保留本说明的讲解顺序不变
- 若真实链路部分波动：
  - 仍按本样例说明字段意义
  - 不宣称已完成复杂自动拼接算法
