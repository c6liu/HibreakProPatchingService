#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#ifdef __ANDROID__
#include <sys/system_properties.h>
#endif

#include "ir/hxd-transmit-guard.h"

static volatile sig_atomic_t interrupted;

static void on_signal(int number) {
    interrupted = number;
}

static void usage(FILE *stream) {
    fprintf(stream,
            "Usage: hxd-learn capture [--short] [--timeout SECONDS] OUTPUT\n"
            "       hxd-learn --service [extended|short|tx-test]\n"
            "       hxd-learn --help\n\n"
            "Capture only: sends a learning command to /dev/ctrl, never an IR replay.\n"
            "Exception: --service tx-test transmits five fixed manufacturer sample packets.\n"
            "Default: 230-byte extended record; --short selects 110 bytes.\n"
            "Timeout: 1..60 seconds (default 25); cannot interrupt a stuck kernel call.\n"
            "OUTPUT must not exist. Saved bytes are raw, not a transmit packet.\n");
}

static int monotonic_time(double *result) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0) {
        perror("clock_gettime");
        return -1;
    }
    *result = (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
    return 0;
}

static int pause_capture(double deadline) {
    double now;
    if (monotonic_time(&now) < 0)
        return -1;
    double duration = deadline - now;
    if (duration <= 0.0)
        return 0;
    if (duration > 0.2)
        duration = 0.2;
    struct timespec delay = {
        .tv_sec = 0,
        .tv_nsec = (long)(duration * 1000000000.0),
    };
    if (nanosleep(&delay, NULL) < 0 && errno != EINTR) {
        perror("nanosleep");
        return -1;
    }
    return 0;
}

static int save_record(int fd, const unsigned char *record, size_t length) {
    size_t saved = 0;
    while (saved < length) {
        ssize_t count = write(fd, record + saved, length - saved);
        if (count < 0) {
            if (errno == EINTR && !interrupted)
                continue;
            perror("write capture file");
            return -1;
        }
        if (count == 0) {
            fprintf(stderr, "Capture file write returned zero.\n");
            return -1;
        }
        saved += (size_t)count;
    }
    if (fsync(fd) < 0) {
        perror("fsync capture file");
        return -1;
    }
    return 0;
}

static bool observed_no_signal(const unsigned char *record, size_t length) {
    /* Exact extended record observed with and without remote input on stock 3.1.6. */
    static const unsigned char empty_record[230] = {
        0x00, 0x88, 0x99, 0xaa, 0x00,
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        [227] = 0xf2, [228] = 0xe1, [229] = 0x51,
    };
    return length == sizeof(empty_record) && memcmp(record, empty_record, length) == 0;
}

