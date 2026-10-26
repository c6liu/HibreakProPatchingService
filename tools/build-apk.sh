#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
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
    command -v "$tool" >/dev/null || { echo "Missing dependency: $tool" >&2; exit 1; }
done
for input in "$1" "$APKTOOL_JAR" "$APK_SIGNER_JAR"; do
    [ -s "$input" ] || { echo "Missing input: $input" >&2; exit 1; }
done
[ -z "$RELEASE_KEYSTORE" ] && [ -z "$RELEASE_ALIAS" ] &&
    [ -z "$RELEASE_CERT_SHA256" ] || {
    [ -n "$RELEASE_KEYSTORE" ] && [ -n "$RELEASE_ALIAS" ] &&
        [ -n "$RELEASE_CERT_SHA256" ] || {
        echo "Set APK_RELEASE_KEYSTORE, APK_RELEASE_KEY_ALIAS, and APK_RELEASE_CERT_SHA256 together." >&2
        exit 1
    }
}
if [ -n "$RELEASE_KEYSTORE" ]; then
    [ -s "$RELEASE_KEYSTORE" ] || {
        echo "Missing release keystore: $RELEASE_KEYSTORE" >&2; exit 1;
    }
    RELEASE_CERT_SHA256="${RELEASE_CERT_SHA256//:/}"
    [[ "$RELEASE_CERT_SHA256" =~ ^[[:xdigit:]]{64}$ ]] || {
        echo "APK_RELEASE_CERT_SHA256 must be a 64-digit SHA-256 certificate fingerprint." >&2
        exit 1
    }
fi
[ ! -e "$2" ] || { echo "Refusing to overwrite: $2" >&2; exit 1; }
EXPECTED=7e45b54372dd21070cbfbb33f0c0b19bb0aea57382d2e6bab92896db747d6ed7
ACTUAL="$(sha256sum "$1" | cut -d ' ' -f 1)"
[ "$ACTUAL" = "$EXPECTED" ] || {
    echo "Unsupported base APK ($ACTUAL). See docs/BUILDING.md for the tested input." >&2
    exit 1
}
mkdir -p "$ROOT/build"
TMP="$(mktemp -d "$ROOT/build/apk.XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
java -jar "$APKTOOL_JAR" d "$1" -o "$TMP/app"
python3 "$ROOT/tools/patch-apk.py" "$TMP/app"
java -jar "$APKTOOL_JAR" b "$TMP/app" -o "$TMP/HiBreakEink.apk"
if [ -n "$RELEASE_KEYSTORE" ]; then
    echo "Signing with release alias '$RELEASE_ALIAS'; enter keystore/key passwords at the signer prompts."
    java -jar "$APK_SIGNER_JAR" -a "$TMP/HiBreakEink.apk" \
        --ks "$RELEASE_KEYSTORE" --ksAlias "$RELEASE_ALIAS" \
        --verifySha256 "$RELEASE_CERT_SHA256" -o "$TMP/signed"
else
    java -jar "$APK_SIGNER_JAR" -a "$TMP/HiBreakEink.apk" -o "$TMP/signed"
fi
SIGNED_APKS=("$TMP"/signed/*.apk)
[ "${#SIGNED_APKS[@]}" -eq 1 ] && [ -s "${SIGNED_APKS[0]}" ] || {
    echo "Expected exactly one verified signed APK in $TMP/signed." >&2
    exit 1
}
cp "${SIGNED_APKS[0]}" "$2"
sha256sum "$2"
