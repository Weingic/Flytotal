from __future__ import annotations

# 一致性核对工具
# 对 captures/event_exports/ 目录下的证据文件做三重核对：
#   1. evidence_hash 字段完整性（是否存在、是否合法 sha256 hex）
#   2. evidence_hash 重新计算后与存储值是否一致
#   3. 核心字段完整性（EVIDENCE_HASH_FIELDS 是否全部存在且非 None）
#
# 使用方式：
#   python tools/consistency_check_一致性核对.py
#   python tools/consistency_check_一致性核对.py --export-dir captures/event_exports
#   python tools/consistency_check_一致性核对.py --input captures/event_exports/event_evidence_xxx.json
#   python tools/consistency_check_一致性核对.py --mock
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 与 evidence_hash_证据链哈希.py 保持同步
EVIDENCE_HASH_FIELDS: tuple[str, ...] = (
    "event_id", "track_id", "risk_score", "rid_status", "wl_status",
    "reason_flags", "capture_path", "ts_open", "ts_close", "close_reason",
)
HASH_EXCLUDED: frozenset[str] = frozenset({"evidence_hash", "hash_fields", "hash_algorithm"})


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"读取失败: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"顶层必须是 JSON object: {path}")
    return data


def compute_hash(evidence: dict[str, Any]) -> str:
    """按固定字段顺序计算 SHA-256（与 evidence_hash_证据链哈希.py 完全一致）。"""
    payload: dict[str, Any] = {}
    for key in EVIDENCE_HASH_FIELDS:
        if key in HASH_EXCLUDED:
            continue
        payload[key] = evidence.get(key, None)
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 核对结果数据结构
# ---------------------------------------------------------------------------

@dataclass
class FieldCheck:
    field: str
    present: bool
    is_none: bool


@dataclass
class FileCheckResult:
    file_name: str
    event_id: str
    has_event_object_v1: bool
    hash_present: bool
    hash_format_ok: bool          # 是否是 64 位 hex
    hash_match: bool              # 重算后是否一致
    stored_hash: str
    recomputed_hash: str
    missing_fields: list[str]     # EVIDENCE_HASH_FIELDS 中缺失或为 None 的字段
    passed: bool
    note: str


def _check_file(path: Path) -> FileCheckResult:
    try:
        doc = load_json_file(path)
    except ValueError as exc:
        return FileCheckResult(
            file_name=path.name, event_id="UNKNOWN", has_event_object_v1=False,
            hash_present=False, hash_format_ok=False, hash_match=False,
            stored_hash="", recomputed_hash="", missing_fields=[],
            passed=False, note=str(exc),
        )

    event_id = str(doc.get("event_id", "NONE") or "NONE")

    # 优先从 event_object_v1 取；退化到顶层
    detail = doc.get("event_detail", {}) or {}
    ev_obj = detail.get("event_object_v1", {}) if isinstance(detail, dict) else {}
    if not isinstance(ev_obj, dict):
        ev_obj = {}

    has_v1 = bool(ev_obj)

    # 如果 event_object_v1 为空，尝试从 doc 顶层 fallback（老格式兼容）
    evidence = ev_obj if has_v1 else doc

    stored = str(evidence.get("evidence_hash", "") or "")
    hash_present = bool(stored)
    hash_format_ok = len(stored) == 64 and all(c in "0123456789abcdef" for c in stored)

    recomputed = compute_hash(evidence)
    hash_match = stored == recomputed if hash_present else False

    # 字段完整性：检查 EVIDENCE_HASH_FIELDS 是否存在且非 None
    missing: list[str] = []
    for f in EVIDENCE_HASH_FIELDS:
        if f in HASH_EXCLUDED:
            continue
        val = evidence.get(f, "__MISSING__")
        if val == "__MISSING__" or val is None:
            missing.append(f)

    passed = hash_present and hash_format_ok and hash_match and len(missing) == 0

    note_parts: list[str] = []
    if not has_v1:
        note_parts.append("无event_object_v1(用顶层fallback)")
    if not hash_present:
        note_parts.append("evidence_hash缺失")
    elif not hash_format_ok:
        note_parts.append("hash格式非法")
    elif not hash_match:
        note_parts.append("hash不一致")
    if missing:
        note_parts.append(f"缺字段:{','.join(missing)}")

    return FileCheckResult(
        file_name=path.name,
        event_id=event_id,
        has_event_object_v1=has_v1,
        hash_present=hash_present,
        hash_format_ok=hash_format_ok,
        hash_match=hash_match,
        stored_hash=stored,
        recomputed_hash=recomputed,
        missing_fields=missing,
        passed=passed,
        note=" | ".join(note_parts) if note_parts else "OK",
    )


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def print_result(r: FileCheckResult, verbose: bool = False) -> None:
    flag = "PASS" if r.passed else "FAIL"
    print(f"[check] {flag}  {r.file_name}  event_id={r.event_id}")
    if not r.passed or verbose:
        print(f"  note={r.note}")
        if r.hash_present and not r.hash_match:
            print(f"  stored    = {r.stored_hash}")
            print(f"  recomputed= {r.recomputed_hash}")
        if r.missing_fields:
            print(f"  missing_fields = {r.missing_fields}")


