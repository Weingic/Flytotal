# ???? Node A ?????????? JSON ???????????????????????????????????
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from session_log_utils_会话日志工具 import append_session_event as append_session_timeline_event
from session_log_utils_会话日志工具 import resolve_path as resolve_shared_path

try:
    import serial
except ImportError:  # pragma: no cover - handled on the user's machine
    serial = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MONITORED_PREFIXES = {
    "STATUS",
    "SELFTEST",
    "UPLINK,HB",
    "UPLINK,TRACK",
    "UPLINK,EVENT",
    "EVENT,STATUS",
    "LASTEVENT",
    "SUMMARY",
}
EVENT_HISTORY_PREFIXES = {"UPLINK,EVENT", "LASTEVENT", "EVENT,STATUS"}
SUMMARY_COUNTER_FIELDS = (
    "track_active_count",
    "track_confirmed_count",
    "track_lost_count",
    "event_opened_count",
    "event_closed_count",
    "handover_queued_count",
    "handover_emitted_count",
    "handover_ignored_count",
)


def require_pyserial() -> Any:
    if serial is None:
        print("PySerial is not installed. Run `pip install pyserial` first.", file=sys.stderr)
        raise SystemExit(1)
    return serial


def resolve_path(value: Path) -> Path:
    return resolve_shared_path(value)


def parse_prefix_and_fields(line: str) -> tuple[str, dict[str, str]]:
    parts = [part.strip() for part in line.strip().split(",") if part.strip()]
    if not parts:
        return "", {}

    if len(parts) > 1 and "=" not in parts[1]:
        prefix = f"{parts[0]},{parts[1]}"
        kv_tokens = parts[2:]
    else:
        prefix = parts[0]
        kv_tokens = parts[1:]

    fields: dict[str, str] = {}
    for token in kv_tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key.strip()] = value.strip()
    return prefix, fields


def coerce_value(value: str) -> Any:
    if value in ("0", "1"):
        return int(value)
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def normalize_fields(prefix: str, raw_fields: dict[str, str]) -> dict[str, Any]:
    # 这里做“字段别名统一”。
    # 例如 STATUS 里可能叫 track/active/confirmed，
    # 而统一状态文件里统一改成 track_id/track_active/track_confirmed。
    normalized: dict[str, Any] = {
        "last_message_type": prefix,
        "last_update_ms": int(time.time() * 1000),
    }

    alias_map = {
        "node": "node_id",
        "zone": "node_zone",
        "role": "node_role",
        "main_state": "main_state",
        "hunter": "hunter_state",
        "hunter_state": "hunter_state",
        "gimbal": "gimbal_state",
        "gimbal_state": "gimbal_state",
        "rid": "rid_status",
        "rid_status": "rid_status",
        "rid_whitelist": "rid_whitelist_hit",
        "rid_whitelist_hit": "rid_whitelist_hit",
        "wl_status": "wl_status",
        "wl_owner": "wl_owner",
        "wl_label": "wl_label",
        "wl_expire_time_ms": "wl_expire_time_ms",
        "wl_note": "wl_note",
        "rid_last_update_ms": "rid_last_update_ms",
        "rid_last_match_ms": "rid_last_match_ms",
        "rid_id": "rid_id",
        "rid_device_type": "rid_device_type",
        "rid_source": "rid_source",
        "rid_auth_status": "rid_auth_status",
        "rid_whitelist_tag": "rid_whitelist_tag",
        "rid_signal_strength": "rid_signal_strength",
        "risk": "risk_score",
        "risk_score": "risk_score",
        "risk_level": "risk_level",
        "track": "track_id",
        "track_id": "track_id",
        "active": "track_active",
        "track_active": "track_active",
        "confirmed": "track_confirmed",
        "track_confirmed": "track_confirmed",
        "x": "x_mm",
        "x_mm": "x_mm",
        "y": "y_mm",
        "y_mm": "y_mm",
        "vx": "vx_mm_s",
        "vx_mm_s": "vx_mm_s",
        "vy": "vy_mm_s",
        "vy_mm_s": "vy_mm_s",
        "event_active": "event_active",
        "event_id": "event_id",
        "current_event_id": "event_id",
        "vision_state": "vision_state",
        "vision_locked": "vision_locked",
        "capture_ready": "capture_ready",
        "uplink_state": "uplink_state",
        "last_event_id": "last_event_id",
        "last_reason": "last_reason",
        "last_event_level": "event_level",
        "last_event_status": "event_status",
        "last_source_node": "source_node",
        "event_level": "event_level",
        "event_status": "event_status",
        "reason": "event_reason",
        "ts": "timestamp_ms",
        "timestamp": "timestamp_ms",
        "source_node": "source_node",
        "handover_last_result": "handover_last_result",
        "handover_last_target": "handover_last_target",
        "handover_last_ts": "handover_last_ts",
        "handover_last_event_id": "handover_last_event_id",
        "monitor_baud": "monitor_baud",
        "radar_baud": "radar_baud",
        "sim_hold_ms": "sim_hold_ms",
        "test_mode": "test_mode_enabled",
        "servo_enabled": "servo_enabled",
        "servo_attached": "servo_attached",
        "safe_mode": "safe_mode_enabled",
        "diag_running": "diag_running",
        "debug": "debug_enabled",
        "quiet": "quiet_enabled",
        "uplink": "uplink_enabled",
        "predictor_kp": "predictor_kp",
        "predictor_kd": "predictor_kd",
        "heartbeat_ms": "heartbeat_ms",
        "event_report_ms": "event_report_ms",
        "idle_ready": "idle_ready",
    }

    summary_alias_map = {
        "started_ms": "summary_started_ms",
        "track_active": "track_active_count",
        "track_confirmed": "track_confirmed_count",
        "track_lost": "track_lost_count",
        "event_opened": "event_opened_count",
        "event_closed": "event_closed_count",
        "handover_queued": "handover_queued_count",
        "handover_emitted": "handover_emitted_count",
        "handover_ignored": "handover_ignored_count",
        "risk_suspicious": "risk_suspicious_count",
        "risk_high_risk": "risk_high_risk_count",
        "risk_event": "risk_event_count",
        "max_risk": "max_risk_score",
        "last_track": "summary_last_track_id",
        "last_x": "summary_last_x_mm",
        "last_y": "summary_last_y_mm",
    }

    for key, value in raw_fields.items():
        if prefix == "SUMMARY":
            summary_key = summary_alias_map.get(key)
            if summary_key is not None:
                normalized[summary_key] = coerce_value(value)
                continue

        target_key = alias_map.get(key)
        if target_key is not None:
            normalized[target_key] = coerce_value(value)

    return normalized


