#include "Ld2451Parser.h"

#include <string.h>

namespace {
constexpr uint8_t Header[] = {0xF4, 0xF3, 0xF2, 0xF1};
constexpr uint8_t Tail[] = {0xF8, 0xF7, 0xF6, 0xF5};
constexpr float KmhToMps = 1000.0f / 3600.0f;

int selectedScore(const Ld2451Target &target) {
    int score = 0;
    score += target.approach ? 10000 : 0;
    score += static_cast<int>(target.snr) * 20;
    score += 100 - static_cast<int>(target.range_m);
    return score;
}
}  // namespace

Ld2451Parser::Ld2451Parser() {
    reset();
}

void Ld2451Parser::resetFrame() {
    memset(&frame_, 0, sizeof(frame_));
}

void Ld2451Parser::reset() {
    state_ = WAIT_HEADER;
    header_index_ = 0;
    tail_index_ = 0;
    payload_length_ = 0;
    payload_index_ = 0;
    memset(payload_, 0, sizeof(payload_));
    resetFrame();
}

const Ld2451Frame &Ld2451Parser::frame() const {
    return frame_;
}

bool Ld2451Parser::feed(uint8_t byte_in) {
    switch (state_) {
        case WAIT_HEADER:
            if (byte_in == Header[header_index_]) {
                header_index_++;
                if (header_index_ == sizeof(Header)) {
                    state_ = READ_LEN0;
                    header_index_ = 0;
                }
            } else {
                header_index_ = byte_in == Header[0] ? 1 : 0;
            }
            break;

        case READ_LEN0:
            payload_length_ = byte_in;
            state_ = READ_LEN1;
            break;

        case READ_LEN1:
            payload_length_ |= static_cast<uint16_t>(byte_in) << 8;
            if (payload_length_ > sizeof(payload_)) {
                reset();
            } else if (payload_length_ == 0) {
                state_ = READ_TAIL;
                tail_index_ = 0;
            } else {
                payload_index_ = 0;
                state_ = READ_PAYLOAD;
            }
            break;

        case READ_PAYLOAD:
            payload_[payload_index_++] = byte_in;
            if (payload_index_ >= payload_length_) {
                state_ = READ_TAIL;
                tail_index_ = 0;
            }
            break;

        case READ_TAIL:
            if (byte_in == Tail[tail_index_]) {
                tail_index_++;
                if (tail_index_ == sizeof(Tail)) {
                    const bool parsed = parsePayload();
                    state_ = WAIT_HEADER;
                    tail_index_ = 0;
                    payload_length_ = 0;
                    payload_index_ = 0;
                    return parsed;
                }
            } else {
                reset();
            }
            break;
    }
    return false;
}

bool Ld2451Parser::parsePayload() {
    Ld2451Frame parsed = {};
    parsed.valid = true;

    if (payload_length_ == 0) {
        frame_ = parsed;
        return true;
    }
    if (payload_length_ < 2) {
        return false;
    }

    parsed.target_count = payload_[0];
    parsed.alarm = payload_[1] == 0x01;
    const uint16_t expectedLength = 2 + static_cast<uint16_t>(parsed.target_count) * 5;
    if (payload_length_ != expectedLength) {
        return false;
    }

    const uint8_t storedTargets = min<uint8_t>(parsed.target_count, Ld2451MaxTargets);
    int bestIndex = -1;
    int bestScore = -32768;
    for (uint8_t i = 0; i < storedTargets; ++i) {
        const uint16_t offset = 2 + i * 5;
        Ld2451Target target = {};
        target.valid = true;
        target.angle_deg = static_cast<int8_t>(payload_[offset] - 0x80);
        target.range_m = payload_[offset + 1];
        target.approach = payload_[offset + 2] == 0x00;
        target.speed_kmh = payload_[offset + 3];
        target.snr = payload_[offset + 4];
        parsed.targets[i] = target;

        const int score = selectedScore(target);
        if (score > bestScore) {
            bestScore = score;
            bestIndex = i;
        }
    }

    if (bestIndex >= 0) {
        parsed.selected = parsed.targets[bestIndex];
    }
    frame_ = parsed;
    return true;
}
