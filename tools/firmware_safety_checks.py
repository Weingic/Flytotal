from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.cpp"
CONFIG = ROOT / "include" / "AppConfig.h"
FUSION = ROOT / "lib" / "Fusion" / "Fusion.cpp"
CLOUD_CLIENT = ROOT / "lib" / "CloudClient" / "CloudClient.cpp"
CLOUD_CLIENT_HEADER = ROOT / "lib" / "CloudClient" / "CloudClient.h"
GITIGNORE = ROOT / ".gitignore"
SECRETS = ROOT / "include" / "secrets.h"
ARK_KEY_GIT_PATTERN = r"(^|[^A-Za-z0-9_])ark-[A-Za-z0-9_-]{8,}"
ARK_KEY_BYTES_PATTERN = re.compile(rb"(?<![A-Za-z0-9_])ark-[A-Za-z0-9_-]{8,}")


class SecretAuditError(RuntimeError):
    pass


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        fail(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        fail(f"forbidden {label}: {needle}")


def extract_braced_block(text: str, marker: str, label: str) -> str:
    marker_start = text.find(marker)
    if marker_start < 0:
        fail(f"missing {label}: {marker}")

    brace_start = text.find("{", marker_start)
    if brace_start < 0:
        fail(f"missing opening brace for {label}")

    depth = 0
    for index in range(brace_start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start : index + 1]
    fail(f"unbalanced braces for {label}")
    return ""


def audit_git_secret_hygiene(root: Path) -> int:
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SecretAuditError("git tracked-file audit unavailable")

    tracked_files = [
        item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        for item in completed.stdout.split(b"\0")
        if item
    ]
    if "include/secrets.h" in tracked_files:
        raise SecretAuditError("include/secrets.h is tracked by git")

    secret_values: dict[str, bytes] = {}
    secrets_file = root / "include" / "secrets.h"
    if secrets_file.exists():
        secrets_text = secrets_file.read_text(encoding="utf-8")
        for symbol in ("FLYTOTAL_WIFI_PASSWORD", "FLYTOTAL_ARK_API_KEY"):
            match = re.search(rf'^\s*#define\s+{symbol}\s+"([^"]*)"', secrets_text, re.MULTILINE)
            if match and len(match.group(1)) >= 8:
                secret_values[symbol] = match.group(1).encode("utf-8")

    def git_index_matches(arguments: list[str], input_data: bytes | None = None) -> list[str]:
        grep_result = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "-C",
                str(root),
                "grep",
                "--cached",
                "-a",
                "-l",
                *arguments,
                "--",
            ],
            input=input_data,
            capture_output=True,
            check=False,
        )
        if grep_result.returncode not in (0, 1):
            raise SecretAuditError("git index secret audit unavailable")
        return [
            item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for item in grep_result.stdout.splitlines()
            if item
        ]

    indexed_ark_files = git_index_matches(["-E", ARK_KEY_GIT_PATTERN])
    if indexed_ark_files:
        raise SecretAuditError(
            f"possible Ark API key leaked in Git index file: {indexed_ark_files[0]}"
        )
    if secret_values:
        indexed_secret_files = git_index_matches(
            ["-F", "-f", "-"],
            b"\n".join(secret_values.values()) + b"\n",
        )
        if indexed_secret_files:
            raise SecretAuditError(
                f"local secret value leaked in Git index file: {indexed_secret_files[0]}"
            )

    history_result = subprocess.run(
        [
            "git",
            "-c",
            "core.quotepath=false",
            "-C",
            str(root),
            "log",
            "--all",
            "-G",
            ARK_KEY_GIT_PATTERN,
            "--format=%H",
            "--name-only",
            "--",
        ],
        capture_output=True,
        check=False,
    )
    if history_result.returncode != 0:
        raise SecretAuditError("git history secret audit unavailable")
    if history_result.stdout.strip():
        raise SecretAuditError("possible Ark API key found in reachable Git history")

    for relative_path in tracked_files:
        path = root / Path(relative_path)
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise SecretAuditError(f"cannot inspect tracked file: {relative_path}") from exc
        if ARK_KEY_BYTES_PATTERN.search(data):
            raise SecretAuditError(f"possible Ark API key leaked in tracked file: {relative_path}")
        for symbol, secret_value in secret_values.items():
            if secret_value in data:
                raise SecretAuditError(f"local {symbol} value leaked in tracked file: {relative_path}")

    return len(tracked_files)


