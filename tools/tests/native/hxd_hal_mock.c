#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <hardware/consumerir.h>
#include <stdarg.h>
#include <stdio.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static int fake_open(const char *, int, ...);
static int fake_fstat(int, struct stat *);
static int fake_flock(int, int);
static ssize_t fake_write(int, const void *, size_t);
static int fake_close(int);
static int fake_nanosleep(const struct timespec *, struct timespec *);
#define open(...) fake_open(__VA_ARGS__)
#define fstat(...) fake_fstat(__VA_ARGS__)
#define flock(...) fake_flock(__VA_ARGS__)
#define write(...) fake_write(__VA_ARGS__)
#define close(...) fake_close(__VA_ARGS__)
#define nanosleep(...) fake_nanosleep(__VA_ARGS__)
#include "../../ir/consumerir-hxd.c"
#undef open
#undef fstat
#undef flock
#undef write
#undef close
#undef nanosleep

static int opens, writes, closes, sleeps, scenario;
static long sleep_us;
static int errors;
static int controller_open;

int __android_log_print(int priority, const char *tag, const char *format, ...) {
    (void)tag;
    (void)format;
    if (priority == ANDROID_LOG_ERROR)
        ++errors;
    return 0;
}

static int fake_open(const char *path, int flags, ...) {
    assert(strcmp(path, "/dev/ctrl") == 0 && flags == (O_RDWR | O_CLOEXEC | O_NOFOLLOW));
    ++opens;
    if (scenario == 1) {
        errno = EACCES;
        return -1;
    }
    assert(!controller_open);
    controller_open = 1;
    return 42;
}

static int fake_fstat(int fd, struct stat *status) {
    assert(fd == 42);
    if (scenario == 2) {
        errno = EIO;
        return -1;
    }
    status->st_mode = scenario == 3 ? S_IFREG : S_IFCHR;
    return 0;
}

static int fake_flock(int fd, int operation) {
    assert(fd == 42 && operation == (LOCK_EX | LOCK_NB));
    if (scenario == 4) {
        errno = EWOULDBLOCK;
        return -1;
    }
    return 0;
}

static ssize_t fake_write(int fd, const void *data, size_t count) {
    const unsigned char expected[] = {0x30, 0, 1, 0x0f, 0xf0, 0xea, 0xc7, 0, 0, 0xe1};
    assert(fd == 42 && count == sizeof(expected) && !memcmp(data, expected, count));
    ++writes;
    assert(writes == 1 || scenario == 10);
    if (scenario == 5) {
        errno = EINTR;
        return -1;
    }
    return scenario == 6 ? 4 : (ssize_t)count;
}

static int fake_close(int fd) {
    assert(fd == 42);
    ++closes;
    assert(controller_open);
    controller_open = 0;
    if (scenario == 7) {
        errno = EIO;
        return -1;
    }
    return 0;
}

static int fake_nanosleep(const struct timespec *delay, struct timespec *remaining) {
    ++sleeps;
    sleep_us = delay->tv_sec * 1000000L + delay->tv_nsec / 1000;
    if (scenario == 8 && sleeps == 1) {
        *remaining = (struct timespec){.tv_nsec = 1000000};
        errno = EINTR;
        return -1;
    }
    if (scenario == 9) {
        errno = EIO;
        return -1;
    }
    if (scenario == 10) {
        struct timespec pause = {.tv_nsec = 10000000};
        return nanosleep(&pause, NULL);
    }
    return 0;
}

struct request {
    consumerir_device_t *device;
    int *pattern;
};

static void *send_thread(void *argument) {
    struct request *request = argument;
    assert(request->device->transmit(request->device, 38000, request->pattern, 67) == 0);
    return NULL;
}

int main(void) {
    _Static_assert(sizeof(hw_module_t) == 248, "arm64 module ABI size");
    assert(HAL_MODULE_INFO_SYM.common.tag == HARDWARE_MODULE_TAG);
    assert(HAL_MODULE_INFO_SYM.common.module_api_version == CONSUMERIR_MODULE_API_VERSION_1_0);
    hw_device_t *common = (void *)1;
    assert(open_hal(&HAL_MODULE_INFO_SYM.common, "invalid", &common) == -EINVAL && common == NULL);
    assert(open_hal(&HAL_MODULE_INFO_SYM.common, CONSUMERIR_TRANSMITTER, NULL) == -EINVAL);
    assert(open_hal(&HAL_MODULE_INFO_SYM.common, CONSUMERIR_TRANSMITTER, &common) == 0);
    consumerir_device_t *device = (consumerir_device_t *)common;
    assert(device->common.tag == HARDWARE_DEVICE_TAG);
    consumerir_freq_range_t ranges[3] = {{0}, {0}, {1, 2}};
    assert(device->get_num_carrier_freqs(device) == 2);
    assert(device->get_carrier_freqs(device, 3, ranges) == 2);
    assert(ranges[0].min == 38000 && ranges[0].max == 38000);
    assert(ranges[1].min == 38222 && ranges[1].max == 38222 && ranges[2].min == 1);
    ranges[1].min = 1;
    assert(device->get_carrier_freqs(device, 1, ranges) == 1 && ranges[1].min == 1);
    assert(device->get_carrier_freqs(device, 0, ranges) == -EINVAL);
    assert(device->get_carrier_freqs(device, 1, NULL) == -EINVAL);
    int pattern[67] = {9000, 4500};
    const unsigned char bytes[4] = {0xea, 0xc7, 0x0f, 0xf0};
    int duration = 9000 + 4500 + 560;
    for (int bit = 0; bit < 32; ++bit) {
        pattern[2 + bit * 2] = 560;
        pattern[3 + bit * 2] = bytes[bit / 8] & (1 << (bit % 8)) ? 1690 : 560;
        duration += 560 + pattern[3 + bit * 2];
    }
    pattern[66] = 560;
    assert(device->transmit(device, 36000, pattern, 67) == -ENOTSUP && opens == 0);
    assert(device->transmit(device, 38000, pattern, -1) == -ENOTSUP && opens == 0);
    assert(device->transmit(device, 38000, NULL, 67) == -EINVAL && opens == 0);
    for (scenario = 0; scenario <= 9; ++scenario) {
        opens = writes = closes = sleeps = errors = 0;
        int result = device->transmit(device, scenario % 2 ? 38222 : 38000, pattern, 67);
        assert(result == 0 || result < 0);
        assert((result == 0) == (scenario == 0 || scenario == 8));
        assert(errors == (result == 0 ? 0 : 1));
        assert(opens == 1 && closes == (scenario == 1 ? 0 : 1));
        assert(writes == (scenario >= 1 && scenario <= 4 ? 0 : 1));
        if (scenario == 0)
            assert(sleep_us == duration + 120000 && sleeps == 1);
        if (scenario == 8)
            assert(sleeps == 2 && sleep_us == 1000);
        if (scenario >= 1 && scenario <= 6)
            assert(sleeps == 0);
    }
    scenario = 10;
    opens = writes = closes = sleeps = errors = 0;
    struct request request = {device, pattern};
    pthread_t first, second;
    assert(pthread_create(&first, NULL, send_thread, &request) == 0);
    assert(pthread_create(&second, NULL, send_thread, &request) == 0);
    assert(pthread_join(first, NULL) == 0 && pthread_join(second, NULL) == 0);
    assert(opens == 2 && writes == 2 && closes == 2 && sleeps == 2 && errors == 0);
    assert(common->close(common) == 0);
    return 0;
}
