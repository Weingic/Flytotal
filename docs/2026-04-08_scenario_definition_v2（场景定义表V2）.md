# 2026-04-08 场景定义表 V2

## 1. 目标
这版用于 4.8 阶段统一“测试动作”和“页面预期”。
每个场景除了主链状态，还明确网页显示、抓拍、事件卡片、历史记录、视觉锁定预期。

## 2. 判定字段
- 网页端显示：看板关键区域应出现的状态
- 抓拍触发：是否应出现抓拍记录
- 事件卡片：是否应出现事件语义卡片/高亮
- 历史留痕：测试结果历史是否应新增一条记录
- 视觉 LOCKED：视觉状态是否应进入 `VISION_LOCKED`

## 3. 场景表（V2）
| 场景ID | 输入动作摘要 | 预期主链状态 | 网页端显示 | 抓拍触发 | 事件卡片 | 历史留痕 | 视觉 LOCKED |
|---|---|---|---|---|---|---|---|
| S1_idle_baseline | `RESET` 后执行 `BRIEF` | `IDLE / NONE` | 测试结果简报为基线、逐项陪跑第1关可判定 | 否 | 否 | 是（suite_check） | 否 |
| S2_event_open_missing_rid | 连续 `TRACK` + `RID,MISSING` | `SUSPICIOUS/HIGH_RISK`，事件 `OPEN` | 风险上升、事件状态 `OPEN`、时间线出现 `event_open_*` | 建议是（若视觉链在线） | 是 | 是 | 是（视觉在线时） |
| S3_risk_downgrade | `RID,OK` 后继续 `TRACK` | 风险回落，事件 `CLOSED`，关闭原因为 `RISK_DOWNGRADE` | 逐项陪跑第3关通过，最近事件可见 `RISK_DOWNGRADE` | 否 | 是（关闭语义） | 是 | 否/可回到搜索 |
| S4_track_lost_close | 事件打开后 `TRACK,CLEAR` | `LOST / NONE`，关闭原因为 `TRACK_LOST` | 逐项陪跑第4关通过，`LASTEVENT` 显示 `TRACK_LOST` | 否 | 是（关闭语义） | 是 | 否 |
| S5_suite_all_pass | `--suite standard_acceptance` 全流程 | 7/7 PASS | 时间线显示 `suite_started/check/finished`，结果简报 PASS | 可有可无 | 是 | 是（新增 PASS 记录） | 取决于视觉链 |
| S6_suite_fail_case | 人为构造失败（命令异常或时序不满足） | 存在 FAIL 项 | 逐项陪跑出现 FAIL 关卡，并提示下一步复测命令 | 可无 | 是（失败项高亮） | 是（新增 FAIL/WARN 记录） | 不强制 |
| S7_mock_pipeline | 看板切到模拟模式 `mode=mock` | 数据由 mock 返回 | 顶部显示“模拟链路”，各卡片可更新 | 模拟抓拍可见 | 模拟事件可见 | 是（模拟历史） | 模拟可设为是 |

## 4. 执行建议
- 真实联调：先开 bridge，再跑 suite，再看逐项陪跑关卡。
- 页面开发：先切模拟模式，确认卡片渲染和交互，再回真实链路做回归。

## 5. 验收口径
- 每轮至少保存：一条套件总结果 + 一条关键检查摘要 + 一条事件关闭语义证据。
- 页面与终端冲突时，以结构化字段为准（`EVENT,STATUS / LASTEVENT / suite_check`）。
