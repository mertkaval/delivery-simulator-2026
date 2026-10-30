"""The timestamped event map of "How to Use City Road Maker 2.1 - Full Blender Tutorial" (3Dz, YouTube 4XV2aqDHDtY,
43:12, Blender 5.0.0 in the video), built from the transcript and the contact sheets / settled panel states.

Each event: id, time of the frame that shows the result (m:ss), chapter, action, visible result, evidence class
(A directly observed, B transcript only, C inferred, D unresolved), crop name -> (x, y, w, h) on the 1920x1080 frame.

    python -I tools/roads/crm_reconstruction/build/events.py <video.mp4>     extracts the evidence frames + crops"""
import json, os, subprocess, sys

PANEL = (1558, 310, 360, 690)          # Properties editor, modifier panel (Layout workspace)
PANEL_GN = (1628, 330, 290, 650)       # Properties editor in the Geometry Nodes workspace
NODES = (0, 470, 1575, 435)            # node editor (Geometry Nodes workspace)
VIEW = (0, 60, 1525, 545)              # 3D viewport (Layout workspace, asset browser below)
ASSETS = (0, 610, 1525, 370)           # asset browser

EVENTS = [
    # id, time, chapter, action, visible result, class, crops
    ("E01", "0:44", "Installing Asset Library", "Edit > Preferences > File Paths: add the CRM 2.1.1 folder as an asset library",
     "asset library entry added (method 1)", "B", {}),
    ("E02", "1:02", "Installing Asset Library", "asset browser on library CRM 2.1.1, drag 'Simple road *GN' in",
     "catalogs 01. Roads ... 10. Markings; the road object appears", "A", {"assets": ASSETS}),
    ("E03", "1:24", "Installing Asset Library", "Blender 4.3 / 4.5: drag-and-drop a road",
     "every drop brings object references again (import issue)", "B", {}),
    ("E04", "1:52", "Installing Asset Library", "Blender 5: asset browser, Import Settings 'Pack'",
     "no duplicated references", "A", {"assets": ASSETS}),
    ("E05", "2:59", "Installing Asset Library", "drag the 'simple intersection' sample (a collection of collections)",
     "some collections come in packed: geometry node inputs not editable", "B", {}),
    ("E06", "3:40", "Installing Asset Library", "File > Append > CRM 2.1.1.blend > Collection, select all, append (method 2, recommended)",
     "CRM collections in the current file", "A", {}),
    ("E07", "4:47", "Installing Asset Library", "copy the two catalog files into the project directory",
     "Current File asset view shows the categories", "B", {}),
    ("E08", "5:08", "Road Setup", "select the road: modifier 'GeometryNodes' with node group '01. CRM Road'",
     "panels Curve, Road, RoadSide, Road Median, Start Point, End Point, Extend, Manage", "A", {"panel": PANEL}),
    ("E09", "5:47", "Road Setup", "Tab into edit mode on a packed/linked road",
     "error asking to make the data local; Object > Make Local fixes it", "A", {"view": VIEW}),
    ("E10", "6:09", "Road Setup", "edit mode: scale / extrude the curve points (never scale in object mode)",
     "the road follows the drawn curve (red tongues at both ends)", "A", {"view": VIEW}),
    ("E11", "6:15", "Road Setup", "Curve panel", "Resolution 24, Pull Terrain, Export Ready", "A", {"panel": PANEL}),
    ("E12", "6:39", "Road Setup", "Road panel: shoulders, Double Lanes, Asphalt Type, marking lines",
     "Asphalt Type 'New'; Edge / Center / Lane Markings with Line 1 / Line 2 patterns, Width 0.12 m", "A", {"panel": PANEL}),
    ("E13", "6:46", "Road Setup", "Road panel: Bicycle Lane, Patches, Wet Asphalt, Manholes",
     "Wet* puddles 0.4 wetness 0.2; Patches density / size min-max / seed", "A", {"panel": PANEL}),
    ("E14", "6:53", "Road Setup", "RoadSide panel: Type 'Unpaved*'", "roadside type menu, curb, outer curb, manholes, wet", "A", {"panel": PANEL}),
    ("E15", "8:06", "Road Setup", "File > External Data > Unpack Resources (textures for export)",
     "menu shown", "A", {"view": VIEW}),
    ("E16", "8:47", "Road Setup", "Double Lanes on; Road Median panel", "median road with its own roadside-like settings; centre marking", "A", {"panel": PANEL}),
    ("E17", "8:52", "Road Setup", "Road panel: Parking Lane", "Order Bicycle-Parking, Left / Right Parking, Divider Line 5.5 m, Hatched Area", "A", {"panel": PANEL}),
    ("E18", "9:41", "Road Setup", "RoadSide: My Props collection + Random Collection 'Rocks'",
     "props every Spacing (10 m) left / right; rocks scattered (Density Factor 0.1)", "A", {"panel": PANEL, "view": VIEW}),
    ("E19", "10:45", "Road Setup", "Start Point: Tongue Size, Crosswalk Zebra, End Line, End Marking Stop, Traffic Lights",
     "crosswalk, STOP and a signal at the road start; red tongue beyond", "A", {"panel": PANEL, "view": VIEW}),
    ("E20", "10:28", "Road Setup", "Extend panel", "Start / End Point Offset with Edge / Center / Lane Marking, Median / Roadside Props, Parking, Bus/Bicycle, Bridge Piers", "A", {"panel": PANEL}),
    ("E21", "11:06", "Junction Setup", "four roads ending at a crossing, drag 'Custum junction' in",
     "red cross of road tongues; nothing converts yet", "A", {"view": VIEW}),
    ("E22", "11:22", "Junction Setup", "junction modifier '02. CRM Junctions'", "Roads collection empty; Show, Range 40 m, Inner Radius 2 m, Resolution 10", "A", {"panel": PANEL}),
    ("E23", "11:57", "Junction Setup", "collections 'Roads' and 'Junctions'; set the junction's Roads",
     "tongues inside the range become one junction mesh", "A", {"view": VIEW}),
    ("E24", "12:21", "Junction Setup", "Alt + click RoadSide on all selected roads", "every road gets its roadside; junction corners yellow", "A", {"view": VIEW}),
    ("E25", "12:27", "Junction Setup", "junction RoadSide on; Show off / on", "red part -> road, yellow part -> roadside", "A", {"view": VIEW, "panel": PANEL}),
    ("E26", "13:03", "Junction Setup", "tongues must overlap slightly; a too long tongue", "merging issues", "A", {"view": VIEW}),
    ("E27", "13:30", "Junction Setup", "tongues must share one global height", "misaligned tongues avoided", "B", {"view": VIEW}),
    ("E28", "15:54", "Junction Setup", "downhill road: Make Local + single user, last three points level (global Z)",
     "aligned tongue on a slope; junction clean after moving the point back", "A", {"view": VIEW}),
    ("E29", "16:18", "Junction Setup", "do not rotate / scale the junction in object mode", "range circle", "B", {"view": VIEW}),
    ("E30", "17:00", "Junction Setup", "edit mode: scale the junction's cube", "everything inside the volume converts", "A", {"view": VIEW}),
    ("E31", "17:45", "Junction Setup", "Range 1000 m", "every intersection in the scene converted by one junction object", "A", {"view": VIEW, "panel": PANEL}),
    ("E32", "18:21", "Junction Setup", "overlapping junctions", "double meshes: black effect in Cycles", "A", {"view": VIEW}),
    ("E33", "18:42", "Extension Feature", "Extensions catalog", "three extensions: two mesh-based, one curve-based, red / yellow like tongues", "A", {"assets": ASSETS}),
    ("E34", "19:16", "Extension Feature", "square extension in the Roads collection inside the junction", "converted to road mesh", "A", {"view": VIEW, "panel": PANEL}),
    ("E35", "20:48", "Extension / Bus Stop", "square extension at the road edge, Make Local, scale in edit mode",
     "bus bay notch in the roadside", "A", {"view": VIEW}),
    ("E36", "21:33", "Extension / Bus Stop", "bus stop asset + BUS / STOP markings (at level 1 like the roads)", "furnished bus bay", "A", {"view": VIEW}),
    ("E37", "22:48", "Extension / Rounded End-road", "round extension at a road end, smaller, roadside smaller", "cul-de-sac bulb", "A", {"view": VIEW}),
    ("E38", "24:30", "Extension / Roundabout", "round extension at a crossing + 'sidewalk round' + greenery", "roundabout", "A", {"view": VIEW}),
    ("E39", "26:02", "Extension / Roundabout", "alternative: tongues + sidewalk round only", "roundabout without the big rounded asphalt", "A", {"view": VIEW}),
    ("E40", "27:51", "Extension / Parking Space", "big square extension + small square entrance (apply scale)", "parking area with an entrance", "A", {"view": VIEW}),
    ("E41", "28:45", "Extension / Parking Space", "Marking Lines curve ('03. CRM Marking Lines'), Array modifier", "parking bay lines", "A", {"view": VIEW, "panel": PANEL}),
    ("E42", "30:13", "Extension / Parking Space", "curve extension ('10. CRM Extension'), junction range increased to cover the tongues", "a junction made of extensions", "A", {"view": VIEW, "panel": PANEL}),
    ("E43", "31:06", "Custom Sign", "Custom Sign: Panel shape / colour, Back Post shape / struts / poles", "sign panel and post", "A", {"view": VIEW, "panel": PANEL}),
    ("E44", "31:45", "Custom Sign", "Text Line 1..3: three texts each (colour, size, X, Y)", "up to nine texts", "A", {"panel": PANEL}),
    ("E45", "32:47", "Custom Sign", "node editor: '13. CRM Custom Sign' > 'Panel Text' > String to Curves font", "the font is chosen inside the group", "A", {"nodes": NODES, "panel": PANEL_GN}),
    ("E46", "33:22", "Custom Sign", "Images: material + size / X / Y (three)", "image on the sign from a material", "A", {"panel": PANEL}),
    ("E47", "34:57", "Custom Sign", "a stop sign built with the custom sign (Octagon, Red, outline)", "stop sign", "A", {"view": VIEW, "panel": PANEL}),
    ("E48", "35:17", "Custom Sign", "Lines Shap: up to three lines (colour, length, width, rotation, X, Y)", "lines on the panel", "A", {"panel": PANEL}),
    ("E49", "36:04", "Tunnel / Bridge", "tunnel ('12. CRM_Tunnel') comes without a road: duplicate its curve, add Geometry Nodes '01. CRM Road'", "road exactly under the tunnel", "A", {"view": VIEW, "panel": PANEL}),
    ("E50", "36:21", "Tunnel / Bridge", "cable-stayed bridge ('15. CRM Cable-Stayed'): the same", "road on the bridge", "A", {"view": VIEW, "panel": PANEL}),
    ("E51", "36:52", "Mountain Road", "terrain ('16. CRM Terrain'), view clip end 10000", "terrain object", "A", {"view": VIEW, "panel": PANEL}),
    ("E52", "37:47", "Mountain Road", "draw a road on it, Pull Terrain on, terrain Roads = 'Roads'", "terrain pulled to the road", "A", {"view": VIEW, "panel": PANEL}),
    ("E53", "39:13", "Mountain Road", "Flatting Size 32.5 m, Smoothness 3; fix the road's rotation", "flattened corridor", "A", {"view": VIEW, "panel": PANEL}),
    ("E54", "41:03", "Mountain Road", "bridge segment: Pull Terrain off, Bridge, Bridge Barrier, Piers, Pier Height", "bridge over the valley", "A", {"view": VIEW, "panel": PANEL}),
    ("E55", "42:44", "Mountain Road", "bridge abutment assets at both ends (rotation Z 180)", "finished mountain road", "A", {"view": VIEW}),
]


