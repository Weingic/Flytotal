from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "datasets" / "drone_recognition"
DEFAULT_CAPTURES = PROJECT_ROOT / "captures"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val", "test")
SPLIT_ALIASES = {
    "train": "train",
    "val": "val",
    "valid": "val",
    "validation": "val",
    "test": "test",
}


@dataclass(frozen=True)
class DatasetItem:
    image: Path
    label: Path | None
    split: str | None
    source: str
    source_root: Path | None = None
    is_background: bool = False


def parse_ratio(raw: str) -> tuple[float, float, float]:
    parts = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("split ratio must be three comma-separated numbers, for example 70,20,10")
    total = sum(parts)
    if total <= 0:
        raise argparse.ArgumentTypeError("split ratio total must be positive")
    return tuple(item / total for item in parts)  # type: ignore[return-value]


def parse_class_ids(raw: str) -> set[int]:
    class_ids: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        class_ids.add(int(item))
    if not class_ids:
        raise argparse.ArgumentTypeError("at least one drone source class id is required")
    return class_ids


def parse_source_class_ids(raw: str) -> tuple[Path, set[int]]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("source class mapping must use <source_path>=<class_ids>, for example raw/dataset=1")
    source_raw, class_ids_raw = raw.split("=", 1)
    source = Path(source_raw.strip())
    if not str(source):
        raise argparse.ArgumentTypeError("source path is required before `=`")
    return source.resolve(), parse_class_ids(class_ids_raw)


def iter_images(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def stable_split(path: Path, ratios: tuple[float, float, float], seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{path.as_posix()}".encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    if value < ratios[0]:
        return "train"
    if value < ratios[0] + ratios[1]:
        return "val"
    return "test"


def source_tag(path: Path) -> str:
    name = path.name or "source"
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_") or "source"


def discover_split_folder_items(source: Path, tag: str) -> list[DatasetItem]:
    items: list[DatasetItem] = []
    for folder_name, split in SPLIT_ALIASES.items():
        split_root = source / folder_name
        split_images = split_root / "images"
        split_labels = split_root / "labels"
        if not split_images.exists():
            continue
        for image in iter_images(split_images):
            relative = image.relative_to(split_images)
            label = split_labels / relative.with_suffix(".txt")
            items.append(DatasetItem(image=image, label=label, split=split, source=tag, source_root=source))
    return items


def discover_source_items(source: Path) -> list[DatasetItem]:
    items: list[DatasetItem] = []
    tag = source_tag(source)
    split_folder_items = discover_split_folder_items(source, tag)
    if split_folder_items:
        return split_folder_items

    images_root = source / "images"
    labels_root = source / "labels"

    if images_root.exists():
        split_found = False
        for folder_name, split in SPLIT_ALIASES.items():
            split_images = images_root / folder_name
            if not split_images.exists():
                continue
            split_found = True
            for image in iter_images(split_images):
                relative = image.relative_to(split_images)
                label = labels_root / folder_name / relative.with_suffix(".txt")
                items.append(DatasetItem(image=image, label=label, split=split, source=tag, source_root=source))
        if split_found:
            return items

        for image in iter_images(images_root):
            relative = image.relative_to(images_root)
            label = labels_root / relative.with_suffix(".txt")
            items.append(DatasetItem(image=image, label=label, split=None, source=tag, source_root=source))
        return items

    for image in iter_images(source):
        label = image.with_suffix(".txt")
        items.append(DatasetItem(image=image, label=label, split=None, source=tag, source_root=source))
    return items


def discover_background_items(background_dir: Path) -> list[DatasetItem]:
    return [
        DatasetItem(image=image, label=None, split=None, source=source_tag(background_dir), source_root=background_dir, is_background=True)
        for image in iter_images(background_dir)
    ]


def normalize_label_line(line: str, drone_class_ids: set[int]) -> tuple[str | None, str | None]:
    stripped = line.strip()
    if not stripped:
        return None, None
    parts = stripped.split()
    if len(parts) < 5:
        return None, "bad_field_count"
    try:
        class_id = int(float(parts[0]))
        values = [float(value) for value in parts[1:5]]
    except ValueError:
        return None, "bad_number"
    if class_id not in drone_class_ids:
        return None, None
    cx, cy, width, height = values
    if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0 and 0.0 < width <= 1.0 and 0.0 < height <= 1.0):
        return None, "bad_bbox"
    return f"0 {cx:.6f} {cy:.6f} {width:.6f} {height:.6f}", None


def convert_label(label_path: Path | None, drone_class_ids: set[int], is_background: bool) -> tuple[list[str], list[str]]:
    if is_background:
        return [], []
    if label_path is None or not label_path.exists():
        return [], ["missing_label"]
    converted: list[str] = []
    errors: list[str] = []
    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        normalized, error = normalize_label_line(line, drone_class_ids)
        if normalized is not None:
            converted.append(normalized)
        if error is not None:
            errors.append(error)
    return converted, errors


def clear_output(output_root: Path) -> None:
    for folder in ("images", "labels"):
        target = output_root / folder
        if target.exists():
            shutil.rmtree(target)
    for file_name in ("drone.yaml", "dataset_summary.json"):
        target = output_root / file_name
        if target.exists():
            target.unlink()


def ensure_output_dirs(output_root: Path) -> None:
    for split in SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)


