# ???? Node A ??????????????????????????suite ??????????????????
import argparse
import json
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import serial
from session_log_utils_会话日志工具 import append_session_event, build_serial_record


SCENARIO_FILE = Path(__file__).with_name("track_scenarios.json")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUITE_CHOICES = ["standard_acceptance", "single_node_realtime_v1", "risk_event_vision_chain_v1", "rid_identity_chain_v1"]
EVENT_HISTORY_PREFIXES = {"UPLINK,EVENT", "LASTEVENT"}
RID_VALUE_FIELDS = {"rid", "rid_status", "current_event_rid_status", "last_rid_status"}
RID_STATUS_ALIASES = {
    "OK": "MATCHED",
    "MATCHED": "MATCHED",
    "NONE": "NONE",
    "CLEAR": "NONE",
    "OFF": "NONE",
    "MISSING": "NONE",
    "RECEIVED": "RECEIVED",
    "EXPIRED": "EXPIRED",
    "INVALID": "INVALID",
    "SUSPICIOUS": "INVALID",
}
RID_COMMAND_CHOICES = ["OK", "MATCHED", "RECEIVED", "NONE", "EXPIRED", "INVALID", "MISSING", "SUSPICIOUS"]
RID_VALIDATE_CHOICES = ["MISSING", "NONE", "SUSPICIOUS", "INVALID", "EXPIRED"]
RID_V11_OUTPUT_VALUES = {"NONE", "RECEIVED", "MATCHED", "EXPIRED", "INVALID"}
RID_LEGACY_OUTPUT_VALUES = {"MISSING", "SUSPICIOUS"}
EXPECTED_BASELINE_VERSION = "Node_A_Base_Demo_V1.1"


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def load_scenarios() -> dict:
    with SCENARIO_FILE.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_session_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    content = json.dumps(payload, ensure_ascii=False, indent=2)

    # Windows occasionally reports transient WinError 5 when another process
    # is reading the target file at the same moment we rotate .tmp -> final.
    # Retry a few times to avoid flaky acceptance false-failures.
    last_error: PermissionError | None = None
    for _ in range(8):
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.08)

    if last_error is not None:
        raise last_error


def coerce_value(value: str, default: Any) -> Any:
    text = value.strip()
    if text == "":
        return default
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def build_event_record_from_serial(record: dict) -> dict | None:
    prefix = str(record.get("prefix", ""))
    if prefix not in EVENT_HISTORY_PREFIXES:
        return None

    fields = record.get("fields")
    if not isinstance(fields, dict) or not fields:
        return None

    timestamp_ms = int(
        coerce_value(
            str(fields.get("ts", fields.get("timestamp", record.get("ts_ms", int(time.time() * 1000))))),
            int(time.time() * 1000),
        )
    )
    node_id = str(fields.get("node", "")).strip()
    zone = str(fields.get("zone", "")).strip()
    event_id = str(fields.get("event_id", "NONE")).strip() or "NONE"
    reason = str(fields.get("reason", "NONE")).strip() or "NONE"
    event_level = str(fields.get("event_level", "NONE")).strip() or "NONE"
    event_status = str(fields.get("event_status", "NONE")).strip() or "NONE"
    track_id = coerce_value(str(fields.get("track", fields.get("track_id", "0"))), 0)
    risk_score = coerce_value(str(fields.get("risk", fields.get("risk_score", "0"))), 0.0)
    source_node = str(fields.get("source_node", node_id)).strip() or node_id

    return {
        "source_type": prefix,
        "timestamp_ms": timestamp_ms,
        "node_id": node_id,
        "zone": zone,
        "event_id": event_id,
        "reason": reason,
        "event_level": event_level,
        "event_status": event_status,
        "track_id": track_id,
        "risk_score": risk_score,
        "source_node": source_node,
    }


def append_event_record(history: list[dict[str, Any]], record: dict[str, Any], limit: int) -> bool:
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


def build_event_history_from_records(records: list[dict], limit: int) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    bounded_limit = max(1, limit)
    for record in records:
        event_record = build_event_record_from_serial(record)
        if event_record is None:
            continue
        append_event_record(history, event_record, bounded_limit)
    return history


def write_event_history_json(path: Path, records: list[dict[str, Any]]) -> None:
    payload = {
        "ok": True,
        "available": bool(records),
        "count": len(records),
        "records": records,
        "latest": records[0] if records else None,
    }
    write_session_json(path, payload)


