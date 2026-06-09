from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.cpp"
CONFIG = ROOT / "include" / "AppConfig.h"
FUSION = ROOT / "lib" / "Fusion" / "Fusion.cpp"
CLOUD_CLIENT = ROOT / "lib" / "CloudClient" / "CloudClient.cpp"
GITIGNORE = ROOT / ".gitignore"


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
    cloud_client_cpp = CLOUD_CLIENT.read_text(encoding="utf-8")
    gitignore = GITIGNORE.read_text(encoding="utf-8")

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
    require(main_cpp, "xor_supported=1", "LD2451 optional XOR compatibility reporting")
    require(main_cpp, "crc_error_count", "LD2451 CRC/XOR error counter output")
    require(ROOT.joinpath("lib", "Ld2451Parser", "Ld2451Parser.h").read_text(encoding="utf-8"), "crc_error_count", "LD2451 parser CRC/XOR stats field")
    require(ROOT.joinpath("lib", "Ld2451Parser", "Ld2451Parser.cpp").read_text(encoding="utf-8"), "rejectCrcError", "LD2451 parser CRC/XOR reject path")
    require(ROOT.joinpath("lib", "Ld2451Parser", "Ld2451Parser.cpp").read_text(encoding="utf-8"), "xorChecksum", "LD2451 parser optional XOR checksum")
    require(main_cpp, "xor_valid", "LD2451 optional XOR valid selftest")
    require(main_cpp, "xor_bad", "LD2451 optional XOR reject selftest")
    require(main_cpp, "bit_flip_valid_shape_suspect", "LD2451 bit-flip plausibility selftest")
    require(main_cpp, "ld2451SuspectFrameCount", "LD2451 suspect frame counter")

    require(main_cpp, "deriveTargetVerdictFromSnapshot", "snapshot-only target verdict derivation")
    if "void deriveTargetVerdict(" in main_cpp:
        fail("legacy deriveTargetVerdict() name still exists")

    require(fusion_cpp, "clampScore(data.radar_track.multirotor_score)", "Fusion multirotor score clamp")
    require(main_cpp, "clampMultirotorScore(snapshot.multirotor_score)", "main multirotor score clamp")

    require(gitignore, "include/secrets.h", "local secrets ignore rule")
    require(cloud_client_cpp, "esp_crt_bundle_attach", "HTTPS cert bundle validation")
    require(main_cpp, "CLOUD,TEST", "manual cloud test command")
    require(main_cpp, "CLOUD,ENABLE", "cloud enable command")
    require(main_cpp, "CLOUD,STATUS", "cloud status command")
    require(config_h, "AiEnabledByDefault = false", "CLOUD default disabled")
    require(main_cpp, "applyCloudCommand", "cloud downlink command execution")
    require(main_cpp, "runtime_event_threshold = 0.0f", "runtime event threshold default override disabled")
    require(main_cpp, "effectiveEventThreshold", "runtime event threshold display/runtime helper")
    require(main_cpp, "CLOUD,APPLY", "offline cloud command apply test command")
    require(main_cpp, "CLOUD,RESET", "offline cloud command reset command")
    require(main_cpp, "DOWNGRADE_REJECTED_THREAT_ACTIVE", "edge veto for unsafe economy downgrade")
    require(main_cpp, "PARACHUTE_INTENT_LOGGED", "parachute intent logged only")
    require(main_cpp, "NOT_INTEGRATED", "parachute hardware honesty marker")
    require(main_cpp, "refreshFusionRuntimeLocked(now)", "cloud switch mode refreshes fusion runtime")
    require(main_cpp, "syncActiveNodeRuntimeCacheLocked()", "cloud command syncs active runtime cache")
    require(ROOT.joinpath("lib", "HunterAction", "HunterAction.h").read_text(encoding="utf-8"), "event_threshold_override", "HunterAction runtime threshold parameter")
    require(ROOT.joinpath("lib", "HunterAction", "HunterAction.cpp").read_text(encoding="utf-8"), "effective_event_threshold", "HunterAction effective event threshold")
    require(ROOT.joinpath("lib", "CloudClient", "CloudClient.h").read_text(encoding="utf-8"), "command_threshold_value", "cloud threshold command result field")
    require(ROOT.joinpath("lib", "CloudClient", "CloudClient.h").read_text(encoding="utf-8"), "command_mode", "cloud switch mode command result field")
    require(ROOT.joinpath("lib", "CloudClient", "CloudClient.cpp").read_text(encoding="utf-8"), "event_threshold", "cloud threshold command params parsing")
    require(ROOT.joinpath("lib", "CloudClient", "CloudClient.cpp").read_text(encoding="utf-8"), "command_reason", "cloud switch reason parsing")
    require(main_cpp, "CLOUD,DEGRADED", "LLM failure degraded log")
    require(main_cpp, "shouldEmitCloudFailureLog", "cloud failure log throttle")
    require(main_cpp, "CLOUD,DROP,reason=queue_full", "cloud queue full drop log")
    require(main_cpp, "NO_ACTION_NEEDED", "cloud NONE command no-action semantics")
    require(main_cpp, "THRESHOLD_AUTO_RESTORED", "cloud low-threat threshold auto restore")
    require(main_cpp, "THRESHOLD_EVENT_CLOSED_RESTORED", "cloud event-close threshold restore")
    require(main_cpp, "CLOUD_FAILED_LOCAL_FALLBACK", "cloud failed local fallback marker")
    require(main_cpp, "cloud_command_source_event_id", "cloud command source event audit field")
    require(main_cpp, "cloud_command_reason", "cloud command reason audit field")
    require(main_cpp, "cloud_command_applied_ms", "cloud command applied time audit field")
    require(ROOT.joinpath("include", "SharedData.h").read_text(encoding="utf-8"), "cloud_command_source_event_id", "shared cloud source event audit field")
    require(ROOT.joinpath("include", "SharedData.h").read_text(encoding="utf-8"), "cloud_command_reason", "shared cloud command reason audit field")
    require(ROOT.joinpath("include", "SharedData.h").read_text(encoding="utf-8"), "cloud_command_applied_ms", "shared cloud command applied time audit field")
    require(cloud_client_cpp, "http_status_not_ok", "cloud HTTP status failure reason")
    require(cloud_client_cpp, "response_json_parse_failed", "cloud response JSON failure reason")
    require(cloud_client_cpp, "assessment_json_parse_failed", "cloud assessment JSON failure reason")
    require(cloud_client_cpp, "http_request_failed", "cloud HTTP request failure reason")
    require(ROOT.joinpath("tools", "cloud_demo_replay.py").read_text(encoding="utf-8"), "Flytotal Edge-Cloud-Edge AI Command Loop", "cloud replay evidence diagram tool")
    require(main_cpp, "HandoverFlowState", "handoff state machine enum")
    require(main_cpp, "HANDOVER_FLOW_ACTIVE", "handoff active state")
    require(main_cpp, "HANDOVER_FLOW_DONE", "handoff done state")
    require(main_cpp, "updateHandoverStateMachine", "handoff state machine updater")
    require(main_cpp, "handover_state=", "handoff state serial output")

    scanned_files = [
        MAIN,
        CONFIG,
        ROOT / "include" / "SharedData.h",
        ROOT / "include" / "secrets.example.h",
        ROOT / "lib" / "CloudClient" / "CloudClient.h",
        CLOUD_CLIENT,
        ROOT / "platformio.ini",
        ROOT / "tools" / "node_a_serial_bridge_NodeA串口桥接.py",
    ]
    key_pattern = re.compile(r"ark-[A-Za-z0-9_-]{8,}")
    for path in scanned_files:
        text = path.read_text(encoding="utf-8")
        if key_pattern.search(text):
            fail(f"possible Ark API key leaked in {path.relative_to(ROOT)}")

    print("firmware_safety_checks: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
