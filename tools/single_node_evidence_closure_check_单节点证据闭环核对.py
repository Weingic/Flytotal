# ????? 4.11 ???????????????????????????????????USB ???????????
import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        return [row for row in reader if isinstance(row, dict)]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def normalize_event_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.upper() == "NONE":
        return "NONE"
    return text


def parse_int_flag(value: object) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip().lower()
    if text in {"", "none", "null", "false", "off", "no"}:
        return 0
    if text in {"true", "on", "yes"}:
        return 1
    try:
        return int(float(text))
    except ValueError:
        return 0


def parse_positive_int(value: object) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def parse_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def evaluate_vision_evidence(
    node_status_payload: dict[str, Any],
    vision_status_payload: dict[str, Any],
    event_store_payload: dict[str, Any],
    latest_event_id: str,
    capture_ready_last_capture_max_age_ms: int,
) -> dict[str, Any]:
    records_raw = event_store_payload.get("records", []) if isinstance(event_store_payload, dict) else []
    records = records_raw if isinstance(records_raw, list) else []
    scope_event_id = normalize_event_id(latest_event_id)
    scoped_records: list[dict[str, Any]] = []
    if scope_event_id and scope_event_id != "NONE":
        for item in records:
            if not isinstance(item, dict):
                continue
            event_id = normalize_event_id(item.get("event_id", ""))
            if event_id == scope_event_id:
                scoped_records.append(item)
    else:
        scoped_records = [item for item in records if isinstance(item, dict)]

    vision_lock_record_hits = 0
    capture_ready_record_hits = 0
    for item in scoped_records:
        vision_state = str(item.get("vision_state", "") or "").strip().upper()
        vision_locked = parse_int_flag(item.get("vision_locked", 0))
        capture_ready = parse_int_flag(item.get("capture_ready", 0))
        if vision_locked > 0 or vision_state == "VISION_LOCKED":
            vision_lock_record_hits += 1
        if capture_ready > 0:
            capture_ready_record_hits += 1

    node_vision_state = str(node_status_payload.get("vision_state", "") or "").strip().upper()
    status_vision_state = str(vision_status_payload.get("vision_state", "") or "").strip().upper()
    status_vision_lock_hit = 1 if (
        parse_int_flag(node_status_payload.get("vision_locked", 0)) > 0
        or parse_int_flag(vision_status_payload.get("vision_locked", 0)) > 0
        or node_vision_state == "VISION_LOCKED"
        or status_vision_state == "VISION_LOCKED"
    ) else 0
    status_capture_ready_hit = 1 if (
        parse_int_flag(node_status_payload.get("capture_ready", 0)) > 0
        or parse_int_flag(vision_status_payload.get("capture_ready", 0)) > 0
    ) else 0
    vision_status_ts_ms = parse_positive_int(vision_status_payload.get("timestamp_ms", 0))
    if vision_status_ts_ms <= 0:
        vision_status_ts_ms = int(time.time() * 1000)
    last_capture_ts_ms = parse_positive_int(vision_status_payload.get("last_capture_timestamp_ms", 0))
    last_capture_age_ms = 0
    status_last_capture_hit = 0
    if last_capture_ts_ms > 0 and vision_status_ts_ms >= last_capture_ts_ms:
        last_capture_age_ms = vision_status_ts_ms - last_capture_ts_ms
        max_age_ms = max(0, int(capture_ready_last_capture_max_age_ms))
        if max_age_ms <= 0 or last_capture_age_ms <= max_age_ms:
            status_last_capture_hit = 1

    return {
        "scope_event_id": scope_event_id if scope_event_id else "NONE",
        "scope_record_count": len(scoped_records),
        "vision_lock_record_hits": vision_lock_record_hits,
        "capture_ready_record_hits": capture_ready_record_hits,
        "status_vision_lock_hit": status_vision_lock_hit,
        "status_capture_ready_hit": status_capture_ready_hit,
        "status_last_capture_hit": status_last_capture_hit,
        "status_last_capture_age_ms": last_capture_age_ms,
        "vision_lock_hits": vision_lock_record_hits + status_vision_lock_hit + status_last_capture_hit,
        "capture_ready_hits": capture_ready_record_hits + status_capture_ready_hit + status_last_capture_hit,
    }


