# ?????????????????????????????????????????????????
import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from session_log_utils_会话日志工具 import append_session_event
from session_log_utils_会话日志工具 import load_json_payload
from session_log_utils_会话日志工具 import resolve_path

try:
    import cv2
except ImportError:  # pragma: no cover - handled at runtime on the user's machine
    cv2 = None  # type: ignore[assignment]


VISION_IDLE = "VISION_IDLE"
VISION_SEARCHING = "VISION_SEARCHING"
VISION_LOCKED = "VISION_LOCKED"
VISION_LOST = "VISION_LOST"

WINDOW_NAME = "Flytotal Vision Bridge"
CAPTURE_HINT_COOLDOWN_S = 1.2
SUPPORTED_TRACKERS = ("csrt", "kcf")
SUPPORTED_CAPTURE_BACKENDS = ("auto", "msmf", "dshow")
ACTIVE_EVENT_MAX_AGE_MS_DEFAULT = 15000


@dataclass
class VisionSnapshot:
    # 单帧视觉状态快照。
    timestamp_ms: int
    frame_index: int
    vision_state: str
    vision_locked: bool
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    center_x: int
    center_y: int
    tracker_name: str


@dataclass
class CaptureRecord:
    # 单次抓拍记录。
    timestamp_ms: int
    frame_index: int
    vision_state: str
    vision_locked: bool
    tracker_name: str
    event_id: str
    file_path: str
    capture_reason: str
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    center_x: int
    center_y: int


class CsvVisionLogger:
    # 记录连续运行中的状态快照。
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)
        self.writer.writerow(
            [
                "timestamp_ms",
                "frame_index",
                "vision_state",
                "vision_locked",
                "bbox_x",
                "bbox_y",
                "bbox_w",
                "bbox_h",
                "center_x",
                "center_y",
                "tracker_name",
            ]
        )

    def write(self, snapshot: VisionSnapshot) -> None:
        self.writer.writerow(
            [
                snapshot.timestamp_ms,
                snapshot.frame_index,
                snapshot.vision_state,
                int(snapshot.vision_locked),
                snapshot.bbox_x,
                snapshot.bbox_y,
                snapshot.bbox_w,
                snapshot.bbox_h,
                snapshot.center_x,
                snapshot.center_y,
                snapshot.tracker_name,
            ]
        )
        self.file.flush()

    def close(self) -> None:
        self.file.close()


class CaptureMetadataLogger:
    # 记录每次抓拍的元数据。
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_has_content = self.path.exists() and self.path.stat().st_size > 0
        self.file = self.path.open("a", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)
        if not file_has_content:
            self.writer.writerow(
                [
                    "timestamp_ms",
                    "frame_index",
                    "vision_state",
                    "vision_locked",
                    "tracker_name",
                    "event_id",
                    "capture_reason",
                    "file_path",
                    "bbox_x",
                    "bbox_y",
                    "bbox_w",
                    "bbox_h",
                    "center_x",
                    "center_y",
                ]
            )

    def write(self, record: CaptureRecord) -> None:
        self.writer.writerow(
            [
                record.timestamp_ms,
                record.frame_index,
                record.vision_state,
                int(record.vision_locked),
                record.tracker_name,
                record.event_id,
                record.capture_reason,
                record.file_path,
                record.bbox_x,
                record.bbox_y,
                record.bbox_w,
                record.bbox_h,
                record.center_x,
                record.center_y,
            ]
        )
        self.file.flush()

    def close(self) -> None:
        self.file.close()


