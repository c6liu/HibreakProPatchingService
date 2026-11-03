#ifndef HXD_NEC_H
#define HXD_NEC_H

#include <stddef.h>
#include <stdint.h>

enum { HXD_NEC_PACKET_SIZE = 10, HXD_NEC_FREQUENCY = 38000, HXD_NEC_FREQUENCY_ALIAS = 38222 };

int hxd_nec_encode(int frequency, const int *pattern, size_t count,
                   uint8_t packet[HXD_NEC_PACKET_SIZE], unsigned int *duration_us);

#endif
