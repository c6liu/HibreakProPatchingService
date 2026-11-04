#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/tools/lib/build-common.sh"
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <original-vbbot.apk> <output.apk>" >&2
    echo "Set APKTOOL_JAR and APK_SIGNER_JAR, or put the jars in local/." >&2
    exit 1
fi
APKTOOL_JAR="${APKTOOL_JAR:-$ROOT/local/apktool.jar}"
APK_SIGNER_JAR="${APK_SIGNER_JAR:-$ROOT/local/uber-apk-signer.jar}"
RELEASE_KEYSTORE="${APK_RELEASE_KEYSTORE:-}"
RELEASE_ALIAS="${APK_RELEASE_KEY_ALIAS:-}"
RELEASE_CERT_SHA256="${APK_RELEASE_CERT_SHA256:-}"
for tool in java python3 sha256sum; do
    hibreak_require_tool "$tool"
done
for input in "$1" "$APKTOOL_JAR" "$APK_SIGNER_JAR"; do
    hibreak_require_file "$input"
done
[ -z "$RELEASE_KEYSTORE" ] && [ -z "$RELEASE_ALIAS" ] &&
    [ -z "$RELEASE_CERT_SHA256" ] || {
    [ -n "$RELEASE_KEYSTORE" ] && [ -n "$RELEASE_ALIAS" ] &&
        [ -n "$RELEASE_CERT_SHA256" ] || {
        echo "Set APK_RELEASE_KEYSTORE, APK_RELEASE_KEY_ALIAS, and APK_RELEASE_CERT_SHA256 together." >&2
        exit 1
    }
}
hibreak_refuse_overwrite "$2"
EXPECTED=7e45b54372dd21070cbfbb33f0c0b19bb0aea57382d2e6bab92896db747d6ed7
ACTUAL="$(sha256sum "$1" | cut -d ' ' -f 1)"
[ "$ACTUAL" = "$EXPECTED" ] || {
    echo "Unsupported base APK ($ACTUAL). See docs/build/inputs.md for the tested input." >&2
    exit 1
}
mkdir -p "$ROOT/build"
TMP="$(mktemp -d "$ROOT/build/apk.XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
java -jar "$APKTOOL_JAR" d "$1" -o "$TMP/app"
python3 "$ROOT/tools/patch-apk.py" "$TMP/app"
hibreak_build_and_sign_apk "$APKTOOL_JAR" "$APK_SIGNER_JAR" "$TMP/app" \
    "$TMP/HiBreakEink.apk" "$TMP/signed" "$2" \
    "$RELEASE_KEYSTORE" "$RELEASE_ALIAS" "$RELEASE_CERT_SHA256"
