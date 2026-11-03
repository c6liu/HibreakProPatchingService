#include "hxd-nec.h"

#include <errno.h>
#include <string.h>

static int near(int value, int nominal) {
    return value >= nominal * 85 / 100 && value <= nominal * 115 / 100;
}

int hxd_nec_encode(int frequency, const int *pattern, size_t count,
                   uint8_t packet[HXD_NEC_PACKET_SIZE], unsigned int *duration_us) {
    if (!pattern || !packet || !duration_us)
        return -EINVAL;
    if ((frequency != HXD_NEC_FREQUENCY && frequency != HXD_NEC_FREQUENCY_ALIAS) ||
        (count != 67 && count != 68))
        return -ENOTSUP;
    unsigned int duration = 0;
    for (size_t i = 0; i < count; ++i) {
        if (pattern[i] <= 0 || (unsigned int)pattern[i] > 2000000U - duration)
            return -EINVAL;
        duration += (unsigned int)pattern[i];
    }
    if (!near(pattern[0], 9000) || !near(pattern[1], 4500) || !near(pattern[66], 560))
        return -ENOTSUP;
    uint8_t data[4] = {0};
    for (size_t bit = 0; bit < 32; ++bit) {
        if (!near(pattern[2 + bit * 2], 560))
            return -ENOTSUP;
        int space = pattern[3 + bit * 2];
        if (near(space, 1690))
            data[bit / 8] |= (uint8_t)(1U << (bit % 8));
        else if (!near(space, 560))
            return -ENOTSUP;
    }
    if ((data[2] ^ data[3]) != 0xff)
        return -ENOTSUP;
    /* A final idle gap is allowed, but must not resemble another data interval. */
    if (count == 68 && pattern[67] < 10000)
        return -ENOTSUP;
    uint8_t result[HXD_NEC_PACKET_SIZE] = {
        0x30, 0x00, 0x01, data[2], data[3], data[0], data[1], 0x00, 0x00, 0x00,
    };
    for (size_t i = 0; i + 1 < sizeof(result); ++i)
        result[sizeof(result) - 1] = (uint8_t)(result[sizeof(result) - 1] + result[i]);
    memcpy(packet, result, sizeof(result));
    *duration_us = duration;
    return 0;
}
