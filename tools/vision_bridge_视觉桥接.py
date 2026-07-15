# ?????????????????????????????????????????????????
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
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
SUPPORTED_TRACKERS = ("csrt", "kcf", "mil")
SUPPORTED_CAPTURE_BACKENDS = ("auto", "msmf", "dshow")
ACTIVE_EVENT_MAX_AGE_MS_DEFAULT = 15000
DEFAULT_FRAME_MIN_MEAN_LUMA = 5.0
DEFAULT_FRAME_MAX_MEAN_LUMA = 250.0
DEFAULT_FRAME_MIN_LUMA_STDDEV = 2.0
DEFAULT_YOLO_SCORE_THRESHOLD = 0.45
DEFAULT_YOLO_INTRA_OP_THREADS = 8
DEFAULT_AUTO_LOCK_IOU_THRESHOLD = 0.25
STATUS_REPLACE_RETRY_COUNT = 10
STATUS_REPLACE_RETRY_DELAY_S = 0.05


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
    frame_width: int = 0
    frame_height: int = 0
    vision_confidence: float = 0.0
    bbox_stability_score: float = 0.0
    tracker_state: str = "LOST"
    detector_state: str = "DISABLED"
    detector_model_label: str = "none"
    detector_class_strategy: str = "none"
    yolo_detections: list[dict[str, Any]] = field(default_factory=list)
    lock_source: str = "NONE"
    auto_lock_score: float = 0.0
    auto_lock_class_name: str = "none"
    frame_content_ready: bool = False
    frame_mean_luma: float = 0.0
    frame_luma_stddev: float = 0.0
    frame_quality_reason: str = "UNMEASURED"


@dataclass(frozen=True)
class FrameQuality:
    ready: bool
    mean_luma: float
    luma_stddev: float
    reason: str


@dataclass(frozen=True)
class AutoLockDetection:
    bbox: tuple[int, int, int, int]
    score: float
    class_name: str


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


@dataclass
class NodeRuntimeSignals:
    risk_level: str
    event_active: int
    event_id: str
    last_event_id: str
    updated_ms: int


