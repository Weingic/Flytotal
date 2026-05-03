from __future__ import annotations

import argparse
import json
from pathlib import Path


def classify(stage: str, ld2451: bool, ld2450: bool, rid: bool, vision: bool, held_ms: int) -> dict[str, object]:
    votes = sum([ld2451, ld2450, rid, vision])
    high_ready = votes >= 2 and held_ms >= 800
    level = "NONE"
    reason = "NONE"
    if stage == "FAR":
        if ld2451 and rid:
            level, reason = "MID", "FAR_LD2451_RID"
        elif ld2451:
            level, reason = "LOW", "FAR_LD2451_WARNING"
    elif stage == "MID":
        if high_ready:
            level, reason = "HIGH", "MID_MULTI_SOURCE_HELD"
        elif votes >= 2:
            level, reason = "MID", "MID_WAIT_WINDOW"
        elif votes == 1:
            level, reason = "LOW", "MID_SINGLE_SOURCE"
    elif stage == "NEAR":
        if high_ready and (vision or rid):
            level, reason = "HIGH", "NEAR_CONFIRMED"
        elif votes >= 2:
            level, reason = "MID", "NEAR_NEEDS_VISUAL_OR_RID"
        elif votes == 1:
            level, reason = "LOW", "NEAR_SINGLE_SOURCE"
    confidence = min(1.0, votes * 0.22 + (0.1 if high_ready else 0.0))
    return {
        "stage": stage,
        "fusion_level": level,
        "fusion_confidence": round(confidence, 2),
        "fusion_reason": reason,
        "source_vote_count": votes,
    }


def run_far_mid_near() -> list[dict[str, object]]:
    return [
        {"range_m": 80, **classify("FAR", True, False, False, False, 1000)},
        {"range_m": 80, **classify("FAR", True, False, True, False, 1000)},
        {"range_m": 25, **classify("MID", True, True, False, False, 300)},
        {"range_m": 25, **classify("MID", True, True, False, False, 900)},
        {"range_m": 8, **classify("NEAR", True, True, False, False, 900)},
        {"range_m": 8, **classify("NEAR", True, True, False, True, 900)},
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Flytotal v5.2 fusion stage simulator")
    parser.add_argument("--case", default="far_mid_near", choices=["far_mid_near"])
    parser.add_argument("--output", type=Path, default=Path("captures/v5_2/fusion_simulator_far_mid_near.json"))
    args = parser.parse_args()

    rows = run_far_mid_near()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"case": args.case, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
