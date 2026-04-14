# ????????????????????????????????????????? PASS/FAIL?
import argparse
import json
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


DEFAULT_SCENARIOS = ["sustained_target", "track_lost"]


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def summarize_reports(
    reports_dir: Path,
    required_scenarios: list[str],
    max_age_hours: float,
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    max_age_ms = int(max(0.1, max_age_hours) * 3600 * 1000)

    latest_by_scenario: dict[str, dict[str, Any]] = {}
    report_files = sorted(reports_dir.glob("*.json"))

    for report_path in report_files:
        payload = load_json_file(report_path)
        if payload is None:
            continue
        scenario = str(payload.get("scenario", "") or "")
        if not scenario:
            continue
        started_ms = to_int(payload.get("started_ms", 0), 0)
        existing = latest_by_scenario.get(scenario)
        if existing is None or started_ms > to_int(existing.get("started_ms", 0), 0):
            payload["report_file"] = report_path.as_posix()
            latest_by_scenario[scenario] = payload

    scenario_items: list[dict[str, Any]] = []
    failures: list[str] = []

    for scenario in required_scenarios:
        latest = latest_by_scenario.get(scenario)
        if latest is None:
            failures.append(f"{scenario}: missing_report")
            scenario_items.append(
                {
                    "scenario": scenario,
                    "available": False,
                    "ok": False,
                    "result": "MISSING",
                    "age_minutes": None,
                    "started_ms": 0,
                    "report_file": "NONE",
                    "reasons": ["missing_report"],
                }
            )
            continue

        started_ms = to_int(latest.get("started_ms", 0), 0)
        age_ms = max(0, now_ms - started_ms)
        age_minutes = round(age_ms / 60000.0, 2)
        ok = bool(latest.get("ok", False))
        reasons = latest.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = [str(reasons)]

        if age_ms > max_age_ms:
            ok = False
            failures.append(f"{scenario}: report_too_old age_minutes={age_minutes}")
            reasons = [*reasons, f"report_too_old age_minutes={age_minutes}"]

        if not bool(latest.get("ok", False)):
            failures.append(f"{scenario}: report_result={latest.get('result', 'FAIL')}")

        scenario_items.append(
            {
                "scenario": scenario,
                "available": True,
                "ok": ok,
                "result": str(latest.get("result", "UNKNOWN") or "UNKNOWN"),
                "age_minutes": age_minutes,
                "started_ms": started_ms,
                "report_file": str(latest.get("report_file", "NONE") or "NONE"),
                "reasons": reasons[:6],
            }
        )

    overall_ok = len(failures) == 0
    return {
        "ok": overall_ok,
        "result": "PASS" if overall_ok else "FAIL",
        "checked_at_ms": now_ms,
        "reports_dir": reports_dir.as_posix(),
        "required_scenarios": required_scenarios,
        "max_age_hours": max_age_hours,
        "scenarios": scenario_items,
        "failures": failures,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize latest real radar scenario reports and output a single PASS/FAIL result."
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("captures/real_radar_checks"),
        help="Directory containing real radar scenario report JSON files",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("captures/latest_real_radar_summary.json"),
        help="Summary JSON output path",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=24.0,
        help="Max allowed report age in hours for each required scenario",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=DEFAULT_SCENARIOS,
        help="Required scenarios to include in summary",
    )
    args = parser.parse_args()

    reports_dir = resolve_path(args.reports_dir)
    output_file = resolve_path(args.output_file)
    required_scenarios = [str(item).strip() for item in args.scenarios if str(item).strip()]
    if not required_scenarios:
        required_scenarios = list(DEFAULT_SCENARIOS)

    summary = summarize_reports(reports_dir, required_scenarios, args.max_age_hours)
    write_json(output_file, summary)

    print("Real Radar Reports Summary")
    print(f"result={summary['result']}")
    print(f"output_file={output_file.as_posix()}")
    print(f"required_scenarios={','.join(required_scenarios)}")
    for item in summary["scenarios"]:
        scenario = item["scenario"]
        status = "PASS" if item["ok"] else "FAIL"
        age_text = "NONE" if item["age_minutes"] is None else f"{item['age_minutes']}"
        print(f"- {scenario}: {status} age_minutes={age_text} file={item['report_file']}")
    if summary["failures"]:
        print("failures:")
        for failure in summary["failures"]:
            print(f"- {failure}")

    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

