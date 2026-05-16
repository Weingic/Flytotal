from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATUS_FILE = PROJECT_ROOT / "captures" / "e2e_node_status.json"
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "datasets" / "drone_recognition" / "real_tracks.csv"
FIELDNAMES = ("timestamp_ms", "track_id", "x_mm", "y_mm", "vx_mm_s", "vy_mm_s", "label")


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


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


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def sanitize_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return token.strip("_.-") or "session"


def build_track_id(label: str, session_id: str, node_track_id: int) -> str:
    return f"{sanitize_token(label)}_{sanitize_token(session_id)}_t{node_track_id}"


def output_has_header(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            first_line = handle.readline().strip()
    except OSError:
        return False
    return first_line.split(",")[: len(FIELDNAMES)] == list(FIELDNAMES)


def append_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output_has_header(path)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def collect(args: argparse.Namespace) -> int:
    status_file = resolve_path(args.status)
    output_file = resolve_path(args.output)
    label = sanitize_token(args.label.lower())
    session_id = args.session_id or time.strftime("%Y%m%d_%H%M%S")
    interval_s = max(0.05, args.interval_ms / 1000.0)
    deadline = time.monotonic() + max(0.1, args.duration_s)
    rows: list[dict[str, object]] = []
    skipped_inactive = 0
    skipped_stale = 0
    reads = 0
    start = time.monotonic()

    print(
        "DATASET,COLLECT_START,"
        f"label={label},duration_s={args.duration_s},interval_ms={args.interval_ms},"
        f"status={status_file},output={output_file},session_id={session_id},active_only={int(args.active_only)}"
    )

    try:
        while time.monotonic() < deadline:
            status = read_json(status_file)
            reads += 1
            if not status:
                skipped_stale += 1
                time.sleep(interval_s)
                continue

            available = safe_int(status.get("available", status.get("ok", 0)), 0)
            stale_age_ms = safe_int(status.get("stale_age_ms", 0), 0)
            if not args.allow_stale and (available == 0 or stale_age_ms > args.max_stale_ms):
                skipped_stale += 1
                time.sleep(interval_s)
                continue

            track_active = safe_int(status.get("track_active", 0), 0)
            track_confirmed = safe_int(status.get("track_confirmed", 0), 0)
            if args.active_only and track_active == 0 and track_confirmed == 0:
                skipped_inactive += 1
                time.sleep(interval_s)
                continue

            node_track_id = safe_int(status.get("track_id", 0), 0)
            rows.append(
                {
                    "timestamp_ms": int((time.monotonic() - start) * 1000),
                    "track_id": build_track_id(label, session_id, node_track_id),
                    "x_mm": round(safe_float(status.get("x_mm", 0.0)), 3),
                    "y_mm": round(safe_float(status.get("y_mm", 0.0)), 3),
                    "vx_mm_s": round(safe_float(status.get("vx_mm_s", 0.0)), 3),
                    "vy_mm_s": round(safe_float(status.get("vy_mm_s", 0.0)), 3),
                    "label": label,
                }
            )
            time.sleep(interval_s)
    except KeyboardInterrupt:
        print("DATASET,COLLECT_INTERRUPTED")

    if not rows:
        print(
            "DATASET,COLLECT_DONE,result=NO_ROWS,"
            f"reads={reads},skipped_stale={skipped_stale},skipped_inactive={skipped_inactive}"
        )
        return 2

    append_rows(output_file, rows)
    print(
        "DATASET,COLLECT_DONE,result=OK,"
        f"rows={len(rows)},reads={reads},skipped_stale={skipped_stale},"
        f"skipped_inactive={skipped_inactive},output={output_file}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect NodeA track snapshots into the drone recognition CSV format.")
    parser.add_argument("--label", required=True, help="Ground-truth label, for example drone, person, bird, car, clutter.")
    parser.add_argument("--duration-s", type=float, default=30.0, help="Recording duration in seconds.")
    parser.add_argument("--interval-ms", type=int, default=200, help="Sampling interval in milliseconds.")
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS_FILE, help="NodeA status JSON file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE, help="Output CSV file.")
    parser.add_argument("--session-id", default="", help="Optional stable session id used in generated track_id values.")
    parser.add_argument("--active-only", action="store_true", help="Only write rows while NodeA has an active/confirmed track.")
    parser.add_argument("--allow-stale", action="store_true", help="Allow stale or unavailable status rows.")
    parser.add_argument("--max-stale-ms", type=int, default=3000, help="Maximum accepted status stale age.")
    return collect(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
