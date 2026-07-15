from __future__ import annotations

import csv
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import cv2 as cv
import numpy as np

import collect_drone_dataset as dataset_collector
import field_collection_preflight
import field_evidence_gate
import field_trial_recorder
import firmware_safety_checks as firmware_safety
import multirotor_classifier_验证 as multirotor_classifier
import node_a_serial_command_NodeA串口命令 as node_command
import node_a_serial_bridge_NodeA串口桥接 as node_bridge
import single_node_evidence_closure_check_单节点证据闭环核对 as closure
import startup_helper_411_单节点启动助手 as startup_helper
import usb_camera_readiness_check_USB摄像头就绪核对 as readiness
import vision_bridge_视觉桥接 as bridge
import vision_web_server_视觉网页服务 as web_server


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_textured_frame(width: int = 160, height: int = 120) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, : width // 2] = (35, 80, 140)
    frame[:, width // 2 :] = (210, 170, 80)
    cv.rectangle(frame, (35, 25), (110, 90), (240, 240, 240), -1)
    cv.circle(frame, (80, 60), 18, (20, 20, 20), -1)
    return frame


def check_frame_quality() -> None:
    black = np.zeros((120, 160, 3), dtype=np.uint8)
    white = np.full((120, 160, 3), 255, dtype=np.uint8)
    flat = np.full((120, 160, 3), 128, dtype=np.uint8)
    textured = build_textured_frame()

    require(bridge.evaluate_frame_quality(cv, black).reason == "FRAME_TOO_DARK", "black frame was accepted")
    require(bridge.evaluate_frame_quality(cv, white).reason == "FRAME_TOO_BRIGHT", "white frame was accepted")
    require(bridge.evaluate_frame_quality(cv, flat).reason == "FRAME_TOO_FLAT", "flat frame was accepted")
    require(bridge.evaluate_frame_quality(cv, textured).ready, "textured frame was rejected")

    readiness_quality = readiness.evaluate_frame_quality(cv, textured)
    require(bool(readiness_quality["ready"]), "readiness checker rejected a valid frame")
    require(
        readiness.evaluate_frame_quality(cv, black)["reason"] == "FRAME_TOO_DARK",
        "readiness checker accepted a black frame",
    )


def check_one_class_yolo_decode() -> None:
    output = np.zeros((1, 5, 10), dtype=np.float32)
    output[0, :, 0] = np.array([320.0, 240.0, 96.0, 64.0, 0.91], dtype=np.float32)
    output[0, :, 1] = np.array([110.0, 90.0, 48.0, 32.0, 0.82], dtype=np.float32)
    output[0, :, 2] = np.array([500.0, 400.0, 80.0, 50.0, 0.20], dtype=np.float32)

    detections = bridge.decode_yolo_predictions(
        cv=cv,
        np=np,
        raw_output=output,
        frame_width=640,
        frame_height=480,
        input_size=640,
        class_ids=[0],
        class_names={0: "drone"},
        score_threshold=0.45,
    )
    require(len(detections) == 2, f"expected 2 one-class detections, got {len(detections)}")
    require(all(item["class_name"] == "drone" for item in detections), "one-class mapping was lost")
    require(max(float(item["score"]) for item in detections) >= 0.90, "high-confidence detection was lost")

    row_major = np.transpose(output, (0, 2, 1))
    row_major_detections = bridge.decode_yolo_predictions(
        cv=cv,
        np=np,
        raw_output=row_major,
        frame_width=640,
        frame_height=480,
        input_size=640,
        class_ids=[0],
        class_names={0: "drone"},
        score_threshold=0.45,
    )
    require(len(row_major_detections) == 2, "row-major YOLO output was decoded differently")


def check_yolo_letterbox_decode() -> None:
    require(
        abs(bridge.DEFAULT_YOLO_SCORE_THRESHOLD - 0.45) < 1e-6,
        "deployed YOLO score threshold no longer matches V4b acceptance",
    )
    require(
        bridge.DEFAULT_YOLO_INTRA_OP_THREADS == 8,
        "deployed ONNX thread count no longer matches sustained-latency acceptance",
    )
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    blob, scale_x, scale_y, pad_x, pad_y = bridge.prepare_yolo_letterbox_input(
        cv=cv,
        np=np,
        frame=frame,
        input_size=640,
    )
    require(blob.shape == (1, 3, 640, 640), f"unexpected letterbox blob shape: {blob.shape}")
    require(abs(scale_x - 0.5) < 1e-6 and abs(scale_y - 0.5) < 1e-6, "letterbox scale is wrong")
    require(pad_x == 0 and pad_y == 140, f"letterbox padding is wrong: ({pad_x}, {pad_y})")
    require(abs(float(blob[0, 0, 0, 0]) - 114.0 / 255.0) < 1e-6, "letterbox fill value is wrong")

    output = np.zeros((1, 5, 10), dtype=np.float32)
    output[0, :, 0] = np.array([210.0, 255.0, 100.0, 50.0, 0.93], dtype=np.float32)
    detections = bridge.decode_yolo_predictions(
        cv=cv,
        np=np,
        raw_output=output,
        frame_width=1280,
        frame_height=720,
        input_size=640,
        class_ids=[0],
        class_names={0: "drone"},
        score_threshold=0.45,
        input_scale_x=scale_x,
        input_scale_y=scale_y,
        input_pad_x=pad_x,
        input_pad_y=pad_y,
    )
    require(len(detections) == 1, f"expected 1 letterbox detection, got {len(detections)}")
    detection = detections[0]
    actual_bbox = (
        int(detection["bbox_x"]),
        int(detection["bbox_y"]),
        int(detection["bbox_w"]),
        int(detection["bbox_h"]),
    )
    expected_bbox = (320, 180, 200, 100)
    require(
        all(abs(actual - expected) <= 1 for actual, expected in zip(actual_bbox, expected_bbox)),
        f"letterbox bbox mapping is wrong: expected {expected_bbox}, got {actual_bbox}",
    )


def check_auto_lock_candidate() -> None:
    detections = [
        {"bbox_x": 10, "bbox_y": 10, "bbox_w": 12, "bbox_h": 12, "score": 0.50, "class_name": "drone"},
        {"bbox_x": 60, "bbox_y": 30, "bbox_w": 40, "bbox_h": 24, "score": 0.88, "class_name": "drone"},
    ]
    first = bridge.select_auto_lock_detection(detections, 160, 120, min_score=0.45, margin_ratio=0.10)
    require(first is not None and first.score == 0.88, "auto-lock did not select the best detection")
    require(first is not None and first.bbox[0] < 60 and first.bbox[2] > 40, "auto-lock context margin was not added")

    wide = bridge.select_auto_lock_detection(
        [{"bbox_x": 9, "bbox_y": 67, "bbox_w": 587, "bbox_h": 212, "score": 0.81, "class_name": "drone"}],
        620,
        464,
        min_score=0.45,
        margin_ratio=0.12,
    )
    require(wide is not None, "wide YOLO detection was discarded")
    require(
        wide is not None and wide.bbox[0] >= 1 and wide.bbox[0] + wide.bbox[2] <= 619,
        "wide YOLO bbox touched the MIL-unsafe frame boundary",
    )

    candidate, count = bridge.update_auto_lock_candidate(None, 0, first, 0.25)
    require(candidate is not None and count == 1, "first auto-lock confirmation was not recorded")
    shifted = bridge.AutoLockDetection(
        bbox=(candidate.bbox[0] + 2, candidate.bbox[1] + 1, candidate.bbox[2], candidate.bbox[3]),
        score=0.90,
        class_name="drone",
    )
    candidate, count = bridge.update_auto_lock_candidate(candidate, count, shifted, 0.25)
    require(count == 2, "stable auto-lock target did not reach two confirmations")
    require(bridge.bbox_iou(shifted.bbox, shifted.bbox) == 1.0, "bbox IoU identity failed")


def check_tracker_and_capture_guard() -> None:
    frame = build_textured_frame()
    trackers = bridge.list_available_trackers(cv)
    require(bool(trackers), "no OpenCV tracker is available")
    tracker, bbox = bridge.initialize_tracker_from_bbox(cv, frame, trackers[0], (35, 25, 75, 65))
    require(tracker is not None and bbox is not None, "tracker could not initialize from an automatic bbox")

    valid_quality = bridge.evaluate_frame_quality(cv, frame)
    black = np.zeros_like(frame)
    black_quality = bridge.evaluate_frame_quality(cv, black)
    valid_snapshot = bridge.build_snapshot(
        frame_index=1,
        state=bridge.VISION_LOCKED,
        locked=True,
        bbox=(35, 25, 75, 65),
        tracker_name=trackers[0],
        frame_width=frame.shape[1],
        frame_height=frame.shape[0],
        lock_source="YOLO_AUTO",
        auto_lock_score=0.88,
        auto_lock_class_name="drone",
        frame_quality=valid_quality,
    )
    black_snapshot = bridge.build_snapshot(
        frame_index=2,
        state=bridge.VISION_LOCKED,
        locked=True,
        bbox=(0, 0, frame.shape[1], frame.shape[0]),
        tracker_name=trackers[0],
        frame_width=frame.shape[1],
        frame_height=frame.shape[0],
        lock_source="YOLO_AUTO",
        frame_quality=black_quality,
    )

    with tempfile.TemporaryDirectory(prefix="flytotal-vision-check-") as temp_dir:
        capture_dir = Path(temp_dir)
        rejected = bridge.capture_if_allowed(
            cv=cv,
            frame=black,
            snapshot=black_snapshot,
            capture_dir=capture_dir,
            event_id="A1-TEST-BLACK",
            capture_reason="REGRESSION_BLACK",
            capture_index=1,
            metadata_logger=None,
        )
        require(rejected is None and not list(capture_dir.glob("*.jpg")), "black evidence image was written")

        accepted = bridge.capture_if_allowed(
            cv=cv,
            frame=frame,
            snapshot=valid_snapshot,
            capture_dir=capture_dir,
            event_id="A1-TEST-VALID",
            capture_reason="REGRESSION_VALID",
            capture_index=2,
            metadata_logger=None,
        )
        require(accepted is not None and Path(accepted.file_path).is_file(), "valid evidence image was not written")


def check_detector_revision() -> None:
    detector = bridge.SidecarDetector(
        cv=cv,
        enabled=False,
        model_path=Path("missing.onnx"),
        every_n_frames=10,
        class_ids=[0],
        class_names={0: "drone"},
        model_label="test",
        score_threshold=0.25,
    )
    _, _, before = detector.latest()
    detector._set_latest("READY_ONNX", [{"score": 0.9}])
    state, detections, after = detector.latest()
    require(state == "READY_ONNX" and len(detections) == 1, "detector state snapshot failed")
    require(after == before + 1, "detector revision did not advance")
    require(detector.intra_op_threads >= 1, "detector ONNX thread count was not normalized")


def check_stale_event_binding_guard() -> None:
    with tempfile.TemporaryDirectory(prefix="flytotal-event-binding-") as temp_dir:
        root = Path(temp_dir)
        node_status = root / "node_status.json"
        node_events = root / "node_events.json"
        event_store = root / "event_store.json"
        active_event = root / "active_event.json"
        node_status.write_text(
            json.dumps(
                {
                    "event_id": "A1-STALE-EVENT",
                    "last_event_id": "A1-STALE-EVENT",
                    "last_update_ms": int(time.time() * 1000) - 600_000,
                }
            ),
            encoding="utf-8",
        )
        node_events.write_text('{"records": []}', encoding="utf-8")
        event_store.write_text('{"records": []}', encoding="utf-8")
        active_event.write_text('{"event_id": "NONE"}', encoding="utf-8")

        event_id, source = bridge.resolve_runtime_event_id(
            "",
            active_event,
            node_status,
            node_events,
            event_store,
            event_bind_max_age_ms=300_000,
            active_event_max_age_ms=15_000,
        )
        require(event_id == "NONE" and source == "none", "stale node status was bound to new evidence")

        fresh_payload = {
            "event_id": "A1-FRESH-EVENT",
            "last_update_ms": int(time.time() * 1000),
        }
        node_status.write_text(json.dumps(fresh_payload), encoding="utf-8")
        event_id, source = bridge.resolve_runtime_event_id(
            "",
            active_event,
            node_status,
            node_events,
            event_store,
            event_bind_max_age_ms=300_000,
            active_event_max_age_ms=15_000,
        )
        require(
            event_id == "A1-FRESH-EVENT" and source == "node_status.event_id",
            "fresh node event was not bound",
        )


def check_field_collector_status_freshness() -> None:
    require(
        dataset_collector.DEFAULT_STATUS_FILE.name == "latest_node_status.json",
        "field collector still defaults to the retired Node A status file",
    )

    with tempfile.TemporaryDirectory(prefix="flytotal-field-collector-") as temp_dir:
        status_file = Path(temp_dir) / "node_status.json"
        status_file.write_text("{}", encoding="utf-8")
        now_ms = int(time.time() * 1000)
        os.utime(status_file, (now_ms / 1000.0, now_ms / 1000.0))

        fresh_status = {
            "ok": True,
            "available": True,
            "online": 1,
            "stale_age_ms": 100,
            "last_update_ms": now_ms - 100,
        }
        accepted, fresh_age_ms, reason = dataset_collector.status_is_collectible(
            fresh_status,
            status_file,
            max_stale_ms=3000,
            now_ms=now_ms,
        )
        require(accepted and reason == "OK", "fresh online Node A status was rejected")
        require(100 <= fresh_age_ms <= 200, "fresh Node A status age was computed incorrectly")

        frozen_host_status = dict(fresh_status)
        frozen_host_status["stale_age_ms"] = 0
        frozen_host_status["last_update_ms"] = now_ms - 5000
        accepted, frozen_host_age_ms, reason = dataset_collector.status_is_collectible(
            frozen_host_status,
            status_file,
            max_stale_ms=3000,
            now_ms=now_ms,
        )
        require(not accepted and reason == "STALE", "frozen host update was accepted")
        require(frozen_host_age_ms >= 5000, "host update age was not included in the gate")

        frozen_file_status = dict(fresh_status)
        frozen_file_status["last_update_ms"] = 0
        frozen_file_status["stale_age_ms"] = 250
        old_file_ms = now_ms - 4000
        os.utime(status_file, (old_file_ms / 1000.0, old_file_ms / 1000.0))
        accepted, frozen_file_age_ms, reason = dataset_collector.status_is_collectible(
            frozen_file_status,
            status_file,
            max_stale_ms=3000,
            now_ms=now_ms,
        )
        require(not accepted and reason == "STALE", "frozen status file was accepted")
        require(frozen_file_age_ms >= 4250, "reported and elapsed status ages were not combined")

        offline_status = dict(fresh_status)
        offline_status["online"] = 0
        accepted, _, reason = dataset_collector.status_is_collectible(
            offline_status,
            status_file,
            max_stale_ms=3000,
            now_ms=now_ms,
        )
        require(not accepted and reason == "OFFLINE", "offline Node A status was accepted")

        accepted, _, reason = dataset_collector.status_is_collectible(
            offline_status,
            status_file,
            max_stale_ms=3000,
            allow_stale=True,
            now_ms=now_ms,
        )
        require(accepted and reason == "ALLOW_STALE", "explicit stale-data override stopped working")

        require(
            not dataset_collector.track_is_collectible(
                {"track_active": 1, "track_confirmed": 0},
                active_only=True,
            ),
            "active but unconfirmed track was accepted",
        )
        require(
            not dataset_collector.track_is_collectible(
                {"track_active": 0, "track_confirmed": 1},
                active_only=True,
            ),
            "confirmed flag without an active track was accepted",
        )
        require(
            dataset_collector.track_is_collectible(
                {"track_active": 1, "track_confirmed": 1},
                active_only=True,
            ),
            "active confirmed track was rejected",
        )
        require(
            dataset_collector.track_is_collectible({}, active_only=False),
            "default collection mode unexpectedly required a track",
        )

        output_file = Path(temp_dir) / "real_tracks.csv"
        dataset_collector.append_rows(
            output_file,
            [
                {
                    "timestamp_ms": 0,
                    "track_id": "drone_field_01_t7",
                    "x_mm": 100.0,
                    "y_mm": 900.0,
                    "vx_mm_s": 10.0,
                    "vy_mm_s": 20.0,
                    "label": "drone",
                }
            ],
        )
        output_state, matching_ids = dataset_collector.inspect_existing_output(
            output_file,
            label="drone",
            session_id="field_01",
        )
        require(output_state == "OK", "valid field CSV failed preflight inspection")
        require(matching_ids == {"drone_field_01_t7"}, "existing session id was not detected")

        _, similar_prefix_ids = dataset_collector.inspect_existing_output(
            output_file,
            label="drone",
            session_id="field",
        )
        require(not similar_prefix_ids, "similar session prefix was treated as an exact reuse")
        _, other_label_ids = dataset_collector.inspect_existing_output(
            output_file,
            label="person",
            session_id="field_01",
        )
        require(not other_label_ids, "same session id under another label was rejected")

        fresh_status.update(
            {
                "track_id": 7,
                "track_active": 1,
                "track_confirmed": 1,
                "x_mm": 100.0,
                "y_mm": 900.0,
                "vx_mm_s": 10.0,
                "vy_mm_s": 20.0,
            }
        )
        status_file.write_text(json.dumps(fresh_status), encoding="utf-8")
        os.utime(status_file, (now_ms / 1000.0, now_ms / 1000.0))
        base_args = {
            "status": status_file,
            "output": output_file,
            "label": "drone",
            "duration_s": 0.1,
            "interval_ms": 50,
            "session_id": "field_01",
            "active_only": True,
            "allow_stale": False,
            "max_stale_ms": 3000,
        }
        original_output = output_file.read_bytes()
        require(
            dataset_collector.collect(SimpleNamespace(**base_args, allow_session_reuse=False)) == 3,
            "duplicate field session did not abort",
        )
        require(output_file.read_bytes() == original_output, "duplicate session abort changed the CSV")
        require(
            dataset_collector.collect(SimpleNamespace(**base_args, allow_session_reuse=True)) == 0,
            "explicit field session reuse override did not work",
        )

        invalid_output = Path(temp_dir) / "invalid_tracks.csv"
        invalid_output.write_text("timestamp_ms,wrong_column\n0,bad\n", encoding="utf-8")
        invalid_state, _ = dataset_collector.inspect_existing_output(
            invalid_output,
            label="drone",
            session_id="field_02",
        )
        require(invalid_state == "SCHEMA_MISMATCH", "invalid field CSV schema was accepted")


def check_classifier_real_input_guard() -> None:
    with tempfile.TemporaryDirectory(prefix="flytotal-classifier-input-") as temp_dir:
        empty_input = Path(temp_dir) / "real_tracks.csv"
        empty_input.write_text(
            "timestamp_ms,track_id,x_mm,y_mm,vx_mm_s,vy_mm_s,label\n",
            encoding="utf-8",
        )
        rows, source, error = multirotor_classifier.resolve_input_rows(
            input_path=empty_input,
            use_mock=False,
            label_column="label",
        )
        require(not rows, "empty real input produced classifier rows")
        require(source == empty_input.as_posix(), "empty real input source was changed")
        require(error == "no_real_tracks", "empty real input did not return a hard failure")

        mock_rows, mock_source, mock_error = multirotor_classifier.resolve_input_rows(
            input_path=None,
            use_mock=True,
            label_column="label",
        )
        require(len(mock_rows) == 12, "explicit mock mode lost its synthetic baseline")
        require(mock_source == "mock" and not mock_error, "explicit mock mode was marked as real data")

        output_dir = Path(temp_dir) / "outputs"
        output_dir.mkdir()
        (output_dir / "multirotor_features.png").write_bytes(b"stale-plot")
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(multirotor_classifier.__file__).resolve()),
                "--input",
                str(empty_input),
                "--output-dir",
                str(output_dir),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        require(completed.returncode == 3, "empty real-input CLI did not return its hard-failure code")
        require("ERROR,no_real_tracks" in completed.stdout, "empty real-input CLI hid its failure")
        summary_path = output_dir / "multirotor_classifier_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        require(summary.get("ok") is False, "empty real-input summary reported success")
        require(summary.get("source") == empty_input.as_posix(), "real input was relabeled as mock")
        require(summary.get("row_count") == 0, "empty real input gained synthetic rows")
        require(not list(output_dir.glob("*.png")), "stale classifier plot survived empty-input failure")


