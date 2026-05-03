from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def angle_deg(x_m: float, y_m: float) -> float:
    return 90.0 + math.degrees(math.atan2(x_m, y_m))


def simulate(lead_times: list[float], distance_m: float, lateral_speed_mps: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for lead in lead_times:
        total_error = 0.0
        max_error = 0.0
        samples = 0
        for index in range(1, 101):
            t = index * 0.02
            x_now = lateral_speed_mps * t
            x_future = lateral_speed_mps * (t + 0.18)
            predicted = angle_deg(x_now + lateral_speed_mps * lead, distance_m)
            actual = angle_deg(x_future, distance_m)
            err = abs(predicted - actual)
            total_error += err
            max_error = max(max_error, err)
            samples += 1
        rows.append({
            "distance_m": distance_m,
            "lead_time_s": lead,
            "mean_error_deg": round(total_error / samples, 3),
            "max_error_deg": round(max_error, 3),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Flytotal v5.2 gimbal prediction lead-time simulator")
    parser.add_argument("--lead-times", default="0,0.12,0.18")
    parser.add_argument("--output", type=Path, default=Path("captures/v5_2/gimbal_prediction.csv"))
    args = parser.parse_args()
    lead_times = [float(item) for item in args.lead_times.split(",") if item.strip()]
    rows = simulate(lead_times, 50.0, 12.0) + simulate(lead_times, 100.0, 12.0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
