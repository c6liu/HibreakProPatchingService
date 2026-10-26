#!/usr/bin/env bash
# Offline patching only; never mounts an image or connects to a device.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$#" -lt 4 ] || [ "$#" -gt 6 ]; then
    echo "Usage: $0 <raw-ext4-gsi.img> <output.img> <standalone.apk> <daemon> [adbkey.pub] [--release]" >&2
    exit 1
fi
SRC="$1"; OUT="$2"; APK="$3"; DAEMON="$4"; KEY=""; RELEASE=false
shift 4
while [ "$#" -gt 0 ]; do
    case "$1" in
        --release)
            [ "$RELEASE" = false ] || { echo "Duplicate option: --release" >&2; exit 1; }
            RELEASE=true
            ;;
        *)
            [ -z "$KEY" ] || { echo "Unexpected argument: $1" >&2; exit 1; }
            KEY="$1"
            ;;
    esac
    shift
done
if [ "$RELEASE" = true ] && [ -n "$KEY" ]; then
    echo "--release cannot be combined with an ADB public key" >&2
    exit 1
fi
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
DISPLAY_RC="$ROOT/tools/display/hibreak-display.rc"
EINK_RC="$ROOT/a9_eink_daemon/etc/init/a9_eink_gsi.rc"
debugfs -R "dump system/build.prop \"$TMP/build.prop\"" "$OUT" >/dev/null
python3 - "$TMP/build.prop" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
lines = path.read_text().splitlines(keepends=True)
indices = [i for i, line in enumerate(lines)
           if line.startswith("persist.sys.usb.config=")]
if len(indices) != 1:
    raise SystemExit("Expected exactly one persist.sys.usb.config in system/build.prop")
lines[indices[0]] = "persist.sys.usb.config=mtp\n"
path.write_text("".join(lines))
PY
put "$TMP/build.prop" system/build.prop 0100644
if exists system/bin/hibreak-enable-adb.sh; then
    debugfs -w -R 'rm system/bin/hibreak-enable-adb.sh' "$OUT"
fi
if [ "$RELEASE" = true ]; then
    python3 - "$DISPLAY_RC" "$EINK_RC" "$TMP" <<'PY'
import pathlib
import sys

display_path, eink_path, output_dir = map(pathlib.Path, sys.argv[1:])

def remove_exact(text, block, name):
    if text.count(block) != 1:
        raise SystemExit(f"Expected exactly one {name} block")
    return text.replace(block, "")

display = display_path.read_text()
display = remove_exact(display, """on property:debug.hibreak.disable_hwc=1
    setprop debug.hibreak.disable_hwc 0
    start hibreak_disable_hwc

""", "HWC diagnostic override")
display = remove_exact(display, """# Manual recovery without root: adb shell setprop debug.hibreak.restart_sf 1
on property:debug.hibreak.restart_sf=1
    setprop debug.hibreak.restart_sf 0
    restart surfaceflinger
""", "SurfaceFlinger diagnostic override")
(output_dir / "hibreak-display-release.rc").write_text(display)

eink = eink_path.read_text()
eink = remove_exact(eink, """
# Diagnostic override: adb shell setprop debug.hibreak.refresh_mode <value>.
on property:debug.hibreak.refresh_mode=*
    setprop vendor.xrz.global_refresh_mode ${debug.hibreak.refresh_mode}
    write /sys/kernel/debug/eink_debug/global_mode ${debug.hibreak.refresh_mode}

on property:debug.hibreak.eink_restart=1
    setprop debug.hibreak.eink_restart 0
    restart a9_eink_server
""", "e-ink diagnostic overrides")
(output_dir / "a9_eink_gsi-release.rc").write_text(eink)
PY
    DISPLAY_RC="$TMP/hibreak-display-release.rc"
    EINK_RC="$TMP/a9_eink_gsi-release.rc"
fi
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
put "$EINK_RC" system/etc/init/a9_eink_gsi.rc 0100644
put "$ROOT/a9_accessibility_service/privapp-permissions-accessibility.xml" \
    system/etc/permissions/privapp-permissions-hibreak-eink.xml 0100644
put "$DISPLAY_RC" system/etc/init/hibreak-display.rc 0100644
for name in hibreak-disable-hwc hibreak-wake-cycle hibreak-aod; do
    put "$ROOT/tools/display/$name.sh" "system/bin/$name.sh" 0100755
done
if ! debugfs -R 'cat system/build.prop' "$OUT" 2>/dev/null |
        grep -qx 'persist.sys.usb.config=mtp'; then
        echo "Image does not default to MTP-only USB configuration" >&2
        exit 1
fi
if debugfs -R 'cat system/etc/init/hibreak-display.rc' "$OUT" 2>/dev/null |
    grep -Eq 'setprop (persist\.sys\.usb\.config|sys\.usb\.config)|hibreak_enable_adb'; then
    echo "Image overrides the saved USB debugging state" >&2
    exit 1
fi
if exists system/bin/hibreak-enable-adb.sh; then
    echo "Image still contains the USB ADB enable script" >&2
    exit 1
fi
if [ "$RELEASE" = true ]; then
    echo "Release mode: saved USB debugging state preserved; diagnostic hooks disabled."
    for path in system/etc/init/hibreak-display.rc system/etc/init/a9_eink_gsi.rc; do
        if debugfs -R "cat $path" "$OUT" 2>/dev/null | grep -q 'debug\.hibreak'; then
            echo "Release image retains a diagnostic hook in $path" >&2
            exit 1
        fi
    done
fi
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
