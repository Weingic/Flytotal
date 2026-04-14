# ????? Node A ?????????????????/??????????????????
import argparse
import json
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

STATUS_REQUIRED_FIELDS = (
    "node_id",
    "node_zone",
    "node_role",
    "main_state",
    "hunter_state",
    "gimbal_state",
    "rid_status",
    "risk_score",
    "risk_level",
    "track_id",
    "track_active",
    "track_confirmed",
    "x_mm",
    "y_mm",
    "event_active",
    "event_id",
    "vision_state",
    "vision_locked",
    "capture_ready",
    "uplink_state",
    "timestamp_ms",
    "last_update_ms",
)

EVENT_REQUIRED_FIELDS = (
    "source_type",
    "timestamp_ms",
    "node_id",
    "zone",
    "event_id",
    "reason",
    "event_level",
    "event_status",
    "track_id",
    "risk_score",
    "source_node",
)

ALLOWED_RISK_LEVELS = {"NONE", "NORMAL", "SUSPICIOUS", "HIGH_RISK", "EVENT"}
ALLOWED_EVENT_STATUS = {"NONE", "OPEN", "CLOSED"}
ALLOWED_EVENT_LEVEL = {"NONE", "INFO", "WARN", "CRITICAL"}
ALLOWED_EVENT_SOURCE = {"UPLINK,EVENT", "LASTEVENT"}


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def missing_fields(payload: dict[str, Any], required_fields: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        if field not in payload:
            missing.append(field)
            continue
        value = payload.get(field)
        if value is None:
            missing.append(field)
            continue
        if isinstance(value, str) and value.strip() == "":
            missing.append(field)
    return missing


def validate_status_payload(status: dict[str, Any]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    if not status:
        return ["status_payload_unavailable"], warnings

    missing = missing_fields(status, STATUS_REQUIRED_FIELDS)
    if missing:
        failures.append(f"status_missing_fields: {','.join(missing)}")

    risk_level = str(status.get("risk_level", "NONE")).upper()
    if risk_level not in ALLOWED_RISK_LEVELS:
        failures.append(f"status_risk_level_invalid: {risk_level}")

    for field in ("track_active", "track_confirmed", "event_active", "vision_locked", "capture_ready"):
        value = status.get(field)
        if value not in (0, 1):
            failures.append(f"status_flag_invalid: {field}={value}")

    node_id = str(status.get("node_id", "")).strip()
    if not node_id:
        failures.append("status_node_id_empty")

    consistency_status = str(status.get("consistency_status", "UNKNOWN")).upper()
    if consistency_status not in {"OK", "WARN", "UNKNOWN"}:
        warnings.append(f"status_consistency_status_unexpected: {consistency_status}")

    return failures, warnings


def validate_event_payload(events_payload: dict[str, Any], allow_no_event: bool) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    if not events_payload:
        return ["event_payload_unavailable"], warnings

    latest = events_payload.get("latest")
    if latest is None:
        if allow_no_event:
            warnings.append("event_latest_unavailable_allowed")
            return failures, warnings
        return ["event_latest_unavailable"], warnings

    if not isinstance(latest, dict):
        return ["event_latest_invalid_type"], warnings

    missing = missing_fields(latest, EVENT_REQUIRED_FIELDS)
    if missing:
        failures.append(f"event_missing_fields: {','.join(missing)}")

    source_type = str(latest.get("source_type", "")).upper()
    if source_type and source_type not in ALLOWED_EVENT_SOURCE:
        failures.append(f"event_source_type_invalid: {source_type}")

    event_status = str(latest.get("event_status", "NONE")).upper()
    if event_status not in ALLOWED_EVENT_STATUS:
        failures.append(f"event_status_invalid: {event_status}")

    event_level = str(latest.get("event_level", "NONE")).upper()
    if event_level not in ALLOWED_EVENT_LEVEL:
        failures.append(f"event_level_invalid: {event_level}")

    return failures, warnings


def build_report(
    status_path: Path,
    events_path: Path,
    status_failures: list[str],
    event_failures: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    checked_ms = int(time.time() * 1000)
    failures = status_failures + event_failures
    result = "PASS" if not failures else "FAIL"
    return {
        "checked_ms": checked_ms,
        "result": result,
        "status_file": status_path.as_posix(),
        "events_file": events_path.as_posix(),
        "status_required_field_count": len(STATUS_REQUIRED_FIELDS),
        "event_required_field_count": len(EVENT_REQUIRED_FIELDS),
        "status_failures": status_failures,
        "event_failures": event_failures,
        "warnings": warnings,
        "failure_count": len(failures),
    }


def update_acceptance_snapshot(
    snapshot_path: Path,
    report_path: Path,
    report: dict[str, Any],
) -> None:
    snapshot = load_json(snapshot_path)
    if not snapshot:
        snapshot = {"ok": True, "available": False}

    checked_ms = int(report.get("checked_ms", int(time.time() * 1000)) or int(time.time() * 1000))
    contract_result = str(report.get("result", "UNKNOWN")).upper()
    contract_ok = contract_result == "PASS"

    suite_ok = bool(snapshot.get("suite_ok"))
    if "suite_ok" not in snapshot:
        session_path = resolve_path(Path("captures/latest_test_session.json"))
        session_payload = load_json(session_path)
        suite_name = str(session_payload.get("suite_name", "")).strip()
        suite_report = session_payload.get("suite_report", {})
        if isinstance(suite_report, dict):
            suite_total = int(suite_report.get("total_checks", 0) or 0)
            suite_failed = int(suite_report.get("failed", session_payload.get("suite_failed", 0)) or 0)
            suite_ok = suite_total > 0 and suite_failed == 0
            if suite_name:
                snapshot["suite_name"] = suite_name
                snapshot["suite_total_checks"] = suite_total
                snapshot["suite_passed"] = int(
                    suite_report.get("passed", session_payload.get("suite_passed", 0)) or 0
                )
                snapshot["suite_failed"] = suite_failed
                snapshot["suite_ok"] = suite_ok

    evidence_ready = bool(snapshot.get("evidence_ready"))
    evidence_path_text = str(snapshot.get("joint_evidence_file", "")).strip()
    if not evidence_path_text:
        default_evidence_path = resolve_path(Path("captures/latest_joint_chain_evidence.json"))
        evidence_path_text = default_evidence_path.as_posix()
        snapshot["joint_evidence_file"] = evidence_path_text
    if evidence_path_text:
        evidence_path = resolve_path(Path(evidence_path_text))
        evidence_payload = load_json(evidence_path)
        if evidence_payload:
            evidence_ready = bool(evidence_payload.get("evidence_ready"))
            if "suite_name" not in snapshot:
                snapshot["suite_name"] = str(evidence_payload.get("suite_name", "")).strip()
            if "suite_total_checks" not in snapshot:
                snapshot["suite_total_checks"] = int(evidence_payload.get("suite_total_checks", 0) or 0)
            if "suite_passed" not in snapshot:
                snapshot["suite_passed"] = int(evidence_payload.get("suite_passed", 0) or 0)
            if "suite_failed" not in snapshot:
                snapshot["suite_failed"] = int(evidence_payload.get("suite_failed", 0) or 0)
            if "suite_ok" not in snapshot and "suite_total_checks" in snapshot and "suite_failed" in snapshot:
                snapshot["suite_ok"] = bool(
                    int(snapshot.get("suite_total_checks", 0) or 0) > 0
                    and int(snapshot.get("suite_failed", 0) or 0) == 0
                )
                suite_ok = bool(snapshot.get("suite_ok"))

    snapshot["ok"] = True
    snapshot["updated_ms"] = int(time.time() * 1000)
    snapshot["contract_report_file"] = report_path.as_posix()
    snapshot["contract_result"] = contract_result
    snapshot["contract_checked_ms"] = checked_ms
    snapshot["contract_ok"] = contract_ok
    snapshot["evidence_ready"] = evidence_ready
    has_suite_signal = bool(str(snapshot.get("suite_name", "")).strip()) or int(
        snapshot.get("suite_total_checks", 0) or 0
    ) > 0
    has_evidence_signal = bool(str(snapshot.get("joint_evidence_file", "")).strip())
    has_contract_signal = contract_result in {"PASS", "FAIL"}
    snapshot["available"] = bool(has_suite_signal or has_evidence_signal or has_contract_signal)
    snapshot["deliverable_ready"] = bool(suite_ok and evidence_ready and contract_ok)

    write_json(snapshot_path, snapshot)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Node A status/event packet contracts from bridge JSON outputs."
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=Path("captures/latest_node_status.json"),
        help="Bridge normalized status JSON file",
    )
    parser.add_argument(
        "--events-file",
        type=Path,
        default=Path("captures/latest_node_events.json"),
        help="Bridge normalized event history JSON file",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("captures/latest_uplink_contract_report.json"),
        help="Output JSON report path",
    )
    parser.add_argument(
        "--acceptance-snapshot-file",
        type=Path,
        default=Path("captures/latest_acceptance_snapshot.json"),
        help="Aggregated readiness snapshot file maintained across suite + contract checks",
    )
    parser.add_argument(
        "--allow-no-event",
        action="store_true",
        help="Allow PASS when no latest event exists (status-only checks)",
    )
    args = parser.parse_args()

    status_path = resolve_path(args.status_file)
    events_path = resolve_path(args.events_file)
    report_path = resolve_path(args.report_file)
    acceptance_snapshot_path = resolve_path(args.acceptance_snapshot_file)

    status_payload = load_json(status_path)
    events_payload = load_json(events_path)

    status_failures, status_warnings = validate_status_payload(status_payload)
    event_failures, event_warnings = validate_event_payload(events_payload, args.allow_no_event)
    warnings = status_warnings + event_warnings

    report = build_report(status_path, events_path, status_failures, event_failures, warnings)
    write_json(report_path, report)
    update_acceptance_snapshot(acceptance_snapshot_path, report_path, report)

    print("Uplink Packet Contract Report")
    print(f"result={report['result']}")
    print(f"status_failures={len(status_failures)}")
    print(f"event_failures={len(event_failures)}")
    print(f"warnings={len(warnings)}")
    print(f"report_file={report_path.as_posix()}")

    if report["result"] == "FAIL":
        for item in status_failures + event_failures:
            print(f"- {item}")
        return 2

    if warnings:
        for item in warnings:
            print(f"- WARN: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
