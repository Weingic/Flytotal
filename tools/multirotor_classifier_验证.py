from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any


POSITIVE_LABELS = {"multirotor", "drone", "uav", "hover"}
FEATURE_COLUMNS = [
    "speed_mps",
    "age_s",
    "variance_mps",
    "heading_rate_deg_s",
    "motion_span_m",
]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def score(
    speed_mps: float,
    age_s: float,
    variance_mps: float,
    heading_rate_deg_s: float,
    motion_span_m: float = 1.0,
) -> tuple[bool, float]:
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
    if speed_mps < 0.2 and motion_span_m < 0.2:
        value = min(value, 45.0)
    value = max(0.0, min(100.0, value))
    return value >= 65.0 and age_s >= 2.0, value


def mock_rows() -> list[dict[str, object]]:
    samples = [
        ("multirotor", 8.0, 3.0, 0.4, 20.0),
        ("hover", 0.8, 3.2, 0.2, 10.0),
        ("drone", 6.5, 2.8, 0.5, 25.0),
        ("uav", 4.5, 2.6, 0.6, 18.0),
        ("person", 1.2, 4.0, 0.5, 30.0),
        ("person", 1.5, 3.0, 0.7, 55.0),
        ("ebike", 9.0, 2.5, 1.8, 50.0),
        ("car", 32.0, 2.5, 2.0, 15.0),
        ("bird", 7.0, 2.5, 2.2, 140.0),
        ("bird", 5.0, 2.0, 1.6, 210.0),
        ("clutter", 0.1, 4.0, 0.0, 0.0),
        ("clutter", 0.3, 3.2, 0.1, 15.0),
    ]
    rows: list[dict[str, object]] = []
    for index, (label, speed, age, variance, heading) in enumerate(samples):
        is_like, value = score(speed, age, variance, heading)
        rows.append(
            {
                "track_id": f"synthetic_{index:02d}_{label}",
                "label": label,
                "speed_mps": speed,
                "age_s": age,
                "variance_mps": variance,
                "heading_rate_deg_s": heading,
                "motion_span_m": max(0.1, speed * age * 0.35),
                "is_multirotor_like": int(is_like),
                "multirotor_score": round(value, 1),
                "sample_count": 5,
            }
        )
    return rows


def read_csv_rows(input_path: Path) -> list[dict[str, str]]:
    if input_path.is_file():
        files = [input_path]
    else:
        ignored_parts = {"v5_2", "event_exports", "session_logs", "real_radar_checks"}
        files = sorted(
            path
            for path in input_path.rglob("*.csv")
            if path.is_file() and not any(part in ignored_parts for part in path.parts)
        )
    rows: list[dict[str, str]] = []
    for file_path in files:
        try:
            with file_path.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    if isinstance(row, dict):
                        clean = {str(key): str(value or "") for key, value in row.items() if key is not None}
                        clean.setdefault("_source_file", file_path.as_posix())
                        rows.append(clean)
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
    return rows


def group_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for index, row in enumerate(rows):
        source = row.get("_source_file", "input")
        track_id = row.get("track_id") or row.get("id") or source
        key = f"{source}:{track_id}" if track_id else f"{source}:track-{index}"
        groups.setdefault(key, []).append(row)
    return groups


def timestamp_ms(row: dict[str, str], fallback: int) -> int:
    return int(safe_float(row.get("timestamp_ms", row.get("ts_ms", row.get("time_ms", fallback))), fallback))


def heading_deg(vx: float, vy: float) -> float:
    if abs(vx) < 1e-6 and abs(vy) < 1e-6:
        return 0.0
    return math.degrees(math.atan2(vy, vx))


