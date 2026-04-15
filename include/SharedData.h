#pragma once

#include <freertos/FreeRTOS.h>

enum GimbalState {
    STATE_SCANNING,
    STATE_ACQUIRING,
    STATE_TRACKING,
    STATE_LOST
};

enum RidStatus {
    RID_NONE = 0,
    RID_RECEIVED,
    RID_MATCHED,
    RID_EXPIRED,
    RID_INVALID,
    // Backward-compatible aliases for existing command/docs vocabulary.
    RID_UNKNOWN = RID_NONE,
    RID_MISSING = RID_EXPIRED,
    RID_SUSPICIOUS = RID_INVALID
};

enum WhitelistStatus {
    WL_UNKNOWN = 0,
    WL_ALLOWED,
    WL_DENIED,
    WL_EXPIRED
};

enum VisionState {
    VISION_IDLE,
    VISION_SEARCHING,
    VISION_LOCKED,
    VISION_LOST
};

enum UplinkState {
    UPLINK_IDLE,
    UPLINK_READY,
    UPLINK_SENDING,
    UPLINK_OK,
    UPLINK_FAIL
};

enum HunterState {
    HUNTER_IDLE,
    HUNTER_TRACKING,
    HUNTER_RID_MATCHED,
    HUNTER_SUSPICIOUS,
    HUNTER_HIGH_RISK,
    HUNTER_EVENT_LOCKED
};

enum MainState {
    MAIN_IDLE,
    MAIN_DETECTING,
    MAIN_TRACKING,
    MAIN_SUSPICIOUS,
    MAIN_HIGH_RISK,
    MAIN_EVENT,
    MAIN_LOST
};

enum RiskLevel {
    RISK_NONE,
    RISK_NORMAL,
    RISK_SUSPICIOUS,
    RISK_HIGH_RISK,
    RISK_EVENT
};

enum RiskTransitionMode {
    RISK_TRANSITION_STABLE,
    RISK_TRANSITION_ENTER_HOLD,
    RISK_TRANSITION_EXIT_HOLD
};

enum EventState {
    EVENT_STATE_NONE,
    EVENT_STATE_OPEN,
    EVENT_STATE_CLOSED
};

struct RadarTrack {
    uint32_t track_id;
    bool is_active;
    bool is_confirmed;
    float x_mm;
    float y_mm;
    float vx_mm_s;
    float vy_mm_s;
    uint16_t seen_count;
    uint16_t lost_count;
    unsigned long first_seen_ms;
    unsigned long last_seen_ms;
};

struct SystemData {
    bool is_locked;
    float x_pos;
    float y_pos;
    GimbalState gimbal_state;
    HunterState hunter_state;
    RidStatus rid_status;
    bool rid_whitelist_hit;
    WhitelistStatus wl_status;
    unsigned long wl_expire_time_ms;
    char wl_owner[24];
    char wl_label[24];
    char wl_note[40];
    unsigned long rid_last_update_ms;
    unsigned long rid_last_match_ms;
    char rid_id[32];
    char rid_device_type[16];
    char rid_source[16];
    char rid_auth_status[16];
    char rid_whitelist_tag[16];
    int rid_signal_strength;
    RadarTrack radar_track;
    float risk_score;
    uint32_t risk_reason_flags;
    float risk_base_score;
    float risk_persistence_score;
    float risk_confirmed_score;
    float risk_rid_score;
    float risk_proximity_score;
    float risk_motion_score;
    HunterState hunter_pending_state;
    unsigned long hunter_state_since_ms;
    unsigned long hunter_pending_since_ms;
    RiskTransitionMode risk_transition_mode;
    unsigned long risk_transition_hold_ms;
    unsigned long risk_transition_elapsed_ms;
    bool trigger_alert;
    bool trigger_capture;
    bool trigger_guardian;
    uint32_t trigger_flags;
    VisionState vision_state;
    bool vision_locked;
    bool capture_ready;
    UplinkState uplink_state;
    bool event_active;
    char event_id[32];
    unsigned long timestamp_ms;
};

struct UnifiedOutputSnapshot {
    MainState main_state;
    RiskLevel risk_level;
    HunterState hunter_state;
    GimbalState gimbal_state;
    RidStatus rid_status;
    bool rid_whitelist_hit;
    WhitelistStatus wl_status;
    unsigned long wl_expire_time_ms;
    char wl_owner[24];
    char wl_label[24];
    char wl_note[40];
    unsigned long rid_last_update_ms;
    unsigned long rid_last_match_ms;
    char rid_id[32];
    char rid_device_type[16];
    char rid_source[16];
    char rid_auth_status[16];
    char rid_whitelist_tag[16];
    int rid_signal_strength;
    uint32_t track_id;
    bool track_active;
    bool track_confirmed;
    float x_mm;
    float y_mm;
    float vx_mm_s;
    float vy_mm_s;
    float risk_score;
    uint32_t risk_reason_flags;
    float risk_base_score;
    float risk_persistence_score;
    float risk_confirmed_score;
    float risk_rid_score;
    float risk_proximity_score;
    float risk_motion_score;
    HunterState hunter_pending_state;
    unsigned long hunter_state_since_ms;
    unsigned long hunter_pending_since_ms;
    RiskTransitionMode risk_transition_mode;
    unsigned long risk_transition_hold_ms;
    unsigned long risk_transition_elapsed_ms;
    uint32_t trigger_flags;
    VisionState vision_state;
    bool vision_locked;
    bool capture_ready;
    UplinkState uplink_state;
    bool event_active;
    char event_id[32];
    unsigned long timestamp_ms;
};

struct EventObject {
    bool active;
    EventState event_state;
    char event_id[32];
    char node_id[16];
    char close_reason[24];
    char capture_path[128];
    uint32_t track_id;
    float risk_score;
    RiskLevel risk_level;
    uint32_t risk_reason_flags;
    uint32_t trigger_flags;
    RidStatus rid_status;
    WhitelistStatus wl_status;
    unsigned long start_time_ms;
    unsigned long close_time_ms;
    float last_x_mm;
    float last_y_mm;
    float last_vx_mm_s;
    float last_vy_mm_s;
};

extern SystemData globalData;
extern portMUX_TYPE dataMutex;