def audit_compiled_secret_presence(root: Path, firmware_path: Path) -> int:
    secrets_file = root / "include" / "secrets.h"
    if not secrets_file.exists():
        raise SecretAuditError("local include/secrets.h is missing")
    if not firmware_path.exists():
        raise SecretAuditError(f"firmware binary is missing: {firmware_path}")

    secrets_text = secrets_file.read_text(encoding="utf-8")
    configured_values: dict[str, bytes] = {}
    for symbol in (
        "FLYTOTAL_WIFI_SSID",
        "FLYTOTAL_WIFI_PASSWORD",
        "FLYTOTAL_ARK_API_KEY",
    ):
        match = re.search(rf'^\s*#define\s+{symbol}\s+"([^"]*)"', secrets_text, re.MULTILINE)
        value = match.group(1) if match else ""
        if not value or value.upper().startswith("YOUR_"):
            raise SecretAuditError(f"local secret is not configured: {symbol}")
        configured_values[symbol] = value.encode("utf-8")

    firmware_data = firmware_path.read_bytes()
    missing_symbols = [
        symbol
        for symbol, value in configured_values.items()
        if value not in firmware_data
    ]
    if missing_symbols:
        raise SecretAuditError(
            "configured secret missing from firmware binary: " + ", ".join(missing_symbols)
        )
    return len(configured_values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flytotal firmware static safety checks")
    parser.add_argument(
        "--require-compiled-secrets",
        action="store_true",
        help="Require all local Wi-Fi/API values to be present in the built firmware without printing them",
    )
    parser.add_argument(
        "--firmware-bin",
        type=Path,
        default=Path(".pio/build/esp32-s3-devkitc-1/firmware.bin"),
        help="Firmware binary checked by --require-compiled-secrets",
    )
    args = parser.parse_args(argv)

    main_cpp = MAIN.read_text(encoding="utf-8")
    config_h = CONFIG.read_text(encoding="utf-8")
    fusion_cpp = FUSION.read_text(encoding="utf-8")
    cloud_client_cpp = CLOUD_CLIENT.read_text(encoding="utf-8")
    cloud_client_h = CLOUD_CLIENT_HEADER.read_text(encoding="utf-8")
    gitignore = GITIGNORE.read_text(encoding="utf-8")
    serial_bridge = ROOT.joinpath("tools", "node_a_serial_bridge_NodeA串口桥接.py").read_text(encoding="utf-8")
    strict_closure = ROOT.joinpath(
        "tools", "single_node_evidence_closure_check_单节点证据闭环核对.py"
    ).read_text(encoding="utf-8")

    enters = len(re.findall(r"portENTER_CRITICAL\(&dataMutex\)", main_cpp))
    exits = len(re.findall(r"portEXIT_CRITICAL\(&dataMutex\)", main_cpp))
    print(f"critical_sections: enter={enters} exit={exits}")
    if enters != exits:
        fail("critical section enter/exit count is unbalanced")

    require(config_h, "MaxReconnectAttempts", "NodeB reconnect hard limit")
    require(main_cpp, "nodeBReconnectLockedOut", "NodeB reconnect lockout state")
    require(main_cpp, "NODEB,LINK", "NodeB link status command")
    require(main_cpp, "NODEB,RECOVER", "NodeB manual recover command")

    require(main_cpp, "RTC_DATA_ATTR uint32_t retainedBootCount", "retained node boot counter")
    require(main_cpp, "esp_reset_reason()", "ESP reset reason capture")
    require(main_cpp, "rtc_get_reset_reason(0)", "ESP32-S3 raw reset reason capture")
    require(main_cpp, "BOOT,SESSION", "node boot session telemetry")
    require(main_cpp, "boot_id=", "node boot id status field")
    require(main_cpp, "reset_reason=", "node reset reason status field")
    require(main_cpp, "reset_reason_raw=", "node raw reset reason status field")
    require(main_cpp, "uptime_ms=", "node uptime status field")
    require(serial_bridge, '"BOOT,SESSION"', "serial bridge boot session monitoring")
    require(serial_bridge, '"boot_id": "boot_id"', "serial bridge boot id persistence")
    require(serial_bridge, '"reset_reason": "reset_reason"', "serial bridge reset reason persistence")
    require(serial_bridge, '"reset_reason_raw": "reset_reason_raw"', "serial bridge raw reset reason persistence")
    require(serial_bridge, '"uptime_ms": "node_uptime_ms"', "serial bridge uptime persistence")

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
    require(cloud_client_cpp, "kArkRootCaPem", "HTTPS root CA certificate")
    require(cloud_client_cpp, "config.cert_pem = kArkRootCaPem", "HTTPS cert PEM validation")
    require(cloud_client_cpp, "config.cert_len = sizeof(kArkRootCaPem)", "HTTPS cert length binding")
    require(main_cpp, "CLOUD,TEST", "manual cloud test command")
    require(main_cpp, "CLOUD,ENABLE", "cloud enable command")
    require(main_cpp, "CLOUD,STATUS", "cloud status command")
    require(config_h, "AiEnabledByDefault = false", "CLOUD default disabled")
    require(config_h, "ContractVersion = 2", "cloud event echo contract version")
    require(config_h, "EventEchoRequired = true", "cloud event echo capability")
    require(config_h, "TestNoApply = true", "cloud test no-apply capability")
    require(main_cpp, "cloud_contract_version=", "cloud contract version status field")
    require(main_cpp, "cloud_event_echo_required=", "cloud event echo status field")
    require(main_cpp, "cloud_test_no_apply=", "cloud test no-apply status field")
    require(main_cpp, "cloud_test_validated=", "cloud test validation status field")
    require(main_cpp, "globalData.cloud_test_validated = true", "successful cloud test validation state")
    require(main_cpp, "setCloudTestValidated(false)", "cloud test validation invalidation")
    require(main_cpp, "applyCloudCommand", "cloud downlink command execution")
    require(main_cpp, "runtime_event_threshold = 0.0f", "runtime event threshold default override disabled")
    require(main_cpp, "effectiveEventThreshold", "runtime event threshold display/runtime helper")
    require(main_cpp, "CLOUD,APPLY", "offline cloud command apply test command")
    require(main_cpp, "CLOUD,RESET", "offline cloud command reset command")
    require(main_cpp, "DOWNGRADE_REJECTED_THREAT_ACTIVE", "edge veto for unsafe economy downgrade")
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
    require(ROOT.joinpath("include", "SharedData.h").read_text(encoding="utf-8"), "cloud_test_validated", "shared cloud test validation field")
    require(cloud_client_cpp, "http_status_not_ok", "cloud HTTP status failure reason")
    require(cloud_client_cpp, "response_json_parse_failed", "cloud response JSON failure reason")
    require(cloud_client_cpp, "assessment_json_parse_failed", "cloud assessment JSON failure reason")
    require(cloud_client_cpp, "http_request_failed", "cloud HTTP request failure reason")
    require(strict_closure, "cloud_contract_version >= 2", "strict gate cloud contract version requirement")
    require(strict_closure, "cloud_expected_event_id == expected_id", "strict gate expected cloud event requirement")
    require(strict_closure, "cloud_response_event_id == expected_id", "strict gate returned cloud event requirement")
    require(strict_closure, 'cloud_result_source == "EVENT_OPENED"', "strict gate real event source requirement")
    require(serial_bridge, '"CLOUD,RESULT"', "serial bridge cloud result monitoring")
    require(serial_bridge, '"event_id": "cloud_request_event_id"', "serial bridge cloud request event isolation")
    require(serial_bridge, '"expected_event_id": "cloud_expected_event_id"', "serial bridge expected event persistence")
    require(serial_bridge, '"response_event_id": "cloud_response_event_id"', "serial bridge returned event persistence")
    require(cloud_client_h, "response_event_id", "cloud-returned event ID result field")
    require(cloud_client_cpp, "必须原样回显输入事件中的 event_id", "cloud event ID echo prompt contract")
    require(cloud_client_cpp, "response_event_id_missing", "missing cloud event ID rejection")
    require(cloud_client_cpp, "response_event_id_mismatch", "mismatched cloud event ID rejection")
    require(cloud_client_cpp, "validateAssessmentPolicy", "cloud assessment policy enforcement")
    require(cloud_client_cpp, "test_policy_mismatch", "cloud test policy mismatch rejection")
    require(cloud_client_cpp, "high_risk_policy_mismatch", "high-risk policy mismatch rejection")
    system_prompt_start = cloud_client_cpp.find("constexpr const char *kSystemPrompt")
    system_prompt_end = cloud_client_cpp.find("struct ResponseBuffer", system_prompt_start)
    if system_prompt_start < 0 or system_prompt_end <= system_prompt_start:
        fail("cloud system prompt block missing")
    system_prompt_block = cloud_client_cpp[system_prompt_start:system_prompt_end]
    require(system_prompt_block, "TEST_POLICY", "deterministic cloud test response policy")
    require(system_prompt_block, "HIGH_RISK_POLICY", "high-risk cloud alert policy")
    require(system_prompt_block, "HIGH_RISK_FORBIDDEN", "high-risk no-action/economy prohibition")
    require(system_prompt_block, "event_id=A1-CLOUD-TEST", "cloud test event policy binding")
    require(system_prompt_block, "command.type=GENERATE_ALERT", "safe executable cloud alert command policy")
    require(cloud_client_cpp, "kAssessmentTemperature = 0.1", "low-variance cloud assessment temperature")
    require(
        cloud_client_cpp,
        'addNumber(root, "temperature", kAssessmentTemperature)',
        "cloud request temperature binding",
    )
    require(main_cpp, "cloudResponseMatchesActiveEvent", "active-event cloud response guard")
    require(main_cpp, "active_event_mismatch", "late or closed-event cloud response rejection")
    require(main_cpp, "const bool isTestRequest", "explicit cloud test request branch")
    require(main_cpp, "TEST_RESPONSE_VALIDATED", "cloud test no-apply effect")
    require(main_cpp, "cloud_test_no_apply", "cloud test no-apply audit reason")
    require(main_cpp, "CLOUD,TEST,validated=1,no_apply=1", "cloud test validation serial evidence")
    require(main_cpp, "applyCloudCommand(result, completedAt, result.response_event_id);", "cloud-returned event ID command binding")
    forbid(main_cpp, "applyCloudCommand(result, completedAt, item.event.event_id);", "locally substituted cloud event ID")
    require(main_cpp, "expected_event_id=", "cloud expected event ID serial field")
    require(main_cpp, "response_event_id=", "cloud returned event ID serial field")

    cloud_policy_block = extract_braced_block(
        cloud_client_cpp,
        "bool validateAssessmentPolicy(",
        "cloud assessment policy validator",
    )
    require(cloud_policy_block, 'strcmp(result.threat_level, "HIGH") == 0', "HIGH threat policy")
    require(cloud_policy_block, 'strcmp(result.threat_level, "CRITICAL") == 0', "CRITICAL threat policy")
    require(cloud_policy_block, 'strcmp(result.command_type, "GENERATE_ALERT") == 0', "alert command policy")
    cloud_policy_requirement_block = extract_braced_block(
        cloud_client_cpp,
        "bool isAlertPolicyRequired(",
        "cloud alert policy requirement",
    )
    for policy_marker in (
        "A1-CLOUD-TEST",
        "HIGH_RISK",
        "EVENT",
        "VISUALLY_CONFIRMED_DRONE",
    ):
        require(cloud_policy_requirement_block, policy_marker, f"cloud policy trigger {policy_marker}")

    cloud_assess_block = extract_braced_block(
        cloud_client_cpp,
        "bool CloudClient::assess(",
        "cloud assessment execution",
    )
    policy_call_index = cloud_assess_block.find("validateAssessmentPolicy(event, result)")
    event_guard_index = cloud_assess_block.find("response_event_id_mismatch")
    success_index = cloud_assess_block.find("result.ok = true")
    if not (event_guard_index >= 0 and event_guard_index < policy_call_index < success_index):
        fail("cloud policy validation is not between event echo validation and success")

    require(strict_closure, 'cloud_threat_level in {"HIGH", "CRITICAL"}', "strict gate high threat semantics")
    require(strict_closure, 'cloud_command_type == "GENERATE_ALERT"', "strict gate alert command semantics")
    require(strict_closure, 'cloud_effect == "ALERT_GENERATED"', "strict gate applied alert effect semantics")

    cloud_task_block = extract_braced_block(main_cpp, "void AiCloudTask(", "AI cloud task")
    require(main_cpp, "writeBufferedSerialLine", "single-write serial line helper")
    require(main_cpp, "emitCloudTestValidationLine", "atomic cloud test evidence line")
    require(main_cpp, "emitCloudAssessmentResultLine", "atomic cloud result evidence line")
    require(main_cpp, "emitCloudDegradedLine", "atomic cloud degraded evidence line")
    require(cloud_task_block, "emitCloudTestValidationLine(", "cloud task test evidence call")
    require(cloud_task_block, "emitCloudAssessmentResultLine(", "cloud task result evidence call")
    require(cloud_task_block, "emitCloudDegradedLine(", "cloud task degraded evidence call")
    forbid(cloud_task_block, 'Serial.print("CLOUD,TEST', "split cloud test evidence output")
    forbid(cloud_task_block, 'Serial.print("CLOUD,RESULT', "split cloud result evidence output")
    forbid(cloud_task_block, 'Serial.print("CLOUD,DEGRADED', "split cloud degraded evidence output")
    cloud_success_block = extract_braced_block(cloud_task_block, "if (ok) {", "successful cloud result branch")
    test_request_block = extract_braced_block(
        cloud_success_block,
        "if (isTestRequest) {",
        "cloud test no-apply branch",
    )
    forbid(test_request_block, "applyCloudCommand(", "cloud command execution inside test branch")
    require(test_request_block, "TEST_RESPONSE_VALIDATED", "cloud test validation effect in no-apply branch")

    cloud_test_queue_block = extract_braced_block(main_cpp, "void queueCloudTest(", "cloud test queue guard")
    require(cloud_test_queue_block, "globalData.cloud_test_validated", "cloud test already-validated guard")
    require(cloud_test_queue_block, "aiCloud.request_in_flight", "cloud test in-flight request guard")
    require(cloud_test_queue_block, "aiCloud.test_request_pending", "cloud test pending request guard")
    require(cloud_test_queue_block, "uxQueueMessagesWaiting", "cloud test pending queue guard")
    require(cloud_test_queue_block, "reason=already_validated", "cloud test idempotent skip evidence")
    require(cloud_test_queue_block, "reason=request_busy", "cloud test busy skip evidence")

    downgrade_veto_block = extract_braced_block(
        main_cpp,
        'if (!targetEnabled && strcmp(globalData.cloud_threat_level, "LOW") != 0) {',
        "unsafe economy-mode downgrade veto",
    )
    require(downgrade_veto_block, 'setCloudCommandEffectLocked(false, "DOWNGRADE_REJECTED_THREAT_ACTIVE")', "economy-mode downgrade applied=false")
    forbid(downgrade_veto_block, "setCloudCommandEffectLocked(true", "successful economy-mode downgrade after edge veto")

    parachute_block = extract_braced_block(
        main_cpp,
        'if (commandType == "TRIGGER_PARACHUTE") {',
        "parachute command branch",
    )
    require(parachute_block, 'setCloudCommandEffectLocked(false, "PARACHUTE_REJECTED_NOT_INTEGRATED")', "parachute edge veto")
    forbid(parachute_block, "setCloudCommandEffectLocked(true", "successful parachute application without hardware")
    require(ROOT.joinpath("tools", "cloud_demo_replay.py").read_text(encoding="utf-8"), "Flytotal Edge-Cloud-Edge AI Command Loop", "cloud replay evidence diagram tool")
    require(main_cpp, "HandoverFlowState", "handoff state machine enum")
    require(main_cpp, "HANDOVER_FLOW_ACTIVE", "handoff active state")
    require(main_cpp, "HANDOVER_FLOW_DONE", "handoff done state")
    require(main_cpp, "updateHandoverStateMachine", "handoff state machine updater")
    require(main_cpp, "handover_state=", "handoff state serial output")

    require(
        main_cpp,
        "ManualServoControl manualServo = {false, false, GimbalConfig::CenterPanDeg, GimbalConfig::CenterTiltDeg};",
        "servo output disabled at power-on",
    )
    reset_command_block = extract_braced_block(
        main_cpp,
        '} else if (command == "RESET") {',
        "runtime RESET command",
    )
    require(reset_command_block, "setServoEnabled(false);", "servo output disabled after RESET")
    forbid(reset_command_block, "setServoEnabled(true);", "servo output re-enabled after RESET")
    tracking_task_block = extract_braced_block(main_cpp, "void TrackingTask(", "tracking task")
    forbid(tracking_task_block, "servoPan.attach(", "direct pan-servo attach in tracking task")
    forbid(tracking_task_block, "servoTilt.attach(", "direct tilt-servo attach in tracking task")
    require(
        tracking_task_block,
        "setServoEnabled(manualServo.servo_enabled);",
        "tracking task applies the single servo output gate",
    )

    try:
        tracked_file_count = audit_git_secret_hygiene(ROOT)
    except SecretAuditError as exc:
        fail(str(exc))
    print(f"git_secret_hygiene: PASS tracked_files={tracked_file_count}")

    if args.require_compiled_secrets:
        firmware_path = args.firmware_bin
        if not firmware_path.is_absolute():
            firmware_path = ROOT / firmware_path
        try:
            compiled_secret_count = audit_compiled_secret_presence(ROOT, firmware_path)
        except SecretAuditError as exc:
            fail(str(exc))
        print(f"compiled_secrets: PASS ({compiled_secret_count}/{compiled_secret_count})")

    print("firmware_safety_checks: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
