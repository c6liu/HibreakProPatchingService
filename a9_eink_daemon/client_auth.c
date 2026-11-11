#define _GNU_SOURCE
#include "client_auth.h"

#include <android/log.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>

#define PACKAGE_NAME "com.lmqr.ha9_comp_service"
#define ANDROID_USER_OFFSET 100000U
#define ANDROID_APP_START 10000U
#define ANDROID_APP_END 19999U

int hibreak_package_uid_matches(FILE *packages, uid_t uid) {
    unsigned int appid = uid % ANDROID_USER_OFFSET;
    if (appid < ANDROID_APP_START || appid > ANDROID_APP_END) return 0;
    char *line = NULL;
    size_t capacity = 0;
    unsigned int matches = 0;
    int found = 0;
    while (getline(&line, &capacity, packages) >= 0) {
        char *save = NULL;
        char *name = strtok_r(line, " \t\r\n", &save);
        char *number = strtok_r(NULL, " \t\r\n", &save);
        if (name == NULL || number == NULL || *number < '0' || *number > '9') {
            free(line);
            return 0;
        }
        errno = 0;
        char *end;
        unsigned long parsed = strtoul(number, &end, 10);
        if (errno != 0 || *end != '\0' || parsed > UINT_MAX) {
            free(line);
            return 0;
        }
        if (parsed == appid) {
            matches++;
            if (strcmp(name, PACKAGE_NAME) == 0) found++;
        } else if (strcmp(name, PACKAGE_NAME) == 0) {
            free(line);
            return 0;
        }
    }
    int result = !ferror(packages) && matches == 1 && found == 1;
    free(line);
    return result;
}

int hibreak_authorize_client(int socket_fd) {
    struct ucred peer;
    socklen_t length = sizeof(peer);
    if (getsockopt(socket_fd, SOL_SOCKET, SO_PEERCRED, &peer, &length) != 0 ||
        length != sizeof(peer)) {
        __android_log_print(ANDROID_LOG_ERROR, "a9EinkService", "Cannot read socket peer credentials");
        return 0;
    }
    FILE *packages = fopen("/data/system/packages.list", "re");
    if (packages == NULL) {
        __android_log_print(ANDROID_LOG_ERROR, "a9EinkService",
                            "Cannot open package registry: %s", strerror(errno));
        return 0;
    }
    int authorized = hibreak_package_uid_matches(packages, peer.uid);
    if (fclose(packages) != 0) {
        __android_log_print(ANDROID_LOG_ERROR, "a9EinkService",
                            "Cannot close package registry: %s", strerror(errno));
        return 0;
    }
    if (!authorized) {
        __android_log_print(ANDROID_LOG_ERROR, "a9EinkService",
                            "Rejected socket client uid=%u", (unsigned int)peer.uid);
    }
    return authorized;
}