def is_sha256_hex(value: object) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def evaluate_national_first_event_detail(
    detail_payload: dict[str, Any],
    expected_event_id: str,
    *,
    min_auto_lock_score: float = 0.45,
    required_class_name: str = "drone",
    required_model_label: str = "drone-v4b-hardneg-deployed",
) -> dict[str, Any]:
    expected_id = normalize_event_id(expected_event_id) or "NONE"
    event_object = detail_payload.get("event_object_v1", {}) if isinstance(detail_payload, dict) else {}
    if not isinstance(event_object, dict):
        event_object = {}
    vision = event_object.get("vision_evidence", {})
    if not isinstance(vision, dict):
        vision = {}

    actual_event_id = normalize_event_id(detail_payload.get("event_id", "")) or "NONE"
    object_event_id = normalize_event_id(event_object.get("event_id", "")) or "NONE"
    capture_event_id = normalize_event_id(vision.get("capture_event_id", "")) or "NONE"
    vision_event_id = normalize_event_id(vision.get("vision_event_id", "")) or "NONE"
    required_class = str(required_class_name or "").strip().lower()
    auto_class = str(vision.get("auto_lock_class_name", "") or "").strip().lower()
    required_model = str(required_model_label or "").strip()
    detector_model_label = str(vision.get("detector_model_label", "") or "").strip()
    camera_source = str(vision.get("source", "") or "").strip()
    physical_camera_source = bool(
        parse_int_flag(vision.get("physical_camera_source", 0)) == 1
        and camera_source.isdigit()
        and int(camera_source) >= 0
    )
    cloud_threat_level = str(event_object.get("cloud_threat_level", "NONE") or "NONE").strip().upper()
    cloud_command_type = str(event_object.get("cloud_command_type", "NONE") or "NONE").strip().upper()
    cloud_effect = str(event_object.get("cloud_command_effect", "NONE") or "NONE").strip().upper()
    cloud_source_event_id = normalize_event_id(event_object.get("cloud_command_source_event_id", "")) or "NONE"
    cloud_contract_version = parse_positive_int(event_object.get("cloud_contract_version", 0))
    cloud_event_echo_required = parse_int_flag(event_object.get("cloud_event_echo_required", 0))
    cloud_test_no_apply = parse_int_flag(event_object.get("cloud_test_no_apply", 0))
    cloud_test_validated = parse_int_flag(event_object.get("cloud_test_validated", 0))
    cloud_test_result_no_apply = parse_int_flag(event_object.get("cloud_test_result_no_apply", 0))
    cloud_test_response_event_id = normalize_event_id(
        event_object.get("cloud_test_response_event_id", "")
    ) or "NONE"
    cloud_result_ok = parse_int_flag(event_object.get("cloud_result_ok", 0))
    cloud_result_source = str(event_object.get("cloud_result_source", "NONE") or "NONE").strip().upper()
    cloud_request_event_id = normalize_event_id(event_object.get("cloud_request_event_id", "")) or "NONE"
    cloud_expected_event_id = normalize_event_id(event_object.get("cloud_expected_event_id", "")) or "NONE"
    cloud_response_event_id = normalize_event_id(event_object.get("cloud_response_event_id", "")) or "NONE"
    cloud_result_http_status = parse_positive_int(event_object.get("cloud_result_http_status", 0))
    cloud_result_esp_error = parse_int_flag(event_object.get("cloud_result_esp_error", 0))
    cloud_result_error = str(event_object.get("cloud_result_error", "NONE") or "NONE").strip().upper()
    cloud_result_received_ms = parse_positive_int(event_object.get("cloud_result_received_ms", 0))

    checks: dict[str, bool] = {
        "event_detail_available": bool(detail_payload.get("available")),
        "event_id_exact": expected_id != "NONE" and actual_event_id == expected_id and object_event_id == expected_id,
        "capture_present": parse_positive_int(detail_payload.get("capture_count", 0)) > 0,
        "exact_capture_binding": (
            str(detail_payload.get("capture_binding_mode", "") or "") == "event_id_exact"
            and capture_event_id == expected_id
        ),
        "vision_evidence_valid": (
            str(vision.get("evidence_quality", "") or "").upper() == "VALID"
            and physical_camera_source
        ),
        "status_capture_match": (
            parse_int_flag(vision.get("status_capture_match", 0)) == 1
            and vision_event_id == expected_id
        ),
        "yolo_auto_lock": (
            str(vision.get("lock_source", "") or "").upper() == "YOLO_AUTO"
            and parse_int_flag(vision.get("automatic_lock", 0)) == 1
        ),
        "auto_lock_score": parse_float(vision.get("auto_lock_score", 0.0)) >= max(0.0, float(min_auto_lock_score)),
        "auto_lock_class": bool(auto_class) and (not required_class or auto_class == required_class),
        "detector_ready": (
            str(vision.get("detector_state", "") or "").upper() == "READY_ONNX"
            and bool(detector_model_label)
            and (not required_model or detector_model_label == required_model)
        ),
        "frame_valid": (
            parse_int_flag(vision.get("frame_content_ready", 0)) == 1
            and str(vision.get("frame_quality_reason", "") or "").upper() == "OK"
            and parse_positive_int(vision.get("frame_width", 0)) > 0
            and parse_positive_int(vision.get("frame_height", 0)) > 0
        ),
        "capture_sha256": is_sha256_hex(vision.get("capture_sha256", "")),
        "vision_evidence_sha256": is_sha256_hex(vision.get("vision_evidence_hash", "")),
        "cloud_command_applied": (
            parse_int_flag(event_object.get("cloud_online", 0)) == 1
            and parse_int_flag(event_object.get("cloud_command_applied", 0)) == 1
            and cloud_threat_level in {"HIGH", "CRITICAL"}
            and cloud_command_type == "GENERATE_ALERT"
            and cloud_effect == "ALERT_GENERATED"
        ),
        "cloud_event_match": (
            cloud_source_event_id == expected_id
            and cloud_contract_version >= 2
            and cloud_event_echo_required == 1
            and cloud_test_no_apply == 1
            and cloud_test_validated == 1
            and cloud_test_result_no_apply == 1
            and cloud_test_response_event_id == "A1-CLOUD-TEST"
            and cloud_result_ok == 1
            and cloud_result_source == "EVENT_OPENED"
            and cloud_request_event_id == expected_id
            and cloud_expected_event_id == expected_id
            and cloud_response_event_id == expected_id
            and 200 <= cloud_result_http_status < 300
            and cloud_result_esp_error == 0
            and cloud_result_error == "NONE"
            and cloud_result_received_ms > 0
        ),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "result": "PASS" if not failures else "FAIL",
        "expected_event_id": expected_id,
        "actual_event_id": actual_event_id,
        "passed_count": sum(1 for ok in checks.values() if ok),
        "total_count": len(checks),
        "failure_count": len(failures),
        "failures": failures,
        "checks": checks,
        "evidence_quality": str(vision.get("evidence_quality", "NO_CAPTURE") or "NO_CAPTURE"),
        "lock_source": str(vision.get("lock_source", "UNKNOWN") or "UNKNOWN"),
        "auto_lock_score": parse_float(vision.get("auto_lock_score", 0.0)),
        "auto_lock_class_name": str(vision.get("auto_lock_class_name", "none") or "none"),
        "detector_model_label": detector_model_label or "none",
        "required_model_label": required_model or "none",
        "source": camera_source or "NONE",
        "physical_camera_source": int(physical_camera_source),
        "capture_backend": str(vision.get("capture_backend", "UNKNOWN") or "UNKNOWN"),
        "vision_evidence_hash": str(vision.get("vision_evidence_hash", "") or ""),
        "capture_sha256": str(vision.get("capture_sha256", "") or ""),
        "cloud_threat_level": cloud_threat_level,
        "cloud_command_type": cloud_command_type,
        "cloud_command_effect": cloud_effect,
        "cloud_command_source_event_id": cloud_source_event_id,
        "cloud_contract_version": cloud_contract_version,
        "cloud_event_echo_required": cloud_event_echo_required,
        "cloud_test_no_apply": cloud_test_no_apply,
        "cloud_test_validated": cloud_test_validated,
        "cloud_test_result_no_apply": cloud_test_result_no_apply,
        "cloud_test_response_event_id": cloud_test_response_event_id,
        "cloud_result_ok": cloud_result_ok,
        "cloud_result_source": cloud_result_source,
        "cloud_request_event_id": cloud_request_event_id,
        "cloud_expected_event_id": cloud_expected_event_id,
        "cloud_response_event_id": cloud_response_event_id,
        "cloud_result_http_status": cloud_result_http_status,
        "cloud_result_esp_error": cloud_result_esp_error,
        "cloud_result_error": cloud_result_error,
        "cloud_result_received_ms": cloud_result_received_ms,
    }


