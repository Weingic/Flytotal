# 2026-04-16 周报（第二轮深化冻结版）

## 第一部分：本周真正完成了什么

### Win 侧（固件 / 主链）
1. 音频异常状态占位正式接入主链（`AudioState`：IDLE / NORMAL / ANOMALY / BACKGROUND）。
2. `AudioConfig.AudioEnabled` 开关控制音频因子参与风险计算，默认关闭，不破坏旧验收。
3. 新增串口命令：`AUDIO,ANOMALY` / `AUDIO,NORMAL` / `AUDIO,STATUS`。
4. 多模态主链稳定化：视觉 + 音频 + RID 三因子组合测试通过回归，旧链路未被拖坏。
5. 关键场景回归验证：合法目标不报警、非合作目标升级事件、视觉影响风险、音频影响风险。

### Mac 侧（工具链 / 证据链 / 网页）
1. 证据链 hash 框架正式可运行（`evidence_hash_证据链哈希.py`）：
   - SHA-256 摘要，字段集与 Win 侧冻结口径对齐。
   - 支持 `--verify` 核验存储 hash 是否与内容一致。
2. 误报率基线测试框架正式可运行（`false_alarm_baseline_误报率基线测试.py`）：
   - 支持 `empty` / `static_disturbance` 两个场景。
   - 支持 `--mock` 自测、`--batch` 批量、`--table` ASCII 表、`--csv` 导出。
   - 本周实测：**2 场景 PASS，误报率 0%**（见第四部分指标）。
3. E2E 延迟统计框架正式可运行（`e2e_latency_stats_E2E延迟统计.py`）：
   - 注入点 → 事件输出自动配对，计算 mean / min / max / P50 / P95。
   - 支持 `--mock` 自测（800ms 合成延迟 PASS），`--table` 输出，`--batch` 批量汇总。
4. 一致性核对工具正式可运行（`consistency_check_一致性核对.py`）：
   - 三重核对：hash 存在性 / 格式合法性 / 重算一致性 + 核心字段完整性。
   - `--generate-sample` 一键生成带完整字段和正确 hash 的证据样例。
5. 网页事件详情页补齐：
   - `vision_state` 颜色 pill（LOCKED=绿 / LOST=橙 / SEARCHING=黄 / IDLE=灰）。
   - 视觉贡献（`vision_contribution`）实时展示。
   - `ts_open` / `ts_close` / `close_reason` 字段显示。
   - `evidence_hash` 前缀 + SHA256 pill 展示（tooltip 显示完整 hash）。
6. Python 3.9 兼容修复：所有工具脚本补加 `from __future__ import annotations`。

---

## 第二部分：本周稳定边界

1. 误报率基线：空场和静态扰动两个场景测试结果 **PASS，误报率 0%**。
2. E2E 延迟框架：`--mock 800ms` 自测 PASS，`--mock 3500ms` 正确输出 FAIL。
3. 证据链 hash：mock 样例 `A1-SAMPLE-0001` 一致性核验 **PASS**。
4. 视觉桥接：引导框（radar_to_frame 映射）、VisionStateReporter（3帧防抖）、抓拍链路稳定。
5. 网页端：事件详情页七个字段组全部可显示（ID / 时间 / 风险 / 身份 / 视觉 / 证据 / 抓拍）。

---

## 第三部分：当前还没做 / 没做稳的部分

1. E2E 延迟尚无真机 session log 数据，当前只有 mock 自测，P95 阈值有效性待真机验证。
2. 旧证据 JSON（`A1-0000143953-0003`）不含 `event_object_v1`，一致性核验 FAIL — 需要重新导出。
3. 网页截图尚未系统归档，详情页字段展示未在真机上完整验证。
4. 音频链路当前为占位状态，`AUDIO_ANOMALY` 影响风险的幅度参数尚未真机校准。
5. `capture_ready_hits=0` 偶发问题（P1-01）尚未闭环。

---

## 第四部分：本周指标结果

### 误报率基线（2026-04-16）
| 场景 | 状态 | 观测事件数 | 期望 | 误报数 | 误报率 |
|---|---|---|---|---|---|
| empty（纯空场） | **PASS** | 0 | 0 | 0 | 0.00% |
| static_disturbance（静态扰动） | **PASS** | 0 | 0 | 0 | 0.00% |

### E2E 延迟（mock 自测，无真机数据）
| 场景 | 样本数 | 均值 | P50 | P95 | 阈值 | 状态 |
|---|---|---|---|---|---|---|
| mock_800ms | 5 | 800ms | 800ms | 800ms | 3000ms | **PASS** |
| mock_3500ms（FAIL路径验证） | 5 | 3500ms | 3500ms | 3500ms | 3000ms | **FAIL（符合预期）** |

### 证据链 hash 一致性
| 文件 | 状态 | 说明 |
|---|---|---|
| `event_evidence_A1-SAMPLE-0001_mock.json` | **PASS** | mock 样例，完整字段 + hash 一致 |
| `event_evidence_A1-0000143953-0003_*.json` | FAIL | 旧格式，无 `event_object_v1`，需重新导出 |

---

## 第五部分：下周进入方向

1. **真机 E2E 延迟测量**：接入 `track_injector` 生成真实 session log，跑 `e2e_latency_stats` 得到真机 P95 数据。
2. **旧证据文件重新导出**：用新版 web server（含 `evidence_hash` 自动附加）重新生成导出文件，使 consistency_check 全部 PASS。
3. **音频链路校准**：与 Win 侧对齐 `AudioConfig.RiskBonus`，确认音频因子不破坏现有场景。
4. **P1-01 闭环**：解决 `capture_ready_hits=0` 偶发，补充状态 + 抓拍联合判定逻辑。
5. **网页截图归档**：在真机运行后对详情页做全字段截图，作为答辩证据存档。

---

## 本周冻结结论

冻结版本：`Node A Hunter+Vision+Audio+Evidence Demo V2.0`

本周结束时，当前系统新增具备：
1. 证据链 hash 计算与核验工具（可运行）
2. 误报率基线测试工具（2 场景 PASS，0% 误报率）
3. E2E 延迟统计工具（框架可运行，mock 自测通过）
4. 一致性核对工具（三重核验逻辑验证通过）
5. 网页事件详情页完整字段展示
6. 音频状态正式占位接入主链（Win 侧）
7. 多模态回归测试通过（视觉 + RID + 音频不互相破坏）
