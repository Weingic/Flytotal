#pragma once

#include <Arduino.h>

#include "SharedData.h"

class TrackManager {
private:
    RadarTrack current_track_;
    uint32_t next_track_id_;
    float last_measurement_x_;
    float last_measurement_y_;
    unsigned long last_measurement_ms_;

    void resetTrack(unsigned long now, float x_mm, float y_mm);

public:
    TrackManager();
    const RadarTrack &updateTrack(float x_mm, float y_mm, unsigned long now);
    const RadarTrack &refresh(unsigned long now);
    const RadarTrack &getTrack() const;
};
