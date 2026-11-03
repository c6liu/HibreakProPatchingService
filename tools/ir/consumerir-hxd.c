#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include <hardware/consumerir.h>
#include <android/log.h>

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "hxd-nec.h"

static pthread_mutex_t transmit_mutex = PTHREAD_MUTEX_INITIALIZER;

static int fail(const char *operation, int error) {
    __android_log_print(ANDROID_LOG_ERROR, "HibreakIR", "HXD NEC adapter: %s: %s (%d)",
                        operation, strerror(error), error);
    return -error;
}

static int transmit(consumerir_device_t *device, int frequency, const int *pattern, int count) {
    (void)device;
    uint8_t packet[HXD_NEC_PACKET_SIZE];
    unsigned int duration;
    int result = hxd_nec_encode(frequency, pattern, count < 0 ? 0 : (size_t)count, packet, &duration);
    if (result < 0) {
        __android_log_print(ANDROID_LOG_ERROR, "HibreakIR",
            "Rejected request: frequency=%d Hz durations=%d; expected 38000/38222 Hz, one NEC frame",
            frequency, count);
        return fail("unsupported/invalid waveform", -result);
    }
    result = pthread_mutex_lock(&transmit_mutex);
    if (result)
        return fail("lock transmitter", result);
    int fd = open("/dev/ctrl", O_RDWR | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) {
        result = fail("open /dev/ctrl", errno);
        goto unlock;
    }
    struct stat status;
    if (fstat(fd, &status) < 0) {
        result = fail("stat controller", errno);
        goto close_device;
    }
    if (!S_ISCHR(status.st_mode)) {
        result = fail("controller is not a character device", ENODEV);
        goto close_device;
    }
    if (flock(fd, LOCK_EX | LOCK_NB) < 0) {
        result = fail("controller busy", errno);
        goto close_device;
    }
    ssize_t written = write(fd, packet, sizeof(packet));
    if (written != (ssize_t)sizeof(packet)) {
        result = fail("packet write failed/partial; NOT retried", written < 0 ? errno : EIO);
        goto close_device;
    }
    /*
     * The controller exposes no completion/ACK result. Hold ownership for the
     * requested envelope plus a conservative 120 ms guard after the bus write.
     * This is experimental pacing, not measured optical completion.
     */
    struct timespec delay = {
        .tv_sec = (duration + 120000U) / 1000000U,
        .tv_nsec = (long)((duration + 120000U) % 1000000U) * 1000L,
    };
    while (nanosleep(&delay, &delay) < 0) {
        if (errno != EINTR) {
            result = fail("transmit pacing", errno);
            goto close_device;
        }
    }
    __android_log_print(ANDROID_LOG_INFO, "HibreakIR",
          "HXD NEC adapter: request=%d Hz -> built-in NEC carrier; one packet written, address=%02x%02x command=%02x; optical completion unverified",
          frequency, packet[5], packet[6], packet[3]);
    result = 0;
close_device:
    if (close(fd) < 0)
        result = fail("close controller", errno);
unlock:
    {
        int error = pthread_mutex_unlock(&transmit_mutex);
        if (error)
            result = fail("unlock transmitter", error);
    }
    return result;
}

static int num_frequencies(consumerir_device_t *device) {
    (void)device;
    return 2;
}

static int frequencies(consumerir_device_t *device, size_t count, consumerir_freq_range_t *ranges) {
    (void)device;
    if (!count || !ranges)
        return fail("invalid frequency output", EINVAL);
    ranges[0] = (consumerir_freq_range_t){HXD_NEC_FREQUENCY, HXD_NEC_FREQUENCY};
    if (count > 1)
        ranges[1] = (consumerir_freq_range_t){HXD_NEC_FREQUENCY_ALIAS, HXD_NEC_FREQUENCY_ALIAS};
    return count > 1 ? 2 : 1;
}

static int close_hal(hw_device_t *device) {
    free(device);
    return 0;
}

static int open_hal(const hw_module_t *module, const char *name, hw_device_t **output) {
    if (!output)
        return fail("null device output", EINVAL);
    *output = NULL;
    if (!name || strcmp(name, CONSUMERIR_TRANSMITTER) != 0)
        return fail("unknown device name", EINVAL);
    consumerir_device_t *device = calloc(1, sizeof(*device));
    if (!device)
        return fail("allocate HAL device", ENOMEM);
    device->common.tag = HARDWARE_DEVICE_TAG;
    device->common.version = HARDWARE_DEVICE_API_VERSION(1, 0);
    device->common.module = (hw_module_t *)module;
    device->common.close = close_hal;
    device->transmit = transmit;
    device->get_num_carrier_freqs = num_frequencies;
    device->get_carrier_freqs = frequencies;
    *output = &device->common;
    __android_log_print(ANDROID_LOG_INFO, "HibreakIR",
          "HXD experimental NEC adapter loaded: 38000/38222 Hz nominal aliases -> built-in NEC carrier; single-frame NEC/NECext only");
    return 0;
}

static hw_module_methods_t methods = {.open = open_hal};

consumerir_module_t HAL_MODULE_INFO_SYM = {
    .common = {
        .tag = HARDWARE_MODULE_TAG,
        .module_api_version = CONSUMERIR_MODULE_API_VERSION_1_0,
        .hal_api_version = HARDWARE_HAL_API_VERSION,
        .id = CONSUMERIR_HARDWARE_MODULE_ID,
        .name = "HiBreak experimental NEC to HXD adapter",
        .author = "HiBreakProPatchingService",
        .methods = &methods,
    },
};
