# ??????? bridge ????? API ????????????????????stale_age ?????????
import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent


CHECK_FIELDS: list[tuple[str, str]] = [
    ("main_state", "str"),
    ("hunter_state", "str"),
    ("gimbal_state", "str"),
    ("rid_status", "str"),
    ("risk_score", "float"),
    ("risk_level", "str"),
    ("track_id", "int"),
    ("track_active", "int"),
    ("track_confirmed", "int"),
    ("x_mm", "float"),
    ("y_mm", "float"),
    ("event_active", "int"),
    ("event_id", "str"),
    ("last_event_id", "str"),
    ("last_reason", "str"),
    ("last_message_type", "str"),
    ("consistency_status", "str"),
    ("consistency_expected_main_state", "str"),
    ("consistency_warning_count", "int"),
]


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "available": False, "error": "file_not_found"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "available": False, "error": "invalid_json"}
    if not isinstance(payload, dict):
        return {"ok": False, "available": False, "error": "invalid_payload"}
    return payload


def fetch_json(url: str, timeout_s: float) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout_s) as response:
            content = response.read().decode("utf-8", errors="ignore")
    except URLError as exc:
        return {"ok": False, "available": False, "error": f"request_failed: {exc}"}
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return {"ok": False, "available": False, "error": "invalid_json_response"}
    if not isinstance(payload, dict):
        return {"ok": False, "available": False, "error": "invalid_response_payload"}
    return payload


def normalize_value(raw: Any, value_type: str) -> Any:
    if value_type == "str":
        return str(raw if raw is not None else "").strip().upper()
    if value_type == "int":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    if value_type == "float":
        try:
            return round(float(raw), 3)
        except (TypeError, ValueError):
            return 0.0
    return raw


def compare_field(local_payload: dict[str, Any], web_payload: dict[str, Any], field: str, value_type: str) -> tuple[bool, str]:
    local_value = normalize_value(local_payload.get(field), value_type)
    web_value = normalize_value(web_payload.get(field), value_type)
    ok = local_value == web_value
    detail = f"{field}: local={local_value} web={web_value}"
    return ok, detail


def print_line(prefix: str, message: str) -> None:
    print(f"[{prefix}] {message}")


