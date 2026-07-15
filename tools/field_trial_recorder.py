from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "captures" / "session_logs" / "field_trials"
DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "yolov8n_drone.onnx"
DEFAULT_MODEL_SHA256 = "c33aba9e6e24ce24ae6147a538b46b0c1080093242f0ad1c59100c738121ac74"
DEFAULT_MODEL_LABEL = "drone-v4b-hardneg-deployed"
DEFAULT_FSYNC_INTERVAL_S = 1.0
SCHEMA_VERSION = 1
MIN_REAL_EPOCH_MS = 946_684_800_000
NEGATIVE_TARGETS = {"person", "car", "ebike", "bird", "airplane", "kite", "clutter"}
TARGETS = {"drone", *NEGATIVE_TARGETS}
DISTANCE_SOURCES = {"laser", "tape", "marked_site", "estimate", "not_measured"}
TRIAL_KINDS = {"distance", "long_stability"}


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def sanitize_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return token.strip("_.-") or "session"


def is_physical_camera_source(value: Any) -> bool:
    if isinstance(value, int):
        return value >= 0
    source = str(value if value is not None else "").strip()
    return source.isdigit() and int(source) >= 0


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


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


def fetch_json(url: str, timeout_s: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=max(0.1, float(timeout_s))) as response:
        value = json.loads(response.read().decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("response root is not an object")
    return value


def status_age_ms(payload: dict[str, Any], now_ms: int, *, timestamp_key: str) -> int:
    timestamp_ms = safe_int(payload.get(timestamp_key, 0), 0)
    if timestamp_ms >= MIN_REAL_EPOCH_MS:
        return max(0, now_ms - timestamp_ms)
    return max(0, safe_int(payload.get("stale_age_ms", now_ms), now_ms))


def max_drone_score(vision: dict[str, Any]) -> float:
    scores: list[float] = []
    if str(vision.get("auto_lock_class_name", "")).lower() == "drone":
        scores.append(safe_float(vision.get("auto_lock_score", 0.0), 0.0))
    detections = vision.get("yolo_detections", [])
    if isinstance(detections, list):
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            if str(detection.get("class_name", "")).lower() != "drone":
                continue
            scores.append(safe_float(detection.get("score", 0.0), 0.0))
    return round(max(scores, default=0.0), 6)


def build_sample(
    *,
    host_timestamp_ms: int,
    vision: dict[str, Any] | None,
    node: dict[str, Any] | None,
    vision_error: str = "",
    node_error: str = "",
    max_status_age_ms: int,
) -> dict[str, Any]:
    vision_payload = vision if isinstance(vision, dict) else {}
    node_payload = node if isinstance(node, dict) else {}
    vision_age_ms = status_age_ms(vision_payload, host_timestamp_ms, timestamp_key="timestamp_ms")
    node_age_ms = status_age_ms(node_payload, host_timestamp_ms, timestamp_key="last_update_ms")

    vision_valid = bool(
        not vision_error
        and safe_int(vision_payload.get("available", vision_payload.get("ok", 0)), 0)
        and safe_int(vision_payload.get("source_ready", 0), 0)
        and safe_int(vision_payload.get("detector_ready", 0), 0)
        and safe_int(vision_payload.get("vision_chain_ready", 0), 0)
        and vision_age_ms <= max_status_age_ms
    )
    node_valid = bool(
        not node_error
        and safe_int(node_payload.get("available", node_payload.get("ok", 0)), 0)
        and safe_int(node_payload.get("online", 0), 0)
        and node_age_ms <= max_status_age_ms
    )
    frame_ready = bool(
        safe_int(vision_payload.get("frame_content_ready", 0), 0)
        and str(vision_payload.get("frame_quality_reason", "")) == "OK"
    )
    source = vision_payload.get("source", "")
    physical_camera_source = is_physical_camera_source(source)
    yolo_auto_locked = bool(
        vision_valid
        and frame_ready
        and str(vision_payload.get("vision_state", "")) == "VISION_LOCKED"
        and str(vision_payload.get("lock_source", "")) == "YOLO_AUTO"
        and str(vision_payload.get("auto_lock_class_name", "")).lower() == "drone"
    )
    track_active = safe_int(node_payload.get("track_active", 0), 0)
    track_confirmed = safe_int(node_payload.get("track_confirmed", 0), 0)
    event_active = safe_int(node_payload.get("event_active", 0), 0)
    event_id = str(node_payload.get("event_id", "NONE") or "NONE")
    test_mode_known = "test_mode_enabled" in node_payload
    test_mode_enabled = safe_int(node_payload.get("test_mode_enabled", 0), 0)
    node_boot_id = str(node_payload.get("boot_id", "UNKNOWN") or "UNKNOWN").strip()
    node_reset_reason = str(node_payload.get("reset_reason", "UNKNOWN") or "UNKNOWN").strip().upper()
    node_uptime_ms = safe_int(node_payload.get("node_uptime_ms", 0), 0)
    node_boot_telemetry_valid = bool(
        node_boot_id not in {"", "UNKNOWN", "NONE"}
        and node_reset_reason not in {"", "UNKNOWN", "NONE"}
        and node_uptime_ms >= 0
    )
    fusion_enabled = safe_int(node_payload.get("fusion_enabled", 0), 0)
    fusion_level = str(node_payload.get("fusion_level", "NONE") or "NONE").upper()
    fusion_stage = str(node_payload.get("fusion_stage", "NONE") or "NONE").upper()
    fusion_confidence = safe_float(node_payload.get("fusion_confidence", 0.0), 0.0)
    fusion_reason = str(node_payload.get("fusion_reason", "NONE") or "NONE").upper()
    sample_valid = bool(
        vision_valid
        and node_valid
        and frame_ready
        and physical_camera_source
        and node_boot_telemetry_valid
    )
    physical_fusion = bool(
        sample_valid
        and yolo_auto_locked
        and track_active == 1
        and track_confirmed == 1
        and event_active == 1
        and event_id != "NONE"
        and test_mode_known
        and test_mode_enabled == 0
        and fusion_enabled == 1
        and fusion_level in {"MID", "HIGH"}
        and fusion_stage != "NONE"
        and fusion_confidence > 0.0
        and fusion_reason not in {"", "NONE", "LEGACY_SOURCE_COUNT"}
    )

    errors = [message for message in (vision_error, node_error) if message]
    return {
        "host_timestamp_ms": int(host_timestamp_ms),
        "sample_valid": sample_valid,
        "vision_valid": vision_valid,
        "node_valid": node_valid,
        "errors": errors,
        "vision_age_ms": int(vision_age_ms),
        "node_age_ms": int(node_age_ms),
        "vision_state": str(vision_payload.get("vision_state", "UNKNOWN")),
        "lock_source": str(vision_payload.get("lock_source", "NONE")),
        "auto_lock_class_name": str(vision_payload.get("auto_lock_class_name", "none")),
        "auto_lock_score": round(safe_float(vision_payload.get("auto_lock_score", 0.0)), 6),
        "max_drone_score": max_drone_score(vision_payload),
        "yolo_auto_locked": yolo_auto_locked,
        "frame_content_ready": int(frame_ready),
        "frame_quality_reason": str(vision_payload.get("frame_quality_reason", "UNKNOWN")),
        "source": str(source),
        "physical_camera_source": physical_camera_source,
        "capture_backend": str(vision_payload.get("capture_backend", "UNKNOWN")),
        "detector_model_label": str(vision_payload.get("detector_model_label", "UNKNOWN")),
        "track_active": track_active,
        "track_confirmed": track_confirmed,
        "track_id": safe_int(node_payload.get("track_id", 0), 0),
        "risk_level": str(node_payload.get("risk_level", "NONE")),
        "risk_score": round(safe_float(node_payload.get("risk_score", 0.0)), 3),
        "event_active": event_active,
        "event_id": event_id,
        "test_mode_known": int(test_mode_known),
        "test_mode_enabled": test_mode_enabled,
        "node_boot_id": node_boot_id,
        "node_reset_reason": node_reset_reason,
        "node_uptime_ms": node_uptime_ms,
        "node_boot_telemetry_valid": node_boot_telemetry_valid,
        "fusion_enabled": fusion_enabled,
        "fusion_level": fusion_level,
        "fusion_stage": fusion_stage,
        "fusion_confidence": round(fusion_confidence, 6),
        "fusion_reason": fusion_reason,
        "physical_fusion": physical_fusion,
        "ld2451_valid": safe_int(node_payload.get("ld2451_valid", 0), 0),
        "ld2451_range_m": round(safe_float(node_payload.get("ld2451_range_m", 0.0)), 3),
        "ld2451_speed_mps": round(safe_float(node_payload.get("ld2451_speed_mps", 0.0)), 3),
        "ld2451_approach": safe_int(node_payload.get("ld2451_approach", 0), 0),
        "far_motion_trigger": safe_int(node_payload.get("far_motion_trigger", 0), 0),
    }


def summarize_samples(
    samples: list[dict[str, Any]],
    *,
    target: str,
    expected_model_label: str,
    observed_model_labels: set[str],
    min_valid_ratio: float,
    min_sample_count: int = 1,
) -> dict[str, Any]:
    sample_count = len(samples)
    valid_count = sum(bool(sample.get("sample_valid")) for sample in samples)
    valid_ratio = valid_count / sample_count if sample_count else 0.0
    model_label_ok = observed_model_labels == {expected_model_label}

    lock_episode_count = 0
    longest_lock_duration_ms = 0
    episode_start_ms: int | None = None
    episode_last_ms: int | None = None
    lock_sample_count = 0
    for sample in samples:
        timestamp_ms = safe_int(sample.get("host_timestamp_ms", 0), 0)
        locked = bool(sample.get("sample_valid") and sample.get("yolo_auto_locked"))
        if locked:
            lock_sample_count += 1
            if episode_start_ms is None:
                lock_episode_count += 1
                episode_start_ms = timestamp_ms
            episode_last_ms = timestamp_ms
            continue
        if episode_start_ms is not None and episode_last_ms is not None:
            longest_lock_duration_ms = max(longest_lock_duration_ms, episode_last_ms - episode_start_ms)
        episode_start_ms = None
        episode_last_ms = None
    if episode_start_ms is not None and episode_last_ms is not None:
        longest_lock_duration_ms = max(longest_lock_duration_ms, episode_last_ms - episode_start_ms)

    max_score = max((safe_float(sample.get("max_drone_score", 0.0)) for sample in samples), default=0.0)
    valid_ranges = [
        safe_float(sample.get("ld2451_range_m", 0.0))
        for sample in samples
        if sample.get("sample_valid") and safe_int(sample.get("ld2451_valid", 0), 0)
    ]
    physical_fusion_samples = [
        sample for sample in samples if bool(sample.get("sample_valid") and sample.get("physical_fusion"))
    ]
    physical_fusion_event_ids = sorted(
        {
            str(sample.get("event_id", "") or "")
            for sample in physical_fusion_samples
            if str(sample.get("event_id", "") or "") not in {"", "NONE"}
        }
    )
    node_boot_ids = sorted(
        {
            str(sample.get("node_boot_id", "") or "").strip()
            for sample in samples
            if str(sample.get("node_boot_id", "") or "").strip() not in {"", "UNKNOWN", "NONE"}
        }
    )
    node_reset_reasons = sorted(
        {
            str(sample.get("node_reset_reason", "") or "").strip().upper()
            for sample in samples
            if str(sample.get("node_reset_reason", "") or "").strip().upper()
            not in {"", "UNKNOWN", "NONE"}
        }
    )
    uptime_regression_observed = False
    previous_uptime_by_boot: dict[str, int] = {}
    for sample in samples:
        boot_id = str(sample.get("node_boot_id", "") or "").strip()
        if boot_id in {"", "UNKNOWN", "NONE"}:
            continue
        uptime_ms = safe_int(sample.get("node_uptime_ms", -1), -1)
        if uptime_ms < 0:
            continue
        previous_uptime = previous_uptime_by_boot.get(boot_id)
        if previous_uptime is not None and uptime_ms < previous_uptime:
            uptime_regression_observed = True
        previous_uptime_by_boot[boot_id] = uptime_ms
    node_reset_observed = bool(len(node_boot_ids) > 1 or uptime_regression_observed)
    node_boot_session_valid = bool(len(node_boot_ids) == 1 and not node_reset_observed)
    required_sample_count = max(1, int(min_sample_count))
    trial_valid = bool(
        sample_count >= required_sample_count
        and valid_ratio >= min_valid_ratio
        and model_label_ok
        and node_boot_session_valid
    )
    if not trial_valid:
        outcome = "INVALID_TRIAL"
    elif target == "drone":
        outcome = "DETECTED" if lock_sample_count else "MISSED"
    else:
        outcome = "FALSE_LOCK" if lock_sample_count else "CLEAR"
    performance_pass = bool(
        trial_valid
        and (
            (target == "drone" and outcome == "DETECTED")
            or (target != "drone" and outcome == "CLEAR")
        )
    )

    return {
        "trial_valid": trial_valid,
        "performance_pass": performance_pass,
        "outcome": outcome,
        "sample_count": sample_count,
        "required_sample_count": required_sample_count,
        "valid_sample_count": valid_count,
        "valid_sample_ratio": round(valid_ratio, 6),
        "status_interruption_count": sample_count - valid_count,
        "vision_invalid_count": sum(not bool(sample.get("vision_valid")) for sample in samples),
        "node_invalid_count": sum(not bool(sample.get("node_valid")) for sample in samples),
        "node_boot_session_valid": node_boot_session_valid,
        "node_reset_observed": node_reset_observed,
        "node_uptime_regression_observed": uptime_regression_observed,
        "node_boot_ids": node_boot_ids,
        "node_reset_reasons": node_reset_reasons,
        "node_boot_telemetry_sample_count": sum(
            bool(sample.get("node_boot_telemetry_valid")) for sample in samples
        ),
        "physical_camera_sample_count": sum(
            bool(sample.get("physical_camera_source")) for sample in samples
        ),
        "model_label_ok": model_label_ok,
        "expected_model_label": expected_model_label,
        "observed_model_labels": sorted(observed_model_labels),
        "max_drone_score": round(max_score, 6),
        "yolo_auto_lock_sample_count": lock_sample_count,
        "lock_episode_count": lock_episode_count,
        "longest_lock_duration_ms": int(longest_lock_duration_ms),
        "track_active_sample_count": sum(safe_int(sample.get("track_active", 0), 0) != 0 for sample in samples),
        "track_confirmed_sample_count": sum(
            safe_int(sample.get("track_active", 0), 0) != 0
            and safe_int(sample.get("track_confirmed", 0), 0) != 0
            for sample in samples
        ),
        "test_mode_enabled_sample_count": sum(
            safe_int(sample.get("test_mode_enabled", 0), 0) != 0 for sample in samples
        ),
        "advanced_fusion_enabled_sample_count": sum(
            safe_int(sample.get("fusion_enabled", 0), 0) == 1 for sample in samples
        ),
        "physical_fusion_sample_count": len(physical_fusion_samples),
        "physical_fusion_event_ids": physical_fusion_event_ids,
        "ld2451_valid_sample_count": len(valid_ranges),
        "ld2451_range_min_m": round(min(valid_ranges), 3) if valid_ranges else None,
        "ld2451_range_max_m": round(max(valid_ranges), 3) if valid_ranges else None,
        "ld2451_range_mean_m": round(sum(valid_ranges) / len(valid_ranges), 3) if valid_ranges else None,
        "far_motion_trigger_sample_count": sum(
            safe_int(sample.get("far_motion_trigger", 0), 0) != 0 for sample in samples
        ),
    }


def build_video_evidence(video_ref: str, video_file: Path | None) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "reference": str(video_ref or ""),
        "file_path": "",
        "size_bytes": 0,
        "sha256": "",
        "state": "REFERENCE_ONLY" if video_ref else "MISSING",
    }
    if video_file is None:
        return evidence
    path = resolve_path(video_file)
    evidence["file_path"] = path.as_posix()
    try:
        size_bytes = path.stat().st_size
        if not path.is_file() or size_bytes <= 0:
            evidence["state"] = "EMPTY_OR_INVALID"
            return evidence
        evidence["size_bytes"] = size_bytes
        evidence["sha256"] = sha256_file(path)
        evidence["state"] = "VERIFIED"
    except OSError as exc:
        evidence["state"] = "READ_ERROR"
        evidence["error"] = f"{type(exc).__name__}:{exc}"
    return evidence


