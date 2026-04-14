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
    export_detail_payload: dict[str, Any] = {}
    export_detail_available = False
    export_detail_event_id = "NONE"
    detail_payload: dict[str, Any] = {}
    detail_available = False
    detail_capture_count = 0

    if not health_ok:
        failures.append("web_health_unavailable")
        warnings.append("skip_api_checks_due_to_web_health_unavailable")
    else:
        export_payload = fetch_json_with_retry(
            f"{args.base_url}/api/node-event-exports?limit=5",
            args.timeout_s,
            args.api_retries,
            args.api_retry_interval_s,
        )
        export_count = int(export_payload.get("count", 0) or 0) if export_payload else 0

        if (
            export_count <= 0
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

        if export_count <= 0 and not args.allow_no_export:
            failures.append("node_event_exports_unavailable")
        if export_count <= 0 and args.allow_no_export:
            warnings.append("node_event_exports_unavailable_allowed")
        if auto_export_attempted and not auto_export_ok:
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
                        warnings.append(
                            f"node_event_export_detail_event_id_mismatch:{export_latest_event_id}!={export_detail_event_id}"
                        )

        if latest_event_id and latest_event_id != "NONE":
            detail_payload = fetch_json_with_retry(
                f"{args.base_url}/api/node-event-detail?event_id={quote(latest_event_id)}",
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
        },
        "vision_requirements": {
            "require_vision_lock": bool(args.require_vision_lock),
            "min_vision_lock_hits": max(1, int(args.min_vision_lock_hits)),
            "require_capture_ready": bool(args.require_capture_ready),
            "min_capture_ready_hits": max(1, int(args.min_capture_ready_hits)),
            "capture_ready_last_capture_max_age_ms": max(0, int(args.capture_ready_last_capture_max_age_ms)),
            "scope_event_id": str(vision_evidence.get("scope_event_id", "NONE") or "NONE"),
        },
        "auto_export": {
            "enabled": bool(args.auto_export_if_missing),
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
