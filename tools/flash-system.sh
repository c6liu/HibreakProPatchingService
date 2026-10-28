#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 2 ] || [[ "$2" != [ab] ]]; then
    echo "Usage: $0 <patched.img> <a|b> [--delete-stock-logical-partitions] [--wipe-data] [--flash]" >&2
    echo "Without --flash, only prints the proposed commands." >&2
    exit 1
fi
IMAGE="$1"; SLOT="$2"
WIPE_DATA=false
DELETE_STOCK_PARTITIONS=false
DO_FLASH=false
shift 2
while [ "$#" -gt 0 ]; do
    case "$1" in
        --delete-stock-logical-partitions)
            [ "$DELETE_STOCK_PARTITIONS" = false ] || {
                echo "Duplicate option: --delete-stock-logical-partitions" >&2; exit 1;
            }
            DELETE_STOCK_PARTITIONS=true
            ;;
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
            echo "Usage: $0 <patched.img> <a|b> [--delete-stock-logical-partitions] [--wipe-data] [--flash]" >&2
            exit 1
            ;;
    esac
    shift
done
[ -s "$IMAGE" ] || { echo "Missing image: $IMAGE" >&2; exit 1; }
if [ "$DO_FLASH" = false ]; then
    printf 'adb reboot fastboot\nfastboot getvar is-userspace\nfastboot getvar current-slot\n'
    if [ "$DELETE_STOCK_PARTITIONS" = true ]; then
        printf 'fastboot delete-logical-partition product_%s\n' "$SLOT"
        printf 'fastboot delete-logical-partition system_ext_%s\n' "$SLOT"
        echo "WARNING: --delete-stock-logical-partitions removes product and system_ext from slot $SLOT."
    fi
    printf 'fastboot flash system_%s %q\n' "$SLOT" "$IMAGE"
    if [ "$WIPE_DATA" = true ]; then
        printf 'fastboot reboot bootloader\nfastboot getvar is-userspace\nfastboot -w\n'
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
if [ "$DELETE_STOCK_PARTITIONS" = true ]; then
    for partition in product system_ext; do
        if ! fastboot delete-logical-partition "${partition}_$SLOT"; then
            echo "Failed to delete ${partition}_$SLOT. Do not reboot." >&2
            echo "A preceding logical partition may already be deleted; keep the phone in fastbootd and resolve the partition state." >&2
            exit 1
        fi
    done
fi
if ! fastboot flash "system_$SLOT" "$IMAGE"; then
    echo "Flash failed; the system partition may be incomplete. Do not reboot." >&2
    echo "Keep the device in fastbootd and retry the complete flash." >&2
    exit 1
fi
if [ "$WIPE_DATA" = true ]; then
    # fastbootd cannot wipe userdata on this phone; the bootloader can.
    if ! fastboot reboot bootloader; then
        echo "System image flashed, but rebooting to the bootloader failed." >&2
        echo "Enter the bootloader manually, then run: fastboot -w && fastboot reboot" >&2
        exit 1
    fi
    STATE="$(fastboot getvar is-userspace 2>&1)"
    grep -qE 'is-userspace: *no' <<< "$STATE" || {
        echo "System image flashed, but the phone is not in the bootloader. Not wiping." >&2
        echo "Enter the bootloader manually, then run: fastboot -w && fastboot reboot" >&2
        exit 1
    }
    echo "WARNING: Erasing shared userdata as requested by --wipe-data."
    if WIPE_OUTPUT="$(fastboot -w 2>&1)"; then
        while IFS= read -r line; do
            case "$line" in
                "wipe task partition not found: cache" | \
                "wipe task partition not found: metadata") ;;
                *) printf '%s\n' "$line" ;;
            esac
        done <<< "$WIPE_OUTPUT"
    else
        printf '%s\n' "$WIPE_OUTPUT" >&2
        echo "System image flashed, but userdata wipe failed. Do not reboot." >&2
        echo "Keep the device in the bootloader and resolve the wipe failure." >&2
        exit 1
    fi
fi
fastboot reboot
