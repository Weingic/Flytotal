from __future__ import annotations

import argparse
import csv
import json
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
        rows.append(
            {
                "distance_m": distance_m,
                "lateral_speed_mps": lateral_speed_mps,
                "lead_time_s": lead,
                "mean_error_deg": round(total_error / samples, 3),
                "max_error_deg": round(max_error, 3),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_plot(path: Path, rows: list[dict[str, float]]) -> str:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        return ""
    path.parent.mkdir(parents=True, exist_ok=True)
    distances = sorted({row["distance_m"] for row in rows})
    plt.figure(figsize=(8.8, 4.8))
    for distance in distances:
        subset = [row for row in rows if row["distance_m"] == distance]
        plt.plot(
            [row["lead_time_s"] * 1000.0 for row in subset],
            [row["mean_error_deg"] for row in subset],
            marker="o",
            linewidth=2,
            label=f"{distance:.0f}m mean error",
        )
    plt.xlabel("lead time (ms)")
    plt.ylabel("mean angle error (deg)")
    plt.title("Gimbal prediction lead-time comparison")
    plt.grid(True, alpha=0.28)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return path.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Flytotal v5.2 gimbal prediction lead-time simulator")
    parser.add_argument("--lead-times", default="0,0.12,0.18")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=None, help="Legacy CSV output path")
    args = parser.parse_args()
    lead_times = [float(item) for item in args.lead_times.split(",") if item.strip()]
    rows = simulate(lead_times, 50.0, 12.0) + simulate(lead_times, 100.0, 12.0)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output or (output_dir / "gimbal_prediction.csv")
    png_path = output_dir / "gimbal_prediction.png"
    json_path = output_dir / "gimbal_prediction_summary.json"
    write_csv(csv_path, rows)
    plot_path = write_plot(png_path, rows)
    json_path.write_text(
        json.dumps({"ok": True, "rows": rows, "csv_path": csv_path.as_posix(), "plot_path": plot_path}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(csv_path.as_posix())
    if plot_path:
        print(plot_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