def build_model_evidence(model_file: Path, expected_sha256: str) -> dict[str, Any]:
    path = resolve_path(model_file)
    expected_hash = str(expected_sha256 or "").strip().lower()
    evidence: dict[str, Any] = {
        "file_path": path.as_posix(),
        "expected_sha256": expected_hash,
        "actual_sha256": "",
        "size_bytes": 0,
        "state": "READ_ERROR",
    }
    try:
        size_bytes = path.stat().st_size
        if not path.is_file() or size_bytes <= 0:
            evidence["state"] = "EMPTY_OR_INVALID"
            return evidence
        evidence["size_bytes"] = size_bytes
        evidence["actual_sha256"] = sha256_file(path)
        evidence["state"] = (
            "VERIFIED" if evidence["actual_sha256"] == expected_hash else "HASH_MISMATCH"
        )
    except OSError as exc:
        evidence["error"] = f"{type(exc).__name__}:{exc}"
    return evidence


def validate_record_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    session_id = str(getattr(args, "session_id", "") or "").strip()
    target = str(getattr(args, "target", "") or "").strip().lower()
    distance_m = safe_float(getattr(args, "distance_m", -1.0), -1.0)
    distance_source = str(getattr(args, "distance_source", "") or "").strip()
    trial_kind = str(getattr(args, "trial_kind", "distance") or "").strip()
    if not session_id:
        errors.append("session_id_required")
    elif sanitize_token(session_id) != session_id:
        errors.append("session_id_must_be_ascii_token")
    if target not in TARGETS:
        errors.append("unsupported_target")
    if distance_m < 0.0:
        errors.append("distance_m_must_be_non_negative")
    if distance_source not in DISTANCE_SOURCES:
        errors.append("invalid_distance_source")
    if trial_kind not in TRIAL_KINDS:
        errors.append("invalid_trial_kind")
    if distance_source == "not_measured" and distance_m != 0.0:
        errors.append("not_measured_distance_must_be_zero")
    if distance_source != "not_measured" and distance_m <= 0.0:
        errors.append("measured_distance_must_be_positive")
    for field in ("action", "site", "weather", "lighting", "video_ref"):
        if not str(getattr(args, field, "") or "").strip():
            errors.append(f"{field}_required")
    duration_s = safe_float(getattr(args, "duration_s", 0.0), 0.0)
    interval_ms = safe_int(getattr(args, "interval_ms", 0), 0)
    if duration_s <= 0.0:
        errors.append("duration_s_must_be_positive")
    if interval_ms < 50:
        errors.append("interval_ms_must_be_at_least_50")
    min_valid_ratio = safe_float(getattr(args, "min_valid_ratio", -1.0), -1.0)
    if not 0.0 < min_valid_ratio <= 1.0:
        errors.append("min_valid_ratio_out_of_range")
    if safe_int(getattr(args, "max_status_age_ms", -1), -1) < 0:
        errors.append("max_status_age_ms_must_be_non_negative")
    return errors


