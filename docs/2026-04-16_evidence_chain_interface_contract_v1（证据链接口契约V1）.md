# 2026-04-16 证据链接口契约 V1

## 定位

本文档定义证据链（Evidence Chain）相关的字段集合、hash 计算规则和跨侧约定。  
Win 侧（固件）和 Mac 侧（Python 工具）均须遵守本文档的字段顺序和计算规范，否则 hash 核验会失败。

---

## 一、证据 hash 核心字段集（冻结）

以下字段按顺序参与 SHA-256 计算，**顺序不可改变**：

| 序号 | 字段名 | 类型 | 含义 | 缺失时填充值 |
|---|---|---|---|---|
| 1 | `event_id` | string | 事件唯一编号 | `null` |
| 2 | `track_id` | int | 轨迹编号 | `null` |
| 3 | `risk_score` | float | 风险分（精度 2 位小数） | `null` |
| 4 | `rid_status` | string | 身份状态（`RID_*`） | `null` |
| 5 | `wl_status` | string | 白名单状态（`WL_*`） | `null` |
| 6 | `reason_flags` | string | 风险来源标志集合 | `null` |
| 7 | `capture_path` | string | 抓拍图相对路径 | `null` |
| 8 | `ts_open` | int(ms) | 事件开启时间戳 | `null` |
| 9 | `ts_close` | int(ms) | 事件关闭时间戳 | `null` |
| 10 | `close_reason` | string | 关闭原因（`RISK_DOWNGRADE` 等） | `null` |

---

## 二、hash 计算规范

```
1. 按上表顺序提取字段值，字段不存在时填充 null。
2. 序列化：json.dumps(payload, ensure_ascii=False, separators=(',', ':'), sort_keys=False)
3. 编码：UTF-8
4. 摘要：hashlib.sha256(canonical.encode('utf-8')).hexdigest()
5. 输出：64 位十六进制小写字符串
```

**排除字段**：`evidence_hash` / `hash_fields` / `hash_algorithm` 本身不参与计算（避免循环依赖）。

---

## 三、证据对象附加字段

计算完成后，向证据对象写入以下三个元字段：

| 字段名 | 类型 | 值 |
|---|---|---|
| `evidence_hash` | string | 64 位 SHA-256 hex |
| `hash_fields` | list[string] | 上表字段名列表（按序） |
| `hash_algorithm` | string | `"sha256"` |

---

## 四、事件对象完整字段（`event_object_v1`）

`event_object_v1` 是证据导出文件中 `event_detail.event_object_v1` 对象的标准结构：

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `schema_version` | string | Mac | 固定 `"event_object_v1"` |
| `event_id` | string | Win | 事件唯一编号 |
| `node_id` | string | Win | 节点编号 |
| `track_id` | int | Win | 轨迹编号 |
| `risk_score` | float | Win | 风险分 |
| `risk_level` | string | Win | `NONE/NORMAL/HIGH_RISK/EVENT` |
| `hunter_state` | string | Win | Hunter 子状态 |
| `rid_status` | string | Win | 身份状态 |
| `wl_status` | string | Win | 白名单状态（hash 用） |
| `whitelist_status` | string | Win | 白名单状态（展示用，同值） |
| `vision_state` | string | Mac | 视觉状态 |
| `trigger_flags` | string | Win | 触发标志 |
| `reason_flags` | string | Win | 风险来源标志（hash 用） |
| `start_time` | int(ms) | Win | 事件开始（兼容旧字段） |
| `update_time` | int(ms) | Win | 最近更新（兼容旧字段） |
| `ts_open` | int(ms) | Win | 事件开启时间戳（hash 字段） |
| `ts_close` | int(ms) | Win | 事件关闭时间戳（hash 字段） |
| `close_reason` | string | Win | 关闭原因（hash 字段） |
| `x` | float | Win | x 坐标（mm） |
| `y` | float | Win | y 坐标（mm） |
| `capture_path` | string | Mac | 抓拍图路径（hash 字段） |
| `event_state` | string | Win | `OPEN/CLOSED/NONE` |
| `evidence_hash` | string | Mac | SHA-256 摘要 |
| `hash_fields` | list | Mac | 参与 hash 的字段名列表 |
| `hash_algorithm` | string | Mac | `"sha256"` |

---

## 五、证据导出文件结构（`event_evidence_*.json`）

```json
{
  "ok": true,
  "available": true,
  "export_generated_ms": 1776323000000,
  "event_id": "A1-XXXX-NNNN",
  "evidence_hash": "<64位hex>",
  "event_detail": {
    "ok": true,
    "available": true,
    "event_id": "A1-XXXX-NNNN",
    "event_object_v1": { "<上表所有字段>" },
    "capture_binding_mode": "strict|fallback",
    "capture_count": 1,
    "latest_capture": { "file_path": "...", "url": "...", "reason": "..." },
    "captures": []
  },
  "node_status_snapshot": { "<导出时的节点快照>" },
  "capture_match_mode": "strict",
  "suggested_file_name": "event_evidence_A1-XXXX-NNNN_<ts>.json",
  "export_saved": true,
  "export_file_path": "captures/event_exports/..."
}
```

---

## 六、核验命令

```bash
# 核验单个文件 hash 是否一致
python3 tools/evidence_hash_证据链哈希.py --input captures/event_exports/event_evidence_xxx.json --verify

# 批量一致性核对
python3 tools/consistency_check_一致性核对.py --export-dir captures/event_exports

# 生成 mock 样例（可直接通过核验）
python3 tools/consistency_check_一致性核对.py --generate-sample captures/event_exports/event_evidence_sample.json
```

---

## 七、变更记录

| 日期 | 版本 | 变更内容 |
|---|---|---|
| 2026-04-16 | V1 | 初始定义，冻结 10 个 hash 字段，建立证据导出文件结构 |
