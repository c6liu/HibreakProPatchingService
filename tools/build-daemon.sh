#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$#" -ne 1 ]; then
    echo "Usage: ANDROID_NDK_HOME=/path/to/ndk $0 <output-binary>" >&2
    exit 1
fi
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to an installed Android NDK (tested: 27.2.12479018)}"
BIN="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin"
for tool in aarch64-linux-android30-clang llvm-strip; do
    [ -x "$BIN/$tool" ] || { echo "Missing NDK tool: $BIN/$tool" >&2; exit 1; }
done
[ ! -e "$1" ] || { echo "Refusing to overwrite: $1" >&2; exit 1; }
"$BIN/aarch64-linux-android30-clang" -O2 -Wall -Wextra -Werror \
    "$ROOT/a9_eink_daemon/eink_daemon.c" "$ROOT/a9_eink_daemon/side_keys.c" -llog -o "$1"
"$BIN/llvm-strip" "$1"
sha256sum "$1"
