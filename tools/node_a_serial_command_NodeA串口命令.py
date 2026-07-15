import argparse
import json
import os
import time
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INBOX_DIR = Path("captures/serial_command_inbox")
DEFAULT_TTL_MS = 30_000
MAX_COMMAND_BYTES = 192


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def normalize_command(command: str) -> str:
    line = str(command or "").strip()
    if not line:
        raise ValueError("command is empty")
    if "\r" in line or "\n" in line:
        raise ValueError("command must contain exactly one line")
    if len(line.encode("utf-8")) > MAX_COMMAND_BYTES:
        raise ValueError(f"command exceeds {MAX_COMMAND_BYTES} bytes")
    return line


def submit_command(inbox_dir: Path, command: str, ttl_ms: int, index: int) -> tuple[str, Path]:
    line = normalize_command(command)
    created_ms = int(time.time() * 1000)
    request_id = f"{created_ms}-{os.getpid()}-{index:02d}-{uuid.uuid4().hex[:8]}"
    payload = {
        "version": 1,
        "id": request_id,
        "created_ms": created_ms,
        "ttl_ms": max(1, int(ttl_ms)),
        "command": line,
    }
    inbox_dir.mkdir(parents=True, exist_ok=True)
    request_path = inbox_dir / f"{request_id}.json"
    temp_path = inbox_dir / f".{request_id}.tmp"
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(request_path)
    return request_id, request_path


def submit_commands(
    inbox_dir: Path,
    commands: list[str],
    ttl_ms: int,
    interval_s: float = 0.0,
    *,
    sleep_fn=time.sleep,
) -> list[tuple[str, Path]]:
    delay_s = float(interval_s)
    if delay_s < 0.0:
        raise ValueError("interval_s must be >= 0")
    submitted: list[tuple[str, Path]] = []
    for index, command in enumerate(commands, start=1):
        submitted.append(submit_command(inbox_dir, command, ttl_ms, index))
        if index < len(commands) and delay_s > 0.0:
            sleep_fn(delay_s)
    return submitted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit Node A commands to the running serial bridge without opening COM"
    )
    parser.add_argument("command", nargs="+", help="One or more quoted firmware commands")
    parser.add_argument(
        "--inbox-dir",
        type=Path,
        default=DEFAULT_INBOX_DIR,
        help="Serial bridge command inbox directory",
    )
    parser.add_argument(
        "--ttl-ms",
        type=int,
        default=DEFAULT_TTL_MS,
        help="Request lifetime in milliseconds; expired commands are never replayed",
    )
    parser.add_argument(
        "--interval-s",
        type=float,
        default=0.0,
        help="Delay between request files; use a positive value for repeated state commands",
    )
    args = parser.parse_args()

    inbox_dir = resolve_path(args.inbox_dir)
    try:
        submitted = submit_commands(
            inbox_dir,
            args.command,
            max(1, args.ttl_ms),
            args.interval_s,
        )
    except (OSError, ValueError) as exc:
        print(f"SERIAL_COMMAND_SUBMIT_FAILED,error={type(exc).__name__},detail={exc}")
        return 1

    for request_id, request_path in submitted:
        print(
            "SERIAL_COMMAND_SUBMITTED,"
            f"id={request_id},file={request_path.as_posix()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
