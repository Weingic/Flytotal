#pragma once

#include <Arduino.h>

#include "SharedData.h"

struct HunterOutput {
    HunterState state;
    HunterState pending_state;
    float risk_score;
    uint32_t risk_reason_flags;
    float risk_base_score;
    float risk_persistence_score;
    float risk_confirmed_score;
    float risk_rid_score;
    float risk_proximity_score;
    float risk_motion_score;
    unsigned long state_since_ms;
    unsigned long pending_since_ms;
    RiskTransitionMode transition_mode;
    unsigned long transition_hold_ms;
    unsigned long transition_elapsed_ms;
    bool trigger_alert;
    bool trigger_capture;
    bool trigger_guardian;
};

struct HunterRiskAssessment {
    float score;
    uint32_t reason_flags;
    float base_score;
    float persistence_score;
    float confirmed_score;
    float rid_score;
    float proximity_score;
    float motion_score;
};

class HunterAction {
private:
    HunterState current_state_;
    unsigned long state_entered_ms_;
    HunterState pending_state_;
    unsigned long pending_state_started_ms_;

    void setState(HunterState next_state, unsigned long now);
    HunterRiskAssessment computeRiskAssessment(
        const RadarTrack &track,
        RidStatus rid_status,
        WhitelistStatus wl_status,
        VisionState vision_state
    ) const;
    void applyStateTarget(HunterState target_state, unsigned long now);

public:
    HunterAction();
    HunterOutput update(
        const RadarTrack &track,
        RidStatus rid_status,
        WhitelistStatus wl_status,
        VisionState vision_state,
        unsigned long now
    );
};
