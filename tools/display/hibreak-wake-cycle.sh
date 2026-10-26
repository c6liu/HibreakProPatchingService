#!/system/bin/sh
# Do not put a newly booted device to sleep unless explicitly requested.
set -e
trap 'log -p e -t hibreak-display "Post-boot display wake failed"' EXIT
sleep 5
/system/bin/hibreak-disable-hwc.sh
if [ "$(getprop persist.sys.hibreak.boot_sleep_cycle)" = "true" ]; then
    input keyevent KEYCODE_SLEEP
    sleep 2
fi
input keyevent KEYCODE_WAKEUP
sleep 1
/system/bin/hibreak-disable-hwc.sh
log -t hibreak-display "Post-boot display wake completed"
trap - EXIT
