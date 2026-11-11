#include <stdio.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <errno.h>
#include <android/log.h>
#include <ctype.h>
#include <sys/xattr.h>
#include <sys/wait.h>
#include <signal.h>
#include <sys/system_properties.h>
#include <sys/wait.h>

static const char* kTAG = "a9EinkService";
#define LOGI(...) ((void)__android_log_print(ANDROID_LOG_INFO, kTAG, __VA_ARGS__))
#define LOGE(...) ((void)__android_log_print(ANDROID_LOG_ERROR, kTAG, __VA_ARGS__))

#define SOCKET_NAME "0a9_eink_socket"
#define BUFFER_SIZE 512
#define HD_256_MODE "2147483825" // 0x800000b1: stock HD with the 256-level flag.

static const char* controlProperty(const char* name) {
#ifdef HIBREAK_ENFORCING_CANDIDATE
    static const struct { const char* destination; const char* request; } properties[] = {
        {"vendor.xrz.global_refresh_mode", "sys.hibreak.request.refresh_mode"},
        {"persist.sys.hibreak.aod_invert", "sys.hibreak.request.aod_invert"},
        {"sys.linevibrator_type", "sys.hibreak.request.linevibrator_type"},
        {"sys.linevibrator_touch", "sys.hibreak.request.linevibrator_touch"},
        {"sys.wakeup_on_volume", "sys.hibreak.request.wakeup_on_volume"},
    };
    for (size_t i = 0; i < sizeof(properties) / sizeof(properties[0]); i++) {
        if (strcmp(name, properties[i].destination) == 0) return properties[i].request;
    }
    LOGE("Unmapped candidate control property: %s", name);
    return NULL;
#else
    return name;
#endif
}

void startSideKeyMonitor(void);

void logPolicyPath(const char* path) {
    struct stat info;
    if (stat(path, &info) != 0) {
        LOGE("Policy probe: cannot stat %s: %s", path, strerror(errno));
        return;
    }
    char context[256];
    ssize_t length = getxattr(path, "security.selinux", context, sizeof(context) - 1);
    if (length < 0) {
        LOGE("Policy probe: cannot read label for %s: %s", path, strerror(errno));
        return;
    }
    context[length] = '\0';
    LOGI("Policy probe: path=%s context=%s uid=%u gid=%u mode=%04o",
         path, context, (unsigned int)info.st_uid, (unsigned int)info.st_gid,
         (unsigned int)(info.st_mode & 07777));
}

static void waitForCommand(pid_t pid) {
    int status;
    pid_t result;
    do {
        result = waitpid(pid, &status, 0);
    } while (result < 0 && errno == EINTR);
    if (result < 0) {
        LOGE("Failed to wait for command: %s", strerror(errno));
    } else if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        LOGE("Command failed (status=%d)", status);
    }
}

static const char* theme_styles[] = {
        "TONAL_SPOT",
        "VIBRANT",
        "RAINBOW",
        "EXPRESSIVE",
        "FRUIT_SALAD",
        "SPRITZ"
};

int valid_number(const char *s) {
    if(strlen(s) > 4 || strlen(s) == 0)
        return 0;

    while (*s)
        if (isdigit(*s++) == 0) return 0;

    return 1;
}

int valid_hex_color(const char *s) {
    if (strlen(s) != 6)
        return 0;

    while (*s)
        if (!isxdigit(*s++)) return 0;

    return 1;
}

void sanitize_input(int theme_style_index, const char* hex_color, char* sanitized_theme_style, char* sanitized_hex_color) {
    if (theme_style_index < 0 || theme_style_index > 5) {
        theme_style_index = 5; // Default to monotone
    }
    strcpy(sanitized_theme_style, theme_styles[theme_style_index]);

    if (!valid_hex_color(hex_color)) {
        strcpy(sanitized_hex_color, "333333");
    } else {
        strcpy(sanitized_hex_color, hex_color);
    }
}

void generate_json_string(char* json_str, const char* theme_style, const char* hex_color) {
    sprintf(json_str, "{\"android.theme.customization.theme_style\":\"%s\",\"android.theme.customization.color_source\":\"preset\",\"android.theme.customization.system_palette\":\"%s\"}", theme_style, hex_color);
}

void execute_settings_command(const char* json_str) {
    pid_t pid = fork();
    if (pid == 0) {
        execl("/system/bin/settings", "settings", "put", "secure", "theme_customization_overlay_packages", json_str, (char *)NULL);
        LOGE("execlp failed: %s", strerror(errno));
        exit(EXIT_FAILURE);
    } else if (pid < 0) {
        LOGE("fork failed: %s", strerror(errno));
    } else {
        waitForCommand(pid);
    }
}

