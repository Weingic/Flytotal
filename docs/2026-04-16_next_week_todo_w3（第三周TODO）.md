# 2026-04-16 第三周 TODO

截止：下周冻结日（预计 2026-04-23）

---

## Mac 侧

### P0（必须完成）
- [ ] **真机 E2E 延迟测量**
  - 接入 `track_injector` 生成真实 session log
  - 跑 `e2e_latency_stats --table` 得到真机 P50 / P95
  - 验证 P95 ≤ 3000ms（当前阈值）
  - 输出：`captures/e2e_latency_result.json`

- [ ] **旧证据文件重新导出**
  - 用新版 web server（含 `evidence_hash` 自动附加）重导 `A1-0000143953-0003`
  - 确认 `consistency_check` 全部 PASS（目标：2/2 PASS）

- [ ] **误报率真机验证**
  - 在真机空场运行 `false_alarm_baseline --mode empty --duration 60`
  - 记录结果并归档到 `captures/false_alarm_result.json`

### P1（本周完成更好）
- [ ] **网页详情页全字段截图归档**
  - 在真机事件上截取详情页，确认 hash / rid / wl / vision / capture 七组字段全部可见
  - 存入 `docs/screenshots/` 目录（新建）

- [ ] **VisionStateReporter 串口对接**
  - 当前 `VISION_CMD,VISION_LOCKED` 只打 stdout
  - 接入真实串口，向 Win 侧发送 vision 状态（需与 Win 侧约定串口命令格式）

- [ ] **文档索引修复**
  - `README（文档索引）.md` 存在历史乱码（P1-03）
  - 清理旧条目，补充第二周新增文档条目

### P2（优化项）
- [ ] 抓拍质量优化（曝光参数、锁定时机，P2-02）
- [ ] 误报率脚本 `--csv` 输出格式验证（与表格数字一致性核对）
- [ ] E2E batch 模式在真机目录下跑通

---

## Win 侧（只读，不执行）

| 任务 | 说明 |
|---|---|
| 音频因子参数校准 | `AudioConfig.RiskBonus` 真机测量，确保不破坏现有 6 个场景 |
| P1-01 闭环 | `capture_ready_hits=0` 偶发，补充状态+抓拍联合判定 |
| 双节点协同前置 | 评估 Node A → Node B 事件广播接口需求 |

---

## 本周退出条件

以下条件全部满足，本周可冻结：
1. 真机 E2E P95 ≤ 3000ms（有实测数据）
2. `consistency_check` 全部 PASS（包含真实事件文件）
3. 误报率真机测试至少 1 次 PASS
4. 网页详情页截图存档
