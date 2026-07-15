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
DEFAULT_STATUS_FILE = PROJECT_ROOT / "captures" / "latest_node_status.json"
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "datasets" / "drone_recognition" / "real_tracks.csv"
FIELDNAMES = ("timestamp_ms", "track_id", "x_mm", "y_mm", "vx_mm_s", "vy_mm_s", "label")
MIN_REAL_EPOCH_MS = 946_684_800_000


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


def compute_status_stale_age_ms(
    status: dict[str, Any],
    status_file: Path,
    *,
    now_ms: int | None = None,
) -> int:
    current_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    reported_age_ms = max(0, safe_int(status.get("stale_age_ms", 0), 0))

    try:
        file_updated_ms = int(status_file.stat().st_mtime * 1000)
    except OSError:
        return current_ms

    file_age_ms = max(0, current_ms - file_updated_ms)
    ages_ms = [file_age_ms, reported_age_ms + file_age_ms]

    last_update_ms = safe_int(status.get("last_update_ms", 0), 0)
    if last_update_ms >= MIN_REAL_EPOCH_MS:
        ages_ms.append(max(0, current_ms - last_update_ms))

    return max(ages_ms)


def status_is_collectible(
    status: dict[str, Any],
    status_file: Path,
    *,
    max_stale_ms: int,
    allow_stale: bool = False,
    now_ms: int | None = None,
) -> tuple[bool, int, str]:
    effective_age_ms = compute_status_stale_age_ms(status, status_file, now_ms=now_ms)
    if allow_stale:
        return True, effective_age_ms, "ALLOW_STALE"

    available = safe_int(status.get("available", status.get("ok", 0)), 0)
    if available == 0:
        return False, effective_age_ms, "UNAVAILABLE"

    online = safe_int(status.get("online", 1), 1)
    if online == 0:
        return False, effective_age_ms, "OFFLINE"

    if max_stale_ms < 0:
        return False, effective_age_ms, "INVALID_MAX_STALE_MS"
    if effective_age_ms > max_stale_ms:
        return False, effective_age_ms, "STALE"

    return True, effective_age_ms, "OK"


def track_is_collectible(status: dict[str, Any], *, active_only: bool) -> bool:
    if not active_only:
        return True
    track_active = safe_int(status.get("track_active", 0), 0)
    track_confirmed = safe_int(status.get("track_confirmed", 0), 0)
    return track_active != 0 and track_confirmed != 0


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
    return first_line.split(",") == list(FIELDNAMES)


def inspect_existing_output(
    path: Path,
    *,
    label: str,
    session_id: str,
) -> tuple[str, set[str]]:
    try:
        if not path.exists() or path.stat().st_size == 0:
            return "NEW", set()
    except OSError:
        return "READ_ERROR", set()

    track_prefix = f"{sanitize_token(label)}_{sanitize_token(session_id)}_t"
    matching_track_ids: set[str] = set()
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != FIELDNAMES:
                return "SCHEMA_MISMATCH", set()
            for row in reader:
                track_id = str(row.get("track_id", "") or "")
                if track_id.startswith(track_prefix):
                    matching_track_ids.add(track_id)
    except (OSError, UnicodeDecodeError, csv.Error):
        return "READ_ERROR", set()
    return "OK", matching_track_ids


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
    last_gate_reason = "NOT_READ"
    last_effective_age_ms = -1

    print(
        "DATASET,COLLECT_START,"
        f"label={label},duration_s={args.duration_s},interval_ms={args.interval_ms},"
        f"status={status_file},output={output_file},session_id={session_id},active_only={int(args.active_only)},"
        f"max_stale_ms={args.max_stale_ms},allow_stale={int(args.allow_stale)},"
        f"allow_session_reuse={int(args.allow_session_reuse)}"
    )

    output_state, existing_track_ids = inspect_existing_output(
        output_file,
        label=label,
        session_id=session_id,
    )
    if output_state in {"SCHEMA_MISMATCH", "READ_ERROR"}:
        print(f"DATASET,COLLECT_ABORT,reason=OUTPUT_{output_state},output={output_file}")
        return 4
    if existing_track_ids and not args.allow_session_reuse:
        print(
            "DATASET,COLLECT_ABORT,reason=SESSION_ID_EXISTS,"
            f"session_id={sanitize_token(session_id)},existing_track_count={len(existing_track_ids)},"
            "next_step=USE_NEW_SESSION_ID"
        )
        return 3
    if existing_track_ids:
        print(
            "DATASET,COLLECT_WARNING,reason=SESSION_ID_REUSE_ALLOWED,"
            f"session_id={sanitize_token(session_id)},existing_track_count={len(existing_track_ids)}"
        )

    try:
        while time.monotonic() < deadline:
            status = read_json(status_file)
            reads += 1
            if not status:
                skipped_stale += 1
                last_gate_reason = "READ_ERROR"
                last_effective_age_ms = -1
                time.sleep(interval_s)
                continue

            collectible, effective_age_ms, gate_reason = status_is_collectible(
                status,
                status_file,
                max_stale_ms=args.max_stale_ms,
                allow_stale=args.allow_stale,
            )
            last_gate_reason = gate_reason
            last_effective_age_ms = effective_age_ms
            if not collectible:
                skipped_stale += 1
                time.sleep(interval_s)
                continue

            if not track_is_collectible(status, active_only=args.active_only):
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
            f"reads={reads},skipped_stale={skipped_stale},skipped_inactive={skipped_inactive},"
            f"last_gate_reason={last_gate_reason},last_effective_stale_ms={last_effective_age_ms}"
        )
        return 2

    append_rows(output_file, rows)
    print(
        "DATASET,COLLECT_DONE,result=OK,"
        f"rows={len(rows)},reads={reads},skipped_stale={skipped_stale},"
        f"skipped_inactive={skipped_inactive},last_gate_reason={last_gate_reason},"
        f"last_effective_stale_ms={last_effective_age_ms},output={output_file}"
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
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Only write rows while NodeA reports both an active and confirmed track.",
    )
    parser.add_argument("--allow-stale", action="store_true", help="Allow stale or unavailable status rows.")
    parser.add_argument(
        "--allow-session-reuse",
        action="store_true",
        help="Allow appending to a session id already present in the output CSV; debugging only.",
    )
    parser.add_argument("--max-stale-ms", type=int, default=3000, help="Maximum accepted status stale age.")
    return collect(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
