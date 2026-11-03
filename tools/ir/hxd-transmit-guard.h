#ifndef HXD_TRANSMIT_GUARD_H
#define HXD_TRANSMIT_GUARD_H

#include <errno.h>
#include <time.h>

enum { HXD_TRANSMIT_GUARD_US = 120000 };

/* Finish the ownership guard even if a cancellation signal interrupts sleep. */
static int hxd_transmit_guard(unsigned int envelope_us) {
    unsigned int wait_us = envelope_us + HXD_TRANSMIT_GUARD_US;
    struct timespec delay = {
        .tv_sec = wait_us / 1000000U,
        .tv_nsec = (long)(wait_us % 1000000U) * 1000L,
    };
    while (nanosleep(&delay, &delay) < 0) {
        if (errno != EINTR)
            return -1;
    }
    return 0;
}

#endif
