#!/system/bin/sh
# Do not put a newly booted device to sleep unless explicitly requested.
set -e
trap 'log -p e -t hibreak-display "Post-boot display wake failed"' EXIT
sleep 5
/system/bin/hibreak-disable-hwc.sh "$@"
if [ "$(getprop persist.sys.hibreak.boot_sleep_cycle)" = "true" ]; then
    input keyevent KEYCODE_SLEEP
    sleep 2
fi
input keyevent KEYCODE_WAKEUP
sleep 1
/system/bin/hibreak-disable-hwc.sh "$@"
log -t hibreak-display "Post-boot display wake completed"
trap - EXIT
# TrebleApp replays its "Disable HW overlays" preference after BOOT_COMPLETED;
# while that switch is off, it re-enables HWC behind the requests above.
remaining=180
while [ $remaining -gt 0 ]; do
    sleep 5
    remaining=$((remaining - 5))
    if dumpsys SurfaceFlinger 2>/dev/null | grep -q 'h/w composer enabled$'; then
        log -p w -t hibreak-display "HWC re-enabled after boot; reapplying forced GPU composition"
        /system/bin/hibreak-disable-hwc.sh "$@" || true
    fi
done
