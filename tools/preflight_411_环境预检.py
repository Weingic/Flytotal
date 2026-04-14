# Purpose: Run 4.11 preflight checks (serial/web/USB/vision runtime) before single-node acceptance.
import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"


def find_tool_script(prefix: str) -> Path:
    matches = sorted(TOOLS_DIR.glob(f"{prefix}*.py"))
    if matches:
        return matches[0]
    return TOOLS_DIR / f"{prefix}.py"


USB_CHECK_SCRIPT = find_tool_script("usb_camera_readiness_check_")
VISION_BRIDGE_SCRIPT = find_tool_script("vision_bridge_")

def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def fetch_health(base_url: str, timeout_s: float) -> tuple[bool, dict[str, Any], str]:
    url = f"{base_url.rstrip('/')}/api/health"
    try:
        with urlopen(url, timeout=max(0.2, float(timeout_s))) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except URLError as exc:
        return False, {}, f"request_failed:{exc}"
    except Exception as exc:  # pragma: no cover
        return False, {}, f"request_failed:{exc}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False, {}, "invalid_json"
    if not isinstance(payload, dict):
        return False, {}, "invalid_payload"
    if bool(payload.get("ok")):
        return True, payload, ""
    return False, payload, "ok_false"


def parse_host_port(base_url: str) -> tuple[str, int]:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
    return host, port


def check_tcp_port(host: str, port: int, timeout_s: float) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(max(0.2, float(timeout_s)))
    try:
        sock.connect((host, int(port)))
        return True, ""
    except Exception as exc:
        return False, str(exc)
    finally:
        sock.close()


def list_serial_ports() -> tuple[list[str], str]:
    try:
        import serial.tools.list_ports as list_ports
    except Exception as exc:
        return [], f"pyserial_unavailable:{exc}"
    return [str(item.device) for item in list_ports.comports()], ""


def run_usb_check(python_exe: str, usb_report_file: Path) -> tuple[int, str]:
    command = [python_exe, str(USB_CHECK_SCRIPT), "--report-file", usb_report_file.as_posix()]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    output = (completed.stdout or "").strip()
    return int(completed.returncode), output


def tail_lines(text: str, max_lines: int = 20) -> str:
    rows = [line for line in str(text or "").splitlines() if line.strip()]
    if not rows:
        return ""
    return "\n".join(rows[-max(1, int(max_lines)):])


def evaluate_vision_runtime(status_file: Path, max_stale_ms: int) -> tuple[bool, dict[str, Any], str]:
    now_ms = int(time.time() * 1000)
    info: dict[str, Any] = {
        "status_file": status_file.as_posix(),
        "status_file_exists": status_file.exists(),
        "timestamp_ms": 0,
        "stale_age_ms": 0,
        "max_stale_ms": max(1, int(max_stale_ms)),
        "source_ready": 0,
        "tracker_ready": 0,
        "vision_chain_ready": 0,
        "runtime_ready": False,
        "reason": "",
    }

    if not status_file.exists():
        info["reason"] = "vision_status_file_missing"
        return False, info, str(info["reason"])

    payload = load_json(status_file)
    if not payload:
        info["reason"] = "vision_status_payload_invalid"
        return False, info, str(info["reason"])

    timestamp_ms = int(payload.get("timestamp_ms", 0) or 0)
    source_ready = int(payload.get("source_ready", 0) or 0)
    tracker_ready = int(payload.get("tracker_ready", 0) or 0)
    vision_chain_ready = int(payload.get("vision_chain_ready", 0) or 0)
    stale_age_ms = max(0, now_ms - timestamp_ms) if timestamp_ms > 0 else max(1, int(max_stale_ms)) + 1

    info["timestamp_ms"] = timestamp_ms
    info["stale_age_ms"] = stale_age_ms
    info["source_ready"] = source_ready
    info["tracker_ready"] = tracker_ready
    info["vision_chain_ready"] = vision_chain_ready

    if timestamp_ms <= 0:
        reason = "vision_status_timestamp_missing"
    elif stale_age_ms > max(1, int(max_stale_ms)):
        reason = f"vision_status_stale:{stale_age_ms}ms"
    elif source_ready != 1:
        reason = "vision_source_not_ready"
    elif tracker_ready != 1:
        reason = "vision_tracker_not_ready"
    elif vision_chain_ready != 1:
        reason = "vision_chain_not_ready"
    else:
        reason = ""

    runtime_ready = reason == ""
    info["runtime_ready"] = runtime_ready
    info["reason"] = reason
    return runtime_ready, info, reason