def evaluate_national_first_event_freshness(
    detail_payload: dict[str, Any],
    *,
    max_age_ms: int,
    now_ms: int | None = None,
    max_future_skew_ms: int = 60_000,
) -> dict[str, Any]:
    event = detail_payload.get("event", {}) if isinstance(detail_payload, dict) else {}
    if not isinstance(event, dict):
        event = {}
    event_object = detail_payload.get("event_object_v1", {}) if isinstance(detail_payload, dict) else {}
    if not isinstance(event_object, dict):
        event_object = {}

    timestamp_ms = parse_positive_int(event.get("host_logged_ms", 0))
    timestamp_source = "event.host_logged_ms"
    if timestamp_ms <= 0:
        candidate = parse_positive_int(event_object.get("update_time", 0))
        if candidate >= 1_000_000_000_000:
            timestamp_ms = candidate
            timestamp_source = "event_object_v1.update_time"
    checked_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    raw_age_ms = checked_ms - timestamp_ms if timestamp_ms > 0 else 0
    allowed_age_ms = max(1, int(max_age_ms))
    allowed_future_skew_ms = max(0, int(max_future_skew_ms))
    checks = {
        "event_timestamp_available": timestamp_ms > 0,
        "event_not_from_future": timestamp_ms > 0 and raw_age_ms >= -allowed_future_skew_ms,
        "event_within_max_age": timestamp_ms > 0 and raw_age_ms <= allowed_age_ms,
    }
    failures: list[str] = []
    if not checks["event_timestamp_available"]:
        failures.append("event_timestamp_unavailable")
    else:
        if not checks["event_not_from_future"]:
            failures.append("event_timestamp_in_future")
        if not checks["event_within_max_age"]:
            failures.append("event_stale")
    return {
        "result": "PASS" if not failures else "FAIL",
        "event_timestamp_ms": timestamp_ms,
        "timestamp_source": timestamp_source if timestamp_ms > 0 else "NONE",
        "checked_ms": checked_ms,
        "age_ms": max(0, raw_age_ms) if timestamp_ms > 0 else 0,
        "raw_age_ms": raw_age_ms,
        "max_age_ms": allowed_age_ms,
        "max_future_skew_ms": allowed_future_skew_ms,
        "failure_count": len(failures),
        "failures": failures,
        "checks": checks,
    }