def load_json_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_acceptance_snapshot_payload(
    final_session_payload: dict[str, Any],
    joint_evidence_file: Path,
    contract_report_file: Path,
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    suite_name = str(final_session_payload.get("suite_name", "")).strip()
    suite_report = final_session_payload.get("suite_report", {})
    if not isinstance(suite_report, dict):
        suite_report = {}

    suite_total = int(suite_report.get("total_checks", 0) or 0)
    suite_passed = int(suite_report.get("passed", final_session_payload.get("suite_passed", 0)) or 0)
    suite_failed = int(suite_report.get("failed", final_session_payload.get("suite_failed", 0)) or 0)
    suite_ok = suite_total > 0 and suite_failed == 0
    suite_finished_ms = int(final_session_payload.get("finished_ms", final_session_payload.get("updated_ms", now_ms)) or now_ms)

    evidence_payload = load_json_payload(joint_evidence_file)
    evidence_ready = bool(evidence_payload.get("evidence_ready"))

    contract_payload = load_json_payload(contract_report_file)
    contract_result = str(contract_payload.get("result", "UNKNOWN")).upper()
    contract_checked_ms = int(contract_payload.get("checked_ms", 0) or 0)
    contract_fresh = bool(contract_checked_ms >= suite_finished_ms > 0)
    contract_stale_by_ms = int(max(0, suite_finished_ms - contract_checked_ms)) if contract_checked_ms > 0 else 0
    contract_ok = contract_result == "PASS" and contract_fresh

    return {
        "ok": True,
        "available": bool(suite_name),
        "updated_ms": now_ms,
        "suite_name": suite_name,
        "suite_total_checks": suite_total,
        "suite_passed": suite_passed,
        "suite_failed": suite_failed,
        "suite_ok": suite_ok,
        "suite_finished_ms": suite_finished_ms,
        "joint_evidence_file": joint_evidence_file.as_posix(),
        "evidence_ready": evidence_ready,
        "contract_report_file": contract_report_file.as_posix(),
        "contract_result": contract_result,
        "contract_checked_ms": contract_checked_ms,
        "contract_fresh": contract_fresh,
        "contract_stale_by_ms": contract_stale_by_ms,
        "contract_ok": contract_ok,
        "deliverable_ready": bool(suite_ok and evidence_ready and contract_ok),
    }


def build_session_payload(
    scenario_name: str = "",
    scenario_description: str = "",
    suite_name: str = "",
    suite_step: str = "",
    suite_step_index: int = 0,
    suite_step_total: int = 0,
    suite_passed: int = 0,
    suite_failed: int = 0,
    scenario_index: int = 0,
    scenario_total: int = 0,
    rid_mode: str = "UNCHANGED",
    point_total: int = 0,
    repeat_total: int = 0,
    point_index: int = 0,
    repeat_index: int = 0,
    points_sent: int = 0,
    current_x_mm: float = 0.0,
    current_y_mm: float = 0.0,
    status: str = "IDLE",
    started_ms: int = 0,
    finished_ms: int = 0,
    suite_report: dict | None = None,
) -> dict:
    now_ms = int(time.time() * 1000)
    payload = {
        "ok": True,
        "available": status != "IDLE",
        "status": status,
        "scenario_name": scenario_name,
        "scenario_description": scenario_description,
        "suite_name": suite_name,
        "suite_step": suite_step,
        "suite_step_index": suite_step_index,
        "suite_step_total": suite_step_total,
        "suite_passed": suite_passed,
        "suite_failed": suite_failed,
        "scenario_index": scenario_index,
        "scenario_total": scenario_total,
        "rid_mode": rid_mode,
        "point_total": point_total,
        "repeat_total": repeat_total,
        "point_index": point_index,
        "repeat_index": repeat_index,
        "points_sent": points_sent,
        "current_x_mm": current_x_mm,
        "current_y_mm": current_y_mm,
        "started_ms": started_ms,
        "updated_ms": now_ms,
        "finished_ms": finished_ms,
    }
    if suite_report is not None:
        payload["suite_report"] = suite_report
    return payload


@dataclass
class SuiteCheck:
    name: str
    command: str
    expected_prefix: str
    timeout_s: float
    required_fields: dict[str, str]
    allowed_fields: dict[str, set[str]] | None = None
    note: str = ""


class SerialObserver:
    def __init__(self) -> None:
        self.records: list[dict] = []
        self.condition = threading.Condition()

    def add_line(self, line: str) -> None:
        record = build_serial_record(line)
        record["ts_ms"] = int(time.time() * 1000)
        with self.condition:
            self.records.append(record)
            self.condition.notify_all()

    def cursor(self) -> int:
        with self.condition:
            return len(self.records)

    def records_since(self, cursor: int) -> list[dict]:
        with self.condition:
            return list(self.records[cursor:])

    def wait_for_record(self, cursor: int, expected_prefix: str, timeout_s: float) -> dict | None:
        deadline = time.time() + timeout_s
        with self.condition:
            while True:
                for record in self.records[cursor:]:
                    if record["prefix"] == expected_prefix or record["command"] == expected_prefix:
                        return record

                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self.condition.wait(timeout=remaining)


def read_serial_background(ser: serial.Serial, stop_event: threading.Event, observer: SerialObserver) -> None:
    while not stop_event.is_set():
        try:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            if line:
                observer.add_line(line)
                print(f"[ESP32] {line}")
        except Exception:
            return


def send_line(ser: serial.Serial, line: str) -> None:
    ser.write((line + "\n").encode("utf-8"))
    ser.flush()
    print(f">>> {line}")


def send_command_and_wait(ser: serial.Serial, line: str, wait_s: float) -> None:
    send_line(ser, line)
    time.sleep(wait_s)


def send_command_and_collect(
    ser: serial.Serial,
    observer: SerialObserver,
    line: str,
    wait_s: float,
) -> list[dict]:
    cursor = observer.cursor()
    send_line(ser, line)
    time.sleep(wait_s)
    return observer.records_since(cursor)


def send_command_and_capture(
    ser: serial.Serial,
    observer: SerialObserver,
    line: str,
    expected_prefix: str,
    timeout_s: float,
) -> dict | None:
    cursor = observer.cursor()
    send_line(ser, line)
    return observer.wait_for_record(cursor, expected_prefix, timeout_s)


def extract_record_fields(record: dict | None) -> dict[str, str]:
    if not isinstance(record, dict):
        return {}
    fields = record.get("fields")
    return fields if isinstance(fields, dict) else {}


def run_baseline_precheck(
    ser: serial.Serial,
    observer: SerialObserver,
    expected_baseline_version: str,
    timeout_s: float = 1.2,
) -> dict[str, Any]:
    status_record = send_command_and_capture(ser, observer, "STATUS", "STATUS", timeout_s)
    rid_record = send_command_and_capture(ser, observer, "RID,STATUS", "RID,STATUS", timeout_s)
    status_fields = extract_record_fields(status_record)
    rid_fields = extract_record_fields(rid_record)
    baseline_version = str(status_fields.get("baseline_version", "")).strip()
    rid_status_raw = str(rid_fields.get("rid_status", status_fields.get("rid_status", ""))).strip().upper()
    rid_status_norm = normalize_field_value("rid_status", rid_status_raw) or ""
    precheck = {
        "status_available": bool(status_record),
        "rid_available": bool(rid_record),
        "baseline_version": baseline_version,
        "expected_baseline_version": expected_baseline_version,
        "rid_status_raw": rid_status_raw,
        "rid_status_normalized": rid_status_norm,
    }
    issues: list[str] = []
    if not precheck["status_available"]:
        issues.append("STATUS_MISSING")
    if not precheck["rid_available"]:
        issues.append("RID_STATUS_MISSING")
    if baseline_version != expected_baseline_version:
        issues.append("BASELINE_VERSION_MISMATCH")
    if rid_status_raw in RID_LEGACY_OUTPUT_VALUES:
        issues.append("RID_LEGACY_OUTPUT")
    elif rid_status_raw and rid_status_norm not in RID_V11_OUTPUT_VALUES:
        issues.append("RID_OUTPUT_UNKNOWN")
    precheck["ok"] = not issues
    precheck["issues"] = issues
    return precheck


def normalize_field_value(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if field_name in RID_VALUE_FIELDS:
        return RID_STATUS_ALIASES.get(text.upper(), text.upper())
    return text


def field_matches(
    field_name: str,
    expected: str,
    actual: str | None,
    allowed_values: set[str] | None = None,
) -> bool:
    normalized_actual = normalize_field_value(field_name, actual)
    if normalized_actual is None:
        return False
    if allowed_values:
        normalized_allowed = {
            normalized
            for normalized in (normalize_field_value(field_name, value) for value in allowed_values)
            if normalized is not None
        }
        return normalized_actual in normalized_allowed
    normalized_expected = normalize_field_value(field_name, expected)
    return normalized_actual == normalized_expected


def execute_suite_check(
    ser: serial.Serial,
    observer: SerialObserver,
    check: SuiteCheck,
) -> dict:
    record = send_command_and_capture(ser, observer, check.command, check.expected_prefix, check.timeout_s)
    if record is None:
        return {
            "name": check.name,
            "ok": False,
            "reason": f"Timed out waiting for {check.expected_prefix}",
            "command": check.command,
            "note": check.note,
        }

    fields = record.get("fields", {})
    mismatches: list[str] = []

    for key, expected in check.required_fields.items():
        allowed_values = None
        if check.allowed_fields and key in check.allowed_fields:
            allowed_values = check.allowed_fields[key]
        actual = fields.get(key)
        if not field_matches(key, expected, actual, allowed_values):
            if allowed_values:
                mismatches.append(f"{key} expected one of {sorted(allowed_values)} but got {actual or 'NONE'}")
            else:
                mismatches.append(f"{key} expected {expected} but got {actual or 'NONE'}")

    if check.allowed_fields:
        for key, allowed_values in check.allowed_fields.items():
            if key in check.required_fields:
                continue
            actual = fields.get(key)
            if not field_matches(key, "", actual, allowed_values):
                mismatches.append(f"{key} expected one of {sorted(allowed_values)} but got {actual or 'NONE'}")

    return {
        "name": check.name,
        "ok": not mismatches,
        "reason": "; ".join(mismatches) if mismatches else "PASS",
        "command": check.command,
        "note": check.note,
        "record": record,
    }


def print_suite_result(result: dict) -> None:
    status_text = "PASS" if result["ok"] else "FAIL"
    print(f"[{status_text}] {result['name']}: {result['reason']}")
    if result.get("note"):
        print(f"        note: {result['note']}")
    record = result.get("record")
    if isinstance(record, dict):
        print(f"        line: {record.get('raw', '')}")


def normalize_suite_result(result: dict) -> dict:
    record = result.get("record") if isinstance(result.get("record"), dict) else {}
    return {
        "name": result.get("name", ""),
        "ok": bool(result.get("ok")),
        "reason": result.get("reason", ""),
        "command": result.get("command", ""),
        "note": result.get("note", ""),
        "line": record.get("raw", ""),
    }


def build_suite_report(suite_name: str, results: list[dict]) -> dict:
    normalized_results = [normalize_suite_result(result) for result in results]
    failed_checks = [result for result in normalized_results if not result["ok"]]
    passed_checks = [result["name"] for result in normalized_results if result["ok"]]
    return {
        "suite_name": suite_name,
        "total_checks": len(normalized_results),
        "passed": len(passed_checks),
        "failed": len(failed_checks),
        "passed_checks": passed_checks,
        "failed_checks": [
            {
                "name": result["name"],
                "reason": result["reason"],
                "command": result["command"],
                "line": result["line"],
            }
            for result in failed_checks
        ],
        "all_checks": normalized_results,
    }


def build_joint_chain_evidence_payload(
    suite_results: list[dict],
    suite_report: dict,
    x_mm: float,
    y_mm: float,
    confirm_repeat: int,
    rid_mode: str,
    session_file: Path,
    events_file: Path,
    status_file: Path,
    contract_report_file: Path,
    latest_session_log_file: Path | None,
) -> dict:
    result_by_name: dict[str, dict] = {}
    for item in suite_results:
        name = str(item.get("name", "")).strip()
        if name and name not in result_by_name:
            result_by_name[name] = item

    check_specs: dict[str, tuple[str, tuple[str, ...]]] = {
        "scenario1": (
            "scenario1_short_missing_rid_no_direct_event",
            (
                "main",
                "track",
                "active",
                "confirmed",
                "hunter",
                "gimbal",
                "rid",
                "risk",
                "risk_level",
                "event_active",
                "event_id",
                "event_state",
                "event_close_reason",
                "x",
                "y",
            ),
        ),
        "scenario2": (
            "scenario2_sustained_missing_rid_risk_upgrade",
            (
                "main_state",
                "current_risk_state",
                "pending_risk_state",
                "risk_transition_mode",
                "risk_score",
                "risk_level",
                "risk_reasons",
                "track_active",
                "track_confirmed",
                "rid_status",
                "event_active",
                "event_id",
                "timestamp",
            ),
        ),
        "scenario3": (
            "scenario3_legal_target_keep_low_risk",
            (
                "main_state",
                "hunter_state",
                "gimbal_state",
                "rid_status",
                "risk_score",
                "risk_level",
                "event_active",
                "event_id",
                "current_event_state",
                "current_event_close_reason",
                "vision_state",
                "vision_locked",
                "capture_ready",
                "timestamp",
            ),
        ),
        "scenario4": (
            "scenario4_suspicious_rid_fast_risk_upgrade",
            (
                "main_state",
                "current_risk_state",
                "pending_risk_state",
                "risk_transition_mode",
                "risk_score",
                "risk_level",
                "risk_reasons",
                "track_active",
                "track_confirmed",
                "rid_status",
                "event_active",
                "event_id",
                "timestamp",
            ),
        ),
        "scenario5": (
            "scenario5_high_risk_visual_capture_ready",
            (
                "main_state",
                "risk_score",
                "risk_level",
                "event_active",
                "event_id",
                "current_event_state",
                "current_event_close_reason",
                "vision_state",
                "vision_locked",
                "capture_ready",
                "trigger_flags",
                "current_event_trigger_flags",
                "current_event_trigger_reasons",
                "timestamp",
            ),
        ),
        "scenario6": (
            "scenario6_track_lost_smooth_recover",
            (
                "main_state",
                "risk_level",
                "event_active",
                "event_id",
                "current_event_state",
                "current_event_close_reason",
                "last_event_id",
                "last_reason",
                "vision_state",
                "vision_locked",
                "capture_ready",
                "timestamp",
            ),
        ),
    }

    evidence_items: dict[str, dict[str, Any]] = {}
    for item_key, (check_name, wanted_fields) in check_specs.items():
        result = result_by_name.get(check_name)
        if result is None:
            evidence_items[item_key] = {
                "check_name": check_name,
                "check_ok": False,
                "available": False,
                "reason": "check_result_not_found",
                "line": "",
                "fields": {},
            }
            continue

        record = result.get("record")
        raw_line = ""
        fields: dict[str, Any] = {}
        if isinstance(record, dict):
            raw_line = str(record.get("raw", ""))
            raw_fields = record.get("fields")
            if isinstance(raw_fields, dict):
                for field_name in wanted_fields:
                    fields[field_name] = raw_fields.get(field_name, "")

        evidence_items[item_key] = {
            "check_name": check_name,
            "check_ok": bool(result.get("ok")),
            "available": bool(raw_line),
            "reason": str(result.get("reason", "")),
            "line": raw_line,
            "fields": fields,
        }

    evidence_ready = all(
        bool(item.get("available")) and bool(item.get("check_ok"))
        for item in evidence_items.values()
    )

    return {
        "ok": True,
        "available": True,
        "suite_name": str(suite_report.get("suite_name", "risk_event_vision_chain_v1")),
        "generated_ms": int(time.time() * 1000),
        "suite_total_checks": int(suite_report.get("total_checks", 0)),
        "suite_passed": int(suite_report.get("passed", 0)),
        "suite_failed": int(suite_report.get("failed", 0)),
        "suite_failed_checks": suite_report.get("failed_checks", []),
        "target_point": {"x_mm": x_mm, "y_mm": y_mm},
        "confirm_repeat": confirm_repeat,
        "rid_mode": rid_mode,
        "evidence_ready": evidence_ready,
        "record_index": {
            "latest_test_session": session_file.as_posix(),
            "latest_node_events": events_file.as_posix(),
            "latest_node_status": status_file.as_posix(),
            "latest_uplink_contract_report": contract_report_file.as_posix(),
            "latest_session_log": latest_session_log_file.as_posix() if latest_session_log_file is not None else "",
        },
        "evidence_items": evidence_items,
    }


def print_suite_report(report: dict) -> None:
    print("\nAcceptance report:")
    print(
        f"  suite={report.get('suite_name', '')} total={report.get('total_checks', 0)} "
        f"passed={report.get('passed', 0)} failed={report.get('failed', 0)}"
    )
    passed_checks = report.get("passed_checks", [])
    if passed_checks:
        print(f"  passed_checks={', '.join(passed_checks)}")
    failed_checks = report.get("failed_checks", [])
    if failed_checks:
        print("  failed_checks:")
        for item in failed_checks:
            print(f"    - {item.get('name', '')}: {item.get('reason', '')}")


def log_suite_result(session_payload: dict, session_log_dir: Path, result: dict) -> None:
    append_session_event(
        session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_check",
        payload={
            "name": result["name"],
            "ok": result["ok"],
            "reason": result["reason"],
            "command": result.get("command", ""),
            "note": result.get("note", ""),
            "line": result.get("record", {}).get("raw", "") if isinstance(result.get("record"), dict) else "",
        },
    )


def inject_confirmed_track(
    ser: serial.Serial,
    x_mm: float,
    y_mm: float,
    confirm_repeat: int,
    confirm_interval_s: float,
) -> None:
    for _ in range(confirm_repeat):
        send_line(ser, f"TRACK,{x_mm:.1f},{y_mm:.1f}")
        time.sleep(confirm_interval_s)


def run_standard_acceptance_suite(
    ser: serial.Serial,
    observer: SerialObserver,
    suite_name: str,
    rid: str,
    x_mm: float,
    y_mm: float,
    confirm_repeat: int,
    confirm_interval_s: float,
    session_file: Path,
    session_log_dir: Path,
) -> tuple[dict, bool]:
    description = "4.8 standard acceptance suite built on the stable 4.7 risk/event chain"
    started_ms = int(time.time() * 1000)
    total_checks = 7
    passed = 0
    failed = 0
    suite_results: list[dict] = []

    print(f"\n--- Running suite: {suite_name} ---")
    print(f"Target point: x={x_mm:.1f}, y={y_mm:.1f}, confirm_repeat={confirm_repeat}, rid={rid}")

    session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step="prepare",
        suite_step_index=0,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=1,
        scenario_total=1,
        rid_mode=rid,
        point_total=1,
        repeat_total=confirm_repeat,
        status="RUNNING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    append_session_event(
        session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_started",
        payload={
            "suite_name": suite_name,
            "x_mm": x_mm,
            "y_mm": y_mm,
            "confirm_repeat": confirm_repeat,
            "rid_mode": rid,
        },
    )

    send_command_and_wait(ser, "RESET", 0.8)
    send_command_and_wait(ser, "DEBUG,OFF", 0.3)
    send_command_and_wait(ser, "UPLINK,OFF", 0.3)
    send_command_and_wait(ser, "LASTEVENT,CLEAR", 0.2)

    checks: list[SuiteCheck] = [
        SuiteCheck(
            name="idle_baseline",
            command="BRIEF",
            expected_prefix="BRIEF",
            timeout_s=0.5,
            required_fields={"active": "0", "confirmed": "0", "event_active": "0"},
            allowed_fields={"main": {"IDLE", "LOST"}},
            note="复位后先确认系统回到空闲基线。",
        ),
    ]

    for check_index, check in enumerate(checks, start=1):
        session_payload = build_session_payload(
            scenario_name=suite_name,
            scenario_description=description,
            suite_name=suite_name,
            suite_step=check.name,
            suite_step_index=check_index,
            suite_step_total=total_checks,
            suite_passed=passed,
            suite_failed=failed,
            scenario_index=1,
            scenario_total=1,
            rid_mode=rid,
            point_total=1,
            repeat_total=confirm_repeat,
            status="RUNNING",
            started_ms=started_ms,
        )
        write_session_json(session_file, session_payload)
        result = execute_suite_check(ser, observer, check)
        print_suite_result(result)
        log_suite_result(session_payload, session_log_dir, result)
        suite_results.append(result)
        if result["ok"]:
            passed += 1
        else:
            failed += 1

    inject_confirmed_track(ser, x_mm, y_mm, confirm_repeat, confirm_interval_s)
    send_command_and_wait(ser, f"RID,{rid}", 0.15)

    open_checks = [
        SuiteCheck(
            name="event_open_brief",
            command="BRIEF",
            expected_prefix="BRIEF",
            timeout_s=0.5,
            required_fields={
                "active": "1",
                "confirmed": "1",
                "rid": rid,
                "event_active": "1",
            },
            note="确认模拟目标进入活跃、确认、事件开启状态。",
        ),
        SuiteCheck(
            name="event_open_risk",
            command="RISK,STATUS",
            expected_prefix="RISK,STATUS",
            timeout_s=0.6,
            required_fields={"risk_level": "SUSPICIOUS", "track_active": "1", "track_confirmed": "1"},
            allowed_fields={"risk_level": {"SUSPICIOUS", "HIGH_RISK", "EVENT"}},
            note="风险状态允许继续向上升级，但不能还是 NONE/NORMAL。",
        ),
        SuiteCheck(
            name="event_open_status",
            command="EVENT,STATUS",
            expected_prefix="EVENT,STATUS",
            timeout_s=0.6,
            required_fields={
                "current_event_state": "OPEN",
                "current_event_close_reason": "NONE",
                "event_active": "1",
            },
            note="事件对象要处于 OPEN，且还没有关闭原因。",
        ),
    ]

    for offset, check in enumerate(open_checks, start=2):
        session_payload = build_session_payload(
            scenario_name=suite_name,
            scenario_description=description,
            suite_name=suite_name,
            suite_step=check.name,
            suite_step_index=offset,
            suite_step_total=total_checks,
            suite_passed=passed,
            suite_failed=failed,
            scenario_index=1,
            scenario_total=1,
            rid_mode=rid,
            point_total=1,
            repeat_total=confirm_repeat,
            points_sent=confirm_repeat,
            current_x_mm=x_mm,
            current_y_mm=y_mm,
            status="RUNNING",
            started_ms=started_ms,
        )
        write_session_json(session_file, session_payload)
        result = execute_suite_check(ser, observer, check)
        print_suite_result(result)
        log_suite_result(session_payload, session_log_dir, result)
        suite_results.append(result)
        if result["ok"]:
            passed += 1
        else:
            failed += 1

    send_command_and_wait(ser, "RID,OK", 0.05)
    inject_confirmed_track(ser, x_mm, y_mm, 3, confirm_interval_s)
    downgrade_checks = [
        SuiteCheck(
            name="risk_downgrade_event_status",
            command="EVENT,STATUS",
            expected_prefix="EVENT,STATUS",
            timeout_s=0.6,
            required_fields={
                "current_event_state": "CLOSED",
                "current_event_close_reason": "RISK_DOWNGRADE",
                "event_active": "0",
            },
            note="RID 恢复 OK 后，事件对象应因风险回落而关闭。",
        ),
        SuiteCheck(
            name="risk_downgrade_last_event",
            command="LASTEVENT",
            expected_prefix="LASTEVENT",
            timeout_s=0.6,
            required_fields={
                "event_close_reason": "RISK_DOWNGRADE",
                "event_status": "CLOSED",
            },
            note="最近事件留痕里也要保住 RISK_DOWNGRADE。",
        ),
    ]

    for offset, check in enumerate(downgrade_checks, start=5):
        session_payload = build_session_payload(
            scenario_name=suite_name,
            scenario_description=description,
            suite_name=suite_name,
            suite_step=check.name,
            suite_step_index=offset,
            suite_step_total=total_checks,
            suite_passed=passed,
            suite_failed=failed,
            scenario_index=1,
            scenario_total=1,
            rid_mode="OK",
            point_total=1,
            repeat_total=confirm_repeat,
            points_sent=confirm_repeat + 3,
            current_x_mm=x_mm,
            current_y_mm=y_mm,
            status="RUNNING",
            started_ms=started_ms,
        )
        write_session_json(session_file, session_payload)
        result = execute_suite_check(ser, observer, check)
        print_suite_result(result)
        log_suite_result(session_payload, session_log_dir, result)
        suite_results.append(result)
        if result["ok"]:
            passed += 1
        else:
            failed += 1

    inject_confirmed_track(ser, x_mm, y_mm, confirm_repeat, confirm_interval_s)
    send_command_and_wait(ser, f"RID,{rid}", 0.1)
    send_command_and_wait(ser, "EVENT,STATUS", 0.25)
    send_command_and_wait(ser, "TRACK,CLEAR", 0.3)

    lost_check = SuiteCheck(
        name="track_lost_last_event",
        command="LASTEVENT",
        expected_prefix="LASTEVENT",
        timeout_s=0.6,
        required_fields={
            "event_close_reason": "TRACK_LOST",
            "event_status": "CLOSED",
        },
        note="清轨后，最近事件里要能看到 TRACK_LOST。",
    )
    session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step=lost_check.name,
        suite_step_index=7,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=1,
        scenario_total=1,
        rid_mode=rid,
        point_total=1,
        repeat_total=confirm_repeat,
        points_sent=(confirm_repeat * 2) + 3,
        status="RUNNING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    result = execute_suite_check(ser, observer, lost_check)
    print_suite_result(result)
    log_suite_result(session_payload, session_log_dir, result)
    suite_results.append(result)
    if result["ok"]:
        passed += 1
    else:
        failed += 1

    finished_ms = int(time.time() * 1000)
    final_status = "DONE" if failed == 0 else "FAILED"
    suite_report = build_suite_report(suite_name, suite_results)
    final_session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step="finished",
        suite_step_index=total_checks,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=1,
        scenario_total=1,
        rid_mode=rid,
        point_total=1,
        repeat_total=confirm_repeat,
        points_sent=(confirm_repeat * 2) + 3,
        current_x_mm=x_mm,
        current_y_mm=y_mm,
        status=final_status,
        started_ms=started_ms,
        finished_ms=finished_ms,
        suite_report=suite_report,
    )
    write_session_json(session_file, final_session_payload)
    append_session_event(
        final_session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_finished",
        payload={
            "suite_name": suite_name,
            "passed": passed,
            "failed": failed,
            "failed_checks": suite_report.get("failed_checks", []),
        },
    )
    send_command_and_wait(ser, "RESET", 0.5)
    print_suite_report(suite_report)
    print(f"\nSuite summary: passed={passed}, failed={failed}")
    return final_session_payload, failed == 0


