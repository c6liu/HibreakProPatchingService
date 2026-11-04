#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/lib/build-common.sh"
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <output.apk>" >&2
    exit 1
fi
APKTOOL_JAR="${APKTOOL_JAR:-$ROOT/local/apktool.jar}"
APK_SIGNER_JAR="${APK_SIGNER_JAR:-$ROOT/local/uber-apk-signer.jar}"
for tool in java sha256sum; do
    hibreak_require_tool "$tool"
done
hibreak_require_file "$APKTOOL_JAR"
hibreak_require_file "$APK_SIGNER_JAR"
hibreak_refuse_overwrite "$1"
mkdir -p "$ROOT/build"
TMP="$(mktemp -d "$ROOT/build/ir-api-test.XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
cp -r "$ROOT/tools/ir/api-test" "$TMP/app"
hibreak_build_and_sign_apk "$APKTOOL_JAR" "$APK_SIGNER_JAR" "$TMP/app" \
    "$TMP/AndroidIrApiTest.apk" "$TMP/signed" "$1"
