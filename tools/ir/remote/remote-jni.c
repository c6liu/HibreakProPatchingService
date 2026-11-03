#include <jni.h>
#include <stdio.h>
#include <string.h>
#include <sys/system_properties.h>
#include <time.h>
#include <stdlib.h>

static char token[24];
static double started;

static int service_running(void) {
    char state[PROP_VALUE_MAX];
    __system_property_get("init.svc.hibreak_ir_tcl", state);
    return strcmp(state, "running") == 0 || strcmp(state, "restarting") == 0;
}

static double monotonic(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0)
        return -1;
    return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
}

JNIEXPORT jboolean JNICALL
Java_com_hibreak_irremote_MainActivity_isPending(JNIEnv *env, jobject activity) {
    (void)env;
    (void)activity;
    char request[PROP_VALUE_MAX], result[PROP_VALUE_MAX];
    __system_property_get("debug.hibreak.ir_tcl_request", request);
    size_t length = strlen(request);
    if (!length || length > 20 || strspn(request, "0123456789") != length)
        return service_running();
    double request_time = strtod(request, NULL) / 1000000000.0;
    double now = monotonic();
    __system_property_get("debug.hibreak.ir_tcl_result", result);
    int running = service_running();
    int complete = strncmp(result, request, length) == 0 && result[length] == ':';
    if (running || (!complete && (now < 0 || now - request_time < 10))) {
        memcpy(token, request, length + 1);
        started = request_time;
        return 1;
    }
    return 0;
}

JNIEXPORT jstring JNICALL
Java_com_hibreak_irremote_MainActivity_request(JNIEnv *env, jobject activity) {
    if (Java_com_hibreak_irremote_MainActivity_isPending(env, activity))
        return (*env)->NewStringUTF(env, "Previous IR request is still pending. No new request sent.");
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
    if (service_running())
        return NULL;
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
