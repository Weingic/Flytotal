# 2026-04-16 Week 2 冻结清单（Freeze Manifest）

冻结时间：2026-04-16  
分支：`integration/multimodal-v1.2`  
冻结目标：将 integration 稳定版合并到 main

---

## 一、冻结验收结果

| 验收项 | 命令 | 结果 |
|---|---|---|
| 误报率基线 empty | `false_alarm_baseline --mock` | **PASS** |
| 误报率基线 static_disturbance | `false_alarm_baseline --mock --batch` | **PASS** |
| E2E 延迟 800ms 路径 | `e2e_latency_stats --mock` | **PASS** |
| E2E 延迟 3500ms 失败路径 | `e2e_latency_stats --mock --mock-latency-ms 3500` | FAIL（正确检测） |
| 证据链 hash 验证 | `evidence_hash --input A1-SAMPLE-0001 --verify` | **PASS** |
| 一致性核对 | `consistency_check --input A1-SAMPLE-0001` | **PASS** |
| Python 语法检查（全工具） | `py_compile` × 6 | **全部 PASS** |

---

## 二、冻结内容清单

### Mac 侧工具链（新增）
| 文件 | 说明 |
|---|---|
| `tools/e2e_latency_stats_E2E延迟统计.py` | E2E 注入→事件配对延迟统计，支持 mock/batch/table/csv |
| `tools/false_alarm_baseline_误报率基线测试.py` | 误报率基线，支持 empty/static_disturbance 场景 |
| `tools/consistency_check_一致性核对.py` | 三重一致性核对：hash 存在 / 格式合法 / 重算一致 |
| `tools/evidence_hash_证据链哈希.py` | SHA-256 证据链 hash 计算与核验（已修复包裹格式识别） |

### Mac 侧工具链（修改）
| 文件 | 修改说明 |
|---|---|
| `tools/vision_bridge_视觉桥接.py` | 引导框绘制、注释完善、f-string 清理 |
| `tools/vision_web_server_视觉网页服务.py` | vision_contribution 注入、score_delta 计算 |
| `tools/vision_dashboard.html` | 事件详情页补全 ts_open/ts_close/close_reason/risk_score/evidence_hash |

### 证据链样例
| 文件 | 说明 |
|---|---|
| `captures/event_exports/event_evidence_A1-SAMPLE-0001_mock.json` | 完整 mock 证据 JSON，hash 已核验 PASS |

### 文档
| 文件 | 说明 |
|---|---|
| `docs/2026-04-16_evidence_chain_interface_contract_v1（证据链接口契约V1）.md` | hash 字段集、计算规范、event_object_v1 完整字段定义 |
| `docs/2026-04-16_metrics_results_w2（第二周指标结果）.md` | 本周全指标结果（含修复后状态） |
| `docs/2026-04-16_weekly_report_w2（第二周周报）.md` | 本周工作总结 |
| `docs/2026-04-16_open_issues_backlog_v2（当前问题剩余清单V2）.md` | 当前 P1/P2 问题列表 |
| `docs/2026-04-16_next_week_todo_w3（第三周TODO）.md` | 下周 P0/P1 任务清单 |

---

## 三、已知未闭环项（不阻塞本次冻结）

| ID | 问题 | 绕行策略 |
|---|---|---|
| P1-01 | `capture_ready_hits=0` 偶发 | mock 路径已验证，真机有偶发；下周闭环 |
| P1-04 | 旧证据 JSON 无 `event_object_v1` | hash 工具已修复识别逻辑；旧文件需重新导出 |
| P1-05 | E2E 无真机 session log | mock 800ms PASS，P95 阈值有效性待真机验证 |
| P2-03 | VisionStateReporter 只打 stdout | 视觉状态未实际回写 Win 侧，下周接串口 |

---

## 四、merge 到 main 的条件确认

- [x] 所有工具 py_compile 通过
- [x] 证据链 hash 一致性 PASS
- [x] 误报率基线 2 场景 PASS
- [x] E2E 延迟 mock PASS（800ms < 3000ms 阈值）
- [x] 网页详情页六字段 DOM + JS 齐备
- [x] integration 分支无未解决冲突
- [ ] 真机 E2E 数据（P1-05，记录为已知缺口，不阻塞 merge）

**结论：满足本轮冻结条件，可合并到 main。**
