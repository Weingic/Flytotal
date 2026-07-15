# ????? USB ????????????????????????????????????????
import argparse
import json
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_TRACKERS = ("csrt", "kcf", "mil")
SUPPORTED_CAPTURE_BACKENDS = ("auto", "msmf", "dshow")
DEFAULT_FRAME_MIN_MEAN_LUMA = 5.0
DEFAULT_FRAME_MAX_MEAN_LUMA = 250.0
DEFAULT_FRAME_MIN_LUMA_STDDEV = 2.0
DEFAULT_DRONE_MODEL = PROJECT_ROOT / "models" / "yolov8n_drone.onnx"


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def tracker_available(cv: Any, tracker_name: str) -> bool:
    tracker_name = tracker_name.lower().strip()
    if tracker_name == "csrt":
        return hasattr(cv, "TrackerCSRT_create") or (hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerCSRT_create"))
    if tracker_name == "kcf":
        return hasattr(cv, "TrackerKCF_create") or (hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerKCF_create"))
    if tracker_name == "mil":
        return hasattr(cv, "TrackerMIL_create") or (hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerMIL_create"))
    return False


def list_available_trackers(cv: Any) -> list[str]:
    return [name for name in SUPPORTED_TRACKERS if tracker_available(cv, name)]


def evaluate_frame_quality(
    cv: Any,
    frame: Any,
    min_mean_luma: float = DEFAULT_FRAME_MIN_MEAN_LUMA,
    max_mean_luma: float = DEFAULT_FRAME_MAX_MEAN_LUMA,
    min_luma_stddev: float = DEFAULT_FRAME_MIN_LUMA_STDDEV,
) -> dict[str, Any]:
    if frame is None:
        return {"ready": False, "mean_luma": 0.0, "luma_stddev": 0.0, "reason": "FRAME_MISSING"}
    try:
        gray = frame if len(frame.shape) == 2 else cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        mean_value, stddev_value = cv.meanStdDev(gray)
        mean_luma = float(mean_value[0][0])
        luma_stddev = float(stddev_value[0][0])
    except Exception:
        return {"ready": False, "mean_luma": 0.0, "luma_stddev": 0.0, "reason": "FRAME_INVALID"}

    if mean_luma < max(0.0, float(min_mean_luma)):
        reason = "FRAME_TOO_DARK"
    elif mean_luma > min(255.0, float(max_mean_luma)):
        reason = "FRAME_TOO_BRIGHT"
    elif luma_stddev < max(0.0, float(min_luma_stddev)):
        reason = "FRAME_TOO_FLAT"
    else:
        reason = "OK"
    return {
        "ready": reason == "OK",
        "mean_luma": round(mean_luma, 3),
        "luma_stddev": round(luma_stddev, 3),
        "reason": reason,
    }


def resolve_capture_backend(cv: Any, backend: str) -> tuple[int, str]:
    backend_name = str(backend or "auto").strip().lower()
    if backend_name == "msmf":
        value = getattr(cv, "CAP_MSMF", None)
        if isinstance(value, int):
            return value, "msmf"
        return int(getattr(cv, "CAP_ANY", 0) or 0), "auto"
    if backend_name == "dshow":
        value = getattr(cv, "CAP_DSHOW", None)
        if isinstance(value, int):
            return value, "dshow"
        return int(getattr(cv, "CAP_ANY", 0) or 0), "auto"
    return int(getattr(cv, "CAP_ANY", 0) or 0), "auto"


def build_backend_candidates(preferred_backend: str, fallback_mode: str) -> list[str]:
    preferred = str(preferred_backend or "auto").strip().lower()
    if preferred not in SUPPORTED_CAPTURE_BACKENDS:
        preferred = "auto"
    if str(fallback_mode or "auto").strip().lower() != "auto":
        return [preferred]
    ordered = [preferred]
    for backend in SUPPORTED_CAPTURE_BACKENDS:
        if backend not in ordered:
            ordered.append(backend)
    return ordered


def probe_camera(
    cv: Any,
    index: int,
    width: int,
    height: int,
    warmup_frames: int,
    backend: str,
    min_mean_luma: float,
    max_mean_luma: float,
    min_luma_stddev: float,
) -> dict[str, Any]:
    api_preference, active_backend = resolve_capture_backend(cv, backend)
    try:
        cap = cv.VideoCapture(index, api_preference)
    except TypeError:
        cap = cv.VideoCapture(index)
        active_backend = "auto"
    record: dict[str, Any] = {
        "source_index": index,
        "backend_requested": str(backend or "auto").lower(),
        "backend_active": active_backend,
        "opened": False,
        "frame_ready": False,
        "frame_width": 0,
        "frame_height": 0,
        "fps": 0.0,
        "read_success_count": 0,
        "read_attempt_count": 0,
        "content_ready_count": 0,
        "frame_content_ready": False,
        "frame_mean_luma": 0.0,
        "frame_luma_stddev": 0.0,
        "frame_quality_reason": "FRAME_MISSING",
    }
    if not cap.isOpened():
        cap.release()
        return record

    record["opened"] = True
    if width > 0:
        cap.set(cv.CAP_PROP_FRAME_WIDTH, width)
    if height > 0:
        cap.set(cv.CAP_PROP_FRAME_HEIGHT, height)

    attempts = max(1, warmup_frames + 1)
    success_count = 0
    content_ready_count = 0
    last_shape = (0, 0)
    selected_quality: dict[str, Any] = {
        "ready": False,
        "mean_luma": 0.0,
        "luma_stddev": 0.0,
        "reason": "FRAME_MISSING",
    }
    for _ in range(attempts):
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        success_count += 1
        try:
            last_shape = (int(frame.shape[1]), int(frame.shape[0]))
        except Exception:
            last_shape = (0, 0)
        quality = evaluate_frame_quality(
            cv,
            frame,
            min_mean_luma=min_mean_luma,
            max_mean_luma=max_mean_luma,
            min_luma_stddev=min_luma_stddev,
        )
        if bool(quality.get("ready")):
            content_ready_count += 1
            selected_quality = quality
        elif not bool(selected_quality.get("ready")):
            selected_quality = quality

    fps_value = float(cap.get(cv.CAP_PROP_FPS) or 0.0)
    cap.release()

    record["read_attempt_count"] = attempts
    record["read_success_count"] = success_count
    record["frame_ready"] = content_ready_count > 0
    record["frame_width"] = last_shape[0]
    record["frame_height"] = last_shape[1]
    record["fps"] = round(fps_value, 3)
    record["content_ready_count"] = content_ready_count
    record["frame_content_ready"] = bool(selected_quality.get("ready"))
    record["frame_mean_luma"] = float(selected_quality.get("mean_luma", 0.0) or 0.0)
    record["frame_luma_stddev"] = float(selected_quality.get("luma_stddev", 0.0) or 0.0)
    record["frame_quality_reason"] = str(selected_quality.get("reason", "FRAME_MISSING"))
    return record


def build_report(
    report_file: Path,
    camera_records: list[dict[str, Any]],
    trackers_available: list[str],
    probe_backends: list[str],
    requested_index_range: tuple[int, int],
    recommended_tracker_fallback: str,
    recommended_source_warmup_frames: int,
    drone_model_path: Path,
    drone_model_ready: bool,
    failures: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    checked_ms = int(time.time() * 1000)
    ready_records = [item for item in camera_records if bool(item.get("frame_ready"))]
    opened_records = [item for item in camera_records if bool(item.get("opened"))]
    recommended_source = int(ready_records[0]["source_index"]) if ready_records else -1
    recommended_backend = str(ready_records[0].get("backend_active", "auto") or "auto") if ready_records else str(probe_backends[0] if probe_backends else "auto")
    recommended_tracker = next((name for name in SUPPORTED_TRACKERS if name in trackers_available), "")
    recommended_command = ""
    if recommended_source >= 0 and recommended_tracker:
        try:
            model_command_path = drone_model_path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            model_command_path = drone_model_path.as_posix()
        yolo_args = ""
        if drone_model_ready:
            yolo_args = (
                f" --yolo-enabled --yolo-model {model_command_path}"
                " --yolo-class-ids 0 --yolo-class-names 0:drone"
                " --yolo-model-label drone-v4b-hardneg-deployed"
                " --yolo-score-threshold 0.45 --yolo-intra-op-threads 8 --yolo-auto-lock"
            )
        recommended_command = (
            "python tools/vision_bridge_视觉桥接.py "
            f"--backend {recommended_backend} "
            f"--source {recommended_source} --tracker {recommended_tracker} "
            f"--tracker-fallback {recommended_tracker_fallback} "
            f"--source-warmup-frames {max(1, int(recommended_source_warmup_frames))}"
            f"{yolo_args}"
        )
    recommended_web_server_command = "python tools/vision_web_server_视觉网页服务.py"

    return {
        "checked_ms": checked_ms,
        "result": "PASS" if not failures else "FAIL",
        "report_file": report_file.as_posix(),
        "opencv_version": "",
        "probe": {
            "start_index": requested_index_range[0],
            "end_index": requested_index_range[1],
            "probe_count": len(camera_records),
            "opened_count": len(opened_records),
            "ready_count": len(ready_records),
        },
        "trackers": {
            "supported": list(SUPPORTED_TRACKERS),
            "available": trackers_available,
        },
        "detector": {
            "drone_model_path": drone_model_path.as_posix(),
            "drone_model_ready": bool(drone_model_ready),
            "auto_lock_recommended": bool(drone_model_ready),
        },
        "capture_backends": {
            "supported": list(SUPPORTED_CAPTURE_BACKENDS),
            "probe_backends": probe_backends,
        },
        "recommended": {
            "source_index": recommended_source,
            "backend": recommended_backend,
            "tracker": recommended_tracker,
            "tracker_fallback": recommended_tracker_fallback,
            "source_warmup_frames": max(1, int(recommended_source_warmup_frames)),
            "vision_bridge_command": recommended_command,
            "vision_web_server_command": recommended_web_server_command,
        },
        "camera_records": camera_records,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="USB camera readiness check for 4.11 minimal vision-chain onboarding."
    )
    parser.add_argument("--start-index", type=int, default=0, help="First camera index to probe")
    parser.add_argument("--end-index", type=int, default=4, help="Last camera index to probe (inclusive)")
    parser.add_argument("--width", type=int, default=1280, help="Requested camera width during probe")
    parser.add_argument("--height", type=int, default=720, help="Requested camera height during probe")
    parser.add_argument("--warmup-frames", type=int, default=6, help="Frames to read before readiness decision")
    parser.add_argument("--frame-min-mean-luma", type=float, default=DEFAULT_FRAME_MIN_MEAN_LUMA, help="Reject camera frames darker than this mean luma")
    parser.add_argument("--frame-max-mean-luma", type=float, default=DEFAULT_FRAME_MAX_MEAN_LUMA, help="Reject camera frames brighter than this mean luma")
    parser.add_argument("--frame-min-luma-stddev", type=float, default=DEFAULT_FRAME_MIN_LUMA_STDDEV, help="Reject camera frames with less visual variation than this luma standard deviation")
    parser.add_argument("--backend", choices=list(SUPPORTED_CAPTURE_BACKENDS), default="auto", help="Preferred OpenCV capture backend")
    parser.add_argument("--backend-fallback", choices=["auto", "off"], default="auto", help="When probe fails on preferred backend, auto-try other backends or not")
    parser.add_argument("--require-csrt", action="store_true", help="Fail when CSRT tracker is unavailable")
    parser.add_argument("--recommended-tracker-fallback", choices=["auto", "off"], default="auto", help="Tracker fallback mode used in recommended vision_bridge command")
    parser.add_argument("--recommended-source-warmup-frames", type=int, default=12, help="Source warmup frames used in recommended vision_bridge command")
    parser.add_argument("--allow-no-camera", action="store_true", help="Do not fail when no camera source is ready")
    parser.add_argument("--drone-model", type=Path, default=DEFAULT_DRONE_MODEL, help="Drone-specific ONNX model used in the recommended automatic-lock command")
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("captures/latest_usb_camera_readiness_report.json"),
        help="Output JSON report path",
    )
    args = parser.parse_args()

    report_file = resolve_path(args.report_file)
    drone_model_path = resolve_path(args.drone_model)
    drone_model_ready = drone_model_path.is_file() and drone_model_path.stat().st_size > 0
    failures: list[str] = []
    warnings: list[str] = []
    camera_records: list[dict[str, Any]] = []
    trackers_available: list[str] = []
    probe_backends = build_backend_candidates(args.backend, args.backend_fallback)
    opencv_version = ""

    try:
        import cv2 as cv
    except ImportError:
        failures.append("opencv_not_installed")
        report = build_report(
            report_file=report_file,
            camera_records=[],
            trackers_available=[],
            probe_backends=probe_backends,
            requested_index_range=(args.start_index, args.end_index),
            recommended_tracker_fallback=args.recommended_tracker_fallback,
            recommended_source_warmup_frames=args.recommended_source_warmup_frames,
            drone_model_path=drone_model_path,
            drone_model_ready=drone_model_ready,
            failures=failures,
            warnings=warnings,
        )
        write_json(report_file, report)
        print("USB Camera Readiness Report")
        print(f"result={report['result']}")
        print("camera_ready_count=0")
        print("trackers_available=NONE")
        print(f"failure_count={report['failure_count']}")
        print(f"warning_count={report['warning_count']}")
        print(f"report_file={report_file.as_posix()}")
        for item in failures:
            print(f"- {item}")
        return 1

    opencv_version = str(getattr(cv, "__version__", "") or "")
    trackers_available = list_available_trackers(cv)
    start_index = min(args.start_index, args.end_index)
    end_index = max(args.start_index, args.end_index)

    for source_index in range(start_index, end_index + 1):
        selected_record: dict[str, Any] | None = None
        attempt_records: list[dict[str, Any]] = []
        for backend_name in probe_backends:
            record = probe_camera(
                cv=cv,
                index=source_index,
                width=max(0, args.width),
                height=max(0, args.height),
                warmup_frames=max(0, args.warmup_frames),
                backend=backend_name,
                min_mean_luma=args.frame_min_mean_luma,
                max_mean_luma=args.frame_max_mean_luma,
                min_luma_stddev=args.frame_min_luma_stddev,
            )
            attempt_records.append(record)
            if bool(record.get("frame_ready")):
                selected_record = record
                break
        if selected_record is None:
            selected_record = attempt_records[0] if attempt_records else {"source_index": source_index, "opened": False, "frame_ready": False}
        selected_record = dict(selected_record)
        selected_record["backend_attempts"] = [str(item.get("backend_active", "auto")) for item in attempt_records]
        camera_records.append(selected_record)

    ready_count = sum(1 for item in camera_records if bool(item.get("frame_ready")))

    if ready_count <= 0 and not args.allow_no_camera:
        failures.append("camera_ready_unavailable")
    elif ready_count <= 0 and args.allow_no_camera:
        warnings.append("camera_ready_unavailable_allowed")

    if not trackers_available:
        failures.append("tracker_unavailable_all")
    elif args.require_csrt and "csrt" not in trackers_available:
        failures.append("tracker_csrt_required_but_unavailable")
    elif "csrt" not in trackers_available:
        warnings.append("tracker_csrt_unavailable_using_tracker_fallback")
    if not drone_model_ready:
        warnings.append("drone_yolo_model_unavailable_manual_lock_only")

    report = build_report(
        report_file=report_file,
        camera_records=camera_records,
        trackers_available=trackers_available,
        probe_backends=probe_backends,
        requested_index_range=(start_index, end_index),
        recommended_tracker_fallback=args.recommended_tracker_fallback,
        recommended_source_warmup_frames=args.recommended_source_warmup_frames,
        drone_model_path=drone_model_path,
        drone_model_ready=drone_model_ready,
        failures=failures,
        warnings=warnings,
    )
    report["opencv_version"] = opencv_version
    write_json(report_file, report)

    recommended = report.get("recommended", {}) if isinstance(report.get("recommended"), dict) else {}
    tracker_text = "/".join(trackers_available).upper() if trackers_available else "NONE"
    print("USB Camera Readiness Report")
    print(f"result={report['result']}")
    print(f"camera_probe_count={report['probe']['probe_count']}")
    print(f"camera_ready_count={report['probe']['ready_count']}")
    print(f"trackers_available={tracker_text}")
    print(f"failure_count={report['failure_count']}")
    print(f"warning_count={report['warning_count']}")
    print(f"recommended_source={recommended.get('source_index', -1)}")
    print(f"recommended_backend={recommended.get('backend', 'auto')}")
    print(f"recommended_tracker={recommended.get('tracker', 'NONE') or 'NONE'}")
    print(f"recommended_tracker_fallback={recommended.get('tracker_fallback', 'auto')}")
    print(f"recommended_source_warmup_frames={recommended.get('source_warmup_frames', 12)}")
    print(f"drone_model_ready={int(drone_model_ready)}")
    print(f"drone_model={drone_model_path.as_posix()}")
    print(f"recommended_command={recommended.get('vision_bridge_command', '')}")
    print(f"recommended_web_server_command={recommended.get('vision_web_server_command', '')}")
    print(f"report_file={report_file.as_posix()}")

    for item in failures:
        print(f"- {item}")
    for item in warnings:
        print(f"- {item}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