def check_field_trial_recorder() -> None:
    samples = [
        {
            "host_timestamp_ms": 1000,
            "sample_valid": True,
            "vision_valid": True,
            "node_valid": True,
            "node_boot_id": "A1-00000001-CAFEBABE",
            "node_reset_reason": "POWERON",
            "node_uptime_ms": 60_000,
            "yolo_auto_locked": False,
            "max_drone_score": 0.30,
            "ld2451_valid": 0,
        },
        {
            "host_timestamp_ms": 1200,
            "sample_valid": True,
            "vision_valid": True,
            "node_valid": True,
            "node_boot_id": "A1-00000001-CAFEBABE",
            "node_reset_reason": "POWERON",
            "node_uptime_ms": 60_200,
            "yolo_auto_locked": True,
            "max_drone_score": 0.88,
            "track_active": 1,
            "track_confirmed": 1,
            "event_active": 1,
            "event_id": "A1-REAL-FUSION-0001",
            "test_mode_enabled": 0,
            "fusion_enabled": 1,
            "fusion_level": "HIGH",
            "fusion_stage": "NEAR",
            "fusion_confidence": 0.82,
            "fusion_reason": "NEAR_VISUAL_CONFIRMED",
            "physical_fusion": True,
            "ld2451_valid": 1,
            "ld2451_range_m": 10.2,
        },
        {
            "host_timestamp_ms": 1400,
            "sample_valid": True,
            "vision_valid": True,
            "node_valid": True,
            "node_boot_id": "A1-00000001-CAFEBABE",
            "node_reset_reason": "POWERON",
            "node_uptime_ms": 60_400,
            "yolo_auto_locked": True,
            "max_drone_score": 0.91,
            "ld2451_valid": 1,
            "ld2451_range_m": 10.1,
        },
    ]
    drone_summary = field_trial_recorder.summarize_samples(
        samples,
        target="drone",
        expected_model_label="drone-v4b-hardneg-deployed",
        observed_model_labels={"drone-v4b-hardneg-deployed"},
        min_valid_ratio=0.80,
    )
    require(drone_summary["trial_valid"], "valid field trial was rejected")
    require(drone_summary["performance_pass"], "detected drone trial did not pass performance")
    require(drone_summary["outcome"] == "DETECTED", "drone auto-lock was not counted")
    require(drone_summary["max_drone_score"] == 0.91, "field maximum score is wrong")
    require(drone_summary["lock_episode_count"] == 1, "continuous lock was split incorrectly")
    require(drone_summary["longest_lock_duration_ms"] == 200, "lock duration is wrong")
    require(drone_summary["physical_fusion_sample_count"] == 1, "physical fusion sample was lost")
    require(drone_summary["node_boot_session_valid"], "stable node boot session was rejected")
    require(
        drone_summary["node_boot_ids"] == ["A1-00000001-CAFEBABE"],
        "node boot id was not persisted",
    )
    require(
        drone_summary["physical_fusion_event_ids"] == ["A1-REAL-FUSION-0001"],
        "physical fusion event binding is wrong",
    )

    reset_samples = json.loads(json.dumps(samples))
    reset_samples[-1]["node_boot_id"] = "A1-00000002-DEADBEEF"
    reset_samples[-1]["node_reset_reason"] = "TASK_WDT"
    reset_samples[-1]["node_uptime_ms"] = 500
    reset_summary = field_trial_recorder.summarize_samples(
        reset_samples,
        target="drone",
        expected_model_label="drone-v4b-hardneg-deployed",
        observed_model_labels={"drone-v4b-hardneg-deployed"},
        min_valid_ratio=0.80,
    )
    require(reset_summary["node_reset_observed"], "mid-trial node reset was not detected")
    require(not reset_summary["node_boot_session_valid"], "mixed node boot ids were accepted")
    require(not reset_summary["trial_valid"], "mid-trial node reset did not invalidate the trial")

    negative_summary = field_trial_recorder.summarize_samples(
        samples,
        target="person",
        expected_model_label="drone-v4b-hardneg-deployed",
        observed_model_labels={"drone-v4b-hardneg-deployed"},
        min_valid_ratio=0.80,
    )
    require(negative_summary["outcome"] == "FALSE_LOCK", "negative false lock was hidden")
    require(not negative_summary["performance_pass"], "negative false lock passed performance")

    invalid_frame_sample = field_trial_recorder.build_sample(
        host_timestamp_ms=1_800_000_000_000,
        vision={
            "ok": True,
            "available": True,
            "timestamp_ms": 1_800_000_000_000,
            "source_ready": 1,
            "detector_ready": 1,
            "vision_chain_ready": 1,
            "frame_content_ready": 0,
            "frame_quality_reason": "FRAME_TOO_DARK",
            "source": "0",
            "capture_backend": "dshow",
        },
        node={
            "ok": True,
            "available": True,
            "online": 1,
            "last_update_ms": 1_800_000_000_000,
        },
        max_status_age_ms=1000,
    )
    require(not invalid_frame_sample["sample_valid"], "invalid video frame counted as field evidence")

    replay_sample = field_trial_recorder.build_sample(
        host_timestamp_ms=1_800_000_000_000,
        vision={
            "ok": True,
            "available": True,
            "timestamp_ms": 1_800_000_000_000,
            "source_ready": 1,
            "detector_ready": 1,
            "vision_chain_ready": 1,
            "frame_content_ready": 1,
            "frame_quality_reason": "OK",
            "source": "captures/replay.mp4",
        },
        node={
            "ok": True,
            "available": True,
            "online": 1,
            "last_update_ms": 1_800_000_000_000,
        },
        max_status_age_ms=1000,
    )
    require(not replay_sample["sample_valid"], "replay video counted as a real field trial")

    with tempfile.TemporaryDirectory(prefix="flytotal-field-trial-") as temp_dir:
        root = Path(temp_dir)
        output_dir = root / "field_trials"
        video_file = root / "trial.mp4"
        video_file.write_bytes(b"field-video-fixture")
        model_file = root / "yolov8n_drone.onnx"
        model_file.write_bytes(b"deployed-field-model-fixture")
        model_sha256 = hashlib.sha256(model_file.read_bytes()).hexdigest()

        class FakeClock:
            def __init__(self) -> None:
                self.monotonic_s = 0.0
                self.epoch_ms = 1_800_000_000_000

            def monotonic(self) -> float:
                return self.monotonic_s

            def now_ms(self) -> int:
                return self.epoch_ms + int(self.monotonic_s * 1000)

            def sleep(self, seconds: float) -> None:
                self.monotonic_s += seconds

        clock = FakeClock()

        def fetch_fixture(url: str, _timeout_s: float) -> dict[str, object]:
            now_ms = clock.now_ms()
            if url.endswith("/api/status"):
                return {
                    "ok": True,
                    "available": True,
                    "timestamp_ms": now_ms,
                    "source_ready": 1,
                    "detector_ready": 1,
                    "vision_chain_ready": 1,
                    "vision_state": "VISION_LOCKED",
                    "lock_source": "YOLO_AUTO",
                    "auto_lock_class_name": "drone",
                    "auto_lock_score": 0.89,
                    "frame_content_ready": 1,
                    "frame_quality_reason": "OK",
                    "detector_model_label": "drone-v4b-hardneg-deployed",
                    "source": "0",
                    "capture_backend": "dshow",
                    "yolo_detections": [{"class_name": "drone", "score": 0.89}],
                }
            return {
                "ok": True,
                "available": True,
                "online": 1,
                "stale_age_ms": 0,
                "last_update_ms": now_ms,
                "track_active": 1,
                "track_confirmed": 1,
                "track_id": 7,
                "event_active": 1,
                "event_id": "A1-REAL-FUSION-0001",
                "test_mode_enabled": 0,
                "boot_id": "A1-00000001-CAFEBABE",
                "reset_reason": "POWERON",
                "node_uptime_ms": 60_000 + int(clock.monotonic_s * 1000),
                "fusion_enabled": 1,
                "fusion_level": "HIGH",
                "fusion_stage": "NEAR",
                "fusion_confidence": 0.82,
                "fusion_reason": "NEAR_VISUAL_CONFIRMED",
                "ld2451_valid": 1,
                "ld2451_range_m": 10.1,
                "ld2451_speed_mps": 0.4,
                "ld2451_approach": 1,
                "far_motion_trigger": 1,
            }

        args = SimpleNamespace(
            base_url="http://fixture",
            timeout_s=0.1,
            duration_s=0.6,
            interval_ms=200,
            max_status_age_ms=1000,
            min_valid_ratio=0.80,
            session_id="drone_10m_hover_01",
            target="drone",
            distance_m=10.0,
            distance_source="laser",
            action="hover",
            site="field_a",
            weather="clear",
            lighting="daylight",
            video_ref="phone_clip_001",
            video_file=video_file,
            notes="regression",
            model_file=model_file,
            expected_model_sha256=model_sha256,
            expected_model_label="drone-v4b-hardneg-deployed",
            output_dir=output_dir,
        )
        result = field_trial_recorder.record_trial(
            args,
            fetch_json_fn=fetch_fixture,
            monotonic_fn=clock.monotonic,
            now_ms_fn=clock.now_ms,
            sleep_fn=clock.sleep,
        )
        require(result == 0, "valid field trial recorder fixture failed")

        session_dir = output_dir / "drone_10m_hover_01"
        report_path = session_dir / "trial_report.json"
        samples_path = session_dir / "samples.jsonl"
        require(report_path.is_file() and samples_path.is_file(), "field evidence files were not persisted")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        require(report["result"] == "PASS", "field report did not pass")
        require(report["summary"]["outcome"] == "DETECTED", "field report lost the outcome")
        require(report["summary"]["node_boot_session_valid"], "field report lost stable boot proof")
        require(
            report["summary"]["node_boot_ids"] == ["A1-00000001-CAFEBABE"],
            "field report lost the node boot id",
        )
        require(report["video_evidence"]["sha256"], "field video was not hashed")
        require(report["samples_evidence"]["sha256"], "field samples were not hashed")
        require(report["model_evidence"]["state"] == "VERIFIED", "field model was not bound")
        require(report["runtime"]["actual_elapsed_s"] >= 0.6, "actual trial duration was not saved")
        require(report["runtime"]["fsync_interval_s"] == 1.0, "field fsync cadence is wrong")
        require(report["metadata"]["distance_m"] == 10.0, "field distance was not bound")
        require(
            report["summary"]["physical_fusion_sample_count"] == report["summary"]["sample_count"],
            "same-sample physical fusion was not persisted",
        )
        require(
            report["summary"]["physical_fusion_event_ids"] == ["A1-REAL-FUSION-0001"],
            "recorded physical fusion lost the strict event id",
        )
        require(
            field_trial_recorder.record_trial(
                args,
                fetch_json_fn=fetch_fixture,
                monotonic_fn=clock.monotonic,
                now_ms_fn=clock.now_ms,
                sleep_fn=clock.sleep,
            )
            == 3,
            "duplicate field trial session was not rejected",
        )

        wrong_model_args = SimpleNamespace(
            **{
                **vars(args),
                "session_id": "drone_10m_wrong_model_01",
                "expected_model_sha256": "0" * 64,
            }
        )
        require(
            field_trial_recorder.record_trial(
                wrong_model_args,
                fetch_json_fn=fetch_fixture,
                monotonic_fn=clock.monotonic,
                now_ms_fn=clock.now_ms,
                sleep_fn=clock.sleep,
            )
            == 10,
            "wrong field model hash was accepted by the recorder",
        )
        require(
            not (output_dir / "drone_10m_wrong_model_01").exists(),
            "preflight model failure consumed a field session id",
        )

        pending_args = SimpleNamespace(
            **{
                **vars(args),
                "session_id": "person_10m_cross_01",
                "target": "person",
                "action": "cross",
                "video_ref": "phone_clip_002",
                "video_file": None,
            }
        )
        pending_result = field_trial_recorder.record_trial(
            pending_args,
            fetch_json_fn=fetch_fixture,
            monotonic_fn=clock.monotonic,
            now_ms_fn=clock.now_ms,
            sleep_fn=clock.sleep,
        )
        require(pending_result == 7, "missing field video did not keep evidence pending")
        pending_report_path = output_dir / "person_10m_cross_01" / "trial_report.json"
        pending_report = json.loads(pending_report_path.read_text(encoding="utf-8"))
        require(pending_report["summary"]["outcome"] == "FALSE_LOCK", "false lock changed while video was pending")
        require(not pending_report["evidence_complete"], "reference-only video was marked complete")
        require(
            field_trial_recorder.finalize_video(
                SimpleNamespace(
                    finalize_session="person_10m_cross_01",
                    output_dir=output_dir,
                    video_file=video_file,
                )
            )
            == 0,
            "field video finalize failed",
        )
        finalized_report = json.loads(pending_report_path.read_text(encoding="utf-8"))
        require(finalized_report["evidence_complete"], "video finalize did not complete evidence")
        require(
            not finalized_report["summary"]["performance_pass"],
            "video finalize hid the negative false lock",
        )

        failed_args = SimpleNamespace(**{**vars(args), "session_id": "drone_10m_hover_fail_01"})

        def failed_fetch(_url: str, _timeout_s: float) -> dict[str, object]:
            raise OSError("fixture offline")

        failed_result = field_trial_recorder.record_trial(
            failed_args,
            fetch_json_fn=failed_fetch,
            monotonic_fn=clock.monotonic,
            now_ms_fn=clock.now_ms,
            sleep_fn=clock.sleep,
        )
        require(failed_result != 0, "offline field trial was marked successful")
        failed_report = json.loads(
            (output_dir / "drone_10m_hover_fail_01" / "trial_report.json").read_text(encoding="utf-8")
        )
        require(failed_report["result"] == "FAIL", "failed field attempt was not preserved")
        require(failed_report["summary"]["status_interruption_count"] > 0, "status failures were hidden")