def circular_delta(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def features_from_group(key: str, rows: list[dict[str, str]], label_column: str) -> dict[str, object]:
    ordered = sorted(enumerate(rows), key=lambda item: timestamp_ms(item[1], item[0] * 200))
    speeds: list[float] = []
    headings: list[tuple[int, float]] = []
    positions: list[tuple[float, float]] = []
    previous: tuple[int, float, float] | None = None
    label = ""

    for index, row in ordered:
        ts = timestamp_ms(row, index * 200)
        x_mm = safe_float(row.get("x_mm", row.get("x", 0.0)), 0.0)
        y_mm = safe_float(row.get("y_mm", row.get("y", 0.0)), 0.0)
        positions.append((x_mm, y_mm))
        vx = safe_float(row.get("vx_mm_s", row.get("vx", "")), math.nan)
        vy = safe_float(row.get("vy_mm_s", row.get("vy", "")), math.nan)
        if math.isnan(vx) or math.isnan(vy):
            if previous:
                prev_ts, prev_x, prev_y = previous
                dt = max(1, ts - prev_ts) / 1000.0
                vx = (x_mm - prev_x) / dt
                vy = (y_mm - prev_y) / dt
            else:
                vx = 0.0
                vy = 0.0
        speed_mps = math.hypot(vx, vy) / 1000.0
        if speed_mps > 0:
            speeds.append(speed_mps)
            headings.append((ts, heading_deg(vx, vy)))
        previous = (ts, x_mm, y_mm)
        if not label and label_column in row:
            label = str(row.get(label_column, "") or "").strip()

    if not ordered:
        mean_speed = 0.0
        age_s = 0.0
    else:
        first_ts = timestamp_ms(ordered[0][1], 0)
        last_ts = timestamp_ms(ordered[-1][1], first_ts)
        age_s = max(0.0, (last_ts - first_ts) / 1000.0)
        mean_speed = statistics.fmean(speeds) if speeds else 0.0

    variance_mps = statistics.pstdev(speeds) if len(speeds) > 1 else 0.0
    if positions:
        xs = [item[0] for item in positions]
        ys = [item[1] for item in positions]
        motion_span_m = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) / 1000.0
    else:
        motion_span_m = 0.0
    heading_rates: list[float] = []
    for left, right in zip(headings, headings[1:]):
        dt_s = max(0.001, (right[0] - left[0]) / 1000.0)
        heading_rates.append(circular_delta(right[1], left[1]) / dt_s)
    heading_rate = statistics.fmean(heading_rates) if heading_rates else 0.0
    is_like, value = score(mean_speed, age_s, variance_mps, heading_rate, motion_span_m)
    return {
        "track_id": key,
        "label": label,
        "speed_mps": round(mean_speed, 3),
        "age_s": round(age_s, 3),
        "variance_mps": round(variance_mps, 3),
        "heading_rate_deg_s": round(heading_rate, 3),
        "motion_span_m": round(motion_span_m, 3),
        "is_multirotor_like": int(is_like),
        "multirotor_score": round(value, 1),
        "sample_count": len(ordered),
    }


def classify_input(input_path: Path, label_column: str) -> list[dict[str, object]]:
    rows = read_csv_rows(input_path)
    if not rows:
        return []
    return [features_from_group(key, group, label_column) for key, group in group_rows(rows).items()]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def label_is_positive(label: str) -> bool:
    return str(label or "").strip().lower() in POSITIVE_LABELS


def labels_from_rows(rows: list[dict[str, object]]) -> list[int]:
    return [1 if label_is_positive(str(row.get("label", "") or "")) else 0 for row in rows]


def matrix_from_predictions(actual: list[int], predicted: list[int]) -> dict[str, int]:
    result = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for y_true, y_pred in zip(actual, predicted):
        if y_true == 1 and y_pred == 1:
            result["tp"] += 1
        elif y_true == 1 and y_pred == 0:
            result["fn"] += 1
        elif y_true == 0 and y_pred == 1:
            result["fp"] += 1
        else:
            result["tn"] += 1
    return result


def confusion(rows: list[dict[str, object]]) -> dict[str, int]:
    labeled = [row for row in rows if str(row.get("label", "") or "").strip()]
    return matrix_from_predictions(labels_from_rows(labeled), [int(row.get("is_multirotor_like", 0)) for row in labeled])


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def metrics_from_confusion(matrix: dict[str, int]) -> dict[str, float]:
    tp = int(matrix.get("tp", 0))
    fp = int(matrix.get("fp", 0))
    tn = int(matrix.get("tn", 0))
    fn = int(matrix.get("fn", 0))
    total = tp + fp + tn + fn
    return {
        "accuracy": round(safe_ratio(tp + tn, total), 4),
        "precision": round(safe_ratio(tp, tp + fp), 4),
        "recall": round(safe_ratio(tp, tp + fn), 4),
        "specificity": round(safe_ratio(tn, tn + fp), 4),
        "total": float(total),
    }


