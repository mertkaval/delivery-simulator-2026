#!/usr/bin/env bash
# The add-on install test in a throw-away Blender user-scripts folder (the user's own Blender config is untouched).
#   bash tools/roads/tests/run_addon_test.sh [out_dir]
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${1:-$ROOT/tmp/roads/addon_test}"
BLENDER="${BLENDER:-/c/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe}"
rm -rf "$OUT"; mkdir -p "$OUT/scripts/addons"
WIN_OUT="$(cygpath -w "$OUT" 2>/dev/null || echo "$OUT")"
BLENDER_USER_SCRIPTS="$WIN_OUT\\scripts" "$BLENDER" --background --factory-startup --python "$ROOT/tools/roads/tests/addon_install_test.py" -- "$OUT"