def seconds(t):
    m, s = t.split(":"); return int(m) * 60 + float(s)


def extract(video, out_dir):
    fr = os.path.join(out_dir, "frames"); cr = os.path.join(out_dir, "crops"); os.makedirs(fr, exist_ok=True); os.makedirs(cr, exist_ok=True)
    index = []
    for eid, t, chapter, action, result, cls, crops in EVENTS:
        s = seconds(t); tag = "%s_%s" % (eid, t.replace(":", "m"))
        # the full frame as JPEG (q2, full 1920 x 1080); crops cut from a lossless PNG of the same frame
        lossless = os.path.join(os.path.dirname(os.path.abspath(video)), "frames_png", tag + "_after.png"); os.makedirs(os.path.dirname(lossless), exist_ok=True)
        after = os.path.join(fr, tag + "_after.jpg"); before = os.path.join(fr, tag + "_before.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.2f" % s, "-i", video, "-frames:v", "1", "-y", lossless], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-i", lossless, "-q:v", "2", "-y", after], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.2f" % max(s - 3.0, 0.0), "-i", video, "-frames:v", "1", "-q:v", "2", "-y", before], check=True)
        rec = {"id": eid, "time": t, "seconds": s, "chapter": chapter, "action": action, "result": result, "class": cls,
               "frame_after": "frames/" + tag + "_after.jpg", "frame_before": "frames/" + tag + "_before.jpg", "crops": []}
        for name, (x, y, w, h) in crops.items():
            cp = os.path.join(cr, "%s_%s.png" % (tag, name))
            subprocess.run(["ffmpeg", "-v", "error", "-i", lossless, "-vf", "crop=%d:%d:%d:%d" % (w, h, x, y), "-y", cp], check=True)
            rec["crops"].append({"name": name, "file": "crops/%s_%s.png" % (tag, name), "bounds_xywh": [x, y, w, h], "source": rec["frame_after"]})
        index.append(rec)
    with open(os.path.join(out_dir, "index.json"), "w") as f: json.dump(index, f, indent=1)
    return index


if __name__ == "__main__":
    video = sys.argv[1]
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evidence")
    idx = extract(video, out)
    print("EVIDENCE %d events, %d crops -> %s" % (len(idx), sum(len(r["crops"]) for r in idx), out))