def run_single_node_realtime_v1_suite(
    ser: serial.Serial,
    observer: SerialObserver,
    suite_name: str,
    rid: str,
    x_mm: float,
    y_mm: float,
    confirm_repeat: int,
    confirm_interval_s: float,
    session_file: Path,
    session_log_dir: Path,
) -> tuple[dict, bool]:
    description = "4.9 single-node live chain suite for TRACKING/COARSEAIM/RECOVER/TRACK_LOST with realtime web mapping checks"
    started_ms = int(time.time() * 1000)
    total_checks = 7
    passed = 0
    failed = 0
    suite_results: list[dict] = []

    print(f"\n--- Running suite: {suite_name} ---")
    print(f"Target point: x={x_mm:.1f}, y={y_mm:.1f}, confirm_repeat={confirm_repeat}, rid={rid}")

    session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step="prepare",
        suite_step_index=0,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=1,
        scenario_total=2,
        rid_mode=rid,
        point_total=2,
        repeat_total=confirm_repeat,
        status="RUNNING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    append_session_event(
        session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_started",
        payload={
            "suite_name": suite_name,
            "x_mm": x_mm,
            "y_mm": y_mm,
            "confirm_repeat": confirm_repeat,
            "rid_mode": rid,
            "scenario_total": 2,
        },
    )

    send_command_and_wait(ser, "RESET", 0.8)
    send_command_and_wait(ser, "DEBUG,OFF", 0.3)
    send_command_and_wait(ser, "UPLINK,OFF", 0.3)
    send_command_and_wait(ser, "LASTEVENT,CLEAR", 0.2)

    checks: list[SuiteCheck] = [
        SuiteCheck(
            name="scenario1_idle_baseline",
            command="BRIEF",
            expected_prefix="BRIEF",
            timeout_s=0.6,
            required_fields={"active": "0", "confirmed": "0", "event_active": "0"},
            allowed_fields={"main": {"IDLE", "LOST"}},
            note="场景1起步：复位后先确认基线空闲。",
        ),
    ]

    for check_index, check in enumerate(checks, start=1):
        session_payload = build_session_payload(
            scenario_name=suite_name,
            scenario_description=description,
            suite_name=suite_name,
            suite_step=check.name,
            suite_step_index=check_index,
            suite_step_total=total_checks,
            suite_passed=passed,
            suite_failed=failed,
            scenario_index=1,
            scenario_total=2,
            rid_mode=rid,
            point_total=2,
            repeat_total=confirm_repeat,
            status="RUNNING",
            started_ms=started_ms,
        )
        write_session_json(session_file, session_payload)
        result = execute_suite_check(ser, observer, check)
        print_suite_result(result)
        log_suite_result(session_payload, session_log_dir, result)
        suite_results.append(result)
        if result["ok"]:
            passed += 1
        else:
            failed += 1

    inject_confirmed_track(ser, x_mm, y_mm, confirm_repeat, confirm_interval_s)
    send_command_and_wait(ser, f"RID,{rid}", 0.15)

    scenario1_checks = [
        SuiteCheck(
            name="scenario1_tracking_open_brief",
            command="BRIEF",
            expected_prefix="BRIEF",
            timeout_s=0.6,
            required_fields={"active": "1", "confirmed": "1", "event_active": "1", "rid": rid},
            note="场景1主链：目标建立后应进入活跃确认并打开事件。",
        ),
        SuiteCheck(
            name="scenario1_tracking_open_event",
            command="EVENT,STATUS",
            expected_prefix="EVENT,STATUS",
            timeout_s=0.8,
            required_fields={"current_event_state": "OPEN", "event_active": "1"},
            note="场景1网页映射：事件卡应显示 OPEN。",
        ),
        SuiteCheck(
            name="scenario1_tracking_open_risk",
            command="RISK,STATUS",
            expected_prefix="RISK,STATUS",
            timeout_s=0.8,
            required_fields={"track_active": "1", "track_confirmed": "1"},
            allowed_fields={"risk_level": {"SUSPICIOUS", "HIGH_RISK", "EVENT"}},
            note="场景1风险：不能停留在 NONE/NORMAL。",
        ),
    ]

    for offset, check in enumerate(scenario1_checks, start=2):
        session_payload = build_session_payload(
            scenario_name=suite_name,
            scenario_description=description,
            suite_name=suite_name,
            suite_step=check.name,
            suite_step_index=offset,
            suite_step_total=total_checks,
            suite_passed=passed,
            suite_failed=failed,
            scenario_index=1,
            scenario_total=2,
            rid_mode=rid,
            point_total=2,
            repeat_total=confirm_repeat,
            points_sent=confirm_repeat,
            current_x_mm=x_mm,
            current_y_mm=y_mm,
            status="RUNNING",
            started_ms=started_ms,
        )
        write_session_json(session_file, session_payload)
        result = execute_suite_check(ser, observer, check)
        print_suite_result(result)
        log_suite_result(session_payload, session_log_dir, result)
        suite_results.append(result)
        if result["ok"]:
            passed += 1
        else:
            failed += 1

    coarse_aim_records = send_command_and_collect(ser, observer, f"COARSEAIM,{x_mm:.1f},{y_mm:.1f}", 0.25)
    coarse_aim_unsupported = any(
        str(record.get("raw", "")).startswith("Unknown command: COARSEAIM") for record in coarse_aim_records
    )
    scenario1_coarse_aim_check = SuiteCheck(
        name="scenario1_coarse_aim_status",
        command="STATUS",
        expected_prefix="STATUS",
        timeout_s=0.8,
        required_fields={"test_mode": "1", "servo_enabled": "1"},
        note="场景1接口联动：粗转向入口命令生效后，云台应进入手动测试模式且舵机输出开启。",
    )
    session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step=scenario1_coarse_aim_check.name,
        suite_step_index=5,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=1,
        scenario_total=2,
        rid_mode=rid,
        point_total=2,
        repeat_total=confirm_repeat,
        points_sent=confirm_repeat,
        current_x_mm=x_mm,
        current_y_mm=y_mm,
        status="RUNNING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    result = execute_suite_check(ser, observer, scenario1_coarse_aim_check)
    if not result["ok"] and coarse_aim_unsupported:
        base_reason = str(result.get("reason", "")).strip()
        hint = "COARSEAIM not supported by current firmware; flash latest firmware and rerun this suite."
        result["reason"] = f"{base_reason}; {hint}" if base_reason else hint
    print_suite_result(result)
    log_suite_result(session_payload, session_log_dir, result)
    suite_results.append(result)
    if result["ok"]:
        passed += 1
    else:
        failed += 1
    send_command_and_wait(ser, "TESTMODE,OFF", 0.1)

    send_command_and_wait(ser, "RID,OK", 0.1)
    inject_confirmed_track(ser, x_mm, y_mm, 3, confirm_interval_s)
    scenario2_recover_check = SuiteCheck(
        name="scenario2_risk_recover_event_closed",
        command="EVENT,STATUS",
        expected_prefix="EVENT,STATUS",
        timeout_s=0.8,
        required_fields={
            "current_event_state": "CLOSED",
            "current_event_close_reason": "RISK_DOWNGRADE",
            "event_active": "0",
        },
        note="场景2回落：RID 恢复后应看到事件关闭。",
    )
    session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step=scenario2_recover_check.name,
        suite_step_index=6,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=2,
        scenario_total=2,
        rid_mode="OK",
        point_total=2,
        repeat_total=confirm_repeat,
        points_sent=confirm_repeat + 3,
        current_x_mm=x_mm,
        current_y_mm=y_mm,
        status="RUNNING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    result = execute_suite_check(ser, observer, scenario2_recover_check)
    print_suite_result(result)
    log_suite_result(session_payload, session_log_dir, result)
    suite_results.append(result)
    if result["ok"]:
        passed += 1
    else:
        failed += 1

    inject_confirmed_track(ser, x_mm, y_mm, confirm_repeat, confirm_interval_s)
    send_command_and_wait(ser, f"RID,{rid}", 0.1)
    send_command_and_wait(ser, "TRACK,CLEAR", 0.3)
    scenario2_lost_check = SuiteCheck(
        name="scenario2_track_lost_last_event",
        command="LASTEVENT",
        expected_prefix="LASTEVENT",
        timeout_s=0.8,
        required_fields={"event_close_reason": "TRACK_LOST", "event_status": "CLOSED"},
        note="场景2丢轨：清轨后最近事件应记录 TRACK_LOST。",
    )
    session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step=scenario2_lost_check.name,
        suite_step_index=7,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=2,
        scenario_total=2,
        rid_mode=rid,
        point_total=2,
        repeat_total=confirm_repeat,
        points_sent=(confirm_repeat * 2) + 3,
        status="RUNNING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    result = execute_suite_check(ser, observer, scenario2_lost_check)
    print_suite_result(result)
    log_suite_result(session_payload, session_log_dir, result)
    suite_results.append(result)
    if result["ok"]:
        passed += 1
    else:
        failed += 1

    finished_ms = int(time.time() * 1000)
    final_status = "DONE" if failed == 0 else "FAILED"
    suite_report = build_suite_report(suite_name, suite_results)
    final_session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step="finished",
        suite_step_index=total_checks,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=2,
        scenario_total=2,
        rid_mode=rid,
        point_total=2,
        repeat_total=confirm_repeat,
        points_sent=(confirm_repeat * 2) + 3,
        current_x_mm=x_mm,
        current_y_mm=y_mm,
        status=final_status,
        started_ms=started_ms,
        finished_ms=finished_ms,
        suite_report=suite_report,
    )
    write_session_json(session_file, final_session_payload)
    append_session_event(
        final_session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_finished",
        payload={
            "suite_name": suite_name,
            "passed": passed,
            "failed": failed,
            "failed_checks": suite_report.get("failed_checks", []),
            "scenario_total": 2,
        },
    )
    send_command_and_wait(ser, "RESET", 0.5)
    print_suite_report(suite_report)
    print(f"\nSuite summary: passed={passed}, failed={failed}")
    return final_session_payload, failed == 0


