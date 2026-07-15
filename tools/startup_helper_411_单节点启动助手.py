# Purpose: Generate 4.11 single-node startup command chain with optional preflight and verification order output.
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"


def find_tool_script(prefix: str) -> Path:
    matches = sorted(TOOLS_DIR.glob(f"{prefix}*.py"))
    if matches:
        return matches[0]
    return TOOLS_DIR / f"{prefix}.py"


PREFLIGHT_SCRIPT = find_tool_script("preflight_411_")
NODE_BRIDGE_SCRIPT = find_tool_script("node_a_serial_bridge_")
VISION_BRIDGE_SCRIPT = find_tool_script("vision_bridge_")
WEB_SERVER_SCRIPT = find_tool_script("vision_web_server_")
ACCEPTANCE_FLOW_SCRIPT = find_tool_script("acceptance_flow_411_")
ACCEPTANCE_AUTO_SCRIPT = find_tool_script("acceptance_auto_411_")
USB_REPORT_DEFAULT = PROJECT_ROOT / "captures/latest_usb_camera_readiness_report.json"
PREFLIGHT_REPORT_DEFAULT = PROJECT_ROOT / "captures/latest_411_preflight_report.json"


def build_deployed_v4b_vision_command(
    python_cmd: str,
    *,
    source_index: int,
    backend: str,
    tracker: str,
    tracker_fallback: str,
    source_warmup_frames: int,
) -> str:
    normalized_backend = backend if backend in {"auto", "msmf", "dshow"} else "auto"
    normalized_tracker = tracker if tracker in {"csrt", "kcf", "mil"} else "csrt"
    normalized_fallback = tracker_fallback if tracker_fallback in {"auto", "off"} else "auto"
    return (
        f"{python_cmd} tools/{VISION_BRIDGE_SCRIPT.name} "
        f"--backend {normalized_backend} --source {max(0, int(source_index))} "
        f"--tracker {normalized_tracker} --tracker-fallback {normalized_fallback} "
        f"--source-warmup-frames {max(1, int(source_warmup_frames))} "
        "--yolo-enabled --yolo-model models/yolov8n_drone.onnx "
        "--yolo-class-ids 0 --yolo-class-names 0:drone "
        "--yolo-model-label drone-v4b-hardneg-deployed "
        "--yolo-score-threshold 0.45 --yolo-intra-op-threads 8 --yolo-auto-lock"
    )


def build_recommended_vision_command(python_cmd: str, recommended: dict[str, Any]) -> str:
    try:
        source_index = int(recommended.get("source_index", -1))
        source_warmup_frames = int(recommended.get("source_warmup_frames", 12))
    except (TypeError, ValueError):
        return ""
    tracker = str(recommended.get("tracker", "") or "").lower()
    if source_index < 0 or tracker not in {"csrt", "kcf", "mil"}:
        return ""
    return build_deployed_v4b_vision_command(
        python_cmd,
        source_index=source_index,
        backend=str(recommended.get("backend", "auto") or "auto").lower(),
        tracker=tracker,
        tracker_fallback=str(recommended.get("tracker_fallback", "auto") or "auto").lower(),
        source_warmup_frames=source_warmup_frames,
    )


def build_fallback_vision_command(python_cmd: str) -> str:
    return build_deployed_v4b_vision_command(
        python_cmd,
        source_index=0,
        backend="auto",
        tracker="csrt",
        tracker_fallback="auto",
        source_warmup_frames=12,
    )

def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def run_preflight(
    python_exe: str,
    port: str,
    base_url: str,
    refresh_usb_check: bool,
    usb_report_file: Path,
    preflight_report_file: Path,
) -> tuple[int, str]:
    command = [
        python_exe,
        str(PREFLIGHT_SCRIPT),
        "--port",
        port,
        "--base-url",
        base_url,
        "--usb-report-file",
        usb_report_file.as_posix(),
        "--report-file",
        preflight_report_file.as_posix(),
    ]
    command.append("--refresh-usb-check" if refresh_usb_check else "--no-refresh-usb-check")
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


def tail_lines(text: str, limit: int = 20) -> str:
    rows = [line for line in str(text or "").splitlines() if line.strip()]
    if not rows:
        return ""
    return "\n".join(rows[-max(1, int(limit)):])


