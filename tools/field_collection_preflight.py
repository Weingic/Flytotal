from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import field_trial_recorder
import single_node_evidence_closure_check_单节点证据闭环核对 as closure


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_MODEL_PATH = field_trial_recorder.DEFAULT_MODEL_PATH
DEFAULT_MODEL_SHA256 = field_trial_recorder.DEFAULT_MODEL_SHA256
DEFAULT_MODEL_LABEL = field_trial_recorder.DEFAULT_MODEL_LABEL
DEFAULT_OUTPUT_DIR = field_trial_recorder.DEFAULT_OUTPUT_DIR
DEFAULT_REPORT_FILE = PROJECT_ROOT / "captures" / "latest_field_collection_preflight_report.json"
MIN_REAL_EPOCH_MS = 946_684_800_000
MIN_NODE_STABLE_UPTIME_MS = 15_000


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


def payload_age_ms(payload: dict[str, Any], now_ms: int, *, timestamp_key: str) -> int:
    timestamp_ms = safe_int(payload.get(timestamp_key, 0), 0)
    if timestamp_ms >= MIN_REAL_EPOCH_MS:
        return max(0, now_ms - timestamp_ms)
    return max(0, safe_int(payload.get("stale_age_ms", now_ms), now_ms))


def output_writable(path: Path) -> tuple[bool, str]:
    probe_path = path / f".field_preflight_write_probe_{os.getpid()}.tmp"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_path.write_bytes(b"field-preflight")
        probe_path.unlink()
        return True, "OK"
    except OSError as exc:
        try:
            probe_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False, f"{type(exc).__name__}:{exc}"