def run_risk_event_vision_chain_v1_suite(
    ser: serial.Serial,
    observer: SerialObserver,
    suite_name: str,
    rid: str,
    x_mm: float,
    y_mm: float,
    confirm_repeat: int,
    confirm_interval_s: float,
    session_file: Path,
    session_log_dir: Path,
    joint_evidence_file: Path,
    events_file: Path,
    status_file: Path,
    contract_report_file: Path,
) -> tuple[dict, bool]:
    description = (
        "4.10 joint stress suite for risk chain + event chain + vision/capture trigger chain "
        "(short missing-rid -> sustained upgrade -> legal downgrade -> suspicious upgrade -> "
        "high-risk visual/capture readiness -> track-lost smooth recovery)"
    )
    started_ms = int(time.time() * 1000)
    total_checks = 6
    passed = 0
    failed = 0
    suite_results: list[dict] = []
    points_sent = 0
    missing_rid = "MISSING"

    print(f"\n--- Running suite: {suite_name} ---")
    print(f"Target point: x={x_mm:.1f}, y={y_mm:.1f}, confirm_repeat={confirm_repeat}, rid={rid}")

    session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step="prepare",
        suite_step_index=0,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=1,
        scenario_total=6,
        rid_mode=missing_rid,
        point_total=6,
        repeat_total=confirm_repeat,
        status="RUNNING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    append_session_event(
        session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_started",
        payload={
            "suite_name": suite_name,
            "x_mm": x_mm,
            "y_mm": y_mm,
            "confirm_repeat": confirm_repeat,
            "rid_mode": missing_rid,
            "scenario_total": 6,
        },
    )

    def run_step(
        check: SuiteCheck,
        step_index: int,
        scenario_index: int,
        scenario_label: str,
        rid_mode: str,
        custom_validator: Callable[[dict], tuple[bool, str]] | None = None,
    ) -> None:
        nonlocal passed, failed
        step_payload = build_session_payload(
            scenario_name=suite_name,
            scenario_description=description,
            suite_name=suite_name,
            suite_step=check.name,
            suite_step_index=step_index,
            suite_step_total=total_checks,
            suite_passed=passed,
            suite_failed=failed,
            scenario_index=scenario_index,
            scenario_total=6,
            rid_mode=rid_mode,
            point_total=6,
            repeat_total=confirm_repeat,
            points_sent=points_sent,
            current_x_mm=x_mm,
            current_y_mm=y_mm,
            status="RUNNING",
            started_ms=started_ms,
        )
        write_session_json(session_file, step_payload)
        result = execute_suite_check(ser, observer, check)
        if result.get("ok") and custom_validator is not None:
            fields = {}
            if isinstance(result.get("record"), dict):
                fields = result["record"].get("fields", {})
            custom_ok, custom_reason = custom_validator(fields)
            if not custom_ok:
                result["ok"] = False
                result["reason"] = custom_reason
        print_suite_result(result)
        log_suite_result(step_payload, session_log_dir, result)
        append_session_event(
            step_payload,
            session_log_dir,
            source="track_injector",
            event_type="suite_scenario_marker",
            payload={
                "scenario_label": scenario_label,
                "check_name": check.name,
                "ok": bool(result.get("ok")),
            },
        )
        suite_results.append(result)
        if result["ok"]:
            passed += 1
        else:
            failed += 1

    send_command_and_wait(ser, "RESET", 0.8)
    send_command_and_wait(ser, "DEBUG,OFF", 0.3)
    send_command_and_wait(ser, "UPLINK,OFF", 0.3)
    send_command_and_wait(ser, "LASTEVENT,CLEAR", 0.2)

    short_repeat = 2 if confirm_repeat >= 2 else 1
    for _ in range(short_repeat):
        send_line(ser, f"TRACK,{x_mm:.1f},{y_mm:.1f}")
        points_sent += 1
        time.sleep(confirm_interval_s)
    send_command_and_wait(ser, f"RID,{missing_rid}", 0.15)
    run_step(
        SuiteCheck(
            name="scenario1_short_missing_rid_no_direct_event",
            command="BRIEF",
            expected_prefix="BRIEF",
            timeout_s=0.7,
            required_fields={"event_active": "0", "rid": missing_rid},
            note="场景1：无 RID 短时进入，不应直接事件化。",
        ),
        step_index=1,
        scenario_index=1,
        scenario_label="short_missing_rid",
        rid_mode=missing_rid,
        custom_validator=lambda fields: (
            fields.get("main", "") in {"IDLE", "TRACKING", "SUSPICIOUS", "HIGH_RISK", "LOST"},
            f"main expected IDLE/TRACKING/SUSPICIOUS/HIGH_RISK/LOST but got {fields.get('main', 'NONE')}",
        ),
    )

    inject_confirmed_track(ser, x_mm, y_mm, confirm_repeat, confirm_interval_s)
    points_sent += confirm_repeat
    send_command_and_wait(ser, f"RID,{missing_rid}", 0.1)
    run_step(
        SuiteCheck(
            name="scenario2_sustained_missing_rid_risk_upgrade",
            command="RISK,STATUS",
            expected_prefix="RISK,STATUS",
            timeout_s=0.8,
            required_fields={"track_active": "1", "track_confirmed": "1", "rid_status": missing_rid},
            allowed_fields={"risk_level": {"SUSPICIOUS", "HIGH_RISK", "EVENT"}},
            note="场景2：持续无身份停留，风险应逐步升级。",
        ),
        step_index=2,
        scenario_index=2,
        scenario_label="sustained_missing_rid",
        rid_mode=missing_rid,
    )

    send_command_and_wait(ser, "RID,OK", 0.1)
    inject_confirmed_track(ser, x_mm, y_mm, 3, confirm_interval_s)
    points_sent += 3
    run_step(
        SuiteCheck(
            name="scenario3_legal_target_keep_low_risk",
            command="EVENT,STATUS",
            expected_prefix="EVENT,STATUS",
            timeout_s=0.8,
            required_fields={"event_active": "0", "rid_status": "MATCHED"},
            allowed_fields={
                "risk_level": {"NONE", "NORMAL"},
                "capture_ready": {"0"},
                "vision_locked": {"0"},
                "current_event_state": {"CLOSED", "NONE"},
            },
            note="场景3：合法目标进入，应保持低风险且不触发抓拍事件。",
        ),
        step_index=3,
        scenario_index=3,
        scenario_label="legal_target_low_risk",
        rid_mode="OK",
    )

    send_command_and_wait(ser, "RID,SUSPICIOUS", 0.1)
    inject_confirmed_track(ser, x_mm, y_mm, confirm_repeat, confirm_interval_s)
    points_sent += confirm_repeat
    run_step(
        SuiteCheck(
            name="scenario4_suspicious_rid_fast_risk_upgrade",
            command="RISK,STATUS",
            expected_prefix="RISK,STATUS",
            timeout_s=0.8,
            required_fields={"track_active": "1", "track_confirmed": "1", "rid_status": "SUSPICIOUS"},
            allowed_fields={"risk_level": {"SUSPICIOUS", "HIGH_RISK", "EVENT"}},
            note="场景4：身份异常目标进入，应快速升风险。",
        ),
        step_index=4,
        scenario_index=4,
        scenario_label="suspicious_rid_upgrade",
        rid_mode="SUSPICIOUS",
    )

    send_command_and_wait(ser, f"RID,{missing_rid}", 0.1)
    inject_confirmed_track(ser, x_mm, y_mm, confirm_repeat, confirm_interval_s)
    points_sent += confirm_repeat
    run_step(
        SuiteCheck(
            name="scenario5_high_risk_visual_capture_ready",
            command="EVENT,STATUS",
            expected_prefix="EVENT,STATUS",
            timeout_s=0.8,
            required_fields={"event_active": "1", "rid_status": missing_rid, "current_event_state": "OPEN"},
            allowed_fields={"risk_level": {"SUSPICIOUS", "HIGH_RISK", "EVENT"}},
            note="场景5：高风险目标出现后，应触发视觉锁定或抓拍预备。",
        ),
        step_index=5,
        scenario_index=5,
        scenario_label="high_risk_visual_trigger",
        rid_mode=missing_rid,
        custom_validator=lambda fields: (
            fields.get("capture_ready") == "1"
            or fields.get("vision_locked") == "1"
            or "CAPTURE" in (fields.get("current_event_trigger_flags", "") or fields.get("trigger_flags", "")),
            (
                "capture_ready/vision_locked/trigger_flags expected capture indicator, got "
                f"capture_ready={fields.get('capture_ready', 'NONE')}, "
                f"vision_locked={fields.get('vision_locked', 'NONE')}, "
                f"trigger_flags={fields.get('current_event_trigger_flags', fields.get('trigger_flags', 'NONE'))}"
            ),
        ),
    )

    send_command_and_wait(ser, "TRACK,CLEAR", 0.5)
    run_step(
        SuiteCheck(
            name="scenario6_track_lost_smooth_recover",
            command="EVENT,STATUS",
            expected_prefix="EVENT,STATUS",
            timeout_s=0.8,
            required_fields={
                "event_active": "0",
                "current_event_state": "CLOSED",
                "current_event_close_reason": "TRACK_LOST",
            },
            allowed_fields={
                "main_state": {"LOST", "IDLE"},
                "risk_level": {"NONE", "NORMAL"},
            },
            note="场景6：目标丢失后，状态应平稳回落且不挂死。",
        ),
        step_index=6,
        scenario_index=6,
        scenario_label="track_lost_recover",
        rid_mode=missing_rid,
    )
    send_command_and_wait(ser, "LASTEVENT", 0.25)

    finished_ms = int(time.time() * 1000)
    final_status = "DONE" if failed == 0 else "FAILED"
    suite_report = build_suite_report(suite_name, suite_results)
    latest_session_log_file = session_log_dir / f"{started_ms}_{suite_name}.jsonl"
    if not latest_session_log_file.exists():
        latest_session_log_file = None
    joint_evidence_payload = build_joint_chain_evidence_payload(
        suite_results,
        suite_report,
        x_mm,
        y_mm,
        confirm_repeat,
        missing_rid,
        session_file,
        events_file,
        status_file,
        contract_report_file,
        latest_session_log_file,
    )
    write_session_json(joint_evidence_file, joint_evidence_payload)
    final_session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step="finished",
        suite_step_index=total_checks,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=6,
        scenario_total=6,
        rid_mode=missing_rid,
        point_total=6,
        repeat_total=confirm_repeat,
        points_sent=points_sent,
        current_x_mm=x_mm,
        current_y_mm=y_mm,
        status=final_status,
        started_ms=started_ms,
        finished_ms=finished_ms,
        suite_report=suite_report,
    )
    write_session_json(session_file, final_session_payload)
    append_session_event(
        final_session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_finished",
        payload={
            "suite_name": suite_name,
            "passed": passed,
            "failed": failed,
            "failed_checks": suite_report.get("failed_checks", []),
            "scenario_total": 6,
        },
    )
    append_session_event(
        final_session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_evidence_written",
        payload={
            "joint_evidence_file": joint_evidence_file.as_posix(),
            "evidence_ready": bool(joint_evidence_payload.get("evidence_ready")),
        },
    )
    send_command_and_wait(ser, "RESET", 0.5)
    print_suite_report(suite_report)
    print(f"\nSuite summary: passed={passed}, failed={failed}")
    return final_session_payload, failed == 0


