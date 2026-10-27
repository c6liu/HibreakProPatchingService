#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static char driverValue[32];
static char propertyValue[32];
static int writes;

int probeOpen(const char *path, int flags, ...) {
    (void)flags;
    assert(strcmp(path, "/sys/kernel/debug/eink_debug/global_mode") == 0);
    return 123;
}

ssize_t probeWrite(int fd, const void *value, size_t count) {
    assert(fd == 123);
    assert(count < sizeof(driverValue));
    memcpy(driverValue, value, count);
    driverValue[count] = '\0';
    writes++;
    return (ssize_t)count;
}

int probeClose(int fd) {
    assert(fd == 123);
    return 0;
}

int __android_log_print(int priority, const char *tag, const char *format, ...) {
    (void)priority;
    (void)tag;
    (void)format;
    return 0;
}

int __system_property_set(const char *name, const char *value) {
    assert(strcmp(name, "vendor.xrz.global_refresh_mode") == 0);
    assert(strlen(value) < sizeof(propertyValue));
    strcpy(propertyValue, value);
    return 0;
}

void startSideKeyMonitor(void) {}

#define open probeOpen
#define write probeWrite
#define close probeClose
#define main daemonMain
#include "../../../a9_eink_daemon/eink_daemon.c"
#undef main

int main(void) {
    const char *commands[] = {"s", "c", "b", "p", "h"};
    const char *values[] = {"2147483825", "180", "178", "179", "183"};
    for (size_t i = 0; i < sizeof(commands) / sizeof(commands[0]); i++) {
        int previousWrites = writes;
        processCommand(commands[i]);
        assert(writes == previousWrites + 1);
        assert(strcmp(driverValue, values[i]) == 0);
        assert(strcmp(propertyValue, values[i]) == 0);
    }
    assert(!valid_number("2147483825"));
    int previousWrites = writes;
    writeToEpdDisplayMode("2147483826");
    writeToEpdDisplayMode("not-a-mode");
    assert(writes == previousWrites);
    return 0;
}
