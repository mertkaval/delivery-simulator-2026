"""OPERATION_LOG.md from evidence/index.json (written by events.py): one row per event, links to its frames and crops.
    python -I tools/roads/crm_reconstruction/build/docs.py"""
import json, os
RECON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
idx = json.load(open(os.path.join(RECON, "evidence", "index.json")))
CLASS = {"A": "A observed", "B": "B transcript", "C": "C inferred", "D": "D unresolved"}
lines = ["# Operation log", "",
         "Every meaningful operation of the tutorial, in order. Times are the frame that shows the result (m:ss). "
         "Class: A directly observed in the frames, B supported by the narration only, C inferred, D unresolved. "
         "`before` is the frame 3 s earlier. Crops are cut from the full frame at the bounds given (x, y, w, h on 1920 x 1080).", ""]
chapter = None
for r in idx:
    if r["chapter"] != chapter:
        chapter = r["chapter"]; lines += ["## %s" % chapter, "", "| id | time | action | visible result | class | evidence |", "|---|---|---|---|---|---|"]
    ev = ["[after](evidence/%s)" % r["frame_after"], "[before](evidence/%s)" % r["frame_before"]]
    ev += ["[%s](evidence/%s) `%s`" % (c["name"], c["file"], ",".join(str(v) for v in c["bounds_xywh"])) for c in r["crops"]]
    lines.append("| %s | %s | %s | %s | %s | %s |" % (r["id"], r["time"], r["action"].replace("|", "/"), r["result"].replace("|", "/"), CLASS[r["class"]], " ".join(ev)))
    nxt = idx[idx.index(r) + 1]["chapter"] if idx.index(r) + 1 < len(idx) else None
    if nxt != chapter: lines.append("")
with open(os.path.join(RECON, "OPERATION_LOG.md"), "w", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")
print("OPERATION_LOG.md: %d events" % len(idx))
