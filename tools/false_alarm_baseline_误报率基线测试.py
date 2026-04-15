# 误报率基线测试框架
# 支持场景：纯空场、静态扰动
# 输出：事件数统计、误报率、原始记录
#
# 使用方式（本地 mock 验证，无需真机）：
#   python tools/false_alarm_baseline_误报率基线测试.py --mode empty --duration 60
#   python tools/false_alarm_baseline_误报率基线测试.py --mode static_disturbance --duration 60
#   python tools/false_alarm_baseline_误报率基线测试.py --mode empty --node-events-file captures/latest_node_events.json
import argparse
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 场景类型
SCENARIO_EMPTY = "empty"              # 纯空场：无目标，期望事件数 = 0
SCENARIO_STATIC = "static_disturbance"  # 静态扰动：固定非飞行物，期望事件数 = 0

VALID_SCENARIOS = (SCENARIO_EMPTY, SCENARIO_STATIC)


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def normalize_event_id(value: object) -> str:
    text = str(value or "").strip()
    return "" if not text or text.upper() == "NONE" else text


@dataclass
class EventRecord:
    event_id: str
    reason: str
    risk_score: float
    event_status: str
    timestamp_ms: int
    source: str = ""


@dataclass
class FalseAlarmResult:
    scenario: str
    duration_s: float
    started_ms: int
    finished_ms: int
    expected_event_count: int       # 该场景期望触发的事件数（误报基线 = 0）
    observed_event_count: int       # 实际观测到的事件数
    false_alarm_count: int          # 超出期望的数量
    false_alarm_rate: float         # false_alarm_count / max(observed, 1)
    events: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    def passed(self) -> bool:
        return self.false_alarm_count == 0


# ---------------------------------------------------------------------------
# 事件采集
# ---------------------------------------------------------------------------

def collect_events_from_file(node_events_file: Path, since_ms: int, until_ms: int) -> list[EventRecord]:
    """从 node_events JSON 文件读取时间窗口内的事件记录。"""
    payload = load_json_file(node_events_file)
    records = payload.get("records", [])
    if not isinstance(records, list):
        return []

    result: list[EventRecord] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        ts = safe_int(item.get("timestamp_ms", item.get("host_logged_ms", 0)))
        if ts < since_ms or ts > until_ms:
            continue
        event_id = normalize_event_id(item.get("event_id", ""))
        if not event_id:
            continue
        result.append(EventRecord(
            event_id=event_id,
            reason=str(item.get("reason", "NONE")),
            risk_score=float(item.get("risk_score", 0.0) or 0.0),
            event_status=str(item.get("event_status", "UNKNOWN")),
            timestamp_ms=ts,
            source="node_events_file",
        ))
    return result


def collect_events_from_event_store(store_file: Path, since_ms: int, until_ms: int) -> list[EventRecord]:
    """从持久化 event_store 文件读取时间窗口内的事件。"""
    payload = load_json_file(store_file)
    records = payload.get("records", [])
    if not isinstance(records, list):
        return []

    result: list[EventRecord] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        ts = safe_int(item.get("host_logged_ms", item.get("timestamp_ms", 0)))
        if ts < since_ms or ts > until_ms:
            continue
        event_id = normalize_event_id(item.get("event_id", ""))
        if not event_id:
            continue
        result.append(EventRecord(
            event_id=event_id,
            reason=str(item.get("reason", "NONE")),
            risk_score=float(item.get("risk_score", 0.0) or 0.0),
            event_status=str(item.get("event_status", "UNKNOWN")),
            timestamp_ms=ts,
            source="event_store",
        ))
    return result


def deduplicate_events(events: list[EventRecord]) -> list[EventRecord]:
    """按 event_id 去重，保留最早记录。"""
    seen: dict[str, EventRecord] = {}
    for ev in sorted(events, key=lambda e: e.timestamp_ms):
        if ev.event_id not in seen:
            seen[ev.event_id] = ev
    return list(seen.values())


# ---------------------------------------------------------------------------
# 场景运行器
# ---------------------------------------------------------------------------

