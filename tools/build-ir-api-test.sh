#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <output.apk>" >&2
    exit 1
fi
APKTOOL_JAR="${APKTOOL_JAR:-$ROOT/local/apktool.jar}"
APK_SIGNER_JAR="${APK_SIGNER_JAR:-$ROOT/local/uber-apk-signer.jar}"
for input in "$APKTOOL_JAR" "$APK_SIGNER_JAR"; do
    [ -s "$input" ] || { echo "Missing dependency: $input" >&2; exit 1; }
done
[ ! -e "$1" ] && [ ! -L "$1" ] || { echo "Refusing to overwrite: $1" >&2; exit 1; }
mkdir -p "$ROOT/build"
TMP="$(mktemp -d "$ROOT/build/ir-api-test.XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
cp -r "$ROOT/tools/ir/api-test" "$TMP/app"
java -jar "$APKTOOL_JAR" b "$TMP/app" -o "$TMP/AndroidIrApiTest.apk"
java -jar "$APK_SIGNER_JAR" -a "$TMP/AndroidIrApiTest.apk" -o "$TMP/signed"
SIGNED=("$TMP"/signed/*.apk)
[ "${#SIGNED[@]}" -eq 1 ] && [ -s "${SIGNED[0]}" ] || {
    echo "Expected exactly one verified signed APK" >&2; exit 1;
}
cp "${SIGNED[0]}" "$1"
sha256sum "$1"
