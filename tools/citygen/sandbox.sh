#!/bin/bash
# Runs Blender headless in the isolated tool-evaluation profile (never the user's own config).
T="$(cd "$(dirname "$0")/.." && pwd)"
export BLENDER_USER_CONFIG="$T/sandbox/config"
export BLENDER_USER_SCRIPTS="$T/sandbox/scripts"
export BLENDER_USER_EXTENSIONS="$T/sandbox/extensions"
export PYTHONPATH="$T/sandbox/pylib"
"/c/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" --background --factory-startup --python-use-system-env "$@"
