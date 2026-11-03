#ifndef TEST_JNI_H
#define TEST_JNI_H
#define JNIEXPORT
#define JNICALL
typedef void *jobject;
typedef const char *jstring;
typedef unsigned char jboolean;
typedef const struct JNINativeInterface *JNIEnv;
struct JNINativeInterface {
    jstring (*NewStringUTF)(JNIEnv *, const char *);
};
#endif
