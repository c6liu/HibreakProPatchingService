#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/lib/build-common.sh"
if [ "$#" -ne 1 ]; then
    echo "Usage: ANDROID_NDK_HOME=/path/to/ndk $0 <output-binary>" >&2
    exit 1
fi
hibreak_ndk_bin aarch64-linux-android30-clang llvm-strip
hibreak_refuse_overwrite "$1"
"$HIBREAK_NDK_BIN/aarch64-linux-android30-clang" -O2 -Wall -Wextra -Werror \
    "$ROOT/a9_eink_daemon/eink_daemon.c" "$ROOT/a9_eink_daemon/side_keys.c" -llog -o "$1"
"$HIBREAK_NDK_BIN/llvm-strip" "$1"
sha256sum "$1"
