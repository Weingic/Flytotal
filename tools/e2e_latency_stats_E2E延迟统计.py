# E2E 延迟统计框架
# 记录注入时刻 → 事件输出时刻，计算平均 / 最大 / 最小延迟
#
# 使用方式：
#   python tools/e2e_latency_stats_E2E延迟统计.py \
#       --session-log captures/session_logs/1234567890_standard_acceptance.jsonl \
#       --output captures/e2e_latency_result.json
#
# 离线分析模式（读已有 session log，不需要真机）：
#   python tools/e2e_latency_stats_E2E延迟统计.py --session-log <path>
import argparse
import json
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# session_log 中的事件类型
EVENT_TYPE_INJECT = "suite_started"       # 轨迹注入开始（注入时刻基准）
EVENT_TYPE_TRACK_INJECT = "track_point_sent"  # 单个轨迹点发送
EVENT_TYPE_NODE_EVENT = "node_event"      # 固件事件输出（事件时刻）
EVENT_TYPE_NODE_STATUS = "node_status_changed"


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class InjectionPoint:
    ts_ms: int          # 注入时刻
    x_mm: float
    y_mm: float
    scenario_name: str
    point_index: int = 0


@dataclass
class EventOutput:
    ts_ms: int          # 固件事件输出时刻
    event_id: str
    reason: str
    risk_score: float
    scenario_name: str


@dataclass
class LatencySample:
    injection_ts_ms: int
    event_ts_ms: int
    latency_ms: int
    event_id: str
    reason: str
    scenario_name: str


@dataclass
class E2ELatencyResult:
    scenario_name: str
    session_log: str
    sample_count: int
    latency_ms_mean: float
    latency_ms_min: int
    latency_ms_max: int
    latency_ms_p50: float
    latency_ms_p95: float
    samples: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    def passed(self, max_allowed_ms: int = 3000) -> bool:
        """默认 P95 ≤ 3000ms 为合格。"""
        return self.sample_count > 0 and self.latency_ms_p95 <= max_allowed_ms


# ---------------------------------------------------------------------------
# Session log 解析
# ---------------------------------------------------------------------------

def load_session_log(path: Path) -> list[dict[str, Any]]:
    """加载 JSONL 格式的 session log，每行一条记录。"""
    if not path.exists():
        print(f"[e2e] session log 不存在: {path}")
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def extract_injection_points(records: list[dict[str, Any]]) -> list[InjectionPoint]:
    """从 session log 提取轨迹注入时刻。

    优先使用 track_point_sent 事件（每个注入点）；
    如无，退化使用 suite_started 时刻作为单一基准。
    """
    points: list[InjectionPoint] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        event_type = str(rec.get("event_type", ""))
        ts_ms = safe_int(rec.get("ts_ms", 0))
        payload = rec.get("payload", {}) or {}
        scenario = str(rec.get("scenario_name", ""))

        if event_type == EVENT_TYPE_TRACK_INJECT:
            points.append(InjectionPoint(
                ts_ms=ts_ms,
                x_mm=float(payload.get("x_mm", 0.0) or 0.0),
                y_mm=float(payload.get("y_mm", 0.0) or 0.0),
                scenario_name=scenario,
                point_index=safe_int(payload.get("point_index", len(points))),
            ))
        elif event_type == EVENT_TYPE_INJECT and not points:
            # 退化基准：取 suite_started 时刻
            points.append(InjectionPoint(
                ts_ms=ts_ms,
                x_mm=float(payload.get("x_mm", 0.0) or 0.0),
                y_mm=float(payload.get("y_mm", 0.0) or 0.0),
                scenario_name=scenario,
                point_index=0,
            ))
    return points


def extract_event_outputs(records: list[dict[str, Any]]) -> list[EventOutput]:
    """从 session log 提取固件事件输出时刻。"""
    outputs: list[EventOutput] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if str(rec.get("event_type", "")) != EVENT_TYPE_NODE_EVENT:
            continue
        ts_ms = safe_int(rec.get("ts_ms", 0))
        payload = rec.get("payload", {}) or {}
        reason = str(payload.get("reason", "NONE"))
        # 只计 EVENT_OPENED / HIGH_RISK_ENTER 类事件（首次触发，不计关闭）
        if reason not in {"EVENT_OPENED", "HIGH_RISK_ENTER", "RISK_ELEVATED"}:
            continue
        outputs.append(EventOutput(
            ts_ms=ts_ms,
            event_id=str(payload.get("event_id", "NONE")),
            reason=reason,
            risk_score=float(payload.get("risk_score", 0.0) or 0.0),
            scenario_name=str(rec.get("scenario_name", "")),
        ))
    return outputs


# ---------------------------------------------------------------------------
# 延迟配对
# ---------------------------------------------------------------------------

