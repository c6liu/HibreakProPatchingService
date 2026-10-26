#!/usr/bin/env bash
# Offline patching only; never mounts an image or connects to a device.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$#" -lt 4 ] || [ "$#" -gt 5 ]; then
    echo "Usage: $0 <raw-ext4-gsi.img> <output.img> <standalone.apk> <daemon> [adbkey.pub]" >&2
    exit 1
fi
SRC="$1"; OUT="$2"; APK="$3"; DAEMON="$4"; KEY="${5:-}"
for tool in debugfs e2fsck resize2fs dumpe2fs truncate cmp sha256sum python3; do
    command -v "$tool" >/dev/null || { echo "Missing dependency: $tool" >&2; exit 1; }
done
for input in "$SRC" "$APK" "$DAEMON"; do
    [ -s "$input" ] || { echo "Missing input: $input" >&2; exit 1; }
done
[ ! -e "$OUT" ] || { echo "Refusing to overwrite: $OUT" >&2; exit 1; }
# debugfs uses its own command parser, not the shell's quoting rules.
for path in "$SRC" "$OUT" "$APK" "$DAEMON" "$KEY" "$ROOT" "${TMPDIR:-/tmp}"; do
    case "$path" in
        *\"*|*\\*|*$'\n'*|*$'\r'*) echo "Unsupported character in path: $path" >&2; exit 1 ;;
    esac
done
if [ -n "$KEY" ]; then
    python3 - "$KEY" <<'PY'
import base64
import pathlib
import struct
import sys
lines = pathlib.Path(sys.argv[1]).read_text().splitlines()
if len(lines) != 1 or not lines[0].split():
    sys.exit("Expected a single ADB public key, not a private key or key bundle")
try:
    data = base64.b64decode(lines[0].split()[0], validate=True)
except ValueError:
    sys.exit("Invalid ADB public key encoding")
if len(data) != 524 or struct.unpack_from("<I", data)[0] != 64:
    sys.exit("Expected an Android 2048-bit RSA adbkey.pub")
PY
fi
mkdir -p "$ROOT/build"
TMP="$(mktemp -d "$ROOT/build/gsi.XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
exists() {
    debugfs -R "stat $1" "$OUT" 2>/dev/null | grep -q 'Inode:'
}
debugfs -R 'dump system/etc/init/vndk.rc /dev/stdout' "$SRC" 2>/dev/null |
    grep -q 'u:r:phhsu_daemon:s0' || {
        echo "Expected a raw ext4 TrebleDroid GSI providing phhsu_daemon in vndk.rc." >&2
        echo "Extract .xz first; sparse images need simg2img. EROFS is not supported." >&2
        exit 1
    }
printf 'u:object_r:system_file:s0\0' > "$TMP/context"
printf 'u:object_r:adb_keys_file:s0\0' > "$TMP/adb-context"
cp --reflink=auto "$SRC" "$OUT"
truncate -s +256M "$OUT"
fsck_fix() {
    local status=0
    e2fsck -fy "$@" "$OUT" || status=$?
    [ "$status" -le 1 ] || { echo "Filesystem repair failed: $status" >&2; exit "$status"; }
}
fsck_fix
resize2fs "$OUT"
fsck_fix -E unshare_blocks
put() {
    local source="$1" dest="$2" mode="$3" context="${4:-$TMP/context}"
    if exists "$dest"; then debugfs -w -R "rm $dest" "$OUT"; fi
    debugfs -w -R "write \"$source\" $dest" "$OUT"
    debugfs -w -R "sif $dest mode $mode" "$OUT"
    debugfs -w -R "sif $dest uid 0" "$OUT"
    debugfs -w -R "sif $dest gid 0" "$OUT"
    debugfs -w -R "ea_set -f \"$context\" $dest security.selinux" "$OUT"
    rm -f "$TMP/check"
    debugfs -R "dump $dest \"$TMP/check\"" "$OUT"
    cmp "$source" "$TMP/check"
    debugfs -R "stat $dest" "$OUT" > "$TMP/stat"
    grep -q "Mode:  ${mode#010}" "$TMP/stat"
    grep -q 'User:     0   Group:     0' "$TMP/stat"
    grep -q "$(tr -d '\0' < "$context")" "$TMP/stat"
}
if ! exists system/priv-app/HiBreakEink; then
    debugfs -w -R 'mkdir system/priv-app/HiBreakEink' "$OUT"
fi
debugfs -w -R 'sif system/priv-app/HiBreakEink mode 040755' "$OUT"
debugfs -w -R 'sif system/priv-app/HiBreakEink uid 0' "$OUT"
debugfs -w -R 'sif system/priv-app/HiBreakEink gid 0' "$OUT"
debugfs -w -R "ea_set -f \"$TMP/context\" system/priv-app/HiBreakEink security.selinux" "$OUT"
if exists system/etc/init/a9_eink_daemon.rc; then
    echo "Conflicting AOSP daemon service exists; start from the unmodified GSI." >&2
    exit 1
fi
put "$APK" system/priv-app/HiBreakEink/HiBreakEink.apk 0100644
put "$DAEMON" system/bin/a9_eink_server 0100755
put "$ROOT/a9_eink_daemon/etc/init/a9_eink_gsi.rc" system/etc/init/a9_eink_gsi.rc 0100644
put "$ROOT/a9_accessibility_service/privapp-permissions-accessibility.xml" \
    system/etc/permissions/privapp-permissions-hibreak-eink.xml 0100644
put "$ROOT/tools/display/hibreak-display.rc" system/etc/init/hibreak-display.rc 0100644
for name in hibreak-disable-hwc hibreak-enable-adb hibreak-wake-cycle hibreak-aod; do
    put "$ROOT/tools/display/$name.sh" "system/bin/$name.sh" 0100755
done
if [ -n "$KEY" ]; then put "$KEY" adb_keys 0100644 "$TMP/adb-context"; fi
fsck_fix
resize2fs -M "$OUT"
fsck_fix
BLOCKS="$(dumpe2fs -h "$OUT" 2>/dev/null | awk '/^Block count:/{print $3}')"
BLOCK_SIZE="$(dumpe2fs -h "$OUT" 2>/dev/null | awk '/^Block size:/{print $3}')"
[[ "$BLOCKS" =~ ^[0-9]+$ && "$BLOCK_SIZE" =~ ^[0-9]+$ ]] || {
    echo "Unable to determine image size" >&2; exit 1;
}
truncate -s "$((BLOCKS * BLOCK_SIZE))" "$OUT"
e2fsck -fn "$OUT"
sha256sum "$OUT"
echo "Verified image ready. Nothing has been flashed."