def parse_suite_sequence(primary_suite: str, suite_chain_raw: str) -> list[str]:
    sequence: list[str] = []
    raw_value = str(suite_chain_raw or "").strip()
    if raw_value:
        normalized = raw_value.replace(";", ",")
        for token in normalized.split(","):
            suite_name = str(token).strip()
            if not suite_name:
                continue
            if suite_name in sequence:
                continue
            sequence.append(suite_name)

    primary = str(primary_suite or "").strip()
    if not sequence:
        if primary:
            sequence.append(primary)
        else:
            sequence.append("risk_event_vision_chain_v1")
    return sequence


def main() -> int:
    parser = argparse.ArgumentParser(description="4.11 startup helper: print stable multi-terminal command sequence")
    parser.add_argument("--python-cmd", default="python", help="Command prefix shown in generated commands")
    parser.add_argument("--python-exe", default=sys.executable, help="Python executable used by helper sub-steps")
    parser.add_argument("--port", default="COM4", help="Node A serial port, for example COM4")
    parser.add_argument("--baud", type=int, default=115200, help="Node A serial baud rate")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Vision web base URL")
    parser.add_argument("--suite", default="risk_event_vision_chain_v1", help="Suite used by acceptance flow")
    parser.add_argument(
        "--suite-chain",
        default="",
        help="Optional comma-separated suite chain, for example rid_identity_chain_v1,risk_event_vision_chain_v1",
    )
    parser.add_argument("--run-preflight", action=argparse.BooleanOptionalAction, default=True, help="Run preflight script before printing commands")
    parser.add_argument("--refresh-usb-check", action=argparse.BooleanOptionalAction, default=True, help="When preflight runs, whether to refresh usb readiness report")
    parser.add_argument("--usb-report-file", type=Path, default=USB_REPORT_DEFAULT, help="USB readiness report path")
    parser.add_argument("--preflight-report-file", type=Path, default=PREFLIGHT_REPORT_DEFAULT, help="Preflight report path")
    parser.add_argument("--output-file", type=Path, default=Path("captures/latest_411_startup_helper_plan.json"), help="Output startup plan JSON path")
    args = parser.parse_args()

    python_cmd = str(args.python_cmd).strip() or "python"
    python_exe = str(args.python_exe).strip() or sys.executable
    port_value = str(args.port).strip() or "COM4"
    baud_value = max(1, int(args.baud))
    base_url = str(args.base_url).strip() or "http://127.0.0.1:8765"
    suite_name = str(args.suite).strip() or "risk_event_vision_chain_v1"
    suite_chain_raw = str(args.suite_chain).strip()
    suite_names = parse_suite_sequence(suite_name, suite_chain_raw)
    suite_name = suite_names[0]
    suite_chain_value = ",".join(suite_names)
    usb_report_file = resolve_path(args.usb_report_file)
    preflight_report_file = resolve_path(args.preflight_report_file)
    output_file = resolve_path(args.output_file)

    preflight_returncode = 0
    preflight_output_tail = ""
    if bool(args.run_preflight):
        preflight_returncode, preflight_output = run_preflight(
            python_exe=python_exe,
            port=port_value,
            base_url=base_url,
            refresh_usb_check=bool(args.refresh_usb_check),
            usb_report_file=usb_report_file,
            preflight_report_file=preflight_report_file,
        )
        preflight_output_tail = tail_lines(preflight_output, 18)

    preflight_report = load_json(preflight_report_file) if bool(args.run_preflight) else {}
    preflight_result = (
        str(preflight_report.get("result", "UNKNOWN")).upper()
        if bool(args.run_preflight) and preflight_report
        else "SKIPPED"
    )
    preflight_blocking_failures = (
        [str(item) for item in preflight_report.get("blocking_failures", [])]
        if isinstance(preflight_report, dict)
        else []
    )
    if not preflight_blocking_failures:
        preflight_blocking_failures = (
            [str(item) for item in preflight_report.get("failures", [])]
            if isinstance(preflight_report, dict)
            else []
        )
    preflight_non_blocking_warnings = (
        [str(item) for item in preflight_report.get("non_blocking_warnings", [])]
        if isinstance(preflight_report, dict)
        else []
    )
    if not preflight_non_blocking_warnings:
        preflight_non_blocking_warnings = (
            [str(item) for item in preflight_report.get("warnings", [])]
            if isinstance(preflight_report, dict)
            else []
        )
    preflight_acceptance_blocking_failures = (
        [str(item) for item in preflight_report.get("acceptance_blocking_failures", [])]
        if isinstance(preflight_report, dict)
        else []
    )
    if not preflight_acceptance_blocking_failures:
        preflight_acceptance_blocking_failures = list(preflight_blocking_failures)
    preflight_hints = [str(item) for item in preflight_report.get("hints", [])] if isinstance(preflight_report, dict) else []
    preflight_can_start_live_stack = (
        bool(preflight_report.get("can_start_live_stack", preflight_result != "FAIL"))
        if bool(args.run_preflight) and isinstance(preflight_report, dict)
        else True
    )
    preflight_can_run_acceptance = (
        bool(preflight_report.get("can_run_acceptance", preflight_result == "PASS"))
        if bool(args.run_preflight) and isinstance(preflight_report, dict)
        else False
    )

    usb_report = load_json(usb_report_file)
    usb_result = str(usb_report.get("result", "UNKNOWN")).upper() if usb_report else "UNKNOWN"
    recommended = usb_report.get("recommended", {}) if isinstance(usb_report.get("recommended"), dict) else {}
    recommended_vision_command = build_recommended_vision_command(python_cmd, recommended)
    if not recommended_vision_command:
        recommended_vision_command = build_fallback_vision_command(python_cmd)

    bridge_command = (
        f"{python_cmd} tools/{NODE_BRIDGE_SCRIPT.name} --port {port_value} --baud {baud_value} "
        "--vision-forward-status"
    )
    web_server_command = f"{python_cmd} tools/{WEB_SERVER_SCRIPT.name}"
    preflight_command = (
        f"{python_cmd} tools/{PREFLIGHT_SCRIPT.name} --port {port_value} --base-url {base_url} "
        "--skip-usb --no-refresh-usb-check"
    )
    health_check_command = (
        f"{python_cmd} -c \"import urllib.request,json;"
        f"print(json.load(urllib.request.urlopen('{base_url}/api/health')))\""
    )
    if len(suite_names) > 1:
        suite_option_fragment = f"--suite-chain {suite_chain_value}"
    else:
        suite_option_fragment = f"--suite {suite_name}"
    acceptance_command = (
        f"{python_cmd} tools/{ACCEPTANCE_FLOW_SCRIPT.name} "
        f"--mode full --port {port_value} {suite_option_fragment} "
        f"--no-run-suite --skip-usb --base-url {base_url}"
    )
    live_quick_check_command = (
        f"{python_cmd} tools/{ACCEPTANCE_FLOW_SCRIPT.name} "
        f"--mode quick --port {port_value} {suite_option_fragment} "
        f"--no-run-suite --skip-usb --base-url {base_url}"
    )
    auto_acceptance_command = (
        f"{python_cmd} tools/{ACCEPTANCE_AUTO_SCRIPT.name} "
        f"--port {port_value} {suite_option_fragment} "
        f"--no-run-suite --skip-usb --base-url {base_url}"
    )

    terminals = [
        {"terminal": "Terminal-1", "role": "NodeA serial bridge", "command": bridge_command},
        {"terminal": "Terminal-2", "role": "USB vision bridge", "command": recommended_vision_command},
        {"terminal": "Terminal-3", "role": "Vision web server", "command": web_server_command},
    ]
    verify_steps = [
        {"name": "preflight", "command": preflight_command},
        {"name": "web_health", "command": health_check_command},
        {"name": "acceptance_auto", "command": auto_acceptance_command},
        {"name": "acceptance_quick", "command": live_quick_check_command},
        {"name": "acceptance_full", "command": acceptance_command},
    ]

    recommended_check_mode = "full"
    recommended_check_command = auto_acceptance_command
    recommended_check_reason = (
        "Environment ready. Run live acceptance without reopening the serial port or camera."
    )
    preflight_vision_gate_failures = [
        item for item in preflight_acceptance_blocking_failures if "vision_runtime_not_ready" in item
    ]
    if not preflight_can_start_live_stack:
        recommended_check_mode = "blocked"
        recommended_check_command = preflight_command
        recommended_check_reason = "Preflight has blocking failures. Fix preflight issues before acceptance."
    elif not preflight_can_run_acceptance:
        if preflight_vision_gate_failures:
            recommended_check_mode = "vision_gate"
            recommended_check_command = recommended_vision_command
            recommended_check_reason = "Vision bridge is not ready. Start vision bridge first, then run full acceptance."
        else:
            recommended_check_mode = "quick"
            recommended_check_command = live_quick_check_command
            recommended_check_reason = "Live stack can start, but acceptance prerequisites are not fully met. Run quick checks first."

    result = "PASS"
    if bool(args.run_preflight):
        if not preflight_can_start_live_stack:
            result = "BLOCKED"
        elif preflight_non_blocking_warnings or preflight_result in {"WARN", "UNKNOWN"}:
            result = "WARN"
    if usb_result == "FAIL" and result == "PASS":
        result = "WARN"

    report = {
        "generated_ms": int(time.time() * 1000),
        "result": result,
        "base_url": base_url,
        "port": port_value,
        "baud": baud_value,
        "vision_forward_status_enabled": True,
        "serial_owner": "node_a_serial_bridge",
        "camera_owner": "vision_bridge",
        "live_acceptance_run_suite": False,
        "live_acceptance_skip_usb": True,
        "suite": suite_name,
        "suite_names": suite_names,
        "suite_count": len(suite_names),
        "suite_chain_raw": suite_chain_raw,
        "run_preflight": bool(args.run_preflight),
        "refresh_usb_check": bool(args.refresh_usb_check),
        "preflight_report_file": preflight_report_file.as_posix(),
        "preflight_result": preflight_result,
        "preflight_can_start_live_stack": preflight_can_start_live_stack,
        "preflight_can_run_acceptance": preflight_can_run_acceptance,
        "preflight_returncode": preflight_returncode,
        "preflight_output_tail": preflight_output_tail,
        "preflight_blocking_failures": preflight_blocking_failures,
        "preflight_acceptance_blocking_failures": preflight_acceptance_blocking_failures,
        "preflight_non_blocking_warnings": preflight_non_blocking_warnings,
        "preflight_failures": preflight_blocking_failures,
        "preflight_hints": preflight_hints,
        "usb_report_file": usb_report_file.as_posix(),
        "usb_result": usb_result,
        "auto_acceptance_command": auto_acceptance_command,
        "live_quick_check_command": live_quick_check_command,
        "full_acceptance_command": acceptance_command,
        "recommended_check_mode": recommended_check_mode,
        "recommended_check_command": recommended_check_command,
        "recommended_check_reason": recommended_check_reason,
        "terminals": terminals,
        "verify_steps": verify_steps,
    }
    write_json(output_file, report)

    print("4.11 Startup Helper")
    print(f"result={result}")
    print(f"preflight_result={preflight_result}")
    print(f"preflight_can_start_live_stack={int(preflight_can_start_live_stack)}")
    print(f"preflight_can_run_acceptance={int(preflight_can_run_acceptance)}")
    print(f"usb_result={usb_result}")
    print(f"suite={suite_name}")
    if len(suite_names) > 1:
        print(f"suite_chain={suite_chain_value}")
    print(f"recommended_check_mode={recommended_check_mode}")
    print(f"recommended_check_reason={recommended_check_reason}")
    print(f"recommended_check_command={recommended_check_command}")
    print(f"base_url={base_url}")
    print(f"report_file={output_file.as_posix()}")
    for item in terminals:
        print(f"{item['terminal']} {item['role']}:")
        print(item["command"])
    print("Verification order:")
    for item in verify_steps:
        print(f"- {item['name']}: {item['command']}")
    for item in preflight_blocking_failures:
        print(f"- preflight_blocking:{item}")
    for item in preflight_non_blocking_warnings:
        print(f"- preflight_warning:{item}")
    for item in preflight_acceptance_blocking_failures:
        print(f"- preflight_acceptance_blocking:{item}")
    for item in preflight_hints:
        print(f"- preflight_hint:{item}")

    # Startup helper is primarily a guidance tool; always return 0 so users can read commands even when preflight warns.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





