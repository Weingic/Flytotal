#include "HunterAction.h"

#include "AppConfig.h"

namespace {
constexpr uint32_t RiskReasonTrackPersistent = 1u << 0;
constexpr uint32_t RiskReasonTrackConfirmed = 1u << 1;
constexpr uint32_t RiskReasonRidMatched = 1u << 2;
constexpr uint32_t RiskReasonRidUnknown = 1u << 3;
constexpr uint32_t RiskReasonRidMissing = 1u << 4;
constexpr uint32_t RiskReasonRidSuspicious = 1u << 5;
constexpr uint32_t RiskReasonProximity = 1u << 6;
constexpr uint32_t RiskReasonMotionAnomaly = 1u << 7;

bool isAlertState(HunterState state) {
    return state == HUNTER_SUSPICIOUS || state == HUNTER_HIGH_RISK || state == HUNTER_EVENT_LOCKED;
}

bool isCaptureState(HunterState state) {
    return state == HUNTER_HIGH_RISK || state == HUNTER_EVENT_LOCKED;
}

int stateRiskRank(HunterState state) {
    switch (state) {
        case HUNTER_SUSPICIOUS:
            return 1;
        case HUNTER_HIGH_RISK:
            return 2;
        case HUNTER_EVENT_LOCKED:
            return 3;
        case HUNTER_IDLE:
        case HUNTER_TRACKING:
        case HUNTER_RID_MATCHED:
        default:
            return 0;
    }
}

unsigned long enterHoldForState(HunterState state) {
    switch (state) {
        case HUNTER_SUSPICIOUS:
            return HunterConfig::SuspiciousEnterHoldMs;
        case HUNTER_HIGH_RISK:
            return HunterConfig::HighRiskEnterHoldMs;
        case HUNTER_EVENT_LOCKED:
            return HunterConfig::EventEnterHoldMs;
        default:
            return 0;
    }
}

unsigned long exitHoldForState(HunterState state) {
    switch (state) {
        case HUNTER_EVENT_LOCKED:
            return HunterConfig::EventExitHoldMs;
        case HUNTER_HIGH_RISK:
            return HunterConfig::HighRiskExitHoldMs;
        case HUNTER_SUSPICIOUS:
            return HunterConfig::SuspiciousExitHoldMs;
        default:
            return 0;
    }
}
}  // namespace

HunterAction::HunterAction() {
    current_state_ = HUNTER_IDLE;
    state_entered_ms_ = 0;
    pending_state_ = HUNTER_IDLE;
    pending_state_started_ms_ = 0;
}

void HunterAction::setState(HunterState next_state, unsigned long now) {
    if (next_state != current_state_) {
        current_state_ = next_state;
        state_entered_ms_ = now;
    }
    pending_state_ = current_state_;
    pending_state_started_ms_ = now;
}

HunterRiskAssessment HunterAction::computeRiskAssessment(const RadarTrack &track, RidStatus rid_status, WhitelistStatus wl_status) const {
    HunterRiskAssessment assessment = {0.0f, 0u, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f};
    if (!track.is_active) {
        return assessment;
    }

    float score = 0.0f;
    assessment.base_score = HunterConfig::TrackingBaseScore;
    score += assessment.base_score;

    assessment.persistence_score = min(track.seen_count * HunterConfig::PersistenceScorePerSeen, HunterConfig::PersistenceScoreMax);
    score += assessment.persistence_score;
    assessment.reason_flags |= RiskReasonTrackPersistent;

    if (track.is_confirmed) {
        assessment.confirmed_score = HunterConfig::ConfirmedBonusScore;
        score += assessment.confirmed_score;
        assessment.reason_flags |= RiskReasonTrackConfirmed;
    }

    if (wl_status == WL_ALLOWED) {
        // Allowed targets keep low-risk behavior even during short re-confirm windows.
        assessment.rid_score = HunterConfig::RidMatchedScore;
        score += assessment.rid_score;
        assessment.reason_flags |= RiskReasonRidMatched;
    } else if (wl_status == WL_DENIED) {
        assessment.rid_score = HunterConfig::RidInvalidScore;
        score += assessment.rid_score;
        assessment.reason_flags |= RiskReasonRidSuspicious;
    } else if (wl_status == WL_EXPIRED) {
        assessment.rid_score = HunterConfig::RidExpiredScore;
        score += assessment.rid_score;
        assessment.reason_flags |= RiskReasonRidMissing;
    } else {
        switch (rid_status) {
            case RID_MATCHED:
                assessment.rid_score = HunterConfig::RidInvalidScore;
                score += assessment.rid_score;
                assessment.reason_flags |= RiskReasonRidSuspicious;
                break;
            case RID_NONE:
                assessment.rid_score = HunterConfig::RidNoneScore;
                score += assessment.rid_score;
                assessment.reason_flags |= RiskReasonRidMissing;
                break;
            case RID_EXPIRED:
                assessment.rid_score = HunterConfig::RidExpiredScore;
                score += assessment.rid_score;
                assessment.reason_flags |= RiskReasonRidMissing;
                break;
            case RID_INVALID:
                assessment.rid_score = HunterConfig::RidInvalidScore;
                score += assessment.rid_score;
                assessment.reason_flags |= RiskReasonRidSuspicious;
                break;
            case RID_RECEIVED:
            default:
                assessment.rid_score = HunterConfig::RidReceivedScore;
                score += assessment.rid_score;
                assessment.reason_flags |= RiskReasonRidUnknown;
                break;
        }
    }

    if (track.y_mm <= HunterConfig::ProximityThresholdMm) {
        assessment.proximity_score = HunterConfig::ProximityScore;
        score += assessment.proximity_score;
        assessment.reason_flags |= RiskReasonProximity;
    }

    if (fabs(track.vx_mm_s) >= HunterConfig::MotionAnomalySpeedThresholdMmS ||
        fabs(track.vy_mm_s) >= HunterConfig::MotionAnomalySpeedThresholdMmS) {
        assessment.motion_score = HunterConfig::MotionAnomalyScore;
        score += assessment.motion_score;
        assessment.reason_flags |= RiskReasonMotionAnomaly;
    }

    if (score < 0.0f) {
        score = 0.0f;
    }
    if (score > 100.0f) {
        score = 100.0f;
    }

    assessment.score = score;
    return assessment;
}