def print_summary(results: list[FileCheckResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    print(f"\n[check] 汇总: 共{total}个文件  PASS={passed}  FAIL={failed}")


# ---------------------------------------------------------------------------
# Mock 自测
# ---------------------------------------------------------------------------

def run_mock_self_test() -> bool:
    """用合成数据验证核对逻辑，返回 True 表示通过。"""
    print("\n[check][mock] 开始自测")
    ok_all = True

    # Case 1：完整字段 + 正确 hash → 期望 PASS
    ev_ok: dict[str, Any] = {
        "event_id": "MOCK_001", "track_id": 1, "risk_score": 42.0,
        "rid_status": "RID_OK", "wl_status": "NOT_WL",
        "reason_flags": "SPEED|ALT", "capture_path": "captures/img.jpg",
        "ts_open": 1000, "ts_close": 5000, "close_reason": "RISK_DOWNGRADE",
    }
    ev_ok["evidence_hash"] = compute_hash(ev_ok)
    ev_ok["hash_fields"] = list(EVIDENCE_HASH_FIELDS)
    ev_ok["hash_algorithm"] = "sha256"

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
        json.dump({"event_id": "MOCK_001", "event_detail": {"event_object_v1": ev_ok}}, f, ensure_ascii=False)
        tmp1 = Path(f.name)
    r1 = _check_file(tmp1)
    tmp1.unlink(missing_ok=True)
    s1 = "PASS" if r1.passed else "FAIL(unexpected)"
    if not r1.passed:
        ok_all = False
    print(f"[check][mock] Case1(完整+正确hash): {s1}  note={r1.note}")

    # Case 2：hash 被篡改 → 期望 FAIL
    ev_bad = dict(ev_ok)
    ev_bad["evidence_hash"] = "a" * 64
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
        json.dump({"event_id": "MOCK_002", "event_detail": {"event_object_v1": ev_bad}}, f, ensure_ascii=False)
        tmp2 = Path(f.name)
    r2 = _check_file(tmp2)
    tmp2.unlink(missing_ok=True)
    case2_ok = not r2.passed   # 期望 FAIL
    s2 = "PASS(FAIL路径验证成功)" if case2_ok else "FAIL(未检测到篡改)"
    if not case2_ok:
        ok_all = False
    print(f"[check][mock] Case2(hash篡改): {s2}  note={r2.note}")

    # Case 3：缺少 ts_open / ts_close → 期望 FAIL
    ev_missing = dict(ev_ok)
    ev_missing.pop("ts_open", None)
    ev_missing.pop("ts_close", None)
    ev_missing["evidence_hash"] = compute_hash(ev_missing)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
        json.dump({"event_id": "MOCK_003", "event_detail": {"event_object_v1": ev_missing}}, f, ensure_ascii=False)
        tmp3 = Path(f.name)
    r3 = _check_file(tmp3)
    tmp3.unlink(missing_ok=True)
    case3_ok = not r3.passed  # 期望 FAIL (missing_fields)
    s3 = "PASS(缺字段检测成功)" if case3_ok else "FAIL(未检测到缺字段)"
    if not case3_ok:
        ok_all = False
    print(f"[check][mock] Case3(缺字段): {s3}  note={r3.note}")

    overall = "PASS" if ok_all else "FAIL"
    print(f"[check][mock] 自测结果={overall}")
    return ok_all


# ---------------------------------------------------------------------------
# 样例生成
# ---------------------------------------------------------------------------

def _generate_sample(out_path: Path) -> None:
    """生成一个带完整字段和正确 evidence_hash 的 mock 证据文件。"""
    import time as _time
    now = int(_time.time() * 1000)
    ts_open = now - 12000
    ts_close = now - 2000

    ev: dict[str, Any] = {
        "schema_version": "event_object_v1",
        "event_id": "A1-SAMPLE-0001",
        "node_id": "NODE_A1",
        "track_id": 7,
        "risk_score": 62.5,
        "risk_level": "HIGH",
        "hunter_state": "HUNTING",
        "rid_status": "RID_MATCHED",
        "wl_status": "NOT_WL",
        "whitelist_status": "NOT_WL",
        "vision_state": "VISION_LOCKED",
        "trigger_flags": "SPEED|ALT",
        "reason_flags": "SPEED|ALT",
        "start_time": ts_open,
        "update_time": ts_close,
        "ts_open": ts_open,
        "ts_close": ts_close,
        "close_reason": "RISK_DOWNGRADE",
        "x": 320.5,
        "y": 1840.0,
        "capture_path": "captures/2026-04-16_sample_cap001.jpg",
        "event_state": "CLOSED",
    }
    h = compute_hash(ev)
    ev["evidence_hash"] = h
    ev["hash_fields"] = list(EVIDENCE_HASH_FIELDS)
    ev["hash_algorithm"] = "sha256"

    export: dict[str, Any] = {
        "ok": True,
        "available": True,
        "export_generated_ms": now,
        "event_id": ev["event_id"],
        "evidence_hash": h,
        "event_detail": {
            "ok": True,
            "available": True,
            "requested_event_id": ev["event_id"],
            "event_id": ev["event_id"],
            "event_object_v1": ev,
            "capture_binding_mode": "strict",
            "capture_binding_note": "event_id exact match (sample)",
            "capture_fallback_window_ms": 8000,
            "capture_match_mode": "strict",
            "capture_count": 1,
            "latest_capture": {
                "event_id": ev["event_id"],
                "timestamp_ms": ts_open + 3000,
                "file_path": ev["capture_path"],
                "url": "/captures/2026-04-16_sample_cap001.jpg",
                "reason": "VISION_LOCKED",
            },
            "captures": [],
        },
        "node_status_snapshot": {
            "node_id": "NODE_A1",
            "hunter_state": "IDLE",
            "vision_state": "VISION_IDLE",
            "rid_status": "RID_OK",
            "wl_status": "NOT_WL",
            "snapshot_ms": now,
        },
        "capture_match_mode": "strict",
        "suggested_file_name": f"event_evidence_A1-SAMPLE-0001_{now}.json",
        "export_saved": False,
        "export_file_path": "",
        "export_file_url": "",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[check] 样例已生成: {out_path}")
    print(f"  event_id={ev['event_id']}  hash={h[:16]}...")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="证据链一致性核对工具")
    parser.add_argument("--export-dir", type=Path,
                        default=Path("captures/event_exports"),
                        help="event_exports 目录（扫目录下所有 .json 文件）")
    parser.add_argument("--input", type=Path, default=None,
                        help="指定单个证据 JSON 文件（与 --export-dir 互斥，优先）")
    parser.add_argument("--output", type=Path, default=None,
                        help="核对结果输出文件（JSON，不指定则只打印）")
    parser.add_argument("--mock", action="store_true",
                        help="框架自测模式：用合成数据验证逻辑，无需真机文件")
    parser.add_argument("--generate-sample", type=Path, default=None,
                        metavar="OUTPUT_PATH",
                        help="生成一个带完整字段和正确 hash 的 mock 证据 JSON 样例")
    parser.add_argument("--verbose", action="store_true",
                        help="显示每个文件的详细字段信息")
    args = parser.parse_args()

    if args.mock:
        ok = run_mock_self_test()
        return 0 if ok else 1

    if args.generate_sample:
        out_path = resolve_path(args.generate_sample)
        _generate_sample(out_path)
        return 0

    # 确定待核对文件列表
    if args.input:
        files = [resolve_path(args.input)]
    else:
        export_dir = resolve_path(args.export_dir)
        if not export_dir.exists():
            print(f"[check] 目录不存在: {export_dir}")
            return 1
        files = sorted(export_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            print(f"[check] 目录下无 .json 文件: {export_dir}")
            return 1

    results: list[FileCheckResult] = []
    for path in files:
        r = _check_file(path)
        results.append(r)
        print_result(r, verbose=args.verbose)

    print_summary(results)

    if args.output:
        out = resolve_path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "records": [asdict(r) for r in results],
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[check] 结果已写入 {out}")

    all_passed = all(r.passed for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
