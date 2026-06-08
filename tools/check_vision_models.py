from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_onnx(path: Path) -> dict[str, Any]:
    try:
        import onnxruntime as ort  # type: ignore
    except ImportError as exc:
        raise RuntimeError("onnxruntime is not installed. Run `python -m pip install -U -r requirements-vision.txt`.") from exc

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return {
        "inputs": [{"name": item.name, "shape": list(item.shape), "type": item.type} for item in session.get_inputs()],
        "outputs": [{"name": item.name, "shape": list(item.shape), "type": item.type} for item in session.get_outputs()],
    }


def infer_model_hint(path: Path) -> str:
    name = path.name.lower()
    if "drone" in name or "uav" in name:
        return "drone_specific_candidate"
    if "yolov8n" in name:
        return "coco_generic_yolov8n"
    return "unknown_onnx_detector"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local ONNX vision models used by the Flytotal vision bridge.")
    parser.add_argument("--model", type=Path, default=Path("models/yolov8n.onnx"), help="ONNX model path")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    args = parser.parse_args()

    model_path = args.model
    if not model_path.exists():
        payload = {
            "ok": False,
            "model": model_path.as_posix(),
            "error": "model_missing",
            "hint": "Run `python tools/export_yolo_models.py --preset coco` first.",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    try:
        metadata = load_onnx(model_path)
    except Exception as exc:
        payload = {
            "ok": False,
            "model": model_path.as_posix(),
            "error": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    payload = {
        "ok": True,
        "model": model_path.as_posix(),
        "model_hint": infer_model_hint(model_path),
        "sha256": sha256_file(model_path),
        "onnx": metadata,
        "note": "COCO yolov8n has no drone class; use it as generic detection + CSRT tracking only." if infer_model_hint(model_path) == "coco_generic_yolov8n" else "Check class mapping before demo.",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ok=1 model={payload['model']} hint={payload['model_hint']}")
        print(f"sha256={payload['sha256']}")
        for item in metadata["inputs"]:
            print(f"input name={item['name']} shape={item['shape']} type={item['type']}")
        for item in metadata["outputs"]:
            print(f"output name={item['name']} shape={item['shape']} type={item['type']}")
        print(payload["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
