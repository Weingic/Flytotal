import argparse
import time

import serial


def build_rid_msg(
    rid_id: str,
    device_type: str,
    source: str,
    timestamp_ms: int,
    auth_status: str,
    whitelist_tag: str,
    signal_strength: int,
) -> str:
    return (
        f"RID,MSG,{rid_id},{device_type},{source},{timestamp_ms},"
        f"{auth_status},{whitelist_tag},{signal_strength}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Broadcast RID simulation packets to Node A over serial.")
    parser.add_argument("--port", required=True, help="Serial port, for example COM4")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--interval", type=float, default=0.8, help="Seconds between packets")
    parser.add_argument("--count", type=int, default=0, help="How many packets to send, 0 means loop forever")
    parser.add_argument(
        "--mode",
        choices=["normal", "missing", "invalid", "received"],
        default="normal",
        help="normal=white list matched, missing=clear identity, invalid=auth/white list failed, received=received but not matched",
    )
    parser.add_argument("--rid-id", default="SIM-RID-001", help="RID id field")
    parser.add_argument("--device-type", default="UAV", help="device_type field")
    parser.add_argument("--source", default="RID_SIM", help="source field")
    parser.add_argument("--signal-strength", type=int, default=-48, help="signal_strength field")
    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.2)
    except serial.SerialException as exc:
        print(f"Failed to open {args.port}: {exc}")
        return 1

    sent = 0
    print(
        f"RID simulator started: port={args.port} baud={args.baud} mode={args.mode} interval={args.interval}s count={args.count or 'INF'}"
    )
    with ser:
        try:
            while True:
                if args.mode == "missing":
                    line = "RID,CLEAR"
                else:
                    auth_status = "VALID"
                    whitelist_tag = "WL_OK"
                    if args.mode == "invalid":
                        auth_status = "INVALID"
                        whitelist_tag = "DENY"
                    elif args.mode == "received":
                        auth_status = "VALID"
                        whitelist_tag = "PENDING"
                    line = build_rid_msg(
                        rid_id=args.rid_id,
                        device_type=args.device_type,
                        source=args.source,
                        timestamp_ms=int(time.time() * 1000),
                        auth_status=auth_status,
                        whitelist_tag=whitelist_tag,
                        signal_strength=args.signal_strength,
                    )

                ser.write((line + "\n").encode("utf-8"))
                ser.flush()
                sent += 1
                print(f"[{sent}] >>> {line}")

                if args.count > 0 and sent >= args.count:
                    break

                time.sleep(max(0.05, args.interval))
        except KeyboardInterrupt:
            print("\nRID simulator stopped by user.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