def write_yaml(output_root: Path) -> None:
    resolved_output = output_root.resolve()
    try:
        dataset_path = resolved_output.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        dataset_path = resolved_output.as_posix()
    yaml_text = f"""path: {json.dumps(dataset_path)}
train: images/train
val: images/val
test: images/test
names:
  0: drone
"""
    (output_root / "drone.yaml").write_text(yaml_text, encoding="utf-8")


def unique_stem(item: DatasetItem, index: int) -> str:
    digest = hashlib.sha1(str(item.image.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:8]
    prefix = "bg" if item.is_background else "drone"
    return f"{item.source}_{prefix}_{index:06d}_{digest}"


def prepare_dataset(
    sources: list[Path],
    background_dirs: list[Path],
    output_root: Path,
    drone_class_ids: set[int],
    source_class_ids: dict[Path, set[int]],
    ratios: tuple[float, float, float],
    seed: int,
    clear: bool,
) -> dict[str, object]:
    if clear:
        clear_output(output_root)
    ensure_output_dirs(output_root)

    items: list[DatasetItem] = []
    for source in sources:
        items.extend(discover_source_items(source))
    for background_dir in background_dirs:
        items.extend(discover_background_items(background_dir))

    random.Random(seed).shuffle(items)

    summary: dict[str, object] = {
        "output_root": output_root.as_posix(),
        "drone_class_ids": sorted(drone_class_ids),
        "source_class_ids": {path.as_posix(): sorted(class_ids) for path, class_ids in source_class_ids.items()},
        "sources": [source.as_posix() for source in sources],
        "background_dirs": [path.as_posix() for path in background_dirs],
        "splits": {split: {"images": 0, "positive_images": 0, "background_images": 0, "boxes": 0} for split in SPLITS},
        "warnings": {},
    }
    warnings: dict[str, int] = {}

    for index, item in enumerate(items):
        split = item.split or stable_split(item.image, ratios, seed)
        if split not in SPLITS:
            warnings["unknown_split"] = warnings.get("unknown_split", 0) + 1
            split = "train"
        item_class_ids = source_class_ids.get(item.source_root, drone_class_ids)
        labels, errors = convert_label(item.label, item_class_ids, item.is_background)
        for error in errors:
            warnings[error] = warnings.get(error, 0) + 1
        stem = unique_stem(item, index)
        image_target = output_root / "images" / split / f"{stem}{item.image.suffix.lower()}"
        label_target = output_root / "labels" / split / f"{stem}.txt"
        shutil.copy2(item.image, image_target)
        label_target.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")

        split_summary = summary["splits"][split]  # type: ignore[index]
        split_summary["images"] += 1
        split_summary["boxes"] += len(labels)
        if item.is_background or not labels:
            split_summary["background_images"] += 1
        else:
            split_summary["positive_images"] += 1

    summary["warnings"] = warnings
    summary["total_images"] = sum(summary["splits"][split]["images"] for split in SPLITS)  # type: ignore[index]
    summary["total_boxes"] = sum(summary["splits"][split]["boxes"] for split in SPLITS)  # type: ignore[index]
    write_yaml(output_root)
    (output_root / "dataset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a single-class YOLOv8 drone dataset for Flytotal vision training.")
    parser.add_argument("--source", action="append", type=Path, default=[], help="YOLO-format dataset source. Can be repeated.")
    parser.add_argument("--background-dir", action="append", type=Path, default=[], help="Image folder used as empty-label negative samples. Can be repeated.")
    parser.add_argument("--include-captures", action="store_true", help="Add local captures/*.jpg as background negative samples.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output dataset root.")
    parser.add_argument("--drone-class-ids", type=parse_class_ids, default=parse_class_ids("0"), help="Source class ids that mean drone, comma-separated.")
    parser.add_argument(
        "--source-class-ids",
        action="append",
        type=parse_source_class_ids,
        default=[],
        help="Per-source drone class mapping, formatted as <source_path>=<class_ids>. Can be repeated.",
    )
    parser.add_argument("--split", type=parse_ratio, default=parse_ratio("70,20,10"), help="Split ratio for flat sources, default 70,20,10.")
    parser.add_argument("--seed", type=int, default=42, help="Stable split seed.")
    parser.add_argument("--clear", action="store_true", help="Clear generated images/labels/drone.yaml before preparing.")
    args = parser.parse_args()

    sources = [path.resolve() for path in args.source]
    source_set = set(sources)
    source_class_ids = dict(args.source_class_ids)
    unknown_mappings = [path for path in source_class_ids if path not in source_set]
    if unknown_mappings:
        parser.error("source class mapping path is not listed in --source: " + ", ".join(path.as_posix() for path in unknown_mappings))
    background_dirs = [path.resolve() for path in args.background_dir]
    if args.include_captures:
        background_dirs.append(DEFAULT_CAPTURES.resolve())

    if not sources and not background_dirs:
        parser.error("provide at least one --source or --background-dir, or use --include-captures")

    summary = prepare_dataset(
        sources=sources,
        background_dirs=background_dirs,
        output_root=args.output.resolve(),
        drone_class_ids=args.drone_class_ids,
        source_class_ids=source_class_ids,
        ratios=args.split,
        seed=int(args.seed),
        clear=bool(args.clear),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
