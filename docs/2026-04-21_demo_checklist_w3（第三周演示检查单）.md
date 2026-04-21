# 2026-04-21 第三周演示检查单

## 演示前 5 分钟
- 确认串口桥接正在运行，`latest_node_status.json` 有刷新时间。
- 确认视觉桥接正在运行，`latest_status.json` 有刷新时间。
- 打开 dashboard，确认页面不是 mock 模式。
- 检查 `测试结果历史`、`联调时间线`、`事件详情` 均能打开。

## 演示主流程
1. 讲首页摘要区
   - 当前是否 `deliverable_ready`
   - 套件 / 合同 / 证据链是否为 PASS
   - 误报率、E2E、证据闭环三个指标是否可读
2. 讲 Node A 最近事件
   - 选择一条事件
   - 打开事件详情
   - 解释 `reason_flags / risk_score / vision_state / RID`
3. 讲证据导出
   - 点击导出当前事件证据 JSON
   - 展示最新导出记录
4. 讲联调时间线
   - 展示 `open -> capture -> hold/close`
   - 指出结果记录与时间线相互对应

## 演示必讲字段
- `event_id`
- `node_id`
- `risk_score`
- `vision_state`
- `rid_status`
- `reason_flags`
- `capture_path`
- `evidence_hash`
- `ts_open`
- `ts_close`
- `close_reason`

## 演示边界
- 当前版本主打单节点成熟度与 node-aware 预留，不宣称已完成真实双节点拼接算法。
- 若截图未补齐，可先展示实时页面和结果文件路径。