def check_field_collection_preflight() -> None:
    with tempfile.TemporaryDirectory(prefix="flytotal-field-preflight-") as temp_dir:
        root = Path(temp_dir)
        model_path = root / "yolov8n_drone.onnx"
        model_path.write_bytes(b"deployed-field-model-fixture")
        expected_hash = field_collection_preflight.sha256_file(model_path)
        now_ms = 1_800_000_000_000
        vision = {
            "ok": True,
            "available": True,
            "timestamp_ms": now_ms,
            "source_ready": 1,
            "detector_ready": 1,
            "vision_chain_ready": 1,
            "frame_content_ready": 1,
            "frame_quality_reason": "OK",
            "detector_model_label": "drone-v4b-hardneg-deployed",
            "detector_class_strategy": "0:drone",
            "active_tracker_name": "MIL",
            "source": "0",
            "capture_backend": "dshow",
        }
        node = {
            "ok": True,
            "available": True,
            "online": 1,
            "stale_age_ms": 0,
            "last_update_ms": now_ms,
            "boot_id": "A1-00000001-CAFEBABE",
            "reset_reason": "POWERON",
            "node_uptime_ms": 60_000,
            "node_boot_last_change_ms": now_ms - 60_000,
            "track_active": 0,
            "event_active": 0,
            "event_id": "NONE",
            "test_mode_enabled": 0,
            "fusion_enabled": 1,
            "fusion_level": "NONE",
            "fusion_stage": "NONE",
            "servo_enabled": 0,
            "cloud_request_in_flight": 0,
            "serial_bridge_contract_version": 2,
            "web_evidence_contract_version": 2,
        }
        report = field_collection_preflight.evaluate_preflight(
            vision,
            node,
            model_path=model_path,
            expected_model_sha256=expected_hash,
            expected_model_label="drone-v4b-hardneg-deployed",
            output_dir=root / "field_trials",
            now_ms=now_ms,
            max_status_age_ms=3000,
            min_free_bytes=2_000_000_000,
            disk_free_bytes=3_000_000_000,
            require_cloud_test=False,
        )
        require(report["result"] == "GO", "complete field collection baseline did not pass")
        require(report["passed_count"] == report["total_count"], "GO report contains failed checks")
        require(report["total_count"] == 17, "distance preflight check count is not 17")

        def failed_check_names(
            vision_overrides: dict[str, object] | None = None,
            node_overrides: dict[str, object] | None = None,
            *,
            model_hash: str = expected_hash,
            disk_free_bytes: int = 3_000_000_000,
        ) -> set[str]:
            candidate_vision = {**vision, **(vision_overrides or {})}
            candidate_node = {**node, **(node_overrides or {})}
            candidate = field_collection_preflight.evaluate_preflight(
                candidate_vision,
                candidate_node,
                model_path=model_path,
                expected_model_sha256=model_hash,
                expected_model_label="drone-v4b-hardneg-deployed",
                output_dir=root / "field_trials",
                now_ms=now_ms,
                max_status_age_ms=3000,
                min_free_bytes=2_000_000_000,
                disk_free_bytes=disk_free_bytes,
                require_cloud_test=False,
            )
            require(candidate["result"] == "NO-GO", "unsafe field baseline was accepted")
            return {str(item["name"]) for item in candidate["checks"] if not item["passed"]}

        require(
            "vision_runtime_fresh" in failed_check_names({"timestamp_ms": now_ms - 5000}),
            "stale field camera was not rejected",
        )
        require(
            "physical_camera_source" in failed_check_names({"source": "captures/replay.mp4"}),
            "replay source was accepted as a physical field camera",
        )
        require(
            "deployed_model_hash" in failed_check_names(model_hash="0" * 64),
            "wrong field model hash was not rejected",
        )
        require(
            "track_idle" in failed_check_names(node_overrides={"track_active": 1}),
            "active simulated/old track was not rejected",
        )
        require(
            "servo_disabled" in failed_check_names(node_overrides={"servo_enabled": 1}),
            "enabled unattended servo was not rejected",
        )
        require(
            "advanced_fusion_enabled" in failed_check_names(node_overrides={"fusion_enabled": 0}),
            "disabled advanced fusion was not rejected before field collection",
        )
        require(
            "node_online_fresh"
            in failed_check_names(
                node_overrides={"boot_id": "", "reset_reason": "UNKNOWN", "node_uptime_ms": 0}
            ),
            "missing node boot telemetry was accepted before field collection",
        )
        require(
            "node_online_fresh"
            in failed_check_names(
                node_overrides={
                    "boot_id": "A1-00000002-DEADBEEF",
                    "reset_reason": "TASK_WDT",
                    "node_uptime_ms": 2_000,
                    "node_boot_last_change_ms": now_ms - 2_000,
                }
            ),
            "freshly reset node was accepted before field collection",
        )
        require(
            "contracts_v2" in failed_check_names(node_overrides={"serial_bridge_contract_version": 1}),
            "legacy evidence contract was not rejected",
        )
        require(
            "disk_free" in failed_check_names(disk_free_bytes=1_000_000),
            "insufficient field evidence disk was not rejected",
        )


