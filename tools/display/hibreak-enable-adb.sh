#!/system/bin/sh
set -e
trap 'log -p e -t hibreak-display "USB debugging configuration failed"' EXIT
settings put global development_settings_enabled 1
settings put global adb_enabled 1
setprop persist.sys.usb.config mtp,adb
setprop sys.usb.config mtp,adb
log -t hibreak-display "USB debugging enabled; ADB authentication remains required"
trap - EXIT
