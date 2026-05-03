from __future__ import annotations

import argparse
import json
from pathlib import Path


def boundary_crossing() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for step in range(16):
        ts = step * 200
        x = -8.0 + step * 1.2
        nodeb_online = step < 13
        if x < -1.0:
            state = "SINGLE_NODE"
        elif x < 1.0:
            state = "HANDOFF_PENDING"
        elif x < 5.0:
            state = "HANDOFF_ACTIVE"
        else:
            state = "HANDOVER_DONE"
        if not nodeb_online:
            state = "NODEB_OFFLINE"
        rows.append({
            "timestamp_ms": ts,
            "node_id": "NodeA",
            "nodeb_online": int(nodeb_online),
            "track_x_m": round(x, 2),
            "continuity_hint": state,
            "handoff_from": "NodeA" if state.startswith("HANDOFF") else "NONE",
            "handoff_to": "NodeB" if state.startswith("HANDOFF") else "NONE",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Flytotal v5.2 co-sensing handoff simulator")
    parser.add_argument("--scenario", default="boundary_crossing", choices=["boundary_crossing"])
    parser.add_argument("--output", type=Path, default=Path("captures/v5_2/co_sensing_boundary_crossing.json"))
    args = parser.parse_args()
    payload = {"scenario": args.scenario, "records": boundary_crossing()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