void HunterAction::applyStateTarget(HunterState target_state, unsigned long now) {
    if (target_state == current_state_) {
        pending_state_ = target_state;
        pending_state_started_ms_ = now;
        return;
    }

    if (target_state == HUNTER_IDLE || target_state == HUNTER_TRACKING || target_state == HUNTER_RID_MATCHED) {
        setState(target_state, now);
        return;
    }

    const int current_rank = stateRiskRank(current_state_);
    const int target_rank = stateRiskRank(target_state);
    const bool upgrading = target_rank > current_rank;
    const unsigned long hold_ms = upgrading ? enterHoldForState(target_state) : exitHoldForState(current_state_);

    if (pending_state_ != target_state) {
        pending_state_ = target_state;
        pending_state_started_ms_ = now;
        return;
    }

    if (hold_ms == 0 || (now - pending_state_started_ms_) >= hold_ms) {
        setState(target_state, now);
    }
}

HunterOutput HunterAction::update(const RadarTrack &track, RidStatus rid_status, WhitelistStatus wl_status, unsigned long now) {
    HunterOutput output = {};
    HunterRiskAssessment assessment = computeRiskAssessment(track, rid_status, wl_status);
    output.risk_score = assessment.score;
    output.risk_reason_flags = assessment.reason_flags;
    output.risk_base_score = assessment.base_score;
    output.risk_persistence_score = assessment.persistence_score;
    output.risk_confirmed_score = assessment.confirmed_score;
    output.risk_rid_score = assessment.rid_score;
    output.risk_proximity_score = assessment.proximity_score;
    output.risk_motion_score = assessment.motion_score;

    if (!track.is_active) {
        setState(HUNTER_IDLE, now);
    } else if (!track.is_confirmed) {
        setState(HUNTER_TRACKING, now);
    } else if (
        wl_status == WL_ALLOWED &&
        (rid_status == RID_MATCHED || rid_status == RID_RECEIVED)
    ) {
        setState(HUNTER_RID_MATCHED, now);
    } else {
        HunterState target_state = HUNTER_TRACKING;
        if (output.risk_score >= HunterConfig::EventThreshold) {
            target_state = HUNTER_EVENT_LOCKED;
        } else if (output.risk_score >= HunterConfig::HighRiskThreshold) {
            target_state = HUNTER_HIGH_RISK;
        } else if (output.risk_score >= HunterConfig::SuspiciousThreshold) {
            target_state = HUNTER_SUSPICIOUS;
        }
        applyStateTarget(target_state, now);
    }

    output.state = current_state_;
    output.pending_state = pending_state_;
    output.state_since_ms = state_entered_ms_;
    output.pending_since_ms = pending_state_started_ms_;
    output.transition_mode = RISK_TRANSITION_STABLE;
    output.transition_hold_ms = 0;
    output.transition_elapsed_ms = 0;
    if (pending_state_ != current_state_) {
        const bool upgrading = stateRiskRank(pending_state_) > stateRiskRank(current_state_);
        output.transition_mode = upgrading ? RISK_TRANSITION_ENTER_HOLD : RISK_TRANSITION_EXIT_HOLD;
        output.transition_hold_ms = upgrading ? enterHoldForState(pending_state_) : exitHoldForState(current_state_);
        output.transition_elapsed_ms = pending_state_started_ms_ > 0 ? (now - pending_state_started_ms_) : 0;
    }
    output.trigger_alert = isAlertState(current_state_);
    output.trigger_capture = isCaptureState(current_state_);
    output.trigger_guardian = current_state_ == HUNTER_RID_MATCHED;
    return output;
}
