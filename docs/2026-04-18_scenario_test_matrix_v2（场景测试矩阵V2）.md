# 2026-04-18 场景测试矩阵 V2

## 必测场景（6 个）
| 场景 | 输入 | 预期状态 | 预期事件 | 预期视觉 |
|---|---|---|---|---|
| 合法目标通过 | TRACK + RID 合法 | `TRACKING/RID_MATCHED/NORMAL` | 无高危事件 | 可 `SEARCHING/LOCKED` |
| 无身份短时穿越 | 短时 TRACK + RID 缺失 | 不直接事件化 | 可无事件 | 可无锁定 |
| 无身份悬停 | 持续 TRACK + RID 缺失 | 升至 `HIGH_RISK` | 打开事件 | 进入抓拍准备 |
| 身份异常目标 | TRACK + RID INVALID | 快速升风险 | 触发事件 | 进入锁定/抓拍 |
| 高风险事件触发 | 持续高危条件 | `HIGH_RISK/EVENT` | `OPEN` | `VISION_LOCKED` 优先 |
| 目标丢失回落 | `TRACK,CLEAR` 或丢失 | 平稳回落 `LOST/IDLE` | 事件关闭 | `VISION_LOST` |

## 结果记录口径
1. 每场景记录：命令、关键日志、PASS/FAIL、异常说明。
2. 统一输出到 `captures/latest_acceptance_snapshot.json` 与 `captures/session_logs/*.jsonl`。

## 本轮实测记录（2026-04-14）
### 执行命令
`python tools/acceptance_flow_411_单节点闭环验收流程.py --mode full --port COM4 --suite-chain rid_identity_chain_v1,risk_event_vision_chain_v1 --closure-require-vision-lock --no-closure-require-capture-ready`

### 总结结果
1. 验收总结果：`PASS`（`steps_passed=5/5`）。
2. 预检：`PASS`（`vision_runtime_ready=1`）。
3. 套件链：
   - `rid_identity_chain_v1`：`3/3 PASS`
   - `risk_event_vision_chain_v1`：`6/6 PASS`
4. 闭环证据：`PASS`（`vision_lock_hits=2`，`capture_ready_hits=1`，`closure_export_count=1`）。

### 场景结果（6 场景）
| 场景 | 本轮结果 | 证据摘要 |
|---|---|---|
| 合法目标通过 | PASS | `scenario3_legal_target_keep_low_risk` 通过，合法目标保持低风险 |
| 无身份短时穿越 | PASS | `scenario1_short_missing_rid_no_direct_event` 通过，不直接事件化 |
| 无身份悬停 | PASS | `scenario2_sustained_missing_rid_risk_upgrade` 通过，持续后升风险 |
| 身份异常目标 | PASS | `scenario4_suspicious_rid_fast_risk_upgrade` 通过，快速升风险 |
| 高风险事件触发 | PASS | `scenario5_high_risk_visual_capture_ready` 通过，视觉锁定与抓拍预备成立 |
| 目标丢失回落 | PASS | `scenario6_track_lost_smooth_recover` 通过，平稳回落并关闭事件 |

### 证据文件
1. `captures/latest_411_acceptance_flow_report.json`
2. `captures/latest_single_node_evidence_closure_report.json`
3. `captures/latest_test_session.json`
4. `captures/latest_acceptance_snapshot.json`
