# ?????????????? API ??????????/??/?????????????????
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_FILE = Path(__file__).with_name("vision_dashboard.html")
MIN_REAL_EPOCH_MS = 946684800000  # 2000-01-01

# ---------------------------------------------------------------------------
# 证据链 hash（与 evidence_hash_证据链哈希.py 保持同步）
# ---------------------------------------------------------------------------
_EVIDENCE_HASH_FIELDS: tuple[str, ...] = (
    "event_id", "track_id", "risk_score", "rid_status", "wl_status",
    "reason_flags", "capture_path", "ts_open", "ts_close", "close_reason",
)
_EVIDENCE_HASH_EXCLUDED: frozenset[str] = frozenset({"evidence_hash", "hash_fields", "hash_algorithm"})


def _compute_evidence_hash(evidence: dict) -> str:
    """计算证据对象 SHA-256 hash（字段顺序与 Win 侧冻结保持一致）。"""
    payload: dict = {}
    for key in _EVIDENCE_HASH_FIELDS:
        if key in _EVIDENCE_HASH_EXCLUDED:
            continue
        payload[key] = evidence.get(key, None)
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _attach_evidence_hash(evidence: dict) -> dict:
    """向证据 dict 写入 evidence_hash / hash_fields / hash_algorithm（in-place）。"""
    evidence["evidence_hash"] = _compute_evidence_hash(evidence)
    evidence["hash_fields"] = list(_EVIDENCE_HASH_FIELDS)
    evidence["hash_algorithm"] = "sha256"
    return evidence
MOCK_IMAGE_URL = (
    "data:image/svg+xml;utf8,"
    + quote(
        "<svg xmlns='http://www.w3.org/2000/svg' width='960' height='540'>"
        "<rect width='100%' height='100%' fill='#1f1f1f'/>"
        "<rect x='250' y='140' width='460' height='260' rx='14' ry='14' fill='none' stroke='#ffb24a' stroke-width='4'/>"
        "<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='#f8f0e2' font-size='30'>MOCK CAPTURE</text>"
        "</svg>"
    )
)


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def to_record_url(file_path: Path, capture_dir: Path) -> str:
    try:
        relative = file_path.resolve().relative_to(capture_dir.resolve())
        return "/captures/" + "/".join(relative.parts)
    except ValueError:
        return "/captures/" + file_path.name


def to_static_url(file_path: Path, root_dir: Path, prefix: str) -> str:
    try:
        relative = file_path.resolve().relative_to(root_dir.resolve())
    except ValueError:
        return ""
    return prefix.rstrip("/") + "/" + "/".join(quote(part) for part in relative.parts)


def load_capture_records(capture_log_file: Path, capture_dir: Path) -> list[dict[str, object]]:
    # 抓拍记录来自 vision_bridge_视觉桥接.py 输出的 CSV。
    # 这里把它整理成网页和接口都能直接消费的对象列表。
    if not capture_log_file.exists():
        return []

    records: list[dict[str, object]] = []
    with capture_log_file.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            file_value = row.get("file_path", "")
            file_path = resolve_path(Path(file_value)) if file_value else capture_dir
            records.append(
                {
                    "timestamp_ms": int(row.get("timestamp_ms") or 0),
                    "frame_index": int(row.get("frame_index") or 0),
                    "vision_state": row.get("vision_state", ""),
                    "vision_locked": int(row.get("vision_locked") or 0),
                    "tracker_name": row.get("tracker_name", ""),
                    "event_id": row.get("event_id", ""),
                    "capture_reason": row.get("capture_reason", ""),
                    "file_path": str(file_path.as_posix()),
                    "image_url": to_record_url(file_path, capture_dir),
                    "bbox_x": int(row.get("bbox_x") or 0),
                    "bbox_y": int(row.get("bbox_y") or 0),
                    "bbox_w": int(row.get("bbox_w") or 0),
                    "bbox_h": int(row.get("bbox_h") or 0),
                    "center_x": int(row.get("center_x") or 0),
                    "center_y": int(row.get("center_y") or 0),
                }
            )

    records.sort(key=lambda item: int(item["timestamp_ms"]), reverse=True)
    return records


def load_json_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"ok": True, "available": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "available": False, "error": "invalid_json"}
    payload["ok"] = True
    payload["available"] = True
    return payload


