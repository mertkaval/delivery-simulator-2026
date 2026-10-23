"""Write assets/people/people.json: the townspeople the game can use (built + exported NPCs).
    python tools/npc/manifest.py
Each entry: id, name (GLB root / rig node), scene, skeleton (path to the retargeted skeleton),
role, gender ("f" / "m"), height (m), age (years, approximate)."""
import json, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
ns = {}
exec(open(os.path.join(ROOT, "tools", "npc", "people.py"), encoding="utf-8").read(), ns)
people = dict(ns["PEOPLE"])
# the two characters with their own build scripts
people["middle_aged_woman"] = dict(name="NPC01_MiddleAgedWoman", role="resident",
                                   body=dict(macros=dict(gender=0.0, age=0.69), height=1.64))
people["bugra"] = dict(name="NPC02_BugraBaskan", role="pedestrian", body=dict(macros=dict(gender=1.0, age=0.52), height=1.78))


def years(age):
    # MPFB age macro: 0.5 = 25 y, 1.0 = 90 y (linear above 0.5)
    return round(25 + (age - 0.5) * 130) if age >= 0.5 else round(1 + age * 48)


out = []
for pid, s in people.items():
    glb = os.path.join(ROOT, "assets", "people", pid + ".glb")
    if not os.path.exists(glb):
        continue
    m = s["body"]["macros"]
    out.append(dict(id=pid, name=s["name"], scene="res://assets/people/%s.glb" % pid, skeleton="%s/GeneralSkeleton" % s["name"],
                    role=s["role"], gender="f" if m.get("gender", 0.5) < 0.5 else "m", height=s["body"].get("height", 1.7),
                    age=years(m.get("age", 0.5))))
out.sort(key=lambda e: e["id"])
path = os.path.join(ROOT, "assets", "people", "people.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump({"people": out, "clips": "res://assets/people/npc_role_clips.glb"}, f, indent=2)
print("wrote", os.path.normpath(path), len(out), "people")
