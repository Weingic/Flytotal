from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


LEVEL_VALUE = {"NONE": 0, "LOW": 1, "MID": 2, "HIGH": 3}
VALUE_LEVEL = {value: key for key, value in LEVEL_VALUE.items()}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "locked", "matched", "online"}


def classify(stage: str, ld2451: bool, ld2450: bool, rid: bool, vision: bool, held_ms: int) -> dict[str, object]:
    votes = sum([ld2451, ld2450, rid, vision])
    high_ready = votes >= 2 and held_ms >= 800
    level = "NONE"
    reason = "NONE"
    if stage == "FAR":
        if ld2451 and rid:
            level, reason = "MID", "FAR_LD2451_RID"
        elif ld2451:
            level, reason = "LOW", "FAR_LD2451_WARNING"
    elif stage == "MID":
        if high_ready:
            level, reason = "HIGH", "MID_MULTI_SOURCE_HELD"
        elif votes >= 2:
            level, reason = "MID", "MID_WAIT_WINDOW"
        elif votes == 1:
            level, reason = "LOW", "MID_SINGLE_SOURCE"
    elif stage == "NEAR":
        if high_ready and (vision or rid):
            level, reason = "HIGH", "NEAR_CONFIRMED"
        elif votes >= 2:
            level, reason = "MID", "NEAR_NEEDS_VISUAL_OR_RID"
        elif votes == 1:
            level, reason = "LOW", "NEAR_SINGLE_SOURCE"
    confidence = min(1.0, votes * 0.22 + (0.1 if high_ready else 0.0))
    return {
        "stage": stage,
        "fusion_level": level,
        "fusion_confidence": round(confidence, 2),
        "fusion_reason": reason,
        "source_vote_count": votes,
    }