def run_scenario(
    scenario: str,
    duration_s: float,
    node_events_file: Path,
    event_store_file: Path,
    poll_interval_s: float = 2.0,
    verbose: bool = False,
) -> FalseAlarmResult:
    """执行一次误报率测试场景，返回结果。

    实时模式：在 duration_s 时间窗口内轮询文件，累计事件。
    mock 模式（duration_s <= 0）：直接读文件全量，不等待。
    """
    started_ms = int(time.time() * 1000)
    print(f"[false_alarm] 场景={scenario} 时长={duration_s:.0f}s 开始 ts={started_ms}")

    collected: list[EventRecord] = []

    if duration_s > 0:
        deadline = time.time() + duration_s
        while time.time() < deadline:
            remaining = deadline - time.time()
            if verbose:
                print(f"[false_alarm] 剩余 {remaining:.0f}s ...")
            time.sleep(min(poll_interval_s, max(0.1, remaining)))

        finished_ms = int(time.time() * 1000)
        ev_from_events = collect_events_from_file(node_events_file, started_ms, finished_ms)
        ev_from_store = collect_events_from_event_store(event_store_file, started_ms, finished_ms)
        collected = deduplicate_events(ev_from_events + ev_from_store)
    else:
        # mock / 离线模式：扫全量文件
        finished_ms = int(time.time() * 1000)
        ev_from_events = collect_events_from_file(node_events_file, 0, finished_ms)
        ev_from_store = collect_events_from_event_store(event_store_file, 0, finished_ms)
        collected = deduplicate_events(ev_from_events + ev_from_store)

    expected = 0  # 空场和静态扰动场景期望事件数均为 0
    observed = len(collected)
    false_alarms = max(0, observed - expected)
    rate = false_alarms / max(observed, 1) if observed > 0 else 0.0

    result = FalseAlarmResult(
        scenario=scenario,
        duration_s=duration_s,
        started_ms=started_ms,
        finished_ms=finished_ms,
        expected_event_count=expected,
        observed_event_count=observed,
        false_alarm_count=false_alarms,
        false_alarm_rate=round(rate, 4),
        events=[asdict(ev) for ev in collected],
        note=f"scenario={scenario},expected={expected},observed={observed}",
    )
    return result


# ---------------------------------------------------------------------------
# 结果输出
# ---------------------------------------------------------------------------

def print_result(result: FalseAlarmResult) -> None:
    status = "PASS" if result.passed() else "FAIL"
    print(f"[false_alarm] 结果={status} 场景={result.scenario}")
    print(f"  观测事件数={result.observed_event_count} 期望={result.expected_event_count} "
          f"误报数={result.false_alarm_count} 误报率={result.false_alarm_rate:.2%}")
    if result.events:
        print(f"  触发事件（前5条）：")
        for ev in result.events[:5]:
            print(f"    event_id={ev['event_id']} reason={ev['reason']} "
                  f"risk_score={ev['risk_score']} ts={ev['timestamp_ms']}")


def write_result(output_file: Path, result: FalseAlarmResult) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["passed"] = result.passed()
    payload["result_label"] = "PASS" if result.passed() else "FAIL"
    temp = output_file.with_suffix(output_file.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(output_file)
    print(f"[false_alarm] 结果已写入 {output_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="误报率基线测试框架")
    parser.add_argument("--mode", choices=list(VALID_SCENARIOS), default=SCENARIO_EMPTY,
                        help="测试场景：empty=纯空场 static_disturbance=静态扰动")
    parser.add_argument("--duration", type=float, default=0,
                        help="采集时长（秒）。0=离线模式，直接读现有文件")
    parser.add_argument("--poll-interval", type=float, default=2.0,
                        help="轮询间隔（秒），仅在 duration>0 时有效")
    parser.add_argument("--node-events-file", type=Path,
                        default=Path("captures/latest_node_events.json"))
    parser.add_argument("--event-store-file", type=Path,
                        default=Path("captures/latest_node_event_store.json"))
    parser.add_argument("--output-file", type=Path,
                        default=Path("captures/false_alarm_result.json"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    node_events_file = resolve_path(args.node_events_file)
    event_store_file = resolve_path(args.event_store_file)
    output_file = resolve_path(args.output_file)

    result = run_scenario(
        scenario=args.mode,
        duration_s=args.duration,
        node_events_file=node_events_file,
        event_store_file=event_store_file,
        poll_interval_s=args.poll_interval,
        verbose=args.verbose,
    )
    print_result(result)
    write_result(output_file, result)
    return 0 if result.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