def build_initial_status() -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {
        "ok": True,
        "available": False,
        "online": 0,
        "stale_age_ms": 0,
        "node_id": "",
        "node_zone": "",
        "node_role": "",
        "main_state": "UNKNOWN",
        "hunter_state": "UNKNOWN",
        "gimbal_state": "UNKNOWN",
        "rid_status": "UNKNOWN",
        "rid_whitelist_hit": 0,
        "wl_status": "WL_UNKNOWN",
        "wl_owner": "NONE",
        "wl_label": "NONE",
        "wl_expire_time_ms": 0,
        "wl_note": "NONE",
        "rid_last_update_ms": 0,
        "rid_last_match_ms": 0,
        "rid_id": "NONE",
        "rid_device_type": "NONE",
        "rid_source": "NONE",
        "rid_auth_status": "NONE",
        "rid_whitelist_tag": "NONE",
        "rid_signal_strength": 0,
        "risk_score": 0.0,
        "risk_level": "NONE",
        "track_id": 0,
        "track_active": 0,
        "track_confirmed": 0,
        "x_mm": 0.0,
        "y_mm": 0.0,
        "vx_mm_s": 0.0,
        "vy_mm_s": 0.0,
        "event_active": 0,
        "event_id": "NONE",
        "vision_state": "UNKNOWN",
        "vision_locked": 0,
        "capture_ready": 0,
        "uplink_state": "UNKNOWN",
        "last_event_id": "NONE",
        "last_reason": "NONE",
        "event_level": "NONE",
        "event_status": "NONE",
        "event_reason": "NONE",
        "source_node": "",
        "handover_last_result": "NONE",
        "handover_last_target": "NONE",
        "handover_last_ts": 0,
        "handover_last_event_id": "NONE",
        "monitor_baud": 0,
        "radar_baud": 0,
        "sim_hold_ms": 0,
        "test_mode_enabled": 0,
        "servo_enabled": 0,
        "servo_attached": 0,
        "safe_mode_enabled": 0,
        "diag_running": 0,
        "debug_enabled": 0,
        "quiet_enabled": 0,
        "uplink_enabled": 0,
        "predictor_kp": 0.0,
        "predictor_kd": 0.0,
        "heartbeat_ms": 0,
        "event_report_ms": 0,
        "idle_ready": 0,
        "timestamp_ms": now_ms,
        "last_update_ms": now_ms,
        "last_message_type": "NONE",
        "last_raw_line": "",
        "consistency_status": "UNKNOWN",
        "consistency_warning_count": 0,
        "consistency_warnings": [],
        "consistency_expected_main_state": "UNKNOWN",
        "consistency_main_state_match": 0,
        "consistency_checked_ms": now_ms,
    }


def refresh_runtime_flags(state: dict[str, Any], offline_timeout_s: float) -> None:
    now_ms = int(time.time() * 1000)
    last_update_ms = int(state.get("last_update_ms") or 0)
    stale_age_ms = max(0, now_ms - last_update_ms)
    online = 1 if state.get("available") and stale_age_ms <= int(max(offline_timeout_s, 0.0) * 1000) else 0
    state["stale_age_ms"] = stale_age_ms
    state["online"] = online