static int run_capture(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        usage(stdout);
        return 0;
    }

    if (argc < 3 || strcmp(argv[1], "capture") != 0) {
        usage(stderr);
        return 2;
    }
    bool short_record = false;
    bool timeout_set = false;
    long timeout = 25;
    const char *output = NULL;
    bool options = true;
    for (int i = 2; i < argc; ++i) {
        if (options && strcmp(argv[i], "--") == 0) {
            options = false;
        } else if (options && strcmp(argv[i], "--short") == 0 && !short_record) {
            short_record = true;
        } else if (options && strcmp(argv[i], "--timeout") == 0 && !timeout_set && i + 1 < argc) {
            const char *value = argv[++i];
            char *end;
            errno = 0;
            timeout = strtol(value, &end, 10);
            if (!*value || strspn(value, "0123456789") != strlen(value) ||
                *end || errno || timeout < 1 || timeout > 60) {
                fprintf(stderr, "Timeout must be an integer from 1 to 60 seconds.\n");
                return 2;
            }
            timeout_set = true;
        } else if (!output && (!options || argv[i][0] != '-')) {
            output = argv[i];
        } else {
            fprintf(stderr, "Unexpected argument: %s\n", argv[i]);
            usage(stderr);
            return 2;
        }
    }
    if (!output) {
        fprintf(stderr, "A new output file path is required.\n");
        return 2;
    }

    struct sigaction action = {.sa_handler = on_signal};
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) < 0 || sigaction(SIGTERM, &action, NULL) < 0) {
        perror("sigaction");
        return 1;
    }

    /* Reserve the destination before starting a learning session. */
    int saved_fd = open(output, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (saved_fd < 0) {
        perror("create capture file (must not already exist)");
        return 1;
    }
    int result = 1;
    int device = -1;
    bool command_attempted = false;
    device = open("/dev/ctrl", O_RDWR | O_CLOEXEC | O_NOFOLLOW);
    if (device < 0) {
        perror("open /dev/ctrl");
        fprintf(stderr, "Check SELinux ctrl_device access; mode 0666 does not override SELinux.\n");
        goto cleanup;
    }
    struct stat status;
    if (fstat(device, &status) < 0) {
        perror("fstat /dev/ctrl");
        goto cleanup;
    }
    if (!S_ISCHR(status.st_mode)) {
        fprintf(stderr, "/dev/ctrl is not a character device; refusing access.\n");
        goto cleanup;
    }
    if (flock(device, LOCK_EX | LOCK_NB) < 0) {
        perror("lock /dev/ctrl");
        fprintf(stderr, "Stop other learning tools; no learning command was sent.\n");
        goto cleanup;
    }

    double now;
    if (monotonic_time(&now) < 0)
        goto cleanup;
    double deadline = now + (double)timeout;
    if (interrupted)
        goto cleanup;
    const unsigned char command[] = {0x30, short_record ? 0x10 : 0x20, short_record ? 0x40 : 0x50};
    size_t length = short_record ? 110 : 230;
    unsigned char record[230];
    fprintf(stderr, "Starting %s IR learning (%zu bytes). Point the TV remote at the phone's IR port\n"
                    "and press one button. No replay will be sent. Timeout: %ld seconds.\n",
            short_record ? "short" : "extended", length, timeout);
    command_attempted = true;
    ssize_t sent = write(device, command, sizeof(command));
    if (sent != (ssize_t)sizeof(command)) {
        if (sent < 0)
            perror("write learning command");
        else
            fprintf(stderr, "Incomplete learning command: %zd of %zu bytes.\n", sent, sizeof(command));
        fprintf(stderr, "Command was not retried: each write is a separate controller transaction.\n");
        goto cleanup;
    }
    if (pause_capture(deadline) < 0)
        goto cleanup;
    while (!interrupted) {
        if (monotonic_time(&now) < 0)
            goto cleanup;
        if (now >= deadline) {
            fprintf(stderr, "Learning timed out; no record saved.\n");
            goto cleanup;
        }
        memset(record, 0, sizeof(record));
        ssize_t count = read(device, record, length);
        if (interrupted)
            goto cleanup;
        if (count < 0) {
            perror("read learned record");
            fprintf(stderr, "Stock driver also returns raw -1 for a nonzero controller status;\n"
                            "this may appear as EPERM. A syscall error alone cannot distinguish it\n"
                            "from an access denial. No automatic re-arm or retry was attempted.\n");
            goto cleanup;
        }
        if (monotonic_time(&now) < 0)
            goto cleanup;
        if (now >= deadline) {
            fprintf(stderr, "Learning deadline expired during read; no record saved.\n");
            goto cleanup;
        }
        if (count == 0) {
            if (pause_capture(deadline) < 0)
                goto cleanup;
            continue;
        }
        if (count != (ssize_t)length) {
            fprintf(stderr, "Incomplete learned record: %zd bytes, expected %zu; refusing to pad or combine reads.\n",
                    count, length);
            goto cleanup;
        }
        fprintf(stderr, "Received %zu bytes after %.3f seconds.\n", length, (double)timeout - (deadline - now));
        if (observed_no_signal(record, length)) {
            fprintf(stderr, "No signal learned: record matches the observed no-button control exactly.\n"
                            "Controller data was read, but this is not a successful remote capture.\n");
            goto cleanup;
        }
        bool payload = false;
        for (size_t i = 1; i < length; ++i)
            payload |= record[i] != 0;
        if (record[0] != 0 || !payload) {
            fprintf(stderr, "Invalid learned record: expected zero status and a nonzero payload.\n");
            goto cleanup;
        }
        if (save_record(saved_fd, record, length) < 0)
            goto cleanup;
        if (interrupted)
            goto cleanup;
        result = 0;
        break;
    }

cleanup:
    if (device >= 0 && close(device) < 0) {
        perror("close /dev/ctrl");
        result = 1;
    }
    if (close(saved_fd) < 0) {
        perror("close capture file");
        result = 1;
    }
    if (interrupted) {
        fprintf(stderr, "Capture interrupted by signal %d.\n", (int)interrupted);
        result = 1;
    }
    if (result != 0) {
        if (unlink(output) < 0)
            perror("remove incomplete capture file");
        if (command_attempted)
            fprintf(stderr, "Controller learning may remain active until its own timeout (about 20 seconds).\n"
                            "No undocumented cancel/reset command was sent.\n");
        return interrupted ? 128 + (int)interrupted : 1;
    }
    printf("Saved %zu raw learned bytes to %s\n", short_record ? (size_t)110 : (size_t)230, output);
    fprintf(stderr, "The driver discards the receive checksum: capture integrity is not independently verified.\n"
                    "Saved bytes are a candidate only; signal reception is not established by this check.\n"
                    "This is a raw learning record, NOT a transmit packet or Android pulse array.\n");
    return 0;
}