def write_json_file(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    last_error: OSError | None = None
    for _ in range(10):
        try:
            temp_path.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        raise last_error


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def refresh_node_runtime_flags(payload: dict[str, object], offline_timeout_ms: int) -> dict[str, object]:
    normalized = dict(payload)
    now_ms = int(time.time() * 1000)
    last_update_ms = safe_int(normalized.get("last_update_ms", normalized.get("timestamp_ms", 0)), 0)
    stale_age_ms = max(0, now_ms - max(0, last_update_ms))
    available = bool(normalized.get("available", False))
    online = 1 if available and stale_age_ms <= max(0, offline_timeout_ms) else 0
    normalized["last_update_ms"] = last_update_ms
    normalized["stale_age_ms"] = stale_age_ms
    normalized["online"] = online
    normalized["center_checked_ms"] = now_ms
    normalized["center_offline_timeout_ms"] = max(0, offline_timeout_ms)
    return normalized


def normalize_event_record_time(record: dict[str, object], fallback_host_ms: int) -> dict[str, object]:
    normalized = dict(record)
    timestamp_ms = safe_int(normalized.get("timestamp_ms", 0))
    host_logged_ms = safe_int(normalized.get("host_logged_ms", normalized.get("display_time_ms", 0)))

    if host_logged_ms <= 0:
        if timestamp_ms >= MIN_REAL_EPOCH_MS:
            host_logged_ms = timestamp_ms
        else:
            host_logged_ms = max(0, fallback_host_ms)

    normalized["host_logged_ms"] = host_logged_ms
    normalized["display_time_ms"] = host_logged_ms
    normalized["device_timestamp_ms"] = timestamp_ms
    return normalized


def build_captures_payload(records: list[dict[str, object]], limit: int) -> dict[str, object]:
    latest = records[0] if records else None
    trimmed = records[:limit]
    event_ids = {
        str(record["event_id"])
        for record in records
        if str(record["event_id"]).strip() and str(record["event_id"]) != "NONE"
    }
    return {
        "ok": True,
        "count": len(records),
        "latest": latest,
        "records": trimmed,
        "event_count": len(event_ids),
        "last_timestamp_ms": latest["timestamp_ms"] if latest else 0,
    }


def build_node_events_payload(events_file: Path, limit: int) -> dict[str, object]:
    payload = load_json_file(events_file)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        records = []
    file_mtime_ms = int(events_file.stat().st_mtime * 1000) if events_file.exists() else int(time.time() * 1000)
    normalized_records = [
        normalize_event_record_time(item, file_mtime_ms)
        for item in records
        if isinstance(item, dict)
    ]
    trimmed = normalized_records[:limit]
    latest = trimmed[0] if trimmed else None
    return {
        "ok": True,
        "available": bool(trimmed),
        "count": len(normalized_records),
        "latest": latest,
        "records": trimmed,
    }


def build_node_brief_payload(
    node_label: str,
    status_file: Path,
    events_file: Path,
    event_limit: int = 20,
    offline_timeout_ms: int = 5000,
) -> dict[str, object]:
    status_payload = refresh_node_runtime_flags(load_json_file(status_file), offline_timeout_ms)
    events_payload = build_node_events_payload(events_file, event_limit)
    records = events_payload.get("records", []) if isinstance(events_payload, dict) else []
    if not isinstance(records, list):
        records = []
    latest_event = records[0] if records else {}
    node_id = str(
        status_payload.get(
            "node_id",
            latest_event.get("node_id", latest_event.get("source_node", node_label)),
        )
        or node_label
    ).strip() or node_label
    last_update_ms = safe_int(status_payload.get("last_update_ms", status_payload.get("timestamp_ms", 0)))
    return {
        "label": node_label,
        "available": bool(status_payload.get("available", False)),
        "online": safe_int(status_payload.get("online", 0)),
        "node_id": node_id,
        "source_node": str(latest_event.get("source_node", node_id) or node_id),
        "last_update_ms": last_update_ms,
        "stale_age_ms": safe_int(status_payload.get("stale_age_ms", 0)),
        "track_count": 1 if safe_int(status_payload.get("track_active", 0)) == 1 else 0,
        "events_count": 1 if safe_int(status_payload.get("event_active", 0)) == 1 else 0,
        "history_event_count": len(records),
        "main_state": str(status_payload.get("main_state", "UNKNOWN") or "UNKNOWN"),
        "risk_level": str(status_payload.get("risk_level", "NONE") or "NONE"),
        "last_event_id": str(status_payload.get("last_event_id", latest_event.get("event_id", "NONE")) or "NONE"),
        "last_reason": str(status_payload.get("last_reason", latest_event.get("reason", "NONE")) or "NONE"),
        "event_status": str(status_payload.get("event_status", latest_event.get("event_status", "NONE")) or "NONE"),
        "prev_node_id": str(status_payload.get("prev_node_id", latest_event.get("prev_node_id", "NONE")) or "NONE"),
        "handoff_from": str(status_payload.get("handoff_from", latest_event.get("handoff_from", "NONE")) or "NONE"),
        "handoff_to": str(status_payload.get("handoff_to", latest_event.get("handoff_to", "NONE")) or "NONE"),
        "continuity_hint": str(status_payload.get("continuity_hint", latest_event.get("continuity_hint", "SINGLE_NODE")) or "SINGLE_NODE"),
        "status_file": status_file.as_posix(),
        "events_file": events_file.as_posix(),
    }


def build_node_fleet_payload(
    node_specs: list[tuple[str, Path, Path]],
    offline_timeout_ms: int = 5000,
) -> dict[str, object]:
    nodes = [
        build_node_brief_payload(label, status_file, events_file, offline_timeout_ms=offline_timeout_ms)
        for label, status_file, events_file in node_specs
    ]
    online_count = sum(1 for item in nodes if safe_int(item.get("online", 0)) == 1)
    total_tracks = sum(safe_int(item.get("track_count", 0)) for item in nodes)
    total_events = sum(safe_int(item.get("events_count", 0)) for item in nodes)
    return {
        "ok": True,
        "available": bool(nodes),
        "count": len(nodes),
        "online_count": online_count,
        "total_tracks": total_tracks,
        "total_events": total_events,
        "nodes": nodes,
    }


def resolve_node_storage_targets(
    node_label_or_id: str,
    node_status_file: Path,
    node_status_file_a2: Path,
    node_events_file: Path,
    node_events_file_a2: Path,
) -> tuple[str, Path, Path]:
    normalized = str(node_label_or_id or "").strip().upper()
    if normalized == "A2":
        return "A2", node_status_file_a2, node_events_file_a2
    return "A1", node_status_file, node_events_file


def build_center_ingest_result(
    node_label: str,
    status_path: Path,
    events_path: Path,
    payload_type: str,
) -> dict[str, object]:
    return {
        "ok": True,
        "accepted": True,
        "node_label": node_label,
        "payload_type": payload_type,
        "status_file": status_path.as_posix(),
        "events_file": events_path.as_posix(),
        "received_ms": int(time.time() * 1000),
    }


def normalize_event_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.upper() == "NONE":
        return "NONE"
    return text


def normalize_capture_match_mode(value: object) -> str:
    text = str(value or "fallback").strip().lower()
    return "strict" if text == "strict" else "fallback"


def event_record_time_ms(record: dict[str, object]) -> int:
    return safe_int(
        record.get(
            "display_time_ms",
            record.get(
                "host_logged_ms",
                record.get("timestamp_ms", 0),
            ),
        ),
        0,
    )


def normalize_whitelist_status(record: dict[str, object]) -> str:
    status = str(
        record.get(
            "whitelist_status",
            record.get("wl_status", ""),
        )
        or ""
    ).strip().upper()
    if status:
        return status
    if safe_int(record.get("rid_whitelist_hit", 0), 0) == 1:
        return "WL_ALLOWED"
    return "WL_UNKNOWN"


def pick_capture_path(record: dict[str, object], captures: list[dict[str, object]]) -> str:
    raw_capture_path = str(record.get("capture_path", "") or "").strip()
    if raw_capture_path and raw_capture_path.upper() != "NONE":
        return raw_capture_path
    if captures:
        latest_capture = captures[0]
        if isinstance(latest_capture, dict):
            latest_path = str(latest_capture.get("file_path", "") or "").strip()
            if latest_path:
                return latest_path
    return "NONE"


def build_event_object_v1(
    event_record: dict[str, object] | None,
    captures: list[dict[str, object]],
) -> dict[str, object]:
    if not isinstance(event_record, dict):
        return {}
    event_id = normalize_event_id(event_record.get("event_id", "")) or "NONE"
    node_id = str(event_record.get("node_id", event_record.get("source_node", "NONE")) or "NONE").strip() or "NONE"
    track_id = safe_int(event_record.get("track_id", 0), 0)
    risk_score = round(safe_float(event_record.get("risk_score", 0.0), 0.0), 2)
    risk_level = str(event_record.get("risk_level", event_record.get("event_level", "NONE")) or "NONE").strip() or "NONE"
    hunter_state = str(event_record.get("hunter_state", "UNKNOWN") or "UNKNOWN").strip() or "UNKNOWN"
    rid_status = str(event_record.get("rid_status", "UNKNOWN") or "UNKNOWN").strip() or "UNKNOWN"
    whitelist_status = normalize_whitelist_status(event_record)
    vision_state = str(event_record.get("vision_state", "UNKNOWN") or "UNKNOWN").strip() or "UNKNOWN"
    trigger_flags = str(
        event_record.get(
            "trigger_flags",
            event_record.get("event_trigger_reasons", "NONE"),
        )
        or "NONE"
    ).strip() or "NONE"
    start_time = safe_int(
        event_record.get(
            "start_time_ms",
            event_record.get("current_event_start_time", event_record.get("timestamp_ms", 0)),
        ),
        0,
    )
    update_time = safe_int(
        event_record.get(
            "update_time_ms",
            event_record.get("display_time_ms", event_record.get("host_logged_ms", event_record.get("timestamp_ms", 0))),
        ),
        0,
    )
    x = safe_float(event_record.get("x_mm", event_record.get("x", 0.0)), 0.0)
    y = safe_float(event_record.get("y_mm", event_record.get("y", 0.0)), 0.0)
    capture_path = pick_capture_path(event_record, captures)
    event_state = str(event_record.get("event_state", event_record.get("event_status", "NONE")) or "NONE").strip() or "NONE"

    # 事件生命周期时间戳（与 Win 侧证据链字段对齐）
    ts_open = safe_int(
        event_record.get(
            "ts_open",
            event_record.get("start_time_ms", event_record.get("current_event_start_time", 0)),
        ),
        0,
    )
    ts_close = safe_int(event_record.get("ts_close", event_record.get("close_time_ms", 0)), 0)
    close_reason = str(event_record.get("close_reason", event_record.get("event_close_reason", "NONE")) or "NONE").strip() or "NONE"

    # 风险来源标志 + wl_status（用于证据 hash）
    reason_flags = str(event_record.get("reason_flags", trigger_flags) or "NONE").strip() or "NONE"
    wl_status = whitelist_status  # 对齐 evidence_hash 字段名

    return {
        "schema_version": "event_object_v1",
        "event_id": event_id,
        "node_id": node_id,
        "track_id": track_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "hunter_state": hunter_state,
        "rid_status": rid_status,
        "wl_status": wl_status,
        "whitelist_status": whitelist_status,
        "vision_state": vision_state,
        "trigger_flags": trigger_flags,
        "reason_flags": reason_flags,
        "start_time": start_time,
        "update_time": update_time,
        "ts_open": ts_open,
        "ts_close": ts_close,
        "close_reason": close_reason,
        "x": round(x, 2),
        "y": round(y, 2),
        "capture_path": capture_path,
        "event_state": event_state,
    }


def select_captures_for_event(
    captures: list[dict[str, object]],
    selected_event: dict[str, object] | None,
    selected_event_id: str,
    capture_limit: int,
    capture_fallback_window_ms: int,
    capture_match_mode: str,
) -> tuple[list[dict[str, object]], str, str]:
    limit = max(1, capture_limit)
    normalized_event_id = normalize_event_id(selected_event_id)
    match_mode = normalize_capture_match_mode(capture_match_mode)

    if normalized_event_id and normalized_event_id != "NONE":
        exact_matches = [
            item
            for item in captures
            if normalize_event_id(item.get("event_id", "")) == normalized_event_id
        ]
        if exact_matches:
            return exact_matches[:limit], "event_id_exact", "按 event_id 精确匹配到抓拍。"

    if match_mode == "strict":
        return [], "strict_no_capture", "严格模式：仅允许 event_id 精确匹配。"

    if not isinstance(selected_event, dict):
        return [], "no_capture", "事件对象不可用，无法匹配抓拍。"

    event_time = event_record_time_ms(selected_event)
    if event_time <= 0:
        return [], "no_capture", "事件时间不可用，无法执行时间窗口补链。"

    window_ms = max(0, safe_int(capture_fallback_window_ms, 0))
    if window_ms <= 0:
        return [], "no_capture", "未启用时间窗口补链。"

    fallback_candidates: list[tuple[int, dict[str, object]]] = []
    for item in captures:
        if not isinstance(item, dict):
            continue
        capture_event_id = normalize_event_id(item.get("event_id", ""))
        if capture_event_id and capture_event_id != "NONE":
            continue
        capture_ts = safe_int(item.get("timestamp_ms", 0), 0)
        if capture_ts <= 0:
            continue
        delta_ms = abs(capture_ts - event_time)
        if delta_ms <= window_ms:
            fallback_candidates.append((delta_ms, item))

    if not fallback_candidates:
        return [], "no_capture", "未命中精确抓拍，时间窗口补链也未找到候选。"

    fallback_candidates.sort(key=lambda pair: (pair[0], -safe_int(pair[1].get("timestamp_ms", 0), 0)))
    matched = [item for _, item in fallback_candidates[:limit]]
    return matched, "time_window_fallback_none_event", "未命中精确抓拍，使用时间窗口补链。"


def build_active_event_payload(active_event_file: Path) -> dict[str, object]:
    payload = load_json_file(active_event_file)
    event_id = normalize_event_id(payload.get("event_id", "")) if isinstance(payload, dict) else ""
    updated_ms = safe_int(payload.get("updated_ms", 0), 0) if isinstance(payload, dict) else 0
    source = str(payload.get("source", "manual") or "manual") if isinstance(payload, dict) else "manual"
    return {
        "ok": True,
        "available": bool(event_id and event_id != "NONE"),
        "event_id": event_id or "NONE",
        "updated_ms": updated_ms,
        "source": source,
    }


def write_active_event_payload(active_event_file: Path, event_id: str, source: str) -> dict[str, object]:
    normalized = normalize_event_id(event_id) or "NONE"
    payload = {
        "event_id": normalized,
        "updated_ms": int(time.time() * 1000),
        "source": source or "manual",
    }
    active_event_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = active_event_file.with_suffix(active_event_file.suffix + ".tmp")
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(active_event_file)
    return {
        "ok": True,
        "available": normalized != "NONE",
        "event_id": normalized,
        "updated_ms": payload["updated_ms"],
        "source": payload["source"],
    }


def write_event_export_payload(
    export_dir: Path,
    capture_dir: Path,
    file_name: str,
    payload: dict[str, object],
) -> tuple[bool, str, str, str]:
    # 导出证据对象时同时落盘，保证网页点击后本地也有留痕文件。
    safe_name = Path(str(file_name or "event_evidence.json")).name
    if not safe_name.lower().endswith(".json"):
        safe_name = f"{safe_name}.json"
    if not safe_name:
        safe_name = "event_evidence.json"

    export_dir.mkdir(parents=True, exist_ok=True)
    target = (export_dir / safe_name).resolve()
    try:
        target.relative_to(export_dir.resolve())
    except ValueError:
        return False, "", "", "invalid_export_path"

    temp_file = target.with_suffix(target.suffix + ".tmp")
    try:
        temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_file.replace(target)
    except OSError as error:
        return False, "", "", f"write_failed:{error}"

    export_url = ""
    try:
        relative = target.relative_to(capture_dir.resolve())
        export_url = "/captures/" + "/".join(relative.parts)
    except ValueError:
        export_url = ""

    return True, target.as_posix(), export_url, ""


def build_node_event_store_payload(event_store_file: Path, limit: int, event_id: str = "") -> dict[str, object]:
    payload = load_json_file(event_store_file)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        records = []
    file_mtime_ms = (
        int(event_store_file.stat().st_mtime * 1000)
        if event_store_file.exists()
        else int(time.time() * 1000)
    )
    records = [
        normalize_event_record_time(item, file_mtime_ms)
        for item in records
        if isinstance(item, dict)
    ]

    normalized_event_id = normalize_event_id(event_id)
    if normalized_event_id and normalized_event_id != "NONE":
        records = [item for item in records if normalize_event_id(item.get("event_id", "")) == normalized_event_id]

    trimmed = records[:limit]
    latest = trimmed[0] if trimmed else None
    return {
        "ok": True,
        "available": bool(trimmed),
        "count": len(records),
        "latest": latest,
        "records": trimmed,
        "event_id": normalized_event_id,
    }


def build_node_event_detail_payload(
    event_store_file: Path,
    node_events_file: Path,
    capture_log_file: Path,
    capture_dir: Path,
    event_id: str = "",
    capture_limit: int = 10,
    capture_fallback_window_ms: int = 8000,
    capture_match_mode: str = "fallback",
) -> dict[str, object]:
    store_payload = build_node_event_store_payload(event_store_file, 500)
    store_records = store_payload.get("records", []) if isinstance(store_payload, dict) else []
    if not isinstance(store_records, list):
        store_records = []

    node_events_payload = build_node_events_payload(node_events_file, 500)
    node_event_records = node_events_payload.get("records", []) if isinstance(node_events_payload, dict) else []
    if not isinstance(node_event_records, list):
        node_event_records = []

    # 详情查询优先使用实时 node_events，再回退到持久 event_store。
    # 这样可避免“表格有事件但详情不可点”的时间窗口问题。
    store_records = [item for item in node_event_records if isinstance(item, dict)] + [
        item for item in store_records if isinstance(item, dict)
    ]

    normalized_event_id = normalize_event_id(event_id)
    selected_event: dict[str, object] | None = None
    selected_event_id = ""
    if normalized_event_id and normalized_event_id != "NONE":
        for item in store_records:
            if not isinstance(item, dict):
                continue
            if normalize_event_id(item.get("event_id", "")) == normalized_event_id:
                selected_event = item
                selected_event_id = normalized_event_id
                break
    else:
        for item in store_records:
            if not isinstance(item, dict):
                continue
            candidate = normalize_event_id(item.get("event_id", ""))
            if candidate and candidate != "NONE":
                selected_event = item
                selected_event_id = candidate
                break
        if selected_event is None and store_records and isinstance(store_records[0], dict):
            selected_event = store_records[0]
            selected_event_id = normalize_event_id(selected_event.get("event_id", ""))

    captures = load_capture_records(capture_log_file, capture_dir)
    captures, capture_binding_mode, capture_binding_note = select_captures_for_event(
        captures=captures,
        selected_event=selected_event,
        selected_event_id=selected_event_id,
        capture_limit=capture_limit,
        capture_fallback_window_ms=capture_fallback_window_ms,
        capture_match_mode=capture_match_mode,
    )
    event_object_v1 = build_event_object_v1(selected_event, captures)

    return {
        "ok": True,
        "available": selected_event is not None,
        "requested_event_id": normalized_event_id,
        "event_id": selected_event_id or "NONE",
        "event": selected_event,
        "event_object_v1": event_object_v1,
        "capture_binding_mode": capture_binding_mode,
        "capture_binding_note": capture_binding_note,
        "capture_fallback_window_ms": max(0, safe_int(capture_fallback_window_ms, 0)),
        "capture_match_mode": normalize_capture_match_mode(capture_match_mode),
        "capture_count": len(captures),
        "latest_capture": captures[0] if captures else None,
        "captures": captures,
    }


def build_node_event_export_payload(
    event_store_file: Path,
    node_events_file: Path,
    capture_log_file: Path,
    capture_dir: Path,
    node_status_file: Path,
    event_export_dir: Path,
    event_id: str = "",
    capture_limit: int = 20,
    capture_fallback_window_ms: int = 8000,
    capture_match_mode: str = "fallback",
) -> dict[str, object]:
    detail = build_node_event_detail_payload(
        event_store_file=event_store_file,
        node_events_file=node_events_file,
        capture_log_file=capture_log_file,
        capture_dir=capture_dir,
        event_id=event_id,
        capture_limit=capture_limit,
        capture_fallback_window_ms=capture_fallback_window_ms,
        capture_match_mode=capture_match_mode,
    )
    node_status = load_json_file(node_status_file)
    export_generated_ms = int(time.time() * 1000)
    effective_event_id = normalize_event_id(detail.get("event_id", "NONE")) or "NONE"
    safe_event_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in effective_event_id)
    if not safe_event_id:
        safe_event_id = "NONE"

    # 自动计算证据链 hash（基于 event_object_v1 字段集）
    event_obj_v1 = detail.get("event_object_v1", {}) if isinstance(detail, dict) else {}
    evidence_hash = ""
    if isinstance(event_obj_v1, dict) and event_obj_v1.get("event_id", "NONE") not in ("", "NONE"):
        evidence_hash = _compute_evidence_hash(event_obj_v1)
        if isinstance(event_obj_v1, dict):
            event_obj_v1["evidence_hash"] = evidence_hash
            event_obj_v1["hash_fields"] = list(_EVIDENCE_HASH_FIELDS)
            event_obj_v1["hash_algorithm"] = "sha256"

    export_payload = {
        "ok": True,
        "available": bool(detail.get("available")),
        "export_generated_ms": export_generated_ms,
        "event_id": effective_event_id,
        "evidence_hash": evidence_hash,
        "event_detail": detail,
        "node_status_snapshot": node_status,
        "capture_match_mode": normalize_capture_match_mode(capture_match_mode),
        "suggested_file_name": f"event_evidence_{safe_event_id}_{export_generated_ms}.json",
    }
    export_saved = False
    export_file_path = ""
    export_file_url = ""
    export_file_error = ""
    if bool(export_payload.get("available")):
        export_saved, export_file_path, export_file_url, export_file_error = write_event_export_payload(
            export_dir=event_export_dir,
            capture_dir=capture_dir,
            file_name=str(export_payload["suggested_file_name"]),
            payload=export_payload,
        )
    export_payload["export_saved"] = export_saved
    export_payload["export_file_path"] = export_file_path
    export_payload["export_file_url"] = export_file_url
    if export_file_error:
        export_payload["export_file_error"] = export_file_error
    return export_payload


