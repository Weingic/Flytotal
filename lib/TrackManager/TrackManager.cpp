#include "TrackManager.h"

#include "AppConfig.h"

#include <math.h>

namespace {
float clampFloat(float value, float low, float high) {
    if (value < low) {
        return low;
    }
    if (value > high) {
        return high;
    }
    return value;
}
}  // namespace

TrackManager::TrackManager() {
    current_track_ = {0, false, false, 0.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0, 0};
    next_track_id_ = 1;
    last_measurement_x_ = 0.0f;
    last_measurement_y_ = 0.0f;
    last_speed_mm_s_ = 0.0f;
    last_heading_deg_ = 0.0f;
    last_measurement_ms_ = 0;
}

void TrackManager::resetTrack(unsigned long now, float x_mm, float y_mm) {
    current_track_.track_id = next_track_id_++;
    current_track_.is_active = true;
    current_track_.is_confirmed = false;
    current_track_.x_mm = x_mm;
    current_track_.y_mm = y_mm;
    current_track_.vx_mm_s = 0.0f;
    current_track_.vy_mm_s = 0.0f;
    current_track_.seen_count = 1;
    current_track_.lost_count = 0;
    current_track_.first_seen_ms = now;
    current_track_.last_seen_ms = now;
    current_track_.is_multirotor_like = false;
    current_track_.multirotor_score = 0.0f;
    current_track_.track_age_ms = 0;
    current_track_.speed_variance_mm_s = 0.0f;
    current_track_.heading_rate_deg_s = 0.0f;

    last_measurement_x_ = x_mm;
    last_measurement_y_ = y_mm;
    last_speed_mm_s_ = 0.0f;
    last_heading_deg_ = 0.0f;
    last_measurement_ms_ = now;
}

void TrackManager::updateMultirotorFeatures(unsigned long now) {
    if (!current_track_.is_active) {
        current_track_.is_multirotor_like = false;
        current_track_.multirotor_score = 0.0f;
        current_track_.track_age_ms = 0;
        return;
    }

    current_track_.track_age_ms = now >= current_track_.first_seen_ms ? now - current_track_.first_seen_ms : 0;
    const float speed = sqrtf(
        current_track_.vx_mm_s * current_track_.vx_mm_s +
        current_track_.vy_mm_s * current_track_.vy_mm_s
    );
    const float speedDelta = fabsf(speed - last_speed_mm_s_);
    current_track_.speed_variance_mm_s = 0.80f * current_track_.speed_variance_mm_s + 0.20f * speedDelta;

    float heading = last_heading_deg_;
    if (speed > 1.0f) {
        heading = atan2f(current_track_.vx_mm_s, current_track_.vy_mm_s) * 180.0f / PI;
    }
    float headingDelta = fabsf(heading - last_heading_deg_);
    if (headingDelta > 180.0f) {
        headingDelta = 360.0f - headingDelta;
    }
    const float dt = last_measurement_ms_ > 0 ? (now - last_measurement_ms_) / 1000.0f : 0.0f;
    if (dt > 0.0f && dt < 1.0f) {
        current_track_.heading_rate_deg_s = headingDelta / dt;
    }

    float score = 0.0f;
    if (speed >= MultirotorConfig::MinSpeedMmS && speed <= MultirotorConfig::MaxSpeedMmS) {
        score += 35.0f;
    }
    if (current_track_.track_age_ms >= MultirotorConfig::MinTrackAgeMs) {
        score += 30.0f;
    }
    if (current_track_.speed_variance_mm_s <= MultirotorConfig::HoverVarianceMaxMmS) {
        score += 20.0f;
    }
    if (current_track_.heading_rate_deg_s <= MultirotorConfig::HeadingRatePenaltyDegS) {
        score += 15.0f;
    } else {
        score -= 15.0f;
    }

    current_track_.multirotor_score = clampFloat(score, 0.0f, 100.0f);
    current_track_.is_multirotor_like =
        current_track_.track_age_ms >= MultirotorConfig::MinTrackAgeMs &&
        current_track_.multirotor_score >= 65.0f;

    last_speed_mm_s_ = speed;
    last_heading_deg_ = heading;
}

const RadarTrack &TrackManager::updateTrack(float x_mm, float y_mm, unsigned long now) {
    bool should_rebuild = !current_track_.is_active;
    if (!should_rebuild && (now - current_track_.last_seen_ms > TrackConfig::RebuildGapMs)) {
        should_rebuild = true;
    }

    if (should_rebuild) {
        resetTrack(now, x_mm, y_mm);
        return current_track_;
    }

    float dt = (now - last_measurement_ms_) / 1000.0f;
    if (dt > 0.0f && dt < 1.0f) {
        current_track_.vx_mm_s = (x_mm - last_measurement_x_) / dt;
        current_track_.vy_mm_s = (y_mm - last_measurement_y_) / dt;
    } else {
        current_track_.vx_mm_s = 0.0f;
        current_track_.vy_mm_s = 0.0f;
    }

    current_track_.is_active = true;
    current_track_.x_mm = x_mm;
    current_track_.y_mm = y_mm;
    current_track_.last_seen_ms = now;
    current_track_.lost_count = 0;
    current_track_.seen_count++;
    current_track_.is_confirmed = current_track_.seen_count >= TrackConfig::ConfirmFrames;
    updateMultirotorFeatures(now);

    last_measurement_x_ = x_mm;
    last_measurement_y_ = y_mm;
    last_measurement_ms_ = now;

    return current_track_;
}

const RadarTrack &TrackManager::refresh(unsigned long now) {
    if (current_track_.is_active && (now - current_track_.last_seen_ms > TrackConfig::LostTimeoutMs)) {
        current_track_.is_active = false;
        current_track_.is_confirmed = false;
        current_track_.lost_count++;
        current_track_.vx_mm_s = 0.0f;
        current_track_.vy_mm_s = 0.0f;
        current_track_.is_multirotor_like = false;
        current_track_.multirotor_score = 0.0f;
    }

    return current_track_;
}

const RadarTrack &TrackManager::getTrack() const {
    return current_track_;
}
