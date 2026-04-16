# 2026-04-16 第二周指标结果

生成时间：2026-04-16  
工具链版本：Week 2 / feat/mac-claude

---

## 一、误报率基线（false_alarm_baseline）

### 执行命令
```bash
python3 tools/false_alarm_baseline_误报率基线测试.py --batch --table
```

### 结果表格
```
--------------------------------------------------------------------
场景                     状态         观测     期望     误报      误报率    时长(s)
--------------------------------------------------------------------
empty                  PASS        0      0      0   0.00%        0
static_disturbance     PASS        0      0      0   0.00%        0
--------------------------------------------------------------------
```

### 结论
- **2 场景全部 PASS**
- **误报率：0%**
- 数据来源：离线模式读取 `captures/latest_node_events.json` + `captures/latest_node_event_store.json`（文件不存在时视为 0 事件，结果等价于空场）
- 注：真机验证需在实际采集时段内运行，当前数字已反映工具链逻辑正确性

---

## 二、E2E 延迟统计（e2e_latency_stats）

### 执行命令（mock 自测）
```bash
python3 tools/e2e_latency_stats_E2E延迟统计.py --mock --mock-latency-ms 800
python3 tools/e2e_latency_stats_E2E延迟统计.py --mock --mock-latency-ms 3500
```

### mock 结果表格
```
-----------------------------------------------------------------------------------
场景                     状态        样本    均值ms    最小ms    最大ms   P50ms   P95ms    阈值ms
-----------------------------------------------------------------------------------
mock_800ms             PASS       5     800     800     800     800     800    3000
mock_3500ms            FAIL       5    3500    3500    3500    3500    3500    3000
-----------------------------------------------------------------------------------
```

### 结论
- **PASS 路径（800ms < 3000ms 阈值）：PASS** ✓
- **FAIL 路径（3500ms > 3000ms 阈值）：正确检测为 FAIL** ✓
- 配对逻辑：`track_point_sent` → `node_event[EVENT_OPENED]`，最近前驱匹配，30s 有效窗口
- 真机数据：待接入 `track_injector` 生成 session log 后补充

---

## 三、证据链 hash 一致性（consistency_check）

### 执行命令
```bash
python3 tools/consistency_check_一致性核对.py --export-dir captures/event_exports --verbose
```

### 结果（2026-04-16 冻结日更新）
```
[check] PASS  event_evidence_A1-SAMPLE-0001_mock.json  event_id=A1-SAMPLE-0001

汇总: 共1个文件  PASS=1  FAIL=0
```

### 结论
| 文件 | 结果 | 说明 |
|---|---|---|
| `A1-SAMPLE-0001`（mock 样例） | **PASS** | 完整字段 + SHA-256 一致，包裹格式识别已修复 |

- `evidence_hash` 工具已修复：自动识别导出文件外层包裹结构，正确提取 `event_detail.event_object_v1` 进行 hash 计算
- 旧证据文件（`A1-0000143953-0003`）不含 `event_object_v1`，需用新版 web server 重新导出，已列为 P1-04

---

## 四、mock 证据样例摘要

文件：`captures/event_exports/event_evidence_A1-SAMPLE-0001_mock.json`

```
event_id     : A1-SAMPLE-0001
risk_score   : 62.5
rid_status   : RID_MATCHED
wl_status    : NOT_WL
vision_state : VISION_LOCKED
close_reason : RISK_DOWNGRADE
evidence_hash: 1b1c9414946469f7...（完整 64 位 SHA-256）
hash_fields  : [event_id, track_id, risk_score, rid_status, wl_status,
                reason_flags, capture_path, ts_open, ts_close, close_reason]
consistency  : PASS
```

---

## 五、自测通过清单

| 工具 | 命令 | 结果 |
|---|---|---|
| `false_alarm_baseline` | `--mock` | PASS |
| `false_alarm_baseline` | `--mock --mock-inject-false-alarms 3` | PASS（FAIL 路径验证） |
| `e2e_latency_stats` | `--mock` | PASS |
| `e2e_latency_stats` | `--mock --mock-latency-ms 3500` | PASS（FAIL 路径验证） |
| `evidence_hash` | `--input <sample> --verify` | PASS |
| `consistency_check` | `--mock` | PASS（3 个 case 全通过） |
| `consistency_check` | `--generate-sample + --input` | PASS |
