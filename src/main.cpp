#include <Arduino.h>
#include <ESP32Servo.h>
#include <freertos/FreeRTOS.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "AppConfig.h"
#include "GimbalController.h"
#include "GimbalPredictor.h"
#include "HunterAction.h"
#include "RadarParser.h"
#include "SharedData.h"
#include "TrackManager.h"

SystemData globalData = {
    false,
    0.0f,
    0.0f,
    STATE_SCANNING,
    HUNTER_IDLE,
    RID_NONE,
    false,
    WL_UNKNOWN,
    0,
    {0},
    {0},
    {0},
    0,
    0,
    {0},
    {0},
    {0},
    {0},
    {0},
    0,
    {0, false, false, 0.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0, 0},
    0.0f,
    0u,
    0.0f,
    0.0f,
    0.0f,
    0.0f,
    0.0f,
    0.0f,
    HUNTER_IDLE,
    0,
    0,
    RISK_TRANSITION_STABLE,
    0,
    0,
    false,
    false,
    false,
    0,
    VISION_IDLE,
    false,
    false,
    AUDIO_IDLE,
    UPLINK_READY,
    false,
    {0},
    0
};
portMUX_TYPE dataMutex = portMUX_INITIALIZER_UNLOCKED;

GimbalPredictor myGimbal(GimbalConfig::PredictorKp, GimbalConfig::PredictorKd);
GimbalController myGimbalController(myGimbal);
RadarParser myRadar;
TrackManager myTrackManager;
HunterAction myHunter;
Servo servoPan;
Servo servoTilt;

namespace {
struct SimTrackInput {
    bool enabled;
    float x_mm;
    float y_mm;
    unsigned long last_update_ms;
};

struct RidIdentityPacket {
    bool valid;
    char rid_id[32];
    char device_type[16];
    char source[16];
    unsigned long packet_timestamp_ms;
    char auth_status[16];
    char whitelist_tag[16];
    int signal_strength;
    unsigned long received_ms;
};

struct WhitelistEntry {
    const char *rid_id;
    const char *owner;
    const char *label;
    bool allowed;
    unsigned long expire_time_ms;
    const char *note;
};

struct WhitelistDecision {
    WhitelistStatus status;
    bool hit;
    unsigned long expire_time_ms;
    char owner[24];
    char label[24];
    char note[40];
};

struct EventContext {
    bool active;
    uint32_t sequence;
    uint32_t track_id;
    unsigned long opened_ms;
    char event_id[32];
};

struct RuntimeEventStatus {
    bool active;
    uint32_t track_id;
    unsigned long opened_ms;
    char event_id[32];
};

struct ManualServoControl {
    bool test_mode_enabled;
    bool servo_enabled;
    float pan_deg;
    float tilt_deg;
};

struct DebugOutputControl {
    bool enabled;
    bool quiet_mode_enabled;
    unsigned long last_gimbal_ms;
    unsigned long last_data_ms;
    unsigned long last_state_ms;
    MainState last_telemetry_main_state;
    GimbalState last_telemetry_gimbal_state;
    bool telemetry_initialized;
};

struct UplinkOutputControl {
    bool enabled;
};

struct SafetyControl {
    bool safe_mode_enabled;
};

struct ServoDiagnosticControl {
    bool running;
    uint8_t step_index;
    unsigned long step_started_ms;
};

struct ServoDiagnosticStep {
    float pan_deg;
    float tilt_deg;
    unsigned long hold_ms;
    const char *name;
    const char *hint;
};

struct HandoverRequest {
    bool pending;
    unsigned long requested_ms;
    char target_node[16];
};

struct HandoverStatus {
    bool pending;
    unsigned long pending_since_ms;
    char pending_target[16];
    unsigned long last_updated_ms;
    char last_result[24];
    char last_target[16];
    char last_event_id[32];
};

struct LastEventSnapshot {
    bool valid;
    unsigned long ts;
    MainState main_state;
    RiskLevel risk_level;
    uint32_t track_id;
    bool track_active;
    bool track_confirmed;
    HunterState hunter_state;
    GimbalState gimbal_state;
    RidStatus rid_status;
    bool rid_whitelist_hit;
    WhitelistStatus wl_status;
    float risk_score;
    uint32_t trigger_flags;
    float x_mm;
    float y_mm;
    float vx_mm_s;
    float vy_mm_s;
    char event_id[32];
    char reason[24];
    char close_reason[24];
    char event_level[16];
    char event_status[16];
    char source_node[16];
    char handover_from[16];
    char handover_to[16];
};

struct SummaryStats {
    unsigned long started_ms;
    uint32_t track_active_count;
    uint32_t track_confirmed_count;
    uint32_t track_lost_count;
    uint32_t gimbal_tracking_entries;
    uint32_t gimbal_lost_entries;
    uint32_t hunter_state_changes;
    uint32_t risk_suspicious_entries;
    uint32_t risk_high_risk_entries;
    uint32_t risk_event_entries;
    uint32_t event_opened_count;
    uint32_t event_closed_count;
    uint32_t handover_queued_count;
    uint32_t handover_emitted_count;
    uint32_t handover_ignored_count;
    float max_risk_score;
    uint32_t last_track_id;
    float last_track_x_mm;
    float last_track_y_mm;
    char last_event_id[32];
};

String commandBuffer;
float runtimeKp = GimbalConfig::PredictorKp;
float runtimeKd = GimbalConfig::PredictorKd;
SimTrackInput simTrack = {false, 0.0f, 0.0f, 0};
RidIdentityPacket ridIdentity = {false, {0}, {0}, {0}, 0, {0}, {0}, 0, 0};
ManualServoControl manualServo = {false, true, GimbalConfig::CenterPanDeg, GimbalConfig::CenterTiltDeg};
DebugOutputControl debugOutput = {true, false, 0, 0, 0, MAIN_IDLE, STATE_SCANNING, false};
UplinkOutputControl uplinkOutput = {true};
SafetyControl safetyControl = {false};
ServoDiagnosticControl servoDiagnostic = {false, 0, 0};
HandoverRequest handoverRequest = {false, 0, {0}};
HandoverStatus handoverStatus = {false, 0, {0}, 0, {0}, {0}, {0}};
LastEventSnapshot lastEventSnapshot = {
    false,
    0,
    MAIN_IDLE,
    RISK_NONE,
    0,
    false,
    false,
    HUNTER_IDLE,
    STATE_SCANNING,
    RID_NONE,
    false,
    WL_UNKNOWN,
    0.0f,
    0u,
    0.0f,
    0.0f,
    0.0f,
    0.0f,
    {0},
    {0},
    {0},
    {0},
    {0},
    {0},
    {0},
    {0}
};
RuntimeEventStatus runtimeEventStatus = {false, 0, 0, {0}};
EventObject currentEventObject = {
    false,
    EVENT_STATE_NONE,
    {0},
    {0},
    {0},
    0,
    0.0f,
    RISK_NONE,
    0u,
    0u,
    RID_NONE,
    WL_UNKNOWN,
    0,
    0.0f,
    0.0f,
    0.0f,
    0.0f
};
SummaryStats summaryStats = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0f, 0, 0.0f, 0.0f, {0}};
bool servosAttached = false;
constexpr unsigned long SimTrackHoldMs = 1500;
constexpr unsigned long GimbalDebugIntervalMs = 250;
constexpr unsigned long DataDebugIntervalMs = 250;
constexpr unsigned long StateDebugIntervalMs = 250;
constexpr float SafePanMinDeg = 80.0f;
constexpr float SafePanMaxDeg = 100.0f;
constexpr float SafeTiltMinDeg = 80.0f;
constexpr float SafeTiltMaxDeg = 100.0f;
constexpr uint32_t TriggerFlagAlert = 1u << 0;
constexpr uint32_t TriggerFlagCapture = 1u << 1;
constexpr uint32_t TriggerFlagGuardian = 1u << 2;
constexpr uint32_t TriggerFlagRidMissing = 1u << 3;
constexpr uint32_t TriggerFlagRidSuspicious = 1u << 4;
constexpr uint32_t TriggerFlagEventActive = 1u << 5;
constexpr uint32_t TriggerFlagVisionLocked = 1u << 6;
constexpr uint32_t TriggerFlagCaptureReady = 1u << 7;
constexpr uint32_t TriggerFlagProximity = 1u << 8;
constexpr uint32_t TriggerFlagMotionAnomaly = 1u << 9;
constexpr uint32_t RiskReasonTrackPersistent = 1u << 0;
constexpr uint32_t RiskReasonTrackConfirmed = 1u << 1;
constexpr uint32_t RiskReasonRidMatched = 1u << 2;
constexpr uint32_t RiskReasonRidUnknown = 1u << 3;
constexpr uint32_t RiskReasonRidMissing = 1u << 4;
constexpr uint32_t RiskReasonRidSuspicious = 1u << 5;
constexpr uint32_t RiskReasonProximity = 1u << 6;
constexpr uint32_t RiskReasonMotionAnomaly = 1u << 7;
constexpr uint32_t RiskReasonAudioAnomaly = 1u << 8;
constexpr uint32_t RiskReasonVisionLocked = 1u << 9;
constexpr uint32_t RiskReasonVisionLost = 1u << 10;

constexpr WhitelistEntry RidWhitelistTable[] = {
    {"SIM-RID", "TeamA", "LegalDemo", true, 0, "默认合法演示目标"},
    {"SIM-RID-001", "LabA", "UAV-001", true, 0, "RID,MSG 合法样例"},
    {"SIM-RID-999", "LabA", "UAV-999", false, 0, "不在允许名单"},
    {"SIM-RID-EXPIRED", "LabA", "UAV-EXP", true, 1000UL, "白名单已过期样例"},
};

constexpr ServoDiagnosticStep ServoDiagnosticSteps[] = {
    {GimbalConfig::CenterPanDeg, GimbalConfig::CenterTiltDeg, 1500, "CENTER",
     "Observe center hold. If it already shakes here, suspect power, ground, or mechanical preload."},
    {85.0f, GimbalConfig::CenterTiltDeg, 1200, "PAN_LEFT_SMALL",
     "Expect a small smooth move left. If only this step shakes, inspect the left-side mechanical limit."},
    {95.0f, GimbalConfig::CenterTiltDeg, 1200, "PAN_RIGHT_SMALL",
     "Expect a small smooth move right. If only this step shakes, inspect the right-side mechanical limit."},
    {GimbalConfig::CenterPanDeg, 85.0f, 1200, "TILT_UP_SMALL",
     "Expect a small smooth tilt move. If tilt shakes but pan does not, focus on tilt linkage or tilt servo."},
    {GimbalConfig::CenterPanDeg, 95.0f, 1200, "TILT_DOWN_SMALL",
     "Expect a small smooth move the other way. Repeated shaking here often means tilt load or weak power."},
    {GimbalConfig::CenterPanDeg, GimbalConfig::CenterTiltDeg, 1500, "CENTER_END",
     "Diagnostic returns to center. If all steps were smooth, basic servo motion is likely okay."},
};

RidStatus parseRidStatus(const String &token) {
    if (token == "OK" || token == "MATCHED") {
        return RID_MATCHED;
    }
    if (token == "NONE" || token == "CLEAR" || token == "OFF") {
        return RID_NONE;
    }
    if (token == "RECEIVED") {
        return RID_RECEIVED;
    }
    if (token == "EXPIRED") {
        return RID_EXPIRED;
    }
    if (token == "INVALID") {
        return RID_INVALID;
    }
    if (token == "MISSING") {
        return RID_NONE;
    }
    if (token == "SUSPICIOUS") {
        return RID_INVALID;
    }
    return RID_NONE;
}

bool parseVisionStateToken(const String &token, VisionState &state) {
    if (token == "IDLE") {
        state = VISION_IDLE;
        return true;
    }
    if (token == "SEARCHING") {
        state = VISION_SEARCHING;
        return true;
    }
    if (token == "LOCKED") {
        state = VISION_LOCKED;
        return true;
    }
    if (token == "LOST") {
        state = VISION_LOST;
        return true;
    }
    return false;
}

bool parseAudioStateToken(const String &token, AudioState &state) {
    if (token == "IDLE") {
        state = AUDIO_IDLE;
        return true;
    }
    if (token == "NORMAL") {
        state = AUDIO_NORMAL;
        return true;
    }
    if (token == "ANOMALY") {
        state = AUDIO_ANOMALY;
        return true;
    }
    if (token == "BACKGROUND") {
        state = AUDIO_BACKGROUND;
        return true;
    }
    return false;
}
void copyRidTextField(char *destination, size_t destination_size, const String &source) {
    if (destination == nullptr || destination_size == 0) {
        return;
    }
    String trimmed = source;
    trimmed.trim();
    if (trimmed.length() == 0) {
        destination[0] = '\0';
        return;
    }
    snprintf(destination, destination_size, "%s", trimmed.c_str());
}

bool ridTokenEquals(const char *token, const char *expected_upper) {
    if (token == nullptr || expected_upper == nullptr) {
        return false;
    }
    size_t index = 0;
    while (token[index] != '\0' && expected_upper[index] != '\0') {
        char lhs = token[index];
        char rhs = expected_upper[index];
        if (lhs >= 'a' && lhs <= 'z') {
            lhs = static_cast<char>(lhs - ('a' - 'A'));
        }
        if (rhs >= 'a' && rhs <= 'z') {
            rhs = static_cast<char>(rhs - ('a' - 'A'));
        }
        if (lhs != rhs) {
            return false;
        }
        index++;
    }
    return token[index] == '\0' && expected_upper[index] == '\0';
}

const char *whitelistStatusName(WhitelistStatus status) {
    switch (status) {
        case WL_ALLOWED:
            return "WL_ALLOWED";
        case WL_DENIED:
            return "WL_DENIED";
        case WL_EXPIRED:
            return "WL_EXPIRED";
        case WL_UNKNOWN:
        default:
            return "WL_UNKNOWN";
    }
}

WhitelistDecision resolveWhitelistDecision(const RidIdentityPacket &packet, unsigned long now) {
    WhitelistDecision decision = {WL_UNKNOWN, false, 0, {0}, {0}, {0}};
    snprintf(decision.owner, sizeof(decision.owner), "%s", "NONE");
    snprintf(decision.label, sizeof(decision.label), "%s", "NONE");
    snprintf(decision.note, sizeof(decision.note), "%s", "RID 不在白名单配置中");

    if (!packet.valid || packet.rid_id[0] == '\0') {
        return decision;
    }

    for (const WhitelistEntry &entry : RidWhitelistTable) {
        if (!ridTokenEquals(packet.rid_id, entry.rid_id)) {
            continue;
        }

        snprintf(decision.owner, sizeof(decision.owner), "%s", entry.owner != nullptr ? entry.owner : "NONE");
        snprintf(decision.label, sizeof(decision.label), "%s", entry.label != nullptr ? entry.label : "NONE");
        snprintf(decision.note, sizeof(decision.note), "%s", entry.note != nullptr ? entry.note : "NONE");
        decision.expire_time_ms = entry.expire_time_ms;

        if (!entry.allowed) {
            decision.status = WL_DENIED;
            decision.hit = false;
            return decision;
        }

        if (entry.expire_time_ms > 0 && now >= entry.expire_time_ms) {
            decision.status = WL_EXPIRED;
            decision.hit = false;
            return decision;
        }

        decision.status = WL_ALLOWED;
        decision.hit = true;
        return decision;
    }

    return decision;
}

bool parseRidMessagePayload(const String &payload, RidIdentityPacket &packet, unsigned long now) {
    String tokens[8];
    size_t token_count = 0;
    int start = 0;
    while (start <= payload.length() && token_count < 8) {
        int comma = payload.indexOf(',', start);
        String token = comma >= 0 ? payload.substring(start, comma) : payload.substring(start);
        token.trim();
        tokens[token_count++] = token;
        if (comma < 0) {
            break;
        }
        start = comma + 1;
    }

    if (token_count < 6) {
        return false;
    }

    packet.valid = true;
    copyRidTextField(packet.rid_id, sizeof(packet.rid_id), tokens[0]);
    copyRidTextField(packet.device_type, sizeof(packet.device_type), tokens[1]);
    copyRidTextField(packet.source, sizeof(packet.source), tokens[2]);
    packet.packet_timestamp_ms = static_cast<unsigned long>(strtoul(tokens[3].c_str(), nullptr, 10));
    copyRidTextField(packet.auth_status, sizeof(packet.auth_status), tokens[4]);
    copyRidTextField(packet.whitelist_tag, sizeof(packet.whitelist_tag), tokens[5]);
    packet.signal_strength = token_count >= 7 ? static_cast<int>(strtol(tokens[6].c_str(), nullptr, 10)) : 0;
    packet.received_ms = now;
    return true;
}

bool isRidAuthValid(const RidIdentityPacket &packet) {
    return ridTokenEquals(packet.auth_status, "OK") ||
           ridTokenEquals(packet.auth_status, "VALID") ||
           ridTokenEquals(packet.auth_status, "PASS") ||
           ridTokenEquals(packet.auth_status, "PASSED") ||
           ridTokenEquals(packet.auth_status, "AUTH_OK");
}

bool isRidWhitelistHit(const RidIdentityPacket &packet) {
    return ridTokenEquals(packet.whitelist_tag, "1") ||
           ridTokenEquals(packet.whitelist_tag, "YES") ||
           ridTokenEquals(packet.whitelist_tag, "TRUE") ||
           ridTokenEquals(packet.whitelist_tag, "OK") ||
           ridTokenEquals(packet.whitelist_tag, "ALLOW") ||
           ridTokenEquals(packet.whitelist_tag, "ALLOWED") ||
           ridTokenEquals(packet.whitelist_tag, "WL_OK") ||
           ridTokenEquals(packet.whitelist_tag, "WHITELIST");
}

void clearRidIdentityPacket(unsigned long now) {
    portENTER_CRITICAL(&dataMutex);
    ridIdentity.valid = false;
    ridIdentity.rid_id[0] = '\0';
    ridIdentity.device_type[0] = '\0';
    ridIdentity.source[0] = '\0';
    ridIdentity.packet_timestamp_ms = 0;
    ridIdentity.auth_status[0] = '\0';
    ridIdentity.whitelist_tag[0] = '\0';
    ridIdentity.signal_strength = 0;
    ridIdentity.received_ms = 0;

    globalData.rid_status = RID_NONE;
    globalData.rid_whitelist_hit = false;
    globalData.wl_status = WL_UNKNOWN;
    globalData.wl_expire_time_ms = 0;
    globalData.wl_owner[0] = '\0';
    globalData.wl_label[0] = '\0';
    globalData.wl_note[0] = '\0';
    globalData.rid_last_update_ms = now;
    globalData.rid_last_match_ms = 0;
    globalData.rid_id[0] = '\0';
    globalData.rid_device_type[0] = '\0';
    globalData.rid_source[0] = '\0';
    globalData.rid_auth_status[0] = '\0';
    globalData.rid_whitelist_tag[0] = '\0';
    globalData.rid_signal_strength = 0;
    portEXIT_CRITICAL(&dataMutex);
}

void setRidIdentityPacket(const RidIdentityPacket &packet) {
    portENTER_CRITICAL(&dataMutex);
    ridIdentity = packet;
    portEXIT_CRITICAL(&dataMutex);
}

