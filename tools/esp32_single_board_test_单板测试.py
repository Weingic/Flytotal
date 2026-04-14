# ????? ESP32 ????????????????????????????????????
import argparse
import sys
import time

import serial


DEFAULT_COMMANDS: list[tuple[str, float | None]] = [
    ("HELP", None),
    ("STATUS", None),
    ("SELFTEST", None),
    ("RID,OK", None),
    ("STATUS", None),
    ("RID,MISSING", None),
    ("STATUS", None),
    ("RID,SUSPICIOUS", None),
    ("STATUS", None),
    ("KP,0.60", None),
    ("KD,0.10", None),
    ("TRACK,320,1800", 1.6),
    ("STATUS", None),
    ("TRACK,CLEAR", 1.2),
    ("RESET", None),
    ("STATUS", None),
]


def read_lines(ser: serial.Serial, duration_s: float, prefix: str = "") -> list[str]:
    deadline = time.time() + duration_s
    lines: list[str] = []
    while time.time() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        lines.append(line)
        print(f"{prefix}{line}")
    return lines


def send_command(ser: serial.Serial, command: str) -> None:
    ser.write((command + "\n").encode("utf-8"))
    ser.flush()
    print(f"\n>>> {command}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ESP32 single-board serial smoke test")
    parser.add_argument("--port", required=True, help="Serial port, for example COM4")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument(
        "--boot-wait",
        type=float,
        default=4.0,
        help="Seconds to wait for startup logs after opening the port",
    )
    parser.add_argument(
        "--command-wait",
        type=float,
        default=1.2,
        help="Default seconds to wait after each command",
    )
    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.2)
    except serial.SerialException as exc:
        print(f"Failed to open {args.port}: {exc}", file=sys.stderr)
        return 1

    with ser:
        time.sleep(0.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print(f"Connected to {args.port} at {args.baud}")
        print("\n--- Boot logs ---")
        boot_lines = read_lines(ser, args.boot_wait)

        print("\n--- Command test ---")
        all_lines: list[str] = []
        for command, custom_wait in DEFAULT_COMMANDS:
            send_command(ser, command)
            wait_s = custom_wait if custom_wait is not None else args.command_wait
            all_lines.extend(read_lines(ser, wait_s, prefix="    "))

        all_output = boot_lines + all_lines

        print("\n--- Summary ---")
        heartbeat_count = sum(1 for line in all_output if line.startswith("UPLINK,HB"))
        track_count = sum(1 for line in all_output if line.startswith("UPLINK,TRACK"))
        status_count = sum(1 for line in all_output if line.startswith("STATUS,"))
        selftest_count = sum(1 for line in all_output if line.startswith("SELFTEST,"))
        unknown_count = sum(1 for line in all_output if "Unknown command" in line)

        print(f"Heartbeats observed: {heartbeat_count}")
        print(f"Track frames observed: {track_count}")
        print(f"Status snapshots observed: {status_count}")
        print(f"Selftest lines observed: {selftest_count}")
        print(f"Unknown command responses: {unknown_count}")

        last_status = next((line for line in reversed(all_output) if line.startswith("STATUS,")), None)
        if last_status:
            print(f"Last STATUS: {last_status}")

        last_track = next((line for line in reversed(all_output) if line.startswith("UPLINK,TRACK")), None)
        if last_track:
            print(f"Last UPLINK,TRACK: {last_track}")

        return 0


if __name__ == "__main__":
    raise SystemExit(main())
