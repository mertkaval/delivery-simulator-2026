#!/usr/bin/env bash
# CityForge: the whole city from its two spec files, in one go.
#   tools/cityforge/build.sh [work_dir]
#   --materials   also rebake the material library (tools/cityforge/materials.py, ~1 min)
#   --houses      also rebuild the house catalogue (tools/cityforge/houses.py, ~4 min)
#   --cf-streets  CityForge's own street ribbons and street furniture instead of Mert Road Studio's
#                 (default: tools/cityforge/mrs_streets.py builds roads, junctions, lanes, bridges and street assets)
#   --with-buildings  the classic city (CityForge's buildings, lots, parks) into assets/cityforge; by default the
#                 roads-only city (Mert Road Studio streets on the natural terrain, frontage plots) goes into
#                 assets/cityforge_roads and the classic city is left as it is
# 0 materials / houses (optional, slow; their outputs live in assets/cityforge and are committed)
# 1 terrain   tools/terrain/city_terrain.py  port_halden_terrain.json -> terrain.npz, meta.json
# 2 plan      tools/cityforge/plan_city.py   port_halden_city.json (+ overrides.json) -> city.json, graded heights
# 2b streets  tools/cityforge/mrs_streets.py (Blender, Mert Road Studio) -> mrs/ (chunk GLBs, kit, records) and the
#             plan without CityForge's street props, the ground fitted under the MRS surfaces
# 3 build     tools/cityforge/build_city.py  (Blender, headless) -> kit.glb, outskirts.glb, chunks/*.glb, preview .blend
# 3b map      tools/cityforge/assemble_map.py -> port_halden_map.blend: streets + terrain + water, to open in Blender
# 3c check    tools/cityforge/mrs_junction_atlas.py on the map: every road, junction, sign and lane mouth validated in
#             Blender (renders of every junction); problems stop the build before anything reaches Godot (--force)
# 4 install   copy into assets/cityforge and reimport in Godot
# 5 test      tests/cityforge_test.gd
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$ROOT/tmp/cityforge"
case "${1:-}" in ""|--*) ;; *) WORK="$1" ;; esac
BLENDER="${BLENDER:-/c/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe}"
GODOT="${GODOT:-/c/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe}"
cd "$ROOT"
mkdir -p "$WORK"
for arg in "$@"; do
  case "$arg" in
    --materials) echo "== materials"; "$BLENDER" --background --factory-startup --python tools/cityforge/materials.py -- assets/cityforge/materials | grep -E "^MATERIAL |Traceback"; "$GODOT" --headless --path . --import > /dev/null 2>&1 || true; python -I tools/cityforge/setup_materials.py ;;
    --houses) echo "== houses"; "$BLENDER" --background --factory-startup --python tools/cityforge/houses.py -- assets/cityforge | grep -E "CATALOGUE|FAILED|Traceback" ;;
  esac
done
echo "== terrain"
"$BLENDER" --background --factory-startup --python tools/terrain/city_terrain.py -- tools/cityforge/port_halden_terrain.json "$WORK/terrain" norender | grep -E "cells|Error" || true
echo "== plan"
python -I tools/cityforge/plan_city.py tools/cityforge/port_halden_city.json "$WORK/terrain" "$WORK/plan"
echo "== street audit"
python -I tools/cityforge/audit_streets.py "$WORK/plan/city.json" "$WORK/street_audit.md" | tail -1
PLAN="$WORK/plan"
MRS=1
ROADS_ONLY=1
for arg in "$@"; do [ "$arg" = "--cf-streets" ] && MRS=0; [ "$arg" = "--with-buildings" ] && ROADS_ONLY=0; done
[ "$MRS" = 0 ] && ROADS_ONLY=0
if [ "$ROADS_ONLY" = 1 ]; then DEST=assets/cityforge_roads; BUILD="$WORK/build_roads"; STREETS_OPT=""; else DEST=assets/cityforge; BUILD="$WORK/build"; STREETS_OPT="--with-buildings"; fi
if [ "$MRS" = 1 ]; then
  echo "== streets (Blender, Mert Road Studio)"
  rm -rf "$WORK/mrs_out"
  "$BLENDER" --background --factory-startup --python tools/cityforge/mrs_streets.py -- "$WORK/plan" "$WORK/mrs_out" --blend "$WORK/mrs_out/port_halden_streets.blend" $STREETS_OPT       | grep -E "^NETWORK|^JUNCTIONS|^PLACEMENT|^PLAN|^MRS_STREETS|Error|Traceback" || true
  [ -f "$WORK/mrs_out/mrs/mrs_city.json" ] || { echo "MRS streets failed"; exit 1; }
  PLAN="$WORK/mrs_out/plan"
