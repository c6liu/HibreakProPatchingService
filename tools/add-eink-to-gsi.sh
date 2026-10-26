#!/usr/bin/env bash
# Compatibility entry point; the unified patcher includes display and AOD fixes.
set -euo pipefail
exec "$(dirname "$0")/patch-gsi.sh" "$@"
