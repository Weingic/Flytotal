#pragma once

#include <Arduino.h>

constexpr uint8_t Ld2451MaxTargets = 8;

struct Ld2451Target {
    bool valid;
    int8_t angle_deg;
    uint16_t range_m;
    bool approach;
    uint16_t speed_kmh;
    uint8_t snr;
};

struct Ld2451Frame {
    bool valid;
    bool alarm;
    uint8_t target_count;
    Ld2451Target targets[Ld2451MaxTargets];
    Ld2451Target selected;
};

struct Ld2451ParserStats {
    uint32_t ok;
    uint32_t rejected;
    uint32_t bad_length;
    uint32_t bad_tail;
    uint32_t bad_payload;
    uint32_t invalid_field;
    uint32_t crc_error_count;
};

class Ld2451Parser {
public:
    Ld2451Parser();
    bool feed(uint8_t byte_in);
    const Ld2451Frame &frame() const;
    const Ld2451ParserStats &stats() const;
    void resetStats();
    void reset();

private:
    enum State {
        WAIT_HEADER,
        READ_LEN0,
        READ_LEN1,
        READ_PAYLOAD,
        READ_TAIL
    };

    State state_;
    uint8_t header_index_;
    uint8_t tail_index_;
    uint16_t payload_length_;
    uint16_t payload_index_;
    uint8_t payload_[64];
    Ld2451Frame frame_;
    Ld2451ParserStats stats_;

    bool parsePayload();
    void resetFrame();
    void rejectBadLength();
    void rejectBadTail();
    void rejectBadPayload();
    void rejectInvalidField();
    void rejectCrcError();
};
