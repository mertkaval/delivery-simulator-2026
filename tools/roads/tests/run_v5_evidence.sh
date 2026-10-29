#!/usr/bin/env bash
# Road Studio v5 evidence run (Git Bash on Windows). Rebuilds the library base from a factory scene, runs the full
# street-block validation (regeneration scenarios, frontage rules, export, day / night renders, save + reopen),
# then the Godot captures, the swept traversal + 5 cm lip scan, the traversal recordings (Movie Maker -> MP4),
# the Asset Browser package and the Blender | Godot comparison sheets.
#   bash tools/roads/tests/run_v5_evidence.sh [out_dir]          (SKIP_LIBRARY=1 skips the asset-package step)
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd -W 2>/dev/null || pwd)"
OUT="${1:-tmp/roads/v5/final}"
B="${BLENDER:-/c/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe}"
G="${GODOT:-/c/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe}"
mkdir -p "$OUT" "$OUT/godot" "$OUT/traversal" "$OUT/rec" "$OUT/compare"
WOUT="$ROOT/$OUT"
step() { echo "== $(date +%H:%M:%S) $*"; }

step "blender: base + street block validation (full)"
rm -f tmp/roads/v4/base_built.blend
MRS_V4_OUT="$WOUT" timeout 7200 "$B" -b --factory-startup --python tools/roads/tests/street_block_v4_test.py > "$OUT/log_blender.txt" 2>&1
grep -E "STREET_BLOCK_V4|PROBLEM|FRONTAGE_CHECK|SCENARIO|EXPORT|MOVEMENTS|ROUTES" "$OUT/log_blender.txt" | cut -c1-300

step "godot: captures (day / night, perf)"
timeout 1800 "$G" --path . --script res://tests/capture_street_block_v4.gd -- "$WOUT/export" "$WOUT/godot" "$WOUT/export/cameras.json" > "$OUT/log_godot.txt" 2>&1
grep -E "BLOCK|CAPTURED|GODOT_V4|ERROR" "$OUT/log_godot.txt" | cut -c1-260 | head -60

step "godot: swept traversal + lip scan"
timeout 1800 "$G" --headless --path . --script res://tests/traverse_street_block_v5.gd -- "$WOUT/export" "$WOUT/traversal" > "$OUT/log_traverse.txt" 2>&1
grep -E "TRAVERSE|FAIL|LIPS|lip |step |PROBE" "$OUT/log_traverse.txt" | cut -c1-260

for sc in junction street frontage footbridge trees night; do
  step "godot: recording $sc"
  timeout 2400 "$G" --path . --resolution 1280x720 --fixed-fps 30 --write-movie "$WOUT/rec/$sc.avi" \
      --script res://tests/record_street_block_v5.gd -- "$WOUT/export" "$sc" > "$OUT/rec/log_$sc.txt" 2>&1
  grep -E "RECORD|EVENT|ERROR" "$OUT/rec/log_$sc.txt" | cut -c1-200 | head -12
  if [ -f "$OUT/rec/$sc.avi" ]; then
    ffmpeg -hide_banner -loglevel error -y -i "$OUT/rec/$sc.avi" -c:v libx264 -crf 23 -preset medium -pix_fmt yuv420p -movflags +faststart "$OUT/rec/$sc.mp4" && rm -f "$OUT/rec/$sc.avi"
  fi
done

if [ -z "${SKIP_LIBRARY:-}" ]; then
  step "blender: asset browser package + fresh-file verification"
  MRS_LIB_OUT="$WOUT/library" timeout 3600 "$B" -b --factory-startup --python tools/roads/tests/asset_library_test.py > "$OUT/log_library.txt" 2>&1
  grep -E "BUILT|LIBRARY|FRESH|VERIFY|PROBLEM|ASSET_LIBRARY" "$OUT/log_library.txt" | cut -c1-400
fi

step "comparison sheets"
python tools/roads/tests/compare_sheets.py "$OUT/renders" "$OUT/godot" "$OUT/compare" | wc -l
step "done"
