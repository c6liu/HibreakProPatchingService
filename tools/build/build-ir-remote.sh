#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/tools/lib/build-common.sh"
if [ "$#" -ne 1 ]; then
    echo "Usage: ANDROID_NDK_HOME=/path/to/ndk $0 <output.apk>" >&2
    exit 1
fi
APKTOOL_JAR="${APKTOOL_JAR:-$ROOT/local/apktool.jar}"
APK_SIGNER_JAR="${APK_SIGNER_JAR:-$ROOT/local/uber-apk-signer.jar}"
hibreak_ndk_bin aarch64-linux-android30-clang
CC="$HIBREAK_NDK_BIN/aarch64-linux-android30-clang"
for tool in java sha256sum; do
    hibreak_require_tool "$tool"
done
hibreak_require_file "$APKTOOL_JAR"
hibreak_require_file "$APK_SIGNER_JAR"
hibreak_require_file "$CC"
hibreak_refuse_overwrite "$1"
mkdir -p "$ROOT/build"
TMP="$(mktemp -d "$ROOT/build/ir-remote.XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
cp -r "$ROOT/tools/ir/remote" "$TMP/app"
mkdir -p "$TMP/app/lib/arm64-v8a"
"$CC" -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared \
    "$TMP/app/remote-jni.c" -o "$TMP/app/lib/arm64-v8a/libhibreak_ir_remote.so"
rm "$TMP/app/remote-jni.c"
hibreak_build_and_sign_apk "$APKTOOL_JAR" "$APK_SIGNER_JAR" "$TMP/app" \
    "$TMP/HiBreakIrRemote.apk" "$TMP/signed" "$1"