def check_field_evidence_gate() -> None:
    def build_report(
        session_id: str,
        *,
        target: str,
        distance_m: float,
        outcome: str,
        trial_kind: str = "distance",
        duration_s: float = 12.0,
        interruptions: int = 0,
    ) -> dict[str, object]:
        performance_pass = outcome in {"DETECTED", "CLEAR"}
        sample_count = max(1, int(duration_s * 5))
        started_ms = 1_800_000_000_000
        return {
            "schema_version": 1,
            "result": "PASS",
            "evidence_complete": True,
            "started_ms": started_ms,
            "ended_ms": started_ms + int(duration_s * 1000),
            "metadata": {
                "session_id": session_id,
                "trial_kind": trial_kind,
                "target": target,
                "distance_m": distance_m,
                "distance_source": "laser" if distance_m > 0 else "not_measured",
                "action": "static_site" if target == "clutter" else "normal_traffic" if trial_kind == "long_stability" else "cross",
                "site": "field_a",
                "weather": "clear",
                "lighting": "daylight",
                "video_ref": f"phone_{session_id}",
            },
            "runtime": {
                "duration_s": duration_s,
                "actual_elapsed_s": duration_s,
                "interval_ms": 200,
            },
            "summary": {
                "trial_valid": True,
                "performance_pass": performance_pass,
                "outcome": outcome,
                "sample_count": sample_count,
                "valid_sample_count": sample_count - interruptions,
                "status_interruption_count": interruptions,
                "node_boot_session_valid": True,
                "node_reset_observed": False,
                "node_uptime_regression_observed": False,
                "node_boot_ids": ["A1-00000001-CAFEBABE"],
                "node_reset_reasons": ["POWERON"],
                "node_boot_telemetry_sample_count": sample_count,
                "physical_camera_sample_count": sample_count,
                "model_label_ok": True,
                "expected_model_label": field_trial_recorder.DEFAULT_MODEL_LABEL,
                "observed_model_labels": [field_trial_recorder.DEFAULT_MODEL_LABEL],
            },
            "model_evidence": {
                "state": "VERIFIED",
                "expected_sha256": field_trial_recorder.DEFAULT_MODEL_SHA256,
                "actual_sha256": field_trial_recorder.DEFAULT_MODEL_SHA256,
            },
            "samples_evidence": {
                "sha256": hashlib.sha256((session_id + "-samples").encode()).hexdigest(),
            },
            "video_evidence": {
                "state": "VERIFIED",
                "reference": f"phone_{session_id}",
                "sha256": hashlib.sha256((session_id + "-video").encode()).hexdigest(),
            },
        }

    reports: list[dict[str, object]] = []
    for target in ("drone", "person", "car"):
        for distance_m in (10.0, 30.0, 50.0):
            for trial_index in range(1, 4):
                session_id = f"{target}_{int(distance_m)}m_{trial_index:02d}"
                reports.append(
                    build_report(
                        session_id,
                        target=target,
                        distance_m=distance_m,
                        outcome="DETECTED" if target == "drone" else "CLEAR",
                    )
                )
    reports[0]["summary"].update(
        {
            "physical_fusion_sample_count": 1,
            "physical_fusion_event_ids": ["A1-FIELD-MISSION-0001"],
        }
    )
    reports.append(
        build_report(
            "stability_static_20m_01",
            target="clutter",
            distance_m=0.0,
            outcome="CLEAR",
            trial_kind="long_stability",
            duration_s=1200.0,
        )
    )
    reports.append(
        build_report(
            "stability_traffic_20m_01",
            target="person",
            distance_m=0.0,
            outcome="CLEAR",
            trial_kind="long_stability",
            duration_s=1200.0,
        )
    )

    passed = field_evidence_gate.evaluate_evidence_reports(reports, trials_per_cell=3)
    require(passed["result"] == "GO", "complete real-drone field matrix did not pass")
    require(passed["distance_trial_count"] == 27, "distance matrix count is wrong")
    require(passed["long_stability_count"] == 2, "long-stability count is wrong")
    require(passed["remaining_distance_trial_count"] == 0, "complete matrix still has missing trials")
    require(not passed["next_actions"], "complete field evidence still has next actions")

    mission_preflight_ms = 1_799_999_999_000
    mission_preflight = {
        "result": "GO",
        "mode": "same-event",
        "generated_ms": mission_preflight_ms,
        "passed_count": 18,
        "total_count": 18,
        "failures": [],
        "checks": [
            {"name": "physical_camera_source", "passed": True},
            {"name": "deployed_model_hash", "passed": True},
            {"name": "cloud_test_32_of_32", "passed": True},
        ],
    }
    strict_event_id = "A1-FIELD-MISSION-0001"
    mission_strict = {
        "result": "PASS",
        "checked_ms": 1_800_000_005_000,
        "latest_event_id": strict_event_id,
        "counts": {
            "national_first_checks_passed": 15,
            "national_first_checks_total": 15,
            "strict_export_snapshot_checks_passed": 15,
            "strict_export_snapshot_checks_total": 15,
        },
        "national_first_evidence": {
            "result": "PASS",
            "expected_event_id": strict_event_id,
            "actual_event_id": strict_event_id,
            "passed_count": 15,
            "total_count": 15,
            "source": "0",
            "physical_camera_source": 1,
            "detector_model_label": field_trial_recorder.DEFAULT_MODEL_LABEL,
        },
        "national_first_event_freshness": {
            "result": "PASS",
            "event_timestamp_ms": 1_800_000_003_000,
        },
        "strict_export_snapshot_evidence": {
            "result": "PASS",
            "expected_event_id": strict_event_id,
            "actual_event_id": strict_event_id,
            "passed_count": 15,
            "total_count": 15,
            "source": "0",
            "physical_camera_source": 1,
            "detector_model_label": field_trial_recorder.DEFAULT_MODEL_LABEL,
        },
    }
    mission_passed = field_evidence_gate.evaluate_mission_final(
        passed,
        reports,
        preflight_report=mission_preflight,
        strict_closure_report=mission_strict,
        max_mission_duration_s=8 * 60 * 60,
    )
    require(mission_passed["result"] == "GO", "complete same-field mission did not pass")
    require(
        mission_passed["passed_count"] == 26 and mission_passed["total_count"] == 26,
        "mission-final gate is not 26/26",
    )

    with tempfile.TemporaryDirectory(prefix="flytotal-field-mission-cli-") as temp_dir:
        root = Path(temp_dir)
        input_dir = root / "field_trials"
        for report in reports:
            session_dir = input_dir / str(report["metadata"]["session_id"])
            session_dir.mkdir(parents=True)
            (session_dir / "trial_report.json").write_text(
                json.dumps(report),
                encoding="utf-8",
            )
        preflight_file = root / "preflight.json"
        strict_file = root / "strict.json"
        final_report_file = root / "mission_final.json"
        preflight_file.write_text(json.dumps(mission_preflight), encoding="utf-8")
        strict_file.write_text(json.dumps(mission_strict), encoding="utf-8")
        original_argv = sys.argv
        try:
            sys.argv = [
                str(Path(field_evidence_gate.__file__)),
                "--mode",
                "mission-final",
                "--input-dir",
                str(input_dir),
                "--preflight-report",
                str(preflight_file),
                "--strict-closure-report",
                str(strict_file),
                "--report-file",
                str(final_report_file),
            ]
            require(field_evidence_gate.main() == 0, "mission-final CLI rejected complete evidence")
        finally:
            sys.argv = original_argv
        cli_final = json.loads(final_report_file.read_text(encoding="utf-8"))
        require(cli_final["result"] == "GO", "mission-final CLI report did not pass")
        require(cli_final["passed_count"] == 26, "mission-final CLI report lost checks")

    def failed_mission_names(
        candidate_preflight: dict[str, object],
        candidate_strict: dict[str, object],
        candidate_reports: list[dict[str, object]] = reports,
    ) -> set[str]:
        matrix_result = field_evidence_gate.evaluate_evidence_reports(
            candidate_reports,
            trials_per_cell=3,
        )
        result = field_evidence_gate.evaluate_mission_final(
            matrix_result,
            candidate_reports,
            preflight_report=candidate_preflight,
            strict_closure_report=candidate_strict,
            max_mission_duration_s=8 * 60 * 60,
        )
        require(result["result"] == "NO-GO", "invalid field mission was accepted")
        return {str(item["name"]) for item in result["checks"] if not item["passed"]}

    no_physical_fusion = copy.deepcopy(reports)
    for report in no_physical_fusion:
        report["summary"]["physical_fusion_sample_count"] = 0
    require(
        "real_sensor_fusion_evidence" in failed_mission_names(
            mission_preflight,
            mission_strict,
            no_physical_fusion,
        ),
        "mission-final accepted visual/cloud evidence without physical sensor fusion",
    )

    replay_strict = copy.deepcopy(mission_strict)
    for key in ("national_first_evidence", "strict_export_snapshot_evidence"):
        replay_strict[key].update(
            {
                "source": "captures/replay_sources/field_fixture.mp4",
                "physical_camera_source": 0,
            }
        )
    require(
        "real_event_strict_15_of_15" in failed_mission_names(mission_preflight, replay_strict),
        "replay strict closure passed mission-final",
    )

    distance_only_preflight = copy.deepcopy(mission_preflight)
    distance_only_preflight["mode"] = "distance"
    require(
        "same_event_preflight_go" in failed_mission_names(distance_only_preflight, mission_strict),
        "distance-only preflight passed mission-final",
    )

    out_of_window_reports = copy.deepcopy(reports)
    out_of_window_reports[0]["started_ms"] = mission_preflight_ms - 1000
    out_of_window_reports[0]["ended_ms"] = mission_preflight_ms - 500
    require(
        "single_field_mission_time_window" in failed_mission_names(
            mission_preflight,
            mission_strict,
            out_of_window_reports,
        ),
        "old field report was combined into the current mission",
    )

    def failed_names(candidate_reports: list[dict[str, object]]) -> set[str]:
        result = field_evidence_gate.evaluate_evidence_reports(candidate_reports, trials_per_cell=3)
        require(result["result"] == "NO-GO", "incomplete field evidence was accepted")
        return {str(item["name"]) for item in result["checks"] if not item["passed"]}

    missing = copy.deepcopy(reports)
    missing.pop(0)
    require("matrix_drone_10m" in failed_names(missing), "missing distance trial was not rejected")

    reused_video = copy.deepcopy(reports)
    reused_video[1]["video_evidence"]["sha256"] = reused_video[0]["video_evidence"]["sha256"]
    require(
        "independent_video_hashes" in failed_names(reused_video),
        "reused field video was not rejected",
    )

    wrong_model = copy.deepcopy(reports)
    wrong_model[0]["model_evidence"]["actual_sha256"] = "0" * 64
    wrong_model_result = field_evidence_gate.evaluate_evidence_reports(wrong_model, trials_per_cell=3)
    require(wrong_model_result["result"] == "NO-GO", "wrong model field evidence passed")
    require(
        "official_model_hash_not_bound" in wrong_model_result["invalid_reports"][0]["reasons"],
        "wrong model evidence reason was hidden",
    )

    reset_trial = copy.deepcopy(reports)
    reset_trial[0]["summary"].update(
        {
            "node_boot_session_valid": False,
            "node_reset_observed": True,
            "node_boot_ids": ["A1-00000001-CAFEBABE", "A1-00000002-DEADBEEF"],
        }
    )
    reset_result = field_evidence_gate.evaluate_evidence_reports(reset_trial, trials_per_cell=3)
    require(reset_result["result"] == "NO-GO", "mid-trial reset evidence passed the matrix gate")
    require(
        "node_boot_session_invalid" in reset_result["invalid_reports"][0]["reasons"],
        "mid-trial reset rejection reason was hidden",
    )

    drone_10m_miss = copy.deepcopy(reports)
    drone_10m_miss[0]["summary"].update({"outcome": "MISSED", "performance_pass": False})
    require(
        "performance_drone_10m" in failed_names(drone_10m_miss),
        "10 m drone miss was accepted",
    )

    drone_10m_extra_miss = copy.deepcopy(reports)
    drone_10m_extra_miss.append(
        build_report(
            "drone_10m_extra_miss_04",
            target="drone",
            distance_m=10.0,
            outcome="MISSED",
        )
    )
    require(
        "performance_drone_10m" in failed_names(drone_10m_extra_miss),
        "10 m 3/4 result was mislabeled as 3/3",
    )

    drone_30m_low = copy.deepcopy(reports)
    for index in (3, 4):
        drone_30m_low[index]["summary"].update({"outcome": "MISSED", "performance_pass": False})
    require(
        "performance_drone_30m" in failed_names(drone_30m_low),
        "30 m drone result below 2/3 was accepted",
    )

    drone_30m_extra_misses = copy.deepcopy(reports)
    for trial_index in (4, 5):
        drone_30m_extra_misses.append(
            build_report(
                f"drone_30m_extra_miss_{trial_index:02d}",
                target="drone",
                distance_m=30.0,
                outcome="MISSED",
            )
        )
    require(
        "performance_drone_30m" in failed_names(drone_30m_extra_misses),
        "30 m 3/5 result was mislabeled as at least 2/3",
    )

    estimated_distance = copy.deepcopy(reports)
    estimated_distance[0]["metadata"]["distance_source"] = "estimate"
    estimated_result = field_evidence_gate.evaluate_evidence_reports(estimated_distance, trials_per_cell=3)
    require(estimated_result["result"] == "NO-GO", "estimated distance entered the formal matrix")
    require(
        "distance_source_not_verifiable" in estimated_result["invalid_reports"][0]["reasons"],
        "unverified distance failure reason was hidden",
    )

    wrong_video_binding = copy.deepcopy(reports)
    wrong_video_binding[0]["video_evidence"]["reference"] = "phone_unrelated_clip"
    wrong_video_result = field_evidence_gate.evaluate_evidence_reports(
        wrong_video_binding,
        trials_per_cell=3,
    )
    require(wrong_video_result["result"] == "NO-GO", "wrong video was bound to a field trial")
    require(
        "video_session_binding_missing" in wrong_video_result["invalid_reports"][0]["reasons"],
        "wrong video binding reason was hidden",
    )

    person_false_lock = copy.deepcopy(reports)
    person_false_lock[9]["summary"].update({"outcome": "FALSE_LOCK", "performance_pass": False})
    require(
        "performance_person_10m" in failed_names(person_false_lock),
        "negative false lock was accepted by the field gate",
    )

    short_stability = copy.deepcopy(reports)
    short_stability[-2]["runtime"]["actual_elapsed_s"] = 1199.0
    require(
        "long_stability_static" in failed_names(short_stability),
        "short static stability run was accepted",
    )

    interrupted_stability = copy.deepcopy(reports)
    interrupted_stability[-1]["summary"]["status_interruption_count"] = 1
    require(
        "long_stability_normal_traffic" in failed_names(interrupted_stability),
        "interrupted traffic stability run was accepted",
    )

    load_error_result = field_evidence_gate.evaluate_evidence_reports(
        reports,
        trials_per_cell=3,
        load_errors=[{"path": "broken/trial_report.json", "error": "JSONDecodeError"}],
    )
    require(load_error_result["result"] == "NO-GO", "broken report file was ignored")
    require(
        "report_files_loadable" in {
            str(item["name"]) for item in load_error_result["checks"] if not item["passed"]
        },
        "broken report file was not included in gate checks",
    )
    require(
        load_error_result["passed_count"] == load_error_result["total_count"] - 1,
        "broken report failure is inconsistent with the displayed check count",
    )


def check_deployed_v4b_startup_commands() -> None:
    with tempfile.TemporaryDirectory(prefix="flytotal-v4b-startup-") as temp_dir:
        root = Path(temp_dir)
        model_path = dataset_collector.PROJECT_ROOT / "models" / "yolov8n_drone.onnx"
        report = readiness.build_report(
            report_file=root / "usb_report.json",
            camera_records=[
                {
                    "source_index": 0,
                    "backend_active": "dshow",
                    "opened": True,
                    "frame_ready": True,
                }
            ],
            trackers_available=["mil"],
            probe_backends=["dshow", "auto"],
            requested_index_range=(0, 1),
            recommended_tracker_fallback="auto",
            recommended_source_warmup_frames=12,
            drone_model_path=model_path,
            drone_model_ready=True,
            failures=[],
            warnings=[],
        )
        recommended = str(report["recommended"]["vision_bridge_command"])
        rebuilt = startup_helper.build_recommended_vision_command("py -3", report["recommended"])
        fallback = startup_helper.build_fallback_vision_command("py -3")
        required_tokens = [
            "--yolo-model models/yolov8n_drone.onnx",
            "--yolo-class-ids 0",
            "--yolo-class-names 0:drone",
            "--yolo-model-label drone-v4b-hardneg-deployed",
            "--yolo-score-threshold 0.45",
            "--yolo-intra-op-threads 8",
            "--yolo-auto-lock",
        ]
        for token in required_tokens:
            require(token in recommended, f"readiness command lost deployed V4b token: {token}")
            require(token in rebuilt, f"startup rebuilt command lost deployed V4b token: {token}")
            require(token in fallback, f"startup fallback lost deployed V4b token: {token}")
        require("--backend dshow --source 0 --tracker mil" in recommended, "readiness camera probe was ignored")
        require("py -3 " in rebuilt, "startup rebuilt command ignored the selected Python command")
        require("--backend dshow --source 0 --tracker mil" in rebuilt, "startup rebuilt command lost probe fields")
        require("py -3 " in fallback, "startup fallback changed the selected Python command")
        require("--tracker csrt --tracker-fallback auto" in fallback, "startup fallback lost tracker recovery")


def check_vision_forward_plan() -> None:
    now_ms = int(time.time() * 1000)
    locked_payload = {
        "ok": True,
        "available": True,
        "timestamp_ms": now_ms,
        "source_ready": 1,
        "vision_chain_ready": 1,
        "vision_state": "VISION_LOCKED",
        "vision_locked": 1,
        "vision_confidence": 0.82,
        "bbox_stability_score": 0.74,
        "frame_content_ready": 1,
        "frame_quality_reason": "OK",
        "lock_source": "YOLO_AUTO",
    }
    locked = node_bridge.build_vision_forward_plan(
        locked_payload,
        now_ms=now_ms,
        max_stale_ms=2500,
    )
    require(locked["state"] == "LOCKED", "fresh valid lock was not forwarded")
    require(
        locked["commands"] == [
            "VISION,CONF,confidence=0.82,stability=0.74,state=TRACKING",
            "VISION,LOCKED",
        ],
        "locked serial command sequence is incomplete",
    )

    invalid_frame = dict(locked_payload)
    invalid_frame["frame_content_ready"] = 0
    rejected = node_bridge.build_vision_forward_plan(
        invalid_frame,
        now_ms=now_ms,
        max_stale_ms=2500,
    )
    require(rejected["state"] == "SEARCHING", "invalid locked frame was forwarded as locked")
    require(rejected["commands"] == ["VISION,SEARCHING"], "invalid frame did not clear lock")

    stale_payload = dict(locked_payload)
    stale_payload["timestamp_ms"] = now_ms - 5000
    stale = node_bridge.build_vision_forward_plan(
        stale_payload,
        now_ms=now_ms,
        max_stale_ms=2500,
    )
    require(stale["state"] == "LOST", "stale vision status did not clear lock")
    require(stale["commands"] == ["VISION,LOST"], "stale status emitted the wrong serial command")

    class RecordingDispatcher:
        def __init__(self) -> None:
            self.bundles: list[list[str]] = []

        def enqueue_bundle(self, commands: list[str], *, source: str) -> bool:
            require(source == "VISION_FORWARD", "vision heartbeat used the wrong dispatcher source")
            self.bundles.append(list(commands))
            return True

    with tempfile.TemporaryDirectory(prefix="flytotal-vision-forward-") as temp_dir:
        status_path = Path(temp_dir) / "latest_status.json"
        status_path.write_text(json.dumps(locked_payload), encoding="utf-8")
        recording_dispatcher = RecordingDispatcher()
        signature, sent_at, first_plan = node_bridge.maybe_forward_vision_status(
            recording_dispatcher,
            status_path,
            last_signature="",
            last_sent_at=0.0,
            interval_s=0.1,
            max_stale_ms=2500,
        )
        require(
            recording_dispatcher.bundles[-1] == locked["commands"],
            "first locked vision update did not include confidence and state",
        )
        _, _, heartbeat_plan = node_bridge.maybe_forward_vision_status(
            recording_dispatcher,
            status_path,
            last_signature=signature,
            last_sent_at=sent_at - 1.0,
            interval_s=0.1,
            max_stale_ms=2500,
        )
        require(first_plan["queued_commands"] == locked["commands"], "first vision bundle was reduced")
        require(
            heartbeat_plan["queued_commands"] == ["VISION,LOCKED"],
            "unchanged locked heartbeat repeated the confidence command",
        )
        require(
            recording_dispatcher.bundles[-1] == ["VISION,LOCKED"],
            "dispatcher received a redundant locked heartbeat bundle",
        )

    class FlakySerial:
        def __init__(self) -> None:
            self.write_calls = 0
            self.flush_calls = 0
            self.reset_calls = 0

        def write(self, payload: bytes) -> int:
            self.write_calls += 1
            if self.write_calls == 1:
                raise node_bridge.serial.SerialTimeoutException("regression timeout")
            return len(payload)

        def flush(self) -> None:
            self.flush_calls += 1

        def reset_output_buffer(self) -> None:
            self.reset_calls += 1

    flaky = FlakySerial()
    require(
        node_bridge.send_serial_line_with_retry(flaky, "STATUS", retry_count=2, retry_delay_s=0.0),
        "serial write did not recover after one timeout",
    )
    require(flaky.write_calls == 2 and flaky.flush_calls == 1, "serial retry count is wrong")
    require(flaky.reset_calls == 1, "serial output buffer was not reset before retry")

    class FlakyJsonPath:
        def __init__(self) -> None:
            self.read_calls = 0

        def exists(self) -> bool:
            return True

        def read_text(self, encoding: str) -> str:
            self.read_calls += 1
            if self.read_calls == 1:
                raise PermissionError("regression writer lock")
            return '{"available": true, "vision_state": "VISION_LOCKED"}'

    flaky_path = FlakyJsonPath()
    recovered_payload = node_bridge.load_json_payload(flaky_path, retry_count=2, retry_delay_s=0.0)
    require(recovered_payload.get("available") is True, "JSON read did not recover after a transient writer lock")
    require(flaky_path.read_calls == 2, "JSON read retry count is wrong")