def evaluate_once(args: argparse.Namespace, sample_index: int = 0, sample_total: int = 0) -> dict[str, Any]:
    node_status_path = resolve_path(args.node_status_file)
    local_payload = load_json_file(node_status_path)
    health_payload = fetch_json(f"{args.base_url}/api/health", args.timeout_s)
    data_source_payload = fetch_json(f"{args.base_url}/api/data-source", args.timeout_s)
    web_node_payload = fetch_json(f"{args.base_url}/api/node-status", args.timeout_s)

    failures: list[str] = []
    sample_label = ""
    if sample_total > 0:
        sample_label = f"[sample {sample_index}/{sample_total}] "

    def emit(prefix: str, message: str) -> None:
        if prefix == "PASS" and args.quiet_pass:
            return
        print_line(prefix, f"{sample_label}{message}")

    health_ok = bool(health_payload.get("ok"))
    web_available = bool(web_node_payload.get("available"))

    if health_ok:
        emit("PASS", "web server health ok")
    else:
        message = str(health_payload.get("error", "health_api_failed"))
        failures.append(f"health_api: {message}")
        emit("FAIL", f"web server health failed ({message})")

    data_source_error = str(data_source_payload.get("error", "") or "")
    mode = str(data_source_payload.get("mode", "unknown")).strip().lower()
    if data_source_error:
        if health_ok:
            failures.append(f"data_source_api: {data_source_error}")
            emit("FAIL", f"data source api failed ({data_source_error})")
        else:
            emit("INFO", "skip data source check because health api is unavailable")
    elif not args.allow_mock and mode != "live":
        failures.append(f"data_source_mode expected live but got {mode}")
        emit("FAIL", f"data source mode is {mode} (expected live)")
    else:
        emit("PASS", f"data source mode={mode}")

    if bool(local_payload.get("available")):
        emit("PASS", f"bridge file available ({node_status_path.as_posix()})")
    else:
        message = str(local_payload.get("error", "bridge_file_unavailable"))
        failures.append(f"bridge_file: {message}")
        emit("FAIL", f"bridge file unavailable ({message})")

    if web_available:
        emit("PASS", "web node status available")
    else:
        message = str(web_node_payload.get("error", "web_node_status_unavailable"))
        failures.append(f"web_node_status: {message}")
        emit("FAIL", f"web node status unavailable ({message})")

    api_unreachable = (not health_ok) or (not web_available)

    stale_age_ms = int(web_node_payload.get("stale_age_ms", 0) or 0)
    if api_unreachable:
        emit("INFO", "skip stale check and field compare because web api is unavailable")
    elif stale_age_ms > args.max_stale_ms:
        failures.append(f"stale_age_ms too high: {stale_age_ms} > {args.max_stale_ms}")
        emit("FAIL", f"stale_age_ms={stale_age_ms} (max {args.max_stale_ms})")
    else:
        emit("PASS", f"stale_age_ms={stale_age_ms}")

    checked_count = 0
    mismatch_count = 0
    if not api_unreachable:
        for field, value_type in CHECK_FIELDS:
            checked_count += 1
            ok, detail = compare_field(local_payload, web_node_payload, field, value_type)
            if ok:
                emit("PASS", detail)
            else:
                mismatch_count += 1
                failures.append(f"field_mismatch: {detail}")
                emit("FAIL", detail)

    if sample_total > 0 and args.quiet_pass:
        result_label = "PASS" if not failures else "FAIL"
        print(
            f"Node-Web Consistency Report sample={sample_index}/{sample_total} "
            f"checked_fields={checked_count} mismatches={mismatch_count} failures={len(failures)} result={result_label}"
        )
    else:
        print("")
        print("Node-Web Consistency Report")
        if sample_total > 0:
            print(f"sample={sample_index}/{sample_total}")
        print(f"checked_fields={checked_count}")
        print(f"mismatches={mismatch_count}")
        print(f"failures={len(failures)}")
        if failures:
            print("result=FAIL")
            print("failure_items:")
            for item in failures:
                print(f"- {item}")
        else:
            print("result=PASS")

    if not failures:
        return {
            "ok": True,
            "checked_fields": checked_count,
            "mismatches": mismatch_count,
            "failures": [],
            "api_unreachable": False,
        }

    return {
        "ok": False,
        "checked_fields": checked_count,
        "mismatches": mismatch_count,
        "failures": failures,
        "api_unreachable": api_unreachable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Node A bridge file and web API field consistency for 4.9 single-node realtime linkage."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Vision web server base URL")
    parser.add_argument(
        "--node-status-file",
        type=Path,
        default=Path("captures/latest_node_status.json"),
        help="Bridge output JSON file",
    )
    parser.add_argument("--timeout-s", type=float, default=2.0, help="HTTP request timeout in seconds")
    parser.add_argument("--max-stale-ms", type=int, default=5000, help="Max allowed stale_age_ms for web node status")
    parser.add_argument("--allow-mock", action="store_true", help="Allow /api/data-source mode=mock")
    parser.add_argument("--watch-seconds", type=float, default=0.0, help="Watch mode duration in seconds (0=single check)")
    parser.add_argument("--interval-s", type=float, default=1.0, help="Watch mode sampling interval in seconds")
    parser.add_argument(
        "--max-fail-samples",
        type=int,
        default=0,
        help="Allowed failed samples in watch mode (default 0 means all samples must pass)",
    )
    parser.add_argument("--quiet-pass", action="store_true", help="Only print FAIL lines for each sample")
    parser.add_argument(
        "--no-abort-on-api-fail",
        action="store_true",
        help="Do not stop watch mode early when first sample cannot reach web api",
    )
    args = parser.parse_args()

    if args.watch_seconds <= 0:
        result = evaluate_once(args)
        return 0 if result["ok"] else 2

    interval_s = max(0.2, float(args.interval_s))
    duration_s = max(0.2, float(args.watch_seconds))
    total_samples = max(1, int(duration_s / interval_s) + 1)
    pass_samples = 0
    fail_samples = 0
    failures_by_sample: list[tuple[int, list[str]]] = []

    for index in range(1, total_samples + 1):
        if index > 1:
            print("")
        result = evaluate_once(args, sample_index=index, sample_total=total_samples)
        if result["ok"]:
            pass_samples += 1
        else:
            fail_samples += 1
            failures_by_sample.append((index, list(result.get("failures", []))))
            if index == 1 and result.get("api_unreachable", False) and not args.no_abort_on_api_fail:
                print("watch_abort=API_UNREACHABLE_ON_FIRST_SAMPLE")
                break
        if index < total_samples:
            time.sleep(interval_s)

    actual_samples = pass_samples + fail_samples

    print("")
    print("Node-Web Consistency Watch Report")
    print(f"watch_seconds={duration_s}")
    print(f"interval_seconds={interval_s}")
    print(f"samples={actual_samples}/{total_samples}")
    print(f"pass_samples={pass_samples}")
    print(f"fail_samples={fail_samples}")
    print(f"max_fail_samples={args.max_fail_samples}")

    if fail_samples > args.max_fail_samples:
        print("result=FAIL")
        print("failure_summary:")
        reason_counts: dict[str, int] = {}
        for _, failures in failures_by_sample:
            for item in failures:
                reason_counts[item] = reason_counts.get(item, 0) + 1
        for reason, count in sorted(reason_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:10]:
            print(f"- {reason} (count={count})")
        return 2

    print("result=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