def require_opencv() -> Any:
    if cv2 is None:
        print(
            "OpenCV is not installed. Run `pip install opencv-python` first.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return cv2


def tracker_available(cv: Any, tracker_name: str) -> bool:
    tracker_name = tracker_name.lower().strip()
    if tracker_name == "csrt":
        return hasattr(cv, "TrackerCSRT_create") or (hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerCSRT_create"))
    if tracker_name == "kcf":
        return hasattr(cv, "TrackerKCF_create") or (hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerKCF_create"))
    return False


def list_available_trackers(cv: Any) -> list[str]:
    return [name for name in SUPPORTED_TRACKERS if tracker_available(cv, name)]


def resolve_tracker_selection(cv: Any, requested_tracker: str, fallback_mode: str) -> tuple[str, bool, list[str]]:
    requested = requested_tracker.lower().strip()
    available = list_available_trackers(cv)
    if requested in available:
        return requested, False, available

    if fallback_mode == "auto":
        for candidate in SUPPORTED_TRACKERS:
            if candidate in available:
                return candidate, True, available

    available_text = ", ".join(name.upper() for name in available) if available else "NONE"
    raise RuntimeError(
        f"Tracker `{requested}` is not available in this OpenCV build. "
        f"Available trackers: {available_text}. "
        "Try another tracker or install opencv-contrib-python."
    )


def create_tracker(cv: Any, tracker_name: str) -> Any:
    tracker_name = tracker_name.lower()
    if tracker_name == "csrt":
        if hasattr(cv, "TrackerCSRT_create"):
            return cv.TrackerCSRT_create()
        if hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerCSRT_create"):
            return cv.legacy.TrackerCSRT_create()
    if tracker_name == "kcf":
        if hasattr(cv, "TrackerKCF_create"):
            return cv.TrackerKCF_create()
        if hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerKCF_create"):
            return cv.legacy.TrackerKCF_create()

    raise RuntimeError(
        f"Tracker `{tracker_name}` is not available in this OpenCV build. "
        "Try another tracker or install opencv-contrib-python."
    )


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


def open_source(cv: Any, source: str, width: int, height: int, backend: str) -> tuple[Any, str]:
    capture_source: Any
    if source.isdigit():
        capture_source = int(source)
    else:
        capture_source = source

    api_preference, active_backend = resolve_capture_backend(cv, backend)
    try:
        cap = cv.VideoCapture(capture_source, api_preference)
    except TypeError:
        cap = cv.VideoCapture(capture_source)
        active_backend = "auto"
    if width > 0:
        cap.set(cv.CAP_PROP_FRAME_WIDTH, width)
    if height > 0:
        cap.set(cv.CAP_PROP_FRAME_HEIGHT, height)
    return cap, active_backend


def capture_backend_candidates(requested_backend: str, fallback_mode: str) -> list[str]:
    requested = str(requested_backend or "auto").strip().lower()
    if requested not in SUPPORTED_CAPTURE_BACKENDS:
        requested = "auto"
    if str(fallback_mode or "auto").strip().lower() != "auto":
        return [requested]

    ordered: list[str] = [requested]
    for backend in SUPPORTED_CAPTURE_BACKENDS:
        if backend not in ordered:
            ordered.append(backend)
    return ordered


def warmup_source_frame(cap: Any, warmup_frames: int) -> tuple[bool, Any | None, int]:
    attempts = max(1, int(warmup_frames))
    for attempt in range(1, attempts + 1):
        ok, frame = cap.read()
        if ok and frame is not None:
            return True, frame, attempt
    return False, None, attempts


def normalize_bbox(bbox: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    x, y, w, h = bbox
    return int(x), int(y), int(w), int(h)


def build_snapshot(
    frame_index: int,
    state: str,
    locked: bool,
    bbox: tuple[int, int, int, int] | None,
    tracker_name: str,
) -> VisionSnapshot:
    timestamp_ms = int(time.time() * 1000)
    if bbox is None:
        x = y = w = h = cx = cy = 0
    else:
        x, y, w, h = bbox
        cx = x + w // 2
        cy = y + h // 2

    return VisionSnapshot(
        timestamp_ms=timestamp_ms,
        frame_index=frame_index,
        vision_state=state,
        vision_locked=locked,
        bbox_x=x,
        bbox_y=y,
        bbox_w=w,
        bbox_h=h,
        center_x=cx,
        center_y=cy,
        tracker_name=tracker_name.upper(),
    )


def print_snapshot(snapshot: VisionSnapshot) -> None:
    print(
        "VISION_STATUS,"
        f"ts={snapshot.timestamp_ms},"
        f"frame={snapshot.frame_index},"
        f"vision_state={snapshot.vision_state},"
        f"vision_locked={int(snapshot.vision_locked)},"
        f"bbox={snapshot.bbox_x},{snapshot.bbox_y},{snapshot.bbox_w},{snapshot.bbox_h},"
        f"cx={snapshot.center_x},"
        f"cy={snapshot.center_y},"
        f"tracker={snapshot.tracker_name}"
    )


def sanitize_file_token(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    return cleaned.strip("_")


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def resolve_event_id_from_records(
    records: list[dict[str, Any]],
    fallback_mtime_ms: int,
    max_age_ms: int,
) -> str:
    now_ms = int(time.time() * 1000)
    for item in records:
        if not isinstance(item, dict):
            continue
        event_id = str(item.get("event_id", "")).strip()
        if not event_id or event_id.upper() == "NONE":
            continue

        host_logged_ms = safe_int(item.get("host_logged_ms", 0), 0)
        display_time_ms = safe_int(item.get("display_time_ms", 0), 0)
        event_ms = host_logged_ms or display_time_ms
        if event_ms <= 0:
            raw_ts = safe_int(item.get("timestamp_ms", 0), 0)
            event_ms = raw_ts if raw_ts >= 946684800000 else fallback_mtime_ms

        if max_age_ms > 0 and event_ms > 0 and (now_ms - event_ms) > max_age_ms:
            continue
        return event_id
    return "NONE"


def resolve_runtime_event_id(
    explicit_event_id: str,
    active_event_file: Path,
    node_status_file: Path,
    node_events_file: Path,
    node_event_store_file: Path,
    event_bind_max_age_ms: int,
    active_event_max_age_ms: int,
) -> tuple[str, str]:
    manual = explicit_event_id.strip()
    if manual:
        return manual, "manual"

    payload = load_json_payload(node_status_file)
    if isinstance(payload, dict):
        for key in ("event_id", "current_event_id", "last_event_id"):
            value = str(payload.get(key, "")).strip()
            if value and value.upper() != "NONE":
                return value, f"node_status.{key}"

    max_age_ms = max(0, safe_int(event_bind_max_age_ms, 0))
    now_ms = int(time.time() * 1000)

    node_events_payload = load_json_payload(node_events_file)
    node_events_records = node_events_payload.get("records", []) if isinstance(node_events_payload, dict) else []
    if not isinstance(node_events_records, list):
        node_events_records = []
    node_events_mtime_ms = int(node_events_file.stat().st_mtime * 1000) if node_events_file.exists() else now_ms
    node_events_event_id = resolve_event_id_from_records(
        node_events_records,
        fallback_mtime_ms=node_events_mtime_ms,
        max_age_ms=max_age_ms,
    )
    if node_events_event_id != "NONE":
        return node_events_event_id, "node_events.latest_non_none"

    active_event_payload = load_json_payload(active_event_file)
    if isinstance(active_event_payload, dict):
        active_event_id = str(active_event_payload.get("event_id", "")).strip()
        active_event_updated_ms = safe_int(active_event_payload.get("updated_ms", 0), 0)
        active_max_age = max(0, safe_int(active_event_max_age_ms, 0))
        active_fresh = (
            active_max_age <= 0
            or (active_event_updated_ms > 0 and (now_ms - active_event_updated_ms) <= active_max_age)
        )
        if active_event_id and active_event_id.upper() != "NONE" and active_fresh:
            return active_event_id, "active_event_file.event_id"

    store_payload = load_json_payload(node_event_store_file)
    store_records = store_payload.get("records", []) if isinstance(store_payload, dict) else []
    if not isinstance(store_records, list):
        store_records = []
    store_mtime_ms = int(node_event_store_file.stat().st_mtime * 1000) if node_event_store_file.exists() else now_ms
    store_event_id = resolve_event_id_from_records(
        store_records,
        fallback_mtime_ms=store_mtime_ms,
        max_age_ms=max_age_ms,
    )
    if store_event_id != "NONE":
        return store_event_id, "event_store.latest_non_none"

    return "NONE", "none"


def build_capture_file_path(
    capture_dir: Path,
    snapshot: VisionSnapshot,
    event_id: str,
    capture_index: int,
) -> Path:
    timestamp = datetime.now()
    name_parts = [
        timestamp.strftime("%Y-%m-%d_%H-%M-%S"),
        f"{int(timestamp.microsecond / 1000):03d}ms",
        f"f{snapshot.frame_index:06d}",
        f"cap{capture_index:03d}",
        snapshot.vision_state.lower(),
    ]
    safe_event_id = sanitize_file_token(event_id)
    if safe_event_id:
        name_parts.append(safe_event_id)
    file_name = "_".join(name_parts) + ".jpg"
    return capture_dir / file_name


def save_capture(
    cv: Any,
    frame: Any,
    snapshot: VisionSnapshot,
    capture_dir: Path,
    event_id: str,
    capture_index: int,
    capture_reason: str,
) -> CaptureRecord | None:
    capture_dir.mkdir(parents=True, exist_ok=True)
    file_path = build_capture_file_path(capture_dir, snapshot, event_id, capture_index)

    if not cv.imwrite(str(file_path), frame):
        return None

    return CaptureRecord(
        timestamp_ms=int(time.time() * 1000),
        frame_index=snapshot.frame_index,
        vision_state=snapshot.vision_state,
        vision_locked=snapshot.vision_locked,
        tracker_name=snapshot.tracker_name,
        event_id=event_id,
        file_path=file_path.as_posix(),
        capture_reason=capture_reason,
        bbox_x=snapshot.bbox_x,
        bbox_y=snapshot.bbox_y,
        bbox_w=snapshot.bbox_w,
        bbox_h=snapshot.bbox_h,
        center_x=snapshot.center_x,
        center_y=snapshot.center_y,
    )


def print_capture(record: CaptureRecord) -> None:
    print(
        "CAPTURE,"
        f"ts={record.timestamp_ms},"
        f"frame={record.frame_index},"
        f"vision_state={record.vision_state},"
        f"vision_locked={int(record.vision_locked)},"
        f"tracker={record.tracker_name},"
        f"event_id={record.event_id or 'NONE'},"
        f"reason={record.capture_reason},"
        f"bbox={record.bbox_x},{record.bbox_y},{record.bbox_w},{record.bbox_h},"
        f"cx={record.center_x},"
        f"cy={record.center_y},"
        f"file={record.file_path}"
    )


def vision_signature(snapshot: VisionSnapshot) -> tuple[str, int, int, int, int, int]:
    return (
        snapshot.vision_state,
        int(snapshot.vision_locked),
        snapshot.bbox_x,
        snapshot.bbox_y,
        snapshot.bbox_w,
        snapshot.bbox_h,
    )


def build_status_payload(
    snapshot: VisionSnapshot,
    event_id: str,
    event_id_source: str,
    last_capture: CaptureRecord | None,
    requested_tracker_name: str,
    active_tracker_name: str,
    tracker_fallback_applied: bool,
    available_trackers: list[str],
    source: str,
    source_ready: bool,
    capture_backend: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "timestamp_ms": snapshot.timestamp_ms,
        "frame_index": snapshot.frame_index,
        "vision_state": snapshot.vision_state,
        "vision_locked": int(snapshot.vision_locked),
        "tracker_name": snapshot.tracker_name,
        "event_id": event_id or "",
        "event_id_source": event_id_source,
        "bbox_x": snapshot.bbox_x,
        "bbox_y": snapshot.bbox_y,
        "bbox_w": snapshot.bbox_w,
        "bbox_h": snapshot.bbox_h,
        "center_x": snapshot.center_x,
        "center_y": snapshot.center_y,
        "last_capture_reason": "",
        "last_capture_file": "",
        "last_capture_timestamp_ms": 0,
        "source": source,
        "source_ready": int(source_ready),
        "capture_backend": capture_backend,
        "requested_tracker_name": requested_tracker_name.upper(),
        "active_tracker_name": active_tracker_name.upper(),
        "tracker_fallback_applied": int(tracker_fallback_applied),
        "available_trackers": [name.upper() for name in available_trackers],
        "tracker_ready": int(bool(active_tracker_name)),
        "vision_chain_ready": int(bool(source_ready and active_tracker_name)),
    }
    if last_capture is not None:
        payload["last_capture_reason"] = last_capture.capture_reason
        payload["last_capture_file"] = last_capture.file_path
        payload["last_capture_timestamp_ms"] = last_capture.timestamp_ms
    return payload


def write_latest_status_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def capture_if_allowed(
    cv: Any,
    frame: Any,
    snapshot: VisionSnapshot,
    capture_dir: Path,
    event_id: str,
    capture_reason: str,
    capture_index: int,
    metadata_logger: CaptureMetadataLogger | None,
) -> CaptureRecord | None:
    record = save_capture(
        cv=cv,
        frame=frame,
        snapshot=snapshot,
        capture_dir=capture_dir,
        event_id=event_id,
        capture_index=capture_index,
        capture_reason=capture_reason,
    )
    if record is None:
        return None
    print_capture(record)
    if metadata_logger is not None:
        metadata_logger.write(record)
    return record


def draw_overlay(
    cv: Any,
    frame: Any,
    snapshot: VisionSnapshot,
    show_help: bool,
) -> Any:
    color = (0, 255, 0) if snapshot.vision_locked else (0, 165, 255)
    if snapshot.bbox_w > 0 and snapshot.bbox_h > 0:
        cv.rectangle(
            frame,
            (snapshot.bbox_x, snapshot.bbox_y),
            (snapshot.bbox_x + snapshot.bbox_w, snapshot.bbox_y + snapshot.bbox_h),
            color,
            2,
        )
        cv.circle(frame, (snapshot.center_x, snapshot.center_y), 3, color, -1)

    cv.putText(
        frame,
        f"State: {snapshot.vision_state}",
        (12, 28),
        cv.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )
    cv.putText(
        frame,
        f"Locked: {int(snapshot.vision_locked)}  Tracker: {snapshot.tracker_name}",
        (12, 56),
        cv.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
    )
    cv.putText(
        frame,
        f"Center: ({snapshot.center_x}, {snapshot.center_y})  Frame: {snapshot.frame_index}",
        (12, 84),
        cv.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )

    if show_help:
        help_lines = [
            "Keys: s/SPACE select target",
            "c capture when locked",
            "r reset tracker",
            "h toggle help",
            "q or ESC quit",
        ]
        start_y = 122
        for index, line in enumerate(help_lines):
            cv.putText(
                frame,
                line,
                (12, start_y + index * 26),
                cv.FONT_HERSHEY_SIMPLEX,
                0.55,
                (220, 220, 220),
                2,
            )

    return frame


def select_target_roi(
    cv: Any,
    frame: Any,
    tracker_name: str,
) -> tuple[Any | None, tuple[int, int, int, int] | None]:
    print("Select a target ROI, then press ENTER. Press C to cancel.")
    roi = cv.selectROI(WINDOW_NAME, frame, fromCenter=False, showCrosshair=True)
    if roi is None:
        return None, None

    bbox = normalize_bbox(roi)
    if bbox[2] <= 0 or bbox[3] <= 0:
        print("ROI selection cancelled.")
        return None, None

    try:
        tracker = create_tracker(cv, tracker_name)
    except RuntimeError as exc:
        print(f"Tracker initialization skipped: {exc}", file=sys.stderr)
        print(
            "Next step: run `python tools/usb_camera_readiness_check_USB摄像头就绪核对.py` "
            "then relaunch vision_bridge with an available tracker (for example `--tracker kcf --tracker-fallback auto`).",
            file=sys.stderr,
        )
        return None, None

    # OpenCV 4.13 on Windows may reject float bbox for tracker.init.
    # Keep bbox as integer tuple for cross-version compatibility.
    try:
        initialized = tracker.init(frame, tuple(int(value) for value in bbox))
    except Exception as exc:
        print(f"Tracker initialization failed: {exc}", file=sys.stderr)
        print(
            "Next step: reselect ROI with a larger box that fully contains the target. "
            "If it still fails, relaunch with `--tracker kcf`.",
            file=sys.stderr,
        )
        return None, None
    if initialized is False:
        print("Tracker initialization failed.", file=sys.stderr)
        return None, None

    print(f"Tracker initialized with ROI {bbox}.")
    return tracker, bbox


def main() -> int:
    cv = require_opencv()

    parser = argparse.ArgumentParser(
        description="Minimal OpenCV vision bridge for close-range visual lock testing"
    )
    parser.add_argument("--source", default="0", help="Camera index like 0, or a video file path")
    parser.add_argument("--backend", choices=list(SUPPORTED_CAPTURE_BACKENDS), default="auto", help="OpenCV capture backend: auto/msmf/dshow")
    parser.add_argument("--backend-fallback", choices=["auto", "off"], default="auto", help="When source open/read fails: auto-try other capture backends, or keep requested backend only")
    parser.add_argument("--tracker", choices=list(SUPPORTED_TRACKERS), default="csrt", help="OpenCV tracker type")
    parser.add_argument(
        "--tracker-fallback",
        choices=["auto", "off"],
        default="auto",
        help="When requested tracker is unavailable: auto fallback to another tracker, or fail directly",
    )
    parser.add_argument(
        "--list-trackers",
        action="store_true",
        help="Print available tracker backends and exit",
    )
    parser.add_argument("--width", type=int, default=1280, help="Requested capture width for camera sources")
    parser.add_argument("--height", type=int, default=720, help="Requested capture height for camera sources")
    parser.add_argument("--source-warmup-frames", type=int, default=12, help="Frames used to warm up source before first status loop")
    parser.add_argument("--log-interval", type=float, default=1.0, help="Seconds between repeated terminal status prints while locked")
    parser.add_argument("--log-file", type=Path, help="Optional CSV output path for status logging")
    parser.add_argument("--capture-dir", type=Path, default=Path("captures"), help="Directory used to store capture images")
    parser.add_argument("--capture-log-file", type=Path, help="Optional CSV output path for capture metadata. Defaults to <capture-dir>/capture_records.csv")
    parser.add_argument("--capture-cooldown", type=float, default=2.0, help="Minimum seconds between automatic captures")
    parser.add_argument("--status-file", type=Path, default=Path("captures/latest_status.json"), help="JSON file used to expose latest runtime status to the local web server")
    parser.add_argument("--status-write-interval", type=float, default=0.25, help="Minimum seconds between two status JSON writes while state stays unchanged")
    parser.add_argument("--session-file", type=Path, default=Path("captures/latest_test_session.json"), help="JSON file written by track_injector with the current test session")
    parser.add_argument("--session-log-dir", type=Path, default=Path("captures/session_logs"), help="Directory used to store per-session JSONL timeline logs")
    parser.add_argument("--active-event-file", type=Path, default=Path("captures/latest_active_event.json"), help="Dashboard-selected active event JSON used as short-lived hint fallback")
    parser.add_argument("--node-status-file", type=Path, default=Path("captures/latest_node_status.json"), help="Node A status JSON file used to auto-bind capture records to current event_id")
    parser.add_argument("--node-events-file", type=Path, default=Path("captures/latest_node_events.json"), help="Node A recent events JSON used as first fallback when node_status event_id is NONE")
    parser.add_argument("--node-event-store-file", type=Path, default=Path("captures/latest_node_event_store.json"), help="Node A persistent event store JSON used as fallback when node_status event_id is NONE")
    parser.add_argument("--event-bind-max-age-ms", type=int, default=300000, help="Maximum age for fallback event binding from node_events/event_store; set 0 to disable age limit")
    parser.add_argument("--active-event-max-age-ms", type=int, default=ACTIVE_EVENT_MAX_AGE_MS_DEFAULT, help="Maximum age for dashboard selected active event; set 0 to disable age limit")
    parser.add_argument("--event-id", default="", help="Optional event_id tag appended to saved capture files")
    args = parser.parse_args()
    args.capture_dir = resolve_path(args.capture_dir)
    args.status_file = resolve_path(args.status_file)
    args.session_file = resolve_path(args.session_file)
    args.session_log_dir = resolve_path(args.session_log_dir)
    args.active_event_file = resolve_path(args.active_event_file)
    args.node_status_file = resolve_path(args.node_status_file)
    args.node_events_file = resolve_path(args.node_events_file)
    args.node_event_store_file = resolve_path(args.node_event_store_file)
    if args.log_file:
        args.log_file = resolve_path(args.log_file)
    if args.capture_log_file:
        args.capture_log_file = resolve_path(args.capture_log_file)

    available_trackers = list_available_trackers(cv)
    if args.list_trackers:
        available_text = ", ".join(name.upper() for name in available_trackers) if available_trackers else "NONE"
        print(f"Available trackers: {available_text}")
        return 0

    try:
        active_tracker_name, fallback_applied, available_trackers = resolve_tracker_selection(
            cv,
            args.tracker,
            args.tracker_fallback,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        print(
            "Next step: run `python tools/vision_bridge_视觉桥接.py --list-trackers` "
            "or `python tools/usb_camera_readiness_check_USB摄像头就绪核对.py` to get a valid tracker command.",
            file=sys.stderr,
        )
        if args.tracker_fallback == "off":
            print("Tip: rerun with `--tracker-fallback auto` to enable automatic tracker fallback.", file=sys.stderr)
        return 1

    cap: Any | None = None
    first_frame: Any | None = None
    source_probe_attempts = 0
    active_backend = "auto"
    backend_candidates = capture_backend_candidates(args.backend, args.backend_fallback)
    for backend_candidate in backend_candidates:
        candidate_cap, candidate_backend = open_source(cv, args.source, args.width, args.height, backend_candidate)
        if not candidate_cap.isOpened():
            candidate_cap.release()
            continue
        source_ready, candidate_first_frame, candidate_attempts = warmup_source_frame(candidate_cap, args.source_warmup_frames)
        if source_ready and candidate_first_frame is not None:
            cap = candidate_cap
            first_frame = candidate_first_frame
            source_probe_attempts = candidate_attempts
            active_backend = candidate_backend
            break
        source_probe_attempts = candidate_attempts
        candidate_cap.release()

    if cap is None or first_frame is None:
        attempted_text = ", ".join(backend_candidates)
        print(f"Failed to open/read video source `{args.source}`. attempted_backends={attempted_text}", file=sys.stderr)
        print(
            "Next step: run `python tools/usb_camera_readiness_check_USB摄像头就绪核对.py` "
            "and use its `recommended_command`.",
            file=sys.stderr,
        )
        return 1

    csv_logger = CsvVisionLogger(args.log_file) if args.log_file else None
    capture_log_file = args.capture_log_file or (args.capture_dir / "capture_records.csv")
    capture_metadata_logger = CaptureMetadataLogger(capture_log_file)
    frame_index = 0
    tracker: Any | None = None
    current_bbox: tuple[int, int, int, int] | None = None
    current_state = VISION_IDLE
    last_state = VISION_IDLE
    last_print_time = 0.0
    last_print_signature: tuple[str, int, int, int, int] | None = None
    last_status_signature: tuple[str, int, int, int, int] | None = None
    show_help = True
    capture_index = 0
    last_auto_capture_time = 0.0
    last_status_write_time = 0.0
    last_capture_record: CaptureRecord | None = None
    last_vision_signature: tuple[str, int, int, int, int, int] | None = None
    last_capture_hint_time = 0.0

    print("Vision bridge started.")
    print(f"Writing session timeline logs to: {args.session_log_dir.as_posix()}")
    print(
        "Event binding: "
        f"active={args.active_event_file.as_posix()} / "
        f"status={args.node_status_file.as_posix()} / "
        f"events={args.node_events_file.as_posix()} / "
        f"store={args.node_event_store_file.as_posix()} / "
        f"max_age_ms={max(0, args.event_bind_max_age_ms)} / "
        f"active_max_age_ms={max(0, args.active_event_max_age_ms)}"
    )
    print(
        "Tracker selection: "
        f"requested={args.tracker.upper()}, active={active_tracker_name.upper()}, fallback={int(fallback_applied)}"
    )
    print(
        "Available trackers in this OpenCV build: "
        + (", ".join(name.upper() for name in available_trackers) if available_trackers else "NONE")
    )
    print(
        "Capture backend: "
        f"requested={str(args.backend).lower()}, active={active_backend}, fallback={str(args.backend_fallback).lower()}"
    )
    source_width = 0
    source_height = 0
    try:
        source_width = int(first_frame.shape[1])
        source_height = int(first_frame.shape[0])
    except Exception:
        source_width = source_height = 0
    source_fps = float(cap.get(cv.CAP_PROP_FPS) or 0.0)
    print(
        f"Source probe: ready=1, source={args.source}, frame={source_width}x{source_height}, "
        f"fps={source_fps:.2f}, warmup_attempts={source_probe_attempts}"
    )
    print(
        "Press `s` or SPACE to select a target. Press `c` to capture when locked. "
        "Auto-capture runs on new lock. Press `r` to reset. Press `q` to quit."
    )

    try:
        pending_frame = first_frame
        while True:
            if pending_frame is not None:
                ok = True
                frame = pending_frame
                pending_frame = None
            else:
                ok, frame = cap.read()
            if not ok or frame is None:
                print("Video source ended or frame capture failed.", file=sys.stderr)
                return 1

            frame_index += 1

            if tracker is not None:
                success, raw_bbox = tracker.update(frame)
                if success:
                    current_bbox = normalize_bbox(raw_bbox)
                    if current_bbox[2] > 0 and current_bbox[3] > 0:
                        current_state = VISION_LOCKED
                    else:
                        tracker = None
                        current_bbox = None
                        current_state = VISION_LOST
                else:
                    tracker = None
                    current_bbox = None
                    current_state = VISION_LOST

            snapshot = build_snapshot(
                frame_index=frame_index,
                state=current_state,
                locked=current_state == VISION_LOCKED,
                bbox=current_bbox,
                tracker_name=active_tracker_name,
            )
            runtime_event_id, runtime_event_id_source = resolve_runtime_event_id(
                args.event_id,
                args.active_event_file,
                args.node_status_file,
                args.node_events_file,
                args.node_event_store_file,
                args.event_bind_max_age_ms,
                args.active_event_max_age_ms,
            )
            current_vision_signature = vision_signature(snapshot)
            if current_vision_signature != last_vision_signature:
                append_session_event(
                    load_json_payload(args.session_file),
                    args.session_log_dir,
                    source="vision_bridge",
                    event_type="vision_status_changed",
                    payload={
                        "frame_index": snapshot.frame_index,
                        "vision_state": snapshot.vision_state,
                        "vision_locked": int(snapshot.vision_locked),
                        "bbox_x": snapshot.bbox_x,
                        "bbox_y": snapshot.bbox_y,
                        "bbox_w": snapshot.bbox_w,
                        "bbox_h": snapshot.bbox_h,
                        "center_x": snapshot.center_x,
                        "center_y": snapshot.center_y,
                        "tracker_name": snapshot.tracker_name,
                    },
                )
                last_vision_signature = current_vision_signature

            signature = (
                snapshot.vision_state,
                snapshot.bbox_x,
                snapshot.bbox_y,
                snapshot.bbox_w,
                snapshot.bbox_h,
            )
            now = time.time()
            should_print = signature != last_print_signature
            if not should_print and snapshot.vision_locked and (now - last_print_time) >= args.log_interval:
                should_print = True

            if should_print:
                print_snapshot(snapshot)
                last_print_time = now
                last_print_signature = signature
                if csv_logger is not None:
                    csv_logger.write(snapshot)

            status_due = signature != last_status_signature or (now - last_status_write_time) >= args.status_write_interval
            if status_due:
                write_latest_status_json(
                    args.status_file,
                    build_status_payload(
                        snapshot,
                        runtime_event_id,
                        runtime_event_id_source,
                        last_capture_record,
                        requested_tracker_name=args.tracker,
                        active_tracker_name=active_tracker_name,
                        tracker_fallback_applied=fallback_applied,
                        available_trackers=available_trackers,
                        source=args.source,
                        source_ready=True,
                        capture_backend=active_backend,
                    ),
                )
                last_status_signature = signature
                last_status_write_time = now

            is_new_lock = snapshot.vision_locked and last_state != VISION_LOCKED
            cooldown_ready = (now - last_auto_capture_time) >= args.capture_cooldown
            if is_new_lock and cooldown_ready:
                capture_index += 1
                record = capture_if_allowed(
                    cv=cv,
                    frame=frame,
                    snapshot=snapshot,
                    capture_dir=args.capture_dir,
                    event_id=runtime_event_id,
                    capture_reason="AUTO_LOCK",
                    capture_index=capture_index,
                    metadata_logger=capture_metadata_logger,
                )
                if record is None:
                    print("Auto capture failed: could not write image file.", file=sys.stderr)
                else:
                    last_auto_capture_time = now
                    last_capture_record = record
                    append_session_event(
                        load_json_payload(args.session_file),
                        args.session_log_dir,
                        source="vision_bridge",
                        event_type="capture_saved",
                        payload={
                            "capture_reason": record.capture_reason,
                            "file_path": record.file_path,
                            "event_id": record.event_id,
                            "frame_index": record.frame_index,
                            "vision_state": record.vision_state,
                        },
                    )
                    write_latest_status_json(
                        args.status_file,
                        build_status_payload(
                            snapshot,
                            runtime_event_id,
                            runtime_event_id_source,
                            last_capture_record,
                            requested_tracker_name=args.tracker,
                            active_tracker_name=active_tracker_name,
                            tracker_fallback_applied=fallback_applied,
                            available_trackers=available_trackers,
                            source=args.source,
                            source_ready=True,
                            capture_backend=active_backend,
                        ),
                    )
                    last_status_signature = signature
                    last_status_write_time = now

            display = draw_overlay(cv, frame.copy(), snapshot, show_help)
            cv.imshow(WINDOW_NAME, display)
            key = cv.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                print("Vision bridge stopped by user.")
                return 0
            if key in (ord("h"), ord("H")):
                show_help = not show_help
                last_state = current_state
                continue
            if key in (ord("r"), ord("R")):
                tracker = None
                current_bbox = None
                current_state = VISION_IDLE
                last_state = current_state
                continue
            if key in (ord("c"), ord("C")):
                if current_state != VISION_LOCKED:
                    if (now - last_capture_hint_time) >= CAPTURE_HINT_COOLDOWN_S:
                        print(
                            "Capture ignored: target is not locked. "
                            "Next step: click video window -> press `s` -> drag ROI -> press ENTER -> wait VISION_LOCKED -> press `c`."
                        )
                        last_capture_hint_time = now
                    last_state = current_state
                    continue
                capture_index += 1
                record = capture_if_allowed(
                    cv=cv,
                    frame=frame,
                    snapshot=snapshot,
                    capture_dir=args.capture_dir,
                    event_id=runtime_event_id,
                    capture_reason="MANUAL",
                    capture_index=capture_index,
                    metadata_logger=capture_metadata_logger,
                )
                if record is None:
                    print("Capture failed: could not write image file.", file=sys.stderr)
                else:
                    last_capture_record = record
                    append_session_event(
                        load_json_payload(args.session_file),
                        args.session_log_dir,
                        source="vision_bridge",
                        event_type="capture_saved",
                        payload={
                            "capture_reason": record.capture_reason,
                            "file_path": record.file_path,
                            "event_id": record.event_id,
                            "frame_index": record.frame_index,
                            "vision_state": record.vision_state,
                        },
                    )
                    write_latest_status_json(
                        args.status_file,
                        build_status_payload(
                            snapshot,
                            runtime_event_id,
                            runtime_event_id_source,
                            last_capture_record,
                            requested_tracker_name=args.tracker,
                            active_tracker_name=active_tracker_name,
                            tracker_fallback_applied=fallback_applied,
                            available_trackers=available_trackers,
                            source=args.source,
                            source_ready=True,
                            capture_backend=active_backend,
                        ),
                    )
                    last_status_signature = signature
                    last_status_write_time = now
                last_state = current_state
                continue
            if key in (ord("s"), ord("S"), 32):
                current_state = VISION_SEARCHING
                snapshot = build_snapshot(
                    frame_index=frame_index,
                    state=current_state,
                    locked=False,
                    bbox=current_bbox,
                    tracker_name=active_tracker_name,
                )
                print_snapshot(snapshot)
                tracker, current_bbox = select_target_roi(cv, frame, active_tracker_name)
                if tracker is not None and current_bbox is not None:
                    current_state = VISION_LOCKED
                else:
                    current_state = VISION_IDLE
                last_print_signature = None

            last_state = current_state
    finally:
        cap.release()
        cv.destroyAllWindows()
        if csv_logger is not None:
            csv_logger.close()
        capture_metadata_logger.close()


if __name__ == "__main__":
    raise SystemExit(main())