RidStatus refreshRidRuntime(const RadarTrack &track, unsigned long now) {
    RidIdentityPacket packet = {};
    unsigned long previous_match_ms = 0;
    WhitelistStatus previous_wl_status = WL_UNKNOWN;
    unsigned long previous_wl_expire_time_ms = 0;
    char previous_wl_owner[24] = {0};
    char previous_wl_label[24] = {0};
    char previous_wl_note[40] = {0};

    portENTER_CRITICAL(&dataMutex);
    packet = ridIdentity;
    previous_match_ms = globalData.rid_last_match_ms;
    previous_wl_status = globalData.wl_status;
    previous_wl_expire_time_ms = globalData.wl_expire_time_ms;
    snprintf(previous_wl_owner, sizeof(previous_wl_owner), "%s", globalData.wl_owner);
    snprintf(previous_wl_label, sizeof(previous_wl_label), "%s", globalData.wl_label);
    snprintf(previous_wl_note, sizeof(previous_wl_note), "%s", globalData.wl_note);
    portEXIT_CRITICAL(&dataMutex);

    RidStatus rid_status = RID_NONE;
    bool whitelist_hit = false;
    WhitelistStatus wl_status = WL_UNKNOWN;
    unsigned long wl_expire_time_ms = 0;
    char wl_owner[24] = {0};
    char wl_label[24] = {0};
    char wl_note[40] = {0};
    unsigned long last_update_ms = 0;
    unsigned long last_match_ms = previous_match_ms;

    snprintf(wl_owner, sizeof(wl_owner), "%s", "NONE");
    snprintf(wl_label, sizeof(wl_label), "%s", "NONE");
    snprintf(wl_note, sizeof(wl_note), "%s", "NONE");

    if (packet.valid) {
        WhitelistDecision decision = resolveWhitelistDecision(packet, now);
        const bool auth_valid = isRidAuthValid(packet);
        wl_status = decision.status;
        wl_expire_time_ms = decision.expire_time_ms;
        snprintf(wl_owner, sizeof(wl_owner), "%s", decision.owner[0] != '\0' ? decision.owner : "NONE");
        snprintf(wl_label, sizeof(wl_label), "%s", decision.label[0] != '\0' ? decision.label : "NONE");
        snprintf(wl_note, sizeof(wl_note), "%s", decision.note[0] != '\0' ? decision.note : "NONE");
        whitelist_hit = decision.hit;
        last_update_ms = packet.received_ms;
        const bool timed_out = packet.received_ms == 0 || (now - packet.received_ms) > RidConfig::ReceiveTimeoutMs;
        const bool has_previous_match = previous_match_ms > 0 && now >= previous_match_ms;
        const unsigned long since_last_match_ms = has_previous_match ? (now - previous_match_ms) : 0;
        const bool in_legal_hold = wl_status == WL_ALLOWED &&
                                   has_previous_match &&
                                   since_last_match_ms <= RidConfig::LegalHoldMs;
        const bool in_reconfirm_window = wl_status == WL_ALLOWED &&
                                         has_previous_match &&
                                         since_last_match_ms <= (RidConfig::LegalHoldMs + RidConfig::ReconfirmWindowMs);

        if (!auth_valid) {
            rid_status = RID_INVALID;
            whitelist_hit = false;
        } else if (wl_status == WL_DENIED) {
            rid_status = RID_INVALID;
            whitelist_hit = false;
        } else if (wl_status == WL_EXPIRED) {
            rid_status = RID_EXPIRED;
            whitelist_hit = false;
        } else if (timed_out) {
            if (track.is_active && in_legal_hold) {
                rid_status = RID_MATCHED;
                whitelist_hit = true;
            } else if (track.is_active && in_reconfirm_window) {
                rid_status = RID_RECEIVED;
                whitelist_hit = true;
            } else {
                rid_status = RID_EXPIRED;
                whitelist_hit = false;
            }
        } else if (wl_status == WL_ALLOWED && track.is_active && (now - packet.received_ms) <= RidConfig::MatchWindowMs) {
            rid_status = RID_MATCHED;
            last_match_ms = now;
            whitelist_hit = true;
        } else if (wl_status == WL_ALLOWED) {
            rid_status = RID_RECEIVED;
            whitelist_hit = true;
        } else if (wl_status == WL_UNKNOWN) {
            rid_status = RID_INVALID;
            whitelist_hit = false;
        } else {
            rid_status = RID_RECEIVED;
            whitelist_hit = false;
        }
    } else {
        const bool has_previous_match = previous_match_ms > 0 && now >= previous_match_ms;
        const unsigned long since_last_match_ms = has_previous_match ? (now - previous_match_ms) : 0;
        if (track.is_active && previous_wl_status == WL_ALLOWED && has_previous_match) {
            wl_status = WL_ALLOWED;
            wl_expire_time_ms = previous_wl_expire_time_ms;
            snprintf(wl_owner, sizeof(wl_owner), "%s", previous_wl_owner[0] != '\0' ? previous_wl_owner : "NONE");
            snprintf(wl_label, sizeof(wl_label), "%s", previous_wl_label[0] != '\0' ? previous_wl_label : "NONE");
            snprintf(wl_note, sizeof(wl_note), "%s", previous_wl_note[0] != '\0' ? previous_wl_note : "NONE");
            if (since_last_match_ms <= RidConfig::LegalHoldMs) {
                rid_status = RID_MATCHED;
                whitelist_hit = true;
            } else if (since_last_match_ms <= (RidConfig::LegalHoldMs + RidConfig::ReconfirmWindowMs)) {
                rid_status = RID_RECEIVED;
                whitelist_hit = true;
            } else {
                rid_status = RID_NONE;
                wl_status = WL_UNKNOWN;
                wl_expire_time_ms = 0;
                snprintf(wl_owner, sizeof(wl_owner), "%s", "NONE");
                snprintf(wl_label, sizeof(wl_label), "%s", "NONE");
                snprintf(wl_note, sizeof(wl_note), "%s", "NONE");
                whitelist_hit = false;
            }
        } else if (track.is_active) {
            rid_status = RID_NONE;
            wl_status = WL_UNKNOWN;
            whitelist_hit = false;
        }
    }

    portENTER_CRITICAL(&dataMutex);
    globalData.rid_status = rid_status;
    globalData.rid_whitelist_hit = whitelist_hit;
    globalData.wl_status = wl_status;
    globalData.wl_expire_time_ms = wl_expire_time_ms;
    snprintf(globalData.wl_owner, sizeof(globalData.wl_owner), "%s", wl_owner);
    snprintf(globalData.wl_label, sizeof(globalData.wl_label), "%s", wl_label);
    snprintf(globalData.wl_note, sizeof(globalData.wl_note), "%s", wl_note);
    globalData.rid_last_update_ms = last_update_ms;
    globalData.rid_last_match_ms = last_match_ms;
    if (packet.valid) {
        snprintf(globalData.rid_id, sizeof(globalData.rid_id), "%s", packet.rid_id);
        snprintf(globalData.rid_device_type, sizeof(globalData.rid_device_type), "%s", packet.device_type);
        snprintf(globalData.rid_source, sizeof(globalData.rid_source), "%s", packet.source);
        snprintf(globalData.rid_auth_status, sizeof(globalData.rid_auth_status), "%s", packet.auth_status);
        snprintf(globalData.rid_whitelist_tag, sizeof(globalData.rid_whitelist_tag), "%s", packet.whitelist_tag);
        globalData.rid_signal_strength = packet.signal_strength;
    } else {
        globalData.rid_id[0] = '\0';
        globalData.rid_device_type[0] = '\0';
        globalData.rid_source[0] = '\0';
        globalData.rid_auth_status[0] = '\0';
        globalData.rid_whitelist_tag[0] = '\0';
        globalData.rid_signal_strength = 0;
    }
    portEXIT_CRITICAL(&dataMutex);
    return rid_status;
}

const char *hunterStateName(HunterState state) {
    switch (state) {
        case HUNTER_IDLE:
            return "IDLE";
        case HUNTER_TRACKING:
            return "TRACKING";
        case HUNTER_RID_MATCHED:
            return "RID_MATCHED";
        case HUNTER_SUSPICIOUS:
            return "SUSPICIOUS";
        case HUNTER_HIGH_RISK:
            return "HIGH_RISK";
        case HUNTER_EVENT_LOCKED:
            return "EVENT_LOCKED";
        default:
            return "UNKNOWN";
    }
}

const char *gimbalStateName(GimbalState state) {
    switch (state) {
        case STATE_SCANNING:
            return "SCANNING";
        case STATE_ACQUIRING:
            return "ACQUIRING";
        case STATE_TRACKING:
            return "TRACKING";
        case STATE_LOST:
            return "LOST";
        default:
            return "UNKNOWN";
    }
}

const char *ridStateName(RidStatus status) {
    switch (status) {
        case RID_NONE:
            return "NONE";
        case RID_RECEIVED:
            return "RECEIVED";
        case RID_MATCHED:
            return "MATCHED";
        case RID_EXPIRED:
            return "EXPIRED";
        case RID_INVALID:
            return "INVALID";
        default:
            return "NONE";
    }
}

const char *visionStateName(VisionState state) {
    switch (state) {
        case VISION_IDLE:
            return "VISION_IDLE";
        case VISION_SEARCHING:
            return "VISION_SEARCHING";
        case VISION_LOCKED:
            return "VISION_LOCKED";
        case VISION_LOST:
            return "VISION_LOST";
        default:
            return "VISION_UNKNOWN";
    }
}

const char *audioStateName(AudioState state) {
    switch (state) {
        case AUDIO_IDLE:
            return "AUDIO_IDLE";
        case AUDIO_NORMAL:
            return "AUDIO_NORMAL";
        case AUDIO_ANOMALY:
            return "AUDIO_ANOMALY";
        case AUDIO_BACKGROUND:
            return "AUDIO_BACKGROUND";
        default:
            return "AUDIO_UNKNOWN";
    }
}

const char *uplinkStateName(UplinkState state) {
    switch (state) {
        case UPLINK_IDLE:
            return "UPLINK_IDLE";
        case UPLINK_READY:
            return "UPLINK_READY";
        case UPLINK_SENDING:
            return "UPLINK_SENDING";
        case UPLINK_OK:
            return "UPLINK_OK";
        case UPLINK_FAIL:
            return "UPLINK_FAIL";
        default:
            return "UPLINK_UNKNOWN";
    }
}

const char *mainStateName(MainState state) {
    switch (state) {
        case MAIN_IDLE:
            return "IDLE";
        case MAIN_DETECTING:
            return "DETECTING";
        case MAIN_TRACKING:
            return "TRACKING";
        case MAIN_SUSPICIOUS:
            return "SUSPICIOUS";
        case MAIN_HIGH_RISK:
            return "HIGH_RISK";
        case MAIN_EVENT:
            return "EVENT";
        case MAIN_LOST:
            return "LOST";
        default:
            return "UNKNOWN";
    }
}

const char *riskLevelName(RiskLevel level) {
    switch (level) {
        case RISK_NONE:
            return "NONE";
        case RISK_NORMAL:
            return "NORMAL";
        case RISK_SUSPICIOUS:
            return "SUSPICIOUS";
        case RISK_HIGH_RISK:
            return "HIGH_RISK";
        case RISK_EVENT:
            return "EVENT";
        default:
            return "UNKNOWN";
    }
}

const char *riskTransitionModeName(RiskTransitionMode mode) {
    switch (mode) {
        case RISK_TRANSITION_ENTER_HOLD:
            return "ENTER_HOLD";
        case RISK_TRANSITION_EXIT_HOLD:
            return "EXIT_HOLD";
        case RISK_TRANSITION_STABLE:
        default:
            return "STABLE";
    }
}

const char *eventStateName(EventState state) {
    switch (state) {
        case EVENT_STATE_OPEN:
            return "OPEN";
        case EVENT_STATE_CLOSED:
            return "CLOSED";
        case EVENT_STATE_NONE:
        default:
            return "NONE";
    }
}

MainState deriveMainState(const SystemData &snapshot) {
    if (!snapshot.radar_track.is_active) {
        return snapshot.gimbal_state == STATE_LOST ? MAIN_LOST : MAIN_IDLE;
    }

    if (!snapshot.radar_track.is_confirmed) {
        return MAIN_DETECTING;
    }

    switch (snapshot.hunter_state) {
        case HUNTER_SUSPICIOUS:
            return MAIN_SUSPICIOUS;
        case HUNTER_HIGH_RISK:
            return MAIN_HIGH_RISK;
        case HUNTER_EVENT_LOCKED:
            return MAIN_EVENT;
        case HUNTER_IDLE:
        case HUNTER_TRACKING:
        case HUNTER_RID_MATCHED:
        default:
            return MAIN_TRACKING;
    }
}

RiskLevel deriveRiskLevel(const SystemData &snapshot) {
    if (!snapshot.radar_track.is_active) {
        return RISK_NONE;
    }

    if (snapshot.hunter_state == HUNTER_EVENT_LOCKED || snapshot.risk_score >= HunterConfig::EventThreshold) {
        return RISK_EVENT;
    }

    if (snapshot.hunter_state == HUNTER_HIGH_RISK || snapshot.risk_score >= HunterConfig::HighRiskThreshold) {
        return RISK_HIGH_RISK;
    }

    if (snapshot.hunter_state == HUNTER_SUSPICIOUS ||
        snapshot.risk_score >= HunterConfig::SuspiciousThreshold ||
        snapshot.rid_status == RID_NONE ||
        snapshot.rid_status == RID_EXPIRED ||
        snapshot.rid_status == RID_INVALID) {
        return RISK_SUSPICIOUS;
    }

    return RISK_NORMAL;
}

const char *mainStateName(const SystemData &snapshot) {
    return mainStateName(deriveMainState(snapshot));
}

const char *riskLevelName(const SystemData &snapshot) {
    return riskLevelName(deriveRiskLevel(snapshot));
}

uint32_t computeTriggerFlags(const SystemData &snapshot) {
    uint32_t flags = 0;

    if (snapshot.trigger_alert) {
        flags |= TriggerFlagAlert;
    }
    if (snapshot.trigger_capture) {
        flags |= TriggerFlagCapture;
    }
    if (snapshot.trigger_guardian) {
        flags |= TriggerFlagGuardian;
    }
    if (snapshot.rid_status == RID_NONE || snapshot.rid_status == RID_EXPIRED) {
        flags |= TriggerFlagRidMissing;
    }
    if (snapshot.rid_status == RID_INVALID) {
        flags |= TriggerFlagRidSuspicious;
    }
    if (snapshot.event_active) {
        flags |= TriggerFlagEventActive;
    }
    if (snapshot.vision_locked) {
        flags |= TriggerFlagVisionLocked;
    }
    if (snapshot.capture_ready) {
        flags |= TriggerFlagCaptureReady;
    }
    if (snapshot.risk_reason_flags & RiskReasonProximity) {
        flags |= TriggerFlagProximity;
    }
    if (snapshot.risk_reason_flags & RiskReasonMotionAnomaly) {
        flags |= TriggerFlagMotionAnomaly;
    }

    return flags;
}

void printTriggerFlags(uint32_t flags) {
    if (flags == 0) {
        Serial.print("NONE");
        return;
    }

    bool first = true;
    auto print_flag = [&](const char *name) {
        if (!first) {
            Serial.print("|");
        }
        Serial.print(name);
        first = false;
    };

    if (flags & TriggerFlagAlert) {
        print_flag("ALERT");
    }
    if (flags & TriggerFlagCapture) {
        print_flag("CAPTURE");
    }
    if (flags & TriggerFlagGuardian) {
        print_flag("GUARDIAN");
    }
    if (flags & TriggerFlagRidMissing) {
        print_flag("RID_MISSING");
    }
    if (flags & TriggerFlagRidSuspicious) {
        print_flag("RID_SUSPICIOUS");
    }
    if (flags & TriggerFlagEventActive) {
        print_flag("EVENT_ACTIVE");
    }
    if (flags & TriggerFlagVisionLocked) {
        print_flag("VISION_LOCKED");
    }
    if (flags & TriggerFlagCaptureReady) {
        print_flag("CAPTURE_READY");
    }
    if (flags & TriggerFlagProximity) {
        print_flag("PROXIMITY");
    }
    if (flags & TriggerFlagMotionAnomaly) {
        print_flag("MOTION_ANOMALY");
    }
}

void printEventTriggerReasonFlags(uint32_t flags) {
    const uint32_t reason_mask = TriggerFlagRidMissing |
                                 TriggerFlagRidSuspicious |
                                 TriggerFlagProximity |
                                 TriggerFlagMotionAnomaly |
                                 TriggerFlagAlert |
                                 TriggerFlagCapture;

    if ((flags & reason_mask) == 0) {
        Serial.print("NONE");
        return;
    }

    bool first = true;
    auto print_flag = [&](const char *name) {
        if (!first) {
            Serial.print("|");
        }
        Serial.print(name);
        first = false;
    };

    if (flags & TriggerFlagRidMissing) {
        print_flag("RID_MISSING");
    }
    if (flags & TriggerFlagRidSuspicious) {
        print_flag("RID_SUSPICIOUS");
    }
    if (flags & TriggerFlagProximity) {
        print_flag("PROXIMITY");
    }
    if (flags & TriggerFlagMotionAnomaly) {
        print_flag("MOTION_ANOMALY");
    }
    if (flags & TriggerFlagAlert) {
        print_flag("ALERT");
    }
    if (flags & TriggerFlagCapture) {
        print_flag("CAPTURE");
    }
}

void printRiskReasonFlags(uint32_t flags) {
    if (flags == 0) {
        Serial.print("NONE");
        return;
    }

    bool first = true;
    auto print_flag = [&](const char *name) {
        if (!first) {
            Serial.print("|");
        }
        Serial.print(name);
        first = false;
    };

    if (flags & RiskReasonTrackPersistent) {
        print_flag("TRACK_PERSISTENT");
    }
    if (flags & RiskReasonTrackConfirmed) {
        print_flag("TRACK_CONFIRMED");
    }
    if (flags & RiskReasonRidMatched) {
        print_flag("RID_MATCHED");
    }
    if (flags & RiskReasonRidUnknown) {
        print_flag("RID_RECEIVED");
    }
    if (flags & RiskReasonRidMissing) {
        print_flag("RID_NONE_OR_EXPIRED");
    }
    if (flags & RiskReasonRidSuspicious) {
        print_flag("RID_INVALID");
    }
    if (flags & RiskReasonProximity) {
        print_flag("PROXIMITY");
    }
    if (flags & RiskReasonMotionAnomaly) {
        print_flag("MOTION_ANOMALY");
    }
    if (flags & RiskReasonAudioAnomaly) {
        print_flag("AUDIO_ANOMALY");
    }
    if (flags & RiskReasonVisionLocked) {
        print_flag("VISION_LOCKED");
    }
    if (flags & RiskReasonVisionLost) {
        print_flag("VISION_LOST");
    }
}

bool parseTrackCoordinates(const String &value, float &x_mm, float &y_mm) {
    int comma = value.indexOf(',');
    if (comma < 0) {
        return false;
    }

    String xToken = value.substring(0, comma);
    String yToken = value.substring(comma + 1);
    xToken.trim();
    yToken.trim();

    if (xToken.length() == 0 || yToken.length() == 0) {
        return false;
    }

    x_mm = xToken.toFloat();
    y_mm = yToken.toFloat();
    return true;
}

void computeCoarseAimAngles(float x_mm, float y_mm, float &pan_deg, float &tilt_deg) {
    pan_deg = myGimbal.calculateFiringAngle(x_mm, y_mm);
    tilt_deg = map(
        static_cast<long>(y_mm),
        GimbalConfig::MinTiltMapInputMm,
        GimbalConfig::MaxTiltMapInputMm,
        GimbalConfig::MinTiltDeg,
        GimbalConfig::MaxTiltDeg
    );
    tilt_deg = constrain(
        tilt_deg,
        static_cast<float>(GimbalConfig::MinTiltDeg),
        static_cast<float>(GimbalConfig::MaxTiltDeg)
    );
}

float clampPanAngle(float angle_deg) {
    float min_pan = safetyControl.safe_mode_enabled ? SafePanMinDeg : GimbalConfig::MinPanDeg;
    float max_pan = safetyControl.safe_mode_enabled ? SafePanMaxDeg : GimbalConfig::MaxPanDeg;
    return constrain(angle_deg, min_pan, max_pan);
}

float clampTiltAngle(float angle_deg) {
    float min_tilt = safetyControl.safe_mode_enabled ? SafeTiltMinDeg : static_cast<float>(GimbalConfig::MinTiltDeg);
    float max_tilt = safetyControl.safe_mode_enabled ? SafeTiltMaxDeg : static_cast<float>(GimbalConfig::MaxTiltDeg);
    return constrain(
        angle_deg,
        min_tilt,
        max_tilt
    );
}

bool parseAngleValue(const String &value, float &angle_deg) {
    if (value.length() == 0) {
        return false;
    }

    char *end_ptr = nullptr;
    angle_deg = strtof(value.c_str(), &end_ptr);
    return end_ptr != value.c_str() && *end_ptr == '\0';
}

void attachServosIfNeeded() {
    if (servosAttached) {
        return;
    }

    servoPan.setPeriodHertz(ServoConfig::PwmFrequencyHz);
    servoTilt.setPeriodHertz(ServoConfig::PwmFrequencyHz);
    servoPan.attach(ServoConfig::PanPin, ServoConfig::PulseMinUs, ServoConfig::PulseMaxUs);
    servoTilt.attach(ServoConfig::TiltPin, ServoConfig::PulseMinUs, ServoConfig::PulseMaxUs);
    servosAttached = true;
}

void detachServosIfNeeded() {
    if (!servosAttached) {
        return;
    }

    servoPan.detach();
    servoTilt.detach();
    servosAttached = false;
}

void setServoEnabled(bool enabled) {
    manualServo.servo_enabled = enabled;
    if (enabled) {
        attachServosIfNeeded();
    } else {
        detachServosIfNeeded();
    }
}

void setManualServoAngles(float pan_deg, float tilt_deg) {
    manualServo.pan_deg = clampPanAngle(pan_deg);
    manualServo.tilt_deg = clampTiltAngle(tilt_deg);
}

void setSafeMode(bool enabled) {
    safetyControl.safe_mode_enabled = enabled;
    setManualServoAngles(manualServo.pan_deg, manualServo.tilt_deg);
}

void stopServoDiagnostic(const char *message) {
    if (!servoDiagnostic.running) {
        return;
    }

    servoDiagnostic.running = false;
    servoDiagnostic.step_index = 0;
    servoDiagnostic.step_started_ms = 0;
    if (message != nullptr) {
        Serial.println(message);
    }
}

void printServoDiagnosticStep() {
    const ServoDiagnosticStep &step = ServoDiagnosticSteps[servoDiagnostic.step_index];
    Serial.print("DIAG,SERVO,step=");
    Serial.print(servoDiagnostic.step_index + 1);
    Serial.print("/");
    Serial.print(sizeof(ServoDiagnosticSteps) / sizeof(ServoDiagnosticSteps[0]));
    Serial.print(",name=");
    Serial.print(step.name);
    Serial.print(",pan=");
    Serial.print(manualServo.pan_deg, 1);
    Serial.print(",tilt=");
    Serial.print(manualServo.tilt_deg, 1);
    Serial.print(",safe_mode=");
    Serial.println(safetyControl.safe_mode_enabled ? 1 : 0);
    Serial.print("DIAG,SERVO,HINT,");
    Serial.println(step.hint);
}

void applyServoDiagnosticStep(unsigned long now) {
    const ServoDiagnosticStep &step = ServoDiagnosticSteps[servoDiagnostic.step_index];
    setManualServoAngles(step.pan_deg, step.tilt_deg);
    servoDiagnostic.step_started_ms = now;
    printServoDiagnosticStep();
}

