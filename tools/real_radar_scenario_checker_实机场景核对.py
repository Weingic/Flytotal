# ??????????????????????????????????????????????
import argparse
import json
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def snapshot_fields(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "main_state": str(status.get("main_state", "UNKNOWN") or "UNKNOWN"),
        "hunter_state": str(status.get("hunter_state", "UNKNOWN") or "UNKNOWN"),
        "gimbal_state": str(status.get("gimbal_state", "UNKNOWN") or "UNKNOWN"),
        "rid_status": str(status.get("rid_status", "UNKNOWN") or "UNKNOWN"),
        "track_active": to_int(status.get("track_active", 0)),
        "track_confirmed": to_int(status.get("track_confirmed", 0)),
        "event_active": to_int(status.get("event_active", 0)),
        "event_id": str(status.get("event_id", "NONE") or "NONE"),
        "risk_level": str(status.get("risk_level", "NONE") or "NONE"),
        "risk_score": round(to_float(status.get("risk_score", 0.0)), 2),
        "x_mm": round(to_float(status.get("x_mm", 0.0)), 1),
        "y_mm": round(to_float(status.get("y_mm", 0.0)), 1),
        "consistency_status": str(status.get("consistency_status", "UNKNOWN") or "UNKNOWN"),
        "stale_age_ms": to_int(status.get("stale_age_ms", 0)),
    }


