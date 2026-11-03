#include <jni.h>
#include <stdio.h>
#include <string.h>
#include <sys/system_properties.h>
#include <time.h>

static char token[24];
static double started;

static double monotonic(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0)
        return -1;
    return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
}

JNIEXPORT jstring JNICALL
Java_com_hibreak_irremote_MainActivity_request(JNIEnv *env, jobject activity) {
    (void)activity;
    started = monotonic();
    if (started < 0)
        return (*env)->NewStringUTF(env, "Cannot read monotonic clock. Nothing requested.");
    snprintf(token, sizeof(token), "%llu", (unsigned long long)(started * 1000000000.0));
    if (__system_property_set("debug.hibreak.ir_tcl_request", token) < 0)
        return (*env)->NewStringUTF(env, "Cannot request IR transmission. Install the matching ROM image; check SELinux/property-service logs.");
    return NULL;
}

JNIEXPORT jstring JNICALL
Java_com_hibreak_irremote_MainActivity_poll(JNIEnv *env, jobject activity) {
    (void)activity;
    char value[PROP_VALUE_MAX];
    __system_property_get("debug.hibreak.ir_tcl_result", value);
    size_t length = strlen(token);
    if (strncmp(value, token, length) == 0 && value[length] == ':') {
        const char *status = value + length + 1;
        if (strcmp(status, "written") == 0)
            return (*env)->NewStringUTF(env, "One command written. Did TV volume increase? TV response is not verified.");
        if (strcmp(status, "failed") == 0)
            return (*env)->NewStringUTF(env, "Service failed; transmission may have occurred. Inspect the ROM service result. No automatic retry.");
        return (*env)->NewStringUTF(env, "Unexpected service response. No automatic retry.");
    }
    double now = monotonic();
    if (now < 0 || now - started >= 10)
        return (*env)->NewStringUTF(env, "No matching service result within 10 seconds. Transmission is unknown; no automatic retry.");
    return NULL;
}