void startServoDiagnostic(unsigned long now) {
    setSafeMode(true);
    setServoEnabled(true);
    manualServo.test_mode_enabled = true;
    servoDiagnostic.running = true;
    servoDiagnostic.step_index = 0;
    Serial.println("Servo guided diagnostic started. Use DIAG,STOP to abort if shaking becomes unsafe.");
    applyServoDiagnosticStep(now);
}

void processServoDiagnostic(unsigned long now) {
    if (!servoDiagnostic.running) {
        return;
    }

    const ServoDiagnosticStep &step = ServoDiagnosticSteps[servoDiagnostic.step_index];
    if (now - servoDiagnostic.step_started_ms < step.hold_ms) {
        return;
    }

    servoDiagnostic.step_index++;
    if (servoDiagnostic.step_index >= (sizeof(ServoDiagnosticSteps) / sizeof(ServoDiagnosticSteps[0]))) {
        servoDiagnostic.running = false;
        servoDiagnostic.step_index = 0;
        servoDiagnostic.step_started_ms = 0;
        setManualServoAngles(GimbalConfig::CenterPanDeg, GimbalConfig::CenterTiltDeg);
        Serial.println("DIAG,SERVO,COMPLETE,Servo diagnostic finished. If shaking appeared in every step, suspect power, grounding, or pulse range.");
        Serial.println("DIAG,SERVO,COMPLETE,Use TESTMODE,OFF to resume automatic control when ready.");
        return;
    }

    applyServoDiagnosticStep(now);
}

void setSimTrack(float x_mm, float y_mm) {
    portENTER_CRITICAL(&dataMutex);
    simTrack.enabled = true;
    simTrack.x_mm = x_mm;
    simTrack.y_mm = y_mm;
    simTrack.last_update_ms = millis();
    portEXIT_CRITICAL(&dataMutex);
}

void clearSimTrack() {
    portENTER_CRITICAL(&dataMutex);
    simTrack.enabled = false;
    simTrack.x_mm = 0.0f;
    simTrack.y_mm = 0.0f;
    simTrack.last_update_ms = 0;
    portEXIT_CRITICAL(&dataMutex);
}

bool getSimTrackSnapshot(SimTrackInput &snapshot) {
    portENTER_CRITICAL(&dataMutex);
    snapshot = simTrack;
    portEXIT_CRITICAL(&dataMutex);
    return snapshot.enabled;
}

bool isSimTrackActive(const SimTrackInput &snapshot, unsigned long now) {
    return snapshot.enabled && (now - snapshot.last_update_ms <= SimTrackHoldMs);
}

bool isEventEligible(const SystemData &snapshot, unsigned long now) {
    if (!snapshot.radar_track.is_active || !snapshot.radar_track.is_confirmed) {
        return false;
    }

    // Keep no-RID short entries in warning/tracking flow first; avoid immediate eventization.
    if (snapshot.rid_status == RID_NONE || snapshot.rid_status == RID_EXPIRED) {
        unsigned long track_alive_ms = now - snapshot.radar_track.first_seen_ms;
        if (track_alive_ms < EventConfig::MissingRidEventMinDurationMs) {
            return false;
        }
    }

    RiskLevel level = deriveRiskLevel(snapshot);
    return level == RISK_SUSPICIOUS || level == RISK_HIGH_RISK || level == RISK_EVENT;
}

bool hasEventContext(const EventContext &context) {
    return context.active && context.event_id[0] != '\0';
}

void closeEventContext(EventContext &context) {
    context.active = false;
    context.track_id = 0;
    context.opened_ms = 0;
    context.event_id[0] = '\0';
}

void ensureEventContext(const SystemData &snapshot, unsigned long now, EventContext &context) {
    if (!isEventEligible(snapshot, now)) {
        return;
    }

    if (context.active && context.track_id == snapshot.radar_track.track_id) {
        return;
    }

    context.sequence++;
    context.active = true;
    context.track_id = snapshot.radar_track.track_id;
    context.opened_ms = now;
    snprintf(
        context.event_id,
        sizeof(context.event_id),
        "%s-%010lu-%04lu",
        NodeConfig::NodeId,
        static_cast<unsigned long>(now),
        static_cast<unsigned long>(context.sequence)
    );
}

void printEventContextFields(const EventContext &context) {
    if (!hasEventContext(context)) {
        return;
    }

    Serial.print(",event_id=");
    Serial.print(context.event_id);
    Serial.print(",source_node=");
    Serial.print(NodeConfig::NodeId);
}

