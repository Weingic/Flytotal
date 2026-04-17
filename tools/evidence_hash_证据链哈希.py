# 证据链 Hash 框架
# 对事件证据对象计算 SHA-256 摘要，用于完整性核验。
#
# 关键规则：计算 hash 时必须排除 evidence_hash 字段自身，避免循环依赖。
# 核心字段集（与 Win 侧冻结字段对齐）：
#   event_id, track_id, risk_score, rid_status, wl_status,
#   reason_flags, capture_path, ts_open, ts_close, close_reason
#
# 使用方式：
#   # 计算并写入 hash
#   python tools/evidence_hash_证据链哈希.py --input captures/event_evidence_xxx.json
#
#   # 核验已有 hash
#   python tools/evidence_hash_证据链哈希.py --input captures/event_evidence_xxx.json --verify
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 参与 hash 计算的核心字段（顺序固定，与 Win 侧保持一致）
EVIDENCE_HASH_FIELDS: tuple[str, ...] = (
    "event_id",
    "track_id",
    "risk_score",
    "rid_status",
    "wl_status",
    "reason_flags",
    "capture_path",
    "ts_open",
    "ts_close",
    "close_reason",
)

# 计算时强制排除的字段（避免循环依赖）
HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset({"evidence_hash", "hash_fields", "hash_algorithm"})

HASH_ALGORITHM = "sha256"


def resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"文件顶层必须是 JSON object: {path}")
    return payload


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False), encoding="utf-8")
    temp.replace(path)


# ---------------------------------------------------------------------------
# Hash 计算核心
# ---------------------------------------------------------------------------

def extract_hash_payload(evidence: dict[str, Any]) -> dict[str, Any]:
    """从证据对象提取参与 hash 计算的字段子集。

    规则：
    1. 只取 EVIDENCE_HASH_FIELDS 中定义的字段（字段不存在时填 None）。
    2. 强制排除 HASH_EXCLUDED_FIELDS 中的字段。
    3. 字段顺序固定（按 EVIDENCE_HASH_FIELDS 的定义顺序），确保跨平台一致性。
    """
    payload: dict[str, Any] = {}
    for key in EVIDENCE_HASH_FIELDS:
        if key in HASH_EXCLUDED_FIELDS:
            continue
        payload[key] = evidence.get(key, None)
    return payload


def compute_evidence_hash(evidence: dict[str, Any]) -> str:
    """计算证据对象的 SHA-256 hash。

    序列化规则：
    - 使用 JSON 序列化（ensure_ascii=False, separators=(',', ':'), sort_keys=False）
    - 字段顺序固定，由 extract_hash_payload 保证
    - UTF-8 编码后取摘要
    """
    hash_payload = extract_hash_payload(evidence)
    canonical = json.dumps(hash_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    digest = hashlib.new(HASH_ALGORITHM, canonical.encode("utf-8")).hexdigest()
    return digest


def attach_hash(evidence: dict[str, Any]) -> dict[str, Any]:
    """向证据对象写入 evidence_hash 字段（in-place 修改并返回）。"""
    evidence["evidence_hash"] = compute_evidence_hash(evidence)
    evidence["hash_fields"] = list(EVIDENCE_HASH_FIELDS)
    evidence["hash_algorithm"] = HASH_ALGORITHM
    return evidence


def verify_hash(evidence: dict[str, Any]) -> tuple[bool, str, str]:
    """核验证据对象的 hash 是否与内容一致。

    返回 (ok, stored_hash, recomputed_hash)。
    """
    stored = str(evidence.get("evidence_hash", ""))
    if not stored:
        return False, "", ""
    recomputed = compute_evidence_hash(evidence)
    return stored == recomputed, stored, recomputed


# ---------------------------------------------------------------------------
# 批量处理
# ---------------------------------------------------------------------------

def process_evidence_file(
    input_path: Path,
    output_path: Path | None,
    verify_mode: bool,
    verbose: bool,
) -> bool:
    """处理单个证据 JSON 文件。

    verify_mode=True  → 核验 hash，不写文件
    verify_mode=False → 计算并写入 hash
    """
    raw = load_json_file(input_path)
    # 自动识别两种结构：
    #   A. 证据导出包裹格式（event_detail.event_object_v1）
    #   B. 裸 event_object_v1 格式
    ev_obj = raw.get("event_detail", {}).get("event_object_v1")
    evidence = ev_obj if isinstance(ev_obj, dict) else raw

    if verify_mode:
        ok, stored, recomputed = verify_hash(evidence)
        event_id = evidence.get("event_id", "NONE")
        if ok:
            print(f"[hash] PASS  event_id={event_id}  hash={stored[:16]}...")
        else:
            print(f"[hash] FAIL  event_id={event_id}")
            print(f"  stored    = {stored}")
            print(f"  recomputed= {recomputed}")
            if verbose:
                payload = extract_hash_payload(evidence)
                print(f"  hash_payload = {json.dumps(payload, ensure_ascii=False)}")
        return ok
    else:
        attach_hash(evidence)
        target = output_path or input_path
        write_json_file(target, evidence)
        event_id = evidence.get("event_id", "NONE")
        digest = evidence["evidence_hash"]
        print(f"[hash] 已写入  event_id={event_id}  hash={digest[:16]}...  → {target}")
        if verbose:
            payload = extract_hash_payload(evidence)
            print(f"  hash_payload = {json.dumps(payload, ensure_ascii=False)}")
        return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="证据链 Hash 计算与核验工具")
    parser.add_argument("--input", type=Path, required=True,
                        help="输入证据 JSON 文件路径")
    parser.add_argument("--output", type=Path, default=None,
                        help="输出文件路径（不指定则覆盖原文件，verify 模式忽略）")
    parser.add_argument("--verify", action="store_true",
                        help="核验模式：检查文件中已有的 evidence_hash 是否与内容一致")
    parser.add_argument("--verbose", action="store_true",
                        help="输出参与 hash 计算的字段内容")
    args = parser.parse_args()

    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output) if args.output else None

    try:
        ok = process_evidence_file(
            input_path=input_path,
            output_path=output_path,
            verify_mode=args.verify,
            verbose=args.verbose,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[hash] 错误: {exc}")
        return 1

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
