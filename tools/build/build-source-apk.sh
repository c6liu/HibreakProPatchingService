#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/tools/lib/build-common.sh"
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <output.apk>" >&2
    exit 1
fi
APK_SIGNER_JAR="${APK_SIGNER_JAR:-$ROOT/local/uber-apk-signer.jar}"
RELEASE_KEYSTORE="${APK_RELEASE_KEYSTORE:-}"
RELEASE_ALIAS="${APK_RELEASE_KEY_ALIAS:-}"
RELEASE_CERT_SHA256="${APK_RELEASE_CERT_SHA256:-}"
for tool in gradle java sha256sum; do
    hibreak_require_tool "$tool"
done
hibreak_require_file "$APK_SIGNER_JAR"
hibreak_refuse_overwrite "$1"
hibreak_validate_apk_signing "$RELEASE_KEYSTORE" "$RELEASE_ALIAS" "$RELEASE_CERT_SHA256"

mkdir -p "$ROOT/build"
TMP="$(mktemp -d "$ROOT/build/source-apk.XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
gradle --no-daemon --project-dir "$ROOT" --project-cache-dir "$TMP/project-cache" \
    "-PhibreakBuildDir=$TMP/gradle-output" :app:assembleRelease
hibreak_sign_apk "$APK_SIGNER_JAR" \
    "$TMP/gradle-output/gradle/app/outputs/apk/release/app-release-unsigned.apk" \
    "$TMP/signed" "$1" "$RELEASE_KEYSTORE" "$RELEASE_ALIAS" "$RELEASE_CERT_SHA256"