def run_far_mid_near() -> list[dict[str, object]]:
    return [
        {"timestamp_ms": 0, "range_m": 80, **classify("FAR", True, False, False, False, 1000)},
        {"timestamp_ms": 800, "range_m": 80, **classify("FAR", True, False, True, False, 1000)},
        {"timestamp_ms": 1600, "range_m": 25, **classify("MID", True, True, False, False, 300)},
        {"timestamp_ms": 2400, "range_m": 25, **classify("MID", True, True, False, False, 900)},
        {"timestamp_ms": 3200, "range_m": 8, **classify("NEAR", True, True, False, False, 900)},
        {"timestamp_ms": 4000, "range_m": 8, **classify("NEAR", True, True, False, True, 900)},
    ]


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("records", "rows", "events", "timeline", "samples"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def load_json_records(input_path: Path) -> tuple[str, list[dict[str, Any]]]:
    files: list[Path]
    if input_path.is_dir():
        files = sorted(
            path
            for path in input_path.rglob("*.json")
            if path.is_file() and "v5_2" not in path.parts and "event_exports" not in path.parts
        )
        session_name = input_path.name or "captures"
    else:
        files = [input_path]
        session_name = input_path.stem

    rows: list[dict[str, Any]] = []
    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        for record in extract_records(payload):
            record = dict(record)
            record.setdefault("_source_file", file_path.as_posix())
            rows.append(record)
    rows.sort(key=lambda item: safe_int(item.get("timestamp_ms", item.get("host_logged_ms", item.get("last_update_ms", 0))), 0))
    return session_name, rows


def infer_stage(record: dict[str, Any]) -> str:
    explicit = str(record.get("fusion_stage", "") or "").strip().upper()
    if explicit in {"FAR", "MID", "NEAR"}:
        return explicit
    range_m = safe_float(record.get("ld2451_range_m", record.get("range_m", 0.0)), 0.0)
    x_mm = safe_float(record.get("x_mm", record.get("x", 0.0)), 0.0)
    y_mm = safe_float(record.get("y_mm", record.get("y", 0.0)), 0.0)
    near_range_m = math.hypot(x_mm, y_mm) / 1000.0 if x_mm or y_mm else 0.0
    effective = range_m if range_m > 0 else near_range_m
    if effective <= 0:
        return "NONE"
    if effective > 30:
        return "FAR"
    if effective >= 10:
        return "MID"
    return "NEAR"


def sources_from(record: dict[str, Any]) -> dict[str, bool]:
    near_radar = safe_bool(record.get("track_confirmed")) or safe_bool(record.get("track_active")) or safe_int(record.get("track_id", 0)) > 0
    far_radar = safe_bool(record.get("far_motion_trigger")) or safe_bool(record.get("ld2451_valid")) or safe_float(record.get("ld2451_range_m", 0.0)) > 0
    rid_text = str(record.get("rid_status", record.get("rid", "")) or "").upper()
    rid = safe_bool(record.get("rid_matched")) or "MATCH" in rid_text or "REMOTE_ID" in rid_text
    vision_state = str(record.get("vision_state", record.get("tracker_state", "")) or "").upper()
    vision = (
        safe_bool(record.get("vision_locked"))
        or safe_float(record.get("vision_confidence", 0.0)) >= 0.5
        or "LOCKED" in vision_state
        or "TRACKING" in vision_state
    )
    return {
        "near_radar": near_radar,
        "far_radar": far_radar,
        "radar": near_radar or far_radar,
        "rid": rid,
        "vision": vision,
    }


def legacy_level(record: dict[str, Any]) -> tuple[str, int, str]:
    sources = sources_from(record)
    votes = sum([sources["radar"], sources["rid"], sources["vision"]])
    if votes >= 3:
        return "HIGH", votes, "LEGACY_3_SOURCE"
    if votes == 2:
        return "MID", votes, "LEGACY_2_SOURCE"
    if votes == 1:
        return "LOW", votes, "LEGACY_1_SOURCE"
    return "NONE", votes, "LEGACY_NONE"


def advanced_level(record: dict[str, Any], held_ms: int = 900) -> dict[str, Any]:
    sources = sources_from(record)
    stage = infer_stage(record)
    return classify(
        stage,
        sources["far_radar"],
        sources["near_radar"],
        sources["rid"],
        sources["vision"],
        held_ms,
    )


def compare_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        timestamp_ms = safe_int(
            record.get("timestamp_ms", record.get("host_logged_ms", record.get("last_update_ms", index * 200))),
            index * 200,
        )
        old_level, old_votes, old_reason = legacy_level(record)
        new_result = advanced_level(record)
        rows.append(
            {
                "timestamp_ms": timestamp_ms,
                "old_fusion_level": old_level,
                "old_fusion_value": LEVEL_VALUE[old_level],
                "old_source_vote_count": old_votes,
                "old_reason": old_reason,
                "new_fusion_level": new_result["fusion_level"],
                "new_fusion_value": LEVEL_VALUE[str(new_result["fusion_level"])],
                "new_fusion_stage": new_result["stage"],
                "new_fusion_confidence": new_result["fusion_confidence"],
                "new_fusion_reason": new_result["fusion_reason"],
                "source_file": record.get("_source_file", ""),
            }
        )
    return rows


def write_plot(rows: list[dict[str, Any]], output_path: Path) -> str:
    if not rows:
        return ""
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        return ""

    x_values = [safe_int(row.get("timestamp_ms", 0), 0) / 1000.0 for row in rows]
    old_values = [safe_int(row.get("old_fusion_value", 0), 0) for row in rows]
    new_values = [safe_int(row.get("new_fusion_value", 0), 0) for row in rows]
    confidence = [safe_float(row.get("new_fusion_confidence", 0.0), 0.0) * 3.0 for row in rows]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 4.8))
    plt.step(x_values, old_values, where="post", label="old three-source count", linewidth=2)
    plt.step(x_values, new_values, where="post", label="v5.2 staged fusion", linewidth=2)
    plt.plot(x_values, confidence, label="v5.2 confidence x3", linewidth=1.6, alpha=0.8)
    plt.yticks([0, 1, 2, 3], ["NONE", "LOW", "MID", "HIGH"])
    plt.xlabel("time (s)")
    plt.ylabel("fusion level")
    plt.title("Flytotal fusion comparison")
    plt.grid(True, alpha=0.28)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Flytotal v5.2 fusion stage simulator")
    parser.add_argument("--case", default="far_mid_near", choices=["far_mid_near"])
    parser.add_argument("--input", type=Path, default=None, help="Status JSON file or directory containing history JSON")
    parser.add_argument("--compare", action="store_true", help="Compare old three-source count against v5.2 staged fusion")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=None, help="Legacy JSON output path")
    args = parser.parse_args()

    if args.input:
        session_name, records = load_json_records(args.input)
        rows = compare_records(records)
        output_dir = args.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in session_name) or "session"
        json_path = output_dir / f"fusion_compare_{stem}.json"
        png_path = output_dir / f"fusion_compare_{stem}.png"
        plot_path = write_plot(rows, png_path)
        summary = {
            "ok": True,
            "input": args.input.as_posix(),
            "compare": bool(args.compare),
            "record_count": len(records),
            "rows": rows,
            "plot_path": plot_path,
            "note": "" if records else "no_status_records_found",
        }
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json_path.as_posix())
        if plot_path:
            print(plot_path)
        return 0

    rows = run_far_mid_near()
    output_path = args.output or Path("captures/v5_2/fusion_simulator_far_mid_near.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"case": args.case, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.compare:
        compare_rows = compare_records(rows)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        compare_json = args.output_dir / "fusion_compare_far_mid_near.json"
        plot_path = write_plot(compare_rows, args.output_dir / "fusion_compare_far_mid_near.png")
        compare_json.write_text(
            json.dumps({"ok": True, "record_count": len(compare_rows), "rows": compare_rows, "plot_path": plot_path}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(output_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
