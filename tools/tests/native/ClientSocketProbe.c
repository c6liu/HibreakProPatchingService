#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>

#include "../../../eink_daemon/client_auth.h"

static uid_t peer_uid = 10263;
static int peer_failure;
static int short_peer;
static const char *registry = "com.lmqr.eink_settings 10263 0 /data/user/0/app default 3003\n";
static int errors;

int __android_log_print(int priority, const char *tag, const char *format, ...) {
    (void)priority;
    (void)tag;
    (void)format;
    errors++;
    return 0;
}

int probe_getsockopt(int fd, int level, int name, void *value, socklen_t *length) {
    assert(fd == 42 && level == SOL_SOCKET && name == SO_PEERCRED);
    if (peer_failure) {
        errno = EIO;
        return -1;
    }
    struct ucred *peer = value;
    assert(*length == sizeof(*peer));
    peer->uid = peer_uid;
    if (short_peer) *length = 0;
    return 0;
}

FILE *probe_fopen(const char *path, const char *mode) {
    assert(strcmp(path, "/data/system/packages.list") == 0);
    assert(strcmp(mode, "re") == 0);
    if (registry == NULL) {
        errno = EACCES;
        return NULL;
    }
    return fmemopen((void *)registry, strlen(registry), "r");
}

int main(void) {
    assert(hibreak_authorize_client(42));
    peer_uid = 110263;
    assert(hibreak_authorize_client(42));
    peer_uid = 10264;
    assert(!hibreak_authorize_client(42) && errors == 1);
    peer_uid = 10263;
    registry = "com.lmqr.eink_settings 10263\nother.package 10263\n";
    assert(!hibreak_authorize_client(42) && errors == 2);
    registry = NULL;
    assert(!hibreak_authorize_client(42) && errors == 3);
    peer_failure = 1;
    assert(!hibreak_authorize_client(42) && errors == 4);
    peer_failure = 0;
    short_peer = 1;
    assert(!hibreak_authorize_client(42) && errors == 5);
    return 0;
}
