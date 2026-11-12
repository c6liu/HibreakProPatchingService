#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/tools/lib/build-common.sh"
if [ "$#" -ne 1 ]; then
    echo "Usage: ANDROID_NDK_HOME=/path/to/ndk AOSP_HEADERS=/path/to/include $0 <output.so>" >&2
    exit 1
fi
: "${AOSP_HEADERS:?Set AOSP_HEADERS to Android 12 libhardware/libcutils/system headers}"
hibreak_ndk_bin aarch64-linux-android30-clang
CC="$HIBREAK_NDK_BIN/aarch64-linux-android30-clang"
for header in hardware/consumerir.h hardware/hardware.h; do
    hibreak_require_file "$AOSP_HEADERS/$header"
done
hibreak_refuse_overwrite "$1"
"$CC" -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared \
    -I "$AOSP_HEADERS" -DLOG_TAG='"HibreakIR"' \
    "$ROOT/tools/ir/consumerir-hxd.c" "$ROOT/tools/ir/hxd-nec.c" \
    -Wl,-z,defs -Wl,-soname,consumerir.common.so -llog -o "$1"
sha256sum "$1"
