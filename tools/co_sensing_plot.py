"""Plot co-sensing handoff state timeline from JSON produced by co_sensing_simulator.py."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

STATE_ORDER = ["SINGLE_NODE", "HANDOFF_PENDING", "HANDOFF_ACTIVE", "HANDOVER_DONE", "NODEB_OFFLINE"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot co-sensing state timeline")
    parser.add_argument("--input", type=Path, default=Path("captures/v5_2/co_sensing_boundary_crossing.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/co_sensing_timeline.png"))
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    records = payload["records"]
    times_ms = [r["timestamp_ms"] for r in records]
    states = [r["continuity_hint"] for r in records]
    track_x = [r["track_x_m"] for r in records]
    nodeb = [r["nodeb_online"] for r in records]
    state_idx = [STATE_ORDER.index(s) for s in states]

    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)

    axes[0].step(times_ms, state_idx, where="post", color="#2c7be5", linewidth=2)
    axes[0].set_yticks(range(len(STATE_ORDER)))
    axes[0].set_yticklabels(STATE_ORDER, fontsize=9)
    axes[0].set_ylabel("handoff state")
    axes[0].set_title("Co-sensing handoff timeline (boundary crossing)")
    axes[0].grid(alpha=0.3)

    axes[1].plot(times_ms, track_x, marker="o", color="#16a085", linewidth=1.5, markersize=4)
    axes[1].axhline(-1.0, color="orange", linestyle="--", alpha=0.6, label="enter PENDING")
    axes[1].axhline(1.0, color="red", linestyle="--", alpha=0.6, label="enter ACTIVE")
    axes[1].axhline(5.0, color="#27ae60", linestyle="--", alpha=0.6, label="enter DONE")
    axes[1].set_ylabel("track_x (m)")
    axes[1].legend(loc="lower right", fontsize=8)
    axes[1].grid(alpha=0.3)

    axes[2].fill_between(times_ms, 0, nodeb, step="post", alpha=0.4, color="#8e44ad")
    axes[2].set_yticks([0, 1])
    axes[2].set_yticklabels(["OFFLINE", "ONLINE"])
    axes[2].set_ylabel("NodeB link")
    axes[2].set_xlabel("time (ms)")
    axes[2].grid(alpha=0.3)

    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150)
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
