#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

static char driverValue[32];
static char propertyValue[32];
static char propertyName[128];
static char driverPath[128];
static int writes;
static char lastLog[512];
static int probeFailure;
static int propertyFailure;

int probeStat(const char *path, struct stat *info) {
    assert(strcmp(path, "/policy-probe") == 0);
    if (probeFailure == 1) {
        errno = ENOENT;
        return -1;
    }
    memset(info, 0, sizeof(*info));
    info->st_uid = 0;
    info->st_gid = 1004;
    info->st_mode = 0640;
    return 0;
}

ssize_t probeGetxattr(const char *path, const char *name, void *value, size_t size) {
    assert(strcmp(path, "/policy-probe") == 0);
    assert(strcmp(name, "security.selinux") == 0);
    if (probeFailure == 2) {
        errno = EACCES;
        return -1;
    }
    const char *context = "u:object_r:input_device:s0";
    size_t length = strlen(context);
    assert(length <= size);
    memcpy(value, context, length);
    return (ssize_t)length;
}

int probeOpen(const char *path, int flags, ...) {
    (void)flags;
    assert(strcmp(path, "/sys/kernel/debug/eink_debug/global_mode") == 0 ||
           strcmp(path, "/sys/kernel/debug/eink_debug/clean_a2") == 0 ||
           strcmp(path, "/sys/kernel/debug/eink_debug/anti_flicker") == 0);
    assert(strlen(path) < sizeof(driverPath));
    strcpy(driverPath, path);
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
    va_list arguments;
    va_start(arguments, format);
    vsnprintf(lastLog, sizeof(lastLog), format, arguments);
    va_end(arguments);
    return 0;
}

int __system_property_set(const char *name, const char *value) {
#ifdef HIBREAK_ENFORCING_CANDIDATE
    const char *refresh = "sys.hibreak.request.refresh_mode";
    const char *aod = "sys.hibreak.request.aod_invert";
#else
    const char *refresh = "vendor.xrz.global_refresh_mode";
    const char *aod = "persist.sys.hibreak.aod_invert";
#endif
    assert(strcmp(name, refresh) == 0 || strcmp(name, aod) == 0 ||
           strcmp(name, "vendor.xrz.auto_clean_enabled") == 0 ||
           strcmp(name, "sys.hibreak.eink_bridge.auto_refresh") == 0 ||
           strcmp(name, "sys.hibreak.eink_bridge.anti_flicker") == 0);
    assert(strlen(name) < sizeof(propertyName));
    strcpy(propertyName, name);
    assert(strlen(value) < sizeof(propertyValue));
    strcpy(propertyValue, value);
    return propertyFailure ? -1 : 0;
}

void startSideKeyMonitor(void) {}
#ifdef HIBREAK_SOCKET_AUTH
int hibreak_authorize_client(int socket_fd) {
    (void)socket_fd;
    return 0;
}
#endif

#define open probeOpen
#define write probeWrite
#define close probeClose
#define stat(path, info) probeStat(path, info)
#define getxattr probeGetxattr
#define main daemonMain
#include "../../../a9_eink_daemon/eink_daemon.c"
#undef main

