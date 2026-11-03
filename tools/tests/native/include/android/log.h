#ifndef TEST_ANDROID_LOG_H
#define TEST_ANDROID_LOG_H
enum { ANDROID_LOG_INFO = 4, ANDROID_LOG_ERROR = 6 };
int __android_log_print(int priority, const char *tag, const char *format, ...);
#endif