def evaluate_preflight(
    vision: dict[str, Any],
    node: dict[str, Any],
    *,
    model_path: Path,
    expected_model_sha256: str,
    expected_model_label: str,
    output_dir: Path,
    now_ms: int,
    max_status_age_ms: int,
    min_free_bytes: int,
    disk_free_bytes: int | None = None,
    require_cloud_test: bool,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    model_path = resolve_path(model_path)
    output_dir = resolve_path(output_dir)
    vision_age_ms = payload_age_ms(vision, now_ms, timestamp_key="timestamp_ms")
    node_age_ms = payload_age_ms(node, now_ms, timestamp_key="last_update_ms")

    vision_available = bool(safe_int(vision.get("available", vision.get("ok", 0)), 0))
    add_check("vision_api_available", vision_available, {"available": int(vision_available)})
    vision_fresh = bool(
        vision_available
        and safe_int(vision.get("source_ready", 0), 0)
        and safe_int(vision.get("vision_chain_ready", 0), 0)
        and vision_age_ms <= max_status_age_ms
    )
    add_check(
        "vision_runtime_fresh",
        vision_fresh,
        {
            "age_ms": vision_age_ms,
            "max_age_ms": max_status_age_ms,
            "source_ready": safe_int(vision.get("source_ready", 0), 0),
            "vision_chain_ready": safe_int(vision.get("vision_chain_ready", 0), 0),
        },
    )
    physical_camera_source = field_trial_recorder.is_physical_camera_source(vision.get("source", ""))
    add_check(
        "physical_camera_source",
        physical_camera_source,
        {
            "source": str(vision.get("source", "")),
            "capture_backend": str(vision.get("capture_backend", "UNKNOWN")),
        },
    )
    frame_ready = bool(
        safe_int(vision.get("frame_content_ready", 0), 0)
        and str(vision.get("frame_quality_reason", "")) == "OK"
    )
    add_check(
        "vision_frame_quality",
        frame_ready,
        {
            "frame_content_ready": safe_int(vision.get("frame_content_ready", 0), 0),
            "reason": str(vision.get("frame_quality_reason", "UNKNOWN")),
        },
    )
    deployed_detector = bool(
        safe_int(vision.get("detector_ready", 0), 0)
        and str(vision.get("detector_model_label", "")) == expected_model_label
        and str(vision.get("detector_class_strategy", "")) == "0:drone"
    )
    add_check(
        "deployed_detector",
        deployed_detector,
        {
            "detector_ready": safe_int(vision.get("detector_ready", 0), 0),
            "model_label": str(vision.get("detector_model_label", "UNKNOWN")),
            "expected_model_label": expected_model_label,
            "class_strategy": str(vision.get("detector_class_strategy", "UNKNOWN")),
        },
    )

    actual_model_sha256 = ""
    model_hash_error = ""
    try:
        actual_model_sha256 = sha256_file(model_path)
    except OSError as exc:
        model_hash_error = f"{type(exc).__name__}:{exc}"
    model_hash_ok = bool(
        actual_model_sha256
        and actual_model_sha256.lower() == str(expected_model_sha256).lower()
    )
    add_check(
        "deployed_model_hash",
        model_hash_ok,
        {
            "path": model_path.as_posix(),
            "actual_sha256": actual_model_sha256,
            "expected_sha256": str(expected_model_sha256).lower(),
            "error": model_hash_error,
        },
    )

    node_boot_id = str(node.get("boot_id", "") or "").strip()
    node_reset_reason = str(node.get("reset_reason", "") or "").strip().upper()
    node_uptime_ms = safe_int(node.get("node_uptime_ms", 0), 0)
    node_boot_last_change_ms = safe_int(node.get("node_boot_last_change_ms", 0), 0)
    node_boot_change_age_ms = (
        max(0, now_ms - node_boot_last_change_ms)
        if node_boot_last_change_ms >= MIN_REAL_EPOCH_MS
        else 0
    )
    node_boot_ready = bool(
        node_boot_id not in {"", "UNKNOWN", "NONE"}
        and node_reset_reason not in {"", "UNKNOWN", "NONE"}
        and node_uptime_ms >= MIN_NODE_STABLE_UPTIME_MS
        and node_boot_change_age_ms >= MIN_NODE_STABLE_UPTIME_MS
    )
    node_online = bool(
        safe_int(node.get("available", node.get("ok", 0)), 0)
        and safe_int(node.get("online", 0), 0)
        and node_age_ms <= max_status_age_ms
        and node_boot_ready
    )
    add_check(
        "node_online_fresh",
        node_online,
        {
            "online": safe_int(node.get("online", 0), 0),
            "age_ms": node_age_ms,
            "max_age_ms": max_status_age_ms,
            "boot_id": node_boot_id,
            "reset_reason": node_reset_reason,
            "node_uptime_ms": node_uptime_ms,
            "minimum_stable_uptime_ms": MIN_NODE_STABLE_UPTIME_MS,
            "node_boot_change_count": safe_int(node.get("node_boot_change_count", 0), 0),
            "node_boot_change_age_ms": node_boot_change_age_ms,
        },
    )
    add_check(
        "track_idle",
        safe_int(node.get("track_active", 0), 0) == 0,
        {"track_active": safe_int(node.get("track_active", 0), 0)},
    )
    event_idle = bool(
        safe_int(node.get("event_active", 0), 0) == 0
        and str(node.get("event_id", "NONE")) == "NONE"
    )
    add_check(
        "event_idle",
        event_idle,
        {
            "event_active": safe_int(node.get("event_active", 0), 0),
            "event_id": str(node.get("event_id", "NONE")),
        },
    )
    add_check(
        "test_mode_disabled",
        safe_int(node.get("test_mode_enabled", 0), 0) == 0,
        {"test_mode_enabled": safe_int(node.get("test_mode_enabled", 0), 0)},
    )
    add_check(
        "advanced_fusion_enabled",
        safe_int(node.get("fusion_enabled", 0), 0) == 1,
        {
            "fusion_enabled": safe_int(node.get("fusion_enabled", 0), 0),
            "fusion_level": str(node.get("fusion_level", "NONE")),
            "fusion_stage": str(node.get("fusion_stage", "NONE")),
        },
    )
    add_check(
        "servo_disabled",
        safe_int(node.get("servo_enabled", 0), 0) == 0,
        {"servo_enabled": safe_int(node.get("servo_enabled", 0), 0)},
    )
    add_check(
        "cloud_request_idle",
        safe_int(node.get("cloud_request_in_flight", 0), 0) == 0,
        {"cloud_request_in_flight": safe_int(node.get("cloud_request_in_flight", 0), 0)},
    )
    serial_contract = safe_int(node.get("serial_bridge_contract_version", 0), 0)
    web_contract = safe_int(node.get("web_evidence_contract_version", 0), 0)
    add_check(
        "contracts_v2",
        serial_contract >= 2 and web_contract >= 2,
        {"serial_bridge": serial_contract, "web_evidence": web_contract},
    )

    writable, write_detail = output_writable(output_dir)
    add_check("output_writable", writable, {"path": output_dir.as_posix(), "detail": write_detail})
    free_bytes = disk_free_bytes
    if free_bytes is None:
        try:
            free_bytes = shutil.disk_usage(output_dir).free
        except OSError:
            free_bytes = 0
    add_check(
        "disk_free",
        int(free_bytes) >= int(min_free_bytes),
        {"free_bytes": int(free_bytes), "minimum_bytes": int(min_free_bytes)},
    )
    recorder_path = Path(field_trial_recorder.__file__).resolve()
    add_check(
        "field_recorder_available",
        recorder_path.is_file(),
        {"path": recorder_path.as_posix()},
    )

    if require_cloud_test:
        cloud_report = closure.evaluate_cloud_preflight_status(node, "test")
        add_check(
            "cloud_test_32_of_32",
            cloud_report.get("result") == "PASS",
            {
                "result": cloud_report.get("result", "FAIL"),
                "passed_count": cloud_report.get("passed_count", 0),
                "total_count": cloud_report.get("total_count", 0),
                "failures": cloud_report.get("failures", []),
            },
        )

    passed_count = sum(bool(item["passed"]) for item in checks)
    failures = [str(item["name"]) for item in checks if not item["passed"]]
    return {
        "schema_version": "field_collection_preflight_v2",
        "result": "GO" if passed_count == len(checks) else "NO-GO",
        "passed_count": passed_count,
        "total_count": len(checks),
        "failures": failures,
        "checks": checks,
        "read_only": True,
        "serial_commands_sent": 0,
        "cloud_api_calls_sent": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only GO/NO-GO gate before real-drone field collection."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-s", type=float, default=3.0)
    parser.add_argument("--mode", choices=("distance", "same-event"), default="distance")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--model-sha256", default=DEFAULT_MODEL_SHA256)
    parser.add_argument("--model-label", default=DEFAULT_MODEL_LABEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-status-age-ms", type=int, default=3000)
    parser.add_argument("--min-free-gb", type=float, default=2.0)
    parser.add_argument("--report-file", type=Path, default=DEFAULT_REPORT_FILE)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    now_ms = int(time.time() * 1000)
    base_url = str(args.base_url).rstrip("/")
    api_errors: list[str] = []
    try:
        vision = fetch_json(f"{base_url}/api/status", args.timeout_s)
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        vision = {}
        api_errors.append(f"vision:{type(exc).__name__}")
    try:
        node = fetch_json(f"{base_url}/api/node-status", args.timeout_s)
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        node = {}
        api_errors.append(f"node:{type(exc).__name__}")

    report = evaluate_preflight(
        vision,
        node,
        model_path=args.model,
        expected_model_sha256=args.model_sha256,
        expected_model_label=args.model_label,
        output_dir=args.output_dir,
        now_ms=now_ms,
        max_status_age_ms=max(0, int(args.max_status_age_ms)),
        min_free_bytes=max(0, int(float(args.min_free_gb) * 1024 * 1024 * 1024)),
        require_cloud_test=args.mode == "same-event",
    )
    report.update(
        {
            "generated_ms": int(time.time() * 1000),
            "mode": args.mode,
            "base_url": base_url,
            "api_errors": api_errors,
        }
    )
    report_file = resolve_path(args.report_file)
    atomic_write_json(report_file, report)
    print("Field Collection Preflight")
    print(f"result={report['result']}")
    print(f"checks={report['passed_count']}/{report['total_count']}")
    for failure in report["failures"]:
        print(f"- {failure}")
    print(f"report_file={report_file.as_posix()}")
    return 0 if report["result"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
