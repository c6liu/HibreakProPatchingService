#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 2 ] || [[ "$2" != [ab] ]]; then
    echo "Usage: $0 <patched.img> <a|b> [--wipe-data] [--flash]" >&2
    echo "Without --flash, only prints the proposed commands." >&2
    exit 1
fi
IMAGE="$1"; SLOT="$2"
WIPE_DATA=false
DO_FLASH=false
shift 2
while [ "$#" -gt 0 ]; do
    case "$1" in
        --wipe-data)
            [ "$WIPE_DATA" = false ] || {
                echo "Duplicate option: --wipe-data" >&2; exit 1;
            }
            WIPE_DATA=true
            ;;
        --flash)
            [ "$DO_FLASH" = false ] || {
                echo "Duplicate option: --flash" >&2; exit 1;
            }
            DO_FLASH=true
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 <patched.img> <a|b> [--wipe-data] [--flash]" >&2
            exit 1
            ;;
    esac
    shift
done
[ -s "$IMAGE" ] || { echo "Missing image: $IMAGE" >&2; exit 1; }
if [ "$DO_FLASH" = false ]; then
    printf 'adb reboot fastboot\nfastboot getvar is-userspace\nfastboot getvar current-slot\n'
    printf 'fastboot -S 64M flash system_%s %q\n' "$SLOT" "$IMAGE"
    if [ "$WIPE_DATA" = true ]; then
        printf 'fastboot -w\n'
        echo "WARNING: --wipe-data erases shared userdata (apps, settings, and personal files)."
    fi
    printf 'fastboot reboot\n'
    echo "Check fastbootd and the slot. Nothing was executed."
    exit 0
fi
for tool in fastboot e2fsck; do
    command -v "$tool" >/dev/null || { echo "Missing dependency: $tool" >&2; exit 1; }
done
# Do not automatically change device modes, slots, verification, or user data.
STATE="$(fastboot getvar is-userspace 2>&1)"
grep -qE 'is-userspace: *yes' <<< "$STATE" || {
    echo "Not in fastbootd. Run adb reboot fastboot first." >&2; exit 1;
}
STATE="$(fastboot getvar current-slot 2>&1)"
grep -qE "current-slot: *$SLOT([[:space:]]|$)" <<< "$STATE" || {
    echo "Active slot does not match requested slot $SLOT. Stopping." >&2; exit 1;
}
e2fsck -fn "$IMAGE"
if ! fastboot -S 64M flash "system_$SLOT" "$IMAGE"; then
    echo "Flash failed; the system partition may be incomplete. Do not reboot." >&2
    echo "Keep the device in fastbootd and retry the complete flash." >&2
    exit 1
fi
if [ "$WIPE_DATA" = true ]; then
    echo "WARNING: Erasing shared userdata as requested by --wipe-data."
    if ! fastboot -w; then
        echo "System image flashed, but userdata wipe failed. Do not reboot." >&2
        echo "Keep the device in fastbootd and resolve the wipe failure." >&2
        exit 1
    fi
fi
fastboot reboot