def record_trial(
    args: argparse.Namespace,
    *,
    fetch_json_fn: Callable[[str, float], dict[str, Any]] = fetch_json,
    monotonic_fn: Callable[[], float] = time.monotonic,
    now_ms_fn: Callable[[], int] = lambda: int(time.time() * 1000),
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    validation_errors = validate_record_args(args)
    if validation_errors:
        print("FIELD_TRIAL,ABORT,reason=INVALID_ARGUMENTS,errors=" + "|".join(validation_errors))
        return 6

    session_id = str(args.session_id)
    target = str(args.target).lower()
    output_dir = resolve_path(Path(args.output_dir))
    session_dir = output_dir / session_id
    if session_dir.exists():
        print(f"FIELD_TRIAL,ABORT,reason=SESSION_ID_EXISTS,session_id={session_id}")
        return 3

    model_evidence = build_model_evidence(
        Path(getattr(args, "model_file", DEFAULT_MODEL_PATH)),
        str(getattr(args, "expected_model_sha256", DEFAULT_MODEL_SHA256)),
    )
    if model_evidence["state"] != "VERIFIED":
        print(
            "FIELD_TRIAL,ABORT,reason=MODEL_NOT_VERIFIED,"
            f"state={model_evidence['state']},actual={model_evidence['actual_sha256']},"
            f"expected={model_evidence['expected_sha256']}"
        )
        return 10

    session_dir.mkdir(parents=True, exist_ok=False)
    report_path = session_dir / "trial_report.json"
    samples_path = session_dir / "samples.jsonl"
    started_ms = int(now_ms_fn())
    metadata = {
        "session_id": session_id,
        "trial_kind": str(getattr(args, "trial_kind", "distance") or "distance"),
        "target": target,
        "distance_m": round(safe_float(args.distance_m), 3),
        "distance_source": str(args.distance_source),
        "action": str(args.action),
        "site": str(args.site),
        "weather": str(args.weather),
        "lighting": str(args.lighting),
        "video_ref": str(args.video_ref),
        "notes": str(getattr(args, "notes", "") or ""),
    }
    running_report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "result": "RUNNING",
        "evidence_complete": False,
        "started_ms": started_ms,
        "ended_ms": 0,
        "metadata": metadata,
        "runtime": {
            "base_url": str(args.base_url).rstrip("/"),
            "duration_s": safe_float(args.duration_s),
            "interval_ms": safe_int(args.interval_ms),
            "max_status_age_ms": safe_int(args.max_status_age_ms),
            "min_valid_ratio": safe_float(args.min_valid_ratio),
            "read_only": True,
            "serial_commands_sent": 0,
        },
        "summary": {},
        "model_evidence": model_evidence,
        "samples_evidence": {"file_path": samples_path.as_posix(), "size_bytes": 0, "sha256": ""},
        "video_evidence": build_video_evidence(str(args.video_ref), getattr(args, "video_file", None)),
    }
    atomic_write_json(report_path, running_report)
    print(
        "FIELD_TRIAL,START,"
        f"session_id={session_id},target={target},distance_m={metadata['distance_m']},"
        f"duration_s={args.duration_s},output={session_dir.as_posix()}"
    )

    base_url = str(args.base_url).rstrip("/")
    interval_s = max(0.05, safe_int(args.interval_ms) / 1000.0)
    expected_sample_count = max(1, int(math.ceil(safe_float(args.duration_s) / interval_s)))
    min_sample_count = max(1, int(math.ceil(expected_sample_count * safe_float(args.min_valid_ratio))))
    samples: list[dict[str, Any]] = []
    observed_model_labels: set[str] = set()
    interrupted = False
    started_monotonic = monotonic_fn()
    deadline = started_monotonic + safe_float(args.duration_s)
    fsync_interval_s = DEFAULT_FSYNC_INTERVAL_S
    last_fsync_monotonic = started_monotonic

    try:
        with samples_path.open("w", encoding="utf-8", newline="\n") as samples_handle:
            try:
                while monotonic_fn() < deadline:
                    host_timestamp_ms = int(now_ms_fn())
                    vision: dict[str, Any] | None = None
                    node: dict[str, Any] | None = None
                    vision_error = ""
                    node_error = ""
                    try:
                        vision = fetch_json_fn(f"{base_url}/api/status", float(args.timeout_s))
                    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
                        vision_error = f"VISION_{type(exc).__name__}"
                    try:
                        node = fetch_json_fn(f"{base_url}/api/node-status", float(args.timeout_s))
                    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
                        node_error = f"NODE_{type(exc).__name__}"

                    sample = build_sample(
                        host_timestamp_ms=host_timestamp_ms,
                        vision=vision,
                        node=node,
                        vision_error=vision_error,
                        node_error=node_error,
                        max_status_age_ms=safe_int(args.max_status_age_ms),
                    )
                    model_label = str(sample.get("detector_model_label", ""))
                    if sample.get("sample_valid") and model_label and model_label != "UNKNOWN":
                        observed_model_labels.add(model_label)
                    samples.append(sample)
                    samples_handle.write(
                        json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n"
                    )
                    samples_handle.flush()
                    now_monotonic = monotonic_fn()
                    if now_monotonic - last_fsync_monotonic >= fsync_interval_s:
                        os.fsync(samples_handle.fileno())
                        last_fsync_monotonic = now_monotonic
                    sleep_fn(interval_s)
            finally:
                samples_handle.flush()
                os.fsync(samples_handle.fileno())
    except KeyboardInterrupt:
        interrupted = True

    actual_elapsed_s = max(0.0, monotonic_fn() - started_monotonic)

    summary = summarize_samples(
        samples,
        target=target,
        expected_model_label=str(args.expected_model_label),
        observed_model_labels=observed_model_labels,
        min_valid_ratio=safe_float(args.min_valid_ratio),
        min_sample_count=min_sample_count,
    )
    video_evidence = build_video_evidence(str(args.video_ref), getattr(args, "video_file", None))
    samples_evidence = {
        "file_path": samples_path.as_posix(),
        "size_bytes": samples_path.stat().st_size if samples_path.exists() else 0,
        "sha256": sha256_file(samples_path) if samples_path.exists() else "",
    }
    evidence_complete = bool(summary["trial_valid"] and video_evidence.get("state") == "VERIFIED")
    result = "PASS" if summary["trial_valid"] else "FAIL"
    if interrupted:
        result = "INTERRUPTED"
        evidence_complete = False
    final_report = {
        **running_report,
        "result": result,
        "evidence_complete": evidence_complete,
        "ended_ms": int(now_ms_fn()),
        "runtime": {
            **running_report["runtime"],
            "actual_elapsed_s": round(actual_elapsed_s, 6),
            "expected_sample_count": expected_sample_count,
            "minimum_sample_count": min_sample_count,
            "fsync_interval_s": fsync_interval_s,
        },
        "summary": summary,
        "samples_evidence": samples_evidence,
        "video_evidence": video_evidence,
    }
    atomic_write_json(report_path, final_report)

    if interrupted:
        return_code = 130
    elif not summary["trial_valid"]:
        return_code = 2
    elif not evidence_complete:
        return_code = 7
    else:
        return_code = 0
    print(
        "FIELD_TRIAL,DONE,"
        f"result={result},evidence_complete={int(evidence_complete)},outcome={summary['outcome']},"
        f"samples={summary['sample_count']},valid={summary['valid_sample_count']},"
        f"max_score={summary['max_drone_score']},return_code={return_code},"
        f"report={report_path.as_posix()}"
    )
    return return_code