def run_rid_identity_chain_v1_suite(
    ser: serial.Serial,
    observer: SerialObserver,
    suite_name: str,
    rid: str,
    x_mm: float,
    y_mm: float,
    confirm_repeat: int,
    confirm_interval_s: float,
    session_file: Path,
    session_log_dir: Path,
) -> tuple[dict, bool]:
    description = "4.14 RID identity chain suite for RID,MSG matched/expired/invalid verification"
    started_ms = int(time.time() * 1000)
    total_checks = 3
    passed = 0
    failed = 0
    suite_results: list[dict] = []
    points_sent = 0

    print(f"\n--- Running suite: {suite_name} ---")
    print(f"Target point: x={x_mm:.1f}, y={y_mm:.1f}, confirm_repeat={confirm_repeat}, rid={rid}")

    session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step="prepare",
        suite_step_index=0,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=1,
        scenario_total=3,
        rid_mode="RID_MSG",
        point_total=3,
        repeat_total=confirm_repeat,
        status="RUNNING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    append_session_event(
        session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_started",
        payload={
            "suite_name": suite_name,
            "x_mm": x_mm,
            "y_mm": y_mm,
            "confirm_repeat": confirm_repeat,
            "rid_mode": "RID_MSG",
            "scenario_total": 3,
        },
    )

    def run_step(
        check: SuiteCheck,
        step_index: int,
        scenario_index: int,
        scenario_label: str,
    ) -> None:
        nonlocal passed, failed
        step_payload = build_session_payload(
            scenario_name=suite_name,
            scenario_description=description,
            suite_name=suite_name,
            suite_step=check.name,
            suite_step_index=step_index,
            suite_step_total=total_checks,
            suite_passed=passed,
            suite_failed=failed,
            scenario_index=scenario_index,
            scenario_total=3,
            rid_mode="RID_MSG",
            point_total=3,
            repeat_total=confirm_repeat,
            points_sent=points_sent,
            current_x_mm=x_mm,
            current_y_mm=y_mm,
            status="RUNNING",
            started_ms=started_ms,
        )
        write_session_json(session_file, step_payload)
        result = execute_suite_check(ser, observer, check)
        print_suite_result(result)
        log_suite_result(step_payload, session_log_dir, result)
        append_session_event(
            step_payload,
            session_log_dir,
            source="track_injector",
            event_type="suite_scenario_marker",
            payload={
                "scenario_label": scenario_label,
                "check_name": check.name,
                "ok": bool(result.get("ok")),
            },
        )
        suite_results.append(result)
        if result["ok"]:
            passed += 1
        else:
            failed += 1

    send_command_and_wait(ser, "RESET", 0.8)
    send_command_and_wait(ser, "DEBUG,OFF", 0.3)
    send_command_and_wait(ser, "UPLINK,OFF", 0.3)
    send_command_and_wait(ser, "LASTEVENT,CLEAR", 0.2)

    warmup_repeat = confirm_repeat if confirm_repeat >= 3 else 3
    inject_confirmed_track(ser, x_mm, y_mm, warmup_repeat, confirm_interval_s)
    points_sent += warmup_repeat

    send_command_and_wait(ser, "RID,MSG,SIM-RID-001,UAV,RID_SIM,1712880000000,VALID,WL_OK,-48", 0.15)
    inject_confirmed_track(ser, x_mm, y_mm, 2, confirm_interval_s)
    points_sent += 2
    run_step(
        SuiteCheck(
            name="scenario1_msg_valid_becomes_matched",
            command="RID,STATUS",
            expected_prefix="RID,STATUS",
            timeout_s=0.8,
            required_fields={
                "rid_status": "MATCHED",
                "rid_whitelist_hit": "1",
                "rid_auth_status": "VALID",
                "rid_whitelist_tag": "WL_OK",
                "track_active": "1",
                "track_confirmed": "1",
            },
            note="场景1：合法身份包进入后，RID 状态应进入 MATCHED 且命中白名单。",
        ),
        step_index=1,
        scenario_index=1,
        scenario_label="rid_msg_valid",
    )

    time.sleep(3.4)
    run_step(
        SuiteCheck(
            name="scenario2_msg_timeout_becomes_expired",
            command="RID,STATUS",
            expected_prefix="RID,STATUS",
            timeout_s=0.8,
            required_fields={
                "rid_status": "EXPIRED",
                "rid_whitelist_hit": "1",
                "rid_packet_valid": "1",
                "rid_auth_status": "VALID",
            },
            note="场景2：超过接收超时窗口后，RID 状态应从 MATCHED/RECEIVED 进入 EXPIRED。",
        ),
        step_index=2,
        scenario_index=2,
        scenario_label="rid_msg_timeout",
    )

    send_command_and_wait(ser, "RID,MSG,SIM-RID-999,UAV,RID_SIM,1712880000000,INVALID,DENY,-45", 0.15)
    inject_confirmed_track(ser, x_mm, y_mm, 2, confirm_interval_s)
    points_sent += 2
    run_step(
        SuiteCheck(
            name="scenario3_msg_invalid_becomes_invalid",
            command="RID,STATUS",
            expected_prefix="RID,STATUS",
            timeout_s=0.8,
            required_fields={
                "rid_status": "INVALID",
                "rid_whitelist_hit": "0",
                "rid_auth_status": "INVALID",
                "rid_whitelist_tag": "DENY",
                "track_active": "1",
                "track_confirmed": "1",
            },
            note="场景3：异常身份包进入后，RID 状态应为 INVALID 且不命中白名单。",
        ),
        step_index=3,
        scenario_index=3,
        scenario_label="rid_msg_invalid",
    )

    finished_ms = int(time.time() * 1000)
    final_status = "DONE" if failed == 0 else "FAILED"
    suite_report = build_suite_report(suite_name, suite_results)
    final_session_payload = build_session_payload(
        scenario_name=suite_name,
        scenario_description=description,
        suite_name=suite_name,
        suite_step="finished",
        suite_step_index=total_checks,
        suite_step_total=total_checks,
        suite_passed=passed,
        suite_failed=failed,
        scenario_index=3,
        scenario_total=3,
        rid_mode="RID_MSG",
        point_total=3,
        repeat_total=confirm_repeat,
        points_sent=points_sent,
        current_x_mm=x_mm,
        current_y_mm=y_mm,
        status=final_status,
        started_ms=started_ms,
        finished_ms=finished_ms,
        suite_report=suite_report,
    )
    write_session_json(session_file, final_session_payload)
    append_session_event(
        final_session_payload,
        session_log_dir,
        source="track_injector",
        event_type="suite_finished",
        payload={
            "suite_name": suite_name,
            "passed": passed,
            "failed": failed,
            "failed_checks": suite_report.get("failed_checks", []),
            "scenario_total": 3,
        },
    )
    send_command_and_wait(ser, "RESET", 0.5)
    print_suite_report(suite_report)
    print(f"\nSuite summary: passed={passed}, failed={failed}")
    return final_session_payload, failed == 0


