#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int fake_clock_gettime(clockid_t clock, struct timespec *now);
#define clock_gettime fake_clock_gettime
#include "../../ir/remote/remote-jni.c"
#undef clock_gettime

static time_t seconds = 100;
static int property_error;
static char response[PROP_VALUE_MAX];
static char last_request[PROP_VALUE_MAX];
static char message[256];

static jstring new_string(JNIEnv *env, const char *value) {
    (void)env;
    assert(strlen(value) < sizeof(message));
    strcpy(message, value);
    return message;
}

static int fake_clock_gettime(clockid_t clock, struct timespec *now) {
    assert(clock == CLOCK_MONOTONIC);
    *now = (struct timespec){.tv_sec = seconds};
    return 0;
}

int __system_property_set(const char *name, const char *value) {
    assert(strcmp(name, "debug.hibreak.ir_tcl_request") == 0);
    assert(strlen(value) < sizeof(last_request));
    strcpy(last_request, value);
    errno = EACCES;
    return property_error;
}

int __system_property_get(const char *name, char *value) {
    assert(strcmp(name, "debug.hibreak.ir_tcl_result") == 0);
    strcpy(value, response);
    return (int)strlen(value);
}

int main(void) {
    const struct JNINativeInterface methods = {.NewStringUTF = new_string};
    JNIEnv env = &methods;
    property_error = -1;
    assert(strstr(Java_com_hibreak_irremote_MainActivity_request(&env, NULL), "Cannot request"));
    property_error = 0;
    assert(Java_com_hibreak_irremote_MainActivity_request(&env, NULL) == NULL);
    assert(strcmp(last_request, "100000000000") == 0);
    strcpy(response, "999:written");
    assert(Java_com_hibreak_irremote_MainActivity_poll(&env, NULL) == NULL);
    strcpy(response, "100000000000:written");
    assert(strstr(Java_com_hibreak_irremote_MainActivity_poll(&env, NULL), "TV response is not verified"));
    strcpy(response, "100000000000:failed");
    assert(strstr(Java_com_hibreak_irremote_MainActivity_poll(&env, NULL), "may have occurred"));
    strcpy(response, "100000000000:unexpected");
    assert(strstr(Java_com_hibreak_irremote_MainActivity_poll(&env, NULL), "Unexpected"));
    response[0] = '\0';
    seconds += 10;
    assert(strstr(Java_com_hibreak_irremote_MainActivity_poll(&env, NULL), "within 10 seconds"));
    assert(strcmp(last_request, "100000000000") == 0);
    return 0;
}
