#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ] || [[ "$2" != [ab] ]] ||
    { [ "$#" -eq 3 ] && [ "$3" != --flash ]; }; then
    echo "Usage: $0 <patched.img> <a|b> [--flash]" >&2
    echo "Without --flash, only prints the proposed commands." >&2
    exit 1
fi
IMAGE="$1"; SLOT="$2"
[ -s "$IMAGE" ] || { echo "Missing image: $IMAGE" >&2; exit 1; }
if [ "${3:-}" != --flash ]; then
    printf 'adb reboot fastboot\nfastboot getvar is-userspace\nfastboot getvar current-slot\n'
    printf 'fastboot -S 64M flash system_%s %q\nfastboot reboot\n' "$SLOT" "$IMAGE"
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
fastboot reboot
