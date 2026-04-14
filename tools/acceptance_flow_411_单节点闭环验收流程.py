# Purpose: Run 4.11 one-command single-node acceptance (preflight/suite/USB/closure) and output unified report.
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"


def find_tool_script(prefix: str) -> Path:
    matches = sorted(TOOLS_DIR.glob(f"{prefix}*.py"))
    if matches:
        return matches[0]
    return TOOLS_DIR / f"{prefix}.py"


USB_CHECK_SCRIPT = find_tool_script("usb_camera_readiness_check_")
CLOSURE_CHECK_SCRIPT = find_tool_script("single_node_evidence_closure_check_")
TRACK_INJECTOR_SCRIPT = find_tool_script("track_injector_")
PREFLIGHT_SCRIPT = find_tool_script("preflight_411_")
STARTUP_HELPER_SCRIPT = find_tool_script("startup_helper_411_")
VISION_BRIDGE_SCRIPT = find_tool_script("vision_bridge_")
USB_REPORT_DEFAULT = PROJECT_ROOT / "captures/latest_usb_camera_readiness_report.json"
CLOSURE_REPORT_DEFAULT = PROJECT_ROOT / "captures/latest_single_node_evidence_closure_report.json"
PREFLIGHT_REPORT_DEFAULT = PROJECT_ROOT / "captures/latest_411_preflight_report.json"

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


def tail_lines(text: str, max_lines: int = 20) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    trimmed = lines[-max_lines:]
    return "\n".join(trimmed)


def fetch_health(base_url: str, timeout_s: float) -> tuple[bool, str]:
    url = f"{base_url.rstrip('/')}/api/health"
    try:
        with urlopen(url, timeout=max(0.2, timeout_s)) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except URLError as exc:
        return False, f"request_failed:{exc}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False, "invalid_json"
    if not isinstance(payload, dict):
        return False, "invalid_payload"
    if bool(payload.get("ok")):
        return True, ""
    return False, "ok_false"


def wait_web_health_ready(base_url: str, timeout_s: float, max_wait_s: float, poll_interval_s: float) -> tuple[bool, str]:
    deadline = time.time() + max(0.0, max_wait_s)
    last_error = "unknown"
    while True:
        ok, error = fetch_health(base_url, timeout_s)
        if ok:
            return True, ""
        last_error = error or "unknown"
        if time.time() >= deadline:
            return False, last_error
        time.sleep(max(0.05, poll_interval_s))


def run_step(name: str, command: list[str], timeout_s: float) -> dict[str, Any]:
    started_ms = int(time.time() * 1000)
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=max(1.0, timeout_s),
            check=False,
        )
        returncode = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        timeout_flag = False
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
        timeout_flag = True

    finished_ms = int(time.time() * 1000)
    ok = (returncode == 0) and not timeout_flag
    return {
        "name": name,
        "command": command,
        "started_ms": started_ms,
        "finished_ms": finished_ms,
        "duration_ms": max(0, finished_ms - started_ms),
        "returncode": returncode,
        "timeout": timeout_flag,
        "ok": ok,
        "stdout_tail": tail_lines(stdout),
        "stderr_tail": tail_lines(stderr),
    }


