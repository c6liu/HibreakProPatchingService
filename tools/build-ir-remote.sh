#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$#" -ne 1 ]; then
    echo "Usage: ANDROID_NDK_HOME=/path/to/ndk $0 <output.apk>" >&2
    exit 1
fi
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to an installed Android NDK}"
APKTOOL_JAR="${APKTOOL_JAR:-$ROOT/local/apktool.jar}"
APK_SIGNER_JAR="${APK_SIGNER_JAR:-$ROOT/local/uber-apk-signer.jar}"
CC="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
for input in "$APKTOOL_JAR" "$APK_SIGNER_JAR" "$CC"; do
    [ -s "$input" ] || { echo "Missing dependency: $input" >&2; exit 1; }
done
[ ! -e "$1" ] && [ ! -L "$1" ] || { echo "Refusing to overwrite: $1" >&2; exit 1; }
mkdir -p "$ROOT/build"
TMP="$(mktemp -d "$ROOT/build/ir-remote.XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
cp -r "$ROOT/tools/ir/remote" "$TMP/app"
mkdir -p "$TMP/app/lib/arm64-v8a"
"$CC" -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared \
    "$TMP/app/remote-jni.c" -o "$TMP/app/lib/arm64-v8a/libhibreak_ir_remote.so"
rm "$TMP/app/remote-jni.c"
java -jar "$APKTOOL_JAR" b "$TMP/app" -o "$TMP/HiBreakIrRemote.apk"
java -jar "$APK_SIGNER_JAR" -a "$TMP/HiBreakIrRemote.apk" -o "$TMP/signed"
SIGNED=("$TMP"/signed/*.apk)
[ "${#SIGNED[@]}" -eq 1 ] && [ -s "${SIGNED[0]}" ] || {
    echo "Expected exactly one verified signed APK" >&2; exit 1;
}
cp "${SIGNED[0]}" "$1"
sha256sum "$1"