static int transmit_packets(const unsigned char *packet, size_t length, int count,
                            unsigned int envelope_us) {
    struct sigaction action = {.sa_handler = on_signal};
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) < 0 || sigaction(SIGTERM, &action, NULL) < 0) {
        perror("sigaction");
        return 1;
    }
    int device = open("/dev/ctrl", O_RDWR | O_CLOEXEC | O_NOFOLLOW);
    if (device < 0) {
        perror("open transmit test controller");
        return 1;
    }
    int result = 1;
    struct stat status;
    if (fstat(device, &status) < 0) {
        perror("fstat transmit test controller");
        goto cleanup;
    }
    if (!S_ISCHR(status.st_mode)) {
        fprintf(stderr, "Transmit test controller is not a character device.\n");
        goto cleanup;
    }
    if (flock(device, LOCK_EX | LOCK_NB) < 0) {
        perror("lock transmit test controller");
        goto cleanup;
    }
    for (int i = 0; i < count; ++i) {
        if (interrupted)
            goto cleanup;
        ssize_t sent = write(device, packet, length);
        if (sent != (ssize_t)length) {
            if (sent < 0)
                perror("write transmit test packet");
            else
                fprintf(stderr, "Incomplete transmit test packet: %zd of %zu bytes.\n", sent, length);
            fprintf(stderr, "Aborting test; failed or partial command is not retried.\n");
            goto cleanup;
        }
        fprintf(stderr, "Transmit test write %d/%d completed; optical output is NOT verified.\n", i + 1, count);
        if (hxd_transmit_guard(envelope_us) < 0) {
            perror("transmit ownership guard");
            goto cleanup;
        }
        if (i + 1 < count) {
            double now;
            if (monotonic_time(&now) < 0)
                goto cleanup;
            double deadline = now + 1.0 - (double)(envelope_us + HXD_TRANSMIT_GUARD_US) / 1000000.0;
            while (!interrupted) {
                if (monotonic_time(&now) < 0)
                    goto cleanup;
                if (now >= deadline)
                    break;
                if (pause_capture(deadline) < 0)
                    goto cleanup;
            }
        }
    }
    result = 0;
cleanup:
    if (close(device) < 0) {
        perror("close transmit test controller");
        result = 1;
    }
    if (interrupted) {
        fprintf(stderr, "Transmit test interrupted by signal %d.\n", (int)interrupted);
        return 128 + (int)interrupted;
    }
    return result;
}