def main() -> int:
    parser = argparse.ArgumentParser(description="4.11 preflight checks for single-node startup")
    parser.add_argument("--python-exe", default=sys.executable, help="Python executable used for nested checks")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Vision web base URL")
    parser.add_argument("--port", default="COM4", help="Expected serial port, for example COM4")
    parser.add_argument("--timeout-s", type=float, default=1.2, help="Timeout for network checks")
    parser.add_argument("--skip-usb", action="store_true", help="Skip USB camera checks in preflight")
    parser.add_argument("--refresh-usb-check", action=argparse.BooleanOptionalAction, default=True, help="Run usb readiness check before evaluating camera status")
    parser.add_argument("--skip-vision-runtime-check", action="store_true", help="Skip vision runtime gate (latest_status freshness + ready flags)")
    parser.add_argument("--vision-status-file", type=Path, default=Path("captures/latest_status.json"), help="Vision runtime status JSON path")
    parser.add_argument("--vision-max-stale-ms", type=int, default=6000, help="Max allowed stale age for vision status JSON")
    parser.add_argument("--usb-report-file", type=Path, default=Path("captures/latest_usb_camera_readiness_report.json"), help="USB readiness report path")
    parser.add_argument("--report-file", type=Path, default=Path("captures/latest_411_preflight_report.json"), help="Output preflight report path")
    args = parser.parse_args()

    usb_report_file = resolve_path(args.usb_report_file)
    vision_status_file = resolve_path(args.vision_status_file)
    report_file = resolve_path(args.report_file)
    expected_port = str(args.port).strip() or "COM4"
    base_url = str(args.base_url).strip() or "http://127.0.0.1:8765"

    blocking_failures: list[str] = []
    non_blocking_warnings: list[str] = []
    acceptance_blocking_failures: list[str] = []
    hints: list[str] = []

    serial_ports, serial_error = list_serial_ports()
    serial_port_ready = expected_port in serial_ports
    if serial_error:
        blocking_failures.append(serial_error)
        acceptance_blocking_failures.append(serial_error)
    elif not serial_port_ready:
        serial_missing = f"serial_port_missing:{expected_port}"
        blocking_failures.append(serial_missing)
        acceptance_blocking_failures.append(serial_missing)
        hints.append("Check USB cable/driver and verify the device COM port is visible, then retry.")

    host, tcp_port = parse_host_port(base_url)
    tcp_open, tcp_error = check_tcp_port(host, tcp_port, args.timeout_s)
    web_health_ok = False
    health_payload: dict[str, Any] = {}
    health_error = ""
    if tcp_open:
        web_health_ok, health_payload, health_error = fetch_health(base_url, args.timeout_s)
        if not web_health_ok:
            health_failure = f"web_health_unavailable:{health_error}"
            blocking_failures.append(health_failure)
            acceptance_blocking_failures.append(health_failure)
            hints.append("Port is reachable but /api/health is unavailable: restart vision_web_server.")
    else:
        web_not_ready = "web_service_not_running_yet"
        non_blocking_warnings.append(web_not_ready)
        acceptance_blocking_failures.append(web_not_ready)
        hints.append("Web service is not running yet: start `python tools/vision_web_server_视觉网页服务.py` first.")

    vision_runtime_ready = True
    vision_runtime_error = ""
    vision_runtime_info: dict[str, Any] = {
        "status_file": vision_status_file.as_posix(),
        "skip_vision_runtime_check": bool(args.skip_vision_runtime_check),
        "runtime_ready": True,
        "reason": "",
    }
    if not bool(args.skip_vision_runtime_check):
        vision_runtime_ready, vision_runtime_info, vision_runtime_error = evaluate_vision_runtime(
            vision_status_file,
            max(1, int(args.vision_max_stale_ms)),
        )
        vision_runtime_info["skip_vision_runtime_check"] = False
        if not vision_runtime_ready:
            vision_not_ready = f"vision_runtime_not_ready:{vision_runtime_error}"
            non_blocking_warnings.append(vision_not_ready)
            acceptance_blocking_failures.append(vision_not_ready)
            hints.append(
                "Vision bridge not ready yet: run "
                f"`python tools/{VISION_BRIDGE_SCRIPT.name} --backend dshow --source 0 --tracker csrt --tracker-fallback auto --source-warmup-frames 12`."
            )

    usb_check_rc = 0
    usb_check_output_tail = ""
    usb_result = "SKIPPED" if bool(args.skip_usb) else "UNKNOWN"
    usb_ready_count = 0
    if not bool(args.skip_usb):
        if bool(args.refresh_usb_check):
            usb_check_rc, usb_output = run_usb_check(str(args.python_exe), usb_report_file)
            usb_check_output_tail = tail_lines(usb_output, 18)

        usb_report = load_json(usb_report_file)
        usb_result = str(usb_report.get("result", "UNKNOWN")).upper() if usb_report else "UNKNOWN"
        usb_probe = usb_report.get("probe", {}) if isinstance(usb_report, dict) else {}
        usb_ready_count = int((usb_probe.get("ready_count", 0) or 0) if isinstance(usb_probe, dict) else 0)
        if usb_result != "PASS":
            usb_not_pass = f"usb_report_not_pass:{usb_result}"
            blocking_failures.append(usb_not_pass)
            acceptance_blocking_failures.append(usb_not_pass)
        if usb_ready_count <= 0:
            usb_ready_zero = "usb_camera_ready_count_zero"
            blocking_failures.append(usb_ready_zero)
            acceptance_blocking_failures.append(usb_ready_zero)
            hints.append("Close apps occupying camera devices, then run USB camera readiness check separately.")

    # Keep legacy fields for compatibility while exposing explicit startup/acceptance gates.
    failures = list(dict.fromkeys(blocking_failures))
    warnings = list(dict.fromkeys(non_blocking_warnings))
    acceptance_blocking_failures = list(dict.fromkeys(acceptance_blocking_failures))
    can_start_live_stack = len(failures) == 0
    can_run_acceptance = len(acceptance_blocking_failures) == 0
    if failures:
        result = "FAIL"
    elif warnings:
        result = "WARN"
    else:
        result = "PASS"
    report = {
        "checked_ms": int(time.time() * 1000),
        "result": result,
        "base_url": base_url,
        "expected_serial_port": expected_port,
        "serial_ports": serial_ports,
        "serial_port_ready": serial_port_ready,
        "web": {
            "host": host,
            "port": tcp_port,
            "tcp_open": tcp_open,
            "tcp_error": tcp_error,
            "health_ok": web_health_ok,
            "health_error": health_error,
            "health_payload": health_payload,
        },
        "vision": vision_runtime_info,
        "usb": {
            "skip_usb": bool(args.skip_usb),
            "refresh_usb_check": bool(args.refresh_usb_check),
            "usb_check_returncode": usb_check_rc,
            "usb_check_output_tail": usb_check_output_tail,
            "usb_report_file": usb_report_file.as_posix(),
            "usb_result": usb_result,
            "usb_ready_count": usb_ready_count,
        },
        "can_start_live_stack": can_start_live_stack,
        "can_run_acceptance": can_run_acceptance,
        "blocking_failure_count": len(failures),
        "blocking_failures": failures,
        "non_blocking_warning_count": len(warnings),
        "non_blocking_warnings": warnings,
        "acceptance_blocking_failure_count": len(acceptance_blocking_failures),
        "acceptance_blocking_failures": acceptance_blocking_failures,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "hints": hints,
    }
    write_json(report_file, report)

    print("4.11 Preflight Report")
    print(f"result={result}")
    print(f"serial_port_ready={int(serial_port_ready)}")
    print(f"web_health_ok={int(web_health_ok)}")
    print(f"vision_runtime_ready={int(vision_runtime_ready)}")
    if not bool(args.skip_vision_runtime_check):
        print(f"vision_status_stale_age_ms={int(vision_runtime_info.get('stale_age_ms', 0) or 0)}")
    print(f"usb_result={usb_result}")
    print(f"usb_ready_count={usb_ready_count}")
    print(f"can_start_live_stack={int(can_start_live_stack)}")
    print(f"can_run_acceptance={int(can_run_acceptance)}")
    print(f"failure_count={len(failures)}")
    print(f"warning_count={len(warnings)}")
    print(f"report_file={report_file.as_posix()}")
    for item in failures:
        print(f"- {item}")
    for item in hints:
        line = f"- hint:{item}"
        try:
            print(line)
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or "utf-8"
            safe_line = line.encode(encoding, errors="replace").decode(encoding, errors="replace")
            print(safe_line)

    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

