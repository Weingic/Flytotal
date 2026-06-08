from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_REPLAY: dict[str, Any] = {
    "event": {
        "event_id": "A1-0000123456-0001",
        "target_verdict": "VISUALLY_CONFIRMED_DRONE",
        "risk_level": "HIGH_RISK",
        "fusion_stage": "MID",
        "ld2451": {"range_m": 45, "speed_mps": 3.5},
        "rid": {"id": "SIM-RID-999", "wl_status": "WL_DENIED"},
        "multirotor": {"score": 78, "is_like": True},
    },
    "assessment": {
        "threat_level": "HIGH",
        "assessment": "non-cooperative high risk",
        "alert_text": "suspicious low-alt target",
    },
    "command": {
        "type": "SWITCH_MODE",
        "params": {"mode": "ECONOMY", "reason": "cloud suggested economy"},
    },
    "edge_veto": {
        "applied": False,
        "reason": "DOWNGRADE_REJECTED_THREAT_ACTIVE",
    },
}


def load_replay(path: Path | None) -> dict[str, Any]:
    if path is None:
        return DEFAULT_REPLAY
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("replay JSON must be an object")
    return payload


def compact_json(value: Any, width: int = 38) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    wrapped = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if len(wrapped) > 5:
        wrapped = wrapped[:4] + ["..."]
    return "\n".join(wrapped)


def box_text(title: str, body: Any) -> str:
    return f"{title}\n{compact_json(body)}"


def build_stages(replay: dict[str, Any]) -> list[tuple[str, Any, str]]:
    event = replay.get("event", {})
    assessment = replay.get("assessment", {})
    command = replay.get("command", {})
    edge_veto = replay.get("edge_veto", {})
    dashboard = {
        "cloud_threat_level": assessment.get("threat_level", "NONE"),
        "cloud_alert_text": assessment.get("alert_text", "NONE"),
        "cloud_command_type": command.get("type", "NONE"),
        "cloud_command_effect": edge_veto.get("reason", "NONE"),
    }
    return [
        ("1 Edge Event", event, "#dbeafe"),
        ("2 Doubao Assessment", assessment, "#dcfce7"),
        ("3 Downlink Command", command, "#fef3c7"),
        ("4 Edge Apply/Veto", edge_veto, "#fee2e2"),
        ("5 Dashboard Fields", dashboard, "#ede9fe"),
    ]


def render_replay(replay: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    stages = build_stages(replay)

    fig, ax = plt.subplots(figsize=(16, 5.6))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    xs = [0.10, 0.30, 0.50, 0.70, 0.90]
    y = 0.56
    box_width = 0.16
    box_height = 0.46

    fig.suptitle("Flytotal Edge-Cloud-Edge AI Command Loop", fontsize=16, fontweight="bold")
    ax.text(
        0.5,
        0.93,
        "Evidence replay: sensing data upload, LLM assessment, command downlink, edge safety decision, dashboard update",
        ha="center",
        va="center",
        fontsize=10,
        color="#475569",
    )

    for index, ((title, body, color), x) in enumerate(zip(stages, xs)):
        ax.text(
            x,
            y,
            box_text(title, body),
            ha="center",
            va="center",
            fontsize=8.5,
            bbox={
                "boxstyle": "round,pad=0.6,rounding_size=0.18",
                "facecolor": color,
                "edgecolor": "#94a3b8",
                "linewidth": 1.2,
            },
        )
        if index < len(xs) - 1:
            ax.annotate(
                "",
                xy=(xs[index + 1] - box_width / 2, y),
                xytext=(x + box_width / 2, y),
                arrowprops={"arrowstyle": "->", "lw": 1.6, "color": "#334155"},
            )

    edge_veto = replay.get("edge_veto", {})
    applied = bool(edge_veto.get("applied", False))
    verdict = "APPLIED" if applied else "VETO / LOGGED"
    ax.text(
        0.5,
        0.12,
        f"Edge safety result: {verdict} | reason={edge_veto.get('reason', 'NONE')}",
        ha="center",
        va="center",
        fontsize=11,
        color="#0f172a",
        bbox={
            "boxstyle": "round,pad=0.5,rounding_size=0.12",
            "facecolor": "#f8fafc",
            "edgecolor": "#cbd5e1",
        },
    )

    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.95])
    fig.savefig(output, dpi=180)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Flytotal cloud loop replay evidence diagram.")
    parser.add_argument("--input", type=Path, help="Replay JSON file. Uses a built-in demo when omitted.")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "cloud_loop_demo.png")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    replay = load_replay(args.input)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    render_replay(replay, output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
