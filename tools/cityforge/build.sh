#!/usr/bin/env bash
# CityForge: the whole city from its two spec files, in one go.
#   tools/cityforge/build.sh [work_dir]
# 1 terrain   tools/terrain/city_terrain.py  port_halden_terrain.json -> terrain.npz, meta.json
# 2 plan      tools/cityforge/plan_city.py   port_halden_city.json (+ overrides.json) -> city.json, graded heights
# 3 build     tools/cityforge/build_city.py  (Blender, headless) -> kit.glb, outskirts.glb, chunks/*.glb, preview .blend
# 4 install   copy into assets/cityforge and reimport in Godot
# 5 test      tests/cityforge_test.gd
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${1:-$ROOT/tmp/cityforge}"
BLENDER="${BLENDER:-/c/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe}"
GODOT="${GODOT:-/c/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe}"
cd "$ROOT"
mkdir -p "$WORK"
echo "== terrain"
"$BLENDER" --background --factory-startup --python tools/terrain/city_terrain.py -- tools/cityforge/port_halden_terrain.json "$WORK/terrain" norender | grep -E "cells|Error" || true
echo "== plan"
python -I tools/cityforge/plan_city.py tools/cityforge/port_halden_city.json "$WORK/terrain" "$WORK/plan"
echo "== build (Blender)"
rm -rf "$WORK/build"
"$BLENDER" --background --factory-startup --python tools/cityforge/build_city.py -- "$WORK/plan" "$WORK/build" --blend "$WORK/build/port_halden.blend" | grep -E "^BUILD|Error|Traceback" || true
echo "== install"
mkdir -p assets/cityforge/chunks
rm -f assets/cityforge/chunks/*.glb
cp "$WORK/build/kit.glb" "$WORK/build/outskirts.glb" assets/cityforge/
cp "$WORK/build/chunks/"*.glb assets/cityforge/chunks/
cp "$WORK/plan/city.json" "$WORK/plan/heights.f32" assets/cityforge/
"$GODOT" --headless --path . --import > /dev/null 2>&1 || true
if grep -l "valid=false" assets/cityforge/*.import assets/cityforge/chunks/*.import 2>/dev/null; then
  echo "Some imports failed (is the Godot editor open?): delete those .import files and run again"; exit 1
fi
echo "== test"
"$GODOT" --headless --path . --script res://tests/cityforge_test.gd 2>&1 | grep -E "FAIL|CITYFORGE"