def evaluate_cloud_preflight_status(
    status_payload: dict[str, Any],
    stage: str,
) -> dict[str, Any]:
    stage_name = str(stage or "").strip().lower()
    if stage_name not in {"contract", "test"}:
        raise ValueError("cloud preflight stage must be contract or test")

    expected_test_event_id = "A1-CLOUD-TEST"
    test_response_event_id = normalize_event_id(
        status_payload.get("cloud_test_response_event_id", "")
    ) or "NONE"
    request_event_id = normalize_event_id(status_payload.get("cloud_request_event_id", "")) or "NONE"
    expected_event_id = normalize_event_id(status_payload.get("cloud_expected_event_id", "")) or "NONE"
    response_event_id = normalize_event_id(status_payload.get("cloud_response_event_id", "")) or "NONE"
    command_source_event_id = normalize_event_id(
        status_payload.get("cloud_command_source_event_id", "")
    ) or "NONE"
    current_event_id = normalize_event_id(status_payload.get("event_id", "")) or "NONE"
    result_source = str(status_payload.get("cloud_result_source", "NONE") or "NONE").strip().upper()
    result_error = str(status_payload.get("cloud_result_error", "NONE") or "NONE").strip().upper()
    result_threat_level = str(
        status_payload.get("cloud_result_threat_level", "NONE") or "NONE"
    ).strip().upper()
    result_command_type = str(
        status_payload.get("cloud_result_command_type", "NONE") or "NONE"
    ).strip().upper()
    runtime_error = str(status_payload.get("cloud_error", "NONE") or "NONE").strip().upper()
    wifi_status = str(status_payload.get("cloud_wifi_status", "UNKNOWN") or "UNKNOWN").strip().upper()
    command_effect = str(status_payload.get("cloud_command_effect", "NONE") or "NONE").strip().upper()
    http_status = parse_positive_int(status_payload.get("cloud_result_http_status", 0))
    esp_error = parse_int_flag(status_payload.get("cloud_result_esp_error", 0))

    checks: dict[str, bool] = {
        "node_status_available": bool(status_payload) and bool(status_payload.get("available", True)),
        "node_online": parse_int_flag(status_payload.get("online", 0)) == 1,
        "serial_bridge_contract_v2": parse_positive_int(
            status_payload.get("serial_bridge_contract_version", 0)
        ) >= 2,
        "web_evidence_contract_v2": parse_positive_int(
            status_payload.get("web_evidence_contract_version", 0)
        ) >= 2,
        "cloud_status_observed": all(
            key in status_payload
            for key in (
                "cloud_enabled",
                "cloud_configured",
                "cloud_wifi_status",
                "cloud_request_in_flight",
            )
        ),
        "cloud_contract_v2": parse_positive_int(status_payload.get("cloud_contract_version", 0)) >= 2,
        "cloud_event_echo_required": parse_int_flag(status_payload.get("cloud_event_echo_required", 0)) == 1,
        "cloud_test_no_apply_capability": parse_int_flag(status_payload.get("cloud_test_no_apply", 0)) == 1,
        "cloud_configured": parse_int_flag(status_payload.get("cloud_configured", 0)) == 1,
        "cloud_request_idle": parse_int_flag(status_payload.get("cloud_request_in_flight", 0)) == 0,
        "track_idle": (
            "track_active" in status_payload
            and parse_int_flag(status_payload.get("track_active", 0)) == 0
        ),
        "event_idle": (
            "event_active" in status_payload
            and "event_id" in status_payload
            and parse_int_flag(status_payload.get("event_active", 0)) == 0
            and current_event_id == "NONE"
        ),
    }

    if stage_name == "contract":
        checks.update(
            {
                "cloud_default_disabled": parse_int_flag(status_payload.get("cloud_enabled", 0)) == 0,
                "cloud_test_not_yet_validated": parse_int_flag(status_payload.get("cloud_test_validated", 0)) == 0,
                "cloud_test_raw_clear": (
                    parse_int_flag(status_payload.get("cloud_test_result_no_apply", 0)) == 0
                    and test_response_event_id == "NONE"
                    and parse_positive_int(status_payload.get("cloud_test_result_received_ms", 0)) == 0
                ),
                "cloud_result_raw_clear": (
                    parse_int_flag(status_payload.get("cloud_result_ok", 0)) == 0
                    and result_source == "NONE"
                    and request_event_id == "NONE"
                    and expected_event_id == "NONE"
                    and response_event_id == "NONE"
                    and parse_positive_int(status_payload.get("cloud_result_received_ms", 0)) == 0
                ),
            }
        )
    else:
        checks.update(
            {
                "cloud_enabled": parse_int_flag(status_payload.get("cloud_enabled", 0)) == 1,
                "cloud_wifi_connected": wifi_status == "CONNECTED",
                "cloud_online": parse_int_flag(status_payload.get("cloud_online", 0)) == 1,
                "cloud_test_validated": parse_int_flag(status_payload.get("cloud_test_validated", 0)) == 1,
                "cloud_test_no_apply_observed": parse_int_flag(
                    status_payload.get("cloud_test_result_no_apply", 0)
                ) == 1,
                "cloud_test_response_event_match": test_response_event_id == expected_test_event_id,
                "cloud_result_ok": parse_int_flag(status_payload.get("cloud_result_ok", 0)) == 1,
                "cloud_result_source_test": result_source == "TEST",
                "cloud_test_policy_threat_high": result_threat_level in {"HIGH", "CRITICAL"},
                "cloud_test_policy_generate_alert": result_command_type == "GENERATE_ALERT",
                "cloud_request_event_match": request_event_id == expected_test_event_id,
                "cloud_expected_event_match": expected_event_id == expected_test_event_id,
                "cloud_response_event_match": response_event_id == expected_test_event_id,
                "cloud_http_success": 200 <= http_status < 300,
                "cloud_esp_error_clear": esp_error == 0,
                "cloud_result_error_clear": result_error == "NONE",
                "cloud_runtime_error_clear": runtime_error == "NONE",
                "cloud_test_not_applied": (
                    parse_int_flag(status_payload.get("cloud_command_applied", 0)) == 0
                    and command_effect == "TEST_RESPONSE_VALIDATED"
                    and command_source_event_id == expected_test_event_id
                ),
                "cloud_test_result_timestamped": parse_positive_int(
                    status_payload.get("cloud_test_result_received_ms", 0)
                ) > 0,
                "cloud_result_timestamped": parse_positive_int(
                    status_payload.get("cloud_result_received_ms", 0)
                ) > 0,
            }
        )

    failures = [name for name, ok in checks.items() if not ok]
    return {
        "result": "PASS" if not failures else "FAIL",
        "stage": stage_name,
        "checked_ms": int(time.time() * 1000),
        "passed_count": sum(1 for ok in checks.values() if ok),
        "total_count": len(checks),
        "failure_count": len(failures),
        "failures": failures,
        "checks": checks,
        "values": {
            "node_id": str(status_payload.get("node_id", "NONE") or "NONE"),
            "serial_bridge_contract_version": parse_positive_int(
                status_payload.get("serial_bridge_contract_version", 0)
            ),
            "web_evidence_contract_version": parse_positive_int(
                status_payload.get("web_evidence_contract_version", 0)
            ),
            "cloud_contract_version": parse_positive_int(status_payload.get("cloud_contract_version", 0)),
            "cloud_enabled": parse_int_flag(status_payload.get("cloud_enabled", 0)),
            "cloud_configured": parse_int_flag(status_payload.get("cloud_configured", 0)),
            "cloud_wifi_status": wifi_status,
            "cloud_online": parse_int_flag(status_payload.get("cloud_online", 0)),
            "track_active": parse_int_flag(status_payload.get("track_active", 0)),
            "event_active": parse_int_flag(status_payload.get("event_active", 0)),
            "event_id": current_event_id,
            "cloud_test_validated": parse_int_flag(status_payload.get("cloud_test_validated", 0)),
            "cloud_test_result_no_apply": parse_int_flag(status_payload.get("cloud_test_result_no_apply", 0)),
            "cloud_test_response_event_id": test_response_event_id,
            "cloud_result_ok": parse_int_flag(status_payload.get("cloud_result_ok", 0)),
            "cloud_result_source": result_source,
            "cloud_result_threat_level": result_threat_level,
            "cloud_result_command_type": result_command_type,
            "cloud_request_event_id": request_event_id,
            "cloud_expected_event_id": expected_event_id,
            "cloud_response_event_id": response_event_id,
            "cloud_result_http_status": http_status,
            "cloud_result_esp_error": esp_error,
            "cloud_result_error": result_error,
            "cloud_command_applied": parse_int_flag(status_payload.get("cloud_command_applied", 0)),
            "cloud_command_effect": command_effect,
            "cloud_command_source_event_id": command_source_event_id,
        },
    }


def fetch_json(url: str, timeout_s: float) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except URLError:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def fetch_json_with_retry(url: str, timeout_s: float, retries: int, retry_interval_s: float) -> dict[str, Any]:
    attempts = max(1, retries)
    for index in range(attempts):
        payload = fetch_json(url, timeout_s)
        if payload:
            return payload
        if index < attempts - 1:
            time.sleep(max(0.0, retry_interval_s))
    return {}