def run_validation_47(
    ser: serial.Serial,
    observer: SerialObserver,
    rid: str,
    x_mm: float,
    y_mm: float,
    confirm_repeat: int,
    confirm_interval_s: float,
    session_file: Path,
    session_log_dir: Path,
) -> tuple[dict, bool]:
    return run_standard_acceptance_suite(
        ser,
        observer,
        "validate_47",
        rid,
        x_mm,
        y_mm,
        confirm_repeat,
        confirm_interval_s,
        session_file,
        session_log_dir,
    )


def run_scenario(
    ser: serial.Serial,
    name: str,
    scenario: dict,
    scenario_index: int,
    scenario_total: int,
    interval_s: float,
    hold_repeat: int,
    rid: str | None,
    settle_s: float,
    session_file: Path,
    session_log_dir: Path,
) -> None:
    if rid:
        send_line(ser, f"RID,{rid}")
        time.sleep(0.3)

    description = scenario.get("description", "")
    points = scenario["points"]
    rid_mode = rid or "UNCHANGED"
    started_ms = int(time.time() * 1000)
    print(f"\n--- Running scenario: {name} ---")
    if description:
        print(f"Description: {description}")

    write_session_json(
        session_file,
        build_session_payload(
            scenario_name=name,
            scenario_description=description,
            scenario_index=scenario_index,
            scenario_total=scenario_total,
            rid_mode=rid_mode,
            point_total=len(points),
            repeat_total=hold_repeat,
            points_sent=0,
            status="RUNNING",
            started_ms=started_ms,
        ),
    )
    session_payload = build_session_payload(
        scenario_name=name,
        scenario_description=description,
        scenario_index=scenario_index,
        scenario_total=scenario_total,
        rid_mode=rid_mode,
        point_total=len(points),
        repeat_total=hold_repeat,
        points_sent=0,
        status="RUNNING",
        started_ms=started_ms,
    )
    append_session_event(
        session_payload,
        session_log_dir,
        source="track_injector",
        event_type="session_started",
        payload={
            "scenario_name": name,
            "scenario_description": description,
            "scenario_index": scenario_index,
            "scenario_total": scenario_total,
            "rid_mode": rid_mode,
            "point_total": len(points),
            "repeat_total": hold_repeat,
        },
    )

    points_sent = 0
    for point_index, (x_mm, y_mm) in enumerate(points, start=1):
        for repeat_index in range(1, hold_repeat + 1):
            send_line(ser, f"TRACK,{x_mm:.1f},{y_mm:.1f}")
            points_sent += 1
            session_payload = build_session_payload(
                scenario_name=name,
                scenario_description=description,
                scenario_index=scenario_index,
                scenario_total=scenario_total,
                rid_mode=rid_mode,
                point_total=len(points),
                repeat_total=hold_repeat,
                point_index=point_index,
                repeat_index=repeat_index,
                points_sent=points_sent,
                current_x_mm=x_mm,
                current_y_mm=y_mm,
                status="RUNNING",
                started_ms=started_ms,
            )
            write_session_json(session_file, session_payload)
            append_session_event(
                session_payload,
                session_log_dir,
                source="track_injector",
                event_type="track_point_sent",
                payload={
                    "point_index": point_index,
                    "repeat_index": repeat_index,
                    "points_sent": points_sent,
                    "x_mm": x_mm,
                    "y_mm": y_mm,
                },
            )
            time.sleep(interval_s)

    send_line(ser, "TRACK,CLEAR")
    session_payload = build_session_payload(
        scenario_name=name,
        scenario_description=description,
        scenario_index=scenario_index,
        scenario_total=scenario_total,
        rid_mode=rid_mode,
        point_total=len(points),
        repeat_total=hold_repeat,
        point_index=len(points),
        repeat_index=hold_repeat,
        points_sent=points_sent,
        status="SETTLING",
        started_ms=started_ms,
    )
    write_session_json(session_file, session_payload)
    append_session_event(
        session_payload,
        session_log_dir,
        source="track_injector",
        event_type="session_settling",
        payload={"points_sent": points_sent},
    )
    time.sleep(settle_s)
    session_payload = build_session_payload(
        scenario_name=name,
        scenario_description=description,
        scenario_index=scenario_index,
        scenario_total=scenario_total,
        rid_mode=rid_mode,
        point_total=len(points),
        repeat_total=hold_repeat,
        point_index=len(points),
        repeat_index=hold_repeat,
        points_sent=points_sent,
        status="DONE",
        started_ms=started_ms,
        finished_ms=int(time.time() * 1000),
    )
    write_session_json(session_file, session_payload)
    append_session_event(
        session_payload,
        session_log_dir,
        source="track_injector",
        event_type="session_finished",
        payload={"points_sent": points_sent},
    )


