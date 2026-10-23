"""List the licence metadata of every downloaded model (Sketchfab writes title, author, licence and
URL into the GLB's asset.extras) and flag what needs attention.

    python tools/asset_ledger.py            # table of every source model
    python tools/asset_ledger.py --check    # exit 1 if a model is not CC BY / CC0 or is not in ASSET_LICENSES.md

Scans the raw download folders (sketchup_assets/, source_assets/incoming_*/, the project root);
converted game assets under assets/ are built from these by tools/prepare_*.py."""
import glob, json, os, struct, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FOLDERS = ["sketchup_assets", "source_assets/incoming_*", "."]
OPEN = ("CC-BY-4.0", "CC0", "CC-BY-3.0")


def meta(path):
    try:
        with open(path, "rb") as f:
            head = f.read(20)
            n = struct.unpack("<I", head[12:16])[0]
            return json.loads(f.read(n)).get("asset", {}).get("extras", {}) or {}
    except Exception:
        return None


def scan():
    seen = {}
    for pattern in FOLDERS:
        for folder in glob.glob(os.path.join(ROOT, pattern)):
            for path in sorted(glob.glob(os.path.join(folder, "*.glb"))):
                m = meta(path)
                if m is None:
                    continue
                key = m.get("source") or os.path.basename(path)
                seen.setdefault(key, dict(m, file=os.path.relpath(path, ROOT).replace("\\", "/")))
    return seen


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ledger = open(os.path.join(ROOT, "ASSET_LICENSES.md"), encoding="utf-8").read()
    problems = 0
    for key, m in sorted(scan().items(), key=lambda kv: (kv[1].get("title") or kv[0]).lower()):
        lic = m.get("license") or "NO METADATA"
        flags = []
        if not lic.startswith(OPEN):
            flags.append("RESTRICTED" if m.get("license") else "UNKNOWN SOURCE")
        if m.get("source") and m["source"] not in ledger:
            flags.append("NOT IN ASSET_LICENSES.md")
        problems += bool(flags)
        print("%-45s %-24s %-32s %s %s" % ((m.get("title") or "?")[:45], lic.split(" (")[0][:24],
                                           (m.get("author") or "?").split(" (")[0][:32], m["file"], " ".join(flags)))
    if "--check" in sys.argv and problems:
        print("%d model(s) need attention" % problems)
        sys.exit(1)


if __name__ == "__main__":
    main()
