from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SEND_OK = re.compile(r"SEND_CB.*(成功|SUCCESS|OK)", re.IGNORECASE)
SEND_FAIL = re.compile(r"SEND_CB.*(失败|FAIL)", re.IGNORECASE)
ACK = re.compile(r"ACK_RECV", re.IGNORECASE)


def analyze(text: str) -> dict[str, object]:
    lines = text.splitlines()
    send_ok = sum(1 for line in lines if SEND_OK.search(line))
    send_fail = sum(1 for line in lines if SEND_FAIL.search(line))
    ack = sum(1 for line in lines if ACK.search(line))
    total = send_ok + send_fail
    return {
        "send_total": total,
        "send_ok": send_ok,
        "send_fail": send_fail,
        "ack_count": ack,
        "send_success_rate": round(send_ok / total, 3) if total else 0.0,
        "estimated_loss_rate": round(max(0, send_ok - ack) / send_ok, 3) if send_ok else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze ESP-NOW demo serial logs")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("captures/v5_2/espnow_capture_report.json"))
    args = parser.parse_args()
    report = analyze(args.input.read_text(encoding="utf-8", errors="ignore"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = args.output.with_suffix(".md")
    md.write_text(
        "# ESP-NOW Capture Report\n\n"
        f"- send_total: {report['send_total']}\n"
        f"- send_ok: {report['send_ok']}\n"
        f"- send_fail: {report['send_fail']}\n"
        f"- ack_count: {report['ack_count']}\n"
        f"- send_success_rate: {report['send_success_rate']}\n"
        f"- estimated_loss_rate: {report['estimated_loss_rate']}\n",
        encoding="utf-8",
    )
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