def infer_expected_main_state(state: dict[str, Any]) -> str:
    hunter_state = str(state.get("hunter_state", "UNKNOWN")).upper()
    gimbal_state = str(state.get("gimbal_state", "UNKNOWN")).upper()
    track_active = int(state.get("track_active") or 0)

    if hunter_state == "EVENT_LOCKED":
        return "EVENT"
    if hunter_state == "HIGH_RISK":
        return "HIGH_RISK"
    if hunter_state == "SUSPICIOUS":
        return "SUSPICIOUS"
    if hunter_state in {"TRACKING", "RID_MATCHED"}:
        if track_active == 1:
            return "TRACKING"
        return "LOST" if gimbal_state == "LOST" else "IDLE"
    if hunter_state == "IDLE":
        if track_active == 0 and gimbal_state == "LOST":
            return "LOST"
        return "IDLE"
    return "UNKNOWN"


def evaluate_status_consistency(state: dict[str, Any]) -> None:
    warnings: list[str] = []

    reported_main_state = str(state.get("main_state", "UNKNOWN")).upper()
    expected_main_state = infer_expected_main_state(state)
    main_state_match = int(expected_main_state == "UNKNOWN" or reported_main_state == expected_main_state)
    if main_state_match == 0:
        warnings.append(f"main_state={reported_main_state} expected={expected_main_state}")

    event_active = int(state.get("event_active") or 0)
    event_status = str(state.get("event_status", "NONE")).upper()
    event_id = str(state.get("event_id", "NONE")).upper()
    if event_active == 1 and event_id in {"", "NONE"}:
        warnings.append("event_active=1 but event_id=NONE")
    if event_active == 0 and event_status == "OPEN":
        warnings.append("event_active=0 but event_status=OPEN")

    track_active = int(state.get("track_active") or 0)
    track_confirmed = int(state.get("track_confirmed") or 0)
    if track_confirmed == 1 and track_active == 0:
        warnings.append("track_confirmed=1 but track_active=0")

    vision_locked = int(state.get("vision_locked") or 0)
    capture_ready = int(state.get("capture_ready") or 0)
    vision_state = str(state.get("vision_state", "UNKNOWN")).upper()
    if vision_locked == 1 and vision_state in {"VISION_IDLE", "VISION_LOST"}:
        warnings.append(f"vision_locked=1 but vision_state={vision_state}")
    if capture_ready == 1 and vision_locked == 0:
        warnings.append("capture_ready=1 but vision_locked=0")

    risk_level = str(state.get("risk_level", "NONE")).upper()
    risk_score = float(state.get("risk_score") or 0.0)
    if risk_score >= 60.0 and risk_level in {"NONE", "NORMAL"}:
        warnings.append(f"risk_score={risk_score:.1f} but risk_level={risk_level}")
    if risk_score < 20.0 and risk_level in {"HIGH_RISK", "EVENT"}:
        warnings.append(f"risk_score={risk_score:.1f} but risk_level={risk_level}")

    hunter_state = str(state.get("hunter_state", "UNKNOWN")).upper()
    rid_status = str(state.get("rid_status", "UNKNOWN")).upper()
    wl_status = str(state.get("wl_status", "WL_UNKNOWN")).upper()
    if hunter_state == "RID_MATCHED" and wl_status != "WL_ALLOWED":
        warnings.append(f"hunter_state={hunter_state} but wl_status={wl_status}")
    rid_whitelist_hit = int(state.get("rid_whitelist_hit") or 0)
    if rid_status == "MATCHED" and (rid_whitelist_hit != 1 or wl_status != "WL_ALLOWED"):
        warnings.append("rid_status=MATCHED but whitelist gate not allowed")

    now_ms = int(time.time() * 1000)
    state["consistency_status"] = "WARN" if warnings else "OK"
    state["consistency_warning_count"] = len(warnings)
    state["consistency_warnings"] = warnings[:6]
    state["consistency_expected_main_state"] = expected_main_state
    state["consistency_main_state_match"] = main_state_match
    state["consistency_checked_ms"] = now_ms


