from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import field_trial_recorder


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = field_trial_recorder.DEFAULT_OUTPUT_DIR
DEFAULT_REPORT_FILE = PROJECT_ROOT / "captures" / "latest_field_evidence_gate_report.json"
DEFAULT_MISSION_REPORT_FILE = PROJECT_ROOT / "captures" / "latest_field_mission_final_report.json"
DEFAULT_PREFLIGHT_REPORT_FILE = PROJECT_ROOT / "captures" / "latest_field_collection_preflight_report.json"
DEFAULT_STRICT_CLOSURE_REPORT_FILE = PROJECT_ROOT / "captures" / "latest_real_drone_strict_closure_report.json"
CORE_TARGETS = ("drone", "person", "car")
CORE_DISTANCES_M = (10, 30, 50)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_MODEL_LABEL = field_trial_recorder.DEFAULT_MODEL_LABEL
EXPECTED_MODEL_SHA256 = field_trial_recorder.DEFAULT_MODEL_SHA256
MIN_STABILITY_DURATION_S = 1200.0
MIN_REAL_EPOCH_MS = 946_684_800_000
VERIFIABLE_DISTANCE_SOURCES = {"laser", "tape", "marked_site"}


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def is_sha256(value: Any) -> bool:
    return bool(SHA256_PATTERN.fullmatch(str(value or "").lower()))


def report_session_id(report: dict[str, Any]) -> str:
    metadata = report.get("metadata", {})
    return str(metadata.get("session_id", "")) if isinstance(metadata, dict) else ""


