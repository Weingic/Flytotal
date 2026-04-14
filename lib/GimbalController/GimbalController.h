#pragma once

#include <Arduino.h>

#include "GimbalPredictor.h"
#include "SharedData.h"

struct GimbalOutput {
    GimbalState state;
    float pan_angle;
    float tilt_angle;
    bool state_changed;
};

class GimbalController {
private:
    GimbalState current_state_;
    unsigned long state_entered_ms_;
    unsigned long last_target_seen_ms_;
    GimbalPredictor &predictor_;

    void setState(GimbalState next_state, unsigned long now);

public:
    explicit GimbalController(GimbalPredictor &predictor);
    GimbalOutput update(const RadarTrack &track, unsigned long now);
    GimbalState getState() const;
};