def build_node_event_exports_payload(
    event_export_dir: Path,
    capture_dir: Path,
    limit: int,
    event_id: str = "",
) -> dict[str, object]:
    normalized_event_id = normalize_event_id(event_id)
    files = sorted(
        [item for item in event_export_dir.glob("*.json") if item.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    records: list[dict[str, object]] = []
    for file_path in files:
        payload = load_json_file(file_path)
        if not isinstance(payload, dict):
            continue
        file_event_id = normalize_event_id(payload.get("event_id", ""))
        if normalized_event_id and normalized_event_id != "NONE" and file_event_id != normalized_event_id:
            continue

        detail = payload.get("event_detail", {}) if isinstance(payload.get("event_detail", {}), dict) else {}
        capture_count = safe_int(detail.get("capture_count", 0), 0)
        generated_ms = safe_int(payload.get("export_generated_ms", 0), 0)
        export_url = ""
        try:
            relative = file_path.resolve().relative_to(capture_dir.resolve())
            export_url = "/captures/" + "/".join(relative.parts)
        except ValueError:
            export_url = ""
        records.append(
            {
                "file_name": file_path.name,
                "event_id": file_event_id or "NONE",
                "export_generated_ms": generated_ms,
                "capture_count": capture_count,
                "file_path": file_path.as_posix(),
                "file_url": export_url,
            }
        )
        if len(records) >= max(1, limit):
            break

    return {
        "ok": True,
        "available": bool(records),
        "count": len(records),
        "event_id": normalized_event_id,
        "records": records,
        "latest": records[0] if records else None,
    }


def build_node_event_export_detail_payload(
    event_export_dir: Path,
    capture_dir: Path,
    file_name: str,
) -> dict[str, object]:
    safe_name = Path(str(file_name or "")).name
    if not safe_name:
        return {"ok": True, "available": False, "error": "missing_file_name"}

    target = (event_export_dir / safe_name).resolve()
    try:
        target.relative_to(event_export_dir.resolve())
    except ValueError:
        return {"ok": True, "available": False, "error": "invalid_file_name", "file_name": safe_name}

    if not target.exists() or not target.is_file():
        return {"ok": True, "available": False, "error": "file_not_found", "file_name": safe_name}

    payload = load_json_file(target)
    if not isinstance(payload, dict):
        return {"ok": True, "available": False, "error": "invalid_export_payload", "file_name": safe_name}

    event_detail = payload.get("event_detail", {})
    if not isinstance(event_detail, dict):
        event_detail = {}

    file_url = ""
    try:
        relative = target.relative_to(capture_dir.resolve())
        file_url = "/captures/" + "/".join(relative.parts)
    except ValueError:
        file_url = ""

    return {
        "ok": True,
        "available": bool(event_detail),
        "file_name": safe_name,
        "file_path": target.as_posix(),
        "file_url": file_url,
        "event_id": normalize_event_id(payload.get("event_id", "")) or "NONE",
        "event_detail": event_detail,
        "export": payload,
    }


def build_test_session_payload(test_session_file: Path) -> dict[str, object]:
    payload = load_json_file(test_session_file)
    if not isinstance(payload, dict):
        return {"ok": False, "available": False}
    return payload


def build_test_result_payload(test_result_file: Path, test_results_file: Path, session_log_dir: Path) -> dict[str, object]:
    payload = load_json_file(test_result_file)
    if not isinstance(payload, dict):
        payload = {"ok": False, "available": False}

    result_label = str(payload.get("result_label", "NONE") or "NONE").upper()
    if bool(payload.get("available")) and result_label != "NONE":
        payload.setdefault("result_source", "formal_test_result")
        return payload

    history_payload = build_test_results_payload(test_results_file, session_log_dir, 1)
    history_records = history_payload.get("records", []) if isinstance(history_payload, dict) else []
    if isinstance(history_records, list) and history_records and isinstance(history_records[0], dict):
        latest_record = dict(history_records[0])
        latest_record["ok"] = True
        latest_record["available"] = True
        latest_record.setdefault("result_source", "history_file")
        return latest_record

    payload.setdefault("result_source", "none")
    return payload


def normalize_suite_check_item(record: dict[str, object]) -> dict[str, object]:
    return {
        "name": str(record.get("name", "NONE") or "NONE"),
        "ok": bool(record.get("ok", False)),
        "reason": str(record.get("reason", "NONE") or "NONE"),
        "command": str(record.get("command", "NONE") or "NONE"),
        "note": str(record.get("note", "NONE") or "NONE"),
        "line": str(record.get("line", "--") or "--"),
        "ts_ms": safe_int(record.get("ts_ms", 0)),
    }


def build_test_result_record_from_session_log(path: Path) -> dict[str, object] | None:
    first_record: dict[str, object] | None = None
    last_record: dict[str, object] | None = None
    latest_test_result: dict[str, object] | None = None
    suite_started_payload: dict[str, object] | None = None
    suite_finished_payload: dict[str, object] | None = None
    suite_checks: list[dict[str, object]] = []

    try:
        with path.open("r", encoding="utf-8") as fp:
            for raw_line in fp:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if first_record is None:
                    first_record = payload
                last_record = payload
                event_type = str(payload.get("event_type", ""))
                raw_payload = payload.get("payload", {})
                if not isinstance(raw_payload, dict):
                    raw_payload = {}
                if event_type == "test_result":
                    latest_test_result = raw_payload
                elif event_type == "suite_started":
                    suite_started_payload = raw_payload
                elif event_type == "suite_finished":
                    suite_finished_payload = raw_payload
                elif event_type == "suite_check":
                    suite_checks.append(
                        normalize_suite_check_item(
                            {
                                "name": raw_payload.get("name", "NONE"),
                                "ok": raw_payload.get("ok", False),
                                "reason": raw_payload.get("reason", "NONE"),
                                "command": raw_payload.get("command", "NONE"),
                                "note": raw_payload.get("note", "NONE"),
                                "line": raw_payload.get("line", "--"),
                                "ts_ms": payload.get("ts_ms", 0),
                            }
                        )
                    )
    except OSError:
        return None

    if first_record is None or last_record is None:
        return None

    scenario_name = str(first_record.get("scenario_name", "") or "")
    started_ms = safe_int(first_record.get("started_ms", 0))
    finished_ms = safe_int(last_record.get("ts_ms", 0), started_ms)
    rid_mode = str((suite_started_payload or {}).get("rid_mode", "UNCHANGED") or "UNCHANGED")

    if latest_test_result is not None:
        record = dict(latest_test_result)
        record.setdefault("ok", True)
        record["available"] = True
        record.setdefault("scenario_name", scenario_name)
        record.setdefault("rid_mode", rid_mode)
        record.setdefault("started_ms", started_ms)
        record.setdefault("finished_ms", finished_ms)
        record.setdefault("updated_ms", finished_ms)
        record.setdefault("session_file_name", path.name)
        record.setdefault("result_source", "timeline_test_result")
        return record

    if suite_finished_payload is None:
        return None

    passed = safe_int(suite_finished_payload.get("passed", 0))
    failed = safe_int(suite_finished_payload.get("failed", 0))
    suite_name = str(suite_finished_payload.get("suite_name", scenario_name) or scenario_name)
    failed_checks = [item for item in suite_checks if not bool(item.get("ok", False))]
    passed_checks = [item for item in suite_checks if bool(item.get("ok", False))]
    total_checks = len(suite_checks) or (passed + failed)
    result_label = "PASS" if failed == 0 else "FAIL"

    return {
        "ok": True,
        "available": True,
        "result_label": result_label,
        "scenario_name": scenario_name,
        "scenario_description": "Recovered from session_logs fallback",
        "rid_mode": rid_mode,
        "suite_name": suite_name,
        "suite_step_total": total_checks,
        "suite_passed": passed,
        "suite_failed": failed,
        "suite_failed_checks": failed_checks,
        "suite_report": {
            "suite_name": suite_name,
            "passed": passed,
            "failed": failed,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
        },
        "final_main_state": "UNKNOWN",
        "final_risk_level": "NONE",
        "final_event_id": "NONE",
        "had_event": 0,
        "had_handover": 0,
        "track_active_delta": 0,
        "track_lost_delta": 0,
        "event_opened_delta": 0,
        "event_closed_delta": 0,
        "handover_queued_delta": 0,
        "handover_emitted_delta": 0,
        "handover_ignored_delta": 0,
        "max_risk_score": 0.0,
        "predictor_kp": 0.0,
        "predictor_kd": 0.0,
        "heartbeat_ms": 0,
        "event_report_ms": 0,
        "sim_hold_ms": 0,
        "debug_enabled": 0,
        "quiet_enabled": 0,
        "uplink_enabled": 0,
        "final_gimbal_state": "UNKNOWN",
        "final_risk_score": 0.0,
        "started_ms": started_ms,
        "finished_ms": finished_ms,
        "updated_ms": finished_ms,
        "session_file_name": path.name,
        "result_source": "session_log_fallback",
    }


def test_result_record_key(record: dict[str, object]) -> tuple[str, int]:
    return (str(record.get("scenario_name", "") or ""), safe_int(record.get("started_ms", 0)))


def merge_test_result_records(
    primary_records: list[dict[str, object]],
    fallback_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged: dict[tuple[str, int], dict[str, object]] = {}

    for record in fallback_records:
        merged[test_result_record_key(record)] = record

    for record in primary_records:
        merged[test_result_record_key(record)] = record

    return sorted(
        merged.values(),
        key=lambda item: (
            safe_int(item.get("updated_ms", 0)),
            safe_int(item.get("finished_ms", 0)),
            safe_int(item.get("started_ms", 0)),
        ),
        reverse=True,
    )


def build_test_results_payload(test_results_file: Path, session_log_dir: Path, limit: int) -> dict[str, object]:
    payload = load_json_file(test_results_file)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        records = []
    normalized_records = []
    for item in records:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized.setdefault("result_source", "history_file")
        normalized_records.append(normalized)
    fallback_records = [
        record
        for record in (build_test_result_record_from_session_log(path) for path in load_session_log_files(session_log_dir))
        if record is not None
    ]
    merged_records = merge_test_result_records(normalized_records, fallback_records)
    trimmed = merged_records[:limit]
    latest = trimmed[0] if trimmed else None
    return {
        "ok": True,
        "available": bool(trimmed),
        "count": len(merged_records),
        "latest": latest,
        "records": trimmed,
    }


def build_file_asset(path: Path, root_dir: Path, prefix: str, label: str) -> dict[str, object]:
    available = path.exists() and path.is_file()
    return {
        "label": label,
        "available": available,
        "file_name": path.name,
        "file_path": path.as_posix(),
        "file_url": to_static_url(path, root_dir, prefix) if available else "",
    }


def build_delivery_assets_payload(
    capture_dir: Path,
    event_export_dir: Path,
    session_log_dir: Path,
    docs_dir: Path,
) -> dict[str, object]:
    false_alarm_file = capture_dir / "false_alarm_result.json"
    e2e_file = capture_dir / "e2e_latency_result.json"
    acceptance_snapshot_file = capture_dir / "latest_acceptance_snapshot.json"
    bundle_readiness_file = capture_dir / "latest_delivery_bundle_readiness_report.json"
    evidence_closure_file = capture_dir / "latest_single_node_evidence_closure_report.json"
    auto_acceptance_file = capture_dir / "latest_411_acceptance_auto_report.json"

    false_alarm_payload = load_json_file(false_alarm_file)
    e2e_payload = load_json_file(e2e_file)
    acceptance_snapshot = load_json_file(acceptance_snapshot_file)
    bundle_readiness = load_json_file(bundle_readiness_file)
    evidence_closure = load_json_file(evidence_closure_file)
    auto_acceptance = load_json_file(auto_acceptance_file)
    latest_exports = build_node_event_exports_payload(event_export_dir, capture_dir, 1, "")
    latest_export = latest_exports.get("latest") if isinstance(latest_exports, dict) else None
    latest_export_available = isinstance(latest_export, dict)

    demo_checklist = docs_dir / "2026-04-21_demo_checklist_w3（第三周演示检查单）.md"
    recovery_checklist = docs_dir / "2026-04-21_recovery_checklist_w3（第三周现场恢复检查单）.md"
    freeze_manifest = docs_dir / "2026-04-21_freeze_manifest_w3（第三周冻结清单）.md"
    stability_record = docs_dir / "2026-04-21_day5_win_stability_record（Day5 Win稳定性记录）.md"

    docs_assets = [
        build_file_asset(demo_checklist, docs_dir, "/docs", "演示检查单"),
        build_file_asset(recovery_checklist, docs_dir, "/docs", "现场恢复检查单"),
        build_file_asset(freeze_manifest, docs_dir, "/docs", "冻结清单"),
        build_file_asset(stability_record, docs_dir, "/docs", "Day5 稳定性记录"),
    ]

    latest_session_logs = load_session_log_files(session_log_dir)

    return {
        "ok": True,
        "available": True,
        "updated_ms": int(time.time() * 1000),
        "summary": {
            "deliverable_ready": bool(acceptance_snapshot.get("deliverable_ready", False)),
            "suite_ok": bool(acceptance_snapshot.get("suite_ok", False)),
            "contract_ok": bool(acceptance_snapshot.get("contract_ok", False)),
            "evidence_ready": bool(acceptance_snapshot.get("evidence_ready", False)),
            "bundle_result": str(bundle_readiness.get("result", "NONE") or "NONE"),
            "bundle_failure_count": safe_int(bundle_readiness.get("failure_count", 0)),
            "bundle_warning_count": safe_int(bundle_readiness.get("warning_count", 0)),
            "auto_acceptance_result": str(auto_acceptance.get("result", "NONE") or "NONE"),
            "auto_acceptance_passed": safe_int(auto_acceptance.get("passed", 0)),
            "auto_acceptance_failed": safe_int(auto_acceptance.get("failed", 0)),
            "latest_export_available": latest_export_available,
            "latest_session_count": len(latest_session_logs),
        },
        "metrics": {
            "false_alarm": {
                "available": bool(false_alarm_payload.get("available", False)),
                "result_label": str(false_alarm_payload.get("result_label", "NONE") or "NONE"),
                "false_alarm_count": safe_int(false_alarm_payload.get("false_alarm_count", 0)),
                "false_alarm_rate": safe_float(false_alarm_payload.get("false_alarm_rate", 0.0)),
                "scenario": str(false_alarm_payload.get("scenario", "NONE") or "NONE"),
                "file_path": false_alarm_file.as_posix(),
                "file_url": to_static_url(false_alarm_file, capture_dir, "/captures") if false_alarm_file.exists() else "",
            },
            "e2e_latency": {
                "available": bool(e2e_payload.get("available", True)) if e2e_file.exists() else False,
                "result_label": str(e2e_payload.get("result_label", "NONE") or "NONE"),
                "latency_ms_mean": safe_float(e2e_payload.get("latency_ms_mean", 0.0)),
                "latency_ms_p95": safe_float(e2e_payload.get("latency_ms_p95", 0.0)),
                "sample_count": safe_int(e2e_payload.get("sample_count", 0)),
                "file_path": e2e_file.as_posix(),
                "file_url": to_static_url(e2e_file, capture_dir, "/captures") if e2e_file.exists() else "",
            },
            "evidence_closure": {
                "available": bool(evidence_closure.get("available", True)) if evidence_closure_file.exists() else False,
                "result": str(evidence_closure.get("result", "NONE") or "NONE"),
                "latest_event_id": str(evidence_closure.get("latest_event_id", "NONE") or "NONE"),
                "node_id": str(evidence_closure.get("node_id", "NONE") or "NONE"),
                "bound_capture_count": safe_int((evidence_closure.get("counts", {}) or {}).get("bound_capture_count", 0)),
                "warning_count": safe_int(evidence_closure.get("warning_count", 0)),
                "file_path": evidence_closure_file.as_posix(),
                "file_url": to_static_url(evidence_closure_file, capture_dir, "/captures") if evidence_closure_file.exists() else "",
            },
            "acceptance": {
                "available": bool(acceptance_snapshot.get("available", False)) if acceptance_snapshot_file.exists() else False,
                "deliverable_ready": bool(acceptance_snapshot.get("deliverable_ready", False)),
                "suite_ok": bool(acceptance_snapshot.get("suite_ok", False)),
                "contract_ok": bool(acceptance_snapshot.get("contract_ok", False)),
                "evidence_ready": bool(acceptance_snapshot.get("evidence_ready", False)),
                "file_path": acceptance_snapshot_file.as_posix(),
                "file_url": to_static_url(acceptance_snapshot_file, capture_dir, "/captures") if acceptance_snapshot_file.exists() else "",
            },
        },
        "assets": {
            "docs": docs_assets,
            "latest_export": latest_export if latest_export_available else None,
            "latest_export_count": safe_int(latest_exports.get("count", 0)) if isinstance(latest_exports, dict) else 0,
            "latest_session_file": latest_session_logs[0].name if latest_session_logs else "",
        },
    }


def load_session_log_files(session_log_dir: Path) -> list[Path]:
    if not session_log_dir.exists():
        return []

    return sorted(
        [path for path in session_log_dir.glob("*.jsonl") if path.is_file()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def summarize_session_log_file(path: Path) -> dict[str, object]:
    first_record: dict[str, object] | None = None
    last_record: dict[str, object] | None = None
    count = 0
    has_capture = False
    has_node_event = False
    has_test_result = False
    latest_test_result: dict[str, object] | None = None
    latest_suite_summary: dict[str, object] | None = None
    try:
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if first_record is None:
                    first_record = payload
                last_record = payload
                count += 1
                event_type = str(payload.get("event_type", ""))
                if event_type == "capture_saved":
                    has_capture = True
                if event_type == "node_event":
                    has_node_event = True
                if event_type == "test_result":
                    has_test_result = True
                    raw_payload = payload.get("payload", {})
                    if isinstance(raw_payload, dict):
                        latest_test_result = raw_payload
                if event_type == "suite_finished":
                    raw_payload = payload.get("payload", {})
                    if isinstance(raw_payload, dict):
                        latest_suite_summary = raw_payload
    except OSError:
        return {
            "file_name": path.name,
            "scenario_name": "",
            "started_ms": 0,
            "last_ts_ms": 0,
            "event_count": 0,
            "has_capture": False,
            "has_node_event": False,
            "has_test_result": False,
            "result_label": "NONE",
            "final_risk_level": "NONE",
            "suite_name": "",
            "suite_passed": 0,
            "suite_failed": 0,
            "suite_result": "NONE",
        }

    suite_name = str((latest_suite_summary or {}).get("suite_name", ""))
    suite_passed = int((latest_suite_summary or {}).get("passed", 0) or 0)
    suite_failed = int((latest_suite_summary or {}).get("failed", 0) or 0)
    suite_result = "NONE"
    if latest_suite_summary is not None:
        suite_result = "PASS" if suite_failed == 0 else "FAIL"
    result_label = str((latest_test_result or {}).get("result_label", "NONE") or "NONE")
    if result_label == "NONE" and suite_result != "NONE":
        result_label = suite_result
    result_source = "none"
    if latest_test_result is not None:
        result_source = str((latest_test_result or {}).get("result_source", "test_result") or "test_result")
    elif suite_result != "NONE":
        result_source = "session_suite_fallback"

    return {
        "file_name": path.name,
        "scenario_name": (first_record or {}).get("scenario_name", ""),
        "started_ms": int((first_record or {}).get("started_ms", 0) or 0),
        "last_ts_ms": int((last_record or {}).get("ts_ms", 0) or 0),
        "event_count": count,
        "has_capture": has_capture,
        "has_node_event": has_node_event,
        "has_test_result": has_test_result,
        "result_label": result_label,
        "final_risk_level": (latest_test_result or {}).get("final_risk_level", "NONE"),
        "result_source": result_source,
        "suite_name": suite_name,
        "suite_passed": suite_passed,
        "suite_failed": suite_failed,
        "suite_result": suite_result,
    }


def load_session_timeline_records(session_log_dir: Path, limit: int, session_name: str = "") -> tuple[list[dict[str, object]], str]:
    files = load_session_log_files(session_log_dir)
    if not files:
        return [], ""

    latest_file = files[0]
    if session_name:
        candidate = session_log_dir / session_name
        if candidate.exists() and candidate.is_file():
            latest_file = candidate

    records: list[dict[str, object]] = []
    try:
        with latest_file.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    records.append(payload)
    except OSError:
        return [], latest_file.name

    records = records[-max(1, limit):]
    return records, latest_file.name


def build_session_timeline_payload(session_log_dir: Path, limit: int, session_name: str = "") -> dict[str, object]:
    records, latest_file = load_session_timeline_records(session_log_dir, limit, session_name)
    return {
        "ok": True,
        "available": bool(records),
        "count": len(records),
        "latest_file": latest_file,
        "records": records,
    }


def build_session_timeline_sessions_payload(session_log_dir: Path, limit: int) -> dict[str, object]:
    files = load_session_log_files(session_log_dir)
    trimmed = files[: max(1, limit)]
    sessions = [summarize_session_log_file(path) for path in trimmed]
    return {
        "ok": True,
        "available": bool(sessions),
        "count": len(sessions),
        "latest_file": sessions[0]["file_name"] if sessions else "",
        "sessions": sessions,
    }


def load_session_capture_records(
    session_log_dir: Path,
    capture_dir: Path,
    limit: int,
    session_name: str = "",
) -> tuple[list[dict[str, object]], str]:
    records, latest_file = load_session_timeline_records(session_log_dir, 10000, session_name)
    capture_records: list[dict[str, object]] = []

    for record in records:
        event_type = str(record.get("event_type", ""))
        if event_type != "capture_saved":
            continue

        payload = record.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        file_value = str(payload.get("file_path", "")).strip()
        file_path = resolve_path(Path(file_value)) if file_value else capture_dir
        capture_records.append(
            {
                "timestamp_ms": int(record.get("ts_ms", 0) or 0),
                "frame_index": int(payload.get("frame_index", 0) or 0),
                "vision_state": str(payload.get("vision_state", "")),
                "vision_locked": 1,
                "tracker_name": "",
                "event_id": str(payload.get("event_id", "")),
                "capture_reason": str(payload.get("capture_reason", "")),
                "file_path": str(file_path.as_posix()),
                "image_url": to_record_url(file_path, capture_dir),
                "scenario_name": str(record.get("scenario_name", "")),
            }
        )

    capture_records.sort(key=lambda item: int(item["timestamp_ms"]), reverse=True)
    trimmed = capture_records[: max(1, limit)]
    return trimmed, latest_file


def build_session_captures_payload(
    session_log_dir: Path,
    capture_dir: Path,
    limit: int,
    session_name: str = "",
) -> dict[str, object]:
    records, latest_file = load_session_capture_records(session_log_dir, capture_dir, limit, session_name)
    latest = records[0] if records else None
    return {
        "ok": True,
        "available": bool(records),
        "count": len(records),
        "latest_file": latest_file,
        "latest": latest,
        "records": records,
    }


def is_mock_mode(query: dict[str, list[str]]) -> bool:
    mode_values = query.get("mode", [])
    if not mode_values:
        return False
    mode = str(mode_values[0] or "").strip().lower()
    return mode in {"mock", "simulate", "sim", "demo"}


def compute_vision_contribution(
    vision_state: str,
    wl_status: str,
    risk_score: float | None = None,
) -> dict[str, object]:
    """根据视觉状态和白名单状态推导视觉对风险分的贡献。

    规则镜像自 Win 侧 HunterAction 的约定（Day 2 A2 任务）：
      VISION_LOCKED + WL_ALLOWED  → 降风险（负贡献），合作目标已锁定
      VISION_LOCKED + 非 WL_ALLOWED → 中性（0），非合作目标不降风险
      VISION_LOST                  → 小幅惩罚（正贡献），目标丢失场景
      VISION_SEARCHING             → 微小惩罚，搜索中
      其他 / IDLE / NONE           → 无贡献

    score_delta 正数 = 加风险，负数 = 降风险，None = 未计算。
    """
    v = str(vision_state or "NONE").strip().upper()
    wl = str(wl_status or "WL_UNKNOWN").strip().upper()

    if v in ("VISION_LOCKED", "LOCKED"):
        if wl == "WL_ALLOWED":
            return {
                "vision_state": v,
                "score_delta": -8.0,
                "note": "合作目标锁定，降低风险",
                "wl_status": wl,
            }
        else:
            return {
                "vision_state": v,
                "score_delta": 0.0,
                "note": f"非合作目标锁定（{wl}），不降风险",
                "wl_status": wl,
            }
    if v in ("VISION_LOST", "LOST"):
        return {
            "vision_state": v,
            "score_delta": 4.0,
            "note": "目标丢失，小幅加风险",
            "wl_status": wl,
        }
    if v in ("VISION_SEARCHING", "SEARCHING"):
        return {
            "vision_state": v,
            "score_delta": 1.0,
            "note": "视觉搜索中",
            "wl_status": wl,
        }
    return {
        "vision_state": v,
        "score_delta": None,
        "note": "视觉无贡献",
        "wl_status": wl,
    }


def build_mock_bundle() -> dict[str, object]:
    now_ms = int(time.time() * 1000)
    scenario_name = "standard_acceptance"
    session_file = "mock_standard_acceptance_session.jsonl"
    session_started_ms = now_ms - 95_000
    track_x_mm = 320.0
    track_y_mm = 1800.0
    event_id = f"A1-{(now_ms // 10) % 10000000000:010d}-MOCK"
    suite_checks = [
        ("idle_baseline", "BRIEF", True, "PASS", "复位后先确认系统回到空闲基线。"),
        ("event_open_brief", "BRIEF", True, "PASS", "确认模拟目标进入活跃、确认、事件开启状态。"),
        ("event_open_risk", "RISK,STATUS", True, "PASS", "风险状态允许继续向上升级。"),
        ("event_open_status", "EVENT,STATUS", True, "PASS", "事件对象处于 OPEN。"),
        ("risk_downgrade_event_status", "EVENT,STATUS", True, "PASS", "RID 恢复 OK 后事件关闭。"),
        ("risk_downgrade_last_event", "LASTEVENT", True, "PASS", "最近事件保留 RISK_DOWNGRADE。"),
        ("track_lost_last_event", "LASTEVENT", True, "PASS", "清轨后最近事件出现 TRACK_LOST。"),
    ]

    timeline_records: list[dict[str, object]] = [
        {
            "ts_ms": session_started_ms,
            "source": "test",
            "event_type": "suite_started",
            "scenario_name": scenario_name,
            "started_ms": session_started_ms,
            "payload": {
                "suite_name": scenario_name,
                "rid_mode": "MISSING",
                "x_mm": track_x_mm,
                "y_mm": track_y_mm,
                "confirm_repeat": 6,
            },
        }
    ]

    for index, (check_name, command, ok, reason, note) in enumerate(suite_checks):
        ts_ms = session_started_ms + 2000 + index * 900
        timeline_records.append(
            {
                "ts_ms": ts_ms,
                "source": "test",
                "event_type": "suite_check",
                "scenario_name": scenario_name,
                "started_ms": session_started_ms,
                "payload": {
                    "name": check_name,
                    "ok": ok,
                    "reason": reason,
                    "command": command,
                    "note": note,
                    "line": f"{command},mock={check_name},result={'PASS' if ok else 'FAIL'}",
                },
            }
        )

    capture_ts = session_started_ms + 11_200
    timeline_records.extend(
        [
            {
                "ts_ms": session_started_ms + 10_000,
                "source": "node",
                "event_type": "node_status_changed",
                "scenario_name": scenario_name,
                "started_ms": session_started_ms,
                "payload": {
                    "current": {
                        "main_state": "HIGH_RISK",
                        "risk_level": "HIGH_RISK",
                    }
                },
            },
            {
                "ts_ms": session_started_ms + 10_400,
                "source": "node",
                "event_type": "node_event",
                "scenario_name": scenario_name,
                "started_ms": session_started_ms,
                "payload": {
                    "reason": "EVENT_OPENED",
                    "event_id": event_id,
                },
            },
            {
                "ts_ms": session_started_ms + 10_800,
                "source": "vision",
                "event_type": "vision_status_changed",
                "scenario_name": scenario_name,
                "started_ms": session_started_ms,
                "payload": {
                    "vision_state": "VISION_LOCKED",
                    "vision_locked": 1,
                },
            },
            {
                "ts_ms": capture_ts,
                "source": "vision",
                "event_type": "capture_saved",
                "scenario_name": scenario_name,
                "started_ms": session_started_ms,
                "payload": {
                    "capture_reason": "ALERT",
                    "event_id": event_id,
                    "vision_state": "VISION_LOCKED",
                    "frame_index": 428,
                    "file_path": "mock_capture.png",
                },
            },
            {
                "ts_ms": session_started_ms + 12_000,
                "source": "test",
                "event_type": "test_result",
                "scenario_name": scenario_name,
                "started_ms": session_started_ms,
                "payload": {
                    "result_label": "PASS",
                    "final_risk_level": "NONE",
                    "result_source": "formal_test_result",
                },
            },
            {
                "ts_ms": session_started_ms + 12_300,
                "source": "test",
                "event_type": "suite_finished",
                "scenario_name": scenario_name,
                "started_ms": session_started_ms,
                "payload": {
                    "suite_name": scenario_name,
                    "passed": 7,
                    "failed": 0,
                },
            },
        ]
    )

    capture_record = {
        "timestamp_ms": capture_ts,
        "frame_index": 428,
        "vision_state": "VISION_LOCKED",
        "vision_locked": 1,
        "tracker_name": "CSRT",
        "event_id": event_id,
        "capture_reason": "ALERT",
        "file_path": "mock_capture.png",
        "image_url": MOCK_IMAGE_URL,
        "bbox_x": 258,
        "bbox_y": 132,
        "bbox_w": 420,
        "bbox_h": 250,
        "center_x": 468,
        "center_y": 257,
        "scenario_name": scenario_name,
    }

    suite_failed_checks: list[dict[str, object]] = []
    suite_report = {
        "suite_name": scenario_name,
        "passed": 7,
        "failed": 0,
        "total_checks": 7,
        "passed_checks": [
            {
                "name": name,
                "ok": ok,
                "reason": reason,
                "command": command,
                "note": note,
                "line": f"{command},mock={name},result={'PASS' if ok else 'FAIL'}",
                "ts_ms": session_started_ms + 2000 + idx * 900,
            }
            for idx, (name, command, ok, reason, note) in enumerate(suite_checks)
        ],
        "failed_checks": suite_failed_checks,
    }

    test_result_latest = {
        "ok": True,
        "available": True,
        "result_label": "PASS",
        "scenario_name": scenario_name,
        "scenario_description": "Mock pipeline: dashboard can run without hardware",
        "rid_mode": "MISSING",
        "suite_name": scenario_name,
        "suite_step_total": 7,
        "suite_passed": 7,
        "suite_failed": 0,
        "suite_failed_checks": suite_failed_checks,
        "suite_report": suite_report,
        "final_main_state": "TRACKING",
        "final_risk_level": "NONE",
        "final_event_id": event_id,
        "had_event": 1,
        "had_handover": 0,
        "track_active_delta": 1,
        "track_lost_delta": 1,
        "event_opened_delta": 1,
        "event_closed_delta": 1,
        "handover_queued_delta": 0,
        "handover_emitted_delta": 0,
        "handover_ignored_delta": 0,
        "max_risk_score": 66.0,
        "predictor_kp": 0.24,
        "predictor_kd": 0.08,
        "heartbeat_ms": 3000,
        "event_report_ms": 250,
        "sim_hold_ms": 0,
        "debug_enabled": 0,
        "quiet_enabled": 0,
        "uplink_enabled": 1,
        "final_gimbal_state": "TRACKING",
        "final_risk_score": 0.0,
        "started_ms": session_started_ms,
        "finished_ms": session_started_ms + 12_300,
        "updated_ms": now_ms,
        "session_file_name": session_file,
        "result_source": "formal_test_result",
    }

    fallback_record = {
        "ok": True,
        "available": True,
        "result_label": "FAIL",
        "scenario_name": "validate_47",
        "scenario_description": "Mock fallback sample",
        "rid_mode": "MISSING",
        "suite_name": "validate_47",
        "suite_step_total": 3,
        "suite_passed": 2,
        "suite_failed": 1,
        "suite_failed_checks": [
            {
                "name": "risk_downgrade_last_event",
                "ok": False,
                "reason": "event_close_reason expected RISK_DOWNGRADE but got NONE",
                "command": "LASTEVENT",
                "note": "最近事件未保留",
                "line": "LASTEVENT,NONE",
                "ts_ms": now_ms - 320_000,
            }
        ],
        "suite_report": {
            "suite_name": "validate_47",
            "passed": 2,
            "failed": 1,
            "total_checks": 3,
            "passed_checks": [],
            "failed_checks": [],
        },
        "final_main_state": "SUSPICIOUS",
        "final_risk_level": "HIGH_RISK",
        "final_event_id": "A1-0000000001-MOCK",
        "had_event": 0,
        "had_handover": 0,
        "track_active_delta": 0,
        "track_lost_delta": 0,
        "event_opened_delta": 0,
        "event_closed_delta": 0,
        "handover_queued_delta": 0,
        "handover_emitted_delta": 0,
        "handover_ignored_delta": 0,
        "max_risk_score": 66.0,
        "predictor_kp": 0.0,
        "predictor_kd": 0.0,
        "heartbeat_ms": 0,
        "event_report_ms": 0,
        "sim_hold_ms": 0,
        "debug_enabled": 0,
        "quiet_enabled": 0,
        "uplink_enabled": 0,
        "final_gimbal_state": "TRACKING",
        "final_risk_score": 66.0,
        "started_ms": now_ms - 325_000,
        "finished_ms": now_ms - 320_000,
        "updated_ms": now_ms - 320_000,
        "session_file_name": "mock_validate_47_session.jsonl",
        "result_source": "session_log_fallback",
    }

    test_results_records = [test_result_latest, fallback_record]
    test_results_records.sort(key=lambda item: safe_int(item.get("updated_ms", 0)), reverse=True)

    return {
        "status": {
            "ok": True,
            "available": True,
            "timestamp_ms": now_ms - 350,
            "vision_state": "VISION_LOCKED",
            "vision_locked": 1,
            "tracker_name": "CSRT",
            "frame_index": 428,
            "bbox_x": 258,
            "bbox_y": 132,
            "bbox_w": 420,
            "bbox_h": 250,
            "center_x": 468,
            "center_y": 257,
            "last_capture_reason": "ALERT",
            "data_source_mode": "mock",
        },
        "node_status": {
            "ok": True,
            "available": True,
            "online": 1,
            "stale_age_ms": 180,
            "node_id": "A1",
            "node_zone": "ZONE_NORTH",
            "main_state": "TRACKING",
            "hunter_state": "RID_MATCHED",
            "gimbal_state": "TRACKING",
            "rid_status": "MATCHED",
            "risk_level": "NORMAL",
            "risk_score": 17.0,
            "consistency_status": "OK",
            "consistency_warning_count": 0,
            "consistency_warnings": [],
            "consistency_expected_main_state": "TRACKING",
            "consistency_main_state_match": 1,
            "consistency_checked_ms": now_ms - 150,
            "event_status": "CLOSED",
            "event_active": 0,
            "event_id": "NONE",
            "last_event_id": event_id,
            "last_reason": "EVENT_CLOSED",
            "event_reason": "EVENT_CLOSED",
            "event_level": "INFO",
            "handover_last_result": "NONE",
            "handover_last_target": "NONE",
            "track_id": 1,
            "track_active": 1,
            "track_confirmed": 1,
            "x_mm": track_x_mm,
            "y_mm": track_y_mm,
            "track_active_count": 3,
            "track_confirmed_count": 3,
            "track_lost_count": 1,
            "event_opened_count": 2,
            "event_closed_count": 2,
            "handover_queued_count": 0,
            "handover_emitted_count": 0,
            "handover_ignored_count": 0,
            "last_message_type": "EVENT,STATUS",
            "last_update_ms": now_ms - 180,
            "predictor_kp": 0.24,
            "predictor_kd": 0.08,
            "heartbeat_ms": 3000,
            "event_report_ms": 250,
            "sim_hold_ms": 0,
            "monitor_baud": 115200,
            "radar_baud": 115200,
            "test_mode_enabled": 0,
            "servo_enabled": 1,
            "servo_attached": 1,
            "safe_mode_enabled": 0,
            "diag_running": 0,
            "debug_enabled": 0,
            "quiet_enabled": 0,
            "uplink_enabled": 1,
            "idle_ready": 1,
            "data_source_mode": "mock",
            "vision_state": "VISION_LOCKED",
            "vision_contribution": compute_vision_contribution(
                vision_state="VISION_LOCKED",
                wl_status="WL_ALLOWED",
                risk_score=17.0,
            ),
        },
        # A2 mock 节点（离线状态，用于多节点卡片框架验证）
        "node_a2_status": {
            "ok": True,
            "available": True,
            "online": 0,
            "stale_age_ms": 9800,
            "node_id": "A2",
            "node_zone": "ZONE_SOUTH",
            "main_state": "IDLE",
            "hunter_state": "IDLE",
            "gimbal_state": "IDLE",
            "rid_status": "RID_UNKNOWN",
            "wl_status": "WL_UNKNOWN",
            "risk_level": "NONE",
            "risk_score": 0.0,
            "event_status": "NONE",
            "event_active": 0,
            "event_id": "NONE",
            "last_event_id": "NONE",
            "track_active_count": 0,
            "track_confirmed_count": 0,
            "event_opened_count": 0,
            "event_closed_count": 0,
            "last_update_ms": now_ms - 9800,
            "data_source_mode": "mock",
            "vision_state": "VISION_IDLE",
            "vision_contribution": compute_vision_contribution(
                vision_state="VISION_IDLE",
                wl_status="WL_UNKNOWN",
                risk_score=0.0,
            ),
        },
        "node_events": {
            "ok": True,
            "available": True,
            "count": 2,
            "latest": {
                "timestamp_ms": now_ms - 1200,
                "source_type": "UPLINK",
                "event_id": event_id,
                "reason": "EVENT_CLOSED",
                "event_level": "INFO",
                "event_status": "CLOSED",
                "track_id": 1,
                "risk_score": 17.0,
                "handover_to": "NONE",
            },
            "records": [
                {
                    "timestamp_ms": now_ms - 1200,
                    "source_type": "UPLINK",
                    "event_id": event_id,
                    "reason": "EVENT_CLOSED",
                    "event_level": "INFO",
                    "event_status": "CLOSED",
                    "track_id": 1,
                    "risk_score": 17.0,
                    "handover_to": "NONE",
                },
                {
                    "timestamp_ms": now_ms - 4800,
                    "source_type": "UPLINK",
                    "event_id": event_id,
                    "reason": "EVENT_OPENED",
                    "event_level": "CRITICAL",
                    "event_status": "OPEN",
                    "track_id": 1,
                    "risk_score": 66.0,
                    "handover_to": "NONE",
                },
            ],
        },
        "node_event_store": {
            "ok": True,
            "available": True,
            "count": 2,
            "updated_ms": now_ms - 1000,
            "latest": {
                "timestamp_ms": now_ms - 1200,
                "host_logged_ms": now_ms - 1200,
                "node_id": "A1",
                "zone": "ZONE_NORTH",
                "source_type": "UPLINK",
                "event_id": event_id,
                "reason": "EVENT_CLOSED",
                "event_level": "INFO",
                "event_status": "CLOSED",
                "event_close_reason": "RISK_DOWNGRADE",
                "track_id": 1,
                "risk_score": 17.0,
                "risk_level": "NORMAL",
                "rid_status": "MATCHED",
                "x_mm": track_x_mm,
                "y_mm": track_y_mm,
                "source_node": "A1",
            },
            "records": [
                {
                    "timestamp_ms": now_ms - 1200,
                    "host_logged_ms": now_ms - 1200,
                    "node_id": "A1",
                    "zone": "ZONE_NORTH",
                    "source_type": "UPLINK",
                    "event_id": event_id,
                    "reason": "EVENT_CLOSED",
                    "event_level": "INFO",
                    "event_status": "CLOSED",
                    "event_close_reason": "RISK_DOWNGRADE",
                    "track_id": 1,
                    "risk_score": 17.0,
                    "risk_level": "NORMAL",
                    "rid_status": "MATCHED",
                    "x_mm": track_x_mm,
                    "y_mm": track_y_mm,
                    "source_node": "A1",
                },
                {
                    "timestamp_ms": now_ms - 4800,
                    "host_logged_ms": now_ms - 4800,
                    "node_id": "A1",
                    "zone": "ZONE_NORTH",
                    "source_type": "UPLINK",
                    "event_id": event_id,
                    "reason": "EVENT_OPENED",
                    "event_level": "CRITICAL",
                    "event_status": "OPEN",
                    "track_id": 1,
                    "risk_score": 66.0,
                    "risk_level": "HIGH_RISK",
                    "rid_status": "MISSING",
                    "x_mm": track_x_mm,
                    "y_mm": track_y_mm,
                    "source_node": "A1",
                },
            ],
        },
        "test_session": {
            "ok": True,
            "available": True,
            "status": "DONE",
            "scenario_name": scenario_name,
            "suite_name": scenario_name,
            "scenario_index": 1,
            "scenario_total": 1,
            "rid_mode": "MISSING",
            "point_index": 6,
            "point_total": 6,
            "suite_step_index": 7,
            "suite_step_total": 7,
            "suite_step": "track_lost_last_event",
            "points_sent": 6,
            "suite_passed": 7,
            "suite_failed": 0,
            "current_x_mm": track_x_mm,
            "current_y_mm": track_y_mm,
            "started_ms": session_started_ms,
            "finished_ms": session_started_ms + 12_300,
            "suite_report": suite_report,
            "data_source_mode": "mock",
        },
        "test_result": test_result_latest,
        "test_results": {
            "ok": True,
            "available": True,
            "count": len(test_results_records),
            "latest": test_results_records[0],
            "records": test_results_records,
            "data_source_mode": "mock",
        },
        "captures": {
            "ok": True,
            "count": 1,
            "latest": capture_record,
            "records": [capture_record],
            "event_count": 1,
            "last_timestamp_ms": capture_record["timestamp_ms"],
            "data_source_mode": "mock",
        },
        "session_timeline": {
            "ok": True,
            "available": True,
            "count": len(timeline_records),
            "latest_file": session_file,
            "records": timeline_records,
            "data_source_mode": "mock",
        },
        "session_timeline_sessions": {
            "ok": True,
            "available": True,
            "count": 2,
            "latest_file": session_file,
            "sessions": [
                {
                    "file_name": session_file,
                    "scenario_name": scenario_name,
                    "started_ms": session_started_ms,
                    "last_ts_ms": session_started_ms + 12_300,
                    "event_count": len(timeline_records),
                    "has_capture": True,
                    "has_node_event": True,
                    "has_test_result": True,
                    "result_label": "PASS",
                    "final_risk_level": "NONE",
                    "result_source": "formal_test_result",
                    "suite_name": scenario_name,
                    "suite_passed": 7,
                    "suite_failed": 0,
                    "suite_result": "PASS",
                },
                {
                    "file_name": "mock_validate_47_session.jsonl",
                    "scenario_name": "validate_47",
                    "started_ms": now_ms - 325_000,
                    "last_ts_ms": now_ms - 320_000,
                    "event_count": 5,
                    "has_capture": False,
                    "has_node_event": False,
                    "has_test_result": False,
                    "result_label": "FAIL",
                    "final_risk_level": "HIGH_RISK",
                    "result_source": "session_suite_fallback",
                    "suite_name": "validate_47",
                    "suite_passed": 2,
                    "suite_failed": 1,
                    "suite_result": "FAIL",
                },
            ],
            "data_source_mode": "mock",
        },
        "session_captures": {
            "ok": True,
            "available": True,
            "count": 1,
            "latest_file": session_file,
            "latest": capture_record,
            "records": [capture_record],
            "data_source_mode": "mock",
        },
}


def build_mock_node_event_detail_payload(mock_bundle: dict[str, object], event_id: str = "") -> dict[str, object]:
    store_payload = mock_bundle.get("node_event_store", mock_bundle.get("node_events", {}))
    captures_payload = mock_bundle.get("captures", {})

    store_records = store_payload.get("records", []) if isinstance(store_payload, dict) else []
    if not isinstance(store_records, list):
        store_records = []
    capture_records = captures_payload.get("records", []) if isinstance(captures_payload, dict) else []
    if not isinstance(capture_records, list):
        capture_records = []

    normalized_event_id = normalize_event_id(event_id)
    selected_event = None
    selected_event_id = ""
    if normalized_event_id and normalized_event_id != "NONE":
        for item in store_records:
            if not isinstance(item, dict):
                continue
            if normalize_event_id(item.get("event_id", "")) == normalized_event_id:
                selected_event = item
                selected_event_id = normalized_event_id
                break
    elif store_records and isinstance(store_records[0], dict):
        selected_event = store_records[0]
        selected_event_id = normalize_event_id(selected_event.get("event_id", ""))

    if selected_event_id and selected_event_id != "NONE":
        capture_records = [
            item for item in capture_records if normalize_event_id(item.get("event_id", "")) == selected_event_id
        ]
        capture_binding_mode = "event_id_exact"
        capture_binding_note = "按 event_id 精确匹配到抓拍（mock）。"
    else:
        capture_records = []
        capture_binding_mode = "no_capture"
        capture_binding_note = "mock 数据未命中事件抓拍。"

    return {
        "ok": True,
        "available": selected_event is not None,
        "requested_event_id": normalized_event_id,
        "event_id": selected_event_id or "NONE",
        "event": selected_event,
        "capture_binding_mode": capture_binding_mode,
        "capture_binding_note": capture_binding_note,
        "capture_fallback_window_ms": 8000,
        "capture_match_mode": "fallback",
        "capture_count": len(capture_records),
        "latest_capture": capture_records[0] if capture_records else None,
        "captures": capture_records,
        "data_source_mode": "mock",
    }


def build_mock_node_event_export_payload(mock_bundle: dict[str, object], event_id: str = "") -> dict[str, object]:
    detail = build_mock_node_event_detail_payload(mock_bundle, event_id)
    export_generated_ms = int(time.time() * 1000)
    effective_event_id = normalize_event_id(detail.get("event_id", "NONE")) or "NONE"
    safe_event_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in effective_event_id)
    if not safe_event_id:
        safe_event_id = "NONE"
    return {
        "ok": True,
        "available": bool(detail.get("available")),
        "export_generated_ms": export_generated_ms,
        "event_id": effective_event_id,
        "event_detail": detail,
        "node_status_snapshot": mock_bundle.get("node_status", {"ok": True, "available": False}),
        "capture_match_mode": "fallback",
        "suggested_file_name": f"event_evidence_{safe_event_id}_{export_generated_ms}.json",
        "export_saved": False,
        "export_file_path": "",
        "export_file_url": "",
        "data_source_mode": "mock",
    }


def create_handler(
    dashboard_file: Path,
    capture_dir: Path,
    docs_dir: Path,
    capture_log_file: Path,
    status_file: Path,
    active_event_file: Path,
    node_status_file: Path,
    node_status_file_a2: Path,
    node_events_file: Path,
    node_events_file_a2: Path,
    node_event_store_file: Path,
    test_session_file: Path,
    test_result_file: Path,
    test_results_file: Path,
    session_log_dir: Path,
    event_export_dir: Path,
    default_limit: int,
    capture_fallback_window_ms: int,
    node_offline_timeout_ms: int,
) -> type[BaseHTTPRequestHandler]:
    class VisionDashboardHandler(BaseHTTPRequestHandler):
        server_version = "FlytotalVisionWeb/1.2"

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)

            if parsed.path not in {"/api/ingest/node-status", "/api/ingest/node-events"}:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return

            content_length = safe_int(self.headers.get("Content-Length", "0"), 0)
            if content_length <= 0:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing request body")
                return

            try:
                raw_body = self.rfile.read(content_length)
                payload = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
                return

            if not isinstance(payload, dict):
                self.send_error(HTTPStatus.BAD_REQUEST, "JSON body must be an object")
                return

            node_hint = str(
                payload.get(
                    "node_label",
                    payload.get("node_id", payload.get("source_node", "A1")),
                )
                or "A1"
            ).strip().upper() or "A1"
            node_label, target_status_file, target_events_file = resolve_node_storage_targets(
                node_hint,
                node_status_file,
                node_status_file_a2,
                node_events_file,
                node_events_file_a2,
            )

            if parsed.path == "/api/ingest/node-status":
                payload["ok"] = True
                payload["available"] = True
                payload["center_received_ms"] = int(time.time() * 1000)
                payload["node_label"] = node_label
                write_json_file(target_status_file, payload)
                self.send_json(
                    build_center_ingest_result(node_label, target_status_file, target_events_file, "node_status")
                )
                return

            payload["ok"] = True
            payload["available"] = bool(payload.get("available", False))
            payload["center_received_ms"] = int(time.time() * 1000)
            payload["node_label"] = node_label
            write_json_file(target_events_file, payload)
            self.send_json(
                build_center_ingest_result(node_label, target_status_file, target_events_file, "node_events")
            )

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            mock_mode = is_mock_mode(query)
            mock_bundle = build_mock_bundle() if mock_mode else None

            if parsed.path in ("/", "/dashboard", "/vision_dashboard.html"):
                self.serve_file(dashboard_file, "text/html; charset=utf-8")
                return
            if parsed.path == "/api/health":
                self.send_json(
                    {
                        "ok": True,
                        "service": "vision_web_server",
                        "mode": "mock" if mock_mode else "live",
                    }
                )
                return
            if parsed.path == "/api/data-source":
                self.send_json(
                    {
                        "ok": True,
                        "mode": "mock" if mock_mode else "live",
                        "label": "模拟链路" if mock_mode else "真实链路",
                    }
                )
                return
            if parsed.path == "/api/active-event":
                event_id = str(query.get("event_id", [""])[0]).strip()
                clear_flag = str(query.get("clear", [""])[0]).strip().lower()
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = dict(
                        mock_bundle.get(
                            "active_event",
                            {
                                "ok": True,
                                "available": bool(event_id),
                                "event_id": normalize_event_id(event_id) or "NONE",
                                "updated_ms": int(time.time() * 1000),
                                "source": "mock",
                            },
                        )
                    )
                    self.send_json(payload)
                    return
                if event_id:
                    self.send_json(write_active_event_payload(active_event_file, event_id, "dashboard"))
                    return
                if clear_flag in {"1", "true", "yes", "on"}:
                    self.send_json(write_active_event_payload(active_event_file, "NONE", "dashboard_clear"))
                    return
                self.send_json(build_active_event_payload(active_event_file))
                return
            if parsed.path == "/api/status":
                if mock_mode and isinstance(mock_bundle, dict):
                    self.send_json(mock_bundle.get("status", {"ok": True, "available": False}))
                    return
                self.send_json(load_json_file(status_file))
                return
            if parsed.path == "/api/nodes":
                # 返回所有节点状态列表，供多节点卡片渲染使用。
                # mock 模式：A1（在线）+ A2（离线）；真实模式：仅 A1。
                if mock_mode and isinstance(mock_bundle, dict):
                    a1 = mock_bundle.get("node_status", {"ok": True, "available": False})
                    a2 = mock_bundle.get("node_a2_status", {"ok": True, "available": False, "node_id": "A2", "online": 0})
                    self.send_json({"ok": True, "nodes": [a1, a2]})
                    return
                node_payload = load_json_file(node_status_file)
                vision_payload = load_json_file(status_file)
                v_state = str(vision_payload.get("vision_state", "NONE") or "NONE").strip().upper() or "NONE"
                wl = str(node_payload.get("wl_status", node_payload.get("whitelist_status", "WL_UNKNOWN")) or "WL_UNKNOWN").strip().upper() or "WL_UNKNOWN"
                node_payload["vision_state"] = v_state
                node_payload["vision_contribution"] = compute_vision_contribution(v_state, wl)
                self.send_json({"ok": True, "nodes": [node_payload]})
                return

            if parsed.path == "/api/node-status":
                if mock_mode and isinstance(mock_bundle, dict):
                    self.send_json(mock_bundle.get("node_status", {"ok": True, "available": False}))
                    return
                node_payload = refresh_node_runtime_flags(load_json_file(node_status_file), node_offline_timeout_ms)
                # 从 vision bridge 的 status 文件读取当前视觉状态，注入视觉贡献字段
                # （供网页风险区显示；score_delta 由 compute_vision_contribution 计算）。
                vision_payload = load_json_file(status_file)
                v_state = str(vision_payload.get("vision_state", "NONE") or "NONE").strip().upper() or "NONE"
                wl = str(
                    node_payload.get("wl_status",
                        node_payload.get("whitelist_status", "WL_UNKNOWN"))
                    or "WL_UNKNOWN"
                ).strip().upper() or "WL_UNKNOWN"
                node_payload["vision_state"] = v_state
                node_payload["vision_contribution"] = compute_vision_contribution(v_state, wl)
                self.send_json(node_payload)
                return
            if parsed.path == "/api/node-fleet-status":
                if mock_mode and isinstance(mock_bundle, dict):
                    a1_status = dict(mock_bundle.get("node_status", {"ok": True, "available": False}))
                    a2_status = dict(a1_status)
                    a2_status.update(
                        {
                            "node_id": "A2",
                            "node_zone": "ZONE_SOUTH",
                            "main_state": "DETECTING",
                            "risk_level": "SUSPICIOUS",
                            "risk_score": 43.0,
                            "track_active": 1,
                            "track_confirmed": 0,
                            "event_active": 1,
                            "event_id": "A2-0000000002-MOCK",
                            "last_event_id": "A2-0000000002-MOCK",
                            "last_reason": "EVENT_OPENED",
                            "event_status": "OPEN",
                            "source_node": "A2",
                            "continuity_hint": "HANDOFF_PENDING",
                            "prev_node_id": "A1",
                            "handoff_from": "A1",
                            "handoff_to": "A2",
                        }
                    )
                    a2_events = {
                        "ok": True,
                        "available": True,
                        "count": 1,
                        "latest": {
                            "event_id": "A2-0000000002-MOCK",
                            "reason": "EVENT_OPENED",
                            "event_status": "OPEN",
                            "source_node": "A2",
                            "prev_node_id": "A1",
                            "handoff_from": "A1",
                            "handoff_to": "A2",
                            "continuity_hint": "HANDOFF_PENDING",
                        },
                        "records": [
                            {
                                "event_id": "A2-0000000002-MOCK",
                                "reason": "EVENT_OPENED",
                                "event_status": "OPEN",
                                "source_node": "A2",
                                "prev_node_id": "A1",
                                "handoff_from": "A1",
                                "handoff_to": "A2",
                                "continuity_hint": "HANDOFF_PENDING",
                            }
                        ],
                    }
                    a1_latest = ((mock_bundle.get("node_events", {}) or {}).get("latest", {}) if isinstance(mock_bundle.get("node_events", {}), dict) else {})
                    a1_node = {
                        "label": "A1",
                        "available": bool(a1_status.get("available", False)),
                        "online": safe_int(a1_status.get("online", 0)),
                        "node_id": str(a1_status.get("node_id", "A1") or "A1"),
                        "source_node": str(a1_latest.get("source_node", a1_status.get("node_id", "A1")) or "A1"),
                        "last_update_ms": safe_int(a1_status.get("last_update_ms", 0)),
                        "stale_age_ms": safe_int(a1_status.get("stale_age_ms", 0)),
                        "track_count": 1 if safe_int(a1_status.get("track_active", 0)) == 1 else 0,
                        "events_count": 1 if safe_int(a1_status.get("event_active", 0)) == 1 else 0,
                        "history_event_count": safe_int(((mock_bundle.get("node_events", {}) or {}).get("count", 0)), 0),
                        "main_state": str(a1_status.get("main_state", "UNKNOWN") or "UNKNOWN"),
                        "risk_level": str(a1_status.get("risk_level", "NONE") or "NONE"),
                        "last_event_id": str(a1_status.get("last_event_id", "NONE") or "NONE"),
                        "last_reason": str(a1_status.get("last_reason", "NONE") or "NONE"),
                        "event_status": str(a1_status.get("event_status", "NONE") or "NONE"),
                        "prev_node_id": "NONE",
                        "handoff_from": "NONE",
                        "handoff_to": "NONE",
                        "continuity_hint": "SINGLE_NODE",
                    }
                    a2_node = {
                        "label": "A2",
                        "available": True,
                        "online": 1,
                        "node_id": "A2",
                        "source_node": "A2",
                        "last_update_ms": safe_int(a2_status.get("last_update_ms", 0)),
                        "stale_age_ms": safe_int(a2_status.get("stale_age_ms", 0)),
                        "track_count": 1,
                        "events_count": 1,
                        "history_event_count": 1,
                        "main_state": "DETECTING",
                        "risk_level": "SUSPICIOUS",
                        "last_event_id": "A2-0000000002-MOCK",
                        "last_reason": "EVENT_OPENED",
                        "event_status": "OPEN",
                        "prev_node_id": "A1",
                        "handoff_from": "A1",
                        "handoff_to": "A2",
                        "continuity_hint": "HANDOFF_PENDING",
                    }
                    self.send_json(
                        {
                            "ok": True,
                            "available": True,
                            "count": 2,
                            "online_count": 2,
                            "total_tracks": 2,
                            "total_events": 2,
                            "nodes": [a1_node, a2_node],
                            "data_source_mode": "mock",
                        }
                    )
                    return
                self.send_json(
                    build_node_fleet_payload(
                        [
                            ("A1", node_status_file, node_events_file),
                            ("A2", node_status_file_a2, node_events_file_a2),
                        ],
                        offline_timeout_ms=node_offline_timeout_ms,
                    )
                )
                return
            if parsed.path == "/api/node-events":
                limit = default_limit
                if "limit" in query:
                    try:
                        limit = max(1, min(100, int(query["limit"][0])))
                    except ValueError:
                        limit = default_limit
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = dict(mock_bundle.get("node_events", {"ok": True, "available": False}))
                    records = payload.get("records", [])
                    if isinstance(records, list):
                        payload["records"] = records[:limit]
                        payload["count"] = len(records)
                        payload["latest"] = payload["records"][0] if payload["records"] else None
                    self.send_json(payload)
                    return
                self.send_json(build_node_events_payload(node_events_file, limit))
                return
            if parsed.path == "/api/node-event-store":
                limit = default_limit
                if "limit" in query:
                    try:
                        limit = max(1, min(500, int(query["limit"][0])))
                    except ValueError:
                        limit = default_limit
                event_id = str(query.get("event_id", [""])[0]).strip()
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = dict(
                        mock_bundle.get(
                            "node_event_store",
                            mock_bundle.get("node_events", {"ok": True, "available": False}),
                        )
                    )
                    records = payload.get("records", [])
                    if isinstance(records, list):
                        if event_id and normalize_event_id(event_id) != "NONE":
                            records = [
                                item
                                for item in records
                                if isinstance(item, dict)
                                and normalize_event_id(item.get("event_id", "")) == normalize_event_id(event_id)
                            ]
                        payload["records"] = records[:limit]
                        payload["count"] = len(records)
                        payload["latest"] = payload["records"][0] if payload["records"] else None
                    self.send_json(payload)
                    return
                self.send_json(build_node_event_store_payload(node_event_store_file, limit, event_id))
                return
            if parsed.path == "/api/node-event-detail":
                event_id = str(query.get("event_id", [""])[0]).strip()
                capture_match_mode = normalize_capture_match_mode(query.get("capture_match_mode", ["fallback"])[0])
                if mock_mode and isinstance(mock_bundle, dict):
                    self.send_json(build_mock_node_event_detail_payload(mock_bundle, event_id))
                    return
                self.send_json(
                    build_node_event_detail_payload(
                        node_event_store_file,
                        node_events_file,
                        capture_log_file,
                        capture_dir,
                        event_id,
                        capture_limit=max(1, min(50, default_limit)),
                        capture_fallback_window_ms=capture_fallback_window_ms,
                        capture_match_mode=capture_match_mode,
                    )
                )
                return
            if parsed.path == "/api/node-event-export":
                event_id = str(query.get("event_id", [""])[0]).strip()
                capture_match_mode = normalize_capture_match_mode(query.get("capture_match_mode", ["fallback"])[0])
                if mock_mode and isinstance(mock_bundle, dict):
                    self.send_json(build_mock_node_event_export_payload(mock_bundle, event_id))
                    return
                self.send_json(
                    build_node_event_export_payload(
                        node_event_store_file,
                        node_events_file,
                        capture_log_file,
                        capture_dir,
                        node_status_file,
                        event_export_dir,
                        event_id,
                        capture_limit=max(1, min(50, default_limit)),
                        capture_fallback_window_ms=capture_fallback_window_ms,
                        capture_match_mode=capture_match_mode,
                    )
                )
                return
            if parsed.path == "/api/node-event-exports":
                limit = default_limit
                if "limit" in query:
                    try:
                        limit = max(1, min(100, int(query["limit"][0])))
                    except ValueError:
                        limit = default_limit
                event_id = str(query.get("event_id", [""])[0]).strip()
                if mock_mode and isinstance(mock_bundle, dict):
                    self.send_json(
                        {
                            "ok": True,
                            "available": False,
                            "count": 0,
                            "event_id": normalize_event_id(event_id),
                            "records": [],
                            "latest": None,
                            "data_source_mode": "mock",
                        }
                    )
                    return
                self.send_json(build_node_event_exports_payload(event_export_dir, capture_dir, limit, event_id))
                return
            if parsed.path == "/api/node-event-export-detail":
                file_name = str(query.get("file_name", [""])[0]).strip()
                if mock_mode and isinstance(mock_bundle, dict):
                    self.send_json(
                        {
                            "ok": True,
                            "available": False,
                            "error": "mock_export_detail_not_available",
                            "file_name": file_name,
                            "data_source_mode": "mock",
                        }
                    )
                    return
                self.send_json(build_node_event_export_detail_payload(event_export_dir, capture_dir, file_name))
                return
            if parsed.path == "/api/test-session":
                if mock_mode and isinstance(mock_bundle, dict):
                    self.send_json(mock_bundle.get("test_session", {"ok": True, "available": False}))
                    return
                self.send_json(build_test_session_payload(test_session_file))
                return
            if parsed.path == "/api/test-result":
                if mock_mode and isinstance(mock_bundle, dict):
                    self.send_json(mock_bundle.get("test_result", {"ok": True, "available": False}))
                    return
                self.send_json(build_test_result_payload(test_result_file, test_results_file, session_log_dir))
                return
            if parsed.path == "/api/test-results":
                limit = default_limit
                if "limit" in query:
                    try:
                        limit = max(1, min(100, int(query["limit"][0])))
                    except ValueError:
                        limit = default_limit
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = dict(mock_bundle.get("test_results", {"ok": True, "available": False}))
                    records = payload.get("records", [])
                    if isinstance(records, list):
                        payload["records"] = records[:limit]
                        payload["count"] = len(records)
                        payload["latest"] = payload["records"][0] if payload["records"] else None
                    self.send_json(payload)
                    return
                self.send_json(build_test_results_payload(test_results_file, session_log_dir, limit))
                return
            if parsed.path == "/api/delivery-assets":
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = build_delivery_assets_payload(capture_dir, event_export_dir, session_log_dir, docs_dir)
                    payload["data_source_mode"] = "mock"
                    self.send_json(payload)
                    return
                self.send_json(build_delivery_assets_payload(capture_dir, event_export_dir, session_log_dir, docs_dir))
                return
            if parsed.path == "/api/session-timeline":
                limit = default_limit
                session_name = ""
                if "limit" in query:
                    try:
                        limit = max(1, min(200, int(query["limit"][0])))
                    except ValueError:
                        limit = default_limit
                if "session" in query:
                    session_name = str(query["session"][0]).strip()
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = dict(mock_bundle.get("session_timeline", {"ok": True, "available": False}))
                    records = payload.get("records", [])
                    if isinstance(records, list):
                        payload["records"] = records[-max(1, limit) :]
                        payload["count"] = len(records)
                    payload["latest_file"] = session_name or payload.get("latest_file", "")
                    self.send_json(payload)
                    return
                self.send_json(build_session_timeline_payload(session_log_dir, limit, session_name))
                return
            if parsed.path == "/api/session-timeline-sessions":
                limit = default_limit
                if "limit" in query:
                    try:
                        limit = max(1, min(50, int(query["limit"][0])))
                    except ValueError:
                        limit = default_limit
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = dict(mock_bundle.get("session_timeline_sessions", {"ok": True, "available": False}))
                    sessions = payload.get("sessions", [])
                    if isinstance(sessions, list):
                        payload["sessions"] = sessions[: max(1, limit)]
                        payload["count"] = len(payload["sessions"])
                        payload["latest_file"] = payload["sessions"][0]["file_name"] if payload["sessions"] else ""
                    self.send_json(payload)
                    return
                self.send_json(build_session_timeline_sessions_payload(session_log_dir, limit))
                return
            if parsed.path == "/api/session-captures":
                limit = default_limit
                session_name = ""
                if "limit" in query:
                    try:
                        limit = max(1, min(50, int(query["limit"][0])))
                    except ValueError:
                        limit = default_limit
                if "session" in query:
                    session_name = str(query["session"][0]).strip()
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = dict(mock_bundle.get("session_captures", {"ok": True, "available": False}))
                    records = payload.get("records", [])
                    if isinstance(records, list):
                        payload["records"] = records[: max(1, limit)]
                        payload["count"] = len(payload["records"])
                        payload["latest"] = payload["records"][0] if payload["records"] else None
                    payload["latest_file"] = session_name or payload.get("latest_file", "")
                    self.send_json(payload)
                    return
                self.send_json(build_session_captures_payload(session_log_dir, capture_dir, limit, session_name))
                return
            if parsed.path == "/api/captures":
                limit = default_limit
                if "limit" in query:
                    try:
                        limit = max(1, min(100, int(query["limit"][0])))
                    except ValueError:
                        limit = default_limit
                if mock_mode and isinstance(mock_bundle, dict):
                    payload = dict(mock_bundle.get("captures", {"ok": True, "available": False}))
                    records = payload.get("records", [])
                    if isinstance(records, list):
                        payload["records"] = records[:limit]
                        payload["count"] = len(records)
                        payload["latest"] = payload["records"][0] if payload["records"] else None
                        payload["event_count"] = len(
                            {
                                str(record.get("event_id", ""))
                                for record in records
                                if str(record.get("event_id", "")).strip() and str(record.get("event_id", "")) != "NONE"
                            }
                        )
                        payload["last_timestamp_ms"] = payload["latest"].get("timestamp_ms", 0) if payload["latest"] else 0
                    self.send_json(payload)
                    return
                records = load_capture_records(capture_log_file, capture_dir)
                self.send_json(build_captures_payload(records, limit))
                return
            if parsed.path.startswith("/captures/"):
                # 限制静态文件访问范围，避免通过相对路径越界读取。
                relative = parsed.path.removeprefix("/captures/").strip("/")
                target = (capture_dir / relative).resolve()
                try:
                    target.relative_to(capture_dir.resolve())
                except ValueError:
                    self.send_error(HTTPStatus.FORBIDDEN, "Invalid capture path")
                    return
                if not target.exists() or not target.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND, "Capture not found")
                    return
                mime_type, _ = mimetypes.guess_type(target.name)
                self.serve_file(target, mime_type or "application/octet-stream")
                return
            if parsed.path.startswith("/docs/"):
                relative = parsed.path.removeprefix("/docs/").strip("/")
                target = (docs_dir / relative).resolve()
                try:
                    target.relative_to(docs_dir.resolve())
                except ValueError:
                    self.send_error(HTTPStatus.FORBIDDEN, "Invalid docs path")
                    return
                if not target.exists() or not target.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND, "Document not found")
                    return
                mime_type, _ = mimetypes.guess_type(target.name)
                self.serve_file(target, mime_type or "text/markdown; charset=utf-8")
                return

            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def send_json(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def serve_file(self, file_path: Path, content_type: str) -> None:
            if not file_path.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return
            body = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if content_type.startswith("text/html"):
                self.send_header("Cache-Control", "no-store")
            else:
                self.send_header("Cache-Control", "public, max-age=60")
            self.end_headers()
            self.wfile.write(body)

    return VisionDashboardHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a local dashboard for vision captures and Node A status")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument("--capture-dir", type=Path, default=Path("captures"), help="Directory containing capture images")
    parser.add_argument("--docs-dir", type=Path, default=Path("docs"), help="Directory containing freeze manifests and checklists")
    parser.add_argument("--capture-log-file", type=Path, default=Path("captures/capture_records.csv"), help="CSV file containing capture metadata")
    parser.add_argument("--status-file", type=Path, default=Path("captures/latest_status.json"), help="JSON file containing latest vision runtime status")
    parser.add_argument("--active-event-file", type=Path, default=Path("captures/latest_active_event.json"), help="JSON file storing current active event selected in dashboard")
    parser.add_argument("--node-status-file", type=Path, default=Path("captures/latest_node_status.json"), help="JSON file containing latest Node A serial status")
    parser.add_argument("--node-status-file-a2", type=Path, default=Path("captures/latest_node_status_A2.json"), help="JSON file containing latest Node A2 serial status")
    parser.add_argument("--node-events-file", type=Path, default=Path("captures/latest_node_events.json"), help="JSON file containing recent Node A event history")
    parser.add_argument("--node-events-file-a2", type=Path, default=Path("captures/latest_node_events_A2.json"), help="JSON file containing recent Node A2 event history")
    parser.add_argument("--node-event-store-file", type=Path, default=Path("captures/latest_node_event_store.json"), help="JSON file containing persistent Node A event records")
    parser.add_argument("--test-session-file", type=Path, default=Path("captures/latest_test_session.json"), help="JSON file containing the current test session state")
    parser.add_argument("--test-result-file", type=Path, default=Path("captures/latest_test_result.json"), help="JSON file containing the latest summarized test result")
    parser.add_argument("--test-results-file", type=Path, default=Path("captures/latest_test_results.json"), help="JSON file containing recent summarized test results")
    parser.add_argument("--session-log-dir", type=Path, default=Path("captures/session_logs"), help="Directory containing per-session JSONL timeline logs")
    parser.add_argument("--event-export-dir", type=Path, default=Path("captures/event_exports"), help="Directory used to persist exported event evidence JSON files")
    parser.add_argument("--dashboard-file", type=Path, default=DASHBOARD_FILE, help="HTML dashboard file to serve")
    parser.add_argument("--limit", type=int, default=10, help="Default number of records returned by the API")
    parser.add_argument("--capture-fallback-window-ms", type=int, default=8000, help="Time window used to fallback-match NONE captures to selected events")
    parser.add_argument("--node-offline-timeout-ms", type=int, default=5000, help="Center-side timeout used to mark node status offline when updates stop")
    args = parser.parse_args()

    capture_dir = resolve_path(args.capture_dir)
    docs_dir = resolve_path(args.docs_dir)
    capture_log_file = resolve_path(args.capture_log_file)
    status_file = resolve_path(args.status_file)
    active_event_file = resolve_path(args.active_event_file)
    node_status_file = resolve_path(args.node_status_file)
    node_status_file_a2 = resolve_path(args.node_status_file_a2)
    node_events_file = resolve_path(args.node_events_file)
    node_events_file_a2 = resolve_path(args.node_events_file_a2)
    node_event_store_file = resolve_path(args.node_event_store_file)
    test_session_file = resolve_path(args.test_session_file)
    test_result_file = resolve_path(args.test_result_file)
    test_results_file = resolve_path(args.test_results_file)
    session_log_dir = resolve_path(args.session_log_dir)
    event_export_dir = resolve_path(args.event_export_dir)
    dashboard_file = resolve_path(args.dashboard_file)
    handler = create_handler(
        dashboard_file,
        capture_dir,
        docs_dir,
        capture_log_file,
        status_file,
        active_event_file,
        node_status_file,
        node_status_file_a2,
        node_events_file,
        node_events_file_a2,
        node_event_store_file,
        test_session_file,
        test_result_file,
        test_results_file,
        session_log_dir,
        event_export_dir,
        args.limit,
        max(0, args.capture_fallback_window_ms),
        max(0, args.node_offline_timeout_ms),
    )

    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Vision dashboard server listening on http://{args.host}:{args.port}")
    print(f"Capture dir: {capture_dir.as_posix()}")
    print(f"Docs dir: {docs_dir.as_posix()}")
    print(f"Capture log: {capture_log_file.as_posix()}")
    print(f"Vision status file: {status_file.as_posix()}")
    print(f"Active event file: {active_event_file.as_posix()}")
    print(f"Node status file: {node_status_file.as_posix()}")
    print(f"Node status A2 file: {node_status_file_a2.as_posix()}")
    print(f"Node events file: {node_events_file.as_posix()}")
    print(f"Node events A2 file: {node_events_file_a2.as_posix()}")
    print(f"Node event store file: {node_event_store_file.as_posix()}")
    print(f"Test session file: {test_session_file.as_posix()}")
    print(f"Test result file: {test_result_file.as_posix()}")
    print(f"Test results history file: {test_results_file.as_posix()}")
    print(f"Session log dir: {session_log_dir.as_posix()}")
    print(f"Event export dir: {event_export_dir.as_posix()}")
    print(f"Capture fallback window ms: {max(0, args.capture_fallback_window_ms)}")
    print(f"Node offline timeout ms: {max(0, args.node_offline_timeout_ms)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nVision dashboard server stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

