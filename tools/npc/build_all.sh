#!/bin/bash
# Build every NPC spec (or the ids given) headless, 4 at a time; logs in tmp/build_<id>.log.
cd "$(dirname "$0")/../.."
B="/c/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"
ids="$@"
[ -z "$ids" ] && ids=$(python -c "ns={}; exec(open('tools/npc/people.py',encoding='utf-8').read(), ns); print(' '.join(ns['PEOPLE']))")
printf '%s\n' $ids | xargs -P 4 -I{} sh -c "\"$B\" --background --python tools/npc/build_npc.py -- {} > tmp/build_{}.log 2>&1; grep -h 'BUILT\|Traceback' tmp/build_{}.log | head -1 | sed 's/^/{}: /'"