def build_acceptance(
    has_labels: bool,
    metrics: dict[str, float],
    min_accuracy: float,
    min_recall: float,
) -> dict[str, object]:
    failures: list[str] = []
    checked = min_accuracy > 0.0 or min_recall > 0.0
    if checked and not has_labels:
        failures.append("labels_missing")
    if has_labels and min_accuracy > 0.0 and metrics.get("accuracy", 0.0) < min_accuracy:
        failures.append(f"accuracy_below_{min_accuracy:.2f}")
    if has_labels and min_recall > 0.0 and metrics.get("recall", 0.0) < min_recall:
        failures.append(f"recall_below_{min_recall:.2f}")
    return {
        "checked": checked,
        "passed": len(failures) == 0,
        "min_accuracy": round(max(0.0, min_accuracy), 4),
        "min_recall": round(max(0.0, min_recall), 4),
        "failures": failures,
    }


def write_confusion_plot(matrix: dict[str, int], output_path: Path, title: str) -> str:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        return ""
    values = [[matrix["tp"], matrix["fn"]], [matrix["fp"], matrix["tn"]]]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(5.2, 4.5))
    plt.imshow(values, cmap="Greens")
    plt.xticks([0, 1], ["pred drone", "pred other"])
    plt.yticks([0, 1], ["actual drone", "actual other"])
    for y, row in enumerate(values):
        for x, value in enumerate(row):
            plt.text(x, y, str(value), ha="center", va="center", fontsize=18, fontweight="bold")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path.as_posix()


def write_feature_plot(rows: list[dict[str, object]], output_path: Path) -> str:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        return ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [str(row.get("label") or row.get("track_id") or index) for index, row in enumerate(rows)]
    scores = [safe_float(row.get("multirotor_score", 0.0), 0.0) for row in rows]
    speeds = [safe_float(row.get("speed_mps", 0.0), 0.0) for row in rows]
    positions = list(range(len(rows)))
    plt.figure(figsize=(max(7.0, len(rows) * 0.7), 4.8))
    plt.bar(positions, scores, label="rule score", alpha=0.75)
    plt.plot(positions, [min(100.0, speed * 4.0) for speed in speeds], "o-", label="speed x4")
    plt.axhline(65, color="tab:red", linestyle="--", linewidth=1.2, label="rule threshold")
    plt.xticks(positions, labels, rotation=30, ha="right")
    plt.ylabel("score")
    plt.title("Multirotor rule feature distribution")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path.as_posix()


def feature_matrix(rows: list[dict[str, object]]) -> list[list[float]]:
    return [[safe_float(row.get(column, 0.0), 0.0) for column in FEATURE_COLUMNS] for row in rows]


def choose_cv_folds(labels: list[int], requested: int = 5) -> tuple[int, str]:
    positives = sum(1 for item in labels if item == 1)
    negatives = sum(1 for item in labels if item == 0)
    min_class_count = min(positives, negatives)
    if min_class_count >= requested:
        return requested, "5_fold_cv"
    if min_class_count >= 2:
        return min(requested, min_class_count), "reduced_cv_due_to_class_count"
    return 0, "insufficient_class_balance_train_eval_same_data"