def evaluate_sustained_target(samples: list[dict[str, Any]], min_active_hits: int, min_confirmed_hits: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    active_hits = sum(1 for sample in samples if sample["track_active"] == 1)
    confirmed_hits = sum(1 for sample in samples if sample["track_confirmed"] == 1)
    non_idle_hits = sum(1 for sample in samples if sample["main_state"] != "IDLE")
    bad_consistency_hits = sum(1 for sample in samples if sample["consistency_status"] == "WARN")

    if active_hits < min_active_hits:
        reasons.append(f"active_hits too low: {active_hits} < {min_active_hits}")
    if confirmed_hits < min_confirmed_hits:
        reasons.append(f"confirmed_hits too low: {confirmed_hits} < {min_confirmed_hits}")
    if non_idle_hits == 0:
        reasons.append("main_state stayed IDLE for all samples")
    if bad_consistency_hits > max(1, len(samples) // 2):
        reasons.append(f"consistency WARN too often: {bad_consistency_hits}/{len(samples)}")

    return (len(reasons) == 0), reasons


def evaluate_track_lost(samples: list[dict[str, Any]], min_lost_hits: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    had_active = any(sample["track_active"] == 1 or sample["track_confirmed"] == 1 for sample in samples)
    lost_hits = sum(
        1
        for sample in samples
        if sample["main_state"] == "LOST" or (sample["track_active"] == 0 and sample["gimbal_state"] == "LOST")
    )
    last_sample = samples[-1] if samples else {}

    if not had_active:
        reasons.append("never observed active/confirmed track before loss")
    if lost_hits < min_lost_hits:
        reasons.append(f"lost_hits too low: {lost_hits} < {min_lost_hits}")
    if to_int(last_sample.get("track_active", 1), 1) != 0:
        reasons.append("last sample still has track_active=1")

    return (len(reasons) == 0), reasons


def evaluate_track_lost_phased(
    phase1_samples: list[dict[str, Any]],
    phase2_samples: list[dict[str, Any]],
    min_phase1_active_hits: int,
    min_lost_hits: int,
) -> tuple[bool, list[str], dict[str, int]]:
    reasons: list[str] = []

    phase1_active_hits = sum(
        1 for sample in phase1_samples if sample["track_active"] == 1 or sample["track_confirmed"] == 1
    )
    phase2_lost_hits = sum(
        1
        for sample in phase2_samples
        if sample["main_state"] == "LOST" or (sample["track_active"] == 0 and sample["gimbal_state"] == "LOST")
    )
    phase2_active_hits = sum(1 for sample in phase2_samples if sample["track_active"] == 1)
    last_sample = phase2_samples[-1] if phase2_samples else (phase1_samples[-1] if phase1_samples else {})

    if phase1_active_hits < min_phase1_active_hits:
        reasons.append(f"phase1_active_hits too low: {phase1_active_hits} < {min_phase1_active_hits}")
    if phase2_lost_hits < min_lost_hits:
        reasons.append(f"phase2_lost_hits too low: {phase2_lost_hits} < {min_lost_hits}")
    if to_int(last_sample.get("track_active", 1), 1) != 0:
        reasons.append("last sample still has track_active=1")
    if phase2_active_hits > max(1, len(phase2_samples) // 2):
        reasons.append(f"phase2_active_hits too high: {phase2_active_hits}/{len(phase2_samples)}")

    metrics = {
        "phase1_total": len(phase1_samples),
        "phase2_total": len(phase2_samples),
        "phase1_active_hits": phase1_active_hits,
        "phase2_lost_hits": phase2_lost_hits,
        "phase2_active_hits": phase2_active_hits,
    }
    return (len(reasons) == 0), reasons, metrics


def scenario_description(name: str) -> str:
    if name == "sustained_target":
        return "实机场景：目标持续存在，轨迹应稳定保持 active/confirmed。"
    if name == "track_lost":
        return "实机场景：先有目标，再移走目标，系统应进入 LOST/无活跃轨迹。"
    return "UNKNOWN"


def countdown(seconds: float, message: str) -> None:
    remain = max(0, int(round(seconds)))
    if remain <= 0:
        return
    print(f"{message} ({remain}s)")
    while remain > 0:
        time.sleep(1.0)
        remain -= 1
        if remain > 0:
            print(f"... {remain}s")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record and evaluate real radar single-node scenarios for 4.9 (sustained_target / track_lost)."
    )
    parser.add_argument("--scenario", required=True, choices=["sustained_target", "track_lost"], help="Real radar scenario")
    parser.add_argument(
        "--node-status-file",
        type=Path,
        default=Path("captures/latest_node_status.json"),
        help="Bridge status JSON file",
    )
    parser.add_argument("--duration-s", type=float, default=20.0, help="Observation duration in seconds")
    parser.add_argument("--interval-s", type=float, default=0.5, help="Sampling interval in seconds")
    parser.add_argument("--warmup-s", type=float, default=2.0, help="Warmup time before sampling starts")
    parser.add_argument("--max-stale-ms", type=int, default=5000, help="Max allowed stale_age_ms in samples")
    parser.add_argument("--min-active-hits", type=int, default=4, help="For sustained_target: minimum active hits")
    parser.add_argument("--min-confirmed-hits", type=int, default=3, help="For sustained_target: minimum confirmed hits")
    parser.add_argument("--min-lost-hits", type=int, default=2, help="For track_lost: minimum lost hits")
    parser.add_argument(
        "--track-lost-phase1-ratio",
        type=float,
        default=0.5,
        help="For track_lost: first phase ratio (keep target present), second phase is target removed",
    )
    parser.add_argument(
        "--min-phase1-active-hits",
        type=int,
        default=2,
        help="For track_lost: minimum active/confirmed hits required in phase1",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("captures/real_radar_checks"),
        help="Directory to write scenario report JSON",
    )
    args = parser.parse_args()

    node_status_path = resolve_path(args.node_status_file)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    duration_s = max(2.0, float(args.duration_s))
    interval_s = max(0.2, float(args.interval_s))
    warmup_s = max(0.0, float(args.warmup_s))
    sample_total = max(3, int(duration_s / interval_s) + 1)
    phase1_total = 0
    phase2_total = 0
    phase_split_index = sample_total
    if args.scenario == "track_lost":
        ratio = min(0.8, max(0.2, float(args.track_lost_phase1_ratio)))
        phase1_total = max(1, int(sample_total * ratio))
        phase2_total = max(1, sample_total - phase1_total)
        phase_split_index = phase1_total

    print(f"Scenario: {args.scenario}")
    print(f"Description: {scenario_description(args.scenario)}")
    print(f"Status file: {node_status_path.as_posix()}")
    print(f"Sampling: warmup={warmup_s}s duration={duration_s}s interval={interval_s}s samples={sample_total}")
    if args.scenario == "track_lost":
        phase1_seconds = round(phase1_total * interval_s, 2)
        print(
            f"Phase plan: phase1_keep_target samples={phase1_total} (~{phase1_seconds}s), "
            f"phase2_remove_target samples={phase2_total}"
        )
        print("Start now: keep target present in phase1, then remove/move target away in phase2.")
    else:
        print("Start now: keep target present in this window.")

    samples: list[dict[str, Any]] = []
    stale_violations = 0
    started_ms = int(time.time() * 1000)
    phase_switch_hint_printed = False

    if warmup_s > 0:
        countdown(warmup_s, "Warmup started")
        print("Warmup done, sampling starts now.")

    for index in range(1, sample_total + 1):
        if args.scenario == "track_lost" and index == phase_split_index + 1 and not phase_switch_hint_printed:
            print("")
            print("Phase switch: now remove/move target away (phase2_remove_target).")
            phase_switch_hint_printed = True
        payload = load_json_file(node_status_path)
        sample = snapshot_fields(payload)
        sample["sample_index"] = index
        sample["sample_ts_ms"] = int(time.time() * 1000)
        if args.scenario == "track_lost":
            sample["phase"] = "phase1_keep_target" if index <= phase_split_index else "phase2_remove_target"
        else:
            sample["phase"] = "single_phase"
        samples.append(sample)

        stale_age_ms = sample["stale_age_ms"]
        if stale_age_ms > args.max_stale_ms:
            stale_violations += 1

        phase_text = ""
        if args.scenario == "track_lost":
            phase_text = f"{sample['phase']} "
        print(
            f"[{index:02d}/{sample_total}] {phase_text}main={sample['main_state']} "
            f"track={sample['track_active']}/{sample['track_confirmed']} "
            f"gimbal={sample['gimbal_state']} risk={sample['risk_level']} "
            f"consistency={sample['consistency_status']} stale={stale_age_ms}ms"
        )
        if index < sample_total:
            time.sleep(interval_s)

    if args.scenario == "sustained_target":
        ok, reasons = evaluate_sustained_target(samples, args.min_active_hits, args.min_confirmed_hits)
        scenario_metrics = {}
    elif args.scenario == "track_lost":
        phase1_samples = samples[:phase_split_index]
        phase2_samples = samples[phase_split_index:]
        ok, reasons, scenario_metrics = evaluate_track_lost_phased(
            phase1_samples=phase1_samples,
            phase2_samples=phase2_samples,
            min_phase1_active_hits=max(1, int(args.min_phase1_active_hits)),
            min_lost_hits=max(1, int(args.min_lost_hits)),
        )
    else:
        ok, reasons = evaluate_track_lost(samples, args.min_lost_hits)
        scenario_metrics = {}

    if stale_violations > 0:
        reasons.append(f"stale_age_ms exceeded max in {stale_violations}/{len(samples)} samples")
        ok = False

    finished_ms = int(time.time() * 1000)
    status_label = "PASS" if ok else "FAIL"
    report = {
        "ok": ok,
        "result": status_label,
        "scenario": args.scenario,
        "description": scenario_description(args.scenario),
        "started_ms": started_ms,
        "finished_ms": finished_ms,
        "duration_s": duration_s,
        "warmup_s": warmup_s,
        "interval_s": interval_s,
        "sample_total": len(samples),
        "max_stale_ms": args.max_stale_ms,
        "stale_violations": stale_violations,
        "reasons": reasons if reasons else ["PASS"],
        "samples": samples,
        "thresholds": {
            "min_active_hits": args.min_active_hits,
            "min_confirmed_hits": args.min_confirmed_hits,
            "min_lost_hits": args.min_lost_hits,
            "track_lost_phase1_ratio": args.track_lost_phase1_ratio,
            "min_phase1_active_hits": args.min_phase1_active_hits,
        },
        "scenario_metrics": scenario_metrics,
        "phase_windows": {
            "phase1_start_index": 1,
            "phase1_end_index": phase_split_index if args.scenario == "track_lost" else len(samples),
            "phase2_start_index": (phase_split_index + 1) if args.scenario == "track_lost" else 0,
            "phase2_end_index": len(samples) if args.scenario == "track_lost" else 0,
        },
    }

    report_path = output_dir / f"{started_ms}_{args.scenario}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print("Real Radar Scenario Report")
    print(f"scenario={args.scenario}")
    print(f"result={status_label}")
    print(f"sample_total={len(samples)}")
    print(f"stale_violations={stale_violations}")
    if scenario_metrics:
        print("scenario_metrics:")
        for key, value in scenario_metrics.items():
            print(f"- {key}={value}")
    print(f"report_file={report_path.as_posix()}")
    if reasons:
        print("reasons:")
        for item in reasons:
            print(f"- {item}")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
