#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <new-output-directory>" >&2
    echo "Read-only. Logs may contain personal data; review before sharing." >&2
    exit 1
fi
for tool in adb timeout; do
    command -v "$tool" >/dev/null || { echo "Missing dependency: $tool" >&2; exit 1; }
done
adb get-state
[ ! -e "$1" ] || { echo "Refusing to overwrite: $1" >&2; exit 1; }
mkdir -p "$1"
timeout 20 adb shell getprop > "$1/properties.txt"
for service in power battery display accessibility SurfaceFlinger; do
    timeout 30 adb shell dumpsys "$service" > "$1/$service.txt"
done
timeout 30 adb logcat -b system -b main -b events -d -v threadtime > "$1/logcat.txt"
timeout 10 adb shell 'cat /proc/uptime; settings get secure doze_always_on; settings get secure accessibility_display_inversion_enabled; settings get system screen_off_timeout' > "$1/settings.txt"
echo "Saved diagnostic snapshot to $1. No settings were changed."
