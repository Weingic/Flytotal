# 2026-04-21 第三周冻结清单

## 当前定位
- 分支：当前工作分支冻结，不额外做 Day6 merge。
- 目标：形成一版可演示、可验收、可汇报的 Week 3 交付态。

## 已冻结能力
- 配置化主链
- 统一 `reason_flags` / 事件对象口径
- 事件生命周期与去重、抓拍节流
- node-aware 字段预留
- 事件详情 / 导出 / 时间线 / 测试结果展示
- 结果摘要区与交付资产入口

## 关键参数
- 风险阈值：以 `CONFIG,STATUS` 实时输出为准
- 事件冷却：以 `CONFIG,STATUS` / `EVENT,STATUS` 为准
- 抓拍节流：以 `EVENT,STATUS` 为准
- 音频参与策略：以 `CONFIG,STATUS` 为准

## 结果资产
- 误报率：`captures/false_alarm_result.json`
- E2E 延迟：`captures/e2e_latency_result.json`
- 验收快照：`captures/latest_acceptance_snapshot.json`
- 交付包就绪：`captures/latest_delivery_bundle_readiness_report.json`
- 证据闭环：`captures/latest_single_node_evidence_closure_report.json`

## 样例事件
- 推荐样例：以 dashboard 当前可选事件和 `event_exports/` 最新导出为准。

## 本周完成
- 主链稳定性补强
- 事件解释与证据导出链可展示
- 结果文件从“命令行产物”升级到“页面可读资产”
- 演示检查单与现场恢复检查单补齐

## 本周未完成
- 真实 A1/A2 双节点联动闭环
- 最终比赛版截图全量补齐
- 对外汇报用的最终彩排稿

## 下周优先项
- 真实双节点联调
- A 与 B 的正式闭环
- 补齐现场截图与最终汇报包