def train_model(rows: list[dict[str, object]], output_dir: Path, model_path: Path, source: str) -> dict[str, object]:
    try:
        import joblib  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore
        from sklearn.metrics import auc, roc_curve  # type: ignore
        from sklearn.model_selection import StratifiedKFold, cross_val_predict  # type: ignore
        from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree  # type: ignore
    except ImportError as exc:
        return {
            "ok": False,
            "error": f"missing_training_dependency: {exc}",
            "hint": "Run `python -m pip install -U -r requirements-vision.txt`.",
        }

    labeled = [row for row in rows if str(row.get("label", "") or "").strip()]
    warnings: list[str] = []
    if len(labeled) < 20:
        warnings.append("sample_count_below_20_tracks_results_for_reference_only")
    if source == "mock":
        warnings.append("synthetic_baseline_only_real_model_needs_real_data")
    if not labeled:
        return {"ok": False, "error": "no_labeled_tracks", "warnings": warnings}

    labels = labels_from_rows(labeled)
    if len(set(labels)) < 2:
        return {"ok": False, "error": "need_positive_and_negative_labels", "warnings": warnings}

    x_values = feature_matrix(labeled)
    rule_pred = [int(row.get("is_multirotor_like", 0)) for row in labeled]
    rule_scores = [safe_float(row.get("multirotor_score", 0.0), 0.0) / 100.0 for row in labeled]
    rule_matrix = matrix_from_predictions(labels, rule_pred)
    rule_metrics = metrics_from_confusion(rule_matrix)

    tree = DecisionTreeClassifier(max_depth=4, random_state=42)
    folds, cv_note = choose_cv_folds(labels, requested=5)
    if folds >= 2:
        cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
        model_pred = [int(item) for item in cross_val_predict(tree, x_values, labels, cv=cv, method="predict")]
        model_prob = [float(item[1]) for item in cross_val_predict(tree, x_values, labels, cv=cv, method="predict_proba")]
    else:
        tree.fit(x_values, labels)
        model_pred = [int(item) for item in tree.predict(x_values)]
        model_prob = [float(item[1]) for item in tree.predict_proba(x_values)]
        warnings.append(cv_note)

    model_matrix = matrix_from_predictions(labels, model_pred)
    model_metrics = metrics_from_confusion(model_matrix)
    tree.fit(x_values, labels)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": tree,
            "feature_columns": FEATURE_COLUMNS,
            "positive_labels": sorted(POSITIVE_LABELS),
            "source": source,
        },
        model_path,
    )

    tree_plot = output_dir / "multirotor_tree.png"
    plt.figure(figsize=(14, 8))
    plot_tree(
        tree,
        feature_names=FEATURE_COLUMNS,
        class_names=["other", "multirotor"],
        filled=True,
        rounded=True,
        fontsize=9,
    )
    plt.title("Decision tree for multirotor classification")
    plt.tight_layout()
    plt.savefig(tree_plot, dpi=160)
    plt.close()

    rules_path = output_dir / "multirotor_tree_rules.txt"
    rules_path.write_text(export_text(tree, feature_names=FEATURE_COLUMNS), encoding="utf-8")

    confusion_plot = write_confusion_plot(model_matrix, output_dir / "multirotor_confusion_real.png", "Decision tree confusion matrix")

    roc_plot = ""
    if len(set(labels)) >= 2:
        fpr, tpr, _ = roc_curve(labels, model_prob)
        model_auc = auc(fpr, tpr)
        rule_fpr, rule_tpr, _ = roc_curve(labels, rule_scores)
        rule_auc = auc(rule_fpr, rule_tpr)
        roc_path = output_dir / "multirotor_roc_real.png"
        plt.figure(figsize=(6.2, 5.2))
        plt.plot(fpr, tpr, label=f"tree AUC={model_auc:.2f}")
        plt.plot(rule_fpr, rule_tpr, label=f"rule AUC={rule_auc:.2f}", linestyle="--")
        plt.plot([0, 1], [0, 1], color="gray", linewidth=1.0)
        plt.xlabel("False positive rate")
        plt.ylabel("True positive rate")
        plt.title("Multirotor ROC")
        plt.grid(alpha=0.25)
        plt.legend(loc="best")
        plt.tight_layout()
        plt.savefig(roc_path, dpi=150)
        plt.close()
        roc_plot = roc_path.as_posix()

    compare_path = output_dir / "multirotor_rule_vs_model.png"
    labels_for_plot = ["accuracy", "precision", "recall", "specificity"]
    rule_values = [rule_metrics.get(item, 0.0) for item in labels_for_plot]
    model_values = [model_metrics.get(item, 0.0) for item in labels_for_plot]
    positions = list(range(len(labels_for_plot)))
    width = 0.36
    plt.figure(figsize=(7.2, 4.6))
    plt.bar([item - width / 2 for item in positions], rule_values, width=width, label="rule baseline")
    plt.bar([item + width / 2 for item in positions], model_values, width=width, label="decision tree")
    plt.xticks(positions, labels_for_plot)
    plt.ylim(0.0, 1.05)
    plt.ylabel("score")
    plt.title("Rule baseline vs trained model")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(compare_path, dpi=150)
    plt.close()

    feature_importance = {
        column: round(float(value), 4)
        for column, value in zip(FEATURE_COLUMNS, getattr(tree, "feature_importances_", []))
    }

    trained_rows: list[dict[str, object]] = []
    for row, pred, prob in zip(labeled, model_pred, model_prob):
        item = dict(row)
        item["tree_prediction"] = int(pred)
        item["tree_probability"] = round(float(prob), 4)
        trained_rows.append(item)
    write_csv(output_dir / "multirotor_training_predictions.csv", trained_rows)

    return {
        "ok": True,
        "source": source,
        "track_count": len(labeled),
        "warnings": warnings,
        "cv": {"requested_folds": 5, "effective_folds": folds, "note": cv_note},
        "feature_columns": FEATURE_COLUMNS,
        "feature_importance": feature_importance,
        "rule_baseline": {"confusion_matrix": rule_matrix, "metrics": rule_metrics},
        "decision_tree": {"confusion_matrix": model_matrix, "metrics": model_metrics},
        "model_path": model_path.as_posix(),
        "tree_plot": tree_plot.as_posix(),
        "tree_rules": rules_path.as_posix(),
        "roc_plot": roc_plot,
        "confusion_plot": confusion_plot,
        "rule_vs_model_plot": compare_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Flytotal v5.2 multirotor feature classifier")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--input", type=Path, default=None, help="CSV file or directory with timestamp_ms,x_mm,y_mm,vx_mm_s,vy_mm_s,label")
    parser.add_argument("--label-column", default="label")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=None, help="Legacy JSON output path")
    parser.add_argument("--min-accuracy", type=float, default=0.0, help="Optional labeled-set acceptance threshold")
    parser.add_argument("--min-recall", type=float, default=0.0, help="Optional drone recall acceptance threshold")
    parser.add_argument("--train", action="store_true", help="Train a sklearn decision tree and compare it with the rule baseline")
    parser.add_argument("--model-output", type=Path, default=Path("models/multirotor_tree.pkl"), help="Decision tree model output path")
    args = parser.parse_args()

    if args.input and not args.mock:
        rows = classify_input(args.input, args.label_column)
        source = args.input.as_posix()
    else:
        rows = mock_rows()
        source = "mock"

    if not rows:
        rows = mock_rows()
        source = f"{source}:fallback_mock"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output or (args.output_dir / "multirotor_classifier_summary.json")
    csv_path = json_path.with_suffix(".csv")
    write_csv(csv_path, rows)

    has_labels = any(str(row.get("label", "") or "").strip() for row in rows)
    feature_plot = write_feature_plot(rows, args.output_dir / "multirotor_features.png")
    confusion_path = args.output_dir / "multirotor_confusion_matrix.png"
    if has_labels:
        matrix = confusion(rows)
        confusion_plot = write_confusion_plot(matrix, confusion_path, "Rule baseline confusion matrix")
        metrics = metrics_from_confusion(matrix)
    else:
        if confusion_path.exists():
            confusion_path.unlink()
        matrix = {}
        metrics = {}
        confusion_plot = ""

    acceptance = build_acceptance(has_labels, metrics, float(args.min_accuracy), float(args.min_recall))
    needs_labels = not has_labels or source.endswith("fallback_mock") or source == "mock"
    warnings: list[str] = []
    if needs_labels:
        warnings.append("current_result_is_synthetic_or_unlabeled_baseline_true_model_needs_real_data")
    if has_labels and len(rows) < 20:
        warnings.append("sample_count_below_20_tracks_results_for_reference_only")

    training: dict[str, object] = {}
    if args.train:
        training = train_model(rows, args.output_dir, args.model_output, source if source != "mock" else "mock")
        if not bool(training.get("ok", False)):
            warnings.append(str(training.get("error", "training_failed")))

    payload = {
        "ok": True,
        "source": source,
        "row_count": len(rows),
        "has_labels": has_labels,
        "needs_labels": needs_labels,
        "warnings": warnings,
        "label_column": args.label_column,
        "feature_columns": FEATURE_COLUMNS,
        "rows": rows,
        "confusion_matrix": matrix,
        "metrics": metrics,
        "acceptance": acceptance,
        "feature_plot": feature_plot,
        "confusion_plot": confusion_plot,
        "training": training,
        "note": "synthetic_baseline_only_true_model_needs_real_data" if needs_labels else "labels_available_confusion_matrix_generated",
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if needs_labels:
        needs_path = args.output_dir / "multirotor_needs_labels.json"
        needs_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "message": "Current data is synthetic or lacks reliable labels. Collect real tracks before claiming real-world performance.",
                    "expected_fields": "timestamp_ms,track_id,x_mm,y_mm,vx_mm_s,vy_mm_s,label",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    for warning in warnings:
        print(f"WARNING,{warning}")
    print(json_path.as_posix())
    if feature_plot:
        print(feature_plot)
    if confusion_plot:
        print(confusion_plot)
    if training.get("ok"):
        print(training.get("tree_plot", ""))
        print(training.get("roc_plot", ""))
        print(training.get("rule_vs_model_plot", ""))
        print(training.get("model_path", ""))
    if args.train and not bool(training.get("ok", False)):
        return 1
    return 0 if bool(acceptance.get("passed", True)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
