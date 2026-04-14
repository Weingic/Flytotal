#include "TrackManager.h"

#include "AppConfig.h"

TrackManager::TrackManager() {
    current_track_ = {0, false, false, 0.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0, 0};
    next_track_id_ = 1;
    last_measurement_x_ = 0.0f;
    last_measurement_y_ = 0.0f;
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

    last_measurement_x_ = x_mm;
    last_measurement_y_ = y_mm;
    last_measurement_ms_ = now;
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
    }

    return current_track_;
}

const RadarTrack &TrackManager::getTrack() const {
    return current_track_;
}