def main() -> int:
    scenarios = load_scenarios()

    parser = argparse.ArgumentParser(description="Inject standard TRACK scenarios into Node A")
    parser.add_argument("--port", required=True, help="Serial port, for example COM4")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument(
        "--scenario",
        choices=list(scenarios.keys()) + ["all"],
        default="all",
        help="Which scenario to run",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.18,
        help="Seconds between two TRACK commands",
    )
    parser.add_argument(
        "--hold-repeat",
        type=int,
        default=2,
        help="How many times to resend each point",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=1.5,
        help="Seconds to wait after TRACK,CLEAR",
    )
    parser.add_argument(
        "--rid",
        choices=RID_COMMAND_CHOICES,
        help="Optional RID status to set before running the scenario (supports legacy and V1.1 statuses)",
    )
    parser.add_argument(
        "--boot-wait",
        type=float,
        default=3.5,
        help="Seconds to wait after opening the serial port",
    )
    parser.add_argument(
        "--session-file",
        type=Path,
        default=Path("captures/latest_test_session.json"),
        help="JSON file written with the current test scenario session",
    )
    parser.add_argument(
        "--events-file",
        type=Path,
        default=Path("captures/latest_node_events.json"),
        help="JSON file written with recent event snapshots extracted from serial output",
    )
    parser.add_argument(
        "--events-limit",
        type=int,
        default=12,
        help="How many recent event snapshots to keep in events-file",
    )
    parser.add_argument(
        "--joint-evidence-file",
        type=Path,
        default=Path("captures/latest_joint_chain_evidence.json"),
        help="JSON evidence file for 4.10 risk/event/vision chain key scenarios",
    )
    parser.add_argument(
        "--acceptance-snapshot-file",
        type=Path,
        default=Path("captures/latest_acceptance_snapshot.json"),
        help="JSON snapshot file with suite/evidence/contract aggregated readiness flags",
    )
    parser.add_argument(
        "--session-log-dir",
        type=Path,
        default=Path("captures/session_logs"),
        help="Directory used to store per-session JSONL timeline logs",
    )
    parser.add_argument(
        "--validate-47",
        action="store_true",
        help="Run the scripted 4.7 acceptance sequence instead of the normal scenario flow",
    )
    parser.add_argument(
        "--suite",
        choices=SUITE_CHOICES,
        help="Run a standardized acceptance suite with automatic PASS/FAIL checks",
    )
    parser.add_argument(
        "--validate-x",
        type=float,
        default=320.0,
        help="Target x used by the 4.7 validation sequence",
    )
    parser.add_argument(
        "--validate-y",
        type=float,
        default=1800.0,
        help="Target y used by the 4.7 validation sequence",
    )
    parser.add_argument(
        "--validate-confirm-repeat",
        type=int,
        default=6,
        help="How many TRACK frames to inject before querying risk/event status in 4.7 validation",
    )
    parser.add_argument(
        "--validate-confirm-interval",
        type=float,
        default=0.10,
        help="Seconds between TRACK frames in 4.7 validation",
    )
    parser.add_argument(
        "--validate-rid",
        choices=RID_VALIDATE_CHOICES,
        default="MISSING",
        help="RID mode used during the 4.7/4.14 validation sequence",
    )
    parser.add_argument(
        "--expected-baseline-version",
        default=EXPECTED_BASELINE_VERSION,
        help="Required STATUS baseline_version for suite/validate precheck",
    )
    parser.add_argument(
        "--allow-baseline-mismatch",
        action="store_true",
        help="Continue suite/validate even when baseline precheck reports mismatch",
    )
    args = parser.parse_args()
    session_file = resolve_path(args.session_file)
    events_file = resolve_path(args.events_file)
    joint_evidence_file = resolve_path(args.joint_evidence_file)
    acceptance_snapshot_file = resolve_path(args.acceptance_snapshot_file)
    session_log_dir = resolve_path(args.session_log_dir)
    status_file = resolve_path(Path("captures/latest_node_status.json"))
    contract_report_file = resolve_path(Path("captures/latest_uplink_contract_report.json"))
    write_session_json(session_file, build_session_payload())
    write_event_history_json(events_file, [])

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.2)
    except serial.SerialException as exc:
        print(f"Failed to open {args.port}: {exc}", file=sys.stderr)
        return 1

    stop_event = threading.Event()
    observer = SerialObserver()
    reader = threading.Thread(target=read_serial_background, args=(ser, stop_event, observer), daemon=True)

    with ser:
        time.sleep(0.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print(f"Connected to {args.port} at {args.baud}")
        print(f"Writing session timeline logs to: {session_log_dir.as_posix()}")
        print(f"Writing event snapshot logs to: {events_file.as_posix()}")
        print(f"Writing joint chain evidence logs to: {joint_evidence_file.as_posix()}")
        print(f"Writing acceptance snapshot to: {acceptance_snapshot_file.as_posix()}")
        reader.start()

        time.sleep(args.boot_wait)
        requested_suite = args.suite or ("standard_acceptance" if args.validate_47 else "")
        needs_precheck_gate = bool(args.validate_47 or args.suite)
        precheck_started_ms = int(time.time() * 1000)
        precheck_payload = run_baseline_precheck(ser, observer, args.expected_baseline_version)
        print(
            "[PRECHECK] "
            f"baseline={precheck_payload['baseline_version'] or 'NONE'} "
            f"(expected={precheck_payload['expected_baseline_version']}), "
            f"rid_status={precheck_payload['rid_status_raw'] or 'NONE'} "
            f"(normalized={precheck_payload['rid_status_normalized'] or 'NONE'}), "
            f"ok={1 if precheck_payload['ok'] else 0}"
        )
        if precheck_payload["issues"]:
            print(f"[PRECHECK] issues={','.join(precheck_payload['issues'])}")
        append_session_event(
            build_session_payload(
                scenario_name=requested_suite or (args.scenario if args.scenario else ""),
                suite_name=requested_suite,
                suite_step="precheck",
                suite_step_index=0,
                suite_step_total=0,
                rid_mode=args.validate_rid if needs_precheck_gate else (args.rid or "UNCHANGED"),
                status="RUNNING",
                started_ms=precheck_started_ms,
            ),
            session_log_dir,
            source="track_injector",
            event_type="suite_precheck",
            payload=precheck_payload,
        )

        if needs_precheck_gate and not precheck_payload["ok"] and not args.allow_baseline_mismatch:
            final_session_payload = build_session_payload(
                scenario_name=requested_suite,
                scenario_description="precheck blocked suite execution",
                suite_name=requested_suite,
                suite_step="precheck_failed",
                suite_step_index=0,
                suite_step_total=0,
                suite_passed=0,
                suite_failed=1,
                scenario_index=0,
                scenario_total=0,
                rid_mode=args.validate_rid,
                status="FAILED",
                started_ms=precheck_started_ms,
                finished_ms=int(time.time() * 1000),
                suite_report={
                    "suite_name": requested_suite,
                    "total_checks": 0,
                    "passed": 0,
                    "failed": 1,
                    "passed_checks": [],
                    "failed_checks": [{"name": "precheck", "reason": ",".join(precheck_payload["issues"])}],
                    "all_checks": [],
                },
            )
            final_session_payload["precheck"] = precheck_payload
            write_session_json(session_file, final_session_payload)
            append_session_event(
                final_session_payload,
                session_log_dir,
                source="track_injector",
                event_type="suite_precheck_blocked",
                payload={
                    "suite_name": requested_suite,
                    "issues": precheck_payload["issues"],
                    "expected_baseline_version": args.expected_baseline_version,
                    "allow_baseline_mismatch": False,
                },
            )
            write_event_history_json(events_file, build_event_history_from_records(observer.records_since(0), args.events_limit))
            stop_event.set()
            return 2
        if needs_precheck_gate and not precheck_payload["ok"] and args.allow_baseline_mismatch:
            print("[PRECHECK] baseline mismatch ignored by --allow-baseline-mismatch; continuing suite run.")

        final_session_payload = build_session_payload(status="ALL_DONE", finished_ms=int(time.time() * 1000))
        if args.validate_47:
            final_session_payload, suite_ok = run_validation_47(
                ser,
                observer,
                args.validate_rid,
                args.validate_x,
                args.validate_y,
                args.validate_confirm_repeat,
                args.validate_confirm_interval,
                session_file,
                session_log_dir,
            )
            final_session_payload["status"] = "ALL_DONE" if suite_ok else "FAILED"
            final_session_payload["finished_ms"] = int(time.time() * 1000)
        elif args.suite:
            if args.suite == "single_node_realtime_v1":
                final_session_payload, suite_ok = run_single_node_realtime_v1_suite(
                    ser,
                    observer,
                    args.suite,
                    args.validate_rid,
                    args.validate_x,
                    args.validate_y,
                    args.validate_confirm_repeat,
                    args.validate_confirm_interval,
                    session_file,
                    session_log_dir,
                )
            elif args.suite == "risk_event_vision_chain_v1":
                final_session_payload, suite_ok = run_risk_event_vision_chain_v1_suite(
                    ser,
                    observer,
                    args.suite,
                    args.validate_rid,
                    args.validate_x,
                    args.validate_y,
                    args.validate_confirm_repeat,
                    args.validate_confirm_interval,
                    session_file,
                    session_log_dir,
                    joint_evidence_file,
                    events_file,
                    status_file,
                    contract_report_file,
                )
            elif args.suite == "rid_identity_chain_v1":
                final_session_payload, suite_ok = run_rid_identity_chain_v1_suite(
                    ser,
                    observer,
                    args.suite,
                    args.validate_rid,
                    args.validate_x,
                    args.validate_y,
                    args.validate_confirm_repeat,
                    args.validate_confirm_interval,
                    session_file,
                    session_log_dir,
                )
            else:
                final_session_payload, suite_ok = run_standard_acceptance_suite(
                    ser,
                    observer,
                    args.suite,
                    args.validate_rid,
                    args.validate_x,
                    args.validate_y,
                    args.validate_confirm_repeat,
                    args.validate_confirm_interval,
                    session_file,
                    session_log_dir,
                )
            final_session_payload["status"] = "ALL_DONE" if suite_ok else "FAILED"
            final_session_payload["finished_ms"] = int(time.time() * 1000)
        else:
            scenario_names = list(scenarios.keys()) if args.scenario == "all" else [args.scenario]
            total_scenarios = len(scenario_names)
            for scenario_index, scenario_name in enumerate(scenario_names, start=1):
                run_scenario(
                    ser,
                    scenario_name,
                    scenarios[scenario_name],
                    scenario_index,
                    total_scenarios,
                    args.interval,
                    args.hold_repeat,
                    args.rid,
                    args.settle,
                    session_file,
                    session_log_dir,
                )

            send_line(ser, "RESET")
            time.sleep(0.5)
            final_session_payload = build_session_payload(
                scenario_name=scenario_names[-1] if scenario_names else "",
                scenario_description=scenarios[scenario_names[-1]].get("description", "") if scenario_names else "",
                scenario_index=total_scenarios if scenario_names else 0,
                scenario_total=total_scenarios,
                rid_mode=args.rid or "UNCHANGED",
                status="ALL_DONE",
                finished_ms=int(time.time() * 1000),
            )
        final_session_payload["precheck"] = precheck_payload
        write_session_json(session_file, final_session_payload)
        append_session_event(
            final_session_payload,
            session_log_dir,
            source="track_injector",
            event_type="all_done",
            payload={
                "scenario_total": final_session_payload.get("scenario_total", 0),
                "rid_mode": final_session_payload.get("rid_mode", "UNCHANGED"),
                "validate_47": args.validate_47,
                "suite_name": final_session_payload.get("suite_name", ""),
                "suite_failed": final_session_payload.get("suite_failed", 0),
            },
        )
        event_history = build_event_history_from_records(observer.records_since(0), args.events_limit)
        write_event_history_json(events_file, event_history)
        if str(final_session_payload.get("suite_name", "")) == "risk_event_vision_chain_v1":
            acceptance_snapshot_payload = build_acceptance_snapshot_payload(
                final_session_payload,
                joint_evidence_file,
                contract_report_file,
            )
            write_session_json(acceptance_snapshot_file, acceptance_snapshot_payload)
        stop_event.set()

    if final_session_payload.get("status") == "FAILED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