void applyThemeCustomization(int theme_style_index, const char* hex_color) {
    char sanitized_theme_style[20];
    char sanitized_hex_color[7];
    char json_str[BUFFER_SIZE];

    sanitize_input(theme_style_index, hex_color, sanitized_theme_style, sanitized_hex_color);
    generate_json_string(json_str, sanitized_theme_style, sanitized_hex_color);
    execute_settings_command(json_str);
}


void epdForceClear() {
    LOGE("Native force-clear is not implemented on HiBreak Pro; use the app's Clear Screen action");
}


void epdCommitBitmap() {
    LOGE("Qualcomm bitmap commit is not supported on HiBreak Pro");
}

void writeToEpdDisplayMode(const char* value) {
    const char* filePath = "/sys/kernel/debug/eink_debug/global_mode";
    if (!valid_number(value) && strcmp(value, HD_256_MODE) != 0) {
        LOGE("Error writing to %s: Invalid Number\n", filePath);
        return;
    }

    int fd = open(filePath, O_WRONLY);
    if (fd == -1) {
        LOGE("Error writing to %s: %s\n", filePath, strerror(errno));
        return;
    }
    if (write(fd, value, strlen(value)) != (ssize_t)strlen(value)) {
        LOGE("Error writing to %s: %s\n", filePath, strerror(errno));
    } else {
        LOGI("Applied refresh mode %s to %s", value, filePath);
    }
    close(fd);
}

// Bigme's stock HWC reads its global e-ink mode from this property (decimal EinkRefreshMode value).
void applyRefreshMode(const char* value) {
#ifndef HIBREAK_PROPERTY_ONLY_REFRESH
    writeToEpdDisplayMode(value);
#endif
    const char* property = controlProperty("vendor.xrz.global_refresh_mode");
    if (property != NULL && __system_property_set(property, value) != 0) {
        LOGE("Failed to set vendor.xrz.global_refresh_mode=%s", value);
    }
#ifdef HIBREAK_PROPERTY_ONLY_REFRESH
    else if (property != NULL) {
        LOGI("Property-only refresh test: requested %s=%s", property, value);
    }
#endif
}

static void sendDpadKey(const char* keycode) {
    if (strcmp(keycode, "19") != 0 && strcmp(keycode, "20") != 0 &&
        strcmp(keycode, "21") != 0 && strcmp(keycode, "22") != 0) {
        LOGE("Invalid DPAD keycode: %s", keycode);
        return;
    }

    pid_t pid = fork();
    if (pid == 0) {
        execl("/system/bin/input", "input", "keyevent", keycode, (char *)NULL);
        LOGE("Failed to execute input keyevent: %s", strerror(errno));
        _exit(EXIT_FAILURE);
    }
    if (pid < 0) {
        LOGE("Failed to fork input keyevent: %s", strerror(errno));
        return;
    }

    int status;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno != EINTR) {
            LOGE("Failed to wait for input keyevent: %s", strerror(errno));
            return;
        }
    }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        LOGE("input keyevent %s failed", keycode);
    }
}

void setColdBacklight(const char* brightness) {
    const char* coldBacklightPath = "/sys/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_cold_light";
    if(!valid_number(brightness)){
        LOGE("Error writing to %s: Invalid Brightness Value\n", coldBacklightPath);
        return;
    }
    int fd = open(coldBacklightPath, O_WRONLY);
    if (fd == -1) {
        LOGE("Error writing to %s: %s\n", coldBacklightPath, strerror(errno));
        return;
    }
    if (write(fd, brightness, strlen(brightness)) == -1) {
        LOGE("Error writing to %s: %s\n", coldBacklightPath, strerror(errno));
    }
    close(fd);
}

void setWarmBacklight(const char* brightness) {
    const char* warmBacklightPath = "/sys/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_warm_light";
    if(!valid_number(brightness)){
        LOGE("Error writing to %s: Invalid Brightness Value\n", warmBacklightPath);
        return;
    }
    int fd = open(warmBacklightPath, O_WRONLY);
    if (fd == -1) {
        LOGE("Error writing to %s: %s\n", warmBacklightPath, strerror(errno));
        return;
    }
    if (write(fd, brightness, strlen(brightness)) == -1) {
        LOGE("Error writing to %s: %s\n", warmBacklightPath, strerror(errno));
    }
    close(fd);
}