def has_flag(argv: list[str], option: str) -> bool:
    prefix = f"{option}="
    for token in argv:
        if token == option or token.startswith(prefix):
            return True
    return False


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
    parser = argparse.ArgumentParser(
        description="4.11 one-command acceptance flow for single-node evidence + USB camera readiness."
    )
    parser.add_argument("--python-exe", default=sys.executable, help="Python executable used to run sub-check scripts")
    parser.add_argument(
        "--mode",
        choices=["custom", "quick", "full"],
        default="custom",
        help="Preset mode: quick=live fast check, full=full acceptance, custom=use explicit flags",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Vision web server base URL")
    parser.add_argument("--timeout-s", type=float, default=40.0, help="Per-step timeout in seconds")
    parser.add_argument(
        "--wait-web-health-seconds",
        type=float,
        default=8.0,
        help="Wait window for /api/health before running closure step",
    )
    parser.add_argument(
        "--skip-web-health-precheck",
        action="store_true",
        help="Skip web health precheck before closure step",
    )
    parser.add_argument("--closure-timeout-s", type=float, default=3.0, help="HTTP timeout passed to closure check step")
    parser.add_argument("--closure-api-retries", type=int, default=3, help="Web API retry count passed to closure check step")
    parser.add_argument("--closure-api-retry-interval-s", type=float, default=0.35, help="Web API retry interval passed to closure check step")
    parser.add_argument(
        "--closure-require-vision-lock",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Require vision lock evidence in closure check",
    )
    parser.add_argument(
        "--closure-min-vision-lock-hits",
        type=int,
        default=1,
        help="Minimum vision lock evidence hits required by closure check",
    )
    parser.add_argument(
        "--closure-require-capture-ready",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Require capture-ready evidence in closure check",
    )
    parser.add_argument(
        "--closure-min-capture-ready-hits",
        type=int,
        default=1,
        help="Minimum capture-ready evidence hits required by closure check",
    )
    parser.add_argument("--run-preflight", action=argparse.BooleanOptionalAction, default=True, help="Run preflight checks before suite/usb/closure steps")
    parser.add_argument("--preflight-fail-fast", action="store_true", help="Stop subsequent steps when preflight returns FAIL")
    parser.add_argument(
        "--preflight-fail-fast-scope",
        choices=["live", "acceptance"],
        default="acceptance",
        help="Fail-fast scope: live checks only startup blockers, acceptance checks full acceptance prerequisites",
    )
    parser.add_argument("--preflight-timeout-s", type=float, default=1.2, help="Timeout passed to preflight network checks")
    parser.add_argument("--preflight-refresh-usb-check", action=argparse.BooleanOptionalAction, default=True, help="When preflight runs, whether to refresh usb readiness report")
    parser.add_argument("--preflight-report-file", type=Path, default=Path("captures/latest_411_preflight_report.json"), help="Preflight report JSON path")
    parser.add_argument("--run-suite", action="store_true", help="Run track_injector suite step before readiness checks")
    parser.add_argument("--port", default="", help="Serial port for track_injector when --run-suite is enabled, e.g. COM4")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud for track_injector suite step")
    parser.add_argument(
        "--suite",
        default="risk_event_vision_chain_v1",
        help="Suite name passed to track_injector when --run-suite is enabled",
    )
    parser.add_argument(
        "--suite-chain",
        default="",
        help="Optional comma-separated suite chain, for example rid_identity_chain_v1,risk_event_vision_chain_v1",
    )
    parser.add_argument("--skip-usb", action="store_true", help="Skip USB camera readiness step")
    parser.add_argument("--skip-closure", action="store_true", help="Skip single-node evidence closure step")
    parser.add_argument("--allow-no-export", action="store_true", help="Allow export history count == 0 in closure check")
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("captures/latest_411_acceptance_flow_report.json"),
        help="Output JSON report path",
    )
    args = parser.parse_args()
    raw_argv = sys.argv[1:]

    explicit_run_suite = has_flag(raw_argv, "--run-suite")
    explicit_skip_closure = has_flag(raw_argv, "--skip-closure")
    explicit_preflight_fail_fast = has_flag(raw_argv, "--preflight-fail-fast")
    explicit_preflight_fail_fast_scope = has_flag(raw_argv, "--preflight-fail-fast-scope")
    explicit_closure_timeout = has_flag(raw_argv, "--closure-timeout-s")
    explicit_closure_retries = has_flag(raw_argv, "--closure-api-retries")
    explicit_closure_require_vision_lock = has_flag(raw_argv, "--closure-require-vision-lock") or has_flag(raw_argv, "--no-closure-require-vision-lock")
    explicit_closure_require_capture_ready = has_flag(raw_argv, "--closure-require-capture-ready") or has_flag(raw_argv, "--no-closure-require-capture-ready")
    mode_defaults_applied: list[str] = []

    if args.mode == "quick":
        if not explicit_run_suite:
            args.run_suite = True
            mode_defaults_applied.append("run_suite=true")
        if not explicit_skip_closure:
            args.skip_closure = True
            mode_defaults_applied.append("skip_closure=true")
        if not explicit_preflight_fail_fast:
            args.preflight_fail_fast = True
            mode_defaults_applied.append("preflight_fail_fast=true")
        if not explicit_preflight_fail_fast_scope:
            args.preflight_fail_fast_scope = "live"
            mode_defaults_applied.append("preflight_fail_fast_scope=live")
    elif args.mode == "full":
        if not explicit_run_suite:
            args.run_suite = True
            mode_defaults_applied.append("run_suite=true")
        if not explicit_skip_closure:
            args.skip_closure = False
            mode_defaults_applied.append("skip_closure=false")
        if not explicit_preflight_fail_fast:
            args.preflight_fail_fast = True
            mode_defaults_applied.append("preflight_fail_fast=true")
        if not explicit_preflight_fail_fast_scope:
            args.preflight_fail_fast_scope = "acceptance"
            mode_defaults_applied.append("preflight_fail_fast_scope=acceptance")
        if not explicit_closure_timeout:
            args.closure_timeout_s = 4.0
            mode_defaults_applied.append("closure_timeout_s=4.0")
        if not explicit_closure_retries:
            args.closure_api_retries = 4
            mode_defaults_applied.append("closure_api_retries=4")
        if not explicit_closure_require_vision_lock:
            args.closure_require_vision_lock = True
            mode_defaults_applied.append("closure_require_vision_lock=true")
        if not explicit_closure_require_capture_ready:
            args.closure_require_capture_ready = True
            mode_defaults_applied.append("closure_require_capture_ready=true")

    report_file = resolve_path(args.report_file)
    preflight_report_file = resolve_path(args.preflight_report_file)
    suite_name_value = str(args.suite).strip() or "risk_event_vision_chain_v1"
    suite_chain_raw = str(args.suite_chain).strip()
    suite_names = parse_suite_sequence(suite_name_value, suite_chain_raw)
    suite_chain_value = ",".join(suite_names)
    steps: list[dict[str, Any]] = []
    precheck_failures: list[str] = []
    web_health_precheck_ok = True
    web_health_precheck_error = ""
    warnings: list[str] = []
    notes: list[str] = []
    preflight_result = "SKIPPED"
    preflight_failures: list[str] = []
    preflight_blocking_failures: list[str] = []
    preflight_non_blocking_warnings: list[str] = []
    preflight_acceptance_blocking_failures: list[str] = []
    preflight_hints: list[str] = []
    preflight_can_start_live_stack = True
    preflight_can_run_acceptance = True
    preflight_fail_fast_reason = ""
    preflight_executed = False
    short_circuited_by_preflight = False

    preflight_cmd_step: list[str] = [
        args.python_exe,
        str(PREFLIGHT_SCRIPT),
        "--port",
        str(args.port).strip() or "COM4",
        "--base-url",
        args.base_url,
        "--timeout-s",
        str(max(0.2, float(args.preflight_timeout_s))),
        "--report-file",
        preflight_report_file.as_posix(),
        "--usb-report-file",
        USB_REPORT_DEFAULT.as_posix(),
    ]
    if args.skip_usb:
        preflight_cmd_step.append("--skip-usb")
        preflight_cmd_step.append("--no-refresh-usb-check")
    else:
        preflight_cmd_step.append("--refresh-usb-check" if bool(args.preflight_refresh_usb_check) else "--no-refresh-usb-check")

    if bool(args.run_preflight):
        preflight_executed = True
        preflight_step = run_step("preflight_411", preflight_cmd_step, args.timeout_s)
        steps.append(preflight_step)
        preflight_report = load_json(preflight_report_file)
        preflight_result = str(preflight_report.get("result", "UNKNOWN")).upper() if preflight_report else "UNKNOWN"
        preflight_blocking_failures = (
            [str(item) for item in preflight_report.get("blocking_failures", [])]
            if isinstance(preflight_report, dict)
            else []
        )
        preflight_non_blocking_warnings = (
            [str(item) for item in preflight_report.get("non_blocking_warnings", [])]
            if isinstance(preflight_report, dict)
            else []
        )
        preflight_acceptance_blocking_failures = (
            [str(item) for item in preflight_report.get("acceptance_blocking_failures", [])]
            if isinstance(preflight_report, dict)
            else []
        )
        preflight_failures = (
            preflight_blocking_failures
            or ([str(item) for item in preflight_report.get("failures", [])] if isinstance(preflight_report, dict) else [])
        )
        if not preflight_blocking_failures:
            preflight_blocking_failures = list(preflight_failures)
        if not preflight_non_blocking_warnings:
            preflight_non_blocking_warnings = (
                [str(item) for item in preflight_report.get("warnings", [])]
                if isinstance(preflight_report, dict)
                else []
            )
        if not preflight_acceptance_blocking_failures:
            preflight_acceptance_blocking_failures = list(preflight_failures)
        preflight_hints = [str(item) for item in preflight_report.get("hints", [])] if isinstance(preflight_report, dict) else []
        preflight_can_start_live_stack = bool(preflight_report.get("can_start_live_stack", preflight_result != "FAIL")) if isinstance(preflight_report, dict) else False
        preflight_can_run_acceptance = bool(preflight_report.get("can_run_acceptance", preflight_result == "PASS")) if isinstance(preflight_report, dict) else False
        preflight_step_ok = bool(preflight_step.get("ok"))
        if args.preflight_fail_fast_scope == "live":
            preflight_failed = (not preflight_step_ok) or (not preflight_can_start_live_stack)
            if not preflight_step_ok:
                preflight_fail_fast_reason = "preflight_step_failed"
            elif not preflight_can_start_live_stack:
                preflight_fail_fast_reason = "preflight_live_gate_failed"
        else:
            preflight_failed = (not preflight_step_ok) or (not preflight_can_run_acceptance)
            if not preflight_step_ok:
                preflight_fail_fast_reason = "preflight_step_failed"
            elif not preflight_can_run_acceptance:
                preflight_fail_fast_reason = "preflight_acceptance_gate_failed"
        if bool(args.preflight_fail_fast) and preflight_failed:
            short_circuited_by_preflight = True
            precheck_failures.append("preflight_fail_fast_triggered")
            if preflight_fail_fast_reason:
                precheck_failures.append(f"preflight_fail_fast_reason:{preflight_fail_fast_reason}")
            warnings.append("steps_skipped_due_to_preflight_fail_fast")

    if (not short_circuited_by_preflight) and args.run_suite:
        port_value = str(args.port).strip()
        if not port_value:
            precheck_failures.append("run_suite_requires_port")
        else:
            for suite_name in suite_names:
                suite_cmd = [
                    args.python_exe,
                    str(TRACK_INJECTOR_SCRIPT),
                    "--port",
                    port_value,
                    "--baud",
                    str(max(1, int(args.baud))),
                    "--suite",
                    suite_name,
                ]
                steps.append(
                    run_step(
                        f"track_injector_suite:{suite_name}",
                        suite_cmd,
                        args.timeout_s,
                    )
                )

    if (not short_circuited_by_preflight) and (not args.skip_usb):
        usb_cmd = [args.python_exe, str(USB_CHECK_SCRIPT)]
        steps.append(run_step("usb_camera_readiness", usb_cmd, args.timeout_s))

    if (not short_circuited_by_preflight) and (not args.skip_closure):
        if not args.skip_web_health_precheck:
            web_health_precheck_ok, web_health_precheck_error = wait_web_health_ready(
                args.base_url,
                timeout_s=max(0.5, float(args.closure_timeout_s)),
                max_wait_s=max(0.0, float(args.wait_web_health_seconds)),
                poll_interval_s=0.35,
            )
            if not web_health_precheck_ok:
                precheck_failures.append(f"web_health_precheck_failed:{web_health_precheck_error}")
        if not web_health_precheck_ok:
            # Skip closure when web health precheck fails.
            pass
        else:
            closure_cmd = [
                args.python_exe,
                str(CLOSURE_CHECK_SCRIPT),
                "--base-url",
                args.base_url,
                "--timeout-s",
                str(max(0.5, float(args.closure_timeout_s))),
                "--api-retries",
                str(max(1, int(args.closure_api_retries))),
                "--api-retry-interval-s",
                str(max(0.0, float(args.closure_api_retry_interval_s))),
                "--min-vision-lock-hits",
                str(max(1, int(args.closure_min_vision_lock_hits))),
                "--min-capture-ready-hits",
                str(max(1, int(args.closure_min_capture_ready_hits))),
            ]
            if bool(args.closure_require_vision_lock):
                closure_cmd.append("--require-vision-lock")
            if bool(args.closure_require_capture_ready):
                closure_cmd.append("--require-capture-ready")
            if args.allow_no_export:
                closure_cmd.append("--allow-no-export")
            steps.append(run_step("single_node_evidence_closure", closure_cmd, args.timeout_s))

    step_failures = [item for item in steps if not bool(item.get("ok"))]
    closure_step_executed = any(str(item.get("name", "")) == "single_node_evidence_closure" for item in steps)
    usb_report = load_json(USB_REPORT_DEFAULT)
    closure_report = load_json(CLOSURE_REPORT_DEFAULT)

    usb_result = str(usb_report.get("result", "UNKNOWN")).upper() if usb_report else "UNKNOWN"
    closure_result_raw = str(closure_report.get("result", "UNKNOWN")).upper() if closure_report else "UNKNOWN"
    closure_counts = closure_report.get("counts", {}) if isinstance(closure_report, dict) else {}
    closure_checks = closure_report.get("checks", {}) if isinstance(closure_report, dict) else {}
    closure_cached_export_count = int((closure_counts.get("node_event_exports_count", 0) or 0) if isinstance(closure_counts, dict) else 0)
    closure_cached_export_detail_ok = bool(closure_checks.get("export_detail_ok")) if isinstance(closure_checks, dict) else False
    closure_cached_vision_lock_hits = int((closure_counts.get("vision_lock_hits", 0) or 0) if isinstance(closure_counts, dict) else 0)
    closure_cached_capture_ready_hits = int((closure_counts.get("capture_ready_hits", 0) or 0) if isinstance(closure_counts, dict) else 0)
    closure_cached_vision_lock_ok = bool(closure_checks.get("vision_lock_evidence_ok")) if isinstance(closure_checks, dict) else False
    closure_cached_capture_ready_ok = bool(closure_checks.get("capture_ready_evidence_ok")) if isinstance(closure_checks, dict) else False
    closure_cached_latest_event_id = str(closure_report.get("latest_event_id", "NONE") or "NONE")
    closure_export_count = closure_cached_export_count
    closure_export_detail_ok = closure_cached_export_detail_ok
    closure_vision_lock_hits = closure_cached_vision_lock_hits
    closure_capture_ready_hits = closure_cached_capture_ready_hits
    closure_vision_lock_ok = closure_cached_vision_lock_ok
    closure_capture_ready_ok = closure_cached_capture_ready_ok
    closure_latest_event_id = closure_cached_latest_event_id
    if args.skip_closure:
        closure_result = "SKIPPED"
        closure_export_count = 0
        closure_export_detail_ok = False
        closure_vision_lock_hits = 0
        closure_capture_ready_hits = 0
        closure_vision_lock_ok = False
        closure_capture_ready_ok = False
        closure_latest_event_id = "NONE"
    elif not closure_step_executed:
        closure_result = "SKIPPED_PRECHECK" if not web_health_precheck_ok else "SKIPPED"
        closure_export_count = 0
        closure_export_detail_ok = False
        closure_vision_lock_hits = 0
        closure_capture_ready_hits = 0
        closure_vision_lock_ok = False
        closure_capture_ready_ok = False
        closure_latest_event_id = "NONE"
    else:
        closure_result = closure_result_raw

    failures: list[str] = []

    if precheck_failures:
        failures.extend(precheck_failures)
    if step_failures:
        for item in step_failures:
            failures.append(f"step_failed:{item.get('name')} rc={item.get('returncode')}")

    if not args.skip_usb and usb_result != "PASS":
        failures.append(f"usb_report_not_pass:{usb_result}")
    if (not args.skip_closure) and closure_step_executed and closure_result != "PASS":
        failures.append(f"closure_report_not_pass:{closure_result}")
    if (not args.skip_closure) and (not closure_step_executed) and web_health_precheck_ok and (not short_circuited_by_preflight):
        failures.append("closure_step_not_executed")

    if args.skip_usb:
        warnings.append("usb_step_skipped")
    if args.skip_closure:
        if args.mode == "quick":
            notes.append("closure_step_skipped_by_mode_quick")
        else:
            warnings.append("closure_step_skipped")
    if not steps:
        warnings.append("no_steps_executed")

    operator_hints: list[str] = []
    closure_failures = (
        closure_report.get("failures", [])
        if (isinstance(closure_report, dict) and closure_step_executed)
        else []
    )
    closure_failure_text = [str(item) for item in closure_failures if str(item).strip()]
    usb_recommended = usb_report.get("recommended", {}) if isinstance(usb_report, dict) else {}
    recommended_vision_command = (
        str(usb_recommended.get("vision_bridge_command", "")).strip() if isinstance(usb_recommended, dict) else ""
    )
    if not recommended_vision_command:
        recommended_vision_command = (
            f"python tools/{VISION_BRIDGE_SCRIPT.name} "
            "--backend dshow --source 0 --tracker csrt --tracker-fallback auto --source-warmup-frames 12"
        )
    if preflight_executed and preflight_failures:
        for item in preflight_failures:
            operator_hints.append(f"Preflight blocking: {item}")
    for item in preflight_non_blocking_warnings:
        operator_hints.append(f"Preflight warning: {item}")
    for item in preflight_hints:
        operator_hints.append(f"Preflight hint: {item}")
    preflight_vision_gate_failures = [
        item
        for item in (preflight_acceptance_blocking_failures + preflight_failures)
        if "vision_runtime_not_ready" in item
    ]
    if preflight_vision_gate_failures:
        operator_hints.append(
            f"Vision bridge is not ready: run `{recommended_vision_command}`, then retry acceptance."
        )
    if (not web_health_precheck_ok) or any(item.startswith("web_health_unavailable") for item in closure_failure_text):
        operator_hints.append("Web service is not ready: start `python tools/vision_web_server_视觉网页服务.py`.")
    capture_chain_missing = any(
        ("capture_count_below_min" in item)
        or ("bound_capture_count_below_min" in item)
        or ("latest_event_id_unavailable" in item)
        for item in closure_failure_text
    )
    if capture_chain_missing:
        if recommended_vision_command:
            operator_hints.append(
                f"Capture evidence is missing: run `{recommended_vision_command}`, lock a target (`s`), then capture (`c`)."
            )
        else:
            operator_hints.append("Capture evidence is missing: start vision_bridge and finish one lock + capture cycle.")
    vision_chain_missing = any(
        ("vision_lock_evidence_below_min" in item)
        or ("capture_ready_evidence_below_min" in item)
        for item in closure_failure_text
    )
    if vision_chain_missing:
        operator_hints.append(
            f"Vision lock evidence is insufficient: run `{recommended_vision_command}` and complete one high-risk lock cycle."
        )
    if any("node_event_export_detail_not_available" in item for item in closure_failure_text):
        operator_hints.append("Event export detail is unavailable: export current event evidence JSON from dashboard, then retry.")
    if any(str(item.get("name", "")) == "usb_camera_readiness" for item in step_failures):
        operator_hints.append(
            "USB camera is not ready: close apps occupying camera and run "
            "`python tools/usb_camera_readiness_check_USB摄像头就绪核对.py`."
        )
    if any(str(item.get("name", "")).startswith("track_injector_suite") for item in step_failures):
        operator_hints.append(
            "Suite serial step failed: confirm COM port is available, then rerun "
            f"`python tools/track_injector_轨迹注入器.py --port COM4 --suite {suite_names[0]}`."
        )
    if any(("node_events_count_below_min" in item) or ("event_store_count_below_min" in item) for item in closure_failure_text):
        operator_hints.append(
            "Node event semantics were not persisted: start NodeA serial bridge "
            "`python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200` first."
        )
    preflight_cmd = (
        f"python tools/{PREFLIGHT_SCRIPT.name} "
        f"--port {str(args.port).strip() or 'COM4'} --base-url {args.base_url} "
        + ("--skip-usb --no-refresh-usb-check" if args.skip_usb else ("--refresh-usb-check" if bool(args.preflight_refresh_usb_check) else "--no-refresh-usb-check"))
    )
    startup_helper_cmd = (
        f"python tools/{STARTUP_HELPER_SCRIPT.name} "
        f"--port {str(args.port).strip() or 'COM4'} --base-url {args.base_url} --suite {suite_names[0]}"
    )

    if failures:
        operator_hints.append(f"Run preflight first: `{preflight_cmd}`")
        operator_hints.append(f"Rebuild the 3-terminal setup: `{startup_helper_cmd}`")

    if len(suite_names) > 1:
        suite_option_fragment = f"--suite-chain {suite_chain_value}"
    else:
        suite_option_fragment = f"--suite {suite_names[0]}"

    quick_mode_cmd = (
        f"python tools/{Path(__file__).name} "
        f"--mode quick --port {str(args.port).strip() or 'COM4'} {suite_option_fragment} --base-url {args.base_url}"
    )
    full_mode_cmd = (
        f"python tools/{Path(__file__).name} "
        f"--mode full --port {str(args.port).strip() or 'COM4'} {suite_option_fragment} --base-url {args.base_url}"
    )
    suite_cmd_single = (
        f"python tools/{TRACK_INJECTOR_SCRIPT.name} "
        f"--port {str(args.port).strip() or 'COM4'} --suite {suite_names[0]}"
    )
    bridge_script = find_tool_script("node_a_serial_bridge_")
    web_server_script = find_tool_script("vision_web_server_")
    bridge_cmd_single = f"python tools/{bridge_script.name} --port {str(args.port).strip() or 'COM4'} --baud {max(1, int(args.baud))}"
    usb_check_cmd = f"python tools/{USB_CHECK_SCRIPT.name}"
    web_server_cmd = f"python tools/{web_server_script.name}"

    preflight_serial_missing = any("serial_port_missing" in item for item in preflight_failures)
    preflight_vision_gate_failed = any(
        "vision_runtime_not_ready" in item for item in (preflight_acceptance_blocking_failures + preflight_failures)
    )
    suite_step_failed = any("step_failed:track_injector_suite" in item for item in failures)
    usb_step_failed = any("step_failed:usb_camera_readiness" in item for item in failures)
    usb_not_pass = any("usb_report_not_pass" in item for item in failures)
    needs_node_bridge = any(
        ("node_events_count_below_min" in item) or ("event_store_count_below_min" in item)
        for item in closure_failure_text
    )
    needs_capture = any(
        ("capture_count_below_min" in item)
        or ("bound_capture_count_below_min" in item)
        or ("latest_event_id_unavailable" in item)
        for item in closure_failure_text
    )
    needs_vision_lock = any(
        ("vision_lock_evidence_below_min" in item)
        or ("capture_ready_evidence_below_min" in item)
        for item in closure_failure_text
    )

    next_action_summary = ""
    next_action_command = ""
    if failures:
        if (not web_health_precheck_ok) or any(item.startswith("web_health_unavailable") for item in preflight_failures) or any(item.startswith("web_health_unavailable") for item in closure_failure_text):
            next_action_summary = "Web service is not ready. Start web server then rerun acceptance."
            next_action_command = web_server_cmd
        elif preflight_vision_gate_failed:
            next_action_summary = "Vision bridge is not ready. Start vision bridge and wait for latest_status.json to refresh."
            next_action_command = recommended_vision_command
        elif preflight_serial_missing or any("run_suite_requires_port" in item for item in failures):
            next_action_summary = "Serial port is not ready. Run preflight and confirm COM port first."
            next_action_command = preflight_cmd
        elif needs_node_bridge:
            next_action_summary = "Node event semantics are missing. Start NodeA serial bridge first."
            next_action_command = bridge_cmd_single
        elif suite_step_failed:
            next_action_summary = "Suite serial step failed. Rerun single suite to debug serial contention."
            next_action_command = suite_cmd_single
        elif usb_not_pass or usb_step_failed:
            next_action_summary = "USB camera is not ready. Run USB readiness check first."
            next_action_command = usb_check_cmd
        elif needs_vision_lock and recommended_vision_command:
            next_action_summary = "Vision lock evidence is insufficient. Run vision bridge and complete one high-risk lock cycle."
            next_action_command = recommended_vision_command
        elif needs_capture and recommended_vision_command:
            next_action_summary = "Capture evidence is insufficient. Run vision bridge and complete one lock + capture cycle."
            next_action_command = recommended_vision_command
        else:
            next_action_summary = "Rebuild the 3-terminal environment, then rerun acceptance."
            next_action_command = startup_helper_cmd
    else:
        if args.mode == "quick":
            next_action_summary = "Quick check passed. Continue with full acceptance."
            next_action_command = full_mode_cmd
        elif args.mode == "full":
            next_action_summary = "Full acceptance passed. Ready for demo and evidence archival."
            next_action_command = ""
        else:
            next_action_summary = "Acceptance passed."
            next_action_command = ""

    report = {
        "checked_ms": int(time.time() * 1000),
        "result": "PASS" if not failures else "FAIL",
        "base_url": args.base_url,
        "python_exe": args.python_exe,
        "mode": args.mode,
        "mode_defaults_applied": mode_defaults_applied,
        "effective_config": {
            "run_preflight": bool(args.run_preflight),
            "run_suite": bool(args.run_suite),
            "skip_usb": bool(args.skip_usb),
            "skip_closure": bool(args.skip_closure),
            "preflight_fail_fast": bool(args.preflight_fail_fast),
            "preflight_fail_fast_scope": str(args.preflight_fail_fast_scope),
            "closure_timeout_s": float(args.closure_timeout_s),
            "closure_api_retries": int(args.closure_api_retries),
            "closure_require_vision_lock": bool(args.closure_require_vision_lock),
            "closure_min_vision_lock_hits": max(1, int(args.closure_min_vision_lock_hits)),
            "closure_require_capture_ready": bool(args.closure_require_capture_ready),
            "closure_min_capture_ready_hits": max(1, int(args.closure_min_capture_ready_hits)),
        },
        "steps_total": len(steps),
        "steps_passed": sum(1 for item in steps if bool(item.get("ok"))),
        "steps_failed": len(step_failures),
        "preflight_enabled": bool(args.run_preflight),
        "preflight_executed": preflight_executed,
        "preflight_fail_fast": bool(args.preflight_fail_fast),
        "preflight_fail_fast_scope": str(args.preflight_fail_fast_scope),
        "preflight_fail_fast_reason": preflight_fail_fast_reason,
        "preflight_result": preflight_result,
        "preflight_can_start_live_stack": preflight_can_start_live_stack,
        "preflight_can_run_acceptance": preflight_can_run_acceptance,
        "preflight_blocking_failures": preflight_blocking_failures,
        "preflight_non_blocking_warnings": preflight_non_blocking_warnings,
        "preflight_acceptance_blocking_failures": preflight_acceptance_blocking_failures,
        "preflight_failures": preflight_failures,
        "preflight_hints": preflight_hints,
        "preflight_report_file": preflight_report_file.as_posix(),
        "web_health_precheck_enabled": not bool(args.skip_web_health_precheck),
        "web_health_precheck_ok": bool(web_health_precheck_ok),
        "web_health_precheck_error": web_health_precheck_error,
        "run_suite": bool(args.run_suite),
        "suite_name": suite_names[0],
        "suite_names": suite_names,
        "suite_chain_raw": suite_chain_raw,
        "suite_count": len(suite_names),
        "suite_port": str(args.port).strip(),
        "step_results": steps,
        "usb_report_file": USB_REPORT_DEFAULT.as_posix(),
        "closure_report_file": CLOSURE_REPORT_DEFAULT.as_posix(),
        "usb_result": usb_result,
        "closure_result": closure_result,
        "closure_latest_event_id": closure_latest_event_id,
        "closure_export_count": closure_export_count,
        "closure_export_detail_ok": closure_export_detail_ok,
        "closure_vision_lock_hits": closure_vision_lock_hits,
        "closure_capture_ready_hits": closure_capture_ready_hits,
        "closure_vision_lock_ok": closure_vision_lock_ok,
        "closure_capture_ready_ok": closure_capture_ready_ok,
        "closure_cached_latest_event_id": closure_cached_latest_event_id,
        "closure_cached_export_count": closure_cached_export_count,
        "closure_cached_export_detail_ok": closure_cached_export_detail_ok,
        "closure_cached_vision_lock_hits": closure_cached_vision_lock_hits,
        "closure_cached_capture_ready_hits": closure_cached_capture_ready_hits,
        "closure_cached_vision_lock_ok": closure_cached_vision_lock_ok,
        "closure_cached_capture_ready_ok": closure_cached_capture_ready_ok,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "note_count": len(notes),
        "failures": failures,
        "warnings": warnings,
        "notes": notes,
        "operator_hints": operator_hints,
        "next_action_summary": next_action_summary,
        "next_action_command": next_action_command,
        "quick_mode_command": quick_mode_cmd,
        "full_mode_command": full_mode_cmd,
        "preflight_command": preflight_cmd,
        "startup_helper_command": startup_helper_cmd,
    }
    write_json(report_file, report)

    print("4.11 Acceptance Flow Report")
    print(f"result={report['result']}")
    print(f"steps_total={report['steps_total']}")
    print(f"steps_passed={report['steps_passed']}")
    print(f"steps_failed={report['steps_failed']}")
    print(f"mode={args.mode}")
    print(f"suite_name={suite_names[0]}")
    if len(suite_names) > 1:
        print(f"suite_chain={suite_chain_value}")
    if mode_defaults_applied:
        print(f"mode_defaults_applied={','.join(mode_defaults_applied)}")
    print(f"preflight_result={preflight_result}")
    print(f"preflight_fail_fast_scope={args.preflight_fail_fast_scope}")
    if preflight_fail_fast_reason:
        print(f"preflight_fail_fast_reason={preflight_fail_fast_reason}")
    print(f"preflight_can_start_live_stack={int(preflight_can_start_live_stack)}")
    print(f"preflight_can_run_acceptance={int(preflight_can_run_acceptance)}")
    print(f"usb_result={usb_result}")
    print(f"closure_result={closure_result}")
    print(f"closure_latest_event_id={closure_latest_event_id}")
    print(f"closure_export_count={closure_export_count}")
    print(f"closure_export_detail_ok={closure_export_detail_ok}")
    print(f"closure_vision_lock_hits={closure_vision_lock_hits}")
    print(f"closure_capture_ready_hits={closure_capture_ready_hits}")
    print(f"closure_vision_lock_ok={closure_vision_lock_ok}")
    print(f"closure_capture_ready_ok={closure_capture_ready_ok}")
    print(f"preflight_command={preflight_cmd}")
    print(f"startup_helper_command={startup_helper_cmd}")
    print(f"failure_count={report['failure_count']}")
    print(f"warning_count={report['warning_count']}")
    print(f"note_count={report['note_count']}")
    if next_action_summary:
        print(f"next_action_summary={next_action_summary}")
    if next_action_command:
        print(f"next_action_command={next_action_command}")
    print(f"report_file={report_file.as_posix()}")
    for item in failures:
        print(f"- {item}")
    for item in warnings:
        print(f"- {item}")
    for item in notes:
        print(f"- note:{item}")
    for item in operator_hints:
        print(f"- hint:{item}")

    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())