void printHandoverFields(const char *target_node) {
    if (target_node == nullptr || target_node[0] == '\0') {
        return;
    }

    Serial.print(",handover_from=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",handover_to=");
    Serial.print(target_node);
}

const char *eventLevelForSnapshot(const SystemData &snapshot, const char *reason) {
    if (strcmp(reason, "HANDOVER") == 0) {
        return "INFO";
    }

    if (strcmp(reason, "EVENT_OPENED") == 0) {
        RiskLevel level = deriveRiskLevel(snapshot);
        if (level == RISK_HIGH_RISK || level == RISK_EVENT) {
            return "CRITICAL";
        }
        if (level == RISK_SUSPICIOUS) {
            return "WARN";
        }
        return "INFO";
    }

    if (strcmp(reason, "EVENT_CLOSED") == 0) {
        return "INFO";
    }

    if (strcmp(reason, "HUNTER_STATE") == 0) {
        if (snapshot.hunter_state == HUNTER_HIGH_RISK || snapshot.hunter_state == HUNTER_EVENT_LOCKED) {
            return "CRITICAL";
        }
        if (snapshot.hunter_state == HUNTER_SUSPICIOUS) {
            return "WARN";
        }
        return "INFO";
    }

    if (strcmp(reason, "RID_STATE") == 0) {
        if (snapshot.rid_status == RID_NONE ||
            snapshot.rid_status == RID_EXPIRED ||
            snapshot.rid_status == RID_INVALID) {
            return "WARN";
        }
        return "INFO";
    }

    if (strcmp(reason, "TRACK_ACTIVE") == 0 ||
        strcmp(reason, "TRACK_CHANGED") == 0 ||
        strcmp(reason, "TRACK_LOST") == 0) {
        return "INFO";
    }

    return "INFO";
}

const char *eventStatusForSnapshot(const SystemData &snapshot, const char *reason) {
    if (strcmp(reason, "HANDOVER") == 0) {
        return "OPEN";
    }

    if (strcmp(reason, "EVENT_CLOSED") == 0) {
        return "CLOSED";
    }

    if (strcmp(reason, "TRACK_LOST") == 0 || !snapshot.radar_track.is_active) {
        return "CLOSED";
    }

    return "OPEN";
}

void copyEventId(char *destination, size_t destination_size, const char *source) {
    if (destination_size == 0) {
        return;
    }

    if (source == nullptr || source[0] == '\0') {
        destination[0] = '\0';
        return;
    }

    snprintf(destination, destination_size, "%s", source);
}

bool isTerminalEventCloseReason(const char *close_reason);

EventContext buildEventContextFromRuntimeStatus(const RuntimeEventStatus &status) {
    EventContext context = {false, 0, 0, 0, {0}};
    if (!status.active || status.event_id[0] == '\0') {
        return context;
    }

    context.active = true;
    context.track_id = status.track_id;
    context.opened_ms = status.opened_ms;
    copyEventId(context.event_id, sizeof(context.event_id), status.event_id);
    return context;
}

void resetRuntimeEventStatus(const char *close_reason = nullptr) {
    portENTER_CRITICAL(&dataMutex);
    bool had_event_context =
        (runtimeEventStatus.active && runtimeEventStatus.event_id[0] != '\0') ||
        currentEventObject.event_id[0] != '\0';
    runtimeEventStatus.active = false;
    runtimeEventStatus.track_id = 0;
    runtimeEventStatus.opened_ms = 0;
    runtimeEventStatus.event_id[0] = '\0';
    if (close_reason != nullptr && close_reason[0] != '\0' && had_event_context) {
        currentEventObject.active = false;
        currentEventObject.event_state = EVENT_STATE_CLOSED;
        copyEventId(currentEventObject.close_reason, sizeof(currentEventObject.close_reason), close_reason);
    } else {
        currentEventObject.active = false;
        currentEventObject.event_state = EVENT_STATE_NONE;
        currentEventObject.event_id[0] = '\0';
        currentEventObject.node_id[0] = '\0';
        currentEventObject.close_reason[0] = '\0';
        currentEventObject.track_id = 0;
        currentEventObject.risk_score = 0.0f;
        currentEventObject.risk_level = RISK_NONE;
        currentEventObject.risk_reason_flags = 0;
        currentEventObject.trigger_flags = 0;
        currentEventObject.rid_status = RID_NONE;
        currentEventObject.wl_status = WL_UNKNOWN;
        currentEventObject.start_time_ms = 0;
        currentEventObject.last_x_mm = 0.0f;
        currentEventObject.last_y_mm = 0.0f;
        currentEventObject.last_vx_mm_s = 0.0f;
        currentEventObject.last_vy_mm_s = 0.0f;
    }
    globalData.event_active = false;
    globalData.event_id[0] = '\0';
    portEXIT_CRITICAL(&dataMutex);
}

void syncRuntimeEventStatus(const SystemData &snapshot, const EventContext &context, const char *close_reason = nullptr) {
    portENTER_CRITICAL(&dataMutex);
    runtimeEventStatus.active = hasEventContext(context);
    runtimeEventStatus.track_id = context.track_id;
    runtimeEventStatus.opened_ms = context.opened_ms;
    globalData.event_active = runtimeEventStatus.active;
    if (hasEventContext(context)) {
        copyEventId(runtimeEventStatus.event_id, sizeof(runtimeEventStatus.event_id), context.event_id);
        copyEventId(globalData.event_id, sizeof(globalData.event_id), context.event_id);
        currentEventObject.active = true;
        currentEventObject.event_state = EVENT_STATE_OPEN;
        currentEventObject.close_reason[0] = '\0';
        copyEventId(currentEventObject.event_id, sizeof(currentEventObject.event_id), context.event_id);
        copyEventId(currentEventObject.node_id, sizeof(currentEventObject.node_id), NodeConfig::NodeId);
        currentEventObject.track_id = snapshot.radar_track.track_id;
        currentEventObject.risk_score = snapshot.risk_score;
        currentEventObject.risk_level = deriveRiskLevel(snapshot);
        currentEventObject.risk_reason_flags = snapshot.risk_reason_flags;
        currentEventObject.trigger_flags = computeTriggerFlags(snapshot);
        currentEventObject.rid_status = snapshot.rid_status;
        currentEventObject.wl_status = snapshot.wl_status;
        currentEventObject.start_time_ms = context.opened_ms;
        currentEventObject.last_x_mm = snapshot.radar_track.x_mm;
        currentEventObject.last_y_mm = snapshot.radar_track.y_mm;
        currentEventObject.last_vx_mm_s = snapshot.radar_track.vx_mm_s;
        currentEventObject.last_vy_mm_s = snapshot.radar_track.vy_mm_s;
    } else {
        runtimeEventStatus.event_id[0] = '\0';
        globalData.event_id[0] = '\0';
        currentEventObject.active = false;
        currentEventObject.event_state =
            currentEventObject.event_id[0] != '\0' ? EVENT_STATE_CLOSED : EVENT_STATE_NONE;
        if (currentEventObject.event_state == EVENT_STATE_CLOSED && close_reason != nullptr && close_reason[0] != '\0') {
            if (!isTerminalEventCloseReason(currentEventObject.close_reason)) {
                copyEventId(currentEventObject.close_reason, sizeof(currentEventObject.close_reason), close_reason);
            }
        } else if (currentEventObject.event_state == EVENT_STATE_NONE) {
            currentEventObject.close_reason[0] = '\0';
        }
        currentEventObject.risk_score = snapshot.risk_score;
        currentEventObject.risk_level = deriveRiskLevel(snapshot);
        currentEventObject.risk_reason_flags = snapshot.risk_reason_flags;
        currentEventObject.trigger_flags = computeTriggerFlags(snapshot);
        currentEventObject.rid_status = snapshot.rid_status;
        currentEventObject.wl_status = snapshot.wl_status;
        currentEventObject.last_x_mm = snapshot.radar_track.x_mm;
        currentEventObject.last_y_mm = snapshot.radar_track.y_mm;
        currentEventObject.last_vx_mm_s = snapshot.radar_track.vx_mm_s;
        currentEventObject.last_vy_mm_s = snapshot.radar_track.vy_mm_s;
    }
    portEXIT_CRITICAL(&dataMutex);
}

RuntimeEventStatus getRuntimeEventStatusSnapshot() {
    RuntimeEventStatus snapshot = {};
    portENTER_CRITICAL(&dataMutex);
    snapshot = runtimeEventStatus;
    portEXIT_CRITICAL(&dataMutex);
    return snapshot;
}

EventObject getCurrentEventObjectSnapshot() {
    EventObject snapshot = {};
    portENTER_CRITICAL(&dataMutex);
    snapshot = currentEventObject;
    portEXIT_CRITICAL(&dataMutex);
    return snapshot;
}

UnifiedOutputSnapshot buildUnifiedOutputSnapshot(const SystemData &snapshot, const RuntimeEventStatus &status) {
    UnifiedOutputSnapshot unified = {};
    unified.main_state = deriveMainState(snapshot);
    unified.risk_level = deriveRiskLevel(snapshot);
    unified.hunter_state = snapshot.hunter_state;
    unified.gimbal_state = snapshot.gimbal_state;
    unified.rid_status = snapshot.rid_status;
    unified.rid_whitelist_hit = snapshot.rid_whitelist_hit;
    unified.wl_status = snapshot.wl_status;
    unified.wl_expire_time_ms = snapshot.wl_expire_time_ms;
    copyEventId(unified.wl_owner, sizeof(unified.wl_owner), snapshot.wl_owner);
    copyEventId(unified.wl_label, sizeof(unified.wl_label), snapshot.wl_label);
    copyEventId(unified.wl_note, sizeof(unified.wl_note), snapshot.wl_note);
    unified.rid_last_update_ms = snapshot.rid_last_update_ms;
    unified.rid_last_match_ms = snapshot.rid_last_match_ms;
    copyEventId(unified.rid_id, sizeof(unified.rid_id), snapshot.rid_id);
    copyEventId(unified.rid_device_type, sizeof(unified.rid_device_type), snapshot.rid_device_type);
    copyEventId(unified.rid_source, sizeof(unified.rid_source), snapshot.rid_source);
    copyEventId(unified.rid_auth_status, sizeof(unified.rid_auth_status), snapshot.rid_auth_status);
    copyEventId(unified.rid_whitelist_tag, sizeof(unified.rid_whitelist_tag), snapshot.rid_whitelist_tag);
    unified.rid_signal_strength = snapshot.rid_signal_strength;
    unified.track_id = snapshot.radar_track.track_id;
    unified.track_active = snapshot.radar_track.is_active;
    unified.track_confirmed = snapshot.radar_track.is_confirmed;
    unified.x_mm = snapshot.radar_track.x_mm;
    unified.y_mm = snapshot.radar_track.y_mm;
    unified.vx_mm_s = snapshot.radar_track.vx_mm_s;
    unified.vy_mm_s = snapshot.radar_track.vy_mm_s;
    unified.risk_score = snapshot.risk_score;
    unified.risk_reason_flags = snapshot.risk_reason_flags;
    unified.risk_base_score = snapshot.risk_base_score;
    unified.risk_persistence_score = snapshot.risk_persistence_score;
    unified.risk_confirmed_score = snapshot.risk_confirmed_score;
    unified.risk_rid_score = snapshot.risk_rid_score;
    unified.risk_proximity_score = snapshot.risk_proximity_score;
    unified.risk_motion_score = snapshot.risk_motion_score;
    unified.hunter_pending_state = snapshot.hunter_pending_state;
    unified.hunter_state_since_ms = snapshot.hunter_state_since_ms;
    unified.hunter_pending_since_ms = snapshot.hunter_pending_since_ms;
    unified.risk_transition_mode = snapshot.risk_transition_mode;
    unified.risk_transition_hold_ms = snapshot.risk_transition_hold_ms;
    unified.risk_transition_elapsed_ms = snapshot.risk_transition_elapsed_ms;
    unified.trigger_flags = snapshot.trigger_flags;
    unified.vision_state = snapshot.vision_state;
    unified.vision_locked = snapshot.vision_locked;
    unified.capture_ready = snapshot.capture_ready;
    unified.audio_state = snapshot.audio_state;
    unified.uplink_state = snapshot.uplink_state;
    unified.event_active = status.active;
    copyEventId(
        unified.event_id,
        sizeof(unified.event_id),
        status.active && status.event_id[0] != '\0' ? status.event_id : "NONE"
    );
    unified.timestamp_ms = snapshot.timestamp_ms;
    return unified;
}

void printNormalizedStateFields(const UnifiedOutputSnapshot &snapshot) {
    Serial.print(",main_state=");
    Serial.print(mainStateName(snapshot.main_state));
    Serial.print(",hunter_state=");
    Serial.print(hunterStateName(snapshot.hunter_state));
    Serial.print(",gimbal_state=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",rid_status=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",rid_whitelist_hit=");
    Serial.print(snapshot.rid_whitelist_hit ? 1 : 0);
    Serial.print(",wl_status=");
    Serial.print(whitelistStatusName(snapshot.wl_status));
    Serial.print(",wl_owner=");
    Serial.print(snapshot.wl_owner[0] != '\0' ? snapshot.wl_owner : "NONE");
    Serial.print(",wl_label=");
    Serial.print(snapshot.wl_label[0] != '\0' ? snapshot.wl_label : "NONE");
    Serial.print(",wl_expire_time_ms=");
    Serial.print(snapshot.wl_expire_time_ms);
    Serial.print(",wl_note=");
    Serial.print(snapshot.wl_note[0] != '\0' ? snapshot.wl_note : "NONE");
    Serial.print(",rid_last_update_ms=");
    Serial.print(snapshot.rid_last_update_ms);
    Serial.print(",rid_last_match_ms=");
    Serial.print(snapshot.rid_last_match_ms);
    Serial.print(",rid_id=");
    Serial.print(snapshot.rid_id[0] != '\0' ? snapshot.rid_id : "NONE");
    Serial.print(",rid_source=");
    Serial.print(snapshot.rid_source[0] != '\0' ? snapshot.rid_source : "NONE");
    Serial.print(",rid_auth_status=");
    Serial.print(snapshot.rid_auth_status[0] != '\0' ? snapshot.rid_auth_status : "NONE");
    Serial.print(",rid_whitelist_tag=");
    Serial.print(snapshot.rid_whitelist_tag[0] != '\0' ? snapshot.rid_whitelist_tag : "NONE");
    Serial.print(",rid_signal_strength=");
    Serial.print(snapshot.rid_signal_strength);
    Serial.print(",track_id=");
    Serial.print(snapshot.track_id);
    Serial.print(",track_active=");
    Serial.print(snapshot.track_active ? 1 : 0);
    Serial.print(",track_confirmed=");
    Serial.print(snapshot.track_confirmed ? 1 : 0);
    Serial.print(",risk_score=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",risk_base=");
    Serial.print(snapshot.risk_base_score, 1);
    Serial.print(",risk_persistence=");
    Serial.print(snapshot.risk_persistence_score, 1);
    Serial.print(",risk_confirmed=");
    Serial.print(snapshot.risk_confirmed_score, 1);
    Serial.print(",risk_rid=");
    Serial.print(snapshot.risk_rid_score, 1);
    Serial.print(",risk_proximity=");
    Serial.print(snapshot.risk_proximity_score, 1);
    Serial.print(",risk_motion=");
    Serial.print(snapshot.risk_motion_score, 1);
    Serial.print(",risk_level=");
    Serial.print(riskLevelName(snapshot.risk_level));
    Serial.print(",risk_reasons=");
    printRiskReasonFlags(snapshot.risk_reason_flags);
    Serial.print(",pending_risk_state=");
    Serial.print(hunterStateName(snapshot.hunter_pending_state));
    Serial.print(",risk_transition_mode=");
    Serial.print(riskTransitionModeName(snapshot.risk_transition_mode));
    Serial.print(",risk_state_since_ms=");
    Serial.print(snapshot.hunter_state_since_ms);
    Serial.print(",risk_pending_since_ms=");
    Serial.print(snapshot.hunter_pending_since_ms);
    Serial.print(",risk_hold_ms=");
    Serial.print(snapshot.risk_transition_hold_ms);
    Serial.print(",risk_hold_elapsed_ms=");
    Serial.print(snapshot.risk_transition_elapsed_ms);
    Serial.print(",trigger_flags=");
    printTriggerFlags(snapshot.trigger_flags);
    Serial.print(",vision_state=");
    Serial.print(visionStateName(snapshot.vision_state));
    Serial.print(",vision_locked=");
    Serial.print(snapshot.vision_locked ? 1 : 0);
    Serial.print(",capture_ready=");
    Serial.print(snapshot.capture_ready ? 1 : 0);
    Serial.print(",audio_state=");
    Serial.print(audioStateName(snapshot.audio_state));
    Serial.print(",uplink_state=");
    Serial.print(uplinkStateName(snapshot.uplink_state));
    Serial.print(",timestamp=");
    Serial.print(snapshot.timestamp_ms);
}

void printRuntimeEventFields(const RuntimeEventStatus &status) {
    Serial.print(",event_active=");
    Serial.print(status.active ? 1 : 0);
    Serial.print(",current_event_id=");
    Serial.print(status.active && status.event_id[0] != '\0' ? status.event_id : "NONE");
}

void printCurrentEventAliasFields(const RuntimeEventStatus &status) {
    Serial.print(",event_id=");
    Serial.print(status.active && status.event_id[0] != '\0' ? status.event_id : "NONE");
}

bool shouldEmitVerboseLocalDebug() {
    return debugOutput.enabled && !debugOutput.quiet_mode_enabled;
}

bool shouldEmitFlowDebug() {
    return debugOutput.enabled || debugOutput.quiet_mode_enabled;
}

void refreshDerivedSystemFields(unsigned long now) {
    portENTER_CRITICAL(&dataMutex);
    globalData.timestamp_ms = now;
    globalData.trigger_flags = computeTriggerFlags(globalData);
    portEXIT_CRITICAL(&dataMutex);
}

void setUplinkState(UplinkState state, unsigned long now) {
    portENTER_CRITICAL(&dataMutex);
    globalData.uplink_state = state;
    globalData.timestamp_ms = now;
    globalData.trigger_flags = computeTriggerFlags(globalData);
    portEXIT_CRITICAL(&dataMutex);
}

void stageOutputSnapshot(SystemData &snapshot, UplinkState state, unsigned long now) {
    snapshot.uplink_state = state;
    snapshot.timestamp_ms = now;
    snapshot.trigger_flags = computeTriggerFlags(snapshot);
}

void emitStateFlowDebug(const char *trigger, const SystemData &snapshot, const RuntimeEventStatus &status) {
    if (!shouldEmitFlowDebug()) {
        return;
    }

    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(snapshot, status);
    Serial.print("FLOW,trigger=");
    Serial.print(trigger);
    printNormalizedStateFields(unified);
    printRuntimeEventFields(status);
    Serial.println();
}

void resetHandoverStatus() {
    portENTER_CRITICAL(&dataMutex);
    handoverStatus.pending = false;
    handoverStatus.pending_since_ms = 0;
    handoverStatus.pending_target[0] = '\0';
    handoverStatus.last_updated_ms = 0;
    handoverStatus.last_result[0] = '\0';
    handoverStatus.last_target[0] = '\0';
    handoverStatus.last_event_id[0] = '\0';
    portEXIT_CRITICAL(&dataMutex);
}

HandoverStatus getHandoverStatusSnapshot() {
    HandoverStatus snapshot = {};
    portENTER_CRITICAL(&dataMutex);
    snapshot = handoverStatus;
    portEXIT_CRITICAL(&dataMutex);
    return snapshot;
}

void setHandoverQueued(const char *target_node, unsigned long now) {
    portENTER_CRITICAL(&dataMutex);
    handoverStatus.pending = true;
    handoverStatus.pending_since_ms = now;
    copyEventId(handoverStatus.pending_target, sizeof(handoverStatus.pending_target), target_node);
    handoverStatus.last_updated_ms = now;
    copyEventId(handoverStatus.last_result, sizeof(handoverStatus.last_result), "QUEUED");
    copyEventId(handoverStatus.last_target, sizeof(handoverStatus.last_target), target_node);
    handoverStatus.last_event_id[0] = '\0';
    portEXIT_CRITICAL(&dataMutex);
}

void setHandoverCleared(unsigned long now) {
    portENTER_CRITICAL(&dataMutex);
    handoverStatus.pending = false;
    handoverStatus.pending_since_ms = 0;
    handoverStatus.pending_target[0] = '\0';
    handoverStatus.last_updated_ms = now;
    copyEventId(handoverStatus.last_result, sizeof(handoverStatus.last_result), "CLEARED");
    handoverStatus.last_event_id[0] = '\0';
    portEXIT_CRITICAL(&dataMutex);
}

void setHandoverOutcome(const char *target_node, const char *result, unsigned long now, const EventContext *context = nullptr) {
    portENTER_CRITICAL(&dataMutex);
    handoverStatus.pending = false;
    handoverStatus.pending_since_ms = 0;
    handoverStatus.pending_target[0] = '\0';
    handoverStatus.last_updated_ms = now;
    copyEventId(handoverStatus.last_result, sizeof(handoverStatus.last_result), result);
    copyEventId(handoverStatus.last_target, sizeof(handoverStatus.last_target), target_node);
    if (context != nullptr && hasEventContext(*context)) {
        copyEventId(handoverStatus.last_event_id, sizeof(handoverStatus.last_event_id), context->event_id);
    } else {
        handoverStatus.last_event_id[0] = '\0';
    }
    portEXIT_CRITICAL(&dataMutex);
}

void printHandoverStatusFields(const HandoverStatus &status) {
    Serial.print(",handover_pending=");
    Serial.print(status.pending ? 1 : 0);
    Serial.print(",handover_pending_target=");
    Serial.print(status.pending && status.pending_target[0] != '\0' ? status.pending_target : "NONE");
    Serial.print(",handover_pending_since_ms=");
    Serial.print(status.pending ? status.pending_since_ms : 0);
    Serial.print(",handover_last_result=");
    Serial.print(status.last_result[0] != '\0' ? status.last_result : "NONE");
    Serial.print(",handover_last_target=");
    Serial.print(status.last_target[0] != '\0' ? status.last_target : "NONE");
    Serial.print(",handover_last_ts=");
    Serial.print(status.last_updated_ms);
    Serial.print(",handover_last_event_id=");
    Serial.print(status.last_event_id[0] != '\0' ? status.last_event_id : "NONE");
}

void emitHandoverStatus() {
    HandoverStatus handoverSnapshot = getHandoverStatusSnapshot();
    RuntimeEventStatus eventSnapshot = getRuntimeEventStatusSnapshot();
    SystemData systemSnapshot = {};

    portENTER_CRITICAL(&dataMutex);
    systemSnapshot = globalData;
    portEXIT_CRITICAL(&dataMutex);
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(systemSnapshot, eventSnapshot);

    Serial.print("HANDOVER,STATUS,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    printHandoverStatusFields(handoverSnapshot);
    printNormalizedStateFields(unified);
    printRuntimeEventFields(eventSnapshot);
    printCurrentEventAliasFields(eventSnapshot);
    Serial.println();
}

const char *mainStateNameForLastEvent(const LastEventSnapshot &snapshot) {
    return mainStateName(snapshot.main_state);
}

const char *riskLevelNameForLastEvent(const LastEventSnapshot &snapshot) {
    return riskLevelName(snapshot.risk_level);
}

void resetLastEventSnapshot() {
    portENTER_CRITICAL(&dataMutex);
    lastEventSnapshot.valid = false;
    lastEventSnapshot.ts = 0;
    lastEventSnapshot.main_state = MAIN_IDLE;
    lastEventSnapshot.risk_level = RISK_NONE;
    lastEventSnapshot.track_id = 0;
    lastEventSnapshot.track_active = false;
    lastEventSnapshot.track_confirmed = false;
    lastEventSnapshot.hunter_state = HUNTER_IDLE;
    lastEventSnapshot.gimbal_state = STATE_SCANNING;
    lastEventSnapshot.rid_status = RID_NONE;
    lastEventSnapshot.risk_score = 0.0f;
    lastEventSnapshot.trigger_flags = 0u;
    lastEventSnapshot.x_mm = 0.0f;
    lastEventSnapshot.y_mm = 0.0f;
    lastEventSnapshot.vx_mm_s = 0.0f;
    lastEventSnapshot.vy_mm_s = 0.0f;
    lastEventSnapshot.event_id[0] = '\0';
    lastEventSnapshot.reason[0] = '\0';
    lastEventSnapshot.close_reason[0] = '\0';
    lastEventSnapshot.event_level[0] = '\0';
    lastEventSnapshot.event_status[0] = '\0';
    lastEventSnapshot.source_node[0] = '\0';
    lastEventSnapshot.handover_from[0] = '\0';
    lastEventSnapshot.handover_to[0] = '\0';
    portEXIT_CRITICAL(&dataMutex);
}

bool isTerminalEventCloseReason(const char *close_reason) {
    if (close_reason == nullptr || close_reason[0] == '\0') {
        return false;
    }

    return strcmp(close_reason, "RISK_DOWNGRADE") == 0 ||
           strcmp(close_reason, "TRACK_LOST") == 0 ||
           strcmp(close_reason, "RESET") == 0;
}

bool isOrdinaryStateEventReason(const char *reason) {
    if (reason == nullptr || reason[0] == '\0') {
        return false;
    }

    return strcmp(reason, "HUNTER_STATE") == 0 ||
           strcmp(reason, "RID_STATE") == 0 ||
           strcmp(reason, "TRACK_CHANGED") == 0;
}

bool shouldPreserveLastEventSnapshot(
    const char *reason,
    const EventContext &event_context,
    const char *close_reason
) {
    if (isOrdinaryStateEventReason(reason)) {
        return true;
    }

    if (close_reason != nullptr && close_reason[0] != '\0') {
        return false;
    }

    if (hasEventContext(event_context)) {
        return false;
    }

    if (reason == nullptr || reason[0] == '\0') {
        return false;
    }
    return lastEventSnapshot.valid && isTerminalEventCloseReason(lastEventSnapshot.close_reason);
}

void cacheLastEventSnapshot(
    const SystemData &snapshot,
    unsigned long now,
    const char *reason,
    const EventContext &event_context,
    const char *handover_target,
    const char *close_reason = nullptr
) {
    RuntimeEventStatus eventStatusSnapshot = getRuntimeEventStatusSnapshot();
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(snapshot, eventStatusSnapshot);
    portENTER_CRITICAL(&dataMutex);
    if (shouldPreserveLastEventSnapshot(reason, event_context, close_reason)) {
        portEXIT_CRITICAL(&dataMutex);
        return;
    }
    lastEventSnapshot.valid = true;
    lastEventSnapshot.ts = now;
    lastEventSnapshot.main_state = unified.main_state;
    lastEventSnapshot.risk_level = unified.risk_level;
    lastEventSnapshot.track_id = snapshot.radar_track.track_id;
    lastEventSnapshot.track_active = snapshot.radar_track.is_active;
    lastEventSnapshot.track_confirmed = snapshot.radar_track.is_confirmed;
    lastEventSnapshot.hunter_state = snapshot.hunter_state;
    lastEventSnapshot.gimbal_state = snapshot.gimbal_state;
    lastEventSnapshot.rid_status = snapshot.rid_status;
    lastEventSnapshot.rid_whitelist_hit = snapshot.rid_whitelist_hit;
    lastEventSnapshot.wl_status = snapshot.wl_status;
    lastEventSnapshot.risk_score = snapshot.risk_score;
    lastEventSnapshot.trigger_flags = unified.trigger_flags;
    lastEventSnapshot.x_mm = snapshot.radar_track.x_mm;
    lastEventSnapshot.y_mm = snapshot.radar_track.y_mm;
    lastEventSnapshot.vx_mm_s = snapshot.radar_track.vx_mm_s;
    lastEventSnapshot.vy_mm_s = snapshot.radar_track.vy_mm_s;
    if (hasEventContext(event_context)) {
        copyEventId(lastEventSnapshot.event_id, sizeof(lastEventSnapshot.event_id), event_context.event_id);
    } else {
        lastEventSnapshot.event_id[0] = '\0';
    }
    copyEventId(lastEventSnapshot.reason, sizeof(lastEventSnapshot.reason), reason);
    if (close_reason != nullptr && close_reason[0] != '\0') {
        copyEventId(lastEventSnapshot.close_reason, sizeof(lastEventSnapshot.close_reason), close_reason);
    } else if (strcmp(reason, "TRACK_LOST") == 0) {
        copyEventId(lastEventSnapshot.close_reason, sizeof(lastEventSnapshot.close_reason), "TRACK_LOST");
    } else {
        lastEventSnapshot.close_reason[0] = '\0';
    }
    copyEventId(
        lastEventSnapshot.event_level,
        sizeof(lastEventSnapshot.event_level),
        eventLevelForSnapshot(snapshot, reason)
    );
    copyEventId(
        lastEventSnapshot.event_status,
        sizeof(lastEventSnapshot.event_status),
        eventStatusForSnapshot(snapshot, reason)
    );
    copyEventId(lastEventSnapshot.source_node, sizeof(lastEventSnapshot.source_node), NodeConfig::NodeId);
    if (handover_target != nullptr && handover_target[0] != '\0') {
        copyEventId(lastEventSnapshot.handover_from, sizeof(lastEventSnapshot.handover_from), NodeConfig::NodeId);
        copyEventId(lastEventSnapshot.handover_to, sizeof(lastEventSnapshot.handover_to), handover_target);
    } else {
        lastEventSnapshot.handover_from[0] = '\0';
        lastEventSnapshot.handover_to[0] = '\0';
    }
    portEXIT_CRITICAL(&dataMutex);
}

void emitLastEventSnapshot() {
    LastEventSnapshot snapshot = {};

    portENTER_CRITICAL(&dataMutex);
    snapshot = lastEventSnapshot;
    portEXIT_CRITICAL(&dataMutex);

    if (!snapshot.valid) {
        Serial.println("LASTEVENT,NONE");
        return;
    }

    Serial.print("LASTEVENT,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",ts=");
    Serial.print(snapshot.ts);
    Serial.print(",event_id=");
    Serial.print(snapshot.event_id[0] != '\0' ? snapshot.event_id : "NONE");
    Serial.print(",source_node=");
    Serial.print(snapshot.source_node[0] != '\0' ? snapshot.source_node : NodeConfig::NodeId);
    Serial.print(",reason=");
    Serial.print(snapshot.reason);
    Serial.print(",event_close_reason=");
    Serial.print(snapshot.close_reason[0] != '\0' ? snapshot.close_reason : "NONE");
    Serial.print(",event_level=");
    Serial.print(snapshot.event_level);
    Serial.print(",event_status=");
    Serial.print(snapshot.event_status);
    if (snapshot.handover_to[0] != '\0') {
        Serial.print(",handover_from=");
        Serial.print(snapshot.handover_from);
        Serial.print(",handover_to=");
        Serial.print(snapshot.handover_to);
    }
    Serial.print(",track=");
    Serial.print(snapshot.track_id);
    Serial.print(",track_active=");
    Serial.print(snapshot.track_active ? 1 : 0);
    Serial.print(",track_confirmed=");
    Serial.print(snapshot.track_confirmed ? 1 : 0);
    Serial.print(",hunter=");
    Serial.print(hunterStateName(snapshot.hunter_state));
    Serial.print(",gimbal=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",rid=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",wl=");
    Serial.print(whitelistStatusName(snapshot.wl_status));
    Serial.print(",wl_hit=");
    Serial.print(snapshot.rid_whitelist_hit ? 1 : 0);
    Serial.print(",risk=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",event_trigger_reasons=");
    printEventTriggerReasonFlags(snapshot.trigger_flags);
    Serial.print(",main_state=");
    if (!snapshot.track_active) {
        Serial.print(snapshot.gimbal_state == STATE_LOST ? "LOST" : "IDLE");
    } else if (!snapshot.track_confirmed) {
        Serial.print("DETECTING");
    } else if (snapshot.hunter_state == HUNTER_SUSPICIOUS) {
        Serial.print("SUSPICIOUS");
    } else if (snapshot.hunter_state == HUNTER_HIGH_RISK) {
        Serial.print("HIGH_RISK");
    } else if (snapshot.hunter_state == HUNTER_EVENT_LOCKED) {
        Serial.print("EVENT");
    } else {
        Serial.print("TRACKING");
    }
    Serial.print(",risk_level=");
    if (!snapshot.track_active) {
        Serial.print("NONE");
    } else if (snapshot.hunter_state == HUNTER_EVENT_LOCKED || snapshot.risk_score >= HunterConfig::EventThreshold) {
        Serial.print("EVENT");
    } else if (snapshot.hunter_state == HUNTER_HIGH_RISK || snapshot.risk_score >= HunterConfig::HighRiskThreshold) {
        Serial.print("HIGH_RISK");
    } else if (snapshot.hunter_state == HUNTER_SUSPICIOUS ||
               snapshot.rid_status == RID_NONE ||
               snapshot.rid_status == RID_EXPIRED ||
               snapshot.rid_status == RID_INVALID ||
               snapshot.risk_score >= HunterConfig::SuspiciousThreshold) {
        Serial.print("SUSPICIOUS");
    } else {
        Serial.print("NORMAL");
    }
    Serial.print(",event_active=");
    Serial.print(strcmp(snapshot.event_status, "OPEN") == 0 ? 1 : 0);
    Serial.print(",x=");
    Serial.print(snapshot.x_mm, 1);
    Serial.print(",y=");
    Serial.print(snapshot.y_mm, 1);
    Serial.print(",vx=");
    Serial.print(snapshot.vx_mm_s, 1);
    Serial.print(",vy=");
    Serial.println(snapshot.vy_mm_s, 1);
}

void emitEventStatus() {
    RuntimeEventStatus eventSnapshot = getRuntimeEventStatusSnapshot();
    EventObject currentEventSnapshot = getCurrentEventObjectSnapshot();
    LastEventSnapshot lastSnapshot = {};
    SystemData systemSnapshot = {};

    portENTER_CRITICAL(&dataMutex);
    lastSnapshot = lastEventSnapshot;
    systemSnapshot = globalData;
    portEXIT_CRITICAL(&dataMutex);
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(systemSnapshot, eventSnapshot);

    Serial.print("EVENT,STATUS,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    printNormalizedStateFields(unified);
    printRuntimeEventFields(eventSnapshot);
    printCurrentEventAliasFields(eventSnapshot);
    Serial.print(",current_risk_state=");
    Serial.print(hunterStateName(unified.hunter_state));
    Serial.print(",current_pending_risk_state=");
    Serial.print(hunterStateName(unified.hunter_pending_state));
    Serial.print(",current_risk_transition_mode=");
    Serial.print(riskTransitionModeName(unified.risk_transition_mode));
    Serial.print(",current_event_object_id=");
    Serial.print(currentEventSnapshot.event_id[0] != '\0' ? currentEventSnapshot.event_id : "NONE");
    Serial.print(",current_event_track_id=");
    Serial.print(eventSnapshot.track_id);
    Serial.print(",current_event_opened_ms=");
    Serial.print(eventSnapshot.active ? eventSnapshot.opened_ms : 0);
    Serial.print(",current_event_state=");
    Serial.print(eventStateName(currentEventSnapshot.event_state));
    Serial.print(",current_event_close_reason=");
    Serial.print(currentEventSnapshot.close_reason[0] != '\0' ? currentEventSnapshot.close_reason : "NONE");
    Serial.print(",current_event_node_id=");
    Serial.print(currentEventSnapshot.node_id[0] != '\0' ? currentEventSnapshot.node_id : "NONE");
    Serial.print(",current_event_risk_score=");
    Serial.print(currentEventSnapshot.risk_score, 1);
    Serial.print(",current_event_risk_level=");
    Serial.print(riskLevelName(currentEventSnapshot.risk_level));
    Serial.print(",current_event_risk_reasons=");
    printRiskReasonFlags(currentEventSnapshot.risk_reason_flags);
    Serial.print(",current_event_trigger_flags=");
    printTriggerFlags(currentEventSnapshot.trigger_flags);
    Serial.print(",current_event_trigger_reasons=");
    printEventTriggerReasonFlags(currentEventSnapshot.trigger_flags);
    Serial.print(",current_event_rid_status=");
    Serial.print(ridStateName(currentEventSnapshot.rid_status));
    Serial.print(",current_event_start_time=");
    Serial.print(currentEventSnapshot.start_time_ms);
    Serial.print(",current_event_last_x=");
    Serial.print(currentEventSnapshot.last_x_mm, 1);
    Serial.print(",current_event_last_y=");
    Serial.print(currentEventSnapshot.last_y_mm, 1);
    Serial.print(",current_event_last_vx=");
    Serial.print(currentEventSnapshot.last_vx_mm_s, 1);
    Serial.print(",current_event_last_vy=");
    Serial.print(currentEventSnapshot.last_vy_mm_s, 1);
    Serial.print(",last_event_valid=");
    Serial.print(lastSnapshot.valid ? 1 : 0);
    Serial.print(",last_event_id=");
    Serial.print(lastSnapshot.valid && lastSnapshot.event_id[0] != '\0' ? lastSnapshot.event_id : "NONE");
    Serial.print(",last_reason=");
    Serial.print(lastSnapshot.valid && lastSnapshot.reason[0] != '\0' ? lastSnapshot.reason : "NONE");
    Serial.print(",last_event_level=");
    Serial.print(lastSnapshot.valid && lastSnapshot.event_level[0] != '\0' ? lastSnapshot.event_level : "NONE");
    Serial.print(",last_event_status=");
    Serial.print(lastSnapshot.valid && lastSnapshot.event_status[0] != '\0' ? lastSnapshot.event_status : "NONE");
    Serial.print(",last_source_node=");
    Serial.print(lastSnapshot.valid && lastSnapshot.source_node[0] != '\0' ? lastSnapshot.source_node : "NONE");
    Serial.print(",last_track_id=");
    Serial.print(lastSnapshot.valid ? lastSnapshot.track_id : 0);
    Serial.print(",last_track_active=");
    Serial.print(lastSnapshot.valid && lastSnapshot.track_active ? 1 : 0);
    Serial.print(",last_track_confirmed=");
    Serial.print(lastSnapshot.valid && lastSnapshot.track_confirmed ? 1 : 0);
    Serial.print(",last_hunter_state=");
    Serial.print(lastSnapshot.valid ? hunterStateName(lastSnapshot.hunter_state) : "NONE");
    Serial.print(",last_gimbal_state=");
    Serial.print(lastSnapshot.valid ? gimbalStateName(lastSnapshot.gimbal_state) : "NONE");
    Serial.print(",last_rid_status=");
    Serial.print(lastSnapshot.valid ? ridStateName(lastSnapshot.rid_status) : "NONE");
    Serial.print(",last_risk_score=");
    Serial.print(lastSnapshot.valid ? lastSnapshot.risk_score : 0.0f, 1);
    Serial.print(",last_main_state=");
    Serial.print(lastSnapshot.valid ? mainStateNameForLastEvent(lastSnapshot) : "NONE");
    Serial.print(",last_risk_level=");
    Serial.print(lastSnapshot.valid ? riskLevelNameForLastEvent(lastSnapshot) : "NONE");
    Serial.print(",last_x=");
    Serial.print(lastSnapshot.valid ? lastSnapshot.x_mm : 0.0f, 1);
    Serial.print(",last_y=");
    Serial.print(lastSnapshot.valid ? lastSnapshot.y_mm : 0.0f, 1);
    Serial.print(",last_vx=");
    Serial.print(lastSnapshot.valid ? lastSnapshot.vx_mm_s : 0.0f, 1);
    Serial.print(",last_vy=");
    Serial.print(lastSnapshot.valid ? lastSnapshot.vy_mm_s : 0.0f, 1);
    Serial.print(",last_ts=");
    Serial.print(lastSnapshot.valid ? lastSnapshot.ts : 0);
    Serial.print(",last_handover_from=");
    Serial.print(lastSnapshot.valid && lastSnapshot.handover_from[0] != '\0' ? lastSnapshot.handover_from : "NONE");
    Serial.print(",last_handover_to=");
    Serial.println(lastSnapshot.valid && lastSnapshot.handover_to[0] != '\0' ? lastSnapshot.handover_to : "NONE");
}

void emitRiskStatus() {
    SystemData systemSnapshot = {};
    RuntimeEventStatus eventSnapshot = {};
    portENTER_CRITICAL(&dataMutex);
    systemSnapshot = globalData;
    eventSnapshot = runtimeEventStatus;
    portEXIT_CRITICAL(&dataMutex);

    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(systemSnapshot, eventSnapshot);

    Serial.print("RISK,STATUS,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",main_state=");
    Serial.print(mainStateName(unified.main_state));
    Serial.print(",current_risk_state=");
    Serial.print(hunterStateName(unified.hunter_state));
    Serial.print(",pending_risk_state=");
    Serial.print(hunterStateName(unified.hunter_pending_state));
    Serial.print(",risk_transition_mode=");
    Serial.print(riskTransitionModeName(unified.risk_transition_mode));
    Serial.print(",risk_hold_ms=");
    Serial.print(unified.risk_transition_hold_ms);
    Serial.print(",risk_hold_elapsed_ms=");
    Serial.print(unified.risk_transition_elapsed_ms);
    Serial.print(",risk_score=");
    Serial.print(unified.risk_score, 1);
    Serial.print(",risk_level=");
    Serial.print(riskLevelName(unified.risk_level));
    Serial.print(",risk_base=");
    Serial.print(unified.risk_base_score, 1);
    Serial.print(",risk_persistence=");
    Serial.print(unified.risk_persistence_score, 1);
    Serial.print(",risk_confirmed=");
    Serial.print(unified.risk_confirmed_score, 1);
    Serial.print(",risk_rid=");
    Serial.print(unified.risk_rid_score, 1);
    Serial.print(",risk_proximity=");
    Serial.print(unified.risk_proximity_score, 1);
    Serial.print(",risk_motion=");
    Serial.print(unified.risk_motion_score, 1);
    Serial.print(",risk_reasons=");
    printRiskReasonFlags(unified.risk_reason_flags);
    Serial.print(",track_id=");
    Serial.print(unified.track_id);
    Serial.print(",track_active=");
    Serial.print(unified.track_active ? 1 : 0);
    Serial.print(",track_confirmed=");
    Serial.print(unified.track_confirmed ? 1 : 0);
    Serial.print(",rid_status=");
    Serial.print(ridStateName(unified.rid_status));
    Serial.print(",rid_whitelist_hit=");
    Serial.print(unified.rid_whitelist_hit ? 1 : 0);
    Serial.print(",wl_status=");
    Serial.print(whitelistStatusName(unified.wl_status));
    Serial.print(",rid_last_update_ms=");
    Serial.print(unified.rid_last_update_ms);
    Serial.print(",rid_last_match_ms=");
    Serial.print(unified.rid_last_match_ms);
    Serial.print(",event_active=");
    Serial.print(unified.event_active ? 1 : 0);
    Serial.print(",event_id=");
    Serial.print(unified.event_id);
    Serial.print(",timestamp=");
    Serial.println(unified.timestamp_ms);
}

void emitEventLifecycleLog(
    const char *action,
    const SystemData &snapshot,
    const EventContext *context = nullptr,
    const char *detail = nullptr
) {
    Serial.print("EVENT,LIFECYCLE,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",ts=");
    Serial.print(snapshot.timestamp_ms);
    Serial.print(",action=");
    Serial.print(action != nullptr ? action : "NONE");
    Serial.print(",track_id=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",risk_score=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",rid_status=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",wl_status=");
    Serial.print(whitelistStatusName(snapshot.wl_status));
    Serial.print(",reason_flags=");
    Serial.print(snapshot.risk_reason_flags);
    bool context_open = context != nullptr && context->active && context->event_id[0] != '\0';
    Serial.print(",event_state=");
    Serial.print(context_open ? "OPEN" : "CLOSED");
    Serial.print(",event_id=");
    if (context_open) {
        Serial.print(context->event_id);
    } else {
        Serial.print("NONE");
    }
    if (detail != nullptr && detail[0] != '\0') {
        Serial.print(",detail=");
        Serial.print(detail);
    }
    Serial.println();
}

void emitVisionStatus() {
    SystemData snapshot = {};
    EventObject currentEventSnapshot = {};
    portENTER_CRITICAL(&dataMutex);
    snapshot = globalData;
    portEXIT_CRITICAL(&dataMutex);
    currentEventSnapshot = getCurrentEventObjectSnapshot();

    Serial.print("VISION,STATUS,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",vision_state=");
    Serial.print(visionStateName(snapshot.vision_state));
    Serial.print(",rid_status=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",wl_status=");
    Serial.print(whitelistStatusName(snapshot.wl_status));
    Serial.print(",reason_flags=");
    Serial.print(snapshot.risk_reason_flags);
    Serial.print(",event_state=");
    Serial.print(eventStateName(currentEventSnapshot.event_state));
    Serial.print(",x_mm=");
    Serial.print(snapshot.radar_track.x_mm, 1);
    Serial.print(",y_mm=");
    Serial.print(snapshot.radar_track.y_mm, 1);
    Serial.print(",gimbal_state=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",audio_state=");
    Serial.print(audioStateName(snapshot.audio_state));
    Serial.print(",risk_score=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",timestamp=");
    Serial.println(snapshot.timestamp_ms);
}

void emitAudioStatus() {
    SystemData snapshot = {};
    portENTER_CRITICAL(&dataMutex);
    snapshot = globalData;
    portEXIT_CRITICAL(&dataMutex);

    Serial.print("AUDIO,STATUS,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",audio_enabled=");
    Serial.print(AudioConfig::AudioEnabled ? 1 : 0);
    Serial.print(",audio_state=");
    Serial.print(audioStateName(snapshot.audio_state));
    Serial.print(",track_id=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",track_active=");
    Serial.print(snapshot.radar_track.is_active ? 1 : 0);
    Serial.print(",risk_score=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",reason_flags=");
    Serial.print(snapshot.risk_reason_flags);
    Serial.print(",timestamp=");
    Serial.println(snapshot.timestamp_ms);
}
void emitRidStatus() {
    SystemData snapshot = {};
    RidIdentityPacket packet = {};
    unsigned long now = millis();

    portENTER_CRITICAL(&dataMutex);
    snapshot = globalData;
    packet = ridIdentity;
    portEXIT_CRITICAL(&dataMutex);

    unsigned long rid_age_ms = 0;
    if (snapshot.rid_last_update_ms > 0 && now >= snapshot.rid_last_update_ms) {
        rid_age_ms = now - snapshot.rid_last_update_ms;
    }

    Serial.print("RID,STATUS,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",rid_status=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",rid_whitelist_hit=");
    Serial.print(snapshot.rid_whitelist_hit ? 1 : 0);
    Serial.print(",wl_status=");
    Serial.print(whitelistStatusName(snapshot.wl_status));
    Serial.print(",wl_owner=");
    Serial.print(snapshot.wl_owner[0] != '\0' ? snapshot.wl_owner : "NONE");
    Serial.print(",wl_label=");
    Serial.print(snapshot.wl_label[0] != '\0' ? snapshot.wl_label : "NONE");
    Serial.print(",wl_expire_time_ms=");
    Serial.print(snapshot.wl_expire_time_ms);
    Serial.print(",wl_note=");
    Serial.print(snapshot.wl_note[0] != '\0' ? snapshot.wl_note : "NONE");
    Serial.print(",rid_last_update_ms=");
    Serial.print(snapshot.rid_last_update_ms);
    Serial.print(",rid_last_match_ms=");
    Serial.print(snapshot.rid_last_match_ms);
    Serial.print(",rid_age_ms=");
    Serial.print(rid_age_ms);
    Serial.print(",rid_packet_valid=");
    Serial.print(packet.valid ? 1 : 0);
    Serial.print(",rid_id=");
    Serial.print(snapshot.rid_id[0] != '\0' ? snapshot.rid_id : "NONE");
    Serial.print(",rid_device_type=");
    Serial.print(snapshot.rid_device_type[0] != '\0' ? snapshot.rid_device_type : "NONE");
    Serial.print(",rid_source=");
    Serial.print(snapshot.rid_source[0] != '\0' ? snapshot.rid_source : "NONE");
    Serial.print(",rid_auth_status=");
    Serial.print(snapshot.rid_auth_status[0] != '\0' ? snapshot.rid_auth_status : "NONE");
    Serial.print(",rid_whitelist_tag=");
    Serial.print(snapshot.rid_whitelist_tag[0] != '\0' ? snapshot.rid_whitelist_tag : "NONE");
    Serial.print(",rid_signal_strength=");
    Serial.print(snapshot.rid_signal_strength);
    Serial.print(",track_id=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",track_active=");
    Serial.print(snapshot.radar_track.is_active ? 1 : 0);
    Serial.print(",track_confirmed=");
    Serial.print(snapshot.radar_track.is_confirmed ? 1 : 0);
    Serial.print(",timestamp=");
    Serial.println(snapshot.timestamp_ms);
}

void emitWhitelistStatus() {
    SystemData snapshot = {};
    portENTER_CRITICAL(&dataMutex);
    snapshot = globalData;
    portEXIT_CRITICAL(&dataMutex);

    Serial.print("WL,STATUS,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",wl_status=");
    Serial.print(whitelistStatusName(snapshot.wl_status));
    Serial.print(",wl_owner=");
    Serial.print(snapshot.wl_owner[0] != '\0' ? snapshot.wl_owner : "NONE");
    Serial.print(",wl_label=");
    Serial.print(snapshot.wl_label[0] != '\0' ? snapshot.wl_label : "NONE");
    Serial.print(",wl_expire_time_ms=");
    Serial.print(snapshot.wl_expire_time_ms);
    Serial.print(",wl_note=");
    Serial.print(snapshot.wl_note[0] != '\0' ? snapshot.wl_note : "NONE");
    Serial.print(",rid_id=");
    Serial.print(snapshot.rid_id[0] != '\0' ? snapshot.rid_id : "NONE");
    Serial.print(",rid_status=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",rid_whitelist_hit=");
    Serial.print(snapshot.rid_whitelist_hit ? 1 : 0);
    Serial.print(",timestamp=");
    Serial.println(snapshot.timestamp_ms);
}

void emitWhitelistTable() {
    Serial.print("WL,LIST,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",count=");
    Serial.println(sizeof(RidWhitelistTable) / sizeof(RidWhitelistTable[0]));

    for (size_t index = 0; index < sizeof(RidWhitelistTable) / sizeof(RidWhitelistTable[0]); ++index) {
        const WhitelistEntry &entry = RidWhitelistTable[index];
        Serial.print("WL,ENTRY,index=");
        Serial.print(static_cast<unsigned long>(index + 1));
        Serial.print(",rid_id=");
        Serial.print(entry.rid_id != nullptr ? entry.rid_id : "NONE");
        Serial.print(",owner=");
        Serial.print(entry.owner != nullptr ? entry.owner : "NONE");
        Serial.print(",label=");
        Serial.print(entry.label != nullptr ? entry.label : "NONE");
        Serial.print(",allowed=");
        Serial.print(entry.allowed ? 1 : 0);
        Serial.print(",expire_time_ms=");
        Serial.print(entry.expire_time_ms);
        Serial.print(",note=");
        Serial.println(entry.note != nullptr ? entry.note : "NONE");
    }
}

void clearHandoverRequest() {
    portENTER_CRITICAL(&dataMutex);
    handoverRequest.pending = false;
    handoverRequest.requested_ms = 0;
    handoverRequest.target_node[0] = '\0';
    portEXIT_CRITICAL(&dataMutex);
}

void queueHandoverRequest(const String &target_node) {
    portENTER_CRITICAL(&dataMutex);
    handoverRequest.pending = true;
    handoverRequest.requested_ms = millis();
    snprintf(handoverRequest.target_node, sizeof(handoverRequest.target_node), "%s", target_node.c_str());
    portEXIT_CRITICAL(&dataMutex);
}

bool consumeHandoverRequest(HandoverRequest &request) {
    portENTER_CRITICAL(&dataMutex);
    request = handoverRequest;
    handoverRequest.pending = false;
    handoverRequest.requested_ms = 0;
    handoverRequest.target_node[0] = '\0';
    portEXIT_CRITICAL(&dataMutex);
    return request.pending;
}

void resetSummaryStats(unsigned long now) {
    portENTER_CRITICAL(&dataMutex);
    summaryStats.started_ms = now;
    summaryStats.track_active_count = 0;
    summaryStats.track_confirmed_count = 0;
    summaryStats.track_lost_count = 0;
    summaryStats.gimbal_tracking_entries = 0;
    summaryStats.gimbal_lost_entries = 0;
    summaryStats.hunter_state_changes = 0;
    summaryStats.risk_suspicious_entries = 0;
    summaryStats.risk_high_risk_entries = 0;
    summaryStats.risk_event_entries = 0;
    summaryStats.event_opened_count = 0;
    summaryStats.event_closed_count = 0;
    summaryStats.handover_queued_count = 0;
    summaryStats.handover_emitted_count = 0;
    summaryStats.handover_ignored_count = 0;
    summaryStats.max_risk_score = 0.0f;
    summaryStats.last_track_id = 0;
    summaryStats.last_track_x_mm = 0.0f;
    summaryStats.last_track_y_mm = 0.0f;
    summaryStats.last_event_id[0] = '\0';
    portEXIT_CRITICAL(&dataMutex);
}

void updateSummaryLastTrack(const RadarTrack &track) {
    portENTER_CRITICAL(&dataMutex);
    summaryStats.last_track_id = track.track_id;
    summaryStats.last_track_x_mm = track.x_mm;
    summaryStats.last_track_y_mm = track.y_mm;
    portEXIT_CRITICAL(&dataMutex);
}

void updateSummaryLastEventId(const EventContext &context) {
    if (!hasEventContext(context)) {
        return;
    }

    portENTER_CRITICAL(&dataMutex);
    copyEventId(summaryStats.last_event_id, sizeof(summaryStats.last_event_id), context.event_id);
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryRisk(float risk_score) {
    portENTER_CRITICAL(&dataMutex);
    if (risk_score > summaryStats.max_risk_score) {
        summaryStats.max_risk_score = risk_score;
    }
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryHunterStateChange() {
    portENTER_CRITICAL(&dataMutex);
    summaryStats.hunter_state_changes++;
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryHunterRiskEntry(HunterState state) {
    portENTER_CRITICAL(&dataMutex);
    if (state == HUNTER_SUSPICIOUS) {
        summaryStats.risk_suspicious_entries++;
    } else if (state == HUNTER_HIGH_RISK) {
        summaryStats.risk_high_risk_entries++;
    } else if (state == HUNTER_EVENT_LOCKED) {
        summaryStats.risk_event_entries++;
    }
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryGimbalStateEntry(GimbalState state) {
    portENTER_CRITICAL(&dataMutex);
    if (state == STATE_TRACKING) {
        summaryStats.gimbal_tracking_entries++;
    } else if (state == STATE_LOST) {
        summaryStats.gimbal_lost_entries++;
    }
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryTrackActiveChange(bool active, const RadarTrack &track, const EventContext &context) {
    portENTER_CRITICAL(&dataMutex);
    if (active) {
        summaryStats.track_active_count++;
    } else {
        summaryStats.track_lost_count++;
    }
    summaryStats.last_track_id = track.track_id;
    summaryStats.last_track_x_mm = track.x_mm;
    summaryStats.last_track_y_mm = track.y_mm;
    if (hasEventContext(context)) {
        copyEventId(summaryStats.last_event_id, sizeof(summaryStats.last_event_id), context.event_id);
    }
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryTrackConfirmed(const RadarTrack &track, const EventContext &context) {
    portENTER_CRITICAL(&dataMutex);
    summaryStats.track_confirmed_count++;
    summaryStats.last_track_id = track.track_id;
    summaryStats.last_track_x_mm = track.x_mm;
    summaryStats.last_track_y_mm = track.y_mm;
    if (hasEventContext(context)) {
        copyEventId(summaryStats.last_event_id, sizeof(summaryStats.last_event_id), context.event_id);
    }
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryEventOpened(const EventContext &context) {
    if (!hasEventContext(context)) {
        return;
    }

    portENTER_CRITICAL(&dataMutex);
    summaryStats.event_opened_count++;
    copyEventId(summaryStats.last_event_id, sizeof(summaryStats.last_event_id), context.event_id);
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryEventClosed(const char *event_id) {
    portENTER_CRITICAL(&dataMutex);
    summaryStats.event_closed_count++;
    if (event_id != nullptr && event_id[0] != '\0') {
        copyEventId(summaryStats.last_event_id, sizeof(summaryStats.last_event_id), event_id);
    }
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryHandoverQueued() {
    portENTER_CRITICAL(&dataMutex);
    summaryStats.handover_queued_count++;
    portEXIT_CRITICAL(&dataMutex);
}

void recordSummaryHandoverOutcome(const char *result) {
    if (result == nullptr || result[0] == '\0') {
        return;
    }

    portENTER_CRITICAL(&dataMutex);
    if (strcmp(result, "EMITTED") == 0) {
        summaryStats.handover_emitted_count++;
    } else if (strcmp(result, "IGNORED_NO_TRACK") == 0) {
        summaryStats.handover_ignored_count++;
    }
    portEXIT_CRITICAL(&dataMutex);
}

void printHostCommandHelp() {
    Serial.println("Host commands:");
    Serial.println("  [Common]");
    Serial.println("    HELP");
    Serial.println("    BRIEF");
    Serial.println("    STATUS");
    Serial.println("    RISK,STATUS");
    Serial.println("    EVENT,STATUS");
    Serial.println("    LASTEVENT | LASTEVENT,CLEAR");
    Serial.println("    SUMMARY | SUMMARY,RESET");
    Serial.println("    SELFTEST");
    Serial.println("  [Simulation]");
    Serial.println("    TRACK,x,y | TRACK,CLEAR");
    Serial.println("    RID,MATCHED | RID,NONE | RID,RECEIVED | RID,EXPIRED | RID,INVALID");
    Serial.println("    RID,OK | RID,MISSING | RID,SUSPICIOUS (legacy aliases)");
    Serial.println("    RID,STATUS | RID,CLEAR");
    Serial.println("    RID,MSG,rid_id,device_type,source,timestamp_ms,auth_status,whitelist_tag[,signal_strength]");
    Serial.println("    WL,STATUS | WL,LIST");
    Serial.println("    VISION,LOCKED | VISION,LOST | VISION,IDLE | VISION,STATUS");
    Serial.println("    AUDIO,ANOMALY | AUDIO,NORMAL | AUDIO,STATUS");
    Serial.println("    KP,value");
    Serial.println("    KD,value");
    Serial.println("    HANDOVER,target_node | HANDOVER,STATUS | HANDOVER,CLEAR");
    Serial.println("  [Debug]");
    Serial.println("    DEBUG,ON | DEBUG,OFF");
    Serial.println("    QUIET,ON | QUIET,OFF");
    Serial.println("    UPLINK,ON | UPLINK,OFF");
    Serial.println("  [Servo]");
    Serial.println("    SAFE,ON | SAFE,OFF");
    Serial.println("    DIAG,SERVO | DIAG,STOP");
    Serial.println("    TESTMODE,ON | TESTMODE,OFF");
    Serial.println("    SERVO,ON | SERVO,OFF");
    Serial.println("    CENTER");
    Serial.println("    PAN,angle");
    Serial.println("    TILT,angle");
    Serial.println("    COARSEAIM,x,y");
    Serial.println("  [Reset]");
    Serial.println("    RESET");
}

void emitBriefStatus() {
    SystemData snapshot = {};
    RuntimeEventStatus eventStatus = {};
    portENTER_CRITICAL(&dataMutex);
    snapshot = globalData;
    eventStatus = runtimeEventStatus;
    portEXIT_CRITICAL(&dataMutex);
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(snapshot, eventStatus);
    EventObject currentEventSnapshot = getCurrentEventObjectSnapshot();

    Serial.print("BRIEF,main=");
    Serial.print(mainStateName(unified.main_state));
    Serial.print(",track=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",active=");
    Serial.print(snapshot.radar_track.is_active ? 1 : 0);
    Serial.print(",confirmed=");
    Serial.print(snapshot.radar_track.is_confirmed ? 1 : 0);
    Serial.print(",hunter=");
    Serial.print(hunterStateName(snapshot.hunter_state));
    Serial.print(",gimbal=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",rid=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",risk=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",risk_level=");
    Serial.print(riskLevelName(unified.risk_level));
    Serial.print(",event_active=");
    Serial.print(eventStatus.active ? 1 : 0);
    Serial.print(",event_id=");
    Serial.print(eventStatus.event_id[0] != '\0' ? eventStatus.event_id : "NONE");
    Serial.print(",event_state=");
    Serial.print(eventStateName(currentEventSnapshot.event_state));
    Serial.print(",event_close_reason=");
    Serial.print(currentEventSnapshot.close_reason[0] != '\0' ? currentEventSnapshot.close_reason : "NONE");
    Serial.print(",x=");
    Serial.print(snapshot.radar_track.x_mm, 1);
    Serial.print(",y=");
    Serial.println(snapshot.radar_track.y_mm, 1);
}

void emitStatusSnapshot() {
    SystemData snapshot = {};
    RuntimeEventStatus eventStatus = {};
    HandoverStatus handoverSnapshot = {};
    portENTER_CRITICAL(&dataMutex);
    snapshot = globalData;
    eventStatus = runtimeEventStatus;
    handoverSnapshot = handoverStatus;
    portEXIT_CRITICAL(&dataMutex);
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(snapshot, eventStatus);

    Serial.print("STATUS,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",baseline_version=");
    Serial.print(NodeConfig::BaselineVersion);
    Serial.print(",hunter=");
    Serial.print(hunterStateName(snapshot.hunter_state));
    Serial.print(",gimbal=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",rid=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",risk=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",track=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",active=");
    Serial.print(snapshot.radar_track.is_active ? 1 : 0);
    Serial.print(",confirmed=");
    Serial.print(snapshot.radar_track.is_confirmed ? 1 : 0);
    Serial.print(",x=");
    Serial.print(snapshot.radar_track.x_mm, 1);
    Serial.print(",y=");
    Serial.print(snapshot.radar_track.y_mm, 1);
    Serial.print(",test_mode=");
    Serial.print(manualServo.test_mode_enabled ? 1 : 0);
    Serial.print(",servo_enabled=");
    Serial.print(manualServo.servo_enabled ? 1 : 0);
    Serial.print(",manual_pan=");
    Serial.print(manualServo.pan_deg, 1);
    Serial.print(",manual_tilt=");
    Serial.print(manualServo.tilt_deg, 1);
    Serial.print(",safe_mode=");
    Serial.print(safetyControl.safe_mode_enabled ? 1 : 0);
    Serial.print(",diag_running=");
    Serial.print(servoDiagnostic.running ? 1 : 0);
    Serial.print(",debug=");
    Serial.print(debugOutput.enabled ? 1 : 0);
    Serial.print(",quiet=");
    Serial.print(debugOutput.quiet_mode_enabled ? 1 : 0);
    Serial.print(",uplink=");
    Serial.print(uplinkOutput.enabled ? 1 : 0);
    printNormalizedStateFields(unified);
    printRuntimeEventFields(eventStatus);
    printCurrentEventAliasFields(eventStatus);
    printHandoverStatusFields(handoverSnapshot);
    Serial.println();
}

void emitSelfTestSnapshot() {
    SystemData snapshot = {};
    SimTrackInput simSnapshot = {};
    RuntimeEventStatus eventStatus = {};
    HandoverStatus handoverSnapshot = {};

    portENTER_CRITICAL(&dataMutex);
    snapshot = globalData;
    simSnapshot = simTrack;
    eventStatus = runtimeEventStatus;
    handoverSnapshot = handoverStatus;
    portEXIT_CRITICAL(&dataMutex);
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(snapshot, eventStatus);

    unsigned long now = millis();
    bool simActive = isSimTrackActive(simSnapshot, now);
    bool idleReady = !snapshot.radar_track.is_active &&
                     snapshot.hunter_state == HUNTER_IDLE &&
                     snapshot.gimbal_state == STATE_SCANNING;

    Serial.println("SELFTEST,BEGIN");

    Serial.print("SELFTEST,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",role=");
    Serial.print(NodeConfig::NodeRole);
    Serial.print(",baseline_version=");
    Serial.println(NodeConfig::BaselineVersion);

    Serial.print("SELFTEST,monitor_baud=");
    Serial.print(AppSerialConfig::MonitorBaudRate);
    Serial.print(",radar_baud=");
    Serial.println(AppSerialConfig::RadarBaudRate);

    Serial.print("SELFTEST,hunter=");
    Serial.print(hunterStateName(snapshot.hunter_state));
    Serial.print(",gimbal=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",rid=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",risk=");
    Serial.println(snapshot.risk_score, 1);

    Serial.print("SELFTEST,main_state=");
    Serial.print(mainStateName(unified.main_state));
    Serial.print(",hunter_state=");
    Serial.print(hunterStateName(snapshot.hunter_state));
    Serial.print(",gimbal_state=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",rid_status=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",rid_whitelist_hit=");
    Serial.print(snapshot.rid_whitelist_hit ? 1 : 0);
    Serial.print(",wl_status=");
    Serial.print(whitelistStatusName(snapshot.wl_status));
    Serial.print(",rid_last_update_ms=");
    Serial.print(snapshot.rid_last_update_ms);
    Serial.print(",track_id=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",track_active=");
    Serial.print(snapshot.radar_track.is_active ? 1 : 0);
    Serial.print(",track_confirmed=");
    Serial.print(snapshot.radar_track.is_confirmed ? 1 : 0);
    Serial.print(",risk_score=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",risk_level=");
    Serial.print(riskLevelName(unified.risk_level));
    Serial.print(",event_active=");
    Serial.print(eventStatus.active ? 1 : 0);
    Serial.print(",current_event_id=");
    Serial.print(eventStatus.active && eventStatus.event_id[0] != '\0' ? eventStatus.event_id : "NONE");
    printCurrentEventAliasFields(eventStatus);
    printHandoverStatusFields(handoverSnapshot);
    Serial.println();

    Serial.print("SELFTEST,track=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",active=");
    Serial.print(snapshot.radar_track.is_active ? 1 : 0);
    Serial.print(",confirmed=");
    Serial.print(snapshot.radar_track.is_confirmed ? 1 : 0);
    Serial.print(",x=");
    Serial.print(snapshot.radar_track.x_mm, 1);
    Serial.print(",y=");
    Serial.print(snapshot.radar_track.y_mm, 1);
    Serial.print(",vx=");
    Serial.print(snapshot.radar_track.vx_mm_s, 1);
    Serial.print(",vy=");
    Serial.println(snapshot.radar_track.vy_mm_s, 1);

    Serial.print("SELFTEST,sim_enabled=");
    Serial.print(simSnapshot.enabled ? 1 : 0);
    Serial.print(",sim_active=");
    Serial.print(simActive ? 1 : 0);
    Serial.print(",sim_x=");
    Serial.print(simSnapshot.x_mm, 1);
    Serial.print(",sim_y=");
    Serial.print(simSnapshot.y_mm, 1);
    Serial.print(",sim_hold_ms=");
    Serial.println(SimTrackHoldMs);

    Serial.print("SELFTEST,test_mode=");
    Serial.print(manualServo.test_mode_enabled ? 1 : 0);
    Serial.print(",servo_enabled=");
    Serial.print(manualServo.servo_enabled ? 1 : 0);
    Serial.print(",servo_attached=");
    Serial.print(servosAttached ? 1 : 0);
    Serial.print(",manual_pan=");
    Serial.print(manualServo.pan_deg, 1);
    Serial.print(",manual_tilt=");
    Serial.print(manualServo.tilt_deg, 1);
    Serial.print(",safe_mode=");
    Serial.print(safetyControl.safe_mode_enabled ? 1 : 0);
    Serial.print(",diag_running=");
    Serial.print(servoDiagnostic.running ? 1 : 0);
    Serial.print(",debug=");
    Serial.print(debugOutput.enabled ? 1 : 0);
    Serial.print(",quiet=");
    Serial.print(debugOutput.quiet_mode_enabled ? 1 : 0);
    Serial.print(",uplink=");
    Serial.println(uplinkOutput.enabled ? 1 : 0);

    Serial.print("SELFTEST,predictor_kp=");
    Serial.print(runtimeKp, 3);
    Serial.print(",predictor_kd=");
    Serial.println(runtimeKd, 3);

    Serial.print("SELFTEST,heartbeat_ms=");
    Serial.print(CloudConfig::HeartbeatMs);
    Serial.print(",event_report_ms=");
    Serial.println(CloudConfig::EventReportMs);

    Serial.print("SELFTEST,idle_ready=");
    Serial.println(idleReady ? 1 : 0);
    Serial.println("SELFTEST,END");
}

void emitSummarySnapshot() {
    SummaryStats snapshot = {};

    portENTER_CRITICAL(&dataMutex);
    snapshot = summaryStats;
    portEXIT_CRITICAL(&dataMutex);

    unsigned long now = millis();
    const char *last_event_id = snapshot.last_event_id[0] != '\0' ? snapshot.last_event_id : "NONE";

    Serial.print("SUMMARY,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",uptime_ms=");
    Serial.print(now - snapshot.started_ms);
    Serial.print(",track_active=");
    Serial.print(snapshot.track_active_count);
    Serial.print(",track_confirmed=");
    Serial.print(snapshot.track_confirmed_count);
    Serial.print(",track_lost=");
    Serial.print(snapshot.track_lost_count);
    Serial.print(",gimbal_tracking=");
    Serial.print(snapshot.gimbal_tracking_entries);
    Serial.print(",gimbal_lost=");
    Serial.print(snapshot.gimbal_lost_entries);
    Serial.print(",hunter_changes=");
    Serial.print(snapshot.hunter_state_changes);
    Serial.print(",risk_suspicious=");
    Serial.print(snapshot.risk_suspicious_entries);
    Serial.print(",risk_high_risk=");
    Serial.print(snapshot.risk_high_risk_entries);
    Serial.print(",risk_event=");
    Serial.print(snapshot.risk_event_entries);
    Serial.print(",event_opened=");
    Serial.print(snapshot.event_opened_count);
    Serial.print(",event_closed=");
    Serial.print(snapshot.event_closed_count);
    Serial.print(",handover_queued=");
    Serial.print(snapshot.handover_queued_count);
    Serial.print(",handover_emitted=");
    Serial.print(snapshot.handover_emitted_count);
    Serial.print(",handover_ignored=");
    Serial.print(snapshot.handover_ignored_count);
    Serial.print(",max_risk=");
    Serial.print(snapshot.max_risk_score, 1);
    Serial.print(",last_track=");
    Serial.print(snapshot.last_track_id);
    Serial.print(",last_x=");
    Serial.print(snapshot.last_track_x_mm, 1);
    Serial.print(",last_y=");
    Serial.print(snapshot.last_track_y_mm, 1);
    Serial.print(",last_event_id=");
    Serial.println(last_event_id);
}

void applyTrackMeasurement(float px, float py, unsigned long now) {
    const RadarTrack &track = myTrackManager.updateTrack(px, py, now);

    portENTER_CRITICAL(&dataMutex);
    globalData.x_pos = px;
    globalData.y_pos = py;
    globalData.is_locked = track.is_confirmed && (py > RadarConfig::LockDistanceThresholdMm);
    globalData.radar_track = track;
    portEXIT_CRITICAL(&dataMutex);
}

void handleHostCommand(const String &line) {
    int comma = line.indexOf(',');
    String command = line;
    String value;

    if (comma >= 0) {
        command = line.substring(0, comma);
        value = line.substring(comma + 1);
    }

    command.trim();
    value.trim();
    String rawValue = value;
    command.toUpperCase();
    value.toUpperCase();

    if (command == "TRACK") {
        if (value == "CLEAR" || value == "OFF" || value == "STOP") {
            clearSimTrack();
            Serial.println("Simulation track cleared.");
        } else {
            float x_mm = 0.0f;
            float y_mm = 0.0f;
            if (parseTrackCoordinates(value, x_mm, y_mm)) {
                setSimTrack(x_mm, y_mm);
                Serial.print("Simulation track updated: x=");
                Serial.print(x_mm, 1);
                Serial.print(",y=");
                Serial.println(y_mm, 1);
            } else {
                Serial.println("Invalid TRACK command. Use TRACK,x,y or TRACK,CLEAR.");
            }
        }
    } else if (command == "RID") {
        if (value.length() == 0 || value == "STATUS") {
            emitRidStatus();
            return;
        }

        if (value == "CLEAR") {
            clearRidIdentityPacket(millis());
            Serial.println("RID identity cleared.");
            return;
        }

        if (value.startsWith("MSG,")) {
            RidIdentityPacket packet = {};
            unsigned long now = millis();
            if (!parseRidMessagePayload(rawValue.substring(4), packet, now)) {
                Serial.println(
                    "Invalid RID,MSG command. Use RID,MSG,rid_id,device_type,source,timestamp_ms,auth_status,whitelist_tag[,signal_strength]."
                );
                return;
            }

            setRidIdentityPacket(packet);
            refreshRidRuntime(myTrackManager.getTrack(), now);
            Serial.print("RID message accepted: rid_id=");
            Serial.print(packet.rid_id[0] != '\0' ? packet.rid_id : "NONE");
            Serial.print(",source=");
            Serial.print(packet.source[0] != '\0' ? packet.source : "NONE");
            Serial.print(",auth=");
            Serial.print(packet.auth_status[0] != '\0' ? packet.auth_status : "NONE");
            Serial.print(",whitelist=");
            Serial.println(packet.whitelist_tag[0] != '\0' ? packet.whitelist_tag : "NONE");
            return;
        }

        bool known_rid_token = value == "OK" ||
                               value == "MATCHED" ||
                               value == "MISSING" ||
                               value == "SUSPICIOUS" ||
                               value == "NONE" ||
                               value == "RECEIVED" ||
                               value == "EXPIRED" ||
                               value == "INVALID" ||
                               value == "CLEAR" ||
                               value == "OFF";
        if (!known_rid_token) {
            Serial.println(
                "Invalid RID command. Use RID,MATCHED|NONE|RECEIVED|EXPIRED|INVALID (legacy: OK|MISSING|SUSPICIOUS), RID,STATUS, RID,CLEAR, or RID,MSG,..."
            );
            return;
        }

        RidStatus new_status = parseRidStatus(value);
        unsigned long now = millis();
        if (new_status == RID_NONE) {
            clearRidIdentityPacket(now);
            Serial.println("RID simulation updated: NONE");
            return;
        }

        RidIdentityPacket packet = {};
        packet.valid = true;
        packet.packet_timestamp_ms = now;
        packet.received_ms = now;
        packet.signal_strength = -50;
        snprintf(packet.rid_id, sizeof(packet.rid_id), "SIM-RID");
        snprintf(packet.device_type, sizeof(packet.device_type), "SIM");
        snprintf(packet.source, sizeof(packet.source), "HOST");
        switch (new_status) {
            case RID_MATCHED:
                snprintf(packet.auth_status, sizeof(packet.auth_status), "VALID");
                snprintf(packet.whitelist_tag, sizeof(packet.whitelist_tag), "WL_OK");
                break;
            case RID_INVALID:
                snprintf(packet.auth_status, sizeof(packet.auth_status), "INVALID");
                snprintf(packet.whitelist_tag, sizeof(packet.whitelist_tag), "DENY");
                break;
            case RID_EXPIRED:
                snprintf(packet.auth_status, sizeof(packet.auth_status), "VALID");
                snprintf(packet.whitelist_tag, sizeof(packet.whitelist_tag), "WL_OK");
                packet.received_ms = now > RidConfig::ReceiveTimeoutMs ? (now - RidConfig::ReceiveTimeoutMs - 1) : 0;
                break;
            case RID_RECEIVED:
            default:
                snprintf(packet.auth_status, sizeof(packet.auth_status), "VALID");
                snprintf(packet.whitelist_tag, sizeof(packet.whitelist_tag), "PENDING");
                break;
        }
        setRidIdentityPacket(packet);
        refreshRidRuntime(myTrackManager.getTrack(), now);
        Serial.print("RID simulation updated: ");
        Serial.println(ridStateName(new_status));
    } else if (command == "WL") {
        if (value.length() == 0 || value == "STATUS") {
            emitWhitelistStatus();
        } else if (value == "LIST") {
            emitWhitelistTable();
        } else {
            Serial.println("Invalid WL command. Use WL,STATUS or WL,LIST.");
        }
    } else if (command == "VISION") {
        if (value.length() == 0 || value == "STATUS") {
            emitVisionStatus();
            return;
        }

        VisionState requested_state = VISION_IDLE;
        if (!parseVisionStateToken(value, requested_state)) {
            Serial.println("Invalid VISION command. Use VISION,LOCKED|LOST|IDLE|SEARCHING|STATUS.");
            return;
        }

        portENTER_CRITICAL(&dataMutex);
        globalData.vision_state = requested_state;
        globalData.vision_locked = requested_state == VISION_LOCKED;
        globalData.capture_ready = globalData.vision_locked && globalData.trigger_capture;
        globalData.timestamp_ms = millis();
        globalData.trigger_flags = computeTriggerFlags(globalData);
        portEXIT_CRITICAL(&dataMutex);

        Serial.print("VISION simulation updated: ");
        Serial.println(visionStateName(requested_state));
    } else if (command == "AUDIO") {
        if (value.length() == 0 || value == "STATUS") {
            emitAudioStatus();
            return;
        }

        AudioState requested_state = AUDIO_NORMAL;
        if (!parseAudioStateToken(value, requested_state)) {
            Serial.println("Invalid AUDIO command. Use AUDIO,ANOMALY|NORMAL|STATUS.");
            return;
        }

        portENTER_CRITICAL(&dataMutex);
        globalData.audio_state = requested_state;
        globalData.timestamp_ms = millis();
        globalData.trigger_flags = computeTriggerFlags(globalData);
        portEXIT_CRITICAL(&dataMutex);

        if (!AudioConfig::AudioEnabled) {
            Serial.print("AUDIO placeholder updated while disabled: ");
            Serial.println(audioStateName(requested_state));
        } else {
            Serial.print("AUDIO simulation updated: ");
            Serial.println(audioStateName(requested_state));
        }
    } else if (command == "SAFE") {
        if (value == "ON") {
            setSafeMode(true);
            Serial.println("Safe servo limits enabled.");
        } else if (value == "OFF") {
            setSafeMode(false);
            Serial.println("Safe servo limits disabled.");
        } else {
            Serial.println("Invalid SAFE command. Use SAFE,ON or SAFE,OFF.");
        }
    } else if (command == "DEBUG") {
        if (value == "ON") {
            debugOutput.enabled = true;
            debugOutput.quiet_mode_enabled = false;
            Serial.println("Verbose local debug output enabled.");
        } else if (value == "OFF") {
            debugOutput.enabled = false;
            Serial.println("Verbose local debug output disabled. UPLINK frames stay enabled.");
        } else {
            Serial.println("Invalid DEBUG command. Use DEBUG,ON or DEBUG,OFF.");
        }
    } else if (command == "QUIET") {
        if (value == "ON") {
            debugOutput.quiet_mode_enabled = true;
            Serial.println("Quiet log mode enabled. High-rate local debug is suppressed, but key state-change logs remain.");
        } else if (value == "OFF") {
            debugOutput.quiet_mode_enabled = false;
            Serial.println("Quiet log mode disabled.");
        } else {
            Serial.println("Invalid QUIET command. Use QUIET,ON or QUIET,OFF.");
        }
    } else if (command == "UPLINK") {
        if (value == "ON") {
            uplinkOutput.enabled = true;
            Serial.println("UPLINK output enabled.");
        } else if (value == "OFF") {
            uplinkOutput.enabled = false;
            Serial.println("UPLINK output disabled.");
        } else {
            Serial.println("Invalid UPLINK command. Use UPLINK,ON or UPLINK,OFF.");
        }
    } else if (command == "DIAG") {
        if (value == "SERVO") {
            startServoDiagnostic(millis());
        } else if (value == "STOP" || value == "OFF") {
            stopServoDiagnostic("Servo guided diagnostic stopped.");
        } else {
            Serial.println("Invalid DIAG command. Use DIAG,SERVO or DIAG,STOP.");
        }
    } else if (command == "TESTMODE") {
        if (value == "ON") {
            manualServo.test_mode_enabled = true;
            stopServoDiagnostic("Servo guided diagnostic stopped because TESTMODE was changed manually.");
            Serial.println("Manual gimbal test mode enabled.");
        } else if (value == "OFF") {
            manualServo.test_mode_enabled = false;
            stopServoDiagnostic("Servo guided diagnostic stopped because TESTMODE was changed manually.");
            Serial.println("Manual gimbal test mode disabled.");
        } else {
            Serial.println("Invalid TESTMODE command. Use TESTMODE,ON or TESTMODE,OFF.");
        }
    } else if (command == "SERVO") {
        if (value == "ON") {
            setServoEnabled(true);
            Serial.println("Servo output enabled.");
        } else if (value == "OFF") {
            stopServoDiagnostic("Servo guided diagnostic stopped because SERVO output was disabled.");
            setServoEnabled(false);
            Serial.println("Servo output disabled.");
        } else {
            Serial.println("Invalid SERVO command. Use SERVO,ON or SERVO,OFF.");
        }
    } else if (command == "CENTER") {
        stopServoDiagnostic("Servo guided diagnostic stopped because manual CENTER was requested.");
        setManualServoAngles(GimbalConfig::CenterPanDeg, GimbalConfig::CenterTiltDeg);
        Serial.print("Manual gimbal centered: pan=");
        Serial.print(manualServo.pan_deg, 1);
        Serial.print(",tilt=");
        Serial.println(manualServo.tilt_deg, 1);
    } else if (command == "PAN") {
        float angle_deg = 0.0f;
        if (parseAngleValue(value, angle_deg)) {
            stopServoDiagnostic("Servo guided diagnostic stopped because PAN was changed manually.");
            setManualServoAngles(angle_deg, manualServo.tilt_deg);
            Serial.print("Manual pan target updated: ");
            Serial.println(manualServo.pan_deg, 1);
        } else {
            Serial.println("Invalid PAN command. Use PAN,angle.");
        }
    } else if (command == "TILT") {
        float angle_deg = 0.0f;
        if (parseAngleValue(value, angle_deg)) {
            stopServoDiagnostic("Servo guided diagnostic stopped because TILT was changed manually.");
            setManualServoAngles(manualServo.pan_deg, angle_deg);
            Serial.print("Manual tilt target updated: ");
            Serial.println(manualServo.tilt_deg, 1);
        } else {
            Serial.println("Invalid TILT command. Use TILT,angle.");
        }
    } else if (command == "COARSEAIM") {
        float x_mm = 0.0f;
        float y_mm = 0.0f;
        if (parseTrackCoordinates(value, x_mm, y_mm)) {
            stopServoDiagnostic("Servo guided diagnostic stopped because COARSEAIM was requested.");
            manualServo.test_mode_enabled = true;
            setServoEnabled(true);
            float coarse_pan_deg = GimbalConfig::CenterPanDeg;
            float coarse_tilt_deg = GimbalConfig::CenterTiltDeg;
            computeCoarseAimAngles(x_mm, y_mm, coarse_pan_deg, coarse_tilt_deg);
            setManualServoAngles(coarse_pan_deg, coarse_tilt_deg);
            Serial.print("Coarse aim set: x=");
            Serial.print(x_mm, 1);
            Serial.print(",y=");
            Serial.print(y_mm, 1);
            Serial.print(",pan=");
            Serial.print(manualServo.pan_deg, 1);
            Serial.print(",tilt=");
            Serial.print(manualServo.tilt_deg, 1);
            Serial.print(",test_mode=");
            Serial.print(manualServo.test_mode_enabled ? 1 : 0);
            Serial.print(",servo_enabled=");
            Serial.println(manualServo.servo_enabled ? 1 : 0);
        } else {
            Serial.println("Invalid COARSEAIM command. Use COARSEAIM,x,y.");
        }
    } else if (command == "HANDOVER") {
        if (value == "STATUS") {
            emitHandoverStatus();
            return;
        }

        if (value == "CLEAR") {
            clearHandoverRequest();
            setHandoverCleared(millis());
            Serial.println("Handover request cleared.");
            return;
        }

        int second_comma = value.indexOf(',');
        String target_node = value;

        if (second_comma >= 0) {
            String source_node = value.substring(0, second_comma);
            target_node = value.substring(second_comma + 1);
            source_node.trim();
            target_node.trim();
            if (source_node != NodeConfig::NodeId) {
                Serial.println("Invalid HANDOVER command. Source node must match the local node.");
                return;
            }
        }

        target_node.trim();
        target_node.toUpperCase();

        if (target_node.length() == 0) {
            Serial.println("Invalid HANDOVER command. Use HANDOVER,target_node, HANDOVER,STATUS, or HANDOVER,CLEAR.");
        } else if (target_node == NodeConfig::NodeId) {
            Serial.println("Invalid HANDOVER command. Target node must be different from the local node.");
        } else {
            queueHandoverRequest(target_node);
            setHandoverQueued(target_node.c_str(), millis());
            recordSummaryHandoverQueued();
            Serial.print("Handover request queued: ");
            Serial.print(NodeConfig::NodeId);
            Serial.print(" -> ");
            Serial.println(target_node);
        }
    } else if (command == "KP") {
        runtimeKp = value.toFloat();
        myGimbal.setTunings(runtimeKp, runtimeKd);
        Serial.print("Predictor Kp updated: ");
        Serial.println(runtimeKp, 3);
    } else if (command == "KD") {
        runtimeKd = value.toFloat();
        myGimbal.setTunings(runtimeKp, runtimeKd);
        Serial.print("Predictor Kd stored: ");
        Serial.println(runtimeKd, 3);
    } else if (command == "EVENT") {
        if (value == "STATUS") {
            emitEventStatus();
        } else {
            Serial.println("Invalid EVENT command. Use EVENT,STATUS.");
        }
    } else if (command == "RISK") {
        if (value == "STATUS" || value.length() == 0) {
            emitRiskStatus();
        } else {
            Serial.println("Invalid RISK command. Use RISK,STATUS.");
        }
    } else if (command == "LASTEVENT") {
        if (value == "CLEAR") {
            resetLastEventSnapshot();
            Serial.println("Last event snapshot cleared.");
        } else if (value.length() == 0) {
            emitLastEventSnapshot();
        } else {
            Serial.println("Invalid LASTEVENT command. Use LASTEVENT or LASTEVENT,CLEAR.");
        }
    } else if (command == "SUMMARY") {
        if (value == "RESET") {
            resetSummaryStats(millis());
            Serial.println("Summary statistics reset.");
        } else if (value.length() == 0) {
            emitSummarySnapshot();
        } else {
            Serial.println("Invalid SUMMARY command. Use SUMMARY or SUMMARY,RESET.");
        }
    } else if (command == "RESET") {
        SystemData preResetSnapshot = {};
        portENTER_CRITICAL(&dataMutex);
        preResetSnapshot = globalData;
        portEXIT_CRITICAL(&dataMutex);
        RuntimeEventStatus preResetEventStatus = getRuntimeEventStatusSnapshot();
        EventContext preResetEventContext = buildEventContextFromRuntimeStatus(preResetEventStatus);
        bool hadResettableEvent = hasEventContext(preResetEventContext);

        portENTER_CRITICAL(&dataMutex);
        globalData.hunter_state = HUNTER_IDLE;
        globalData.risk_score = 0.0f;
        globalData.risk_reason_flags = 0u;
        globalData.risk_base_score = 0.0f;
        globalData.risk_persistence_score = 0.0f;
        globalData.risk_confirmed_score = 0.0f;
        globalData.risk_rid_score = 0.0f;
        globalData.risk_proximity_score = 0.0f;
        globalData.risk_motion_score = 0.0f;
        globalData.hunter_pending_state = HUNTER_IDLE;
        globalData.hunter_state_since_ms = 0;
        globalData.hunter_pending_since_ms = 0;
        globalData.risk_transition_mode = RISK_TRANSITION_STABLE;
        globalData.risk_transition_hold_ms = 0;
        globalData.risk_transition_elapsed_ms = 0;
        globalData.trigger_alert = false;
        globalData.trigger_capture = false;
        globalData.trigger_guardian = false;
        globalData.rid_status = RID_NONE;
        globalData.rid_whitelist_hit = false;
        globalData.wl_status = WL_UNKNOWN;
        globalData.wl_expire_time_ms = 0;
        globalData.wl_owner[0] = '\0';
        globalData.wl_label[0] = '\0';
        globalData.wl_note[0] = '\0';
        globalData.rid_last_update_ms = 0;
        globalData.rid_last_match_ms = 0;
        globalData.rid_id[0] = '\0';
        globalData.rid_device_type[0] = '\0';
        globalData.rid_source[0] = '\0';
        globalData.rid_auth_status[0] = '\0';
        globalData.rid_whitelist_tag[0] = '\0';
        globalData.rid_signal_strength = 0;
        globalData.vision_state = VISION_IDLE;
        globalData.vision_locked = false;
        globalData.capture_ready = false;
        globalData.audio_state = AUDIO_IDLE;
        globalData.uplink_state = UPLINK_READY;
        globalData.event_active = false;
        globalData.event_id[0] = '\0';
        globalData.timestamp_ms = millis();
        globalData.trigger_flags = computeTriggerFlags(globalData);
        portEXIT_CRITICAL(&dataMutex);
        clearSimTrack();
        clearRidIdentityPacket(0);
        runtimeKp = GimbalConfig::PredictorKp;
        runtimeKd = GimbalConfig::PredictorKd;
        stopServoDiagnostic(nullptr);
        clearHandoverRequest();
        resetHandoverStatus();
        resetRuntimeEventStatus("RESET");
        if (hadResettableEvent) {
            cacheLastEventSnapshot(preResetSnapshot, millis(), "EVENT_CLOSED", preResetEventContext, nullptr, "RESET");
        }
        manualServo.test_mode_enabled = false;
        setManualServoAngles(GimbalConfig::CenterPanDeg, GimbalConfig::CenterTiltDeg);
        setServoEnabled(true);
        setSafeMode(false);
        debugOutput.enabled = true;
        debugOutput.quiet_mode_enabled = false;
        debugOutput.telemetry_initialized = false;
        uplinkOutput.enabled = true;
        myGimbal.setTunings(runtimeKp, runtimeKd);
        Serial.println("Simulation state reset.");
    } else if (command == "STATUS") {
        emitStatusSnapshot();
    } else if (command == "BRIEF") {
        emitBriefStatus();
    } else if (command == "SELFTEST") {
        emitSelfTestSnapshot();
    } else if (command == "HELP") {
        printHostCommandHelp();
    } else if (command.length() > 0) {
        Serial.print("Unknown command: ");
        Serial.println(line);
        printHostCommandHelp();
    }
}

void pollHostCommands() {
    while (Serial.available() > 0) {
        char ch = static_cast<char>(Serial.read());
        if (ch == '\n' || ch == '\r') {
            if (commandBuffer.length() > 0) {
                handleHostCommand(commandBuffer);
                commandBuffer = "";
            }
        } else {
            commandBuffer += ch;
        }
    }
}

void publishTelemetry(const RadarTrack &track, float pan_angle, const HunterOutput &hunter_output, unsigned long now) {
    if (!shouldEmitVerboseLocalDebug()) {
        return;
    }

    SystemData stateSnapshot = {};
    RuntimeEventStatus eventStatusSnapshot = {};
    portENTER_CRITICAL(&dataMutex);
    stateSnapshot = globalData;
    eventStatusSnapshot = runtimeEventStatus;
    portEXIT_CRITICAL(&dataMutex);
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(stateSnapshot, eventStatusSnapshot);
    bool stateChanged = !debugOutput.telemetry_initialized || unified.main_state != debugOutput.last_telemetry_main_state;

    if (stateChanged || (now - debugOutput.last_state_ms) >= StateDebugIntervalMs) {
        Serial.print("STATE,reason=");
        Serial.print(stateChanged ? "STATE_CHANGE" : "STATE_PULSE");
        printNormalizedStateFields(unified);
        printRuntimeEventFields(eventStatusSnapshot);
        Serial.println();
        debugOutput.last_state_ms = now;
        debugOutput.last_telemetry_main_state = unified.main_state;
    }

    if (track.is_active && (stateChanged || (now - debugOutput.last_data_ms) >= DataDebugIntervalMs)) {
        Serial.print("DATA,track_id=");
        Serial.print(track.track_id);
        Serial.print(",x=");
        Serial.print(track.x_mm, 1);
        Serial.print(",y=");
        Serial.print(track.y_mm, 1);
        Serial.print(",pan=");
        Serial.print(pan_angle, 1);
        Serial.print(",risk_score=");
        Serial.print(hunter_output.risk_score, 1);
        Serial.println();
        debugOutput.last_data_ms = now;
    }

    debugOutput.telemetry_initialized = true;
}

void printGimbalDebug(const RadarTrack &track, GimbalState gimbal_state, unsigned long now) {
    if (!shouldEmitVerboseLocalDebug()) {
        return;
    }

    bool stateChanged = !debugOutput.telemetry_initialized || gimbal_state != debugOutput.last_telemetry_gimbal_state;
    if (!stateChanged && (now - debugOutput.last_gimbal_ms < GimbalDebugIntervalMs)) {
        return;
    }

    Serial.print("GIMBAL,");
    Serial.print(gimbalStateName(gimbal_state));
    Serial.print(",reason=");
    Serial.print(stateChanged ? "STATE_CHANGE" : "STATE_PULSE");
    Serial.print(",test_mode=");
    Serial.print(manualServo.test_mode_enabled ? 1 : 0);
    Serial.print(",servo_enabled=");
    Serial.print(manualServo.servo_enabled ? 1 : 0);
    Serial.print(",safe_mode=");
    Serial.print(safetyControl.safe_mode_enabled ? 1 : 0);
    Serial.print(",diag_running=");
    Serial.print(servoDiagnostic.running ? 1 : 0);
    Serial.print(",track_active=");
    Serial.print(track.is_active ? 1 : 0);
    Serial.print(",confirmed=");
    Serial.print(track.is_confirmed ? 1 : 0);
    Serial.print(",x=");
    Serial.print(track.x_mm, 1);
    Serial.print(",y=");
    Serial.print(track.y_mm, 1);
    Serial.print(",vx=");
    Serial.print(track.vx_mm_s, 1);
    Serial.print(",vy=");
    Serial.print(track.vy_mm_s, 1);
    Serial.print(",main_state=");
    if (!track.is_active) {
        Serial.print(gimbal_state == STATE_LOST ? "LOST" : "IDLE");
    } else if (!track.is_confirmed) {
        Serial.print("DETECTING");
    } else {
        Serial.print("TRACKING");
    }
    Serial.println();
    debugOutput.last_gimbal_ms = now;
    debugOutput.last_telemetry_gimbal_state = gimbal_state;
    debugOutput.telemetry_initialized = true;
}

void emitCloudHeartbeat(const SystemData &snapshot, unsigned long now) {
    if (!uplinkOutput.enabled) {
        return;
    }

    RuntimeEventStatus eventStatusSnapshot = getRuntimeEventStatusSnapshot();
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(snapshot, eventStatusSnapshot);
    Serial.print("UPLINK,HB,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",role=");
    Serial.print(NodeConfig::NodeRole);
    Serial.print(",ts=");
    Serial.print(now);
    Serial.print(",hunter=");
    Serial.print(hunterStateName(snapshot.hunter_state));
    Serial.print(",gimbal=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",rid=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",risk=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",alert=");
    Serial.print(snapshot.trigger_alert ? 1 : 0);
    Serial.print(",capture=");
    Serial.print(snapshot.trigger_capture ? 1 : 0);
    Serial.print(",guardian=");
    Serial.print(snapshot.trigger_guardian ? 1 : 0);
    printNormalizedStateFields(unified);
    printRuntimeEventFields(eventStatusSnapshot);
    printCurrentEventAliasFields(eventStatusSnapshot);
    Serial.println();
}

void emitCloudTrack(const SystemData &snapshot, unsigned long now, const EventContext &event_context) {
    if (!uplinkOutput.enabled) {
        return;
    }

    RuntimeEventStatus eventStatusSnapshot = getRuntimeEventStatusSnapshot();
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(snapshot, eventStatusSnapshot);
    Serial.print("UPLINK,TRACK,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",ts=");
    Serial.print(now);
    printEventContextFields(event_context);
    Serial.print(",track=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",active=");
    Serial.print(snapshot.radar_track.is_active ? 1 : 0);
    Serial.print(",confirmed=");
    Serial.print(snapshot.radar_track.is_confirmed ? 1 : 0);
    Serial.print(",x=");
    Serial.print(snapshot.radar_track.x_mm, 1);
    Serial.print(",y=");
    Serial.print(snapshot.radar_track.y_mm, 1);
    Serial.print(",vx=");
    Serial.print(snapshot.radar_track.vx_mm_s, 1);
    Serial.print(",vy=");
    Serial.print(snapshot.radar_track.vy_mm_s, 1);
    Serial.print(",seen=");
    Serial.print(snapshot.radar_track.seen_count);
    Serial.print(",lost=");
    Serial.print(snapshot.radar_track.lost_count);
    printNormalizedStateFields(unified);
    printRuntimeEventFields(eventStatusSnapshot);
    Serial.println();
}

void emitCloudEvent(
    const SystemData &snapshot,
    unsigned long now,
    const char *reason,
    const EventContext &event_context,
    const char *handover_target = nullptr,
    const char *close_reason = nullptr
) {
    RuntimeEventStatus eventStatusSnapshot = getRuntimeEventStatusSnapshot();
    UnifiedOutputSnapshot unified = buildUnifiedOutputSnapshot(snapshot, eventStatusSnapshot);
    cacheLastEventSnapshot(snapshot, now, reason, event_context, handover_target, close_reason);

    if (!uplinkOutput.enabled) {
        return;
    }

    Serial.print("UPLINK,EVENT,node=");
    Serial.print(NodeConfig::NodeId);
    Serial.print(",zone=");
    Serial.print(NodeConfig::NodeZone);
    Serial.print(",ts=");
    Serial.print(now);
    printEventContextFields(event_context);
    Serial.print(",reason=");
    Serial.print(reason);
    Serial.print(",event_close_reason=");
    if (close_reason != nullptr && close_reason[0] != '\0') {
        Serial.print(close_reason);
    } else if (strcmp(reason, "TRACK_LOST") == 0) {
        Serial.print("TRACK_LOST");
    } else {
        Serial.print("NONE");
    }
    Serial.print(",event_level=");
    Serial.print(eventLevelForSnapshot(snapshot, reason));
    Serial.print(",event_status=");
    Serial.print(eventStatusForSnapshot(snapshot, reason));
    printHandoverFields(handover_target);
    Serial.print(",track=");
    Serial.print(snapshot.radar_track.track_id);
    Serial.print(",hunter=");
    Serial.print(hunterStateName(snapshot.hunter_state));
    Serial.print(",gimbal=");
    Serial.print(gimbalStateName(snapshot.gimbal_state));
    Serial.print(",rid=");
    Serial.print(ridStateName(snapshot.rid_status));
    Serial.print(",risk=");
    Serial.print(snapshot.risk_score, 1);
    Serial.print(",alert=");
    Serial.print(snapshot.trigger_alert ? 1 : 0);
    Serial.print(",capture=");
    Serial.print(snapshot.trigger_capture ? 1 : 0);
    Serial.print(",guardian=");
    Serial.print(snapshot.trigger_guardian ? 1 : 0);
    Serial.print(",event_trigger_reasons=");
    printEventTriggerReasonFlags(unified.trigger_flags);
    Serial.print(",x=");
    Serial.print(snapshot.radar_track.x_mm, 1);
    Serial.print(",y=");
    Serial.print(snapshot.radar_track.y_mm, 1);
    printNormalizedStateFields(unified);
    printRuntimeEventFields(eventStatusSnapshot);
    Serial.println();
}
}  // namespace

void RadarTask(void *pvParameters) {
    Serial1.begin(
        AppSerialConfig::RadarBaudRate,
        SERIAL_8N1,
        AppSerialConfig::RadarRxPin,
        AppSerialConfig::RadarTxPin
    );

    while (1) {
        unsigned long now = millis();
        SimTrackInput simSnapshot = {};
        bool simActive = getSimTrackSnapshot(simSnapshot) && isSimTrackActive(simSnapshot, now);

        while (Serial1.available() > 0) {
            uint8_t byteIn = Serial1.read();

            if (myRadar.feedByte(byteIn) && !simActive) {
                applyTrackMeasurement(myRadar.getParsedX(), myRadar.getParsedY(), millis());
            }
        }

        if (simActive) {
            applyTrackMeasurement(simSnapshot.x_mm, simSnapshot.y_mm, now);
        } else {
            const RadarTrack &track = myTrackManager.refresh(now);
            portENTER_CRITICAL(&dataMutex);
            globalData.radar_track = track;
            globalData.is_locked = track.is_confirmed && (track.y_mm > RadarConfig::LockDistanceThresholdMm);
            portEXIT_CRITICAL(&dataMutex);
        }

        vTaskDelay(pdMS_TO_TICKS(RadarConfig::PollDelayMs));
    }
}

void TrackingTask(void *pvParameters) {
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);

    servoPan.setPeriodHertz(ServoConfig::PwmFrequencyHz);
    servoTilt.setPeriodHertz(ServoConfig::PwmFrequencyHz);

    servoPan.attach(ServoConfig::PanPin, ServoConfig::PulseMinUs, ServoConfig::PulseMaxUs);
    servoTilt.attach(ServoConfig::TiltPin, ServoConfig::PulseMinUs, ServoConfig::PulseMaxUs);
    servosAttached = true;

    HunterState lastHunterState = HUNTER_IDLE;
    GimbalState lastGimbalState = STATE_SCANNING;
    VisionState lastVisionState = VISION_IDLE;
    unsigned long lastVisionLostMs = 0;

    while (1) {
        pollHostCommands();

        RadarTrack track_snapshot = {};
        RidStatus rid_snapshot = RID_NONE;
        WhitelistStatus wl_snapshot = WL_UNKNOWN;

        portENTER_CRITICAL(&dataMutex);
        track_snapshot = globalData.radar_track;
        portEXIT_CRITICAL(&dataMutex);

        unsigned long now = millis();
        rid_snapshot = refreshRidRuntime(track_snapshot, now);
        VisionState vision_input_state = VISION_IDLE;
        AudioState audio_input_state = AUDIO_IDLE;
        portENTER_CRITICAL(&dataMutex);
        wl_snapshot = globalData.wl_status;
        vision_input_state = globalData.vision_state;
        audio_input_state = globalData.audio_state;
        portEXIT_CRITICAL(&dataMutex);
        processServoDiagnostic(now);
        HunterOutput hunter_output =
            myHunter.update(track_snapshot, rid_snapshot, wl_snapshot, vision_input_state, audio_input_state, now);
        RuntimeEventStatus eventStatusSnapshot = getRuntimeEventStatusSnapshot();
        UplinkState uplinkStateSnapshot = UPLINK_READY;
        bool currentEventActiveSnapshot = false;
        char currentEventIdSnapshot[32] = {0};
        bool ridWhitelistHitSnapshot = false;
        WhitelistStatus wlStatusSnapshot = WL_UNKNOWN;
        unsigned long wlExpireTimeSnapshot = 0;
        char wlOwnerSnapshot[24] = {0};
        char wlLabelSnapshot[24] = {0};
        char wlNoteSnapshot[40] = {0};
        unsigned long ridLastUpdateMsSnapshot = 0;
        unsigned long ridLastMatchMsSnapshot = 0;
        char ridIdSnapshot[32] = {0};
        char ridDeviceTypeSnapshot[16] = {0};
        char ridSourceSnapshot[16] = {0};
        char ridAuthStatusSnapshot[16] = {0};
        char ridWhitelistTagSnapshot[16] = {0};
        int ridSignalStrengthSnapshot = 0;
        AudioState audioStateSnapshot = AUDIO_IDLE;
        VisionState nextVisionState = VISION_IDLE;
        bool nextVisionLocked = false;

        if (!track_snapshot.is_active) {
            bool holdLostState = (lastVisionState == VISION_SEARCHING || lastVisionState == VISION_LOCKED);
            if (holdLostState) {
                lastVisionLostMs = now;
                nextVisionState = VISION_LOST;
            } else if (lastVisionState == VISION_LOST &&
                       lastVisionLostMs != 0 &&
                       (now - lastVisionLostMs) < TrackingConfig::LostRecoveryTimeoutMs) {
                nextVisionState = VISION_LOST;
            } else {
                nextVisionState = VISION_IDLE;
            }
        } else if (track_snapshot.is_confirmed) {
            if (hunter_output.trigger_capture) {
                nextVisionState = VISION_LOCKED;
                nextVisionLocked = true;
            } else {
                nextVisionState = VISION_SEARCHING;
            }
            lastVisionLostMs = 0;
        } else {
            nextVisionState = VISION_IDLE;
            lastVisionLostMs = 0;
        }

        bool nextCaptureReady = nextVisionLocked && hunter_output.trigger_capture;

        portENTER_CRITICAL(&dataMutex);
        globalData.hunter_state = hunter_output.state;
        globalData.hunter_pending_state = hunter_output.pending_state;
        globalData.risk_score = hunter_output.risk_score;
        globalData.risk_reason_flags = hunter_output.risk_reason_flags;
        globalData.risk_base_score = hunter_output.risk_base_score;
        globalData.risk_persistence_score = hunter_output.risk_persistence_score;
        globalData.risk_confirmed_score = hunter_output.risk_confirmed_score;
        globalData.risk_rid_score = hunter_output.risk_rid_score;
        globalData.risk_proximity_score = hunter_output.risk_proximity_score;
        globalData.risk_motion_score = hunter_output.risk_motion_score;
        globalData.hunter_state_since_ms = hunter_output.state_since_ms;
        globalData.hunter_pending_since_ms = hunter_output.pending_since_ms;
        globalData.risk_transition_mode = hunter_output.transition_mode;
        globalData.risk_transition_hold_ms = hunter_output.transition_hold_ms;
        globalData.risk_transition_elapsed_ms = hunter_output.transition_elapsed_ms;
        globalData.trigger_alert = hunter_output.trigger_alert;
        globalData.trigger_capture = hunter_output.trigger_capture;
        globalData.trigger_guardian = hunter_output.trigger_guardian;
        globalData.vision_state = nextVisionState;
        globalData.vision_locked = nextVisionLocked;
        globalData.capture_ready = nextCaptureReady;
        globalData.timestamp_ms = now;
        globalData.trigger_flags = computeTriggerFlags(globalData);
        uplinkStateSnapshot = globalData.uplink_state;
        currentEventActiveSnapshot = globalData.event_active;
        copyEventId(currentEventIdSnapshot, sizeof(currentEventIdSnapshot), globalData.event_id);
        ridWhitelistHitSnapshot = globalData.rid_whitelist_hit;
        wlStatusSnapshot = globalData.wl_status;
        wlExpireTimeSnapshot = globalData.wl_expire_time_ms;
        copyEventId(wlOwnerSnapshot, sizeof(wlOwnerSnapshot), globalData.wl_owner);
        copyEventId(wlLabelSnapshot, sizeof(wlLabelSnapshot), globalData.wl_label);
        copyEventId(wlNoteSnapshot, sizeof(wlNoteSnapshot), globalData.wl_note);
        ridLastUpdateMsSnapshot = globalData.rid_last_update_ms;
        ridLastMatchMsSnapshot = globalData.rid_last_match_ms;
        copyEventId(ridIdSnapshot, sizeof(ridIdSnapshot), globalData.rid_id);
        copyEventId(ridDeviceTypeSnapshot, sizeof(ridDeviceTypeSnapshot), globalData.rid_device_type);
        copyEventId(ridSourceSnapshot, sizeof(ridSourceSnapshot), globalData.rid_source);
        copyEventId(ridAuthStatusSnapshot, sizeof(ridAuthStatusSnapshot), globalData.rid_auth_status);
        copyEventId(ridWhitelistTagSnapshot, sizeof(ridWhitelistTagSnapshot), globalData.rid_whitelist_tag);
        ridSignalStrengthSnapshot = globalData.rid_signal_strength;
        audioStateSnapshot = globalData.audio_state;
        portEXIT_CRITICAL(&dataMutex);

        SystemData flowSnapshot = {};
        flowSnapshot.is_locked = track_snapshot.is_confirmed && (track_snapshot.y_mm > RadarConfig::LockDistanceThresholdMm);
        flowSnapshot.x_pos = track_snapshot.x_mm;
        flowSnapshot.y_pos = track_snapshot.y_mm;
        flowSnapshot.gimbal_state = lastGimbalState;
        flowSnapshot.hunter_state = hunter_output.state;
        flowSnapshot.hunter_pending_state = hunter_output.pending_state;
        flowSnapshot.rid_status = rid_snapshot;
        flowSnapshot.rid_whitelist_hit = ridWhitelistHitSnapshot;
        flowSnapshot.wl_status = wlStatusSnapshot;
        flowSnapshot.wl_expire_time_ms = wlExpireTimeSnapshot;
        copyEventId(flowSnapshot.wl_owner, sizeof(flowSnapshot.wl_owner), wlOwnerSnapshot);
        copyEventId(flowSnapshot.wl_label, sizeof(flowSnapshot.wl_label), wlLabelSnapshot);
        copyEventId(flowSnapshot.wl_note, sizeof(flowSnapshot.wl_note), wlNoteSnapshot);
        flowSnapshot.rid_last_update_ms = ridLastUpdateMsSnapshot;
        flowSnapshot.rid_last_match_ms = ridLastMatchMsSnapshot;
        copyEventId(flowSnapshot.rid_id, sizeof(flowSnapshot.rid_id), ridIdSnapshot);
        copyEventId(flowSnapshot.rid_device_type, sizeof(flowSnapshot.rid_device_type), ridDeviceTypeSnapshot);
        copyEventId(flowSnapshot.rid_source, sizeof(flowSnapshot.rid_source), ridSourceSnapshot);
        copyEventId(flowSnapshot.rid_auth_status, sizeof(flowSnapshot.rid_auth_status), ridAuthStatusSnapshot);
        copyEventId(flowSnapshot.rid_whitelist_tag, sizeof(flowSnapshot.rid_whitelist_tag), ridWhitelistTagSnapshot);
        flowSnapshot.rid_signal_strength = ridSignalStrengthSnapshot;
        flowSnapshot.radar_track = track_snapshot;
        flowSnapshot.risk_score = hunter_output.risk_score;
        flowSnapshot.risk_reason_flags = hunter_output.risk_reason_flags;
        flowSnapshot.risk_base_score = hunter_output.risk_base_score;
        flowSnapshot.risk_persistence_score = hunter_output.risk_persistence_score;
        flowSnapshot.risk_confirmed_score = hunter_output.risk_confirmed_score;
        flowSnapshot.risk_rid_score = hunter_output.risk_rid_score;
        flowSnapshot.risk_proximity_score = hunter_output.risk_proximity_score;
        flowSnapshot.risk_motion_score = hunter_output.risk_motion_score;
        flowSnapshot.hunter_state_since_ms = hunter_output.state_since_ms;
        flowSnapshot.hunter_pending_since_ms = hunter_output.pending_since_ms;
        flowSnapshot.risk_transition_mode = hunter_output.transition_mode;
        flowSnapshot.risk_transition_hold_ms = hunter_output.transition_hold_ms;
        flowSnapshot.risk_transition_elapsed_ms = hunter_output.transition_elapsed_ms;
        flowSnapshot.trigger_alert = hunter_output.trigger_alert;
        flowSnapshot.trigger_capture = hunter_output.trigger_capture;
        flowSnapshot.trigger_guardian = hunter_output.trigger_guardian;
        flowSnapshot.vision_state = nextVisionState;
        flowSnapshot.vision_locked = nextVisionLocked;
        flowSnapshot.capture_ready = nextCaptureReady;
        flowSnapshot.audio_state = audioStateSnapshot;
        flowSnapshot.uplink_state = uplinkStateSnapshot;
        flowSnapshot.event_active = currentEventActiveSnapshot;
        copyEventId(flowSnapshot.event_id, sizeof(flowSnapshot.event_id), currentEventIdSnapshot);
        flowSnapshot.timestamp_ms = now;
        flowSnapshot.trigger_flags = computeTriggerFlags(flowSnapshot);

        if (hunter_output.state != lastHunterState) {
            recordSummaryHunterStateChange();
            recordSummaryHunterRiskEntry(hunter_output.state);
            emitStateFlowDebug("hunter", flowSnapshot, eventStatusSnapshot);
            lastHunterState = hunter_output.state;
        }

        GimbalOutput gimbal_output = myGimbalController.update(track_snapshot, now);

        portENTER_CRITICAL(&dataMutex);
        globalData.gimbal_state = gimbal_output.state;
        portEXIT_CRITICAL(&dataMutex);

        flowSnapshot.gimbal_state = gimbal_output.state;

        if (gimbal_output.state != lastGimbalState) {
            recordSummaryGimbalStateEntry(gimbal_output.state);
            emitStateFlowDebug("gimbal", flowSnapshot, eventStatusSnapshot);
            lastGimbalState = gimbal_output.state;
        }

        if (track_snapshot.is_active) {
            updateSummaryLastTrack(track_snapshot);
        }
        recordSummaryRisk(hunter_output.risk_score);
        lastVisionState = nextVisionState;

        float outputPan = gimbal_output.pan_angle;
        float outputTilt = gimbal_output.tilt_angle;
        if (manualServo.test_mode_enabled) {
            outputPan = manualServo.pan_deg;
            outputTilt = manualServo.tilt_deg;
        }

        if (manualServo.servo_enabled) {
            attachServosIfNeeded();
            servoPan.write(static_cast<int>(clampPanAngle(outputPan)));
            servoTilt.write(static_cast<int>(clampTiltAngle(outputTilt)));
        }

        printGimbalDebug(track_snapshot, gimbal_output.state, now);

        if (track_snapshot.is_active) {
            publishTelemetry(track_snapshot, outputPan, hunter_output, now);
        }

        vTaskDelay(pdMS_TO_TICKS(TrackingConfig::LoopDelayMs));
    }
}

void CloudTask(void *pvParameters) {
    unsigned long lastHeartbeatMs = 0;
    unsigned long lastTrackReportMs = 0;
    uint32_t lastTrackId = 0;
    bool lastTrackActive = false;
    bool lastTrackConfirmed = false;
    HunterState lastHunterState = HUNTER_IDLE;
    RidStatus lastRidStatus = RID_NONE;
    EventContext eventContext = {false, 0, 0, 0, {0}};
    bool eventClosePending = false;
    unsigned long eventClosePendingSinceMs = 0;
    unsigned long eventReopenCooldownUntilMs = 0;
    uint32_t lastClosedEventTrackId = 0;
    unsigned long lastClosedEventMs = 0;

    while (1) {
        unsigned long now = millis();
        bool uplinkFrameSent = false;

        SystemData snapshot = {};
        portENTER_CRITICAL(&dataMutex);
        snapshot = globalData;
        portEXIT_CRITICAL(&dataMutex);

        if (!uplinkOutput.enabled) {
            setUplinkState(UPLINK_IDLE, now);
            stageOutputSnapshot(snapshot, UPLINK_IDLE, now);
        } else {
            setUplinkState(UPLINK_READY, now);
            stageOutputSnapshot(snapshot, UPLINK_READY, now);
        }
        refreshDerivedSystemFields(now);

        if (now - lastHeartbeatMs >= CloudConfig::HeartbeatMs) {
            setUplinkState(UPLINK_SENDING, now);
            stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
            emitCloudHeartbeat(snapshot, now);
            setUplinkState(UPLINK_OK, now);
            uplinkFrameSent = true;
            lastHeartbeatMs = now;
        }

        bool hadEventContext = hasEventContext(eventContext);
        char previousEventId[32] = {0};
        if (hadEventContext) {
            copyEventId(previousEventId, sizeof(previousEventId), eventContext.event_id);
        }

        const char *eventCloseReason = nullptr;
        bool eventEligible = isEventEligible(snapshot, now);
        EventContext closingEventContext = eventContext;
        if (!eventEligible && hadEventContext && snapshot.radar_track.is_active && previousEventId[0] != '\0') {
            if (!eventClosePending) {
                eventClosePending = true;
                eventClosePendingSinceMs = now;
            } else if ((now - eventClosePendingSinceMs) >= EventConfig::CloseHoldMs) {
                setUplinkState(UPLINK_SENDING, now);
                stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
                emitCloudEvent(snapshot, now, "EVENT_CLOSED", eventContext, nullptr, "RISK_DOWNGRADE");
                setUplinkState(UPLINK_OK, now);
                uplinkFrameSent = true;
                recordSummaryEventClosed(previousEventId);
                closeEventContext(eventContext);
                eventCloseReason = "RISK_DOWNGRADE";
                eventClosePending = false;
                eventClosePendingSinceMs = 0;
                eventReopenCooldownUntilMs = now + EventConfig::ReopenCooldownMs;
                lastClosedEventTrackId = closingEventContext.track_id;
                lastClosedEventMs = now;
            }
        } else {
            eventClosePending = false;
            eventClosePendingSinceMs = 0;
        }

        if (eventEligible) {
            bool blocked_by_cooldown = now < eventReopenCooldownUntilMs;
            bool blocked_by_same_track =
                lastClosedEventTrackId != 0 &&
                snapshot.radar_track.track_id == lastClosedEventTrackId &&
                (now - lastClosedEventMs) < EventConfig::SameTrackReopenBlockMs;
            if (!(blocked_by_cooldown || blocked_by_same_track)) {
                ensureEventContext(snapshot, now, eventContext);
            }
        }

        if (!hadEventContext && hasEventContext(eventContext)) {
            recordSummaryEventOpened(eventContext);
            setUplinkState(UPLINK_SENDING, now);
            stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
            emitCloudEvent(snapshot, now, "EVENT_OPENED", eventContext);
            setUplinkState(UPLINK_OK, now);
            uplinkFrameSent = true;
        } else if (hadEventContext &&
                   hasEventContext(eventContext) &&
                   strcmp(previousEventId, eventContext.event_id) != 0) {
            recordSummaryEventClosed(previousEventId);
            recordSummaryEventOpened(eventContext);
        }
        syncRuntimeEventStatus(snapshot, eventContext, eventCloseReason);
        if (eventCloseReason != nullptr && strcmp(eventCloseReason, "RISK_DOWNGRADE") == 0) {
            cacheLastEventSnapshot(snapshot, now, "EVENT_CLOSED", closingEventContext, nullptr, "RISK_DOWNGRADE");
        }
        updateSummaryLastEventId(eventContext);
        portENTER_CRITICAL(&dataMutex);
        snapshot = globalData;
        portEXIT_CRITICAL(&dataMutex);

        HandoverRequest pendingHandover = {};
        if (consumeHandoverRequest(pendingHandover)) {
            if (!snapshot.radar_track.is_active || !snapshot.radar_track.is_confirmed || !hasEventContext(eventContext)) {
                setHandoverOutcome(pendingHandover.target_node, "IGNORED_NO_TRACK", now);
                recordSummaryHandoverOutcome("IGNORED_NO_TRACK");
                Serial.println("HANDOVER ignored. A confirmed active track is required before emitting a handover event.");
            } else {
                setUplinkState(UPLINK_SENDING, now);
                stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
                emitCloudEvent(snapshot, now, "HANDOVER", eventContext, pendingHandover.target_node);
                setUplinkState(UPLINK_OK, now);
                uplinkFrameSent = true;
                setHandoverOutcome(pendingHandover.target_node, "EMITTED", now, &eventContext);
                recordSummaryHandoverOutcome("EMITTED");
            }
        }

        if (snapshot.radar_track.is_active && now - lastTrackReportMs >= CloudConfig::EventReportMs) {
            setUplinkState(UPLINK_SENDING, now);
            stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
            emitCloudTrack(snapshot, now, eventContext);
            setUplinkState(UPLINK_OK, now);
            uplinkFrameSent = true;
            lastTrackReportMs = now;
        }

        if (snapshot.radar_track.track_id != lastTrackId) {
            setUplinkState(UPLINK_SENDING, now);
            stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
            emitCloudEvent(snapshot, now, "TRACK_CHANGED", eventContext);
            setUplinkState(UPLINK_OK, now);
            uplinkFrameSent = true;
            lastTrackId = snapshot.radar_track.track_id;
        }

        if (snapshot.radar_track.is_active != lastTrackActive) {
            EventContext trackChangeEventContext = eventContext;
            recordSummaryTrackActiveChange(snapshot.radar_track.is_active, snapshot.radar_track, eventContext);
            setUplinkState(UPLINK_SENDING, now);
            stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
            emitCloudEvent(
                snapshot,
                now,
                snapshot.radar_track.is_active ? "TRACK_ACTIVE" : "TRACK_LOST",
                eventContext,
                nullptr,
                snapshot.radar_track.is_active ? nullptr : "TRACK_LOST"
            );
            setUplinkState(UPLINK_OK, now);
            uplinkFrameSent = true;
            lastTrackActive = snapshot.radar_track.is_active;
            if (!snapshot.radar_track.is_active) {
                if (hasEventContext(eventContext)) {
                    recordSummaryEventClosed(eventContext.event_id);
                }
                closeEventContext(eventContext);
                eventClosePending = false;
                eventClosePendingSinceMs = 0;
                eventReopenCooldownUntilMs = now + EventConfig::ReopenCooldownMs;
                lastClosedEventTrackId = trackChangeEventContext.track_id;
                lastClosedEventMs = now;
                syncRuntimeEventStatus(snapshot, eventContext, "TRACK_LOST");
                cacheLastEventSnapshot(snapshot, now, "TRACK_LOST", trackChangeEventContext, nullptr, "TRACK_LOST");
            }
        }

        if (snapshot.radar_track.is_confirmed != lastTrackConfirmed) {
            if (snapshot.radar_track.is_confirmed) {
                recordSummaryTrackConfirmed(snapshot.radar_track, eventContext);
            }
            lastTrackConfirmed = snapshot.radar_track.is_confirmed;
        }

        if (snapshot.hunter_state != lastHunterState) {
            setUplinkState(UPLINK_SENDING, now);
            stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
            emitCloudEvent(snapshot, now, "HUNTER_STATE", eventContext);
            setUplinkState(UPLINK_OK, now);
            uplinkFrameSent = true;
            lastHunterState = snapshot.hunter_state;
        }

        if (snapshot.rid_status != lastRidStatus) {
            setUplinkState(UPLINK_SENDING, now);
            stageOutputSnapshot(snapshot, UPLINK_SENDING, now);
            emitCloudEvent(snapshot, now, "RID_STATE", eventContext);
            setUplinkState(UPLINK_OK, now);
            uplinkFrameSent = true;
            lastRidStatus = snapshot.rid_status;
        }

        if (uplinkOutput.enabled && !uplinkFrameSent) {
            setUplinkState(UPLINK_READY, now);
            stageOutputSnapshot(snapshot, UPLINK_READY, now);
        }
        refreshDerivedSystemFields(now);

        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

void setup() {
    Serial.begin(AppSerialConfig::MonitorBaudRate);
    delay(AppSerialConfig::StartupDelayMs);
    resetSummaryStats(millis());
    resetHandoverStatus();
    resetLastEventSnapshot();
    resetRuntimeEventStatus();

    Serial.println("========================================");
    Serial.println("Node A control chain starting");
    Serial.print("Baseline version: ");
    Serial.println(NodeConfig::BaselineVersion);
    Serial.println("Single-board test mode is supported over USB serial.");
    Serial.println("CloudTask publishes UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT frames.");
    printHostCommandHelp();
    Serial.println("========================================");

    xTaskCreatePinnedToCore(RadarTask, "Radar_Task", 4096, NULL, 1, NULL, 0);
    xTaskCreatePinnedToCore(TrackingTask, "Track_Task", 12288, NULL, 2, NULL, 1);
    xTaskCreatePinnedToCore(CloudTask, "Cloud_Task", 4096, NULL, 1, NULL, 1);
}

void loop() {
    vTaskDelete(NULL);
}
