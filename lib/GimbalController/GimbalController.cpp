#include "GimbalController.h"

#include "AppConfig.h"

GimbalController::GimbalController(GimbalPredictor &predictor)
    : predictor_(predictor) {
    current_state_ = STATE_SCANNING;
    state_entered_ms_ = 0;
    last_target_seen_ms_ = 0;
}

void GimbalController::setState(GimbalState next_state, unsigned long now) {
    if (next_state != current_state_) {
        current_state_ = next_state;
        state_entered_ms_ = now;
    }
}

GimbalOutput GimbalController::update(const RadarTrack &track, unsigned long now) {
    GimbalOutput output = {};
    output.state = current_state_;
    output.pan_angle = GimbalConfig::CenterPanDeg;
    output.tilt_angle = GimbalConfig::CenterTiltDeg;
    output.state_changed = false;

    bool has_target = track.is_confirmed;

    switch (current_state_) {
        case STATE_SCANNING:
            output.pan_angle = GimbalConfig::CenterPanDeg +
                               GimbalConfig::ScanningAmplitudeDeg * sin(now / GimbalConfig::ScanningPeriodDivisor);
            output.tilt_angle = GimbalConfig::CenterTiltDeg;
            if (has_target) {
                setState(STATE_ACQUIRING, now);
            }
            break;

        case STATE_ACQUIRING:
            output.pan_angle = predictor_.getCurrentAngle();
            if (has_target) {
                if (now - state_entered_ms_ > TrackingConfig::AcquireConfirmMs) {
                    setState(STATE_TRACKING, now);
                }
            } else {
                setState(STATE_SCANNING, now);
            }
            break;

        case STATE_TRACKING:
            output.pan_angle = predictor_.calculateFiringAngle(track.x_mm, track.y_mm);
            output.tilt_angle = map(
                static_cast<long>(track.y_mm),
                GimbalConfig::MinTiltMapInputMm,
                GimbalConfig::MaxTiltMapInputMm,
                GimbalConfig::MinTiltDeg,
                GimbalConfig::MaxTiltDeg
            );
            output.tilt_angle = constrain(
                output.tilt_angle,
                static_cast<float>(GimbalConfig::MinTiltDeg),
                static_cast<float>(GimbalConfig::MaxTiltDeg)
            );

            if (has_target) {
                last_target_seen_ms_ = now;
            } else {
                setState(STATE_LOST, now);
            }
            break;

        case STATE_LOST:
            output.pan_angle = predictor_.getCurrentAngle();
            if (has_target) {
                setState(STATE_TRACKING, now);
            } else if (now - last_target_seen_ms_ > TrackingConfig::LostRecoveryTimeoutMs) {
                setState(STATE_SCANNING, now);
            }
            break;
    }

    output.state_changed = output.state != current_state_;
    output.state = current_state_;
    return output;
}

GimbalState GimbalController::getState() const {
    return current_state_;
}
