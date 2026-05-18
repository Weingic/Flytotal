from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.cpp"
CONFIG = ROOT / "include" / "AppConfig.h"
FUSION = ROOT / "lib" / "Fusion" / "Fusion.cpp"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        fail(f"missing {label}: {needle}")


def main() -> int:
    main_cpp = MAIN.read_text(encoding="utf-8")
    config_h = CONFIG.read_text(encoding="utf-8")
    fusion_cpp = FUSION.read_text(encoding="utf-8")

    enters = len(re.findall(r"portENTER_CRITICAL\(&dataMutex\)", main_cpp))
    exits = len(re.findall(r"portEXIT_CRITICAL\(&dataMutex\)", main_cpp))
    print(f"critical_sections: enter={enters} exit={exits}")
    if enters != exits:
        fail("critical section enter/exit count is unbalanced")

    require(config_h, "MaxReconnectAttempts", "NodeB reconnect hard limit")
    require(main_cpp, "nodeBReconnectLockedOut", "NodeB reconnect lockout state")
    require(main_cpp, "NODEB,LINK", "NodeB link status command")
    require(main_cpp, "NODEB,RECOVER", "NodeB manual recover command")

    require(main_cpp, "crc_supported=0,integrity=STRUCTURAL_NO_CRC", "LD2451 honest no-CRC reporting")
    require(main_cpp, "bit_flip_valid_shape_suspect", "LD2451 bit-flip plausibility selftest")
    require(main_cpp, "ld2451SuspectFrameCount", "LD2451 suspect frame counter")

    require(main_cpp, "deriveTargetVerdictFromSnapshot", "snapshot-only target verdict derivation")
    if "void deriveTargetVerdict(" in main_cpp:
        fail("legacy deriveTargetVerdict() name still exists")

    require(fusion_cpp, "clampScore(data.radar_track.multirotor_score)", "Fusion multirotor score clamp")
    require(main_cpp, "clampMultirotorScore(snapshot.multirotor_score)", "main multirotor score clamp")

    print("firmware_safety_checks: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