def check_serial_command_dispatcher() -> None:
    class FakeClock:
        def __init__(self, now: float = 10.0) -> None:
            self.now = now

        def __call__(self) -> float:
            return self.now

        def advance(self, seconds: float) -> None:
            self.now += seconds

    class RecordingSerial:
        def __init__(self) -> None:
            self.lines: list[str] = []

        def write(self, payload: bytes) -> int:
            self.lines.append(payload.decode("utf-8").strip())
            return len(payload)

        def flush(self) -> None:
            return None

    clock = FakeClock()
    serial_recorder = RecordingSerial()
    dispatcher = node_bridge.SerialCommandDispatcher(
        serial_recorder,
        min_send_interval_s=0.1,
        queue_limit=8,
        clock=clock,
        sleeper=clock.advance,
    )

    require(dispatcher.enqueue("STATUS", source="poll"), "first status poll was rejected")
    require(dispatcher.enqueue("STATUS", source="poll"), "replacement status poll was rejected")
    require(dispatcher.pending_count == 1, "duplicate status polls were not coalesced")
    require(dispatcher.enqueue("TRACK,100,900", source="repeat"), "first track state was rejected")
    require(dispatcher.enqueue("TRACK,320,1000", source="repeat"), "new track state was rejected")
    require(dispatcher.pending_count == 2, "old track state was not replaced")
    require(dispatcher.enqueue("CLOUD,TEST", source="manual"), "first cloud action was rejected")
    require(dispatcher.enqueue("CLOUD,TEST", source="manual"), "second cloud action was rejected")
    require(dispatcher.pending_count == 4, "action commands were incorrectly deduplicated")

    first = dispatcher.pump()
    require(first is not None and first.command == "CLOUD,TEST", "action priority is incorrect")
    require(dispatcher.pump() is None, "global serial send interval was bypassed")
    for _ in range(3):
        clock.advance(0.1)
        dispatcher.pump()
    require(
        serial_recorder.lines == ["CLOUD,TEST", "CLOUD,TEST", "TRACK,320,1000", "STATUS"],
        "dispatcher ordering, state coalescing, or action preservation is incorrect",
    )

    require(
        dispatcher.enqueue("VISION,LOCKED", source="vision", ttl_s=0.05),
        "expiring vision state was rejected",
    )
    clock.advance(0.06)
    require(dispatcher.pump() is None, "expired vision state was replayed")
    require(dispatcher.expired_count == 1, "expired command was not counted")

    small_dispatcher = node_bridge.SerialCommandDispatcher(
        RecordingSerial(),
        min_send_interval_s=0.0,
        queue_limit=2,
        clock=clock,
        sleeper=clock.advance,
    )
    require(small_dispatcher.enqueue("STATUS", source="poll"), "status queue setup failed")
    require(small_dispatcher.enqueue("SELFTEST", source="poll"), "selftest queue setup failed")
    require(small_dispatcher.enqueue("TRACK,CLEAR", source="safety"), "safety command did not preempt a full queue")
    require(
        small_dispatcher.enqueue("TRACK,999,999", source="stale-repeat"),
        "lower-priority track update was not safely coalesced",
    )
    safety = small_dispatcher.pump()
    require(
        safety is not None and safety.command == "TRACK,CLEAR",
        "pending safety clear was overwritten or did not run first",
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        inbox = Path(temp_dir)
        fresh = {
            "version": 1,
            "id": "fresh-command",
            "created_ms": 99_950,
            "ttl_ms": 1_000,
            "command": "CLOUD,STATUS",
        }
        expired = {
            "version": 1,
            "id": "expired-command",
            "created_ms": 98_000,
            "ttl_ms": 1_000,
            "command": "TRACK,1,1",
        }
        (inbox / "001-fresh.json").write_text(json.dumps(fresh), encoding="utf-8")
        (inbox / "002-expired.json").write_text(json.dumps(expired), encoding="utf-8")
        inbox_dispatcher = node_bridge.SerialCommandDispatcher(
            RecordingSerial(),
            min_send_interval_s=0.0,
            queue_limit=4,
            clock=clock,
            sleeper=clock.advance,
        )
        result = node_bridge.consume_serial_command_inbox(
            inbox_dispatcher,
            inbox,
            now_ms=100_000,
        )
        require(result["accepted"] == 1, "fresh inbox command was not accepted")
        require(result["expired"] == 1, "expired inbox command was not discarded")
        require(inbox_dispatcher.pending_count == 1, "inbox queued the wrong number of commands")
        require(not list(inbox.glob("*.json")), "consumed inbox requests were left for replay")


def check_serial_bridge_owner_lock() -> None:
    child_code = """
import importlib
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
bridge = importlib.import_module("node_a_serial_bridge_NodeA串口桥接")
lock = bridge.SerialPortOwnerLock(Path(sys.argv[2]), sys.argv[3])
if not lock.acquire():
    raise SystemExit(2)
Path(sys.argv[4]).write_text(str(os.getpid()), encoding="utf-8")
release_path = Path(sys.argv[5])
while not release_path.exists():
    time.sleep(0.02)
lock.release()
"""

    with tempfile.TemporaryDirectory(prefix="flytotal-serial-owner-") as temp_dir:
        temp_path = Path(temp_dir)
        lock_path = temp_path / "COM4.owner.lock"
        ready_path = temp_path / "ready.txt"
        release_path = temp_path / "release.txt"
        tools_dir = str(Path(__file__).resolve().parent)
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                child_code,
                tools_dir,
                str(lock_path),
                "COM4",
                str(ready_path),
                str(release_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5.0
            while not ready_path.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            if not ready_path.exists():
                stdout, stderr = child.communicate(timeout=2.0)
                raise AssertionError(
                    f"serial owner child did not acquire lock: rc={child.returncode}, stdout={stdout}, stderr={stderr}"
                )

            contender = node_bridge.SerialPortOwnerLock(lock_path, "COM4")
            require(not contender.acquire(), "second serial bridge acquired an already-owned COM lock")
            owner = contender.read_owner_metadata()
            require(int(owner.get("pid") or 0) == child.pid, "owner lock did not expose the current bridge PID")

            release_path.write_text("release", encoding="utf-8")
            child.wait(timeout=5.0)
            require(child.returncode == 0, "serial owner child failed while releasing lock")

            successor = node_bridge.SerialPortOwnerLock(lock_path, "COM4")
            require(successor.acquire(), "serial owner lock remained stuck after the process released it")
            successor.release()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5.0)

    bridge_source = Path(node_bridge.__file__).read_text(encoding="utf-8")
    main_start = bridge_source.index("def main() -> int:")
    owner_acquire = bridge_source.index("if not owner_lock.acquire():", main_start)
    serial_open = bridge_source.index("ser = serial_module.Serial(", main_start)
    first_status_write = bridge_source.index("write_status_json(output_file, status)", main_start)
    require(
        owner_acquire < serial_open < first_status_write,
        "bridge can write formal status before it proves exclusive serial access",
    )

    class BusySerialModule:
        class SerialException(Exception):
            pass

        @staticmethod
        def Serial(*_args: object, **_kwargs: object) -> object:
            raise BusySerialModule.SerialException("regression port already owned")

    with tempfile.TemporaryDirectory(prefix="flytotal-serial-open-fail-") as temp_dir:
        temp_path = Path(temp_dir)
        owner_path = temp_path / "owner.lock"
        formal_outputs = [
            temp_path / "status.json",
            temp_path / "events.json",
            temp_path / "event_store.json",
            temp_path / "result.json",
            temp_path / "result_history.json",
        ]
        original_serial = node_bridge.serial
        original_argv = sys.argv
        try:
            node_bridge.serial = BusySerialModule
            sys.argv = [
                "node_a_serial_bridge",
                "--port",
                "COM-REGRESSION",
                "--owner-lock-file",
                str(owner_path),
                "--output-file",
                str(formal_outputs[0]),
                "--events-file",
                str(formal_outputs[1]),
                "--event-store-file",
                str(formal_outputs[2]),
                "--result-file",
                str(formal_outputs[3]),
                "--result-history-file",
                str(formal_outputs[4]),
            ]
            result = node_bridge.main()
        finally:
            node_bridge.serial = original_serial
            sys.argv = original_argv

        require(result == 1, "busy serial port did not produce the expected bridge failure")
        require(not any(path.exists() for path in formal_outputs), "busy serial port polluted formal evidence files")
        retry_lock = node_bridge.SerialPortOwnerLock(owner_path, "COM-REGRESSION")
        require(retry_lock.acquire(), "bridge kept its process lock after serial open failed")
        retry_lock.release()


def check_serial_command_submission_interval() -> None:
    with tempfile.TemporaryDirectory(prefix="flytotal-serial-command-") as temp_dir:
        inbox_dir = Path(temp_dir)
        commands = ["TRACK,320,1000", "TRACK,320,1000", "EVENT,STATUS"]
        sleep_calls: list[float] = []
        submitted = node_command.submit_commands(
            inbox_dir,
            commands,
            ttl_ms=30_000,
            interval_s=0.2,
            sleep_fn=sleep_calls.append,
        )
        require(len(submitted) == len(commands), "timed serial sequence dropped a command")
        require(sleep_calls == [0.2, 0.2], "timed serial sequence used the wrong intervals")
        payloads = [json.loads(path.read_text(encoding="utf-8")) for _, path in submitted]
        require([payload.get("command") for payload in payloads] == commands, "timed serial sequence changed order")
        require(all(payload.get("ttl_ms") == 30_000 for payload in payloads), "timed serial sequence changed TTL")
        require(not list(inbox_dir.glob(".*.tmp")), "timed serial sequence left a partial request file")

        try:
            node_command.submit_commands(inbox_dir, ["STATUS"], 30_000, interval_s=-0.1)
        except ValueError:
            pass
        else:
            raise AssertionError("negative serial command interval was accepted")


def check_vision_status_write_retry() -> None:
    class FakeParent:
        def __init__(self) -> None:
            self.mkdir_calls = 0

        def mkdir(self, *, parents: bool, exist_ok: bool) -> None:
            require(parents and exist_ok, "status writer did not create its parent safely")
            self.mkdir_calls += 1

    class FlakyTempPath:
        def __init__(self) -> None:
            self.write_calls = 0
            self.replace_calls = 0
            self.text = ""

        def write_text(self, text: str, *, encoding: str) -> int:
            require(encoding == "utf-8", "status writer changed JSON encoding")
            self.write_calls += 1
            self.text = text
            return len(text)

        def replace(self, target: object) -> object:
            self.replace_calls += 1
            if self.replace_calls == 1:
                raise PermissionError("regression reader lock")
            return target

    class FakeStatusPath:
        suffix = ".json"

        def __init__(self) -> None:
            self.parent = FakeParent()
            self.temp_path = FlakyTempPath()

        def with_suffix(self, suffix: str) -> FlakyTempPath:
            require(suffix == ".json.tmp", "status writer used the wrong temporary suffix")
            return self.temp_path

    status_path = FakeStatusPath()
    bridge.write_latest_status_json(
        status_path,
        {"available": True, "vision_state": "VISION_LOCKED"},
        retry_count=2,
        retry_delay_s=0.0,
    )
    require(status_path.parent.mkdir_calls == 1, "status writer parent setup count is wrong")
    require(status_path.temp_path.write_calls == 1, "status JSON was rewritten during replace retry")
    require(status_path.temp_path.replace_calls == 2, "status replace did not recover after one lock")
    require(
        json.loads(status_path.temp_path.text).get("vision_state") == "VISION_LOCKED",
        "status retry changed the JSON payload",
    )


def check_web_json_read_retry() -> None:
    class FlakyJsonPath:
        def __init__(self, failures: int) -> None:
            self.failures = failures
            self.read_calls = 0

        def exists(self) -> bool:
            return True

        def read_text(self, *, encoding: str) -> str:
            require(encoding == "utf-8", "web status reader used the wrong encoding")
            self.read_calls += 1
            if self.read_calls <= self.failures:
                raise PermissionError("simulated Windows read lock")
            return json.dumps({"vision_state": "VISION_LOCKED"})

    recovered_path = FlakyJsonPath(failures=1)
    recovered = web_server.load_json_file(recovered_path, retry_count=2, retry_delay_s=0.0)
    require(recovered_path.read_calls == 2, "web status reader did not retry one transient lock")
    require(bool(recovered.get("ok")) and bool(recovered.get("available")), "web retry did not recover")
    require(recovered.get("vision_state") == "VISION_LOCKED", "web retry changed the JSON payload")

    denied_path = FlakyJsonPath(failures=3)
    denied = web_server.load_json_file(denied_path, retry_count=3, retry_delay_s=0.0)
    require(denied_path.read_calls == 3, "web status reader exceeded its retry limit")
    require(denied.get("error") == "read_denied", "web status reader did not return a stable failure payload")


def check_web_vision_freshness_merge() -> None:
    now_ms = int(time.time() * 1000)
    node_payload = {"vision_state": "VISION_LOCKED", "vision_locked": 1, "node_id": "A1"}
    stale_vision = {
        "available": True,
        "timestamp_ms": now_ms - 10_000,
        "vision_state": "VISION_IDLE",
        "vision_locked": 0,
        "detector_state": "READY_ONNX",
        "frame_content_ready": 1,
    }
    stale_merge = web_server.merge_vision_runtime_fields(node_payload, stale_vision, offline_timeout_ms=1000)
    require(stale_merge["vision_runtime_online"] == 0, "stale vision runtime was reported online")
    require(stale_merge["vision_state"] == "VISION_LOCKED", "stale host state overwrote Node A state")
    require(stale_merge["vision_locked"] == 1, "stale host lock flag overwrote Node A lock")
    require(stale_merge["detector_state"] == "OFFLINE", "stale detector was shown as ready")

    fresh_vision = dict(stale_vision)
    fresh_vision.update(
        {
            "timestamp_ms": now_ms,
            "vision_state": "VISION_SEARCHING",
            "vision_locked": 0,
            "frame_content_ready": 0,
        }
    )
    fresh_vision.pop("available")
    fresh_merge = web_server.merge_vision_runtime_fields(node_payload, fresh_vision, offline_timeout_ms=1000)
    require(
        fresh_merge["vision_runtime_online"] == 1,
        "fresh raw vision status without an available field was reported offline",
    )
    require(fresh_merge["vision_state"] == "VISION_SEARCHING", "fresh host vision state was not merged")
    require(fresh_merge["vision_locked"] == 0, "fresh host lock flag was not merged")


def check_national_first_event_gate() -> None:
    event_id = "A1-NATIONAL-FIRST-TEST"
    cloud_test_event_id = "A1-CLOUD-TEST"
    contract_status = {
        "available": True,
        "online": 1,
        "node_id": "A1",
        "serial_bridge_contract_version": 2,
        "web_evidence_contract_version": 2,
        "cloud_enabled": 0,
        "cloud_configured": 1,
        "cloud_wifi_status": "DISCONNECTED",
        "cloud_request_in_flight": 0,
        "cloud_contract_version": 2,
        "cloud_event_echo_required": 1,
        "cloud_test_no_apply": 1,
        "cloud_test_validated": 0,
        "track_active": 0,
        "event_active": 0,
        "event_id": "NONE",
    }
    contract_preflight = closure.evaluate_cloud_preflight_status(contract_status, "contract")
    require(
        contract_preflight["result"] == "PASS",
        f"clean cloud contract preflight failed: {contract_preflight['failures']}",
    )

    legacy_bridge_status = dict(contract_status)
    legacy_bridge_status["serial_bridge_contract_version"] = 0
    legacy_bridge_preflight = closure.evaluate_cloud_preflight_status(
        legacy_bridge_status,
        "contract",
    )
    require(legacy_bridge_preflight["result"] == "FAIL", "legacy serial bridge passed cloud preflight")
    require(
        "serial_bridge_contract_v2" in legacy_bridge_preflight["failures"],
        "legacy serial bridge version failure was not reported",
    )

    legacy_web_status = dict(contract_status)
    legacy_web_status["web_evidence_contract_version"] = 0
    legacy_web_preflight = closure.evaluate_cloud_preflight_status(legacy_web_status, "contract")
    require(legacy_web_preflight["result"] == "FAIL", "legacy web service passed cloud preflight")
    require(
        "web_evidence_contract_v2" in legacy_web_preflight["failures"],
        "legacy web evidence version failure was not reported",
    )

    dirty_contract_status = dict(contract_status)
    dirty_contract_status.update(
        {
            "cloud_test_validated": 1,
            "cloud_test_result_no_apply": 1,
            "cloud_test_response_event_id": cloud_test_event_id,
            "cloud_test_result_received_ms": 1_783_927_000_000,
        }
    )
    dirty_contract_preflight = closure.evaluate_cloud_preflight_status(
        dirty_contract_status,
        "contract",
    )
    require(dirty_contract_preflight["result"] == "FAIL", "dirty cloud contract state was accepted")
    require(
        "cloud_test_not_yet_validated" in dirty_contract_preflight["failures"],
        "validated cloud state did not fail the clean contract preflight",
    )
    require(
        "cloud_test_raw_clear" in dirty_contract_preflight["failures"],
        "stale raw cloud test evidence did not fail the clean contract preflight",
    )

    active_track_status = dict(contract_status)
    active_track_status["track_active"] = 1
    active_track_preflight = closure.evaluate_cloud_preflight_status(active_track_status, "contract")
    require(active_track_preflight["result"] == "FAIL", "active track passed cloud preflight")
    require(
        "track_idle" in active_track_preflight["failures"],
        "active track did not report the cloud preflight idle failure",
    )

    active_event_status = dict(contract_status)
    active_event_status.update({"event_active": 1, "event_id": "A1-ACCIDENTAL-EVENT"})
    active_event_preflight = closure.evaluate_cloud_preflight_status(active_event_status, "contract")
    require(active_event_preflight["result"] == "FAIL", "active event passed cloud preflight")
    require(
        "event_idle" in active_event_preflight["failures"],
        "active event did not report the cloud preflight idle failure",
    )

    test_status = dict(contract_status)
    test_status.update(
        {
            "cloud_enabled": 1,
            "cloud_wifi_status": "CONNECTED",
            "cloud_online": 1,
            "cloud_test_validated": 1,
            "cloud_test_result_no_apply": 1,
            "cloud_test_response_event_id": cloud_test_event_id,
            "cloud_test_result_received_ms": 1_783_927_000_000,
            "cloud_result_ok": 1,
            "cloud_result_source": "TEST",
            "cloud_result_threat_level": "HIGH",
            "cloud_result_command_type": "GENERATE_ALERT",
            "cloud_request_event_id": cloud_test_event_id,
            "cloud_expected_event_id": cloud_test_event_id,
            "cloud_response_event_id": cloud_test_event_id,
            "cloud_result_http_status": 200,
            "cloud_result_esp_error": 0,
            "cloud_result_error": "NONE",
            "cloud_result_received_ms": 1_783_927_000_100,
            "cloud_error": "NONE",
            "cloud_command_applied": 0,
            "cloud_command_effect": "TEST_RESPONSE_VALIDATED",
            "cloud_command_source_event_id": cloud_test_event_id,
        }
    )
    test_preflight = closure.evaluate_cloud_preflight_status(test_status, "test")
    require(
        test_preflight["result"] == "PASS",
        f"valid cloud test preflight failed: {test_preflight['failures']}",
    )

    invalid_test_status = dict(test_status)
    invalid_test_status["cloud_test_result_no_apply"] = 0
    invalid_test_status["cloud_response_event_id"] = "A1-WRONG-TEST"
    invalid_test_preflight = closure.evaluate_cloud_preflight_status(invalid_test_status, "test")
    require(invalid_test_preflight["result"] == "FAIL", "invalid cloud test preflight was accepted")
    require(
        "cloud_test_no_apply_observed" in invalid_test_preflight["failures"],
        "missing raw no-apply proof was not reported",
    )
    require(
        "cloud_response_event_match" in invalid_test_preflight["failures"],
        "mismatched raw cloud response event ID was not reported",
    )

    applied_test_status = dict(test_status)
    applied_test_status["cloud_command_applied"] = 1
    applied_test_status["cloud_command_effect"] = "ALERT_GENERATED"
    applied_test_preflight = closure.evaluate_cloud_preflight_status(applied_test_status, "test")
    require(applied_test_preflight["result"] == "FAIL", "applied cloud test action was accepted")
    require(
        "cloud_test_not_applied" in applied_test_preflight["failures"],
        "applied cloud test action was not reported",
    )

    unsafe_policy_status = dict(test_status)
    unsafe_policy_status["cloud_result_threat_level"] = "LOW"
    unsafe_policy_status["cloud_result_command_type"] = "NONE"
    unsafe_policy_preflight = closure.evaluate_cloud_preflight_status(unsafe_policy_status, "test")
    require(unsafe_policy_preflight["result"] == "FAIL", "unsafe cloud test policy passed preflight")
    require(
        "cloud_test_policy_threat_high" in unsafe_policy_preflight["failures"],
        "low cloud test threat did not fail policy preflight",
    )
    require(
        "cloud_test_policy_generate_alert" in unsafe_policy_preflight["failures"],
        "cloud test NONE command did not fail policy preflight",
    )

    original_argv = sys.argv
    original_fetch = closure.fetch_json_with_retry
    try:
        with tempfile.TemporaryDirectory(prefix="flytotal-cloud-preflight-") as temp_dir:
            report_path = Path(temp_dir) / "cloud_preflight_report.json"
            pending_test_status = dict(contract_status)
            pending_test_status.update(
                {
                    "cloud_enabled": 1,
                    "cloud_wifi_status": "CONNECTED",
                    "cloud_request_in_flight": 1,
                }
            )
            fetch_sequence = [pending_test_status, test_status]
            fetch_calls = 0

            def fetch_cloud_test_sequence(*_args, **_kwargs):
                nonlocal fetch_calls
                index = min(fetch_calls, len(fetch_sequence) - 1)
                fetch_calls += 1
                return dict(fetch_sequence[index])

            closure.fetch_json_with_retry = fetch_cloud_test_sequence
            sys.argv = [
                str(Path(closure.__file__)),
                "--base-url",
                "http://127.0.0.1:8765",
                "--cloud-preflight-only",
                "--cloud-preflight-stage",
                "test",
                "--cloud-preflight-wait-s",
                "1",
                "--cloud-preflight-poll-interval-s",
                "0",
                "--cloud-preflight-report-file",
                str(report_path),
            ]
            require(closure.main() == 0, "cloud preflight-only CLI rejected valid test status")
            cli_report = json.loads(report_path.read_text(encoding="utf-8"))
            require(cli_report.get("schema_version") == "cloud_preflight_v1", "cloud preflight report schema changed")
            require(cli_report.get("stage") == "test", "cloud preflight report stage changed")
            require(cli_report.get("result") == "PASS", "cloud preflight-only CLI report did not pass")
            require(cli_report.get("attempt_count") == 2, "cloud preflight did not poll until test completion")
            require(fetch_calls == 2, "cloud preflight fetched an unexpected number of test statuses")

            timeout_report_path = Path(temp_dir) / "cloud_preflight_timeout_report.json"
            closure.fetch_json_with_retry = lambda *_args, **_kwargs: dict(pending_test_status)
            sys.argv = [
                str(Path(closure.__file__)),
                "--base-url",
                "http://127.0.0.1:8765",
                "--cloud-preflight-only",
                "--cloud-preflight-stage",
                "test",
                "--cloud-preflight-wait-s",
                "0.02",
                "--cloud-preflight-poll-interval-s",
                "0.005",
                "--cloud-preflight-report-file",
                str(timeout_report_path),
            ]
            require(closure.main() == 2, "incomplete cloud test did not fail after bounded wait")
            timeout_report = json.loads(timeout_report_path.read_text(encoding="utf-8"))
            require(timeout_report.get("result") == "FAIL", "timed-out cloud preflight report passed")
            require(timeout_report.get("attempt_count", 0) >= 2, "bounded cloud preflight did not poll")
            require(timeout_report.get("waited_ms", 0) > 0, "bounded cloud preflight did not record wait time")
    finally:
        closure.fetch_json_with_retry = original_fetch
        sys.argv = original_argv

    detail = {
        "ok": True,
        "available": True,
        "event_id": event_id,
        "capture_count": 1,
        "capture_binding_mode": "event_id_exact",
        "event_object_v1": {
            "event_id": event_id,
            "vision_evidence": {
                "capture_event_id": event_id,
                "vision_event_id": event_id,
                "evidence_quality": "VALID",
                "status_capture_match": 1,
                "lock_source": "YOLO_AUTO",
                "automatic_lock": 1,
                "auto_lock_score": 0.88,
                "auto_lock_class_name": "drone",
                "detector_state": "READY_ONNX",
                "detector_model_label": field_trial_recorder.DEFAULT_MODEL_LABEL,
                "source": "0",
                "physical_camera_source": 1,
                "capture_backend": "dshow",
                "frame_content_ready": 1,
                "frame_quality_reason": "OK",
                "frame_width": 640,
                "frame_height": 480,
                "capture_sha256": "a" * 64,
                "vision_evidence_hash": "b" * 64,
            },
            "cloud_online": 1,
            "cloud_command_applied": 1,
            "cloud_threat_level": "HIGH",
            "cloud_command_type": "GENERATE_ALERT",
            "cloud_command_effect": "ALERT_GENERATED",
            "cloud_command_source_event_id": event_id,
            "cloud_contract_version": 2,
            "cloud_event_echo_required": 1,
            "cloud_test_no_apply": 1,
            "cloud_test_validated": 1,
            "cloud_test_result_no_apply": 1,
            "cloud_test_response_event_id": "A1-CLOUD-TEST",
            "cloud_result_ok": 1,
            "cloud_result_source": "EVENT_OPENED",
            "cloud_request_event_id": event_id,
            "cloud_expected_event_id": event_id,
            "cloud_response_event_id": event_id,
            "cloud_result_http_status": 200,
            "cloud_result_esp_error": 0,
            "cloud_result_error": "NONE",
            "cloud_result_received_ms": 1_783_927_000_000,
        },
    }
    passed = closure.evaluate_national_first_event_detail(detail, event_id)
    require(passed["result"] == "PASS", f"valid national-first evidence failed: {passed['failures']}")
    require(passed["passed_count"] == 15 and passed["total_count"] == 15, "strict gate is not 15/15")

    replay_detail = json.loads(json.dumps(detail))
    replay_detail["event_object_v1"]["vision_evidence"].update(
        {
            "source": "captures/replay_sources/field_fixture.mp4",
            "physical_camera_source": 0,
            "capture_backend": "auto",
        }
    )
    replay_result = closure.evaluate_national_first_event_detail(replay_detail, event_id)
    require(replay_result["result"] == "FAIL", "replay source passed strict real-event evidence")
    require(
        "vision_evidence_valid" in replay_result["failures"],
        "replay source failure was not bound to visual evidence validity",
    )

    invalid_alert_semantics = json.loads(json.dumps(detail))
    invalid_alert_semantics["event_object_v1"]["cloud_threat_level"] = "MEDIUM"
    invalid_alert_semantics["event_object_v1"]["cloud_command_type"] = "ADJUST_THRESHOLD"
    invalid_alert_semantics["event_object_v1"]["cloud_command_effect"] = "THRESHOLD_UPDATED"
    invalid_alert_result = closure.evaluate_national_first_event_detail(invalid_alert_semantics, event_id)
    require(invalid_alert_result["result"] == "FAIL", "non-alert cloud semantics were accepted")
    require(
        "cloud_command_applied" in invalid_alert_result["failures"],
        "non-alert cloud semantics were not reported",
    )

    invalid = json.loads(json.dumps(detail))
    invalid["event_object_v1"]["vision_evidence"]["evidence_quality"] = "CAPTURE_ONLY"
    invalid["event_object_v1"]["vision_evidence"]["auto_lock_score"] = "invalid-score"
    invalid["event_object_v1"]["cloud_command_source_event_id"] = "A1-OTHER-EVENT"
    failed = closure.evaluate_national_first_event_detail(invalid, event_id)
    require(failed["result"] == "FAIL", "invalid national-first evidence was accepted")
    require("vision_evidence_valid" in failed["failures"], "invalid visual evidence was not reported")
    require("auto_lock_score" in failed["failures"], "malformed auto-lock score was not rejected")
    require("cloud_event_match" in failed["failures"], "cross-event cloud evidence was not reported")

    legacy_contract = json.loads(json.dumps(detail))
    for field in (
        "cloud_contract_version",
        "cloud_event_echo_required",
        "cloud_test_no_apply",
        "cloud_test_validated",
    ):
        legacy_contract["event_object_v1"].pop(field, None)
    legacy_result = closure.evaluate_national_first_event_detail(legacy_contract, event_id)
    require(legacy_result["result"] == "FAIL", "legacy cloud contract evidence was accepted")
    require("cloud_event_match" in legacy_result["failures"], "legacy cloud contract failure was not reported")

    missing_raw_result = json.loads(json.dumps(detail))
    for field in (
        "cloud_test_result_no_apply",
        "cloud_test_response_event_id",
        "cloud_result_ok",
        "cloud_result_source",
        "cloud_request_event_id",
        "cloud_expected_event_id",
        "cloud_response_event_id",
        "cloud_result_http_status",
        "cloud_result_esp_error",
        "cloud_result_error",
        "cloud_result_received_ms",
    ):
        missing_raw_result["event_object_v1"].pop(field, None)
    missing_raw_result_gate = closure.evaluate_national_first_event_detail(missing_raw_result, event_id)
    require(missing_raw_result_gate["result"] == "FAIL", "cloud evidence without raw result IDs was accepted")
    require(
        "cloud_event_match" in missing_raw_result_gate["failures"],
        "missing raw cloud result IDs were not reported",
    )

    parsed_status = node_bridge.build_initial_status("A1", "ZONE_A", "HUNTER")
    require(
        parsed_status.get("serial_bridge_contract_version") == 2,
        "serial bridge initial status does not publish evidence contract V2",
    )
    require(
        web_server.WEB_EVIDENCE_CONTRACT_VERSION == 2,
        "web service does not publish evidence contract V2",
    )
    require(
        node_bridge.update_status_from_line(
            parsed_status,
            "BOOT,SESSION,node=A1,boot_id=A1-00000001-CAFEBABE,boot_count=1,"
            "reset_reason=USB_UART,reset_reason_esp=UNKNOWN,reset_reason_raw=21,uptime_ms=1250",
        ),
        "bridge rejected node boot telemetry",
    )
    require(parsed_status.get("boot_id") == "A1-00000001-CAFEBABE", "bridge dropped node boot id")
    require(parsed_status.get("boot_count") == 1, "bridge dropped retained boot count")
    require(parsed_status.get("reset_reason") == "USB_UART", "bridge dropped effective reset reason")
    require(parsed_status.get("reset_reason_esp") == "UNKNOWN", "bridge dropped ESP reset reason")
    require(parsed_status.get("reset_reason_raw") == 21, "bridge dropped raw reset reason")
    require(parsed_status.get("node_uptime_ms") == 1250, "bridge dropped node uptime")
    require(parsed_status.get("node_boot_change_count") == 0, "first observed boot counted as a reset")
    first_boot_seen_ms = int(parsed_status.get("node_boot_last_change_ms", 0) or 0)
    require(first_boot_seen_ms > 0, "bridge did not timestamp the observed boot")
    require(
        node_bridge.update_status_from_line(
            parsed_status,
            "BOOT,SESSION,node=A1,boot_id=A1-00000002-DEADBEEF,boot_count=2,"
            "reset_reason=TASK_WDT,uptime_ms=300",
        ),
        "bridge rejected a changed node boot session",
    )
    require(parsed_status.get("node_boot_change_count") == 1, "bridge did not count a node reset")
    require(
        int(parsed_status.get("node_boot_last_change_ms", 0) or 0) >= first_boot_seen_ms,
        "bridge did not retain reset observation time",
    )
    require(
        node_bridge.update_status_from_line(
            parsed_status,
            "STATUS,node_id=A1,cloud_contract_version=2,cloud_event_echo_required=1,"
            "cloud_test_no_apply=1,cloud_test_validated=1",
        ),
        "bridge rejected cloud contract status fields",
    )
    require(parsed_status.get("cloud_contract_version") == 2, "bridge dropped cloud contract version")
    require(parsed_status.get("cloud_event_echo_required") == 1, "bridge dropped cloud event echo capability")
    require(parsed_status.get("cloud_test_no_apply") == 1, "bridge dropped cloud test no-apply capability")
    require(parsed_status.get("cloud_test_validated") == 1, "bridge dropped cloud test validation state")
    parsed_status["event_id"] = event_id
    require(
        node_bridge.update_status_from_line(
            parsed_status,
            "CLOUD,STATUS,enabled=1,cloud_contract_version=2,cloud_event_echo_required=1,"
            "cloud_test_no_apply=1,cloud_test_validated=0,configured=1,wifi=CONNECTED,"
            "request_in_flight=0,dropped_total=0,cloud_online=0,error=NONE",
        ),
        "bridge rejected CLOUD,STATUS",
    )
    require(parsed_status.get("cloud_enabled") == 1, "bridge dropped cloud enabled state")
    require(parsed_status.get("cloud_configured") == 1, "bridge dropped cloud configured state")
    require(parsed_status.get("cloud_wifi_status") == "CONNECTED", "bridge dropped cloud Wi-Fi state")
    require(parsed_status.get("event_id") == event_id, "CLOUD,STATUS overwrote the active event ID")
    require(
        node_bridge.update_status_from_line(
            parsed_status,
            "CLOUD,TEST,validated=1,no_apply=1,response_event_id=A1-CLOUD-TEST",
        ),
        "bridge rejected CLOUD,TEST",
    )
    require(parsed_status.get("cloud_test_validated") == 1, "bridge dropped direct cloud test validation")
    require(parsed_status.get("cloud_test_result_no_apply") == 1, "bridge dropped observed cloud test no-apply")
    require(
        parsed_status.get("cloud_test_response_event_id") == "A1-CLOUD-TEST",
        "bridge dropped cloud test response event ID",
    )
    parsed_status["cloud_test_result_received_ms"] = 1_783_931_000_000
    cloud_test_proof_before_skip = {
        key: parsed_status.get(key)
        for key in (
            "cloud_test_validated",
            "cloud_test_result_no_apply",
            "cloud_test_response_event_id",
            "cloud_test_result_received_ms",
        )
    }
    for skipped_line in (
        "CLOUD,TEST,queued=0,reason=already_validated",
        "CLOUD,TEST,queued=0,reason=request_busy",
    ):
        require(
            node_bridge.update_status_from_line(parsed_status, skipped_line),
            "bridge rejected cloud test skip evidence",
        )
        require(
            {
                key: parsed_status.get(key)
                for key in cloud_test_proof_before_skip
            }
            == cloud_test_proof_before_skip,
            "cloud test skip log changed validated raw proof or its timestamp",
        )
    require(parsed_status.get("event_id") == event_id, "cloud test event ID overwrote the active event ID")
    require(
        node_bridge.update_status_from_line(
            parsed_status,
            "CLOUD,RESULT,ok=1,source=EVENT_OPENED,event_id=A1-NATIONAL-FIRST-TEST,"
            "expected_event_id=A1-NATIONAL-FIRST-TEST,response_event_id=A1-NATIONAL-FIRST-TEST,"
            "http_status=200,esp_error=0,latency_ms=684,threat_level=HIGH,"
            "action=GENERATE_ALERT,command_type=GENERATE_ALERT,error=NONE",
        ),
        "bridge rejected CLOUD,RESULT",
    )
    require(parsed_status.get("cloud_result_ok") == 1, "bridge dropped cloud result success")
    require(parsed_status.get("cloud_result_source") == "EVENT_OPENED", "bridge dropped cloud result source")
    require(parsed_status.get("cloud_request_event_id") == event_id, "bridge dropped cloud request event ID")
    require(parsed_status.get("cloud_expected_event_id") == event_id, "bridge dropped cloud expected event ID")
    require(parsed_status.get("cloud_response_event_id") == event_id, "bridge dropped cloud response event ID")
    require(parsed_status.get("cloud_result_http_status") == 200, "bridge dropped cloud HTTP status")
    require(parsed_status.get("cloud_result_received_ms", 0) > 0, "bridge did not timestamp the cloud result")
    require(parsed_status.get("event_id") == event_id, "CLOUD,RESULT overwrote the active event ID")

    dashboard_source = Path(__file__).with_name("vision_dashboard.html").read_text(encoding="utf-8")
    require(
        "cloudTestRawReady" in dashboard_source and "cloudPreflightReady" in dashboard_source,
        "dashboard cloud readiness does not require raw test evidence",
    )
    require(
        "cloudTestPolicyReady" in dashboard_source
        and 'cloudResultCommandType === "GENERATE_ALERT"' in dashboard_source,
        "dashboard cloud readiness does not require the safe test policy",
    )
    require(
        "豆包测试策略未返回 HIGH/CRITICAL + GENERATE_ALERT" in dashboard_source
        and "POLICY WAIT" in dashboard_source,
        "dashboard does not explain a noncompliant cloud test policy",
    )
    require(
        "CLOUD,TEST 原始无动作回显未持久化" in dashboard_source,
        "dashboard does not explain missing raw cloud test evidence",
    )
    require(
        "const cloudPreflightLabel = !cloudTestValidated" in dashboard_source
        and '!cloudTestRawReady ? "RAW WAIT"' in dashboard_source
        and 'cloudTestPolicyReady ? "PASS" : "POLICY WAIT"' in dashboard_source,
        "dashboard does not distinguish wait, raw, policy, and pass preflight states",
    )
    require(
        "const testPolicyReady" in dashboard_source
        and "const preflightLabel = !testValidated" in dashboard_source
        and 'testPolicyReady ? "PASS" : "POLICY WAIT"' in dashboard_source,
        "dashboard cloud detail does not enforce the test policy preflight",
    )


def create_strict_event_fixture(root: Path, event_id: str) -> dict[str, Path]:
    capture_dir = root / "captures"
    export_dir = capture_dir / "event_exports"
    docs_dir = root / "docs"
    session_log_dir = capture_dir / "session_logs"
    capture_dir.mkdir(parents=True)
    export_dir.mkdir(parents=True)
    docs_dir.mkdir(parents=True)
    session_log_dir.mkdir(parents=True)

    image_path = capture_dir / f"valid_capture_{event_id}.jpg"
    require(cv.imwrite(str(image_path), build_textured_frame()), "strict export fixture image was not written")

    timestamp_ms = int(time.time() * 1000)
    event_record = {
        "event_id": event_id,
        "node_id": "A1",
        "source_node": "A1",
        "track_id": 7,
        "event_state": "OPEN",
        "risk_score": 86.0,
        "risk_level": "EVENT",
        "vision_state": "VISION_LOCKED",
        "cloud_online": 1,
        "cloud_command_applied": 1,
        "cloud_threat_level": "HIGH",
        "cloud_command_type": "GENERATE_ALERT",
        "cloud_command_effect": "ALERT_GENERATED",
        "cloud_command_source_event_id": event_id,
        "cloud_contract_version": 2,
        "cloud_event_echo_required": 1,
        "cloud_test_no_apply": 1,
        "cloud_test_validated": 1,
        "cloud_test_result_no_apply": 1,
        "cloud_test_response_event_id": "A1-CLOUD-TEST",
        "cloud_result_ok": 1,
        "cloud_result_source": "EVENT_OPENED",
        "cloud_request_event_id": event_id,
        "cloud_expected_event_id": event_id,
        "cloud_response_event_id": event_id,
        "cloud_result_http_status": 200,
        "cloud_result_esp_error": 0,
        "cloud_result_error": "NONE",
        "cloud_result_received_ms": timestamp_ms,
        "timestamp_ms": timestamp_ms,
        "host_logged_ms": timestamp_ms,
    }
    event_payload = {"count": 1, "records": [event_record]}
    event_store_file = root / "event_store.json"
    node_events_file = root / "node_events.json"
    node_status_file = root / "node_status.json"
    vision_status_file = root / "vision_status.json"
    capture_log_file = root / "capture_records.csv"
    usb_readiness_file = root / "usb_readiness.json"
    event_store_file.write_text(json.dumps(event_payload), encoding="utf-8")
    node_events_file.write_text(json.dumps(event_payload), encoding="utf-8")
    node_status_file.write_text(
        json.dumps(
            {
                "node_id": "A1",
                "event_id": event_id,
                "last_event_id": event_id,
                "vision_state": "VISION_LOCKED",
                "vision_locked": 1,
                "capture_ready": 1,
                "last_capture_file": image_path.as_posix(),
                "last_capture_timestamp_ms": timestamp_ms,
                "cloud_contract_version": 2,
                "cloud_event_echo_required": 1,
                "cloud_test_no_apply": 1,
                "cloud_test_validated": 1,
            }
        ),
        encoding="utf-8",
    )
    vision_status = {
        "timestamp_ms": timestamp_ms,
        "event_id": event_id,
        "event_id_source": "active_event",
        "last_capture_file": image_path.as_posix(),
        "last_capture_timestamp_ms": timestamp_ms,
        "vision_state": "VISION_LOCKED",
        "vision_locked": 1,
        "capture_ready": 1,
        "lock_source": "YOLO_AUTO",
        "auto_lock_score": 0.91,
        "auto_lock_class_name": "drone",
        "detector_state": "READY_ONNX",
        "detector_model_label": field_trial_recorder.DEFAULT_MODEL_LABEL,
        "source": "0",
        "capture_backend": "dshow",
        "vision_confidence": 0.91,
        "bbox_stability_score": 0.82,
        "frame_width": 160,
        "frame_height": 120,
        "frame_content_ready": 1,
        "frame_mean_luma": 120.0,
        "frame_luma_stddev": 25.0,
        "frame_quality_reason": "OK",
    }
    vision_status_file.write_text(json.dumps(vision_status), encoding="utf-8")
    usb_readiness_file.write_text(
        json.dumps({"result": "PASS", "probe": {"ready_count": 1}}),
        encoding="utf-8",
    )

    capture_fields = [
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
    with capture_log_file.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=capture_fields)
        writer.writeheader()
        writer.writerow(
            {
                "timestamp_ms": timestamp_ms,
                "frame_index": 1,
                "vision_state": "VISION_LOCKED",
                "vision_locked": 1,
                "tracker_name": "MIL",
                "event_id": event_id,
                "capture_reason": "AUTO_LOCK",
                "file_path": image_path.as_posix(),
                "bbox_x": 35,
                "bbox_y": 25,
                "bbox_w": 75,
                "bbox_h": 65,
                "center_x": 72,
                "center_y": 57,
            }
        )

    dashboard_file = root / "dashboard.html"
    dashboard_file.write_text("<!doctype html><title>strict fixture</title>", encoding="utf-8")
    active_event_file = root / "active_event.json"
    active_event_file.write_text(json.dumps({"event_id": event_id}), encoding="utf-8")

    return {
        "capture_dir": capture_dir,
        "export_dir": export_dir,
        "docs_dir": docs_dir,
        "session_log_dir": session_log_dir,
        "image_path": image_path,
        "event_store_file": event_store_file,
        "node_events_file": node_events_file,
        "node_status_file": node_status_file,
        "vision_status_file": vision_status_file,
        "capture_log_file": capture_log_file,
        "usb_readiness_file": usb_readiness_file,
        "dashboard_file": dashboard_file,
        "active_event_file": active_event_file,
    }


def check_strict_export_snapshot() -> None:
    event_id = "A1-STRICT-EXPORT-TEST"
    with tempfile.TemporaryDirectory(prefix="flytotal-strict-export-") as temp_dir:
        root = Path(temp_dir)
        fixture = create_strict_event_fixture(root, event_id)
        exported = web_server.build_node_event_export_payload(
            event_store_file=fixture["event_store_file"],
            node_events_file=fixture["node_events_file"],
            capture_log_file=fixture["capture_log_file"],
            capture_dir=fixture["capture_dir"],
            node_status_file=fixture["node_status_file"],
            vision_status_file=fixture["vision_status_file"],
            event_export_dir=fixture["export_dir"],
            event_id=event_id,
            capture_match_mode="strict",
        )
        require(bool(exported.get("export_saved")), "strict event export was not saved")
        require(exported.get("capture_match_mode") == "strict", "strict capture mode was lost")
        export_gate = closure.evaluate_national_first_event_detail(exported["event_detail"], event_id)
        require(export_gate["result"] == "PASS", f"strict export snapshot failed: {export_gate['failures']}")
        exported_vision = exported["event_detail"]["event_object_v1"]["vision_evidence"]
        require(exported_vision.get("source") == "0", "strict export lost the camera source")
        require(exported_vision.get("physical_camera_source") == 1, "physical camera was not hashed")

        export_file = Path(str(exported.get("export_file_path", "")))
        replay = web_server.build_node_event_export_detail_payload(
            fixture["export_dir"],
            fixture["capture_dir"],
            export_file.name,
        )
        require(bool(replay.get("available")), "saved strict export could not be replayed")
        create_object = exported["event_detail"]["event_object_v1"]
        replay_object = replay["event_detail"]["event_object_v1"]
        require(closure.is_sha256_hex(replay_object.get("evidence_hash")), "export evidence hash is invalid")
        require(
            replay_object.get("vision_evidence_hash") == create_object.get("vision_evidence_hash"),
            "saved export vision hash differs from its creation snapshot",
        )


def run_strict_closure_cli(
    root: Path,
    fixture: dict[str, Path],
    report_name: str,
    *,
    max_event_age_ms: int = 900_000,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    handler = web_server.create_handler(
        fixture["dashboard_file"],
        fixture["capture_dir"],
        fixture["docs_dir"],
        fixture["capture_log_file"],
        fixture["vision_status_file"],
        fixture["active_event_file"],
        fixture["node_status_file"],
        root / "node_status_a2.json",
        fixture["node_events_file"],
        root / "node_events_a2.json",
        fixture["event_store_file"],
        root / "test_session.json",
        root / "test_result.json",
        root / "test_results.json",
        fixture["session_log_dir"],
        fixture["export_dir"],
        root / "co_sensing.json",
        10,
        8000,
        5000,
    )
    server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report_file = root / report_name
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(closure.__file__).resolve()),
                "--base-url",
                base_url,
                "--timeout-s",
                "1",
                "--api-retries",
                "3",
                "--api-retry-interval-s",
                "0.05",
                "--node-status-file",
                str(fixture["node_status_file"]),
                "--node-events-file",
                str(fixture["node_events_file"]),
                "--node-event-store-file",
                str(fixture["event_store_file"]),
                "--vision-status-file",
                str(fixture["vision_status_file"]),
                "--capture-log-file",
                str(fixture["capture_log_file"]),
                "--usb-readiness-file",
                str(fixture["usb_readiness_file"]),
                "--require-national-first-evidence",
                "--national-first-max-event-age-ms",
                str(max_event_age_ms),
                "--report-file",
                str(report_file),
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    report = json.loads(report_file.read_text(encoding="utf-8"))
    return completed, report


def check_strict_closure_cli_positive() -> None:
    event_id = "A1-STRICT-CLI-TEST"
    with tempfile.TemporaryDirectory(prefix="flytotal-strict-cli-") as temp_dir:
        root = Path(temp_dir)
        fixture = create_strict_event_fixture(root, event_id)
        completed, report = run_strict_closure_cli(root, fixture, "strict_closure_report.json")
        output = completed.stdout + completed.stderr
        require(completed.returncode == 0, f"strict closure CLI failed:\n{output}")
        counts = report.get("counts", {})
        checks = report.get("checks", {})
        auto_export = report.get("auto_export", {})
        require(report.get("result") == "PASS", f"strict closure report failed: {report.get('failures')}")
        require(report.get("latest_event_id") == event_id, "strict closure selected the wrong event")
        require(
            counts.get("national_first_checks_passed") == 15
            and counts.get("national_first_checks_total") == 15,
            "strict closure main evidence gate is not 15/15",
        )
        require(
            counts.get("strict_export_snapshot_checks_passed") == 15
            and counts.get("strict_export_snapshot_checks_total") == 15,
            "strict closure export snapshot gate is not 15/15",
        )
        require(bool(auto_export.get("attempted")) and bool(auto_export.get("ok")), "strict export was not created")
        require(bool(checks.get("strict_export_hash_ok")), "strict export evidence hash check failed")
        require(bool(checks.get("strict_export_vision_hash_ok")), "strict export vision hash check failed")
        require(bool(checks.get("export_detail_ok")), "strict export replay detail was unavailable")
        require(bool(checks.get("national_first_event_fresh_ok")), "fresh event was rejected as stale")


def check_strict_closure_cli_stale_guard() -> None:
    event_id = "A1-STRICT-STALE-TEST"
    with tempfile.TemporaryDirectory(prefix="flytotal-strict-stale-") as temp_dir:
        root = Path(temp_dir)
        fixture = create_strict_event_fixture(root, event_id)
        stale_timestamp_ms = int(time.time() * 1000) - 16 * 60 * 1000
        for event_file in (fixture["event_store_file"], fixture["node_events_file"]):
            payload = json.loads(event_file.read_text(encoding="utf-8"))
            payload["records"][0]["host_logged_ms"] = stale_timestamp_ms
            event_file.write_text(json.dumps(payload), encoding="utf-8")

        completed, report = run_strict_closure_cli(root, fixture, "strict_stale_report.json")
        output = completed.stdout + completed.stderr
        counts = report.get("counts", {})
        freshness = report.get("national_first_event_freshness", {})
        checks = report.get("checks", {})
        auto_export = report.get("auto_export", {})
        require(completed.returncode == 2, f"stale strict event returned an unexpected code:\n{output}")
        require(report.get("result") == "FAIL", "stale strict event was accepted")
        require(
            counts.get("national_first_checks_passed") == 15
            and counts.get("national_first_checks_total") == 15,
            "stale guard fixture did not isolate event age from the 15 content checks",
        )
        require(freshness.get("result") == "FAIL", "stale event freshness result did not fail")
        require("event_stale" in freshness.get("failures", []), "stale event reason was not reported")
        require(not bool(checks.get("national_first_event_fresh_ok")), "stale event freshness check passed")
        require(not bool(auto_export.get("attempted")), "stale event was exported before freshness passed")


def check_git_secret_hygiene_guard() -> None:
    fake_api_key = "ark" + "-REGRESSION_SECRET_1234567890"
    fake_wifi_password = "regression" + "_wifi_password_123"

    def initialize_repo(root: Path) -> None:
        (root / "include").mkdir(parents=True)
        (root / ".gitignore").write_text("include/secrets.h\n", encoding="utf-8")
        (root / "include" / "secrets.h").write_text(
            "\n".join(
                (
                    "#pragma once",
                    f'#define FLYTOTAL_WIFI_PASSWORD "{fake_wifi_password}"',
                    f'#define FLYTOTAL_ARK_API_KEY "{fake_api_key}"',
                    "",
                )
            ),
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)

    with tempfile.TemporaryDirectory(prefix="flytotal-secret-audit-") as temp_dir:
        root = Path(temp_dir)

        safe_root = root / "safe"
        safe_root.mkdir()
        initialize_repo(safe_root)
        (safe_root / "safe.cpp").write_text(
            'const char *normal_label = "mark-normal_identifier_12345678";\n',
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", ".gitignore", "safe.cpp"],
            cwd=safe_root,
            check=True,
            capture_output=True,
        )
        require(firmware_safety.audit_git_secret_hygiene(safe_root) == 2, "safe secret fixture failed")
        complete_firmware = safe_root / "firmware_complete.bin"
        complete_firmware.write_bytes(
            b"prefix\0"
            + b"regression_wifi\0"
            + fake_wifi_password.encode("utf-8")
            + b"\0"
            + fake_api_key.encode("utf-8")
            + b"\0suffix"
        )
        secrets_file = safe_root / "include" / "secrets.h"
        secrets_file.write_text(
            secrets_file.read_text(encoding="utf-8").replace(
                "#pragma once\n",
                '#pragma once\n#define FLYTOTAL_WIFI_SSID "regression_wifi"\n',
            ),
            encoding="utf-8",
        )
        require(
            firmware_safety.audit_compiled_secret_presence(safe_root, complete_firmware) == 3,
            "complete firmware secret fixture failed",
        )
        incomplete_firmware = safe_root / "firmware_incomplete.bin"
        incomplete_firmware.write_bytes(
            b"regression_wifi\0" + fake_wifi_password.encode("utf-8") + b"\0"
        )
        try:
            firmware_safety.audit_compiled_secret_presence(safe_root, incomplete_firmware)
        except firmware_safety.SecretAuditError as exc:
            message = str(exc)
        else:
            raise AssertionError("incomplete firmware secret fixture was accepted")
        require("FLYTOTAL_ARK_API_KEY" in message, "missing compiled API key symbol was not identified")
        require(fake_api_key not in message and fake_wifi_password not in message, "compiled secret value leaked in error")

        tracked_root = root / "tracked"
        tracked_root.mkdir()
        initialize_repo(tracked_root)
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=tracked_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "-f", "include/secrets.h"],
            cwd=tracked_root,
            check=True,
            capture_output=True,
        )
        try:
            firmware_safety.audit_git_secret_hygiene(tracked_root)
        except firmware_safety.SecretAuditError as exc:
            message = str(exc)
        else:
            raise AssertionError("tracked secrets.h fixture was accepted")
        require("include/secrets.h is tracked by git" in message, "tracked secrets failure was unclear")
        require(fake_api_key not in message and fake_wifi_password not in message, "tracked secret value leaked in error")

        leaked_root = root / "leaked"
        leaked_root.mkdir()
        initialize_repo(leaked_root)
        (leaked_root / "leaked.cpp").write_text(
            f'const char *key = "{fake_api_key}";\n',
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", ".gitignore", "leaked.cpp"],
            cwd=leaked_root,
            check=True,
            capture_output=True,
        )
        (leaked_root / "leaked.cpp").write_text(
            "int clean_worktree = 1;\n",
            encoding="utf-8",
        )
        try:
            firmware_safety.audit_git_secret_hygiene(leaked_root)
        except firmware_safety.SecretAuditError as exc:
            message = str(exc)
        else:
            raise AssertionError("tracked API key fixture was accepted")
        require("Git index" in message and "leaked.cpp" in message, "staged API key file was not identified")
        require(fake_api_key not in message and fake_wifi_password not in message, "API key value leaked in error")

        history_root = root / "history"
        history_root.mkdir()
        initialize_repo(history_root)
        history_file = history_root / "history.cpp"
        history_file.write_text(
            f'const char *key = "{fake_api_key}";\n',
            encoding="utf-8",
        )
        commit_command = [
            "git",
            "-c",
            "user.name=Flytotal Regression",
            "-c",
            "user.email=regression@flytotal.local",
            "commit",
            "-q",
            "-m",
        ]
        subprocess.run(
            ["git", "add", ".gitignore", "history.cpp"],
            cwd=history_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [*commit_command, "history leak fixture"],
            cwd=history_root,
            check=True,
            capture_output=True,
        )
        history_file.write_text("int clean_history_head = 1;\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "history.cpp"],
            cwd=history_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [*commit_command, "clean current fixture"],
            cwd=history_root,
            check=True,
            capture_output=True,
        )
        try:
            firmware_safety.audit_git_secret_hygiene(history_root)
        except firmware_safety.SecretAuditError as exc:
            message = str(exc)
        else:
            raise AssertionError("historical API key fixture was accepted")
        require("reachable Git history" in message, "historical API key risk was not identified")
        require(fake_api_key not in message and fake_wifi_password not in message, "historical key value leaked in error")


