class_name StreetNames
extends RefCounted
## Street, park and memorial names. Streets honour figures of the Turkish War of
## Independence; downtown avenues honour Turkish scientists. Each street is one or more
## axis-aligned centreline segments with the carriageway half-width.

## name, sign text, segments [[a, b, half], ...]
const STREETS := [
	["Mustafa Kemal Atatürk Avenue", "ATATÜRK AV", [[Vector2(0, 44), Vector2(0, -690), 6.0]]],
	["Nezahat Onbaşı Street", "NEZAHAT ONBAŞI ST", [[Vector2(-64, 48), Vector2(64, 48), 4.0]]],
	["Kâzım Karabekir Road", "K. KARABEKİR RD", [[Vector2(-64, 48), Vector2(-64, -258), 4.0]]],
	["Ali Fuat Cebesoy Road", "A. F. CEBESOY RD", [[Vector2(64, 48), Vector2(64, -258), 4.0]]],
	["İsmet İnönü Street", "İSMET İNÖNÜ ST", [[Vector2(-64, -258), Vector2(-64, -678), 5.0]]],
	["Fevzi Çakmak Street", "FEVZİ ÇAKMAK ST", [[Vector2(64, -258), Vector2(64, -678), 5.0]]],
	["Refet Bele Street", "REFET BELE ST", [[Vector2(-69, -258), Vector2(120, -258), 5.0], [Vector2(120, -258), Vector2(492, -258), 7.0]]],
	["Rauf Orbay Street", "RAUF ORBAY ST", [[Vector2(-69, -398), Vector2(120, -398), 5.0], [Vector2(120, -398), Vector2(492, -398), 7.0]]],
	["Kara Fatma Street", "KARA FATMA ST", [[Vector2(-69, -538), Vector2(120, -538), 5.0], [Vector2(120, -538), Vector2(492, -538), 7.0]]],
	["Şerife Bacı Street", "ŞERİFE BACI ST", [[Vector2(-69, -678), Vector2(120, -678), 5.0], [Vector2(120, -678), Vector2(492, -678), 7.0]]],
	["Cahit Arf Street", "CAHİT ARF ST", [[Vector2(144, -246), Vector2(144, -690), 7.0]]],
	["Aziz Sancar Avenue", "AZİZ SANCAR AV", [[Vector2(252, -246), Vector2(252, -690), 9.0]]],
	["Feza Gürsey Street", "FEZA GÜRSEY ST", [[Vector2(360, -246), Vector2(360, -690), 7.0]]],
	["Gazi Yaşargil Street", "G. YAŞARGİL ST", [[Vector2(468, -246), Vector2(468, -690), 7.0]]],
]

## Parks keyed by centre (x, z): name and the figure honoured by the bust.
const PARKS := {
	Vector2(-64, -145): "Gördesli Makbule Park",
	Vector2(64, -145): "Halime Çavuş Park",
	Vector2(-44, -330): "Yörük Ali Efe Park",
	Vector2(44, -330): "Hasan Tahsin Park",
	Vector2(-44, -470): "Sütçü İmam Park",
	Vector2(44, -470): "Şahin Bey Park",
	Vector2(-44, -590): "Şekerci Ökkeş Park",
	Vector2(44, -590): "Bombacı Ahmet Park",
}

const SQUARE := "Atatürk Square"
## Street-art murals: honoured name and a short dedication.
const MURALS := [
	["KARA FATMA", "Fatma Seher Erden · Kuva-yi Milliye"],
	["TAYYAR RAHMİYE", "Hero of the Aegean front"],
	["NEZAHAT ONBAŞI", "The youngest corporal"],
	["HALİME ÇAVUŞ", "Ammunition carrier of Kastamonu"],
	["SÜTÇÜ İMAM", "The first shot at Maraş"],
	["HASAN TAHSİN", "The first bullet at İzmir"],
]

static func segments() -> Array[Dictionary]:
	var list: Array[Dictionary] = []
	for street in STREETS:
		for s in street[2]:
			list.append({"name": street[0], "sign": street[1], "a": s[0], "b": s[1], "half": s[2]})
	return list

static func distance(p: Vector2, segment: Dictionary) -> float:
	return Geometry2D.get_closest_point_to_segment(p, segment.a, segment.b).distance_to(p)

## Name of the street at a world position (carriageway plus sidewalks), or "".
static func name_at(at: Vector3, reach: float = 5.5) -> String:
	var p := Vector2(at.x, at.z)
	var best := ""
	var best_distance := INF
	for segment in segments():
		var d := distance(p, segment) - float(segment.half)
		if d < reach and d < best_distance:
			best_distance = d
			best = segment.name
	return best

static func park_at(at: Vector3) -> String:
	for centre in PARKS:
		if absf(at.x - centre.x) < 12.0 and absf(at.z - centre.y) < 18.0: return PARKS[centre]
	return ""

## Location line for the HUD: street, park, square or the district name.
static func describe(at: Vector3) -> String:
	var street := name_at(at)
	if street != "": return street
	var park := park_at(at)
	if park != "": return park
	if at.x > 120: return "Rainline Downtown"
	return "Cedar Heights"

## Junctions as {"at": Vector2, "x_street", "z_street", "x_half", "z_half"}: one per crossing
## of a north-south (constant x) and an east-west (constant z) street, T-junctions included.
static func junctions() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var seen := {}
	var list := segments()
	for v in list:
		if not is_equal_approx(v.a.x, v.b.x): continue
		for h in list:
			if not is_equal_approx(h.a.y, h.b.y): continue
			var point := Vector2(v.a.x, h.a.y)
			if distance(point, v) > 6.0 or distance(point, h) > 6.0: continue
			var key := "%d_%d" % [roundi(point.x), roundi(point.y)]
			if seen.has(key): continue
			seen[key] = true
			result.append({"at": point, "x_street": v.sign, "z_street": h.sign, "x_half": v.half, "z_half": h.half})
	return result

## Point on a carriageway (with a small margin): signs and props must avoid these.
static func on_carriageway(p: Vector2, margin: float = 0.6) -> bool:
	for segment in segments():
		if distance(p, segment) < float(segment.half) + margin: return true
	return false