#ifdef HIBREAK_INIT_EINK_BRIDGE
static void requestEinkControl(const char* property, const char* value) {
    if (strcmp(value, "0") != 0 && strcmp(value, "1") != 0) {
        LOGE("Invalid init e-ink bridge value for %s: %s", property, value);
        return;
    }
    if (__system_property_set(property, value) != 0) {
        LOGE("Failed to request init e-ink bridge %s=%s", property, value);
    } else {
        LOGI("Init e-ink bridge requested %s=%s; hardware write is asynchronous", property, value);
    }
}
#endif

void setGlobalAutoRefresh(const char* value) {
#ifdef HIBREAK_INIT_EINK_BRIDGE
    requestEinkControl("sys.hibreak.eink_bridge.auto_refresh", value);
#else
#ifdef HIBREAK_PROPERTY_ONLY_AUTO_REFRESH
    if (strcmp(value, "0") != 0 && strcmp(value, "1") != 0) {
        LOGE("Invalid property-only auto-refresh value: %s", value);
        return;
    }
    if (__system_property_set("vendor.xrz.auto_clean_enabled", value) != 0) {
        LOGE("Failed to set vendor.xrz.auto_clean_enabled=%s", value);
    } else {
        LOGI("Property-only auto-refresh test: requested vendor.xrz.auto_clean_enabled=%s", value);
    }
#else
    const char* globalAutoRefreshPath = "/sys/kernel/debug/eink_debug/clean_a2";
    if(!valid_number(value)){
        LOGE("Error writing to %s: Invalid Number\n", globalAutoRefreshPath);
        return;
    }
    int fd = open(globalAutoRefreshPath, O_WRONLY);
    if (fd == -1) {
        LOGE("Error writing to %s: %s\n", globalAutoRefreshPath, strerror(errno));
        return;
    }
    if (write(fd, value, strlen(value)) == -1) {
        LOGE("Error writing to %s: %s\n", globalAutoRefreshPath, strerror(errno));
    }
    close(fd);
#endif
#endif
}

void setAntiFlicker(const char* value) {
#ifdef HIBREAK_INIT_EINK_BRIDGE
    requestEinkControl("sys.hibreak.eink_bridge.anti_flicker", value);
#else
    const char* path = "/sys/kernel/debug/eink_debug/anti_flicker";
    if(!valid_number(value)){
        LOGE("Error writing to %s: Invalid Number\n", path);
        return;
    }
    int fd = open(path, O_WRONLY);
    if (fd == -1) {
        LOGE("Error writing to %s: %s\n", path, strerror(errno));
        return;
    }
    if (write(fd, value, strlen(value)) == -1) {
        LOGE("Error writing to %s: %s\n", path, strerror(errno));
    }
    close(fd);
#endif
}


void setWhiteThreshold(const char* brightness) {
    const char* whiteThresholdPath ="/sys/devices/platform/soc/soc:qcom,dsi-display-primary/epd_white_threshold";
    if(!valid_number(brightness)){
        LOGE("Error writing to %s: Invalid Number\n", whiteThresholdPath);
        return;
    }
    int fd = open(whiteThresholdPath, O_WRONLY);
    if (fd == -1) {
        LOGE("Error writing to %s: %s\n", whiteThresholdPath, strerror(errno));
        return;
    }
    if (write(fd, brightness, strlen(brightness)) == -1) {
        LOGE("Error writing to %s: %s\n", whiteThresholdPath, strerror(errno));
    }
    close(fd);
}

void setBlackThreshold(const char* brightness) {
    const char* blackThresholdPath = "/sys/devices/platform/soc/soc:qcom,dsi-display-primary/epd_black_threshold";
    if(!valid_number(brightness)){
        LOGE("Error writing to %s: Invalid Number\n", blackThresholdPath);
        return;
    }
    int fd = open(blackThresholdPath, O_WRONLY);
    if (fd == -1) {
        LOGE("Error writing to %s: %s\n", blackThresholdPath, strerror(errno));
        return;
    }
    if (write(fd, brightness, strlen(brightness)) == -1) {
        LOGE("Error writing to %s: %s\n", blackThresholdPath, strerror(errno));
    }
    close(fd);
}

void setContrast(const char* brightness) {
    const char* contrastPath = "/sys/devices/platform/soc/soc:qcom,dsi-display-primary/epd_contrast";
    if(!valid_number(brightness)){
        LOGE("Error writing to %s: Invalid Number\n", contrastPath);
        return;
    }
    int fd = open(contrastPath, O_WRONLY);
    if (fd == -1) {
        LOGE("Error writing to %s: %s\n", contrastPath, strerror(errno));
        return;
    }
    if (write(fd, brightness, strlen(brightness)) == -1) {
        LOGE("Error writing to %s: %s\n", contrastPath, strerror(errno));
    }
    close(fd);
}

