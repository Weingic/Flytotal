# ??????????????????????????????????????????????
import json
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def load_json_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": True, "available": False}
    last_text = ""
    for attempt in range(6):
        try:
            last_text = path.read_text(encoding="utf-8")
            break
        except (PermissionError, OSError):
            if attempt >= 5:
                return {"ok": False, "available": False, "error": "read_denied"}
            time.sleep(0.03)
    try:
        payload = json.loads(last_text)
    except json.JSONDecodeError:
        return {"ok": False, "available": False}
    if not isinstance(payload, dict):
        return {"ok": False, "available": False}
    payload.setdefault("ok", True)
    return payload


def sanitize_token(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    return cleaned.strip("_") or "session"


def split_serial_prefix(line: str) -> tuple[str, list[str]]:
    text = line.strip()
    if not text:
        return "", []

    parts = [part.strip() for part in text.split(",")]
    prefix_parts: list[str] = []
    field_start = len(parts)

    for index, part in enumerate(parts):
        if "=" in part:
            field_start = index
            break
        prefix_parts.append(part)

    prefix = ",".join(prefix_parts) if prefix_parts else parts[0]
    return prefix, parts[field_start:]


def parse_serial_fields(line: str) -> dict[str, str]:
    _, field_parts = split_serial_prefix(line)
    fields: dict[str, str] = {}
    for part in field_parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def build_serial_record(line: str) -> dict[str, Any]:
    prefix, _ = split_serial_prefix(line)
    fields = parse_serial_fields(line)
    return {
        "raw": line.strip(),
        "command": line.split(",", 1)[0].strip() if line.strip() else "",
        "prefix": prefix,
        "fields": fields,
    }


def session_log_path_from_payload(session_payload: dict[str, Any], session_log_dir: Path) -> Path | None:
    if not bool(session_payload.get("available")):
        return None

    started_ms = int(session_payload.get("started_ms") or 0)
    scenario_name = sanitize_token(str(session_payload.get("scenario_name", "")))
    if started_ms <= 0:
        return None

    session_log_dir.mkdir(parents=True, exist_ok=True)
    return session_log_dir / f"{started_ms}_{scenario_name}.jsonl"


def append_session_event(
    session_payload: dict[str, Any],
    session_log_dir: Path,
    source: str,
    event_type: str,
    payload: dict[str, Any],
) -> Path | None:
    log_path = session_log_path_from_payload(session_payload, session_log_dir)
    if log_path is None:
        return None

    record = {
        "ts_ms": int(time.time() * 1000),
        "source": source,
        "event_type": event_type,
        "scenario_name": session_payload.get("scenario_name", ""),
        "started_ms": int(session_payload.get("started_ms") or 0),
        "payload": payload,
    }
    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")
    return log_path
