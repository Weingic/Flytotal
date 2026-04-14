# 功能：核对 4.10/4.11/4.16 交付链路是否达到“可交付”门槛（含视觉证据门禁）。
import argparse
import json
import time
from pathlib import Path
from typing import Any


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def pick_int(payload: dict[str, Any], *keys: str) -> int:
    for key in keys:
        if key not in payload:
            continue
        try:
            value = int(payload.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 0


def check_suite_payload(session_payload: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if not session_payload:
        return False, ["suite_payload_unavailable"]

    suite_name = str(session_payload.get("suite_name", "")).strip()
    suite_report = session_payload.get("suite_report", {})
    if not suite_name:
        failures.append("suite_name_unavailable")

    if not isinstance(suite_report, dict):
        failures.append("suite_report_unavailable")
        return False, failures

    total_checks = int(suite_report.get("total_checks", 0) or 0)
    failed_checks = int(suite_report.get("failed", session_payload.get("suite_failed", 0)) or 0)
    if total_checks <= 0:
        failures.append("suite_total_checks_invalid")
    if failed_checks > 0:
        failures.append(f"suite_failed_nonzero:{failed_checks}")

    return len(failures) == 0, failures


def check_evidence_payload(evidence_payload: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if not evidence_payload:
        return False, ["evidence_payload_unavailable"]

    if not bool(evidence_payload.get("ok")):
        failures.append("evidence_ok_false")
    if not bool(evidence_payload.get("available")):
        failures.append("evidence_available_false")
    if not bool(evidence_payload.get("evidence_ready")):
        failures.append("evidence_ready_false")

    suite_total = int(evidence_payload.get("suite_total_checks", 0) or 0)
    suite_failed = int(evidence_payload.get("suite_failed", 0) or 0)
    if suite_total <= 0:
        failures.append("evidence_suite_total_invalid")
    if suite_failed > 0:
        failures.append(f"evidence_suite_failed_nonzero:{suite_failed}")

    return len(failures) == 0, failures


def check_contract_payload(contract_payload: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if not contract_payload:
        return False, ["contract_payload_unavailable"]

    contract_result = str(contract_payload.get("result", "UNKNOWN")).upper()
    if contract_result != "PASS":
        failures.append(f"contract_result_not_pass:{contract_result}")

    failure_count = int(contract_payload.get("failure_count", 0) or 0)
    if failure_count > 0:
        failures.append(f"contract_failure_count_nonzero:{failure_count}")

    return len(failures) == 0, failures


def check_snapshot_payload(snapshot_payload: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if not snapshot_payload:
        return False, ["snapshot_payload_unavailable"]

    required_true_fields = (
        "available",
        "suite_ok",
        "evidence_ready",
        "contract_ok",
        "deliverable_ready",
    )
    for field in required_true_fields:
        if not bool(snapshot_payload.get(field)):
            failures.append(f"snapshot_{field}_false")

    return len(failures) == 0, failures


def check_acceptance_payloads(
    auto_payload: dict[str, Any],
    full_payload: dict[str, Any],
    require_vision_evidence: bool,
) -> tuple[bool, bool, list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    if not auto_payload:
        failures.append("acceptance_auto_payload_unavailable")
    else:
        auto_result = str(auto_payload.get("result", "UNKNOWN")).upper()
        if auto_result != "PASS":
            failures.append(f"acceptance_auto_result_not_pass:{auto_result}")

    if not full_payload:
        failures.append("acceptance_full_payload_unavailable")
    else:
        full_result = str(full_payload.get("result", "UNKNOWN")).upper()
        if full_result != "PASS":
            failures.append(f"acceptance_full_result_not_pass:{full_result}")

    vision_evidence_ok = True
    if require_vision_evidence:
        if not full_payload:
            vision_evidence_ok = False
            failures.append("acceptance_full_missing_for_vision_evidence")
        else:
            vision_lock_ok = bool(full_payload.get("closure_vision_lock_ok"))
            capture_ready_ok = bool(full_payload.get("closure_capture_ready_ok"))
            vision_lock_hits = int(full_payload.get("closure_vision_lock_hits", 0) or 0)
            capture_ready_hits = int(full_payload.get("closure_capture_ready_hits", 0) or 0)
            if (not vision_lock_ok) or vision_lock_hits <= 0:
                vision_evidence_ok = False
                failures.append(f"acceptance_full_vision_lock_not_ok:hits={vision_lock_hits}")
            if (not capture_ready_ok) or capture_ready_hits <= 0:
                vision_evidence_ok = False
                failures.append(f"acceptance_full_capture_ready_not_ok:hits={capture_ready_hits}")

            auto_vision_lock_ok = bool(auto_payload.get("full_closure_vision_lock_ok")) if isinstance(auto_payload, dict) else False
            auto_capture_ready_ok = bool(auto_payload.get("full_closure_capture_ready_ok")) if isinstance(auto_payload, dict) else False
            if auto_payload and ((auto_vision_lock_ok != vision_lock_ok) or (auto_capture_ready_ok != capture_ready_ok)):
                warnings.append("acceptance_auto_full_vision_mismatch")

    acceptance_ok = len([item for item in failures if item.startswith("acceptance_")]) == 0
    return acceptance_ok, vision_evidence_ok, failures, warnings


def check_consistency(
    session_payload: dict[str, Any],
    evidence_payload: dict[str, Any],
    contract_payload: dict[str, Any],
    snapshot_payload: dict[str, Any],
    max_backward_ms: int,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    suite_name_set = {
        str(session_payload.get("suite_name", "")).strip(),
        str(evidence_payload.get("suite_name", "")).strip(),
        str(snapshot_payload.get("suite_name", "")).strip(),
    }
    suite_name_set = {name for name in suite_name_set if name}
    if len(suite_name_set) > 1:
        failures.append("suite_name_mismatch")
    if not suite_name_set:
        warnings.append("suite_name_unavailable_for_consistency")

    contract_result = str(contract_payload.get("result", "UNKNOWN")).upper()
    snapshot_contract = str(snapshot_payload.get("contract_result", "UNKNOWN")).upper()
    if contract_result and snapshot_contract and contract_result != snapshot_contract:
        failures.append("contract_result_mismatch")

    session_started_ms = pick_int(session_payload, "started_ms")
    session_finished_ms = pick_int(session_payload, "finished_ms", "updated_ms")
    evidence_generated_ms = pick_int(evidence_payload, "generated_ms", "updated_ms", "checked_ms")
    contract_checked_ms = pick_int(contract_payload, "checked_ms", "updated_ms")
    snapshot_updated_ms = pick_int(snapshot_payload, "updated_ms")
    snapshot_contract_checked_ms = pick_int(snapshot_payload, "contract_checked_ms")

    if session_finished_ms <= 0:
        failures.append("session_finished_ms_unavailable")
    if evidence_generated_ms <= 0:
        warnings.append("evidence_generated_ms_unavailable")
    if contract_checked_ms <= 0:
        failures.append("contract_checked_ms_unavailable")
    if snapshot_updated_ms <= 0:
        failures.append("snapshot_updated_ms_unavailable")

    if (
        session_started_ms > 0
        and evidence_generated_ms > 0
        and evidence_generated_ms + max_backward_ms < session_started_ms
    ):
        failures.append("evidence_generated_before_session_started")

    if (
        session_finished_ms > 0
        and contract_checked_ms > 0
        and contract_checked_ms + max_backward_ms < session_finished_ms
    ):
        failures.append("contract_checked_before_suite_finished")

    if (
        contract_checked_ms > 0
        and snapshot_updated_ms > 0
        and snapshot_updated_ms + max_backward_ms < contract_checked_ms
    ):
        failures.append("snapshot_updated_before_contract_checked")

    if (
        contract_checked_ms > 0
        and snapshot_contract_checked_ms > 0
        and snapshot_contract_checked_ms + max_backward_ms < contract_checked_ms
    ):
        failures.append("snapshot_contract_checked_stale")

    return failures, warnings


def build_report(
    session_file: Path,
    evidence_file: Path,
    contract_file: Path,
    snapshot_file: Path,
    acceptance_auto_file: Path,
    acceptance_full_file: Path,
    suite_ok: bool,
    evidence_ok: bool,
    contract_ok: bool,
    snapshot_ok: bool,
    acceptance_ok: bool,
    vision_evidence_ok: bool,
    failures: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    checked_ms = int(time.time() * 1000)
    result = "PASS" if not failures else "FAIL"
    return {
        "checked_ms": checked_ms,
        "result": result,
        "files": {
            "session_file": session_file.as_posix(),
            "evidence_file": evidence_file.as_posix(),
            "contract_file": contract_file.as_posix(),
            "snapshot_file": snapshot_file.as_posix(),
            "acceptance_auto_file": acceptance_auto_file.as_posix(),
            "acceptance_full_file": acceptance_full_file.as_posix(),
        },
        "checks": {
            "suite_ok": suite_ok,
            "evidence_ok": evidence_ok,
            "contract_ok": contract_ok,
            "snapshot_ok": snapshot_ok,
            "acceptance_ok": acceptance_ok,
            "vision_evidence_ok": vision_evidence_ok,
        },
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-command readiness check for 4.10 delivery bundle outputs."
    )
    parser.add_argument(
        "--session-file",
        type=Path,
        default=Path("captures/latest_test_session.json"),
        help="Suite execution session JSON path",
    )
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("captures/latest_joint_chain_evidence.json"),
        help="Joint chain evidence JSON path",
    )
    parser.add_argument(
        "--contract-file",
        type=Path,
        default=Path("captures/latest_uplink_contract_report.json"),
        help="Uplink contract report JSON path",
    )
    parser.add_argument(
        "--snapshot-file",
        type=Path,
        default=Path("captures/latest_acceptance_snapshot.json"),
        help="Acceptance snapshot JSON path",
    )
    parser.add_argument(
        "--acceptance-auto-file",
        type=Path,
        default=Path("captures/latest_411_acceptance_auto_report.json"),
        help="4.11 auto acceptance merged report JSON path",
    )
    parser.add_argument(
        "--acceptance-full-file",
        type=Path,
        default=Path("captures/latest_411_acceptance_full_report.json"),
        help="4.11 full acceptance report JSON path",
    )
    parser.add_argument(
        "--require-vision-evidence",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require 4.16 vision evidence (closure_vision_lock/capture_ready) to pass readiness",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("captures/latest_delivery_bundle_report.json"),
        help="Output report JSON path",
    )
    parser.add_argument(
        "--max-backward-ms",
        type=int,
        default=1500,
        help="Allowed timestamp backward drift in milliseconds for sequencing checks",
    )
    args = parser.parse_args()

    session_file = resolve_path(args.session_file)
    evidence_file = resolve_path(args.evidence_file)
    contract_file = resolve_path(args.contract_file)
    snapshot_file = resolve_path(args.snapshot_file)
    acceptance_auto_file = resolve_path(args.acceptance_auto_file)
    acceptance_full_file = resolve_path(args.acceptance_full_file)
    report_file = resolve_path(args.report_file)

    session_payload = load_json(session_file)
    evidence_payload = load_json(evidence_file)
    contract_payload = load_json(contract_file)
    snapshot_payload = load_json(snapshot_file)
    acceptance_auto_payload = load_json(acceptance_auto_file)
    acceptance_full_payload = load_json(acceptance_full_file)

    suite_ok, suite_failures = check_suite_payload(session_payload)
    evidence_ok, evidence_failures = check_evidence_payload(evidence_payload)
    contract_ok, contract_failures = check_contract_payload(contract_payload)
    snapshot_ok, snapshot_failures = check_snapshot_payload(snapshot_payload)
    acceptance_ok, vision_evidence_ok, acceptance_failures, acceptance_warnings = check_acceptance_payloads(
        acceptance_auto_payload,
        acceptance_full_payload,
        bool(args.require_vision_evidence),
    )
    consistency_failures, consistency_warnings = check_consistency(
        session_payload,
        evidence_payload,
        contract_payload,
        snapshot_payload,
        max_backward_ms=max(0, int(args.max_backward_ms)),
    )

    failures = (
        suite_failures
        + evidence_failures
        + contract_failures
        + snapshot_failures
        + acceptance_failures
        + consistency_failures
    )
    warnings = consistency_warnings + acceptance_warnings

    report = build_report(
        session_file=session_file,
        evidence_file=evidence_file,
        contract_file=contract_file,
        snapshot_file=snapshot_file,
        acceptance_auto_file=acceptance_auto_file,
        acceptance_full_file=acceptance_full_file,
        suite_ok=suite_ok,
        evidence_ok=evidence_ok,
        contract_ok=contract_ok,
        snapshot_ok=snapshot_ok,
        acceptance_ok=acceptance_ok,
        vision_evidence_ok=vision_evidence_ok,
        failures=failures,
        warnings=warnings,
    )
    write_json(report_file, report)

    print("Delivery Bundle Readiness Report")
    print(f"result={report['result']}")
    print(f"check_failures={report['failure_count']}")
    print(f"warnings={report['warning_count']}")
    print(f"report_file={report_file.as_posix()}")
    for item in failures:
        print(f"- {item}")
    for item in warnings:
        print(f"- WARN: {item}")

    if failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