void writeLockscreenProp(const char* value) {
    if(!valid_number(value)){
        LOGE("Error setting static lockscreen: Invalid Number\n");
        return;
    }
    pid_t pid = fork();
    if (pid == 0) {
        const char* property = controlProperty("sys.linevibrator_type");
        if (property == NULL) _exit(EXIT_FAILURE);
        execl("/system/bin/setprop", "setprop", property, value, (char *)NULL);
        LOGE("execlp failed: %s", strerror(errno));
        exit(EXIT_FAILURE);
    } else if (pid < 0) {
        LOGE("fork failed: %s", strerror(errno));
    } else {
        waitForCommand(pid);
    }
}

void writeMaxBrightnessProp(const char* value) {
    if(!valid_number(value)){
        LOGE("Error setting static lockscreen: Invalid Number\n");
        return;
    }
    pid_t pid = fork();
    if (pid == 0) {
        const char* property = controlProperty("sys.linevibrator_touch");
        if (property == NULL) _exit(EXIT_FAILURE);
        execl("/system/bin/setprop", "setprop", property, value, (char *)NULL);
        LOGE("execlp failed: %s", strerror(errno));
        exit(EXIT_FAILURE);
    } else if (pid < 0) {
        LOGE("fork failed: %s", strerror(errno));
    } else {
        waitForCommand(pid);
    }
}

void writeWakeOnVolumeProp(const char* value) {
    if(!valid_number(value)){
        LOGE("Error setting static lockscreen: Invalid Number\n");
        return;
    }
    pid_t pid = fork();
    if (pid == 0) {
        const char* property = controlProperty("sys.wakeup_on_volume");
        if (property == NULL) _exit(EXIT_FAILURE);
        execl("/system/bin/setprop", "setprop", property, value, (char *)NULL);
        LOGE("execlp failed: %s", strerror(errno));
        exit(EXIT_FAILURE);
    } else if (pid < 0) {
        LOGE("fork failed: %s", strerror(errno));
    } else {
        waitForCommand(pid);
    }
}

// Read by /system/bin/hibreak-aod.sh when the device enters doze.
void setAodInvert(const char* value) {
    if (strcmp(value, "0") != 0 && strcmp(value, "1") != 0) {
        LOGE("Invalid AOD inversion value: %s (expected 0 or 1)", value);
        return;
    }
    const char* enabled = strcmp(value, "0") == 0 ? "false" : "true";
    const char* property = controlProperty("persist.sys.hibreak.aod_invert");
    if (property != NULL && __system_property_set(property, enabled) != 0) {
        LOGE("Failed to set persist.sys.hibreak.aod_invert=%s", enabled);
    }
}

void processCommand(const char* command) {
    if (strcmp(command, "cm") == 0) {
        epdCommitBitmap();
    } else if (strcmp(command, "r") == 0) {
        epdForceClear();
    } else if (strcmp(command, "c") == 0) {
        applyRefreshMode("180");
    } else if (strcmp(command, "b") == 0) {
        applyRefreshMode("178");
    } else if (strcmp(command, "s") == 0) {
        applyRefreshMode(HD_256_MODE);
    } else if (strcmp(command, "p") == 0) {
        applyRefreshMode("179");
    } else if (strcmp(command, "h") == 0) {
        applyRefreshMode("183");
    } else if (strcmp(command, "dpad_up") == 0) {
        sendDpadKey("19");
    } else if (strcmp(command, "dpad_down") == 0) {
        sendDpadKey("20");
    } else if (strcmp(command, "dpad_left") == 0) {
        sendDpadKey("21");
    } else if (strcmp(command, "dpad_right") == 0) {
        sendDpadKey("22");
    } else if (strncmp(command, "stw", 3) == 0) {
        if(valid_number(command+3))
            setWhiteThreshold(command+3);
    } else if (strncmp(command, "stl", 3) == 0) {
        if(valid_number(command+3))
            writeLockscreenProp(command+3);
    } else if (strncmp(command, "stb", 3) == 0) {
        if(valid_number(command+3))
            setBlackThreshold(command+3);
    } else if (strncmp(command, "sco", 3) == 0) {
        if(valid_number(command+3))
            setContrast(command+3);
    } else if (strncmp(command, "smb", 3) == 0) {
        if(valid_number(command+3))
            writeMaxBrightnessProp(command+3);
    } else if (strncmp(command, "wov", 3) == 0) {
        if(valid_number(command+3))
            writeWakeOnVolumeProp(command+3);
    } else if (strncmp(command, "aoi", 3) == 0) {
        setAodInvert(command+3);
    } else if (strncmp(command, "theme", 5) == 0) {
        int theme_style_index;
        char hex_color[7];
        if (sscanf(command + 5, "%d %6s", &theme_style_index, hex_color) == 2) {
            applyThemeCustomization(theme_style_index, hex_color);
        } else {
            LOGE("Invalid theme command format");
        }
    } else if (strncmp(command, "br_co", 5) == 0) {
        if(valid_number(command+5))
            setColdBacklight(command+5);
    } else if (strncmp(command, "br_wm", 5) == 0) {
        if(valid_number(command+5))
            setWarmBacklight(command+5);
    } else if (strncmp(command, "au_br", 5) == 0) {
        if(valid_number(command+5))
            setGlobalAutoRefresh(command+5);
    } else if (strncmp(command, "an_fl", 5) == 0) {
        if(valid_number(command+5))
            setAntiFlicker(command+5);
    }
    else {
        LOGE("Unknown command: %s", command);
    }
}