fi
echo "== build (Blender)"
rm -rf "$BUILD"
"$BLENDER" --background --factory-startup --python tools/cityforge/build_city.py -- "$PLAN" "$BUILD" --blend "$BUILD/port_halden.blend" | grep -E "^BUILD|Error|Traceback" || true
if [ "$MRS" = 1 ]; then
  echo "== map (Blender)"
  "$BLENDER" --background "$WORK/mrs_out/port_halden_streets.blend" --python tools/cityforge/assemble_map.py -- "$BUILD/port_halden.blend" "$WORK/port_halden_map.blend" | grep -E "^MAP|Error|Traceback" || true
  echo "== check (Blender)"
  rm -rf "$WORK/atlas"
  "$BLENDER" --background "$WORK/port_halden_map.blend" --python tools/cityforge/mrs_junction_atlas.py -- "$WORK/atlas" | grep -E "^ATLAS|Traceback" || true
  [ -f "$WORK/atlas/sheet_manifest.json" ] && python -I tools/cityforge/contact_sheet.py "$WORK/atlas/sheet_manifest.json" | tail -1
  FORCE=0; for arg in "$@"; do [ "$arg" = "--force" ] && FORCE=1; done
  if ! python -I -c "import json,sys; r=json.load(open(sys.argv[1])); sys.exit(1 if r['problems'] or r['lane_mouths_without_kerb'] else 0)" "$WORK/atlas/validation.json"; then
    [ "$FORCE" = 1 ] || { echo "Validation found problems ($WORK/atlas/validation.json): nothing installed (--force to install anyway)"; exit 1; }
  fi
fi
echo "== install -> $DEST"
mkdir -p "$DEST/chunks"
rm -f "$DEST/chunks/"*.glb
cp "$BUILD/kit.glb" "$BUILD/outskirts.glb" "$DEST/"
cp "$BUILD/chunks/"*.glb "$DEST/chunks/"
cp "$PLAN/city.json" "$PLAN/heights.f32" "$DEST/"
rm -rf "$DEST/mrs"
if [ "$MRS" = 1 ]; then
  mkdir -p "$DEST/mrs/chunks"
  cp "$WORK/mrs_out/mrs/"*.glb "$WORK/mrs_out/mrs/mrs_city.json" "$DEST/mrs/"
  cp "$WORK/mrs_out/mrs/chunks/"*.glb "$DEST/mrs/chunks/"
fi
"$GODOT" --headless --path . --import > /dev/null 2>&1 || true
if [ "$MRS" = 1 ]; then
  # textures the import extracted from the MRS GLBs come in Lossless: VRAM compression, then import again
  python -I tools/cityforge/vram_textures.py "$DEST/mrs"
  "$GODOT" --headless --path . --import > /dev/null 2>&1 || true
fi
if grep -l "valid=false" "$DEST"/*.import "$DEST"/chunks/*.import "$DEST"/mrs/*.import "$DEST"/mrs/chunks/*.import 2>/dev/null; then
  echo "Some imports failed (is the Godot editor open?): delete those .import files and run again"; exit 1
fi
echo "== test"
"$GODOT" --headless --path . --script res://tests/cityforge_test.gd -- "res://$DEST/" 2>&1 | grep -E "FAIL|CITYFORGE"
