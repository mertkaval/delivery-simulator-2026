"""Tested parameter limits (docs/roads/LIMITS.md). limits.json next to this file holds, per node group and input, the
range the limit sweeps (tools/roads/limits) proved safe, with a safety margin inside the last value that passed every
check, and the evidence for it:

    {"MRS_Road": {"Lane Width": {"min": 2.4, "max": 5.5, "evidence": "tmp/roads/limits/road/Lane_Width.json", ...}}}

The node-group builders apply them as the sockets' min / max (the UI cannot go outside); validate.check_limits reports
a value set outside them by a script. Combination rules (two inputs that are fine alone but not together) are separate:
validate.py checks them and the groups show a modifier warning."""
import json, os

LIMITS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "limits.json")
_CACHE = {}


def load():
    """{group: {input: {"min", "max", ...}}} (empty when no sweep has been applied)."""
    try: mt = os.path.getmtime(LIMITS_FILE)
    except OSError: return {}
    if _CACHE.get("mtime") != mt:
        with open(LIMITS_FILE, encoding="utf-8") as f: _CACHE["data"] = json.load(f)
        _CACHE["mtime"] = mt
    return _CACHE["data"]


def apply_to_group(tree):
    """Set the tested min / max on the group's input sockets. Returns the number of sockets limited."""
    lim = load().get(tree.name, {}); n = 0
    for it in tree.interface.items_tree:
        if getattr(it, "item_type", "") != "SOCKET" or it.in_out != "INPUT" or it.name not in lim: continue
        r = lim[it.name]
        if hasattr(it, "min_value") and r.get("min") is not None: it.min_value = r["min"]
        if hasattr(it, "max_value") and r.get("max") is not None: it.max_value = r["max"]
        if hasattr(it, "default_value") and hasattr(it, "min_value"):
            it.default_value = min(max(it.default_value, it.min_value), it.max_value)
        n += 1
    return n


def out_of_range(group_name, values):
    """[(input, value, min, max)] of `values` ({input: value}) outside the tested limits of `group_name`."""
    lim = load().get(group_name, {}); out = []
    for k, v in values.items():
        r = lim.get(k)
        if r is None or not isinstance(v, (int, float)) or isinstance(v, bool): continue
        lo, hi = r.get("min"), r.get("max")
        if (lo is not None and v < lo - 1e-9) or (hi is not None and v > hi + 1e-9): out.append((k, v, lo, hi))
    return out
