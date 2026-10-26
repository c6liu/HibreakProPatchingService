#include <android/log.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/input.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, "A9SideKeys", __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, "A9SideKeys", __VA_ARGS__)

#ifndef SIDE_KEY_PACKAGE
#define SIDE_KEY_PACKAGE "com.lmqr.ha9_comp_service"
#endif

static int openSideKeys(void) {
    DIR *devices = opendir("/dev/input");
    if (devices == NULL) {
        LOGE("Cannot list input devices: %s", strerror(errno));
        return -1;
    }
    int fd = -1;
    struct dirent *entry;
    while ((entry = readdir(devices)) != NULL) {
        if (strncmp(entry->d_name, "event", 5) != 0) continue;
        char path[sizeof("/dev/input/") + sizeof(entry->d_name)];
        snprintf(path, sizeof(path), "/dev/input/%s", entry->d_name);
        int candidate = open(path, O_RDONLY | O_CLOEXEC);
        if (candidate < 0) {
            LOGE("Cannot open %s: %s", path, strerror(errno));
            continue;
        }
        char name[80] = {0};
        if (ioctl(candidate, EVIOCGNAME(sizeof(name)), name) < 0) {
            LOGE("Cannot identify %s: %s", path, strerror(errno));
        } else if (strcmp(name, "mtk-kpd") == 0) {
            int clock = CLOCK_MONOTONIC;
            if (ioctl(candidate, EVIOCSCLOCKID, &clock) == 0) {
                LOGI("Monitoring side keys on %s", path);
                fd = candidate;
                break;
            }
            LOGE("Cannot select monotonic input clock: %s", strerror(errno));
        }
        close(candidate);
    }
    closedir(devices);
    if (fd < 0) LOGE("HiBreak mtk-kpd side-key device unavailable");
    return fd;
}

static void sendSideKey(const struct input_event *event) {
    char scanCode[8], action[4], eventTime[24];
    snprintf(scanCode, sizeof(scanCode), "%u", event->code);
    snprintf(action, sizeof(action), "%d", event->value == 0 ? 1 : 0);
    int64_t milliseconds = (int64_t)event->time.tv_sec * 1000 + event->time.tv_usec / 1000;
    snprintf(eventTime, sizeof(eventTime), "%" PRId64, milliseconds);
    pid_t pid = fork();
    if (pid == 0) {
        execl("/system/bin/am", "am", "broadcast", "--async", "--receiver-foreground",
              "-a", "com.lmqr.ha9_comp_service.SCREEN_OFF_KEY",
              "-p", SIDE_KEY_PACKAGE,
              "--ei", "scan_code", scanCode, "--ei", "key_action", action,
              "--el", "event_time", eventTime, (char *)NULL);
        _exit(127);
    }
    if (pid < 0) {
        LOGE("Cannot fork side-key delivery: %s", strerror(errno));
        return;
    }
    int status;
    pid_t result;
    do {
        result = waitpid(pid, &status, 0);
    } while (result < 0 && errno == EINTR);
    if (result < 0) {
        LOGE("Cannot wait for side-key delivery: %s", strerror(errno));
    } else if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        LOGE("Side-key broadcast failed (status=%d)", status);
    }
}

static void *monitorSideKeys(void *unused) {
    (void)unused;
    for (;;) {
        int fd = openSideKeys();
        if (fd < 0) {
            sleep(5);
            continue;
        }
        struct input_event event;
        ssize_t count;
        while ((count = read(fd, &event, sizeof(event))) != 0) {
            if (count < 0 && errno == EINTR) continue;
            if (count != sizeof(event)) {
                LOGE("Cannot read side-key input: %s", count < 0 ? strerror(errno) : "short event");
                break;
            }
            if (event.type == EV_SYN && event.code == SYN_DROPPED) {
                LOGE("Side-key input overflow; reconnecting");
                break;
            }
            if (event.type == EV_KEY && (event.code == KEY_F1 || event.code == KEY_F2)
                    && (event.value == 0 || event.value == 1)) {
                sendSideKey(&event);
            }
        }
        close(fd);
        LOGE("Side-key device disconnected; retrying");
        sleep(1);
    }
    return NULL;
}

void startSideKeyMonitor(void) {
    pthread_t thread;
    int error = pthread_create(&thread, NULL, monitorSideKeys, NULL);
    if (error != 0) {
        LOGE("Cannot start side-key monitor: %s", strerror(error));
        return;
    }
    error = pthread_detach(thread);
    if (error != 0) LOGE("Cannot detach side-key monitor: %s", strerror(error));
}
