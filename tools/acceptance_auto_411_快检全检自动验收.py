# Purpose: Run 4.11 auto acceptance (quick then full) and emit one merged report.
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


ACCEPTANCE_FLOW_SCRIPT = find_tool_script("acceptance_flow_411_")


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


def tail_lines(text: str, max_lines: int = 20) -> str:
    rows = [line for line in str(text or "").splitlines() if line.strip()]
    if not rows:
        return ""
    return "\n".join(rows[-max(1, int(max_lines)):])


def run_mode(
    *,
    python_exe: str,
    mode: str,
    port: str,
    suite: str,
    suite_chain: str,
    base_url: str,
    skip_usb: bool,
    report_file: Path,
    timeout_s: float,
) -> dict[str, Any]:
    command = [
        python_exe,
        str(ACCEPTANCE_FLOW_SCRIPT),
        "--mode",
        mode,
        "--port",
        port,
        "--suite",
        suite,
        "--base-url",
        base_url,
        "--report-file",
        report_file.as_posix(),
    ]
    suite_chain_value = str(suite_chain or "").strip()
    if suite_chain_value:
        command.extend(["--suite-chain", suite_chain_value])
    if skip_usb:
        command.append("--skip-usb")

    started_ms = int(time.time() * 1000)
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=max(1.0, float(timeout_s)),
            check=False,
        )
        returncode = int(completed.returncode)
        timeout_flag = False
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        timeout_flag = True
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")

    finished_ms = int(time.time() * 1000)
    return {
        "mode": mode,
        "command": command,
        "started_ms": started_ms,
        "finished_ms": finished_ms,
        "duration_ms": max(0, finished_ms - started_ms),
        "returncode": returncode,
        "timeout": timeout_flag,
        "ok": (returncode == 0) and (not timeout_flag),
        "stdout_tail": tail_lines(stdout),
        "stderr_tail": tail_lines(stderr),
        "report_file": report_file.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="4.11 auto acceptance: run quick first, then full when eligible")
    parser.add_argument("--python-exe", default=sys.executable, help="Python executable used for child steps")
    parser.add_argument("--port", default="COM4", help="Serial port, for example COM4")
    parser.add_argument("--suite", default="risk_event_vision_chain_v1", help="Suite name")
    parser.add_argument(
        "--suite-chain",
        default="",
        help="Optional comma-separated suite chain, for example rid_identity_chain_v1,risk_event_vision_chain_v1",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Vision web base URL")
    parser.add_argument("--skip-usb", action="store_true", help="Pass --skip-usb to both quick/full steps")
    parser.add_argument(
        "--stop-on-quick-fail",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to skip full step when quick mode fails",
    )
    parser.add_argument("--step-timeout-s", type=float, default=120.0, help="Timeout for each acceptance child step")
    parser.add_argument(
        "--quick-report-file",
        type=Path,
        default=Path("captures/latest_411_acceptance_quick_report.json"),
        help="Quick report output path",
    )
    parser.add_argument(
        "--full-report-file",
        type=Path,
        default=Path("captures/latest_411_acceptance_full_report.json"),
        help="Full report output path",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("captures/latest_411_acceptance_auto_report.json"),
        help="Auto acceptance merged report path",
    )
    args = parser.parse_args()

    port_value = str(args.port).strip() or "COM4"
    suite_name = str(args.suite).strip() or "risk_event_vision_chain_v1"
    suite_chain_value = str(args.suite_chain).strip()
    base_url = str(args.base_url).strip() or "http://127.0.0.1:8765"
    python_exe = str(args.python_exe).strip() or sys.executable
    quick_report_file = resolve_path(args.quick_report_file)
    full_report_file = resolve_path(args.full_report_file)
    report_file = resolve_path(args.report_file)

    quick_step = run_mode(
        python_exe=python_exe,
        mode="quick",
        port=port_value,
        suite=suite_name,
        suite_chain=suite_chain_value,
        base_url=base_url,
        skip_usb=bool(args.skip_usb),
        report_file=quick_report_file,
        timeout_s=float(args.step_timeout_s),
    )
    quick_report = load_json(quick_report_file)
    quick_result = str(quick_report.get("result", "FAIL")).upper() if quick_report else "FAIL"
    quick_ok = bool(quick_step.get("ok")) and (quick_result == "PASS")

    full_step: dict[str, Any] = {
        "mode": "full",
        "skipped": True,
        "reason": "skipped_by_quick_failure",
        "report_file": full_report_file.as_posix(),
    }
    full_report: dict[str, Any] = {}
    full_result = "SKIPPED"
    if quick_ok or (not bool(args.stop_on_quick_fail)):
        full_step = run_mode(
            python_exe=python_exe,
            mode="full",
            port=port_value,
            suite=suite_name,
            suite_chain=suite_chain_value,
            base_url=base_url,
            skip_usb=bool(args.skip_usb),
            report_file=full_report_file,
            timeout_s=float(args.step_timeout_s),
        )
        full_report = load_json(full_report_file)
        full_result = str(full_report.get("result", "FAIL")).upper() if full_report else "FAIL"

    if quick_result == "PASS" and full_result == "PASS":
        result = "PASS"
    elif quick_result == "PASS" and full_result == "SKIPPED":
        result = "WARN"
    else:
        result = "FAIL"

    next_action_summary = ""
    next_action_command = ""
    if result != "PASS":
        if isinstance(full_report, dict) and full_report:
            next_action_summary = str(full_report.get("next_action_summary", "") or "")
            next_action_command = str(full_report.get("next_action_command", "") or "")
        if not next_action_summary:
            next_action_summary = str(quick_report.get("next_action_summary", "") or "")
            next_action_command = str(quick_report.get("next_action_command", "") or "")
        if not next_action_summary and full_result == "SKIPPED":
            next_action_summary = "Quick failed and full was skipped. Fix quick blockers, then rerun auto acceptance."
            next_action_command = str(quick_report.get("next_action_command", "") or "")
    else:
        next_action_summary = "Auto acceptance passed. Ready for demo and evidence archival."

    full_closure_vision_lock_hits = int(full_report.get("closure_vision_lock_hits", 0) or 0) if isinstance(full_report, dict) else 0
    full_closure_capture_ready_hits = int(full_report.get("closure_capture_ready_hits", 0) or 0) if isinstance(full_report, dict) else 0
    full_closure_vision_lock_ok = bool(full_report.get("closure_vision_lock_ok")) if isinstance(full_report, dict) else False
    full_closure_capture_ready_ok = bool(full_report.get("closure_capture_ready_ok")) if isinstance(full_report, dict) else False

    report = {
        "checked_ms": int(time.time() * 1000),
        "result": result,
        "port": port_value,
        "suite": suite_name,
        "suite_chain": suite_chain_value,
        "base_url": base_url,
        "skip_usb": bool(args.skip_usb),
        "stop_on_quick_fail": bool(args.stop_on_quick_fail),
        "quick_step": quick_step,
        "quick_result": quick_result,
        "quick_report_file": quick_report_file.as_posix(),
        "full_step": full_step,
        "full_result": full_result,
        "full_report_file": full_report_file.as_posix(),
        "full_closure_vision_lock_hits": full_closure_vision_lock_hits,
        "full_closure_capture_ready_hits": full_closure_capture_ready_hits,
        "full_closure_vision_lock_ok": full_closure_vision_lock_ok,
        "full_closure_capture_ready_ok": full_closure_capture_ready_ok,
        "next_action_summary": next_action_summary,
        "next_action_command": next_action_command,
    }
    write_json(report_file, report)

    print("4.11 Auto Acceptance Report")
    print(f"result={result}")
    print(f"quick_result={quick_result}")
    print(f"full_result={full_result}")
    if suite_chain_value:
        print(f"suite_chain={suite_chain_value}")
    print(f"stop_on_quick_fail={int(bool(args.stop_on_quick_fail))}")
    print(f"full_closure_vision_lock_hits={full_closure_vision_lock_hits}")
    print(f"full_closure_capture_ready_hits={full_closure_capture_ready_hits}")
    print(f"full_closure_vision_lock_ok={full_closure_vision_lock_ok}")
    print(f"full_closure_capture_ready_ok={full_closure_capture_ready_ok}")
    if next_action_summary:
        print(f"next_action_summary={next_action_summary}")
    if next_action_command:
        print(f"next_action_command={next_action_command}")
    print(f"quick_report_file={quick_report_file.as_posix()}")
    print(f"full_report_file={full_report_file.as_posix()}")
    print(f"report_file={report_file.as_posix()}")

    return 0 if result == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
