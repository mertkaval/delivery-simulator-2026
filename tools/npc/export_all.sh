#!/bin/bash
# Export every built NPC master (or the ids given) to assets/people/<id>.glb at the townspeople
# texture budget (skin 1024, the rest 512), 4 at a time; then write assets/people/people.json.
cd "$(dirname "$0")/../.."
B="/c/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"
ids="$@"
[ -z "$ids" ] && ids=$(python -c "ns={}; exec(open('tools/npc/people.py',encoding='utf-8').read(), ns); print(' '.join(ns['PEOPLE']))")
mkdir -p assets/people
for id in $ids; do
  name=$(python -c "ns={}; exec(open('tools/npc/people.py',encoding='utf-8').read(), ns); print(ns['PEOPLE']['$id']['name'])")
  echo "$id $name"
done | xargs -P 4 -L 1 sh -c 'm="source_assets/npc/$1/$1_master.blend"; [ -f "$m" ] || { echo "$0: no master"; exit 0; }; "'"$B"'" --background --factory-startup --python tools/npc/export_npc.py -- "$m" "$1" "assets/people/$0.glb" 1024 512 > "tmp/export_$0.log" 2>&1; grep -h "NPC_EXPORT_DONE\|Traceback" "tmp/export_$0.log" | head -1 | sed "s/^/$0: /"'
python tools/npc/manifest.py
