from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def score(speed_mps: float, age_s: float, variance_mps: float, heading_rate_deg_s: float) -> tuple[bool, float]:
    value = 0.0
    if 2.0 <= speed_mps <= 25.0:
        value += 35.0
    if age_s >= 2.0:
        value += 30.0
    if variance_mps <= 0.9:
        value += 20.0
    if heading_rate_deg_s <= 75.0:
        value += 15.0
    else:
        value -= 15.0
    value = max(0.0, min(100.0, value))
    return value >= 65.0 and age_s >= 2.0, value


def mock_rows() -> list[dict[str, object]]:
    samples = [
        ("multirotor", 8.0, 3.0, 0.4, 20.0),
        ("hover", 0.8, 3.2, 0.2, 10.0),
        ("person", 1.2, 4.0, 0.5, 30.0),
        ("ebike", 9.0, 2.5, 1.8, 50.0),
        ("car", 32.0, 2.5, 2.0, 15.0),
        ("bird", 7.0, 2.5, 2.2, 140.0),
    ]
    rows = []
    for label, speed, age, variance, heading in samples:
        is_like, value = score(speed, age, variance, heading)
        rows.append({
            "label": label,
            "speed_mps": speed,
            "age_s": age,
            "variance_mps": variance,
            "heading_rate_deg_s": heading,
            "is_multirotor_like": int(is_like),
            "multirotor_score": round(value, 1),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Flytotal v5.2 multirotor feature classifier")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("captures/v5_2/multirotor_classifier_mock.json"))
    args = parser.parse_args()
    rows = mock_rows()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
