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

hibreak_validate_apk_signing() {
    local keystore="${1:-}" alias="${2:-}" cert="${3:-}"
    if [ -n "$keystore" ] || [ -n "$alias" ] || [ -n "$cert" ]; then
        [ -n "$keystore" ] && [ -n "$alias" ] && [ -n "$cert" ] || {
            echo "Set APK_RELEASE_KEYSTORE, APK_RELEASE_KEY_ALIAS, and APK_RELEASE_CERT_SHA256 together." >&2
            return 1
        }
        hibreak_require_file "$keystore" || return
        local normalized_cert="${cert//:/}"
        [[ "$normalized_cert" =~ ^[[:xdigit:]]{64}$ ]] || {
            echo "APK_RELEASE_CERT_SHA256 must be a 64-digit SHA-256 certificate fingerprint." >&2
            return 1
        }
    fi
}

hibreak_sign_apk() {
    local signer="$1" unsigned="$2" signed_dir="$3" output="$4"
    shift 4
    local keystore="${1:-}" alias="${2:-}" cert="${3:-}"
    local -a signed_apks

    hibreak_require_file "$signer" || return
    hibreak_require_file "$unsigned" || return
    hibreak_refuse_overwrite "$output" || return
    hibreak_validate_apk_signing "$keystore" "$alias" "$cert" || return
    if [ -n "$keystore" ]; then
        echo "Signing with release alias '$alias'; enter keystore/key passwords at the signer prompts."
        java -jar "$signer" -a "$unsigned" --ks "$keystore" --ksAlias "$alias" \
            --verifySha256 "${cert//:/}" -o "$signed_dir" || return
    else
        java -jar "$signer" -a "$unsigned" -o "$signed_dir" || return
    fi
    signed_apks=("$signed_dir"/*.apk)
    [ "${#signed_apks[@]}" -eq 1 ] && [ -s "${signed_apks[0]}" ] || {
        echo "Expected exactly one verified signed APK in $signed_dir." >&2
        return 1
    }
    dd if="${signed_apks[0]}" of="$output" bs=1M conv=excl status=none || {
        echo "Cannot create signed APK without overwriting: $output" >&2
        return 1
    }
    sha256sum "$output"
}

hibreak_build_and_sign_apk() {
    local apktool="$1" signer="$2" app="$3" unsigned="$4" signed_dir="$5" output="$6"
    shift 6

    hibreak_require_file "$apktool" || return
    hibreak_require_file "$signer" || return
    hibreak_refuse_overwrite "$output" || return
    java -jar "$apktool" b "$app" -o "$unsigned" || return
    hibreak_sign_apk "$signer" "$unsigned" "$signed_dir" "$output" "$@"
}