def write_status_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def build_event_record(prefix: str, raw_fields: dict[str, str]) -> dict[str, Any] | None:
    if prefix not in EVENT_HISTORY_PREFIXES:
        return None
    if not raw_fields:
        return None

    now_ms = int(time.time() * 1000)
    event_id = (
        raw_fields.get(
            "event_id",
            raw_fields.get("current_event_id", raw_fields.get("last_event_id", "NONE")),
        ).strip()
        or "NONE"
    )
    reason = raw_fields.get("reason", raw_fields.get("last_reason", "NONE")).strip() or "NONE"
    event_level = raw_fields.get("event_level", "NONE").strip() or "NONE"
    event_status = raw_fields.get("event_status", "NONE").strip() or "NONE"
    track_id = coerce_value(raw_fields.get("track", raw_fields.get("track_id", "0")))
    risk_score = coerce_value(raw_fields.get("risk", raw_fields.get("risk_score", "0")))
    handover_to = raw_fields.get("handover_to", raw_fields.get("handover_last_target", "NONE")).strip() or "NONE"
    timestamp_ms = coerce_value(raw_fields.get("ts", raw_fields.get("timestamp", str(int(time.time() * 1000)))))
    x_mm = coerce_value(raw_fields.get("x", raw_fields.get("x_mm", raw_fields.get("last_x", "0"))))
    y_mm = coerce_value(raw_fields.get("y", raw_fields.get("y_mm", raw_fields.get("last_y", "0"))))
    vx_mm_s = coerce_value(raw_fields.get("vx", raw_fields.get("vx_mm_s", raw_fields.get("last_vx", "0"))))
    vy_mm_s = coerce_value(raw_fields.get("vy", raw_fields.get("vy_mm_s", raw_fields.get("last_vy", "0"))))
    rid_status = (
        raw_fields.get("rid_status", raw_fields.get("rid", raw_fields.get("last_rid_status", "UNKNOWN"))).strip()
        or "UNKNOWN"
    )
    wl_status = raw_fields.get("wl_status", "WL_UNKNOWN").strip() or "WL_UNKNOWN"
    main_state = (
        raw_fields.get("main_state", raw_fields.get("current_main_state", raw_fields.get("last_main_state", "UNKNOWN")))
        .strip()
        or "UNKNOWN"
    )
    hunter_state = (
        raw_fields.get(
            "hunter_state",
            raw_fields.get("current_hunter_state", raw_fields.get("last_hunter_state", "UNKNOWN")),
        ).strip()
        or "UNKNOWN"
    )
    gimbal_state = (
        raw_fields.get(
            "gimbal_state",
            raw_fields.get("current_gimbal_state", raw_fields.get("last_gimbal_state", "UNKNOWN")),
        ).strip()
        or "UNKNOWN"
    )
    risk_level = (
        raw_fields.get("risk_level", raw_fields.get("current_risk_level", raw_fields.get("last_risk_level", "NONE")))
        .strip()
        or "NONE"
    )
    event_close_reason = (
        raw_fields.get(
            "event_close_reason",
            raw_fields.get("current_event_close_reason", raw_fields.get("last_reason", "NONE")),
        ).strip()
        or "NONE"
    )
    event_trigger_reasons = (
        raw_fields.get("event_trigger_reasons", raw_fields.get("current_event_trigger_reasons", "NONE")).strip()
        or "NONE"
    )
    vision_state = raw_fields.get("vision_state", "UNKNOWN").strip() or "UNKNOWN"
    vision_locked = coerce_value(raw_fields.get("vision_locked", "0"))
    capture_ready = coerce_value(raw_fields.get("capture_ready", "0"))

    # 无事件编号的 EVENT,STATUS 不进入事件仓，避免空状态刷屏。
    if prefix == "EVENT,STATUS" and event_id == "NONE":
        return None

    return {
        "source_type": prefix,
        "timestamp_ms": timestamp_ms,
        "host_logged_ms": now_ms,
        "node_id": raw_fields.get("node", "").strip(),
        "zone": raw_fields.get("zone", "").strip(),
        "event_id": event_id,
        "reason": reason,
        "event_level": event_level,
        "event_status": event_status,
        "event_close_reason": event_close_reason,
        "event_trigger_reasons": event_trigger_reasons,
        "track_id": track_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "rid_status": rid_status,
        "wl_status": wl_status,
        "main_state": main_state,
        "hunter_state": hunter_state,
        "gimbal_state": gimbal_state,
        "x_mm": x_mm,
        "y_mm": y_mm,
        "vx_mm_s": vx_mm_s,
        "vy_mm_s": vy_mm_s,
        "vision_state": vision_state,
        "vision_locked": vision_locked,
        "capture_ready": capture_ready,
        "handover_to": handover_to,
        "source_node": raw_fields.get("source_node", "").strip() or raw_fields.get("node", "").strip(),
    }


def append_event_record(history: list[dict[str, Any]], record: dict[str, Any], limit: int) -> bool:
    # 用几个关键字段做轻量去重，避免同一事件在很短时间内重复刷屏。
    key = (
        str(record.get("source_type", "")),
        str(record.get("timestamp_ms", "")),
        str(record.get("event_id", "")),
        str(record.get("reason", "")),
        str(record.get("track_id", "")),
    )

    for existing in history[:3]:
        existing_key = (
            str(existing.get("source_type", "")),
            str(existing.get("timestamp_ms", "")),
            str(existing.get("event_id", "")),
            str(existing.get("reason", "")),
            str(existing.get("track_id", "")),
        )
        if existing_key == key:
            return False

    history.insert(0, record)
    if len(history) > limit:
        del history[limit:]
    return True