def pick_latest_event_id(
    status_payload: dict[str, Any],
    node_events_payload: dict[str, Any],
    event_store_payload: dict[str, Any],
) -> str:
    for payload in (event_store_payload, node_events_payload):
        records = payload.get("records", []) if isinstance(payload, dict) else []
        if not isinstance(records, list):
            continue
        for item in records:
            if not isinstance(item, dict):
                continue
            event_id = normalize_event_id(item.get("event_id", ""))
            if event_id and event_id != "NONE":
                return event_id

    return normalize_event_id(status_payload.get("event_id", ""))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="4.11 single-node evidence closure gate: status + events + captures + exports + USB camera readiness."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Vision web server base URL")
    parser.add_argument("--timeout-s", type=float, default=2.0, help="HTTP request timeout in seconds")
    parser.add_argument("--api-retries", type=int, default=3, help="Retry count for web API checks")
    parser.add_argument("--api-retry-interval-s", type=float, default=0.35, help="Retry interval for web API checks")
    parser.add_argument(
        "--cloud-preflight-only",
        action="store_true",
        help="Only read /api/node-status and validate the selected cloud preflight stage",
    )
    parser.add_argument(
        "--cloud-preflight-stage",
        choices=("contract", "test"),
        default="contract",
        help="Cloud preflight stage used with --cloud-preflight-only",
    )
    parser.add_argument(
        "--cloud-preflight-report-file",
        type=Path,
        default=Path("captures/latest_cloud_preflight_report.json"),
        help="Independent report path for cloud preflight-only checks",
    )
    parser.add_argument(
        "--cloud-preflight-wait-s",
        type=float,
        default=0.0,
        help="Maximum time to poll node status until the selected cloud preflight passes",
    )
    parser.add_argument(
        "--cloud-preflight-poll-interval-s",
        type=float,
        default=0.5,
        help="Polling interval used while waiting for cloud preflight completion",
    )
    parser.add_argument("--node-status-file", type=Path, default=Path("captures/latest_node_status.json"))
    parser.add_argument("--node-events-file", type=Path, default=Path("captures/latest_node_events.json"))
    parser.add_argument("--node-event-store-file", type=Path, default=Path("captures/latest_node_event_store.json"))
    parser.add_argument("--vision-status-file", type=Path, default=Path("captures/latest_status.json"))
    parser.add_argument("--capture-log-file", type=Path, default=Path("captures/capture_records.csv"))
    parser.add_argument(
        "--usb-readiness-file",
        type=Path,
        default=Path("captures/latest_usb_camera_readiness_report.json"),
    )
    parser.add_argument("--min-events", type=int, default=1, help="Minimum node event count required")
    parser.add_argument("--min-event-store", type=int, default=1, help="Minimum event store count required")
    parser.add_argument("--min-captures", type=int, default=1, help="Minimum capture record count required")
    parser.add_argument(
        "--min-bound-captures",
        type=int,
        default=1,
        help="Minimum capture records with non-NONE event_id required",
    )
    parser.add_argument(
        "--require-vision-lock",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Require at least min vision lock evidence hits from event store/status payloads",
    )
    parser.add_argument(
        "--min-vision-lock-hits",
        type=int,
        default=1,
        help="Minimum vision lock evidence hits when --require-vision-lock is enabled",
    )
    parser.add_argument(
        "--require-capture-ready",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Require at least min capture-ready evidence hits from event store/status payloads",
    )
    parser.add_argument(
        "--min-capture-ready-hits",
        type=int,
        default=1,
        help="Minimum capture-ready evidence hits when --require-capture-ready is enabled",
    )
    parser.add_argument(
        "--capture-ready-last-capture-max-age-ms",
        type=int,
        default=900000,
        help="Treat recent last_capture_timestamp_ms as capture-ready evidence when age <= this value; set 0 to disable age limit",
    )
    parser.add_argument(
        "--require-national-first-evidence",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Require exact YOLO auto-lock, valid frame, hashes, and same-event cloud downlink evidence",
    )
    parser.add_argument(
        "--national-first-min-auto-lock-score",
        type=float,
        default=0.45,
        help="Minimum YOLO auto-lock score accepted by the national-first evidence gate",
    )
    parser.add_argument(
        "--national-first-required-class",
        default="drone",
        help="Required YOLO auto-lock class name for the national-first evidence gate",
    )
    parser.add_argument(
        "--national-first-max-event-age-ms",
        type=int,
        default=900_000,
        help="Maximum host-recorded event age accepted by the national-first gate",
    )
    parser.add_argument("--allow-no-export", action="store_true", help="Allow export history count == 0")
    parser.add_argument(
        "--auto-export-if-missing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When export history is empty, auto-call /api/node-event-export once by latest_event_id",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("captures/latest_single_node_evidence_closure_report.json"),
    )
    args = parser.parse_args()
    if bool(args.require_national_first_evidence) and int(args.national_first_max_event_age_ms) <= 0:
        parser.error("--national-first-max-event-age-ms must be greater than zero in strict mode")

    if bool(args.cloud_preflight_only):
        base_url = str(args.base_url or "").strip().rstrip("/")
        wait_timeout_s = max(0.0, float(args.cloud_preflight_wait_s))
        poll_interval_s = max(0.0, float(args.cloud_preflight_poll_interval_s))
        wait_started = time.monotonic()
        attempt_count = 0
        cloud_preflight: dict[str, Any] = {}
        while True:
            status_payload = fetch_json_with_retry(
                f"{base_url}/api/node-status",
                args.timeout_s,
                args.api_retries,
                args.api_retry_interval_s,
            )
            attempt_count += 1
            cloud_preflight = evaluate_cloud_preflight_status(status_payload, args.cloud_preflight_stage)
            elapsed_s = time.monotonic() - wait_started
            if cloud_preflight["result"] == "PASS" or elapsed_s >= wait_timeout_s:
                break
            remaining_s = max(0.0, wait_timeout_s - elapsed_s)
            time.sleep(min(poll_interval_s, remaining_s))

        waited_ms = max(0, int((time.monotonic() - wait_started) * 1000))
        cloud_report = {
            "schema_version": "cloud_preflight_v1",
            "base_url": base_url,
            "attempt_count": attempt_count,
            "wait_timeout_s": wait_timeout_s,
            "poll_interval_s": poll_interval_s,
            "waited_ms": waited_ms,
            **cloud_preflight,
        }
        cloud_report_file = resolve_path(args.cloud_preflight_report_file)
        write_json(cloud_report_file, cloud_report)
        print("Cloud Preflight Report")
        print(f"result={cloud_report['result']}")
        print(f"stage={cloud_report['stage']}")
        print(
            "checks="
            f"{cloud_report['passed_count']}/{cloud_report['total_count']}"
        )
        print(f"attempts={cloud_report['attempt_count']}")
        print(f"waited_ms={cloud_report['waited_ms']}")
        print(f"report_file={cloud_report_file.as_posix()}")
        for item in cloud_report["failures"]:
            print(f"- {item}")
        return 0 if cloud_report["result"] == "PASS" else 2

    node_status_file = resolve_path(args.node_status_file)
    node_events_file = resolve_path(args.node_events_file)
    node_event_store_file = resolve_path(args.node_event_store_file)
    vision_status_file = resolve_path(args.vision_status_file)
    capture_log_file = resolve_path(args.capture_log_file)
    usb_readiness_file = resolve_path(args.usb_readiness_file)
    report_file = resolve_path(args.report_file)

    node_status = load_json(node_status_file)
    node_events = load_json(node_events_file)
    event_store = load_json(node_event_store_file)
    vision_status = load_json(vision_status_file)
    usb_readiness = load_json(usb_readiness_file)
    capture_rows = load_csv_rows(capture_log_file)

    failures: list[str] = []
    warnings: list[str] = []

    event_count = int(node_events.get("count", 0) or 0)
    event_store_count = int(event_store.get("count", 0) or 0)
    capture_count = len(capture_rows)
    bound_capture_count = 0
    for row in capture_rows:
        event_id = normalize_event_id(row.get("event_id", ""))
        if event_id and event_id != "NONE":
            bound_capture_count += 1

    latest_event_id = pick_latest_event_id(vision_status, node_events, event_store)
    node_id = str(node_status.get("node_id", "") or "").strip()
    vision_evidence = evaluate_vision_evidence(
        node_status,
        vision_status,
        event_store,
        latest_event_id,
        capture_ready_last_capture_max_age_ms=max(0, int(args.capture_ready_last_capture_max_age_ms)),
    )
    vision_lock_hits = int(vision_evidence.get("vision_lock_hits", 0) or 0)
    capture_ready_hits = int(vision_evidence.get("capture_ready_hits", 0) or 0)

    if not node_status:
        failures.append("node_status_unavailable")
    elif not node_id:
        failures.append("node_id_unavailable")

    if event_count < max(0, args.min_events):
        failures.append(f"node_events_count_below_min:{event_count}<{args.min_events}")
    if event_store_count < max(0, args.min_event_store):
        failures.append(f"event_store_count_below_min:{event_store_count}<{args.min_event_store}")
    if capture_count < max(0, args.min_captures):
        failures.append(f"capture_count_below_min:{capture_count}<{args.min_captures}")
    if bound_capture_count < max(0, args.min_bound_captures):
        failures.append(f"bound_capture_count_below_min:{bound_capture_count}<{args.min_bound_captures}")
    if not latest_event_id or latest_event_id == "NONE":
        failures.append("latest_event_id_unavailable")
    if bool(args.require_vision_lock):
        min_vision_lock_hits = max(1, int(args.min_vision_lock_hits))
        if vision_lock_hits < min_vision_lock_hits:
            failures.append(f"vision_lock_evidence_below_min:{vision_lock_hits}<{min_vision_lock_hits}")
    if bool(args.require_capture_ready):
        min_capture_ready_hits = max(1, int(args.min_capture_ready_hits))
        if capture_ready_hits < min_capture_ready_hits:
            failures.append(f"capture_ready_evidence_below_min:{capture_ready_hits}<{min_capture_ready_hits}")

    usb_result = str(usb_readiness.get("result", "UNKNOWN")).upper()
    usb_ready_count = int((usb_readiness.get("probe", {}) or {}).get("ready_count", 0) if isinstance(usb_readiness, dict) else 0)
    if usb_result != "PASS":
        failures.append(f"usb_readiness_result_not_pass:{usb_result}")
    if usb_ready_count <= 0:
        failures.append("usb_camera_ready_count_zero")

    health_payload = fetch_json_with_retry(
        f"{args.base_url}/api/health",
        args.timeout_s,
        args.api_retries,
        args.api_retry_interval_s,
    )
    health_ok = bool(health_payload.get("ok"))
    export_payload: dict[str, Any] = {}
    export_count = 0
    export_latest_file_name = ""
    export_latest_event_id = "NONE"
    auto_export_attempted = False
    auto_export_ok = False
    auto_export_event_id = ""
    export_create_payload: dict[str, Any] = {}
    export_detail_payload: dict[str, Any] = {}
    export_detail_available = False
    export_detail_event_id = "NONE"
    detail_payload: dict[str, Any] = {}
    detail_available = False
    detail_capture_count = 0
    national_first_evidence: dict[str, Any] = {
        "result": "SKIPPED",
        "passed_count": 0,
        "total_count": 15,
        "failure_count": 0,
        "failures": [],
        "checks": {},
    }
    national_first_event_freshness: dict[str, Any] = {
        "result": "SKIPPED",
        "event_timestamp_ms": 0,
        "timestamp_source": "NONE",
        "checked_ms": int(time.time() * 1000),
        "age_ms": 0,
        "raw_age_ms": 0,
        "max_age_ms": max(1, int(args.national_first_max_event_age_ms)),
        "max_future_skew_ms": 60_000,
        "failure_count": 0,
        "failures": [],
        "checks": {},
    }
    strict_export_snapshot_evidence: dict[str, Any] = {
        "result": "SKIPPED",
        "passed_count": 0,
        "total_count": 15,
        "failure_count": 0,
        "failures": [],
        "checks": {},
    }
    strict_export_hash_ok = False
    strict_export_vision_hash_ok = False

    if not health_ok:
        failures.append("web_health_unavailable")
        warnings.append("skip_api_checks_due_to_web_health_unavailable")
    else:
        strict_required = bool(args.require_national_first_evidence)
        capture_match_mode = "strict" if strict_required else "fallback"
        if latest_event_id and latest_event_id != "NONE":
            detail_payload = fetch_json_with_retry(
                f"{args.base_url}/api/node-event-detail?event_id={quote(latest_event_id)}"
                f"&capture_match_mode={capture_match_mode}",
                args.timeout_s,
                args.api_retries,
                args.api_retry_interval_s,
            )
        detail_available = bool(detail_payload.get("available")) if detail_payload else False
        detail_capture_count = int(detail_payload.get("capture_count", 0) or 0) if detail_payload else 0
        if not detail_payload:
            failures.append("node_event_detail_api_unavailable")
        elif not detail_available:
            failures.append("node_event_detail_not_available")

        if strict_required:
            national_first_event_freshness = evaluate_national_first_event_freshness(
                detail_payload,
                max_age_ms=int(args.national_first_max_event_age_ms),
            )
            for item in national_first_event_freshness.get("failures", []):
                failures.append(f"national_first_event_freshness:{item}")
            national_first_evidence = evaluate_national_first_event_detail(
                detail_payload,
                latest_event_id,
                min_auto_lock_score=float(args.national_first_min_auto_lock_score),
                required_class_name=str(args.national_first_required_class),
            )
            for item in national_first_evidence.get("failures", []):
                failures.append(f"national_first_evidence:{item}")

            if (
                national_first_evidence.get("result") == "PASS"
                and national_first_event_freshness.get("result") == "PASS"
            ):
                auto_export_attempted = True
                auto_export_event_id = latest_event_id
                export_create_payload = fetch_json_with_retry(
                    f"{args.base_url}/api/node-event-export?event_id={quote(latest_event_id)}"
                    "&capture_match_mode=strict",
                    args.timeout_s,
                    args.api_retries,
                    args.api_retry_interval_s,
                )
                export_create_detail = export_create_payload.get("event_detail", {})
                if not isinstance(export_create_detail, dict):
                    export_create_detail = {}
                strict_export_snapshot_evidence = evaluate_national_first_event_detail(
                    export_create_detail,
                    latest_event_id,
                    min_auto_lock_score=float(args.national_first_min_auto_lock_score),
                    required_class_name=str(args.national_first_required_class),
                )
                auto_export_ok = (
                    bool(export_create_payload.get("ok"))
                    and bool(export_create_payload.get("available"))
                    and bool(export_create_payload.get("export_saved"))
                    and normalize_event_id(export_create_payload.get("event_id", "")) == latest_event_id
                    and str(export_create_payload.get("capture_match_mode", "") or "").lower() == "strict"
                    and strict_export_snapshot_evidence.get("result") == "PASS"
                )
                for item in strict_export_snapshot_evidence.get("failures", []):
                    failures.append(f"national_first_export_snapshot:{item}")
                if not auto_export_ok:
                    failures.append(f"national_first_strict_export_failed:{latest_event_id}")
                else:
                    time.sleep(0.15)

        export_payload = fetch_json_with_retry(
            f"{args.base_url}/api/node-event-exports?limit=5",
            args.timeout_s,
            args.api_retries,
            args.api_retry_interval_s,
        )
        export_count = int(export_payload.get("count", 0) or 0) if export_payload else 0

        if (
            export_count <= 0
            and not strict_required
            and bool(args.auto_export_if_missing)
            and latest_event_id
            and latest_event_id != "NONE"
        ):
            auto_export_attempted = True
            auto_export_event_id = latest_event_id
            export_create_payload = fetch_json_with_retry(
                f"{args.base_url}/api/node-event-export?event_id={quote(latest_event_id)}",
                args.timeout_s,
                args.api_retries,
                args.api_retry_interval_s,
            )
            auto_export_ok = bool(export_create_payload.get("available")) and bool(export_create_payload.get("ok"))
            # 自动导出成功后立即重新读取导出列表，确保结果反映最新状态。
            if auto_export_ok:
                time.sleep(0.15)
                export_payload = fetch_json_with_retry(
                    f"{args.base_url}/api/node-event-exports?limit=5",
                    args.timeout_s,
                    args.api_retries,
                    args.api_retry_interval_s,
                )
                export_count = int(export_payload.get("count", 0) or 0) if export_payload else 0

        latest_export = export_payload.get("latest", {}) if isinstance(export_payload, dict) else {}
        if isinstance(latest_export, dict):
            export_latest_file_name = str(latest_export.get("file_name", "") or "").strip()
            export_latest_event_id = normalize_event_id(latest_export.get("event_id", "")) or "NONE"

        if export_count <= 0:
            if strict_required or not args.allow_no_export:
                failures.append("node_event_exports_unavailable")
            else:
                warnings.append("node_event_exports_unavailable_allowed")
        if auto_export_attempted and not auto_export_ok:
            if strict_required:
                if not any(item.startswith("national_first_strict_export_failed:") for item in failures):
                    failures.append(f"national_first_strict_export_failed:{auto_export_event_id}")
            else:
                warnings.append(f"auto_export_attempt_failed:{auto_export_event_id}")

        if export_count > 0:
            if not export_latest_file_name:
                failures.append("node_event_exports_latest_file_missing")
            else:
                export_detail_payload = fetch_json_with_retry(
                    f"{args.base_url}/api/node-event-export-detail?file_name={quote(export_latest_file_name)}",
                    args.timeout_s,
                    args.api_retries,
                    args.api_retry_interval_s,
                )
                if not export_detail_payload:
                    failures.append("node_event_export_detail_api_unavailable")
                else:
                    export_detail_available = bool(export_detail_payload.get("available"))
                    export_detail_event_id = normalize_event_id(export_detail_payload.get("event_id", "")) or "NONE"
                    if not export_detail_available:
                        failures.append("node_event_export_detail_not_available")
                    if (
                        export_latest_event_id
                        and export_latest_event_id != "NONE"
                        and export_detail_event_id != export_latest_event_id
                    ):
                        mismatch = (
                            f"node_event_export_detail_event_id_mismatch:"
                            f"{export_latest_event_id}!={export_detail_event_id}"
                        )
                        if strict_required:
                            failures.append(mismatch)
                        else:
                            warnings.append(mismatch)

        if strict_required:
            if export_latest_event_id != latest_event_id:
                failures.append(
                    f"national_first_latest_export_event_id_mismatch:{export_latest_event_id}!={latest_event_id}"
                )
            if export_detail_event_id != latest_event_id:
                failures.append(
                    f"national_first_export_detail_event_id_mismatch:{export_detail_event_id}!={latest_event_id}"
                )

            export_event_detail = (
                export_detail_payload.get("event_detail", {})
                if isinstance(export_detail_payload, dict)
                else {}
            )
            if not isinstance(export_event_detail, dict):
                export_event_detail = {}
            export_event_object = export_event_detail.get("event_object_v1", {})
            if not isinstance(export_event_object, dict):
                export_event_object = {}
            export_vision_hash = str(export_event_object.get("vision_evidence_hash", "") or "")
            expected_vision_hash = str(
                strict_export_snapshot_evidence.get(
                    "vision_evidence_hash",
                    national_first_evidence.get("vision_evidence_hash", ""),
                )
                or ""
            )
            strict_export_hash_ok = (
                normalize_event_id(export_event_object.get("event_id", "")) == latest_event_id
                and is_sha256_hex(export_event_object.get("evidence_hash", ""))
            )
            strict_export_vision_hash_ok = (
                is_sha256_hex(export_vision_hash)
                and export_vision_hash == expected_vision_hash
            )
            if not strict_export_hash_ok:
                failures.append("national_first_export_evidence_hash_invalid")
            if not strict_export_vision_hash_ok:
                failures.append("national_first_export_vision_hash_mismatch")

    report = {
        "checked_ms": int(time.time() * 1000),
        "result": "PASS" if not failures else "FAIL",
        "files": {
            "node_status_file": node_status_file.as_posix(),
            "node_events_file": node_events_file.as_posix(),
            "node_event_store_file": node_event_store_file.as_posix(),
            "vision_status_file": vision_status_file.as_posix(),
            "capture_log_file": capture_log_file.as_posix(),
            "usb_readiness_file": usb_readiness_file.as_posix(),
        },
        "counts": {
            "node_events_count": event_count,
            "event_store_count": event_store_count,
            "capture_count": capture_count,
            "bound_capture_count": bound_capture_count,
            "node_event_exports_count": export_count,
            "node_event_exports_replay_detail_available": 1 if export_detail_available else 0,
            "detail_capture_count": detail_capture_count,
            "usb_camera_ready_count": usb_ready_count,
            "vision_lock_hits": vision_lock_hits,
            "capture_ready_hits": capture_ready_hits,
            "vision_scope_record_count": int(vision_evidence.get("scope_record_count", 0) or 0),
            "status_last_capture_hit": int(vision_evidence.get("status_last_capture_hit", 0) or 0),
            "status_last_capture_age_ms": int(vision_evidence.get("status_last_capture_age_ms", 0) or 0),
            "national_first_checks_passed": int(national_first_evidence.get("passed_count", 0) or 0),
            "national_first_checks_total": int(national_first_evidence.get("total_count", 15) or 15),
            "strict_export_snapshot_checks_passed": int(
                strict_export_snapshot_evidence.get("passed_count", 0) or 0
            ),
            "strict_export_snapshot_checks_total": int(
                strict_export_snapshot_evidence.get("total_count", 15) or 15
            ),
        },
        "latest_event_id": latest_event_id or "NONE",
        "node_id": node_id or "NONE",
        "latest_export_file_name": export_latest_file_name or "",
        "latest_export_event_id": export_latest_event_id or "NONE",
        "checks": {
            "web_health_ok": health_ok,
            "node_status_ok": bool(node_status),
            "usb_readiness_ok": usb_result == "PASS" and usb_ready_count > 0,
            "event_detail_ok": detail_available,
            "exports_ok": export_count > 0,
            "export_detail_ok": export_detail_available,
            "vision_lock_evidence_ok": (not bool(args.require_vision_lock)) or (vision_lock_hits >= max(1, int(args.min_vision_lock_hits))),
            "capture_ready_evidence_ok": (not bool(args.require_capture_ready)) or (capture_ready_hits >= max(1, int(args.min_capture_ready_hits))),
            "auto_export_attempted": auto_export_attempted,
            "auto_export_ok": auto_export_ok,
            "national_first_evidence_ok": (
                not bool(args.require_national_first_evidence)
                or national_first_evidence.get("result") == "PASS"
            ),
            "national_first_event_fresh_ok": (
                not bool(args.require_national_first_evidence)
                or national_first_event_freshness.get("result") == "PASS"
            ),
            "strict_export_hash_ok": (
                not bool(args.require_national_first_evidence) or strict_export_hash_ok
            ),
            "strict_export_vision_hash_ok": (
                not bool(args.require_national_first_evidence) or strict_export_vision_hash_ok
            ),
            "strict_export_snapshot_evidence_ok": (
                not bool(args.require_national_first_evidence)
                or strict_export_snapshot_evidence.get("result") == "PASS"
            ),
        },
        "vision_requirements": {
            "require_vision_lock": bool(args.require_vision_lock),
            "min_vision_lock_hits": max(1, int(args.min_vision_lock_hits)),
            "require_capture_ready": bool(args.require_capture_ready),
            "min_capture_ready_hits": max(1, int(args.min_capture_ready_hits)),
            "capture_ready_last_capture_max_age_ms": max(0, int(args.capture_ready_last_capture_max_age_ms)),
            "scope_event_id": str(vision_evidence.get("scope_event_id", "NONE") or "NONE"),
            "require_national_first_evidence": bool(args.require_national_first_evidence),
            "national_first_min_auto_lock_score": max(0.0, float(args.national_first_min_auto_lock_score)),
            "national_first_required_class": str(args.national_first_required_class),
            "national_first_max_event_age_ms": max(1, int(args.national_first_max_event_age_ms)),
        },
        "national_first_evidence": national_first_evidence,
        "national_first_event_freshness": national_first_event_freshness,
        "strict_export_snapshot_evidence": strict_export_snapshot_evidence,
        "auto_export": {
            "enabled": bool(args.auto_export_if_missing) or bool(args.require_national_first_evidence),
            "forced_by_national_first": bool(args.require_national_first_evidence),
            "attempted": auto_export_attempted,
            "ok": auto_export_ok,
            "event_id": auto_export_event_id,
        },
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "api_payloads": {
            "node_event_exports_latest": export_payload.get("latest", {}) if isinstance(export_payload, dict) else {},
            "node_event_detail": detail_payload,
            "node_event_export_create": export_create_payload,
            "node_event_export_detail": export_detail_payload,
        },
    }
    write_json(report_file, report)

    print("Single Node Evidence Closure Report")
    print(f"result={report['result']}")
    print(f"latest_event_id={report['latest_event_id']}")
    print(f"node_id={report['node_id']}")
    print(
        "counts="
        f"events:{event_count},store:{event_store_count},captures:{capture_count},"
        f"bound_captures:{bound_capture_count},exports:{export_count},"
        f"export_replay_detail:{1 if export_detail_available else 0},"
        f"detail_captures:{detail_capture_count},"
        f"usb_ready:{usb_ready_count},"
        f"vision_lock_hits:{vision_lock_hits},"
        f"capture_ready_hits:{capture_ready_hits}"
    )
    print(
        "national_first_evidence="
        f"{national_first_evidence.get('result', 'SKIPPED')} "
        f"{national_first_evidence.get('passed_count', 0)}/"
        f"{national_first_evidence.get('total_count', 15)}"
    )
    print(
        "national_first_event_freshness="
        f"{national_first_event_freshness.get('result', 'SKIPPED')} "
        f"age_ms:{national_first_event_freshness.get('age_ms', 0)} "
        f"max_age_ms:{national_first_event_freshness.get('max_age_ms', 0)}"
    )
    print(f"strict_export_hash_ok={1 if strict_export_hash_ok else 0}")
    print(f"strict_export_vision_hash_ok={1 if strict_export_vision_hash_ok else 0}")
    print(
        "strict_export_snapshot="
        f"{strict_export_snapshot_evidence.get('result', 'SKIPPED')} "
        f"{strict_export_snapshot_evidence.get('passed_count', 0)}/"
        f"{strict_export_snapshot_evidence.get('total_count', 15)}"
    )
    print(f"failure_count={report['failure_count']}")
    print(f"warning_count={report['warning_count']}")
    print(f"report_file={report_file.as_posix()}")
    for item in failures:
        print(f"- {item}")
    for item in warnings:
        print(f"- {item}")

    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
