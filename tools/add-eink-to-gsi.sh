#!/usr/bin/env bash
# Compatibility entry point; the unified patcher includes display and AOD fixes.
set -euo pipefail
echo "Deprecated: use tools/patch-gsi.sh; this compatibility wrapper will be removed in a future release." >&2
exec "$(dirname "$0")/patch-gsi.sh" "$@"
