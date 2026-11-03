#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$#" -ne 1 ]; then
    echo "Usage: ANDROID_NDK_HOME=/path/to/ndk AOSP_HEADERS=/path/to/include $0 <output.so>" >&2
    exit 1
fi
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME}"
: "${AOSP_HEADERS:?Set AOSP_HEADERS to Android 12 libhardware/libcutils/system headers}"
CC="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
for header in hardware/consumerir.h hardware/hardware.h; do
    [ -s "$AOSP_HEADERS/$header" ] || { echo "Missing dependency: $AOSP_HEADERS/$header" >&2; exit 1; }
done
[ ! -e "$1" ] && [ ! -L "$1" ] || { echo "Refusing to overwrite: $1" >&2; exit 1; }
"$CC" -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared \
    -I "$AOSP_HEADERS" -DLOG_TAG='"HibreakIR"' \
    "$ROOT/tools/ir/consumerir-hxd.c" "$ROOT/tools/ir/hxd-nec.c" \
    -Wl,-z,defs -Wl,-soname,consumerir.common.so -llog -o "$1"
sha256sum "$1"