def main() -> int:
    checks = [
        ("frame_quality", check_frame_quality),
        ("one_class_yolo_decode", check_one_class_yolo_decode),
        ("yolo_letterbox_decode", check_yolo_letterbox_decode),
        ("auto_lock_candidate", check_auto_lock_candidate),
        ("tracker_and_capture_guard", check_tracker_and_capture_guard),
        ("detector_revision", check_detector_revision),
        ("stale_event_binding_guard", check_stale_event_binding_guard),
        ("field_collector_status_freshness", check_field_collector_status_freshness),
        ("field_trial_recorder", check_field_trial_recorder),
        ("field_collection_preflight", check_field_collection_preflight),
        ("field_evidence_gate", check_field_evidence_gate),
        ("classifier_real_input_guard", check_classifier_real_input_guard),
        ("deployed_v4b_startup_commands", check_deployed_v4b_startup_commands),
        ("vision_forward_plan", check_vision_forward_plan),
        ("serial_command_dispatcher", check_serial_command_dispatcher),
        ("serial_bridge_owner_lock", check_serial_bridge_owner_lock),
        ("serial_command_submission_interval", check_serial_command_submission_interval),
        ("vision_status_write_retry", check_vision_status_write_retry),
        ("web_json_read_retry", check_web_json_read_retry),
        ("web_vision_freshness_merge", check_web_vision_freshness_merge),
        ("national_first_event_gate", check_national_first_event_gate),
        ("strict_export_snapshot", check_strict_export_snapshot),
        ("strict_closure_cli_positive", check_strict_closure_cli_positive),
        ("strict_closure_cli_stale_guard", check_strict_closure_cli_stale_guard),
        ("git_secret_hygiene_guard", check_git_secret_hygiene_guard),
    ]
    for name, check in checks:
        check()
        print(f"[vision-regression] PASS {name}")
    print(f"vision_regression_checks: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