_Noreturn void setupServer() {
    int server_sockfd, client_sockfd;
    struct sockaddr_un server_addr;
    char buffer[BUFFER_SIZE];
    socklen_t socket_length = sizeof(server_addr.sun_family) + strlen(SOCKET_NAME);

    server_sockfd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_sockfd < 0) {
        LOGE("Socket creation failed: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sun_family = AF_UNIX;
    strncpy(server_addr.sun_path, SOCKET_NAME, sizeof(server_addr.sun_path) - 1);
    server_addr.sun_path[0] = 0;

    if (bind(server_sockfd, (struct sockaddr*)&server_addr, socket_length) < 0) {
        LOGE("Socket bind failed: %s", strerror(errno));
        close(server_sockfd);
        exit(EXIT_FAILURE);
    }

    if (listen(server_sockfd, 50) < 0) {
        LOGE("Socket listen failed: %s", strerror(errno));
        close(server_sockfd);
        exit(EXIT_FAILURE);
    }

    LOGI("Server started listening.");

    while (1) {
        client_sockfd = accept(server_sockfd, NULL, NULL);
        if (client_sockfd < 0) {
            LOGE("Socket accept failed: %s", strerror(errno));
            continue;
        }

        while (1) {
            memset(buffer, 0, BUFFER_SIZE);
            ssize_t num_read = read(client_sockfd, buffer, BUFFER_SIZE - 1);
            if (num_read > 0) {
                buffer[num_read] = '\0';
                char* cmd = strtok(buffer, "\n");
                while (cmd != NULL) {
                    processCommand(cmd);
                    cmd = strtok(NULL, "\n");
                }
            } else if (num_read == 0) {
                LOGI("Client disconnected");
                break;
            } else {
                LOGE("Socket read failed: %s", strerror(errno));
                break;
            }
        }

        close(client_sockfd);
    }

    close(server_sockfd);
}

int main(void) {
    signal(SIGHUP, SIG_IGN);
    char context[256];
    int context_fd = open("/proc/self/attr/current", O_RDONLY | O_CLOEXEC);
    if (context_fd < 0) {
        LOGE("Policy probe: cannot open process context: %s", strerror(errno));
    } else {
        ssize_t length = read(context_fd, context, sizeof(context) - 1);
        if (length < 0) {
            LOGE("Policy probe: cannot read process context: %s", strerror(errno));
        } else {
            context[length] = '\0';
            LOGI("Policy probe: daemon context=%s uid=%u gid=%u",
                 context, (unsigned int)getuid(), (unsigned int)getgid());
        }
        close(context_fd);
    }
    startSideKeyMonitor();
    const char* paths[] = {
        "/sys/kernel/debug/eink_debug/global_mode",
        "/sys/kernel/debug/eink_debug/clean_a2",
        "/sys/kernel/debug/eink_debug/anti_flicker",
        "/sys/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_cold_light",
        "/sys/devices/platform/11d01000.i2c7/i2c-7/7-0036/lm3630a_warm_light",
        "/dev/input",
        "/system/bin/a9_eink_server",
        "/system/bin/settings",
        "/system/bin/input",
        "/system/bin/am",
        "/system/bin/app_process64",
        "/system/bin/sh",
    };
    for (size_t i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
        struct stat info;
        if (stat(paths[i], &info) == 0) {
            LOGI("Hardware node available: %s", paths[i]);
        } else {
            LOGE("Hardware node unavailable: %s: %s", paths[i], strerror(errno));
        }
        logPolicyPath(paths[i]);
    }
    setupServer();
    return 0;
}