static int transmit_test(void) {
    /* HXD019D manufacturer instructions REV 1.3, section 1.1 sample packet. */
    static const unsigned char packet[] = {0x30, 0x00, 0x01, 0x1c, 0xe3, 0x00, 0xff, 0x20, 0x88, 0xd7};
    fprintf(stderr, "IR TRANSMIT TEST: five manufacturer sample commands, one second apart.\n"
                    "Unknown appliance action: aim away from appliances. No learned data is replayed.\n");
    return transmit_packets(packet, sizeof(packet), 5, 108800);
}

static int transmit_tcl(void) {
    /* Experimental compact F=1 mapping of the public TCL NECext EA C7 / 0F F0 code. */
    static const unsigned char packet[] = {0x30, 0x00, 0x01, 0x0f, 0xf0, 0xea, 0xc7, 0x00, 0x00, 0xe1};
    fprintf(stderr, "Experimental TCL Volume Up: one fixed packet; HXD protocol mapping is unverified.\n");
    return transmit_packets(packet, sizeof(packet), 1, 108800);
}

static int publish_tcl_result(const char *token, int result) {
#ifdef __ANDROID__
    char value[PROP_VALUE_MAX];
    int size = snprintf(value, sizeof(value), "%s:%s", token, result == 0 ? "written" : "failed");
    if (size < 0 || (size_t)size >= sizeof(value) ||
        __system_property_set("debug.hibreak.ir_tcl_result", value) < 0) {
        fprintf(stderr, "Cannot publish TCL transmit result.\n");
        return 1;
    }
#else
    (void)token;
#endif
    return result;
}

int main(int argc, char **argv) {
    bool tcl_service = argc >= 2 && strcmp(argv[1], "--tcl-service") == 0;
    if (tcl_service && (argc != 3 || !argv[2][0] || strlen(argv[2]) > 20 ||
                        strspn(argv[2], "0123456789") != strlen(argv[2]))) {
        fprintf(stderr, "TCL service requires a numeric request token of 1..20 digits.\n");
        return 2;
    }
    if (!tcl_service && (argc < 2 || strcmp(argv[1], "--service") != 0))
        return run_capture(argc, argv);
    if (!tcl_service && (argc > 3 || (argc == 3 && strcmp(argv[2], "extended") != 0 &&
                     strcmp(argv[2], "short") != 0 && strcmp(argv[2], "tx-test") != 0))) {
        fprintf(stderr, "Service mode must be extended, short, or tx-test; no device access attempted.\n");
        return 2;
    }
    bool short_record = argc == 3 && strcmp(argv[2], "short") == 0;
    bool tx_test = argc == 3 && strcmp(argv[2], "tx-test") == 0;

    char record[] = "/data/misc/hibreak-ir/record.bin";
    int log = open(tcl_service ? "/data/misc/hibreak-ir/tcl-result.txt" : "/data/misc/hibreak-ir/result.txt",
                   O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (log < 0) {
        perror("open capture service result");
        return tcl_service ? publish_tcl_result(argv[2], 1) : 1;
    }
    if (dup2(log, STDOUT_FILENO) < 0 || dup2(log, STDERR_FILENO) < 0) {
        perror("redirect capture service output");
        close(log);
        return tcl_service ? publish_tcl_result(argv[2], 1) : 1;
    }
    if (close(log) < 0) {
        perror("close capture service log descriptor");
        return tcl_service ? publish_tcl_result(argv[2], 1) : 1;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    if (!tx_test && !tcl_service && unlink(record) < 0 && errno != ENOENT) {
        perror("remove previous service capture");
        return 1;
    }
    char *capture[] = {argv[0], "capture", short_record ? "--short" : "--", record, NULL};
    int result = tcl_service ? transmit_tcl() : tx_test ? transmit_test() : run_capture(4, capture);
    printf("%s service exit status: %d\n", tcl_service ? "TCL transmit" : tx_test ? "Transmit test" : "Capture", result);
    if (fflush(NULL) != 0) {
        perror("flush capture service result");
        return tcl_service ? publish_tcl_result(argv[2], 1) : 1;
    }
    if (fsync(STDOUT_FILENO) < 0) {
        perror("fsync capture service result");
        return tcl_service ? publish_tcl_result(argv[2], 1) : 1;
    }
    return tcl_service ? publish_tcl_result(argv[2], result) : result;
}
