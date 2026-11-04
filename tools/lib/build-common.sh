hibreak_require_tool() {
    command -v "$1" >/dev/null || {
        echo "Missing dependency: $1" >&2
        return 1
    }
}

hibreak_require_file() {
    [ -s "$1" ] || {
        echo "Missing input: $1" >&2
        return 1
    }
}

hibreak_refuse_overwrite() {
    [ ! -e "$1" ] && [ ! -L "$1" ] || {
        echo "Refusing to overwrite: $1" >&2
        return 1
    }
}

hibreak_ndk_bin() {
    : "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to an installed Android NDK}"
    HIBREAK_NDK_BIN="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin"
    local tool
    for tool in "$@"; do
        [ -x "$HIBREAK_NDK_BIN/$tool" ] || {
            echo "Missing NDK tool: $HIBREAK_NDK_BIN/$tool" >&2
            return 1
        }
    done
}

hibreak_build_and_sign_apk() {
    local apktool="$1" signer="$2" app="$3" unsigned="$4" signed_dir="$5" output="$6"
    shift 6
    local keystore="${1:-}" alias="${2:-}" cert="${3:-}"
    local normalized_cert
    local -a signed_apks

    hibreak_require_file "$apktool" || return
    hibreak_require_file "$signer" || return
    hibreak_refuse_overwrite "$output" || return
    java -jar "$apktool" b "$app" -o "$unsigned" || return
    if [ -n "$keystore" ] || [ -n "$alias" ] || [ -n "$cert" ]; then
        [ -n "$keystore" ] && [ -n "$alias" ] && [ -n "$cert" ] || {
            echo "Set APK_RELEASE_KEYSTORE, APK_RELEASE_KEY_ALIAS, and APK_RELEASE_CERT_SHA256 together." >&2
            return 1
        }
        hibreak_require_file "$keystore" || return
        normalized_cert="${cert//:/}"
        [[ "$normalized_cert" =~ ^[[:xdigit:]]{64}$ ]] || {
            echo "APK_RELEASE_CERT_SHA256 must be a 64-digit SHA-256 certificate fingerprint." >&2
            return 1
        }
        echo "Signing with release alias '$alias'; enter keystore/key passwords at the signer prompts."
        java -jar "$signer" -a "$unsigned" --ks "$keystore" --ksAlias "$alias" \
            --verifySha256 "$normalized_cert" -o "$signed_dir" || return
    else
        java -jar "$signer" -a "$unsigned" -o "$signed_dir" || return
    fi
    signed_apks=("$signed_dir"/*.apk)
    [ "${#signed_apks[@]}" -eq 1 ] && [ -s "${signed_apks[0]}" ] || {
        echo "Expected exactly one verified signed APK in $signed_dir." >&2
        return 1
    }
    cp "${signed_apks[0]}" "$output"
    sha256sum "$output"
}