def write_event_history_json(path: Path, records: list[dict[str, Any]]) -> None:
    payload = {
        "ok": True,
        "available": bool(records),
        "count": len(records),
        "records": records,
        "latest": records[0] if records else None,
    }
    write_status_json(path, payload)


def append_event_store_record(store: list[dict[str, Any]], record: dict[str, Any], limit: int) -> bool:
    # 事件仓用于留痕，去重键不含时间，避免相同语义事件高频刷屏。
    key = (
        str(record.get("source_type", "")),
        str(record.get("event_id", "")),
        str(record.get("event_status", "")),
        str(record.get("event_level", "")),
        str(record.get("reason", "")),
        str(record.get("track_id", "")),
    )
    for existing in store[:8]:
        existing_key = (
            str(existing.get("source_type", "")),
            str(existing.get("event_id", "")),
            str(existing.get("event_status", "")),
            str(existing.get("event_level", "")),
            str(existing.get("reason", "")),
            str(existing.get("track_id", "")),
        )
        if existing_key == key:
            return False

    store.insert(0, record)
    if len(store) > limit:
        del store[limit:]
    return True


def write_event_store_json(path: Path, records: list[dict[str, Any]]) -> None:
    payload = {
        "ok": True,
        "available": bool(records),
        "count": len(records),
        "updated_ms": int(time.time() * 1000),
        "records": records,
        "latest": records[0] if records else None,
    }
    write_status_json(path, payload)


def backfill_event_host_time(records: list[dict[str, Any]]) -> None:
    if not records:
        return
    now_ms = int(time.time() * 1000)
    total = len(records)
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        host_logged_ms = int(coerce_value(str(record.get("host_logged_ms", "0"))) or 0)
        if host_logged_ms > 0:
            continue
        ts_ms = int(coerce_value(str(record.get("timestamp_ms", "0"))) or 0)
        if ts_ms >= 946684800000:
            record["host_logged_ms"] = ts_ms
            continue
        # 旧格式事件仅有设备相对时钟，回退为主机时间，保持记录顺序。
        offset = max(0, total - index - 1)
        record["host_logged_ms"] = now_ms - offset


