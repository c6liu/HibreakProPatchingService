#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/tools/lib/build-common.sh"
if [ "$#" -lt 1 ]; then
    echo "Usage: ANDROID_NDK_HOME=/path/to/ndk $0 <output-binary> [--enforcing-candidate | --enforcing-migration-candidate | experimental options]" >&2
    exit 1
fi
output="$1"
shift
flags=()
candidate=false
migration_candidate=false
experimental=false
for option in "$@"; do
    case "$option" in
        --enforcing-candidate)
            candidate=true
            flags+=(-DHIBREAK_ENFORCING_CANDIDATE)
            ;;
        --enforcing-migration-candidate)
            migration_candidate=true
            ;;
        --experimental-property-only-refresh)
            experimental=true
            flags+=(-DHIBREAK_PROPERTY_ONLY_REFRESH)
            ;;
        --experimental-init-eink-bridge)
            experimental=true
            flags+=(-DHIBREAK_INIT_EINK_BRIDGE)
            ;;
        *)
            echo "Unknown daemon build option: $option" >&2
            exit 1
            ;;
    esac
done
if "$migration_candidate"; then
    if "$candidate" || "$experimental"; then
        echo "The enforcing migration candidate cannot be combined with other build options." >&2
        exit 1
    fi
    candidate=true
    flags+=(-DHIBREAK_ENFORCING_CANDIDATE -DHIBREAK_PROPERTY_ONLY_REFRESH -DHIBREAK_INIT_EINK_BRIDGE -DHIBREAK_SOCKET_AUTH)
fi
if "$candidate" && "$experimental"; then
    echo "Experimental property-only modes cannot be combined with the host-only enforcing candidate." >&2
    exit 1
fi
if "$candidate"; then
    echo "WARNING: development-only enforcing candidate; requires unfinished policy/context migration." >&2
fi
if "$experimental"; then
    echo "WARNING: experimental property-only display controls; behavior is unverified." >&2
fi
hibreak_ndk_bin aarch64-linux-android30-clang llvm-strip
hibreak_refuse_overwrite "$output"
"$HIBREAK_NDK_BIN/aarch64-linux-android30-clang" -O2 -Wall -Wextra -Werror \
    "${flags[@]}" \
    "$ROOT/a9_eink_daemon/eink_daemon.c" "$ROOT/a9_eink_daemon/side_keys.c" \
    "$ROOT/a9_eink_daemon/client_auth.c" -llog -o "$output"
"$HIBREAK_NDK_BIN/llvm-strip" "$output"
sha256sum "$output"
