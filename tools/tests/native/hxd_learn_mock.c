#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static int fake_open(const char *path, int flags, ...);
static int fake_close(int fd);
static int fake_fstat(int fd, struct stat *status);
static int fake_flock(int fd, int operation);
static ssize_t fake_read(int fd, void *buffer, size_t count);
static ssize_t fake_write(int fd, const void *buffer, size_t count);
static int fake_clock_gettime(clockid_t clock, struct timespec *now);
static int fake_nanosleep(const struct timespec *delay, struct timespec *remaining);
static int fake_fsync(int fd);
static int fake_unlink(const char *path);

#define open fake_open
#define close fake_close
#define fstat fake_fstat
#define flock fake_flock
#define read fake_read
#define write fake_write
#define clock_gettime fake_clock_gettime
#define nanosleep fake_nanosleep
#define fsync fake_fsync
#define unlink fake_unlink
#define main capture_main
#include "../../hxd-learn.c"
#undef open
#undef close
#undef fstat
#undef flock
#undef read
#undef write
#undef clock_gettime
#undef nanosleep
#undef fsync
#undef unlink
#undef main

enum { DEVICE = 10000 };
static const char *scenario;
static size_t record_size;
static int command_count;
static int read_count;
static int device_opens;
static int file_fd = -1;
static bool device_open;
static double current_time = 1000;

static bool is(const char *name) {
    return strcmp(scenario, name) == 0;
}

static const char *service_path(const char *path) {
    static char mapped[4096];
    const char *directory = getenv("HXD_TEST_SERVICE_DIR");
    const char *prefix = "/data/misc/hibreak-ir/";
    if (!directory || strncmp(path, prefix, strlen(prefix)) != 0)
        return path;
    int length = snprintf(mapped, sizeof(mapped), "%s/%s", directory, path + strlen(prefix));
    assert(length > 0 && (size_t)length < sizeof(mapped));
    return mapped;
}

static int fake_unlink(const char *path) {
    return unlink(service_path(path));
}

static int fake_open(const char *path, int flags, ...) {
    if (strcmp(path, "/dev/ctrl") != 0) {
        file_fd = open(service_path(path), flags, 0600);
        return file_fd;
    }
    ++device_opens;
    assert(!is("no-device"));
    if (is("open-denied")) {
        errno = EACCES;
        return -1;
    }
    assert(flags & O_RDWR);
    device_open = true;
    return DEVICE;
}

static int fake_close(int fd) {
    if (fd != DEVICE)
        return close(fd);
    assert(device_open);
    device_open = false;
    return 0;
}

static int fake_fstat(int fd, struct stat *status) {
    assert(fd == DEVICE);
    memset(status, 0, sizeof(*status));
    status->st_mode = is("not-char") ? S_IFREG : S_IFCHR;
    return 0;
}

static int fake_flock(int fd, int operation) {
    assert(fd == DEVICE && operation == (LOCK_EX | LOCK_NB));
    if (is("busy")) {
        errno = EWOULDBLOCK;
        return -1;
    }
    return 0;
}

static ssize_t fake_write(int fd, const void *buffer, size_t count) {
    if (fd != DEVICE) {
        assert(fd == file_fd);
        if (is("save-error")) {
            errno = ENOSPC;
            return -1;
        }
        if (is("save-zero"))
            return 0;
        if (is("save-partial") && count > 7)
            count = 7;
        return write(fd, buffer, count);
    }
    assert(device_open);
    if (strncmp(scenario, "tx-", 3) == 0) {
        static const unsigned char expected[] = {0x30, 0x00, 0x01, 0x1c, 0xe3, 0x00, 0xff, 0x20, 0x88, 0xd7};
        assert(count == sizeof(expected) && memcmp(buffer, expected, count) == 0);
        assert(++command_count <= 5 && read_count == 0);
        if (is("tx-error")) {
            errno = EIO;
            return -1;
        }
        if (is("tx-partial"))
            return 4;
        if (is("tx-cancel"))
            on_signal(SIGTERM);
        return (ssize_t)count;
    }
    assert(++command_count == 1);
    const unsigned char *command = buffer;
    assert(count == 3 && command[0] == 0x30);
    assert((command[1] == 0x20 && command[2] == 0x50) ||
           (command[1] == 0x10 && command[2] == 0x40));
    record_size = command[1] == 0x20 ? 230 : 110;
    if (is("write-error")) {
        errno = EPERM;
        return -1;
    }
    if (is("write-interrupted")) {
        errno = EINTR;
        return -1;
    }
    if (is("write-partial"))
        return 2;
    return 3;
}

static ssize_t fake_read(int fd, void *buffer, size_t count) {
    assert(fd == DEVICE && device_open && command_count == 1);
    assert(count == record_size);
    ++read_count;
    current_time += 0.01;
    if (is("timeout"))
        return 0;
    if (is("delayed") && read_count < 3)
        return 0;
    if (is("read-error")) {
        errno = EPERM;
        return -1;
    }
    if (is("cancel")) {
        on_signal(SIGINT);
        errno = EINTR;
        return -1;
    }
    if (is("late"))
        current_time += 60;
    unsigned char *data = buffer;
    for (size_t i = 0; i < count; ++i)
        data[i] = (unsigned char)i;
    if (is("bad-status"))
        data[0] = 1;
    if (is("all-zero"))
        memset(data, 0, count);
    if (is("no-signal") || is("near-no-signal")) {
        assert(count == 230);
        memset(data, 0, count);
        data[1] = 0x88;
        data[2] = 0x99;
        data[3] = 0xaa;
        memset(data + 5, 0xff, 32);
        data[227] = 0xf2;
        data[228] = 0xe1;
        data[229] = is("near-no-signal") ? 0x50 : 0x51;
    }
    return is("read-partial") ? (ssize_t)count - 1 : (ssize_t)count;
}

static int fake_clock_gettime(clockid_t clock, struct timespec *now) {
    assert(clock == CLOCK_MONOTONIC);
    now->tv_sec = (time_t)current_time;
    now->tv_nsec = (long)((current_time - (double)now->tv_sec) * 1000000000);
    return 0;
}

static int fake_nanosleep(const struct timespec *delay, struct timespec *remaining) {
    (void)remaining;
    assert(delay->tv_sec == 0 && delay->tv_nsec >= 0 && delay->tv_nsec <= 200000000);
    current_time += (double)delay->tv_nsec / 1000000000.0 + 0.000001;
    return 0;
}

static int fake_fsync(int fd) {
    if (is("fsync-error")) {
        errno = EIO;
        return -1;
    }
    return fsync(fd);
}

int main(int argc, char **argv) {
    scenario = getenv("HXD_TEST_SCENARIO");
    assert(scenario);
    int result = capture_main(argc, argv);
    assert(!device_open);
    if (is("no-device"))
        assert(device_opens == 0);
    if (is("open-denied") || is("not-char") || is("busy"))
        assert(command_count == 0);
    if (is("write-partial") || is("write-error") || is("write-interrupted"))
        assert(command_count == 1 && read_count == 0);
    if (is("tx-success"))
        assert(command_count == 5 && read_count == 0 && current_time >= 1004);
    if (is("tx-error") || is("tx-partial") || is("tx-cancel"))
        assert(command_count == 1 && read_count == 0);
    return result;
}