def load_records_from_payload(path: Path) -> list[dict[str, Any]]:
    payload = load_json_payload(path)
    records = payload.get("records", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def load_json_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": True, "available": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "available": False}
    if not isinstance(payload, dict):
        return {"ok": False, "available": False}
    payload.setdefault("ok", True)
    return payload


def summary_snapshot_from_status(status: dict[str, Any]) -> dict[str, int]:
    return {field: int(status.get(field) or 0) for field in SUMMARY_COUNTER_FIELDS}


def build_initial_test_result() -> dict[str, Any]:
    return {
        "ok": True,
        "available": False,
        "result_label": "NONE",
        "scenario_name": "",
        "scenario_description": "",
        "rid_mode": "UNCHANGED",
        "suite_name": "",
        "suite_step_total": 0,
        "suite_passed": 0,
        "suite_failed": 0,
        "suite_failed_checks": [],
        "suite_report": {},
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
        "started_ms": 0,
        "finished_ms": 0,
        "updated_ms": int(time.time() * 1000),
    }


def append_test_result_record(history: list[dict[str, Any]], record: dict[str, Any], limit: int) -> bool:
    key = (
        str(record.get("scenario_name", "")),
        str(record.get("rid_mode", "")),
        str(record.get("started_ms", "")),
        str(record.get("finished_ms", "")),
    )

    for existing in history[:5]:
        existing_key = (
            str(existing.get("scenario_name", "")),
            str(existing.get("rid_mode", "")),
            str(existing.get("started_ms", "")),
            str(existing.get("finished_ms", "")),
        )
        if existing_key == key:
            return False

    history.insert(0, record)
    if len(history) > limit:
        del history[limit:]
    return True


def write_test_result_history_json(path: Path, records: list[dict[str, Any]]) -> None:
    payload = {
        "ok": True,
        "available": bool(records),
        "count": len(records),
        "records": records,
        "latest": records[0] if records else None,
    }
    write_status_json(path, payload)


def build_test_result_payload(
    session: dict[str, Any],
    status: dict[str, Any],
    baseline_summary: dict[str, int],
    monitor: dict[str, Any],
) -> dict[str, Any]:
    suite_report = session.get("suite_report", {})
    if not isinstance(suite_report, dict):
        suite_report = {}
    suite_failed_checks = suite_report.get("failed_checks", [])
    if not isinstance(suite_failed_checks, list):
        suite_failed_checks = []

    current_summary = summary_snapshot_from_status(status)
    deltas = {
        field: max(0, current_summary.get(field, 0) - baseline_summary.get(field, 0))
        for field in SUMMARY_COUNTER_FIELDS
    }
    had_event = int(
        deltas["event_opened_count"] > 0
        or monitor.get("saw_event", False)
        or str(status.get("event_id", "NONE")) != "NONE"
        or str(status.get("last_event_id", "NONE")) != "NONE"
    )
    had_handover = int(
        deltas["handover_queued_count"] > 0
        or deltas["handover_emitted_count"] > 0
        or deltas["handover_ignored_count"] > 0
        or monitor.get("saw_handover", False)
    )
    track_seen = deltas["track_active_count"] > 0 or monitor.get("saw_track_active", False)
    max_risk_score = max(float(status.get("risk_score") or 0.0), float(monitor.get("max_risk_score") or 0.0))
    final_risk_level = str(status.get("risk_level", "NONE"))
    final_main_state = str(status.get("main_state", "UNKNOWN"))

    if not track_seen:
        result_label = "FAIL"
    elif deltas["handover_ignored_count"] > 0:
        result_label = "WARN"
    elif final_risk_level in {"SUSPICIOUS", "HIGH_RISK", "EVENT"} or had_event or had_handover:
        result_label = "WARN"
    else:
        result_label = "PASS"

    return {
        "ok": True,
        "available": True,
        "result_label": result_label,
        "scenario_name": session.get("scenario_name", ""),
        "scenario_description": session.get("scenario_description", ""),
        "rid_mode": session.get("rid_mode", "UNCHANGED"),
        "suite_name": session.get("suite_name", ""),
        "suite_step_total": int(session.get("suite_step_total") or 0),
        "suite_passed": int(session.get("suite_passed") or 0),
        "suite_failed": int(session.get("suite_failed") or 0),
        "suite_failed_checks": suite_failed_checks,
        "suite_report": suite_report,
        "final_main_state": final_main_state,
        "final_risk_level": final_risk_level,
        "final_event_id": status.get("event_id", status.get("last_event_id", "NONE")) or "NONE",
        "had_event": had_event,
        "had_handover": had_handover,
        "track_active_delta": deltas["track_active_count"],
        "track_lost_delta": deltas["track_lost_count"],
        "event_opened_delta": deltas["event_opened_count"],
        "event_closed_delta": deltas["event_closed_count"],
        "handover_queued_delta": deltas["handover_queued_count"],
        "handover_emitted_delta": deltas["handover_emitted_count"],
        "handover_ignored_delta": deltas["handover_ignored_count"],
        "max_risk_score": max_risk_score,
        "predictor_kp": float(status.get("predictor_kp") or 0.0),
        "predictor_kd": float(status.get("predictor_kd") or 0.0),
        "heartbeat_ms": int(status.get("heartbeat_ms") or 0),
        "event_report_ms": int(status.get("event_report_ms") or 0),
        "sim_hold_ms": int(status.get("sim_hold_ms") or 0),
        "debug_enabled": int(status.get("debug_enabled") or 0),
        "quiet_enabled": int(status.get("quiet_enabled") or 0),
        "uplink_enabled": int(status.get("uplink_enabled") or 0),
        "final_gimbal_state": str(status.get("gimbal_state", "UNKNOWN")),
        "final_risk_score": float(status.get("risk_score") or 0.0),
        "started_ms": int(session.get("started_ms") or 0),
        "finished_ms": int(session.get("finished_ms") or int(time.time() * 1000)),
        "updated_ms": int(time.time() * 1000),
    }


def update_test_result_monitor(
    session_payload: dict[str, Any],
    status: dict[str, Any],
    monitor: dict[str, Any] | None,
    result_file: Path,
    result_history: list[dict[str, Any]],
    result_history_file: Path,
    result_history_limit: int,
    session_log_dir: Path,
) -> dict[str, Any] | None:
    session_available = bool(session_payload.get("available"))
    session_status = str(session_payload.get("status", "IDLE"))
    session_key = f"{session_payload.get('started_ms', 0)}:{session_payload.get('scenario_name', '')}"

    if session_available and session_status in {"RUNNING", "SETTLING", "DONE"} and (monitor is None or monitor.get("session_key") != session_key):
        monitor = {
            "session_key": session_key,
            "baseline_summary": summary_snapshot_from_status(status),
            "saw_track_active": False,
            "saw_event": False,
            "saw_handover": False,
            "max_risk_score": float(status.get("risk_score") or 0.0),
            "finalized": False,
        }

    if monitor is None:
        return None

    monitor["saw_track_active"] = bool(monitor.get("saw_track_active")) or int(status.get("track_active") or 0) == 1
    monitor["saw_event"] = bool(monitor.get("saw_event")) or int(status.get("event_active") or 0) == 1 or str(status.get("event_id", "NONE")) != "NONE"
    monitor["saw_handover"] = bool(monitor.get("saw_handover")) or str(status.get("handover_last_result", "NONE")) not in {"", "NONE"}
    monitor["max_risk_score"] = max(float(monitor.get("max_risk_score") or 0.0), float(status.get("risk_score") or 0.0))

    if session_available and session_status == "DONE" and not monitor.get("finalized"):
        result_payload = build_test_result_payload(session_payload, status, monitor["baseline_summary"], monitor)
        write_status_json(result_file, result_payload)
        if append_test_result_record(result_history, result_payload, max(1, result_history_limit)):
            write_test_result_history_json(result_history_file, result_history)
        append_session_timeline_event(
            session_payload,
            session_log_dir,
            source="node_a_serial_bridge",
            event_type="test_result",
            payload=result_payload,
        )
        monitor["finalized"] = True
        return monitor

    return monitor


def update_status_from_line(state: dict[str, Any], line: str) -> bool:
    prefix, fields = parse_prefix_and_fields(line)
    if prefix not in MONITORED_PREFIXES or not fields:
        return False

    state.update(normalize_fields(prefix, fields))
    state["ok"] = True
    state["available"] = True
    state["last_raw_line"] = line
    evaluate_status_consistency(state)
    return True


def extract_state_signature(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "main_state": state.get("main_state", "UNKNOWN"),
        "risk_level": state.get("risk_level", "NONE"),
        "event_id": state.get("event_id", "NONE"),
        "track_active": int(state.get("track_active") or 0),
        "handover_last_result": state.get("handover_last_result", "NONE"),
    }


def maybe_send_command(ser: Any, last_sent_at: float, interval_s: float, command: str) -> float:
    if interval_s <= 0:
        return last_sent_at
    now = time.monotonic()
    if last_sent_at == 0.0 or (now - last_sent_at) >= interval_s:
        ser.write((command + "\n").encode("utf-8"))
        ser.flush()
        return now
    return last_sent_at


def main() -> int:
    serial_module = require_pyserial()

    parser = argparse.ArgumentParser(description="Bridge Node A serial status into a JSON file")
    parser.add_argument("--port", required=True, help="Serial port, for example COM4")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--timeout", type=float, default=0.2, help="Serial read timeout in seconds")
    parser.add_argument("--output-file", type=Path, default=Path("captures/latest_node_status.json"), help="JSON file written with the latest Node A status")
    parser.add_argument("--events-file", type=Path, default=Path("captures/latest_node_events.json"), help="JSON file written with the recent Node A events")
    parser.add_argument("--event-store-file", type=Path, default=Path("captures/latest_node_event_store.json"), help="JSON file written with persistent Node A event records for evidence tracing")
    parser.add_argument("--session-file", type=Path, default=Path("captures/latest_test_session.json"), help="JSON file written by track_injector with the current test session")
    parser.add_argument("--result-file", type=Path, default=Path("captures/latest_test_result.json"), help="JSON file written with the latest summarized test result")
    parser.add_argument("--result-history-file", type=Path, default=Path("captures/latest_test_results.json"), help="JSON file written with recent summarized test results")
    parser.add_argument("--session-log-dir", type=Path, default=Path("captures/session_logs"), help="Directory used to store per-session JSONL timeline logs")
    parser.add_argument("--result-history-limit", type=int, default=16, help="How many recent summarized test results to keep")
    parser.add_argument("--events-limit", type=int, default=12, help="How many recent Node A events to keep")
    parser.add_argument("--event-store-limit", type=int, default=200, help="How many persistent Node A event records to keep")
    parser.add_argument("--status-interval", type=float, default=2.0, help="Seconds between automatic STATUS commands, set to 0 to disable")
    parser.add_argument("--selftest-interval", type=float, default=6.0, help="Seconds between automatic SELFTEST commands, set to 0 to disable")
    parser.add_argument("--summary-interval", type=float, default=0.0, help="Seconds between automatic SUMMARY commands, set to 0 to disable")
    parser.add_argument("--event-status-interval", type=float, default=2.0, help="Seconds between automatic EVENT,STATUS commands, set to 0 to disable")
    parser.add_argument("--last-event-interval", type=float, default=3.0, help="Seconds between automatic LASTEVENT commands, set to 0 to disable")
    parser.add_argument("--boot-wait", type=float, default=1.0, help="Seconds to wait after opening the port before polling")
    parser.add_argument("--offline-timeout", type=float, default=5.0, help="Seconds without a valid update before marking Node A offline")
    parser.add_argument("--echo", action="store_true", help="Echo raw serial lines to the terminal")
    args = parser.parse_args()

    output_file = resolve_path(args.output_file)
    events_file = resolve_path(args.events_file)
    event_store_file = resolve_path(args.event_store_file)
    session_file = resolve_path(args.session_file)
    result_file = resolve_path(args.result_file)
    result_history_file = resolve_path(args.result_history_file)
    session_log_dir = resolve_path(args.session_log_dir)
    status = build_initial_status()
    event_history = load_records_from_payload(events_file)
    event_store = load_records_from_payload(event_store_file)
    result_history = load_records_from_payload(result_history_file)
    test_result_monitor: dict[str, Any] | None = None

    # 启动时把已有事件历史并入事件仓，避免重启 bridge 后证据链断档。
    backfill_event_host_time(event_history)
    # 兼容旧版事件仓记录，补齐 host_logged_ms，避免视觉侧绑定时因时间缺失退化为 NONE。
    backfill_event_host_time(event_store)

    for record in event_history:
        if isinstance(record, dict):
            append_event_store_record(event_store, record, max(1, args.event_store_limit))

    refresh_runtime_flags(status, args.offline_timeout)
    write_status_json(output_file, status)
    write_event_history_json(events_file, event_history)
    write_event_store_json(event_store_file, event_store)
    write_status_json(result_file, build_initial_test_result())
    write_test_result_history_json(result_history_file, result_history)

    try:
        ser = serial_module.Serial(args.port, args.baud, timeout=args.timeout)
    except serial_module.SerialException as exc:
        print(f"Failed to open {args.port}: {exc}", file=sys.stderr)
        return 1

    status_sent_at = 0.0
    selftest_sent_at = 0.0
    summary_sent_at = 0.0
    event_status_sent_at = 0.0
    last_event_sent_at = 0.0

    with ser:
        time.sleep(0.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f"Node A serial bridge connected to {args.port} at {args.baud}")
        print(f"Writing node status to: {output_file.as_posix()}")
        print(f"Writing event history to: {events_file.as_posix()}")
        print(f"Writing persistent event store to: {event_store_file.as_posix()}")
        print(f"Reading test session from: {session_file.as_posix()}")
        print(f"Writing test result to: {result_file.as_posix()}")
        print(f"Writing test result history to: {result_history_file.as_posix()}")
        print(f"Writing session timeline logs to: {session_log_dir.as_posix()}")

        time.sleep(max(args.boot_wait, 0.0))

        try:
            while True:
                status_sent_at = maybe_send_command(ser, status_sent_at, args.status_interval, "STATUS")
                selftest_sent_at = maybe_send_command(ser, selftest_sent_at, args.selftest_interval, "SELFTEST")
                summary_sent_at = maybe_send_command(ser, summary_sent_at, args.summary_interval, "SUMMARY")
                event_status_sent_at = maybe_send_command(
                    ser, event_status_sent_at, args.event_status_interval, "EVENT,STATUS"
                )
                last_event_sent_at = maybe_send_command(
                    ser, last_event_sent_at, args.last_event_interval, "LASTEVENT"
                )

                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                if args.echo:
                    print(line)

                prefix, fields = parse_prefix_and_fields(line)
                session_payload = load_json_payload(session_file)
                event_record = build_event_record(prefix, fields)
                if event_record is not None:
                    if append_event_store_record(event_store, event_record, max(1, args.event_store_limit)):
                        write_event_store_json(event_store_file, event_store)
                    if append_event_record(event_history, event_record, max(1, args.events_limit)):
                        write_event_history_json(events_file, event_history)
                        append_session_timeline_event(
                            session_payload,
                            session_log_dir,
                            source="node_a_serial_bridge",
                            event_type="node_event",
                            payload=event_record,
                        )

                previous_signature = extract_state_signature(status)
                if update_status_from_line(status, line):
                    refresh_runtime_flags(status, args.offline_timeout)
                    write_status_json(output_file, status)
                    current_signature = extract_state_signature(status)
                    if current_signature != previous_signature:
                        append_session_timeline_event(
                            session_payload,
                            session_log_dir,
                            source="node_a_serial_bridge",
                            event_type="node_status_changed",
                            payload={
                                "line_prefix": prefix,
                                "previous": previous_signature,
                                "current": current_signature,
                            },
                        )
                    test_result_monitor = update_test_result_monitor(
                        session_payload,
                        status,
                        test_result_monitor,
                        result_file,
                        result_history,
                        result_history_file,
                        args.result_history_limit,
                        session_log_dir,
                    )
                    continue

                refresh_runtime_flags(status, args.offline_timeout)
                write_status_json(output_file, status)
                test_result_monitor = update_test_result_monitor(
                    session_payload,
                    status,
                    test_result_monitor,
                    result_file,
                    result_history,
                    result_history_file,
                    args.result_history_limit,
                    session_log_dir,
                )
                continue

            refresh_runtime_flags(status, args.offline_timeout)
            write_status_json(output_file, status)
        except KeyboardInterrupt:
            print("\nNode A serial bridge stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