def report_eligibility(
    report: dict[str, Any],
    *,
    expected_model_label: str = EXPECTED_MODEL_LABEL,
    expected_model_sha256: str = EXPECTED_MODEL_SHA256,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    metadata = report.get("metadata", {})
    runtime = report.get("runtime", {})
    summary = report.get("summary", {})
    model_evidence = report.get("model_evidence", {})
    samples_evidence = report.get("samples_evidence", {})
    video_evidence = report.get("video_evidence", {})
    if not all(
        isinstance(value, dict)
        for value in (metadata, runtime, summary, model_evidence, samples_evidence, video_evidence)
    ):
        return False, ["schema_invalid"]
    session_id = report_session_id(report)
    if report.get("result") != "PASS":
        reasons.append("recording_not_passed")
    if not bool(report.get("evidence_complete")):
        reasons.append("evidence_incomplete")
    if not bool(summary.get("trial_valid")):
        reasons.append("trial_invalid")
    node_boot_ids = summary.get("node_boot_ids", [])
    if (
        not bool(summary.get("node_boot_session_valid"))
        or bool(summary.get("node_reset_observed"))
        or not isinstance(node_boot_ids, list)
        or len(node_boot_ids) != 1
    ):
        reasons.append("node_boot_session_invalid")
    if not bool(summary.get("model_label_ok")):
        reasons.append("model_label_invalid")
    observed_labels = summary.get("observed_model_labels", [])
    if (
        str(summary.get("expected_model_label", "")) != expected_model_label
        or observed_labels != [expected_model_label]
    ):
        reasons.append("official_model_label_not_bound")
    expected_hash = str(expected_model_sha256).lower()
    if (
        model_evidence.get("state") != "VERIFIED"
        or str(model_evidence.get("expected_sha256", "")).lower() != expected_hash
        or str(model_evidence.get("actual_sha256", "")).lower() != expected_hash
    ):
        reasons.append("official_model_hash_not_bound")
    if safe_float(runtime.get("actual_elapsed_s", 0.0), 0.0) <= 0.0:
        reasons.append("actual_duration_missing")
    started_ms = safe_int(report.get("started_ms", 0), 0)
    ended_ms = safe_int(report.get("ended_ms", 0), 0)
    if started_ms < MIN_REAL_EPOCH_MS or ended_ms <= started_ms:
        reasons.append("recording_time_invalid")
    required_metadata = ("action", "site", "weather", "lighting", "video_ref")
    if any(not str(metadata.get(field, "")).strip() for field in required_metadata):
        reasons.append("metadata_incomplete")
    if (
        str(metadata.get("trial_kind", "distance")) == "distance"
        and str(metadata.get("distance_source", "")) not in VERIFIABLE_DISTANCE_SOURCES
    ):
        reasons.append("distance_source_not_verifiable")
    sample_count = safe_int(summary.get("sample_count", 0), 0)
    if sample_count <= 0:
        reasons.append("samples_missing")
    if safe_int(summary.get("physical_camera_sample_count", 0), 0) != sample_count:
        reasons.append("non_physical_camera_samples")
    if not is_sha256(samples_evidence.get("sha256", "")):
        reasons.append("samples_hash_invalid")
    if video_evidence.get("state") != "VERIFIED" or not is_sha256(video_evidence.get("sha256", "")):
        reasons.append("video_unverified")
    video_reference = str(video_evidence.get("reference", ""))
    if (
        session_id
        and (
            session_id not in video_reference
            and session_id not in str(video_evidence.get("file_path", ""))
        )
    ):
        reasons.append("video_session_binding_missing")
    if video_reference != str(metadata.get("video_ref", "")):
        reasons.append("video_reference_mismatch")
    if not session_id:
        reasons.append("session_id_missing")
    return not reasons, reasons


def distance_matches(report: dict[str, Any], target: str, distance_m: int) -> bool:
    metadata = report.get("metadata", {})
    if not isinstance(metadata, dict):
        return False
    return bool(
        str(metadata.get("trial_kind", "distance")) == "distance"
        and str(metadata.get("target", "")) == target
        and abs(safe_float(metadata.get("distance_m", -1.0), -1.0) - float(distance_m)) <= 0.25
    )


def evaluate_evidence_reports(
    reports: list[dict[str, Any]],
    *,
    trials_per_cell: int = 3,
    load_errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    required_trials = max(1, int(trials_per_cell))
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    normalized_load_errors = list(load_errors or [])
    add_check(
        "report_files_loadable",
        not normalized_load_errors,
        {"error_count": len(normalized_load_errors), "errors": normalized_load_errors},
    )

    eligible_reports: list[dict[str, Any]] = []
    invalid_reports: list[dict[str, Any]] = []
    for report in reports:
        eligible, reasons = report_eligibility(report)
        if eligible:
            eligible_reports.append(report)
        else:
            invalid_reports.append({"session_id": report_session_id(report), "reasons": reasons})

    session_ids = [report_session_id(report) for report in reports if report_session_id(report)]
    duplicate_sessions = sorted(session_id for session_id, count in Counter(session_ids).items() if count > 1)
    add_check(
        "unique_session_ids",
        not duplicate_sessions,
        {"duplicate_session_ids": duplicate_sessions},
    )

    video_hashes = [
        str(report.get("video_evidence", {}).get("sha256", "")).lower()
        for report in eligible_reports
    ]
    duplicate_video_hashes = sorted(value for value, count in Counter(video_hashes).items() if value and count > 1)
    add_check(
        "independent_video_hashes",
        not duplicate_video_hashes,
        {"duplicate_count": len(duplicate_video_hashes), "duplicate_hashes": duplicate_video_hashes},
    )

    distance_reports = [
        report
        for report in eligible_reports
        if str(report.get("metadata", {}).get("trial_kind", "distance")) == "distance"
        and str(report.get("metadata", {}).get("target", "")) in CORE_TARGETS
    ]
    matrix: dict[str, Any] = {}
    completed_distance_trials = 0
    next_actions: list[dict[str, Any]] = []
    for target in CORE_TARGETS:
        for distance_m in CORE_DISTANCES_M:
            cell = [report for report in distance_reports if distance_matches(report, target, distance_m)]
            cell_key = f"{target}_{distance_m}m"
            outcomes = Counter(str(report.get("summary", {}).get("outcome", "UNKNOWN")) for report in cell)
            matrix[cell_key] = {
                "eligible_count": len(cell),
                "required_count": required_trials,
                "outcomes": dict(sorted(outcomes.items())),
                "session_ids": [report_session_id(report) for report in cell],
            }
            completed_distance_trials += min(len(cell), required_trials)
            missing_count = max(0, required_trials - len(cell))
            if missing_count:
                next_actions.append(
                    {
                        "kind": "distance",
                        "target": target,
                        "distance_m": distance_m,
                        "remaining_trials": missing_count,
                    }
                )
            add_check(
                f"matrix_{target}_{distance_m}m",
                len(cell) >= required_trials,
                matrix[cell_key],
            )

            if target == "drone" and distance_m == 10:
                detected_count = outcomes.get("DETECTED", 0)
                add_check(
                    "performance_drone_10m",
                    len(cell) >= required_trials and detected_count == len(cell),
                    {
                        "detected": detected_count,
                        "eligible_count": len(cell),
                        "required_rate": 1.0,
                    },
                )
            elif target == "drone" and distance_m == 30:
                detected_count = outcomes.get("DETECTED", 0)
                detected_rate = detected_count / len(cell) if cell else 0.0
                add_check(
                    "performance_drone_30m",
                    len(cell) >= required_trials and detected_rate >= (2 / 3),
                    {
                        "detected": detected_count,
                        "eligible_count": len(cell),
                        "detected_rate": round(detected_rate, 6),
                        "required_rate": round(2 / 3, 6),
                    },
                )
            elif target != "drone":
                false_lock_count = outcomes.get("FALSE_LOCK", 0)
                add_check(
                    f"performance_{target}_{distance_m}m",
                    len(cell) >= required_trials and false_lock_count == 0,
                    {"false_locks": false_lock_count, "eligible_count": len(cell)},
                )

    long_reports = [
        report
        for report in eligible_reports
        if str(report.get("metadata", {}).get("trial_kind", "distance")) == "long_stability"
    ]

    def stable_report(report: dict[str, Any]) -> bool:
        runtime = report.get("runtime", {})
        summary = report.get("summary", {})
        return bool(
            safe_float(runtime.get("duration_s", 0.0), 0.0) >= MIN_STABILITY_DURATION_S
            and safe_float(runtime.get("actual_elapsed_s", 0.0), 0.0)
            >= MIN_STABILITY_DURATION_S
            and safe_int(summary.get("status_interruption_count", 0), 0) == 0
            and str(summary.get("outcome", "")) == "CLEAR"
        )

    static_candidates = [
        report
        for report in long_reports
        if str(report.get("metadata", {}).get("target", "")) == "clutter"
        and "static" in str(report.get("metadata", {}).get("action", "")).lower()
        and stable_report(report)
    ]
    traffic_candidates = [
        report
        for report in long_reports
        if str(report.get("metadata", {}).get("target", "")) in {"person", "car", "ebike"}
        and stable_report(report)
    ]
    add_check(
        "long_stability_static",
        bool(static_candidates),
        {"eligible_sessions": [report_session_id(report) for report in static_candidates]},
    )
    add_check(
        "long_stability_normal_traffic",
        bool(traffic_candidates),
        {"eligible_sessions": [report_session_id(report) for report in traffic_candidates]},
    )
    if not static_candidates:
        next_actions.append({"kind": "long_stability", "scene": "static_clutter", "remaining_runs": 1})
    if not traffic_candidates:
        next_actions.append({"kind": "long_stability", "scene": "normal_traffic", "remaining_runs": 1})

    passed_count = sum(bool(item["passed"]) for item in checks)
    failures = [str(item["name"]) for item in checks if not item["passed"]]
    return {
        "schema_version": "field_evidence_gate_v1",
        "result": "GO" if passed_count == len(checks) else "NO-GO",
        "passed_count": passed_count,
        "total_count": len(checks),
        "failures": failures,
        "checks": checks,
        "source_report_count": len(reports),
        "eligible_report_count": len(eligible_reports),
        "invalid_report_count": len(invalid_reports),
        "invalid_reports": invalid_reports,
        "load_errors": normalized_load_errors,
        "distance_trial_count": len(distance_reports),
        "long_stability_count": len(long_reports),
        "required_distance_trial_count": len(CORE_TARGETS) * len(CORE_DISTANCES_M) * required_trials,
        "completed_distance_trial_count": completed_distance_trials,
        "remaining_distance_trial_count": (
            len(CORE_TARGETS) * len(CORE_DISTANCES_M) * required_trials
            - completed_distance_trials
        ),
        "completed_stability_run_count": int(bool(static_candidates)) + int(bool(traffic_candidates)),
        "required_stability_run_count": 2,
        "next_actions": next_actions,
        "matrix": matrix,
        "raw_reports_modified": False,
    }


def evaluate_mission_final(
    matrix_result: dict[str, Any],
    reports: list[dict[str, Any]],
    *,
    preflight_report: dict[str, Any],
    strict_closure_report: dict[str, Any],
    max_mission_duration_s: float = 8 * 60 * 60,
) -> dict[str, Any]:
    checks = [dict(item) for item in matrix_result.get("checks", []) if isinstance(item, dict)]

    def add_check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    preflight_checks = {
        str(item.get("name", "")): bool(item.get("passed"))
        for item in preflight_report.get("checks", [])
        if isinstance(item, dict)
    }
    preflight_ms = safe_int(preflight_report.get("generated_ms", 0), 0)
    preflight_ok = bool(
        preflight_report.get("result") == "GO"
        and preflight_report.get("mode") == "same-event"
        and safe_int(preflight_report.get("passed_count", 0), 0)
        == safe_int(preflight_report.get("total_count", -1), -1)
        and not preflight_report.get("failures")
        and preflight_ms >= MIN_REAL_EPOCH_MS
        and preflight_checks.get("physical_camera_source") is True
        and preflight_checks.get("deployed_model_hash") is True
        and preflight_checks.get("cloud_test_32_of_32") is True
    )
    add_check(
        "same_event_preflight_go",
        preflight_ok,
        {
            "result": preflight_report.get("result", "MISSING"),
            "mode": preflight_report.get("mode", "MISSING"),
            "generated_ms": preflight_ms,
            "passed_count": safe_int(preflight_report.get("passed_count", 0), 0),
            "total_count": safe_int(preflight_report.get("total_count", 0), 0),
            "required_checks": {
                name: preflight_checks.get(name, False)
                for name in (
                    "physical_camera_source",
                    "deployed_model_hash",
                    "cloud_test_32_of_32",
                )
            },
        },
    )

    event_id = str(strict_closure_report.get("latest_event_id", "") or "")
    national = strict_closure_report.get("national_first_evidence", {})
    export = strict_closure_report.get("strict_export_snapshot_evidence", {})
    freshness = strict_closure_report.get("national_first_event_freshness", {})
    counts = strict_closure_report.get("counts", {})
    if not isinstance(national, dict):
        national = {}
    if not isinstance(export, dict):
        export = {}
    if not isinstance(freshness, dict):
        freshness = {}
    if not isinstance(counts, dict):
        counts = {}

    def strict_block_ok(block: dict[str, Any]) -> bool:
        source = str(block.get("source", "") or "").strip()
        return bool(
            block.get("result") == "PASS"
            and safe_int(block.get("passed_count", 0), 0) == 15
            and safe_int(block.get("total_count", 0), 0) == 15
            and event_id
            and event_id != "NONE"
            and str(block.get("expected_event_id", "")) == event_id
            and str(block.get("actual_event_id", "")) == event_id
            and safe_int(block.get("physical_camera_source", 0), 0) == 1
            and source.isdigit()
            and int(source) >= 0
            and str(block.get("detector_model_label", "")) == EXPECTED_MODEL_LABEL
        )

    strict_checked_ms = safe_int(strict_closure_report.get("checked_ms", 0), 0)
    event_timestamp_ms = safe_int(freshness.get("event_timestamp_ms", 0), 0)
    strict_ok = bool(
        strict_closure_report.get("result") == "PASS"
        and strict_block_ok(national)
        and strict_block_ok(export)
        and freshness.get("result") == "PASS"
        and safe_int(counts.get("national_first_checks_passed", 0), 0) == 15
        and safe_int(counts.get("national_first_checks_total", 0), 0) == 15
        and safe_int(counts.get("strict_export_snapshot_checks_passed", 0), 0) == 15
        and safe_int(counts.get("strict_export_snapshot_checks_total", 0), 0) == 15
    )
    add_check(
        "real_event_strict_15_of_15",
        strict_ok,
        {
            "result": strict_closure_report.get("result", "MISSING"),
            "event_id": event_id or "NONE",
            "checked_ms": strict_checked_ms,
            "event_timestamp_ms": event_timestamp_ms,
            "national_first": {
                "result": national.get("result", "MISSING"),
                "checks": f"{safe_int(national.get('passed_count', 0), 0)}/{safe_int(national.get('total_count', 0), 0)}",
                "source": national.get("source", "NONE"),
                "physical_camera_source": safe_int(national.get("physical_camera_source", 0), 0),
                "detector_model_label": national.get("detector_model_label", "none"),
            },
            "strict_export": {
                "result": export.get("result", "MISSING"),
                "checks": f"{safe_int(export.get('passed_count', 0), 0)}/{safe_int(export.get('total_count', 0), 0)}",
                "source": export.get("source", "NONE"),
                "physical_camera_source": safe_int(export.get("physical_camera_source", 0), 0),
                "detector_model_label": export.get("detector_model_label", "none"),
            },
        },
    )

    physical_fusion_sessions: list[dict[str, Any]] = []
    for report in reports:
        eligible, _reasons = report_eligibility(report)
        if not eligible:
            continue
        metadata = report.get("metadata", {})
        summary = report.get("summary", {})
        if not isinstance(metadata, dict) or not isinstance(summary, dict):
            continue
        if (
            str(metadata.get("trial_kind", "distance")) != "distance"
            or str(metadata.get("target", "")) != "drone"
        ):
            continue
        fusion_event_ids = summary.get("physical_fusion_event_ids", [])
        if not isinstance(fusion_event_ids, list):
            fusion_event_ids = []
        normalized_event_ids = [str(value or "") for value in fusion_event_ids]
        fusion_sample_count = safe_int(summary.get("physical_fusion_sample_count", 0), 0)
        if fusion_sample_count <= 0 or event_id not in normalized_event_ids:
            continue
        physical_fusion_sessions.append(
            {
                "session_id": report_session_id(report),
                "physical_fusion_sample_count": fusion_sample_count,
                "physical_fusion_event_ids": normalized_event_ids,
            }
        )
    add_check(
        "real_sensor_fusion_evidence",
        bool(strict_ok and physical_fusion_sessions),
        {
            "strict_event_id": event_id or "NONE",
            "required": (
                "same sample: physical camera YOLO lock + confirmed radar track + "
                "test mode off + advanced fusion on + active strict event"
            ),
            "eligible_sessions": physical_fusion_sessions,
        },
    )

    mission_duration_ms = max(1, int(float(max_mission_duration_s) * 1000))
    mission_deadline_ms = preflight_ms + mission_duration_ms
    mission_reports: list[dict[str, Any]] = []
    for report in reports:
        eligible, _reasons = report_eligibility(report)
        if not eligible:
            continue
        metadata = report.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        trial_kind = str(metadata.get("trial_kind", "distance"))
        target = str(metadata.get("target", ""))
        if trial_kind == "distance" and target in CORE_TARGETS:
            mission_reports.append(report)
        elif trial_kind == "long_stability":
            mission_reports.append(report)

    report_times = [
        {
            "session_id": report_session_id(report),
            "started_ms": safe_int(report.get("started_ms", 0), 0),
            "ended_ms": safe_int(report.get("ended_ms", 0), 0),
        }
        for report in mission_reports
    ]
    report_times_ok = bool(
        report_times
        and all(
            preflight_ms <= item["started_ms"] <= item["ended_ms"] <= mission_deadline_ms
            for item in report_times
        )
    )
    strict_times_ok = bool(
        preflight_ms <= event_timestamp_ms <= strict_checked_ms <= mission_deadline_ms
    )
    time_window_ok = bool(preflight_ok and strict_times_ok and report_times_ok)
    out_of_window_sessions = [
        item["session_id"]
        for item in report_times
        if not (
            preflight_ms <= item["started_ms"] <= item["ended_ms"] <= mission_deadline_ms
        )
    ]
    add_check(
        "single_field_mission_time_window",
        time_window_ok,
        {
            "preflight_ms": preflight_ms,
            "deadline_ms": mission_deadline_ms,
            "max_duration_s": float(max_mission_duration_s),
            "event_timestamp_ms": event_timestamp_ms,
            "strict_checked_ms": strict_checked_ms,
            "eligible_mission_report_count": len(report_times),
            "out_of_window_sessions": out_of_window_sessions,
        },
    )

    passed_count = sum(bool(item.get("passed")) for item in checks)
    failures = [str(item.get("name", "unknown")) for item in checks if not item.get("passed")]
    return {
        **matrix_result,
        "schema_version": "field_mission_final_v2",
        "mode": "mission-final",
        "result": "GO" if passed_count == len(checks) else "NO-GO",
        "passed_count": passed_count,
        "total_count": len(checks),
        "failures": failures,
        "checks": checks,
        "mission_window": {
            "preflight_ms": preflight_ms,
            "deadline_ms": mission_deadline_ms,
            "max_duration_s": float(max_mission_duration_s),
        },
        "strict_event_id": event_id or "NONE",
    }


def load_reports(input_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    reports: list[dict[str, Any]] = []
    load_errors: list[dict[str, str]] = []
    if not input_dir.exists():
        return reports, [{"path": input_dir.as_posix(), "error": "INPUT_DIR_MISSING"}]
    for report_path in sorted(input_dir.glob("*/trial_report.json")):
        try:
            value = json.loads(report_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            load_errors.append({"path": report_path.as_posix(), "error": type(exc).__name__})
            continue
        if not isinstance(value, dict):
            load_errors.append({"path": report_path.as_posix(), "error": "ROOT_NOT_OBJECT"})
            continue
        reports.append(value)
    return reports, load_errors


def load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"{type(exc).__name__}:{exc}"
    if not isinstance(value, dict):
        return {}, "ROOT_NOT_OBJECT"
    return value, ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only gate for the 10/30/50 m real-drone matrix and two 20-minute stability runs."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--trials-per-cell", type=int, default=3)
    parser.add_argument("--mode", choices=("matrix", "mission-final"), default="matrix")
    parser.add_argument("--preflight-report", type=Path, default=DEFAULT_PREFLIGHT_REPORT_FILE)
    parser.add_argument("--strict-closure-report", type=Path, default=DEFAULT_STRICT_CLOSURE_REPORT_FILE)
    parser.add_argument("--max-mission-hours", type=float, default=8.0)
    parser.add_argument("--report-file", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_dir = resolve_path(args.input_dir)
    reports, load_errors = load_reports(input_dir)
    result = evaluate_evidence_reports(
        reports,
        trials_per_cell=args.trials_per_cell,
        load_errors=load_errors,
    )
    mission_input_errors: dict[str, str] = {}
    if args.mode == "mission-final":
        preflight_path = resolve_path(args.preflight_report)
        strict_path = resolve_path(args.strict_closure_report)
        preflight_report, preflight_error = load_json_object(preflight_path)
        strict_report, strict_error = load_json_object(strict_path)
        if preflight_error:
            mission_input_errors["preflight_report"] = preflight_error
        if strict_error:
            mission_input_errors["strict_closure_report"] = strict_error
        result = evaluate_mission_final(
            result,
            reports,
            preflight_report=preflight_report,
            strict_closure_report=strict_report,
            max_mission_duration_s=max(1.0, float(args.max_mission_hours) * 60 * 60),
        )
        result["mission_inputs"] = {
            "preflight_report": preflight_path.as_posix(),
            "strict_closure_report": strict_path.as_posix(),
            "errors": mission_input_errors,
        }
    result["generated_ms"] = int(time.time() * 1000)
    result["input_dir"] = input_dir.as_posix()
    default_report = DEFAULT_MISSION_REPORT_FILE if args.mode == "mission-final" else DEFAULT_REPORT_FILE
    report_file = resolve_path(args.report_file or default_report)
    atomic_write_json(report_file, result)
    print("Field Evidence Gate")
    print(f"mode={args.mode}")
    print(f"result={result['result']}")
    print(f"checks={result['passed_count']}/{result['total_count']}")
    print(
        f"reports=source:{result['source_report_count']},eligible:{result['eligible_report_count']},"
        f"distance:{result['distance_trial_count']},long_stability:{result['long_stability_count']}"
    )
    print(
        f"remaining=distance:{result['remaining_distance_trial_count']},"
        f"stability:{result['required_stability_run_count'] - result['completed_stability_run_count']}"
    )
    for failure in result["failures"]:
        print(f"- {failure}")
    for action in result.get("next_actions", []):
        if action.get("kind") == "distance":
            print(
                "NEXT,distance,"
                f"target={action.get('target')},distance_m={action.get('distance_m')},"
                f"remaining={action.get('remaining_trials')}"
            )
        else:
            print(
                "NEXT,long_stability,"
                f"scene={action.get('scene')},remaining={action.get('remaining_runs')}"
            )
    print(f"report_file={report_file.as_posix()}")
    return 0 if result["result"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