def pair_latencies(
    injections: list[InjectionPoint],
    outputs: list[EventOutput],
    max_window_ms: int = 30_000,
) -> list[LatencySample]:
    """将注入点和事件输出按时间顺序最近配对。

    策略：对每个事件输出，找其之前最近的注入点，计算延迟。
    超过 max_window_ms 的配对视为无效（跳过）。
    """
    if not injections or not outputs:
        return []

    inj_sorted = sorted(injections, key=lambda p: p.ts_ms)
    out_sorted = sorted(outputs, key=lambda e: e.ts_ms)
    samples: list[LatencySample] = []

    for ev in out_sorted:
        # 找 ev.ts_ms 之前最近的注入点
        best: InjectionPoint | None = None
        for inj in reversed(inj_sorted):
            if inj.ts_ms <= ev.ts_ms:
                best = inj
                break
        if best is None:
            continue
        latency = ev.ts_ms - best.ts_ms
        if latency < 0 or latency > max_window_ms:
            continue
        samples.append(LatencySample(
            injection_ts_ms=best.ts_ms,
            event_ts_ms=ev.ts_ms,
            latency_ms=latency,
            event_id=ev.event_id,
            reason=ev.reason,
            scenario_name=ev.scenario_name,
        ))
    return samples


# ---------------------------------------------------------------------------
# 统计计算
# ---------------------------------------------------------------------------

def compute_stats(samples: list[LatencySample], session_log: str, scenario_name: str) -> E2ELatencyResult:
    if not samples:
        return E2ELatencyResult(
            scenario_name=scenario_name,
            session_log=session_log,
            sample_count=0,
            latency_ms_mean=0.0,
            latency_ms_min=0,
            latency_ms_max=0,
            latency_ms_p50=0.0,
            latency_ms_p95=0.0,
            note="无有效配对样本",
        )

    latencies = [s.latency_ms for s in samples]
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50 = statistics.median(sorted_lat)
    p95_idx = min(int(n * 0.95), n - 1)
    p95 = float(sorted_lat[p95_idx])

    return E2ELatencyResult(
        scenario_name=scenario_name,
        session_log=session_log,
        sample_count=n,
        latency_ms_mean=round(statistics.mean(latencies), 1),
        latency_ms_min=min(latencies),
        latency_ms_max=max(latencies),
        latency_ms_p50=round(p50, 1),
        latency_ms_p95=round(p95, 1),
        samples=[asdict(s) for s in samples],
        note=f"samples={n},mean={statistics.mean(latencies):.0f}ms,p95={p95:.0f}ms",
    )


# ---------------------------------------------------------------------------
# 结果输出
# ---------------------------------------------------------------------------

def print_result(result: E2ELatencyResult, max_allowed_ms: int = 3000) -> None:
    status = "PASS" if result.passed(max_allowed_ms) else "FAIL"
    print(f"[e2e] 结果={status} 场景={result.scenario_name} 样本数={result.sample_count}")
    if result.sample_count > 0:
        print(f"  平均延迟={result.latency_ms_mean:.0f}ms  "
              f"最小={result.latency_ms_min}ms  最大={result.latency_ms_max}ms")
        print(f"  P50={result.latency_ms_p50:.0f}ms  P95={result.latency_ms_p95:.0f}ms  "
              f"阈值={max_allowed_ms}ms")
    else:
        print("  无有效样本（检查 session log 中是否有 track_point_sent 和 node_event 记录）")


def write_result(output_file: Path, result: E2ELatencyResult, max_allowed_ms: int) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["passed"] = result.passed(max_allowed_ms)
    payload["result_label"] = "PASS" if result.passed(max_allowed_ms) else "FAIL"
    payload["max_allowed_ms"] = max_allowed_ms
    temp = output_file.with_suffix(output_file.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(output_file)
    print(f"[e2e] 结果已写入 {output_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="E2E 延迟统计框架")
    parser.add_argument("--session-log", type=Path, required=False,
                        help="session log JSONL 文件路径（不传则扫 session_logs/ 目录最新文件）")
    parser.add_argument("--session-log-dir", type=Path,
                        default=Path("captures/session_logs"),
                        help="session log 目录（仅在未指定 --session-log 时使用）")
    parser.add_argument("--output", type=Path,
                        default=Path("captures/e2e_latency_result.json"))
    parser.add_argument("--max-latency-ms", type=int, default=3000,
                        help="P95 延迟合格阈值（ms），默认 3000ms")
    parser.add_argument("--max-window-ms", type=int, default=30_000,
                        help="注入→事件最大有效配对窗口（ms），默认 30000ms")
    args = parser.parse_args()

    # 确定 session log 路径
    session_log_path: Path | None = None
    if args.session_log:
        session_log_path = resolve_path(args.session_log)
    else:
        log_dir = resolve_path(args.session_log_dir)
        if log_dir.exists():
            candidates = sorted(log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                session_log_path = candidates[0]
                print(f"[e2e] 自动选取最新 session log: {session_log_path.name}")

    if session_log_path is None:
        print("[e2e] 未找到 session log，请先运行 track_injector 生成会话记录。")
        return 1

    records = load_session_log(session_log_path)
    if not records:
        print(f"[e2e] session log 为空或格式错误: {session_log_path}")
        return 1

    scenario_name = str(records[0].get("scenario_name", "unknown")) if records else "unknown"
    injections = extract_injection_points(records)
    outputs = extract_event_outputs(records)

    print(f"[e2e] 注入点={len(injections)} 事件输出={len(outputs)}")

    samples = pair_latencies(injections, outputs, max_window_ms=args.max_window_ms)
    result = compute_stats(samples, str(session_log_path), scenario_name)

    print_result(result, args.max_latency_ms)
    write_result(resolve_path(args.output), result, args.max_latency_ms)
    return 0 if result.passed(args.max_latency_ms) else 1


if __name__ == "__main__":
    raise SystemExit(main())
