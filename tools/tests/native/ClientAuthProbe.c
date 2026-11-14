#define _GNU_SOURCE
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "../../../eink_daemon/client_auth.h"

int __android_log_print(int priority, const char *tag, const char *format, ...) {
    (void)priority;
    (void)tag;
    (void)format;
    return 0;
}

static int matches(const char *text, uid_t uid) {
    FILE *stream = fmemopen((void *)text, strlen(text), "r");
    assert(stream != NULL);
    int result = hibreak_package_uid_matches(stream, uid);
    assert(fclose(stream) == 0);
    return result;
}

int main(void) {
    const char *valid = "other.package 10123 0 /data/user/0/other default 3003\n"
                        "com.lmqr.eink_settings 10263 0 /data/user/0/app default 3003\n";
    assert(matches(valid, 10263));
    assert(matches(valid, 110263));
    assert(!matches(valid, 10264));
    assert(!matches(valid, 263));
    assert(!matches("", 10263));
    assert(!matches("com.lmqr.eink_settings 10263\nother.package 10263\n", 10263));
    assert(!matches("com.lmqr.eink_settings 10263\ncom.lmqr.eink_settings 10263\n", 10263));
    assert(!matches("com.lmqr.eink_settings 10264\nother.package 10263\n", 10263));
    assert(!matches("com.lmqr.eink_settings 10263x\n", 10263));
    assert(!matches("com.lmqr.eink_settings -10263\n", 10263));
    assert(!matches("com.lmqr.eink_settings 10263\nmalformed\n", 10263));
    return 0;
}
