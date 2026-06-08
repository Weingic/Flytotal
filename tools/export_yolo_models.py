from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COCO_OUTPUT = REPO_ROOT / "models" / "yolov8n.onnx"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_onnx(path: Path) -> dict[str, Any]:
    try:
        import onnxruntime as ort  # type: ignore
    except ImportError as exc:
        raise RuntimeError("onnxruntime is not installed. Run `python -m pip install -U -r requirements-vision.txt`.") from exc

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    inputs = [
        {
            "name": item.name,
            "shape": list(item.shape),
            "type": item.type,
        }
        for item in session.get_inputs()
    ]
    outputs = [
        {
            "name": item.name,
            "shape": list(item.shape),
            "type": item.type,
        }
        for item in session.get_outputs()
    ]
    return {"inputs": inputs, "outputs": outputs}


def export_yolo(weights: str | Path, output: Path, imgsz: int, opset: int) -> Path:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("ultralytics is not installed. Run `python -m pip install -U -r requirements-vision.txt`.") from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    exported = Path(model.export(format="onnx", imgsz=imgsz, opset=opset, simplify=False))
    if not exported.exists():
        raise RuntimeError(f"Ultralytics export finished but output was not found: {exported}")

    exported = exported.resolve()
    output = output.resolve()
    if exported != output:
        shutil.copy2(exported, output)
    return output


def write_local_manifest(path: Path, label: str, weights: str, output: Path, imgsz: int, metadata: dict[str, Any]) -> None:
    manifest_path = output.parent / "MODEL_MANIFEST.local.json"
    payload: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    models = [item for item in payload.get("models", []) if isinstance(item, dict) and item.get("path") != output.as_posix()]
    models.append(
        {
            "name": label,
            "path": output.as_posix(),
            "weights": str(weights),
            "input_size": imgsz,
            "sha256": sha256_file(output),
            "onnx": metadata,
        }
    )
    payload = {"models": models}
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"local_manifest={manifest_path.as_posix()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export YOLO weights to ONNX for the Flytotal vision bridge.")
    parser.add_argument("--preset", choices=["coco"], help="Preset export. `coco` downloads/uses Ultralytics yolov8n.pt.")
    parser.add_argument("--weights", type=Path, help="Local .pt weights for a custom drone detector.")
    parser.add_argument("--output", type=Path, help="Output ONNX path. Defaults to models/yolov8n.onnx for --preset coco.")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO export image size.")
    parser.add_argument("--opset", type=int, default=12, help="ONNX opset for export.")
    parser.add_argument("--model-label", default="", help="Human-readable model label written to the local manifest.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preset == "coco":
        weights: str | Path = "yolov8n.pt"
        output = args.output or DEFAULT_COCO_OUTPUT
        label = args.model_label or "coco-yolov8n"
    else:
        if not args.weights:
            raise SystemExit("Either `--preset coco` or `--weights <file.pt>` is required.")
        weights = args.weights
        if not Path(weights).exists():
            raise SystemExit(f"Weights file not found: {weights}")
        output = args.output or (REPO_ROOT / "models" / f"{Path(weights).stem}.onnx")
        label = args.model_label or Path(weights).stem

    output = output if output.is_absolute() else (REPO_ROOT / output)
    try:
        exported = export_yolo(weights, output, int(args.imgsz), int(args.opset))
        metadata = validate_onnx(exported)
    except RuntimeError as exc:
        print(f"ERROR,{exc}")
        return 1
    write_local_manifest(REPO_ROOT, label, str(weights), exported, int(args.imgsz), metadata)
    print(f"exported={exported.as_posix()}")
    print(f"sha256={sha256_file(exported)}")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