@dataclass
class GimbalSignals:
    # 来自固件侧 node_status 的云台/视觉引导字段。
    gimbal_state: str    # 例如 "TRACKING" / "IDLE" / "LOST"
    track_confirmed: int # 1 = 目标已稳定确认，0 = 未确认
    track_active: int    # 1 = 正在跟踪，0 = 已退出
    x_mm: float          # 雷达/视觉坐标 X（毫米）
    y_mm: float          # 雷达/视觉坐标 Y（毫米）


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
    if tracker_name == "mil":
        return hasattr(cv, "TrackerMIL_create") or (hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerMIL_create"))
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
    if tracker_name == "mil":
        if hasattr(cv, "TrackerMIL_create"):
            return cv.TrackerMIL_create()
        if hasattr(cv, "legacy") and hasattr(cv.legacy, "TrackerMIL_create"):
            return cv.legacy.TrackerMIL_create()

    raise RuntimeError(
        f"Tracker `{tracker_name}` is not available in this OpenCV build. "
        "Try another tracker or install opencv-contrib-python."
    )


def evaluate_frame_quality(
    cv: Any,
    frame: Any,
    min_mean_luma: float = DEFAULT_FRAME_MIN_MEAN_LUMA,
    max_mean_luma: float = DEFAULT_FRAME_MAX_MEAN_LUMA,
    min_luma_stddev: float = DEFAULT_FRAME_MIN_LUMA_STDDEV,
) -> FrameQuality:
    if frame is None:
        return FrameQuality(False, 0.0, 0.0, "FRAME_MISSING")
    try:
        gray = frame if len(frame.shape) == 2 else cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        mean_value, stddev_value = cv.meanStdDev(gray)
        mean_luma = float(mean_value[0][0])
        luma_stddev = float(stddev_value[0][0])
    except Exception:
        return FrameQuality(False, 0.0, 0.0, "FRAME_INVALID")

    if mean_luma < max(0.0, float(min_mean_luma)):
        reason = "FRAME_TOO_DARK"
    elif mean_luma > min(255.0, float(max_mean_luma)):
        reason = "FRAME_TOO_BRIGHT"
    elif luma_stddev < max(0.0, float(min_luma_stddev)):
        reason = "FRAME_TOO_FLAT"
    else:
        reason = "OK"
    return FrameQuality(reason == "OK", round(mean_luma, 3), round(luma_stddev, 3), reason)


def bbox_iou(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> float:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    left_x2 = lx + max(0, lw)
    left_y2 = ly + max(0, lh)
    right_x2 = rx + max(0, rw)
    right_y2 = ry + max(0, rh)
    intersection_w = max(0, min(left_x2, right_x2) - max(lx, rx))
    intersection_h = max(0, min(left_y2, right_y2) - max(ly, ry))
    intersection = float(intersection_w * intersection_h)
    union = float(max(0, lw) * max(0, lh) + max(0, rw) * max(0, rh)) - intersection
    return intersection / union if union > 0.0 else 0.0


def expand_and_clamp_bbox(
    bbox: tuple[int, int, int, int],
    frame_width: int,
    frame_height: int,
    margin_ratio: float,
) -> tuple[int, int, int, int]:
    x, y, w, h = bbox
    margin_x = int(round(max(0.0, float(margin_ratio)) * max(0, w)))
    margin_y = int(round(max(0.0, float(margin_ratio)) * max(0, h)))
    border_x = 1 if frame_width >= 3 else 0
    border_y = 1 if frame_height >= 3 else 0
    x1 = max(border_x, x - margin_x)
    y1 = max(border_y, y - margin_y)
    x2 = min(max(border_x, frame_width - border_x), x + max(0, w) + margin_x)
    y2 = min(max(border_y, frame_height - border_y), y + max(0, h) + margin_y)
    return x1, y1, max(0, x2 - x1), max(0, y2 - y1)


def select_auto_lock_detection(
    detections: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
    min_score: float,
    margin_ratio: float,
) -> AutoLockDetection | None:
    selected: AutoLockDetection | None = None
    for item in detections:
        try:
            score = float(item.get("score", 0.0))
            raw_bbox = (
                int(item.get("bbox_x", 0)),
                int(item.get("bbox_y", 0)),
                int(item.get("bbox_w", 0)),
                int(item.get("bbox_h", 0)),
            )
        except (TypeError, ValueError):
            continue
        if score < max(0.0, float(min_score)) or raw_bbox[2] < 8 or raw_bbox[3] < 8:
            continue
        bbox = expand_and_clamp_bbox(raw_bbox, frame_width, frame_height, margin_ratio)
        if bbox[2] < 8 or bbox[3] < 8:
            continue
        candidate = AutoLockDetection(
            bbox=bbox,
            score=score,
            class_name=str(item.get("class_name", "target") or "target"),
        )
        if selected is None or candidate.score > selected.score:
            selected = candidate
    return selected


def update_auto_lock_candidate(
    previous: AutoLockDetection | None,
    previous_count: int,
    current: AutoLockDetection | None,
    iou_threshold: float,
) -> tuple[AutoLockDetection | None, int]:
    if current is None:
        return None, 0
    same_target = (
        previous is not None
        and previous.class_name == current.class_name
        and bbox_iou(previous.bbox, current.bbox) >= max(0.0, min(1.0, float(iou_threshold)))
    )
    return current, (max(0, previous_count) + 1 if same_target else 1)


def initialize_tracker_from_bbox(
    cv: Any,
    frame: Any,
    tracker_name: str,
    bbox: tuple[int, int, int, int],
) -> tuple[Any | None, tuple[int, int, int, int] | None]:
    normalized_bbox = normalize_bbox(bbox)
    if normalized_bbox[2] <= 0 or normalized_bbox[3] <= 0:
        return None, None
    try:
        tracker = create_tracker(cv, tracker_name)
        initialized = tracker.init(frame, tuple(int(value) for value in normalized_bbox))
    except Exception as exc:
        print(f"Tracker initialization failed: {exc}", file=sys.stderr)
        return None, None
    if initialized is False:
        return None, None
    return tracker, normalized_bbox


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


def warmup_source_frame(
    cv: Any,
    cap: Any,
    warmup_frames: int,
    min_mean_luma: float,
    max_mean_luma: float,
    min_luma_stddev: float,
) -> tuple[bool, Any | None, int, FrameQuality]:
    attempts = max(1, int(warmup_frames))
    last_quality = FrameQuality(False, 0.0, 0.0, "FRAME_MISSING")
    for attempt in range(1, attempts + 1):
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        last_quality = evaluate_frame_quality(
            cv,
            frame,
            min_mean_luma=min_mean_luma,
            max_mean_luma=max_mean_luma,
            min_luma_stddev=min_luma_stddev,
        )
        if last_quality.ready:
            return True, frame, attempt, last_quality
    return False, None, attempts, last_quality


def normalize_bbox(bbox: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    x, y, w, h = bbox
    return int(x), int(y), int(w), int(h)


def build_snapshot(
    frame_index: int,
    state: str,
    locked: bool,
    bbox: tuple[int, int, int, int] | None,
    tracker_name: str,
    frame_width: int = 0,
    frame_height: int = 0,
    lock_source: str = "NONE",
    auto_lock_score: float = 0.0,
    auto_lock_class_name: str = "none",
    frame_quality: FrameQuality | None = None,
) -> VisionSnapshot:
    timestamp_ms = int(time.time() * 1000)
    if bbox is None:
        x = y = w = h = cx = cy = 0
    else:
        x, y, w, h = bbox
        cx = x + w // 2
        cy = y + h // 2

    bbox_area = float(w * h) if bbox is not None else 0.0
    frame_area = float(frame_width * frame_height) if frame_width > 0 and frame_height > 0 else 1.0
    area_ratio = max(0.0, min(1.0, bbox_area / frame_area * 8.0))
    confidence = 0.0
    if locked:
        confidence = max(0.35, min(0.95, 0.55 + area_ratio * 0.25))
    elif state == VISION_SEARCHING:
        confidence = 0.25
    stability = confidence if locked else 0.0

    quality = frame_quality or FrameQuality(False, 0.0, 0.0, "UNMEASURED")
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
        frame_width=frame_width,
        frame_height=frame_height,
        vision_confidence=confidence,
        bbox_stability_score=stability,
        tracker_state="TRACKING" if locked else ("OCCLUDED" if state == VISION_LOST else "LOST"),
        lock_source=lock_source,
        auto_lock_score=max(0.0, float(auto_lock_score)),
        auto_lock_class_name=auto_lock_class_name or "none",
        frame_content_ready=quality.ready,
        frame_mean_luma=quality.mean_luma,
        frame_luma_stddev=quality.luma_stddev,
        frame_quality_reason=quality.reason,
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
        f"tracker={snapshot.tracker_name},"
        f"lock_source={snapshot.lock_source},"
        f"auto_lock_score={snapshot.auto_lock_score:.3f},"
        f"frame_content_ready={int(snapshot.frame_content_ready)},"
        f"frame_quality={snapshot.frame_quality_reason}"
    )


def parse_yolo_class_ids(raw: str) -> list[int]:
    values: list[int] = []
    for token in str(raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = int(token)
        except ValueError:
            continue
        if value >= 0 and value not in values:
            values.append(value)
    return values or [4, 14]


def parse_yolo_class_names(raw: str) -> dict[int, str]:
    names: dict[int, str] = {4: "airplane", 14: "bird"}
    for token in str(raw or "").split(","):
        token = token.strip()
        if not token or ":" not in token:
            continue
        left, right = token.split(":", 1)
        try:
            class_id = int(left.strip())
        except ValueError:
            continue
        name = right.strip()
        if name:
            names[class_id] = name
    return names


def format_class_strategy(class_ids: list[int], class_names: dict[int, str]) -> str:
    return ",".join(f"{class_id}:{class_names.get(class_id, f'class_{class_id}')}" for class_id in class_ids)


def prepare_yolo_letterbox_input(
    cv: Any,
    np: Any,
    frame: Any,
    input_size: int,
) -> tuple[Any, float, float, int, int]:
    frame_height, frame_width = frame.shape[:2]
    target_size = max(1, int(input_size))
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("YOLO input frame must have positive dimensions")

    scale = min(target_size / frame_width, target_size / frame_height)
    resized_width = max(1, min(target_size, int(round(frame_width * scale))))
    resized_height = max(1, min(target_size, int(round(frame_height * scale))))
    resized = cv.resize(frame, (resized_width, resized_height))

    pad_width = target_size - resized_width
    pad_height = target_size - resized_height
    pad_left = pad_width // 2
    pad_right = pad_width - pad_left
    pad_top = pad_height // 2
    pad_bottom = pad_height - pad_top
    letterboxed = cv.copyMakeBorder(
        resized,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        cv.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    rgb = cv.cvtColor(letterboxed, cv.COLOR_BGR2RGB)
    blob = np.ascontiguousarray(np.transpose(rgb.astype("float32") / 255.0, (2, 0, 1))[None, ...])
    return (
        blob,
        resized_width / frame_width,
        resized_height / frame_height,
        pad_left,
        pad_top,
    )


def decode_yolo_predictions(
    cv: Any,
    np: Any,
    raw_output: Any,
    frame_width: int,
    frame_height: int,
    input_size: int,
    class_ids: list[int],
    class_names: dict[int, str],
    score_threshold: float,
    input_scale_x: float | None = None,
    input_scale_y: float | None = None,
    input_pad_x: float = 0.0,
    input_pad_y: float = 0.0,
) -> list[dict[str, Any]]:
    predictions = np.asarray(raw_output).squeeze()
    if predictions.ndim != 2:
        return []

    # Ultralytics exports [1, 4 + class_count, candidate_count]. A one-class
    # model is therefore [1, 5, 8400], which must also be transposed.
    if predictions.shape[0] < predictions.shape[1]:
        predictions = predictions.T

    accepted_class_ids = list(class_ids)
    boxes: list[list[int]] = []
    scores: list[float] = []
    classes: list[int] = []
    threshold = max(0.01, min(0.99, float(score_threshold)))
    scale_x = float(input_scale_x) if input_scale_x is not None else input_size / max(1, frame_width)
    scale_y = float(input_scale_y) if input_scale_y is not None else input_size / max(1, frame_height)
    if scale_x <= 0.0 or scale_y <= 0.0:
        return []
    for row in predictions:
        best_class = -1
        best_score = 0.0
        for class_id in accepted_class_ids:
            score_index = 4 + class_id
            if class_id < 0 or row.shape[0] <= score_index:
                continue
            score = float(row[score_index])
            if score > best_score:
                best_score = score
                best_class = class_id
        if best_class < 0 or best_score < threshold:
            continue

        cx, cy, bw, bh = [float(value) for value in row[:4]]
        x1 = max(0.0, min(float(frame_width), (cx - bw / 2.0 - input_pad_x) / scale_x))
        y1 = max(0.0, min(float(frame_height), (cy - bh / 2.0 - input_pad_y) / scale_y))
        x2 = max(0.0, min(float(frame_width), (cx + bw / 2.0 - input_pad_x) / scale_x))
        y2 = max(0.0, min(float(frame_height), (cy + bh / 2.0 - input_pad_y) / scale_y))
        if x2 <= x1 or y2 <= y1:
            continue
        x = max(0, min(frame_width - 1, int(round(x1))))
        y = max(0, min(frame_height - 1, int(round(y1))))
        right = max(x + 1, min(frame_width, int(round(x2))))
        bottom = max(y + 1, min(frame_height, int(round(y2))))
        w = right - x
        h = bottom - y
        if w <= 0 or h <= 0:
            continue
        boxes.append([x, y, w, h])
        scores.append(best_score)
        classes.append(best_class)

    keep = cv.dnn.NMSBoxes(boxes, scores, threshold, 0.45) if boxes else []
    flattened_keep = np.asarray(keep).reshape(-1).tolist() if len(keep) else []
    detections: list[dict[str, Any]] = []
    for item_index in flattened_keep[:5]:
        index = int(item_index)
        x, y, w, h = boxes[index]
        class_id = classes[index]
        detections.append(
            {
                "bbox_x": x,
                "bbox_y": y,
                "bbox_w": w,
                "bbox_h": h,
                "score": round(float(scores[index]), 3),
                "class_id": class_id,
                "class_name": class_names.get(class_id, f"class_{class_id}"),
            }
        )
    return detections


class SidecarDetector:
    """Non-blocking detector path used by overlays and automatic tracker lock."""

    def __init__(
        self,
        cv: Any,
        enabled: bool,
        model_path: Path,
        every_n_frames: int,
        class_ids: list[int],
        class_names: dict[int, str],
        model_label: str,
        score_threshold: float,
        intra_op_threads: int = DEFAULT_YOLO_INTRA_OP_THREADS,
    ) -> None:
        self.cv = cv
        self.enabled = bool(enabled)
        self.model_path = model_path
        self.every_n_frames = max(1, int(every_n_frames))
        self.class_ids = list(class_ids) or [4, 14]
        self.class_names = dict(class_names)
        self.model_label = model_label or self.model_path.stem or "none"
        self.score_threshold = max(0.01, min(0.99, float(score_threshold)))
        logical_cpu_count = max(1, int(os.cpu_count() or 1))
        self.intra_op_threads = max(1, min(int(intra_op_threads), logical_cpu_count))
        self.class_strategy = format_class_strategy(self.class_ids, self.class_names)
        self.state = "DISABLED"
        self._session: Any | None = None
        self._input_name = ""
        self._lock = threading.Lock()
        self._busy = False
        self._latest: list[dict[str, Any]] = []
        self._revision = 0
        self._last_gray: Any | None = None

        if not self.enabled:
            return
        if not self.model_path.exists():
            self.state = "FALLBACK_FLOW"
            return
        try:
            import onnxruntime as ort  # type: ignore

            session_options = ort.SessionOptions()
            session_options.intra_op_num_threads = self.intra_op_threads
            session_options.inter_op_num_threads = 1
            session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            self._session = ort.InferenceSession(
                str(self.model_path),
                sess_options=session_options,
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name
            self.state = "READY_ONNX"
        except Exception as exc:  # pragma: no cover - depends on local runtime
            self.state = "FALLBACK_FLOW"
            print(f"YOLO sidecar fallback: {exc}", file=sys.stderr)

    def submit(self, frame_index: int, frame: Any) -> None:
        if not self.enabled or frame_index % self.every_n_frames != 0:
            return
        if self._session is None:
            self._run_flow(frame)
            return
        with self._lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._run_onnx, args=(frame.copy(),), daemon=True).start()

    def latest(self) -> tuple[str, list[dict[str, Any]], int]:
        with self._lock:
            return self.state, [dict(item) for item in self._latest], self._revision

    def metadata(self) -> tuple[str, str]:
        return self.model_label, self.class_strategy

    def _set_latest(self, state: str, detections: list[dict[str, Any]]) -> None:
        with self._lock:
            self.state = state
            self._latest = detections
            self._revision += 1
            self._busy = False

    def _run_flow(self, frame: Any) -> None:
        gray = self.cv.cvtColor(frame, self.cv.COLOR_BGR2GRAY)
        gray = self.cv.GaussianBlur(gray, (7, 7), 0)
        if self._last_gray is None:
            self._last_gray = gray
            self._set_latest("FALLBACK_FLOW", [])
            return

        diff = self.cv.absdiff(self._last_gray, gray)
        self._last_gray = gray
        _, thresh = self.cv.threshold(diff, 24, 255, self.cv.THRESH_BINARY)
        thresh = self.cv.dilate(thresh, None, iterations=2)
        contours, _ = self.cv.findContours(thresh, self.cv.RETR_EXTERNAL, self.cv.CHAIN_APPROX_SIMPLE)
        detections: list[dict[str, Any]] = []
        frame_area = max(1, int(frame.shape[0]) * int(frame.shape[1]))
        for contour in sorted(contours, key=self.cv.contourArea, reverse=True)[:3]:
            area = float(self.cv.contourArea(contour))
            if area < max(80.0, frame_area * 0.0004):
                continue
            x, y, w, h = self.cv.boundingRect(contour)
            detections.append(
                {
                    "bbox_x": int(x),
                    "bbox_y": int(y),
                    "bbox_w": int(w),
                    "bbox_h": int(h),
                    "score": round(min(0.75, area / max(1.0, frame_area * 0.02)), 3),
                    "class_id": -1,
                    "class_name": "motion",
                }
            )
        self._set_latest("FALLBACK_FLOW", detections)

    def _run_onnx(self, frame: Any) -> None:
        try:
            import numpy as np  # type: ignore

            height, width = frame.shape[:2]
            input_size = 640
            blob, scale_x, scale_y, pad_x, pad_y = prepare_yolo_letterbox_input(
                self.cv,
                np,
                frame,
                input_size,
            )
            outputs = self._session.run(None, {self._input_name: blob}) if self._session is not None else []
            detections = decode_yolo_predictions(
                cv=self.cv,
                np=np,
                raw_output=outputs[0] if outputs else np.empty((0, 0)),
                frame_width=width,
                frame_height=height,
                input_size=input_size,
                class_ids=self.class_ids,
                class_names=self.class_names,
                score_threshold=self.score_threshold,
                input_scale_x=scale_x,
                input_scale_y=scale_y,
                input_pad_x=pad_x,
                input_pad_y=pad_y,
            )
            self._set_latest("READY_ONNX", detections)
        except Exception as exc:  # pragma: no cover - depends on local runtime/model
            print(f"YOLO sidecar failed, switching to fallback flow: {exc}", file=sys.stderr)
            self._session = None
            self._run_flow(frame)


def sanitize_file_token(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    return cleaned.strip("_")


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_event_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "NONE"
    if text.upper() == "NONE":
        return "NONE"
    return text


def normalize_risk_level(value: object) -> str:
    text = str(value or "NONE").strip().upper()
    return text or "NONE"


def load_node_runtime_signals(node_status_file: Path) -> NodeRuntimeSignals:
    payload = load_json_payload(node_status_file)
    if not isinstance(payload, dict):
        return NodeRuntimeSignals(
            risk_level="NONE",
            event_active=0,
            event_id="NONE",
            last_event_id="NONE",
            updated_ms=0,
        )
    event_active = safe_int(payload.get("event_active", 0), 0)
    event_id = normalize_event_id(payload.get("event_id", payload.get("current_event_id", "NONE")))
    last_event_id = normalize_event_id(payload.get("last_event_id", "NONE"))
    updated_ms = safe_int(payload.get("last_update_ms", payload.get("timestamp_ms", 0)), 0)
    return NodeRuntimeSignals(
        risk_level=normalize_risk_level(payload.get("risk_level", "NONE")),
        event_active=1 if event_active > 0 else 0,
        event_id=event_id,
        last_event_id=last_event_id,
        updated_ms=updated_ms,
    )


def load_gimbal_signals(node_status_file: Path) -> GimbalSignals:
    """从 node_status JSON 读取云台引导字段。固件侧尚未写入时返回安全默认值。"""
    payload = load_json_payload(node_status_file)
    if not isinstance(payload, dict):
        return GimbalSignals(gimbal_state="IDLE", track_confirmed=0, track_active=0, x_mm=0.0, y_mm=0.0)
    gimbal_state = str(payload.get("gimbal_state", "IDLE")).strip().upper() or "IDLE"
    track_confirmed = safe_int(payload.get("track_confirmed", 0), 0)
    track_active = safe_int(payload.get("track_active", 0), 0)
    x_mm = float(payload.get("x_mm", 0.0) or 0.0)
    y_mm = float(payload.get("y_mm", 0.0) or 0.0)
    return GimbalSignals(
        gimbal_state=gimbal_state,
        track_confirmed=track_confirmed,
        track_active=track_active,
        x_mm=x_mm,
        y_mm=y_mm,
    )


def radar_to_frame(
    x_mm: float,
    y_mm: float,
    frame_w: int,
    frame_h: int,
    radar_range_x_mm: float = 10000.0,
    radar_range_y_mm: float = 10000.0,
) -> tuple[int, int]:
    """将雷达坐标 (x_mm, y_mm) 映射到画面像素坐标。

    约定（与固件侧对齐，Win 定稿后只需改此处）：
      x_mm 范围 [-radar_range_x_mm/2, +radar_range_x_mm/2] → 画面 [0, frame_w]
      y_mm 范围 [0, radar_range_y_mm]                       → 画面 [frame_h, 0]（远端在上）
    """
    px = int((x_mm / radar_range_x_mm + 0.5) * frame_w)
    py = int((1.0 - y_mm / radar_range_y_mm) * frame_h)
    return max(0, min(frame_w - 1, px)), max(0, min(frame_h - 1, py))


class VisionStateReporter:
    """封装视觉状态回写逻辑（去抖 + 状态输出）。

    当前阶段只打印串口命令格式到 stdout，不真正发串口。
    Win 侧串口接口定稿后，只需替换 _emit() 内部实现。

    去抖规则：
      同一状态需连续保持 debounce_frames 帧才被确认并上报。
      避免 LOCKED/LOST/LOCKED 来回抖动。
    """

    COMMANDS = {
        VISION_LOCKED: "VISION,LOCKED",
        VISION_LOST:   "VISION,LOST",
        VISION_IDLE:   "VISION,IDLE",
    }

    def __init__(self, debounce_frames: int = 3) -> None:
        self._debounce_frames = max(1, debounce_frames)
        self._candidate: str = VISION_IDLE
        self._candidate_count: int = 0
        self._confirmed: str = VISION_IDLE
        self._last_emitted: str = ""

    def update(self, new_state: str) -> str | None:
        """输入当前帧的视觉状态，返回本帧实际确认的状态（去抖后）。

        如果状态发生跳变，返回新状态并打印串口命令；否则返回 None。
        """
        if new_state == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = new_state
            self._candidate_count = 1

        if self._candidate_count >= self._debounce_frames:
            if self._candidate != self._confirmed:
                self._confirmed = self._candidate
                self._emit(self._confirmed)
                return self._confirmed

        return None

    def status_command(self) -> str:
        """返回 VISION,STATUS 命令格式的当前状态字符串。"""
        return f"VISION,STATUS,state={self._confirmed}"

    def confirmed_state(self) -> str:
        return self._confirmed

    def _emit(self, state: str) -> None:
        cmd = self.COMMANDS.get(state, "VISION,IDLE")
        print(f"VISION_CMD,{cmd},confirmed_state={state}")


def is_high_risk_level(level: str) -> bool:
    normalized = normalize_risk_level(level)
    return normalized in {"HIGH_RISK", "EVENT"}


def select_policy_event_id(
    runtime_event_id: str,
    signals: NodeRuntimeSignals,
    fallback_event_id: str = "NONE",
) -> str:
    for candidate in (
        normalize_event_id(runtime_event_id),
        normalize_event_id(signals.event_id),
        normalize_event_id(signals.last_event_id),
        normalize_event_id(fallback_event_id),
    ):
        if candidate != "NONE":
            return candidate
    return "NONE"


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

    max_age_ms = max(0, safe_int(event_bind_max_age_ms, 0))
    now_ms = int(time.time() * 1000)
    payload = load_json_payload(node_status_file)
    if isinstance(payload, dict):
        node_status_mtime_ms = int(node_status_file.stat().st_mtime * 1000) if node_status_file.exists() else 0
        node_status_updated_ms = safe_int(payload.get("last_update_ms", payload.get("timestamp_ms", 0)), 0)
        if node_status_updated_ms < 946684800000:
            node_status_updated_ms = node_status_mtime_ms
        node_status_fresh = (
            max_age_ms <= 0
            or (node_status_updated_ms > 0 and (now_ms - node_status_updated_ms) <= max_age_ms)
        )
        if node_status_fresh:
            for key in ("event_id", "current_event_id", "last_event_id"):
                value = str(payload.get(key, "")).strip()
                if value and value.upper() != "NONE":
                    return value, f"node_status.{key}"

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
        "frame_width": snapshot.frame_width,
        "frame_height": snapshot.frame_height,
        "vision_confidence": round(float(snapshot.vision_confidence), 3),
        "bbox_stability_score": round(float(snapshot.bbox_stability_score), 3),
        "tracker_state": snapshot.tracker_state,
        "detector_state": snapshot.detector_state,
        "detector_model_label": snapshot.detector_model_label,
        "detector_class_strategy": snapshot.detector_class_strategy,
        "yolo_detections": snapshot.yolo_detections,
        "lock_source": snapshot.lock_source,
        "auto_lock_score": round(float(snapshot.auto_lock_score), 3),
        "auto_lock_class_name": snapshot.auto_lock_class_name,
        "frame_content_ready": int(snapshot.frame_content_ready),
        "frame_mean_luma": round(float(snapshot.frame_mean_luma), 3),
        "frame_luma_stddev": round(float(snapshot.frame_luma_stddev), 3),
        "frame_quality_reason": snapshot.frame_quality_reason,
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
        "detector_ready": int(snapshot.detector_state == "READY_ONNX"),
        "vision_chain_ready": int(bool(source_ready and active_tracker_name and snapshot.frame_content_ready)),
    }
    if last_capture is not None:
        payload["last_capture_reason"] = last_capture.capture_reason
        payload["last_capture_file"] = last_capture.file_path
        payload["last_capture_timestamp_ms"] = last_capture.timestamp_ms
    return payload


def write_latest_status_json(
    path: Path,
    payload: dict[str, object],
    *,
    retry_count: int = STATUS_REPLACE_RETRY_COUNT,
    retry_delay_s: float = STATUS_REPLACE_RETRY_DELAY_S,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    attempts = max(1, int(retry_count))
    for attempt in range(1, attempts + 1):
        try:
            temp_path.replace(path)
            return
        except PermissionError:
            if attempt >= attempts:
                raise
            time.sleep(max(0.0, float(retry_delay_s)))


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
    if not snapshot.frame_content_ready:
        print(
            "CAPTURE_REJECTED,"
            f"reason={snapshot.frame_quality_reason},"
            f"mean_luma={snapshot.frame_mean_luma:.3f},"
            f"luma_stddev={snapshot.frame_luma_stddev:.3f},"
            f"event_id={event_id or 'NONE'},"
            f"capture_reason={capture_reason}",
            file=sys.stderr,
        )
        return None
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

    for detection in snapshot.yolo_detections:
        try:
            dx = int(detection.get("bbox_x", 0))
            dy = int(detection.get("bbox_y", 0))
            dw = int(detection.get("bbox_w", 0))
            dh = int(detection.get("bbox_h", 0))
            score = float(detection.get("score", 0.0))
            class_name = str(detection.get("class_name", "target") or "target")
        except (TypeError, ValueError):
            continue
        if dw <= 0 or dh <= 0:
            continue
        cv.rectangle(frame, (dx, dy), (dx + dw, dy + dh), (0, 0, 255), 2)
        cv.putText(
            frame,
            f"{class_name} {score:.2f}",
            (dx, max(18, dy - 6)),
            cv.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
        )

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
        f"Locked: {int(snapshot.vision_locked)}  Tracker: {snapshot.tracker_name}  Source: {snapshot.lock_source}",
        (12, 56),
        cv.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
    )
    cv.putText(
        frame,
        f"Center: ({snapshot.center_x}, {snapshot.center_y})  Frame: {snapshot.frame_index}  Quality: {snapshot.frame_quality_reason}",
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


def draw_guide_box(
    cv: Any,
    frame: Any,
    gimbal: GimbalSignals,
    frame_w: int,
    frame_h: int,
    radar_range_x_mm: float = 10000.0,
    radar_range_y_mm: float = 10000.0,
    box_half_px: int = 40,
) -> Any:
    """在画面上叠加黄色半自动引导框。

    触发条件：gimbal_state == "TRACKING" 且 track_confirmed == 1 且 track_active == 1。
    退出条件：track_active == 0 或 gimbal_state 不为 TRACKING → 不绘制，直接返回。
    当前阶段只做提示框，不自动启动 CSRT 跟踪器。
    """
    if gimbal.gimbal_state != "TRACKING" or gimbal.track_confirmed != 1 or gimbal.track_active != 1:
        return frame

    cx, cy = radar_to_frame(
        gimbal.x_mm,
        gimbal.y_mm,
        frame_w,
        frame_h,
        radar_range_x_mm,
        radar_range_y_mm,
    )

    # 黄色引导框 (BGR: 0, 255, 255)
    yellow = (0, 255, 255)
    cv.rectangle(frame, (cx - box_half_px, cy - box_half_px), (cx + box_half_px, cy + box_half_px), yellow, 2)
    cv.circle(frame, (cx, cy), 4, yellow, -1)
    cv.putText(
        frame,
        f"GUIDE ({gimbal.x_mm:.0f},{gimbal.y_mm:.0f})mm",
        (cx - box_half_px, cy - box_half_px - 8),
        cv.FONT_HERSHEY_SIMPLEX,
        0.5,
        yellow,
        1,
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

    tracker, initialized_bbox = initialize_tracker_from_bbox(cv, frame, tracker_name, bbox)
    if tracker is None or initialized_bbox is None:
        print("Tracker initialization failed. Reselect a larger ROI or use another tracker.", file=sys.stderr)
        return None, None

    print(f"Tracker initialized with ROI {initialized_bbox}.")
    return tracker, initialized_bbox


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
    parser.add_argument("--frame-min-mean-luma", type=float, default=DEFAULT_FRAME_MIN_MEAN_LUMA, help="Reject evidence frames darker than this mean luma")
    parser.add_argument("--frame-max-mean-luma", type=float, default=DEFAULT_FRAME_MAX_MEAN_LUMA, help="Reject evidence frames brighter than this mean luma")
    parser.add_argument("--frame-min-luma-stddev", type=float, default=DEFAULT_FRAME_MIN_LUMA_STDDEV, help="Reject evidence frames with less visual variation than this luma standard deviation")
    parser.add_argument(
        "--policy-capture-enable",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable event-driven capture policy (high-risk enter / event open / event close)",
    )
    parser.add_argument(
        "--policy-capture-high-risk-enter",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Queue a capture when risk_level enters HIGH_RISK/EVENT",
    )
    parser.add_argument(
        "--policy-capture-event-open",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Queue a capture when event_active changes 0 -> 1",
    )
    parser.add_argument(
        "--policy-capture-event-close",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Queue a capture when event_active changes 1 -> 0",
    )
    parser.add_argument(
        "--policy-capture-pending-window-s",
        type=float,
        default=8.0,
        help="Pending window for policy capture reasons waiting for VISION_LOCKED",
    )
    parser.add_argument("--status-file", type=Path, default=Path("captures/latest_status.json"), help="JSON file used to expose latest runtime status to the local web server")
    parser.add_argument("--yolo-enabled", action="store_true", help="Enable YOLOv8n ONNX sidecar metadata path when model/runtime are available")
    parser.add_argument("--yolo-model", type=Path, default=Path("models/yolov8n.onnx"), help="Local ignored YOLOv8n ONNX model path")
    parser.add_argument("--yolo-every-n-frames", type=int, default=10, help="Run sidecar detector every N frames")
    parser.add_argument("--yolo-class-ids", default="4,14", help="Comma-separated YOLO class ids to accept, for example `4,14` for COCO airplane/bird or `0` for a drone model")
    parser.add_argument("--yolo-class-names", default="4:airplane,14:bird", help="Comma-separated class mapping, for example `4:airplane,14:bird` or `0:drone`")
    parser.add_argument("--yolo-model-label", default="", help="Dashboard label for the active YOLO model")
    parser.add_argument(
        "--yolo-score-threshold",
        type=float,
        default=DEFAULT_YOLO_SCORE_THRESHOLD,
        help="Minimum class score for YOLO sidecar detections",
    )
    parser.add_argument(
        "--yolo-intra-op-threads",
        type=int,
        default=DEFAULT_YOLO_INTRA_OP_THREADS,
        help="CPU threads used inside one ONNX inference",
    )
    parser.add_argument(
        "--yolo-auto-lock",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Automatically initialize the tracker from stable YOLO detections",
    )
    parser.add_argument("--yolo-auto-lock-confirmations", type=int, default=2, help="Consecutive detector updates required before automatic lock")
    parser.add_argument("--yolo-auto-lock-min-score", type=float, default=0.45, help="Minimum YOLO score allowed to start automatic tracking")
    parser.add_argument("--yolo-auto-lock-iou", type=float, default=DEFAULT_AUTO_LOCK_IOU_THRESHOLD, help="Minimum overlap used to confirm the same target across detector updates")
    parser.add_argument("--yolo-auto-lock-margin-ratio", type=float, default=0.12, help="Context margin added around the YOLO box before tracker initialization")
    parser.add_argument("--yolo-auto-lock-cooldown-s", type=float, default=1.0, help="Delay before automatic relock after tracker loss or reset")
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
    args.yolo_model = resolve_path(args.yolo_model)
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
    first_frame_quality = FrameQuality(False, 0.0, 0.0, "FRAME_MISSING")
    last_probe_quality = first_frame_quality
    source_probe_attempts = 0
    active_backend = "auto"
    backend_candidates = capture_backend_candidates(args.backend, args.backend_fallback)
    for backend_candidate in backend_candidates:
        candidate_cap, candidate_backend = open_source(cv, args.source, args.width, args.height, backend_candidate)
        if not candidate_cap.isOpened():
            candidate_cap.release()
            continue
        source_ready, candidate_first_frame, candidate_attempts, candidate_quality = warmup_source_frame(
            cv,
            candidate_cap,
            args.source_warmup_frames,
            min_mean_luma=args.frame_min_mean_luma,
            max_mean_luma=args.frame_max_mean_luma,
            min_luma_stddev=args.frame_min_luma_stddev,
        )
        last_probe_quality = candidate_quality
        if source_ready and candidate_first_frame is not None:
            cap = candidate_cap
            first_frame = candidate_first_frame
            first_frame_quality = candidate_quality
            source_probe_attempts = candidate_attempts
            active_backend = candidate_backend
            break
        source_probe_attempts = candidate_attempts
        candidate_cap.release()

    if cap is None or first_frame is None:
        attempted_text = ", ".join(backend_candidates)
        print(
            f"Failed to open/read a usable video source `{args.source}`. "
            f"attempted_backends={attempted_text}, frame_quality={last_probe_quality.reason}",
            file=sys.stderr,
        )
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
    lock_source = "NONE"
    auto_lock_score = 0.0
    auto_lock_class_name = "none"
    auto_lock_candidate: AutoLockDetection | None = None
    auto_lock_candidate_count = 0
    last_auto_lock_detector_revision = -1
    last_auto_lock_attempt_time = 0.0
    invalid_frame_streak = 0
    last_node_signals = load_node_runtime_signals(args.node_status_file)
    current_gimbal_signals = load_gimbal_signals(args.node_status_file)
    vision_reporter = VisionStateReporter(debounce_frames=3)
    sidecar_detector = SidecarDetector(
        cv=cv,
        enabled=bool(args.yolo_enabled),
        model_path=args.yolo_model,
        every_n_frames=args.yolo_every_n_frames,
        class_ids=parse_yolo_class_ids(args.yolo_class_ids),
        class_names=parse_yolo_class_names(args.yolo_class_names),
        model_label=args.yolo_model_label or args.yolo_model.stem,
        score_threshold=args.yolo_score_threshold,
        intra_op_threads=args.yolo_intra_op_threads,
    )
    pending_policy_captures: list[dict[str, object]] = []

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
        "Capture policy: "
        f"enabled={int(bool(args.policy_capture_enable))},"
        f"high_risk_enter={int(bool(args.policy_capture_high_risk_enter))},"
        f"event_open={int(bool(args.policy_capture_event_open))},"
        f"event_close={int(bool(args.policy_capture_event_close))},"
        f"pending_window_s={max(0.0, float(args.policy_capture_pending_window_s)):.1f}"
    )
    print(
        "Available trackers in this OpenCV build: "
        + (", ".join(name.upper() for name in available_trackers) if available_trackers else "NONE")
    )
    print(
        "Capture backend: "
        f"requested={str(args.backend).lower()}, active={active_backend}, fallback={str(args.backend_fallback).lower()}"
    )
    print(
        "Sidecar detector: "
        f"enabled={int(bool(args.yolo_enabled))}, state={sidecar_detector.state}, "
        f"model={sidecar_detector.model_label}, classes={sidecar_detector.class_strategy}, "
        f"threshold={sidecar_detector.score_threshold:.2f}, every_n={max(1, int(args.yolo_every_n_frames))}, "
        f"intra_op_threads={sidecar_detector.intra_op_threads}, "
        f"auto_lock={int(bool(args.yolo_auto_lock))}, auto_min_score={max(0.0, float(args.yolo_auto_lock_min_score)):.2f}, "
        f"auto_confirmations={max(1, int(args.yolo_auto_lock_confirmations))}"
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
        f"fps={source_fps:.2f}, warmup_attempts={source_probe_attempts}, "
        f"mean_luma={first_frame_quality.mean_luma:.2f}, luma_stddev={first_frame_quality.luma_stddev:.2f}, "
        f"frame_quality={first_frame_quality.reason}"
    )
    print(
        "YOLO auto-lock runs when enabled. Press `s` or SPACE for manual fallback. Press `c` to capture when locked. "
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
            now = time.time()
            frame_quality = evaluate_frame_quality(
                cv,
                frame,
                min_mean_luma=args.frame_min_mean_luma,
                max_mean_luma=args.frame_max_mean_luma,
                min_luma_stddev=args.frame_min_luma_stddev,
            )
            if frame_quality.ready:
                invalid_frame_streak = 0
                sidecar_detector.submit(frame_index, frame)
            else:
                invalid_frame_streak += 1

            if tracker is not None and frame_quality.ready:
                success, raw_bbox = tracker.update(frame)
                if success:
                    current_bbox = normalize_bbox(raw_bbox)
                    if current_bbox[2] > 0 and current_bbox[3] > 0:
                        current_state = VISION_LOCKED
                    else:
                        tracker = None
                        current_bbox = None
                        current_state = VISION_LOST
                        lock_source = "NONE"
                        auto_lock_score = 0.0
                        auto_lock_class_name = "none"
                        last_auto_lock_attempt_time = now
                else:
                    tracker = None
                    current_bbox = None
                    current_state = VISION_LOST
                    lock_source = "NONE"
                    auto_lock_score = 0.0
                    auto_lock_class_name = "none"
                    last_auto_lock_attempt_time = now
            elif tracker is not None and invalid_frame_streak >= 3:
                tracker = None
                current_bbox = None
                current_state = VISION_LOST
                lock_source = "NONE"
                auto_lock_score = 0.0
                auto_lock_class_name = "none"
                last_auto_lock_attempt_time = now

            detector_state, detector_detections, detector_revision = sidecar_detector.latest()
            if tracker is not None:
                auto_lock_candidate = None
                auto_lock_candidate_count = 0
                last_auto_lock_detector_revision = detector_revision
            elif detector_revision != last_auto_lock_detector_revision:
                last_auto_lock_detector_revision = detector_revision
                selected_detection = None
                if detector_state == "READY_ONNX" and frame_quality.ready:
                    selected_detection = select_auto_lock_detection(
                        detector_detections,
                        frame_width=int(frame.shape[1]),
                        frame_height=int(frame.shape[0]),
                        min_score=args.yolo_auto_lock_min_score,
                        margin_ratio=args.yolo_auto_lock_margin_ratio,
                    )
                auto_lock_candidate, auto_lock_candidate_count = update_auto_lock_candidate(
                    auto_lock_candidate,
                    auto_lock_candidate_count,
                    selected_detection,
                    args.yolo_auto_lock_iou,
                )

            auto_lock_ready = (
                bool(args.yolo_enabled)
                and bool(args.yolo_auto_lock)
                and tracker is None
                and frame_quality.ready
                and detector_state == "READY_ONNX"
                and auto_lock_candidate is not None
                and auto_lock_candidate_count >= max(1, int(args.yolo_auto_lock_confirmations))
                and (now - last_auto_lock_attempt_time) >= max(0.0, float(args.yolo_auto_lock_cooldown_s))
            )
            if auto_lock_ready and auto_lock_candidate is not None:
                last_auto_lock_attempt_time = now
                tracker, current_bbox = initialize_tracker_from_bbox(
                    cv,
                    frame,
                    active_tracker_name,
                    auto_lock_candidate.bbox,
                )
                if tracker is not None and current_bbox is not None:
                    current_state = VISION_LOCKED
                    lock_source = "YOLO_AUTO"
                    auto_lock_score = auto_lock_candidate.score
                    auto_lock_class_name = auto_lock_candidate.class_name
                    print(
                        "VISION_AUTO_LOCK,"
                        f"frame={frame_index},class={auto_lock_class_name},score={auto_lock_score:.3f},"
                        f"bbox={current_bbox[0]},{current_bbox[1]},{current_bbox[2]},{current_bbox[3]},"
                        f"confirmations={auto_lock_candidate_count},tracker={active_tracker_name.upper()}"
                    )
                    append_session_event(
                        load_json_payload(args.session_file),
                        args.session_log_dir,
                        source="vision_bridge",
                        event_type="vision_auto_locked",
                        payload={
                            "frame_index": frame_index,
                            "class_name": auto_lock_class_name,
                            "score": round(auto_lock_score, 3),
                            "bbox_x": current_bbox[0],
                            "bbox_y": current_bbox[1],
                            "bbox_w": current_bbox[2],
                            "bbox_h": current_bbox[3],
                            "tracker_name": active_tracker_name.upper(),
                            "detector_revision": detector_revision,
                        },
                    )
                else:
                    current_state = VISION_SEARCHING
                    lock_source = "NONE"
                    auto_lock_score = 0.0
                    auto_lock_class_name = "none"
                auto_lock_candidate = None
                auto_lock_candidate_count = 0

            snapshot = build_snapshot(
                frame_index=frame_index,
                state=current_state,
                locked=current_state == VISION_LOCKED,
                bbox=current_bbox,
                tracker_name=active_tracker_name,
                frame_width=int(frame.shape[1]),
                frame_height=int(frame.shape[0]),
                lock_source=lock_source,
                auto_lock_score=auto_lock_score,
                auto_lock_class_name=auto_lock_class_name,
                frame_quality=frame_quality,
            )
            snapshot.detector_state = detector_state
            snapshot.yolo_detections = detector_detections
            snapshot.detector_model_label, snapshot.detector_class_strategy = sidecar_detector.metadata()
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
                        "lock_source": snapshot.lock_source,
                        "auto_lock_score": round(snapshot.auto_lock_score, 3),
                        "auto_lock_class_name": snapshot.auto_lock_class_name,
                        "frame_content_ready": int(snapshot.frame_content_ready),
                        "frame_quality_reason": snapshot.frame_quality_reason,
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
            current_node_signals = load_node_runtime_signals(args.node_status_file)
            current_gimbal_signals = load_gimbal_signals(args.node_status_file)
            vision_reporter.update(current_state)
            pending_window_s = max(0.0, float(args.policy_capture_pending_window_s))
            if pending_window_s > 0:
                pending_policy_captures = [
                    item
                    for item in pending_policy_captures
                    if (now - float(item.get("queued_at_s", now))) <= pending_window_s
                ]
            else:
                pending_policy_captures = []

            if bool(args.policy_capture_enable):
                policy_triggers: list[tuple[str, str]] = []
                if (
                    bool(args.policy_capture_high_risk_enter)
                    and (not is_high_risk_level(last_node_signals.risk_level))
                    and is_high_risk_level(current_node_signals.risk_level)
                ):
                    policy_triggers.append(
                        (
                            "AUTO_HIGH_RISK_ENTER",
                            select_policy_event_id(runtime_event_id, current_node_signals, last_node_signals.event_id),
                        )
                    )
                if (
                    bool(args.policy_capture_event_open)
                    and last_node_signals.event_active == 0
                    and current_node_signals.event_active == 1
                ):
                    policy_triggers.append(
                        (
                            "AUTO_EVENT_OPENED",
                            select_policy_event_id(runtime_event_id, current_node_signals, last_node_signals.event_id),
                        )
                    )
                if (
                    bool(args.policy_capture_event_close)
                    and last_node_signals.event_active == 1
                    and current_node_signals.event_active == 0
                ):
                    policy_triggers.append(
                        (
                            "AUTO_EVENT_CLOSED",
                            select_policy_event_id(runtime_event_id, current_node_signals, last_node_signals.event_id),
                        )
                    )

                for capture_reason, policy_event_id in policy_triggers:
                    normalized_policy_event_id = normalize_event_id(policy_event_id)
                    already_queued = any(
                        str(item.get("capture_reason", "")) == capture_reason
                        and normalize_event_id(item.get("event_id", "NONE")) == normalized_policy_event_id
                        for item in pending_policy_captures
                    )
                    if already_queued:
                        continue
                    pending_policy_captures.append(
                        {
                            "capture_reason": capture_reason,
                            "event_id": normalized_policy_event_id,
                            "queued_at_s": now,
                        }
                    )
                    append_session_event(
                        load_json_payload(args.session_file),
                        args.session_log_dir,
                        source="vision_bridge",
                        event_type="capture_policy_queued",
                        payload={
                            "capture_reason": capture_reason,
                            "event_id": normalized_policy_event_id,
                            "risk_level": current_node_signals.risk_level,
                            "event_active": current_node_signals.event_active,
                        },
                    )

            last_node_signals = current_node_signals
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

            captured_this_frame = False
            cooldown_ready = (now - last_auto_capture_time) >= args.capture_cooldown
            if (
                bool(args.policy_capture_enable)
                and snapshot.vision_locked
                and cooldown_ready
                and pending_policy_captures
            ):
                policy_item = pending_policy_captures.pop(0)
                policy_capture_reason = str(policy_item.get("capture_reason", "AUTO_POLICY") or "AUTO_POLICY")
                policy_event_id = normalize_event_id(policy_item.get("event_id", runtime_event_id))
                capture_index += 1
                record = capture_if_allowed(
                    cv=cv,
                    frame=frame,
                    snapshot=snapshot,
                    capture_dir=args.capture_dir,
                    event_id=policy_event_id,
                    capture_reason=policy_capture_reason,
                    capture_index=capture_index,
                    metadata_logger=capture_metadata_logger,
                )
                if record is None:
                    print("Policy capture rejected by frame-quality guard or image write failed.", file=sys.stderr)
                else:
                    last_auto_capture_time = now
                    last_capture_record = record
                    captured_this_frame = True
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

            is_new_lock = snapshot.vision_locked and last_state != VISION_LOCKED
            cooldown_ready = (now - last_auto_capture_time) >= args.capture_cooldown
            if (not captured_this_frame) and is_new_lock and cooldown_ready:
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
                    print("Auto capture rejected by frame-quality guard or image write failed.", file=sys.stderr)
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
            display = draw_guide_box(
                cv,
                display,
                current_gimbal_signals,
                frame_w=source_width or display.shape[1],
                frame_h=source_height or display.shape[0],
            )
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
                lock_source = "NONE"
                auto_lock_score = 0.0
                auto_lock_class_name = "none"
                auto_lock_candidate = None
                auto_lock_candidate_count = 0
                last_auto_lock_attempt_time = now
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
                    print("Capture rejected by frame-quality guard or image write failed.", file=sys.stderr)
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
                if not frame_quality.ready:
                    print(
                        f"Manual lock ignored: frame_quality={frame_quality.reason}, "
                        f"mean_luma={frame_quality.mean_luma:.3f}, luma_stddev={frame_quality.luma_stddev:.3f}",
                        file=sys.stderr,
                    )
                    last_state = current_state
                    continue
                current_state = VISION_SEARCHING
                snapshot = build_snapshot(
                    frame_index=frame_index,
                    state=current_state,
                    locked=False,
                    bbox=current_bbox,
                    tracker_name=active_tracker_name,
                    frame_width=int(frame.shape[1]),
                    frame_height=int(frame.shape[0]),
                    lock_source="MANUAL_PENDING",
                    frame_quality=frame_quality,
                )
                snapshot.detector_state, snapshot.yolo_detections, _ = sidecar_detector.latest()
                snapshot.detector_model_label, snapshot.detector_class_strategy = sidecar_detector.metadata()
                print_snapshot(snapshot)
                tracker, current_bbox = select_target_roi(cv, frame, active_tracker_name)
                if tracker is not None and current_bbox is not None:
                    current_state = VISION_LOCKED
                    lock_source = "MANUAL_ROI"
                else:
                    current_state = VISION_IDLE
                    lock_source = "NONE"
                auto_lock_score = 0.0
                auto_lock_class_name = "none"
                auto_lock_candidate = None
                auto_lock_candidate_count = 0
                last_auto_lock_attempt_time = now
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