int main(void) {
    const char *commands[] = {"s", "c", "b", "p", "h"};
    const char *values[] = {"2147483825", "180", "178", "179", "183"};
    for (size_t i = 0; i < sizeof(commands) / sizeof(commands[0]); i++) {
        int previousWrites = writes;
        processCommand(commands[i]);
#ifdef HIBREAK_PROPERTY_ONLY_REFRESH
        assert(writes == previousWrites);
#else
        assert(writes == previousWrites + 1);
        assert(strcmp(driverPath, "/sys/kernel/debug/eink_debug/global_mode") == 0);
        assert(strcmp(driverValue, values[i]) == 0);
#endif
        assert(strcmp(propertyValue, values[i]) == 0);
    }
    const char *controlCommands[] = {"au_br0", "au_br1", "an_fl0", "an_fl1"};
    const char *controlPaths[] = {
        "/sys/kernel/debug/eink_debug/clean_a2", "/sys/kernel/debug/eink_debug/clean_a2",
        "/sys/kernel/debug/eink_debug/anti_flicker", "/sys/kernel/debug/eink_debug/anti_flicker",
    };
    for (size_t i = 0; i < sizeof(controlCommands) / sizeof(controlCommands[0]); i++) {
        int previousWrites = writes;
        processCommand(controlCommands[i]);
#ifdef HIBREAK_INIT_EINK_BRIDGE
        assert(writes == previousWrites);
        assert(strcmp(propertyName, i < 2 ? "sys.hibreak.eink_bridge.auto_refresh" :
                      "sys.hibreak.eink_bridge.anti_flicker") == 0);
        assert(strcmp(propertyValue, i % 2 == 0 ? "0" : "1") == 0);
        continue;
#endif
#ifdef HIBREAK_PROPERTY_ONLY_AUTO_REFRESH
        if (i < 2) {
            assert(writes == previousWrites);
            assert(strcmp(propertyName, "vendor.xrz.auto_clean_enabled") == 0);
            assert(strcmp(propertyValue, i == 0 ? "0" : "1") == 0);
            continue;
        }
#endif
        assert(writes == previousWrites + 1);
        assert(strcmp(driverPath, controlPaths[i]) == 0);
        assert(strcmp(driverValue, i % 2 == 0 ? "0" : "1") == 0);
    }
    propertyFailure = 1;
#ifdef HIBREAK_INIT_EINK_BRIDGE
    processCommand("au_br1");
    assert(strstr(lastLog, "Failed to request init e-ink bridge") != NULL);
    processCommand("an_fl0");
    assert(strstr(lastLog, "Failed to request init e-ink bridge") != NULL);
    propertyFailure = 0;
    processCommand("au_br2");
    assert(strstr(lastLog, "Invalid init e-ink bridge value") != NULL);
    propertyFailure = 1;
#endif
#ifdef HIBREAK_PROPERTY_ONLY_AUTO_REFRESH
    processCommand("au_br1");
    assert(strstr(lastLog, "Failed to set vendor.xrz.auto_clean_enabled=1") != NULL);
    propertyFailure = 0;
    int beforeInvalid = writes;
    processCommand("au_br2");
    assert(writes == beforeInvalid);
    assert(strstr(lastLog, "Invalid property-only auto-refresh value: 2") != NULL);
    propertyFailure = 1;
#endif
    processCommand("c");
    assert(strstr(lastLog, "Failed to set vendor.xrz.global_refresh_mode=180") != NULL);
    propertyFailure = 0;
    assert(!valid_number("2147483825"));
    int previousWrites = writes;
    writeToEpdDisplayMode("2147483826");
    writeToEpdDisplayMode("not-a-mode");
    assert(writes == previousWrites);
    setAodInvert("0");
    assert(strcmp(propertyValue, "false") == 0);
    setAodInvert("1");
    assert(strcmp(propertyValue, "true") == 0);
    setAodInvert("2");
    assert(strcmp(propertyValue, "true") == 0);
    const char *destinations[] = {
        "vendor.xrz.global_refresh_mode", "persist.sys.hibreak.aod_invert",
        "sys.linevibrator_type", "sys.linevibrator_touch", "sys.wakeup_on_volume",
    };
#ifdef HIBREAK_ENFORCING_CANDIDATE
    const char *requests[] = {
        "sys.hibreak.request.refresh_mode", "sys.hibreak.request.aod_invert",
        "sys.hibreak.request.linevibrator_type", "sys.hibreak.request.linevibrator_touch",
        "sys.hibreak.request.wakeup_on_volume",
    };
    for (size_t i = 0; i < sizeof(destinations) / sizeof(destinations[0]); i++) {
        assert(strcmp(controlProperty(destinations[i]), requests[i]) == 0);
    }
    assert(controlProperty("unmapped.property") == NULL);
#else
    for (size_t i = 0; i < sizeof(destinations) / sizeof(destinations[0]); i++) {
        assert(strcmp(controlProperty(destinations[i]), destinations[i]) == 0);
    }
#endif
    logPolicyPath("/policy-probe");
    assert(strcmp(lastLog, "Policy probe: path=/policy-probe context=u:object_r:input_device:s0 uid=0 gid=1004 mode=0640") == 0);
    probeFailure = 1;
    logPolicyPath("/policy-probe");
    assert(strstr(lastLog, "cannot stat /policy-probe") != NULL);
    probeFailure = 2;
    logPolicyPath("/policy-probe");
    assert(strstr(lastLog, "cannot read label for /policy-probe") != NULL);
    return 0;
}