def finalize_video(args: argparse.Namespace) -> int:
    session_id = sanitize_token(str(args.finalize_session or ""))
    output_dir = resolve_path(Path(args.output_dir))
    report_path = output_dir / session_id / "trial_report.json"
    video_file = getattr(args, "video_file", None)
    if not report_path.is_file() or video_file is None:
        print("FIELD_TRIAL,FINALIZE_ABORT,reason=REPORT_OR_VIDEO_MISSING")
        return 8
    try:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        print("FIELD_TRIAL,FINALIZE_ABORT,reason=REPORT_READ_ERROR")
        return 8
    video_evidence = build_video_evidence(
        str(report.get("metadata", {}).get("video_ref", "")),
        Path(video_file),
    )
    if video_evidence.get("state") != "VERIFIED":
        print(f"FIELD_TRIAL,FINALIZE_ABORT,reason=VIDEO_{video_evidence.get('state', 'INVALID')}")
        return 9
    trial_valid = bool(report.get("summary", {}).get("trial_valid"))
    report["video_evidence"] = video_evidence
    report["evidence_complete"] = trial_valid
    report["video_finalized_ms"] = int(time.time() * 1000)
    atomic_write_json(report_path, report)
    print(
        "FIELD_TRIAL,FINALIZE_DONE,"
        f"session_id={session_id},evidence_complete={int(trial_valid)},report={report_path.as_posix()}"
    )
    return 0 if trial_valid else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only 10/30/50 m field trial recorder for V4b and NodeA evidence."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-s", type=float, default=2.0)
    parser.add_argument("--duration-s", type=float, default=12.0)
    parser.add_argument("--interval-ms", type=int, default=200)
    parser.add_argument("--max-status-age-ms", type=int, default=3000)
    parser.add_argument("--min-valid-ratio", type=float, default=0.80)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--trial-kind", choices=sorted(TRIAL_KINDS), default="distance")
    parser.add_argument("--target", choices=sorted(TARGETS), default="")
    parser.add_argument("--distance-m", type=float, default=-1.0)
    parser.add_argument("--distance-source", choices=sorted(DISTANCE_SOURCES), default="")
    parser.add_argument("--action", default="")
    parser.add_argument("--site", default="")
    parser.add_argument("--weather", default="")
    parser.add_argument("--lighting", default="")
    parser.add_argument("--video-ref", default="")
    parser.add_argument("--video-file", type=Path)
    parser.add_argument("--notes", default="")
    parser.add_argument("--model-file", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--expected-model-sha256", default=DEFAULT_MODEL_SHA256)
    parser.add_argument("--expected-model-label", default=DEFAULT_MODEL_LABEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--finalize-session", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.finalize_session:
        return finalize_video(args)
    return record_trial(args)


if __name__ == "__main__":
    raise SystemExit(main())
