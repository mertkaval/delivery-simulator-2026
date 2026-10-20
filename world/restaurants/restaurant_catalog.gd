class_name RestaurantCatalog
extends RefCounted
## The sixteen Turkish restaurants. The first three use the original Atatürk Avenue
## restaurant buildings (CityCatalog pickups 0-2); the other thirteen occupy ground-floor
## storefronts of the mixed-use corridor (CityLayout midrises) and become pickups 8-20.
## Interiors are assembled from the Blender restaurant kit by RestaurantInteriors.

## Corridor midrise serials (CityLayout "id") that keep their shop instead of a restaurant.
const KEEP_SHOPS := [2, 8, 13]

## id, name, Turkish name, tagline, signature, floor, wainscot, wall, accent, seat, menu
const LIST := [
	["cedar_kitchen", "Kebab House", "Kebapçı", "CHARCOAL GRILL · SINCE 1974", "mangal_doner", "terrazzo", "cini", "f1e3c8", "8e2b1f", "8e2b1f",
		["Adana Kebab ₺320", "Urfa Kebab ₺320", "Chicken Şiş ₺280", "Lahmacun ₺120", "Ayran ₺40"]],
	["market_noodles", "Meatball Restaurant", "Köfteci", "TEKİRDAĞ STYLE KÖFTE", "mangal", "wood", "wood", "e8dcc2", "2f4a3a", "6b3a22",
		["Grilled Köfte ₺260", "İnegöl Köfte ₺270", "Piyaz Salad ₺90", "Rice Pilaf ₺70", "Şalgam ₺45"]],
	["harbor_pizza", "Turkish Pizza Parlor", "Pideci", "STONE OVEN PİDE & LAHMACUN", "pide", "terrazzo", "cini", "f3e6cf", "1d3f8f", "b8322a",
		["Kaşarlı Pide ₺210", "Kıymalı Pide ₺240", "Karışık Pide ₺270", "Lahmacun ₺120", "Ayran ₺40"]],
	["kokorech_shop", "Kokorech Shop", "Kokoreççi", "LATE NIGHT · CHARCOAL", "kokorec", "terrazzo", "cini", "efe2c4", "b8322a", "3a2a20",
		["Kokoreç Half ₺220", "Kokoreç Full ₺380", "Midye Dolma ₺15", "Pickles ₺40", "Ayran ₺40"]],
	["fish_restaurant", "Fish Restaurant", "Balıkçı", "FRESH FROM THE MARKET", "fish", "terrazzo", "cini", "e4ecef", "1f4f6f", "1f4f6f",
		["Balık Ekmek ₺190", "Grilled Levrek ₺480", "Hamsi Tava ₺320", "Rocket Salad ₺90", "Lemonade ₺60"]],
	["iskender_house", "Iskender Kebab House", "İskenderci", "BURSA STYLE · BROWN BUTTER", "iskender", "wood", "wood", "f0e2c6", "7a1d1d", "7a1d1d",
		["İskender ₺390", "Half İskender ₺290", "Pide Kebab ₺340", "Kemalpaşa Dessert ₺110", "Ayran ₺40"]],
	["dessert_shop", "Dessert Shop", "Tatlıcı", "BAKLAVA · KADAYIF · KÜNEFE", "dessert", "terrazzo", "cini", "f6ead2", "2d6a4a", "c78838",
		["Pistachio Baklava ₺180", "Künefe ₺160", "Kadayıf ₺150", "Şöbiyet ₺170", "Turkish Tea ₺25"]],
	["soup_house", "Soup House", "Çorbacı", "OPEN 24 HOURS", "soup", "terrazzo", "cini", "efe6d6", "8a4b1c", "8a4b1c",
		["Lentil Soup ₺110", "Ezogelin ₺110", "Tripe Soup ₺150", "Yayla Soup ₺110", "Fresh Bread ₺0"]],
	["doner_shop", "Doner Shop", "Dönerci", "HAND CARVED · EVERY DAY", "doner", "terrazzo", "cini", "f2e4c8", "c0392b", "c0392b",
		["Döner Dürüm ₺210", "Döner Plate ₺290", "Chicken Döner ₺180", "Fries ₺70", "Ayran ₺40"]],
	["local_diner", "Local Diner", "Esnaf Lokantası", "HOME COOKING · DAILY TRAYS", "diner", "terrazzo", "wood", "f4ecd8", "35553f", "35553f",
		["Kuru Fasulye ₺160", "Rice Pilaf ₺70", "Karnıyarık ₺190", "Etli Nohut ₺180", "Cacık ₺60"]],
	["tavern", "Tavern", "Meyhane", "MEZE · MUSIC · RAKI", "tavern", "wood", "wood", "e6d6b8", "4a2a1a", "6b1f2a",
		["Meze Platter ₺420", "Haydari ₺90", "Fried Kalamar ₺290", "Çiğ Börek ₺150", "White Cheese & Melon ₺140"]],
	["pastry_shop", "Pastry Shop", "Börekçi & Fırın", "SİMİT · POĞAÇA · BÖREK", "pastry", "terrazzo", "cini", "f7edd8", "a35a1e", "a35a1e",
		["Su Böreği ₺130", "Simit ₺20", "Cheese Poğaça ₺30", "Açma ₺25", "Turkish Tea ₺25"]],
	["bulgur_wrap", "Spiced Bulgur Wrap Shop", "Çiğ Köfteci", "VEGAN · HANDMADE DAILY", "cigkofte", "terrazzo", "cini", "edeccc", "2f7a3a", "2f7a3a",
		["Çiğ Köfte Dürüm ₺90", "Double Dürüm ₺150", "Çiğ Köfte Plate ₺160", "Pomegranate Sauce ₺0", "Şalgam ₺45"]],
	["pancake_house", "Pancake House", "Gözleme & Krep", "GÖZLEME · KREP · BREAKFAST", "crepe", "wood", "wood", "f6e9d0", "d0743a", "d0743a",
		["Cheese Gözleme ₺140", "Potato Gözleme ₺130", "Chocolate Krep ₺150", "Menemen ₺160", "Turkish Tea ₺25"]],
	["baked_potato", "Baked Potato Shop", "Kumpirci", "ORTAKÖY STYLE KUMPİR", "kumpir", "terrazzo", "cini", "f3ead6", "d39b1e", "1d5f8a",
		["Classic Kumpir ₺180", "Kumpir Deluxe ₺240", "Corn Cup ₺70", "Pickles ₺40", "Lemonade ₺60"]],
	["dairy_dessert", "Dairy Dessert Parlor", "Muhallebici", "SÜTLAÇ · KAZANDİBİ · TAVUK GÖĞSÜ", "dairy", "terrazzo", "cini", "f8f1e2", "3c6fa0", "3c6fa0",
		["Fırın Sütlaç ₺110", "Kazandibi ₺120", "Tavuk Göğsü ₺120", "Keşkül ₺110", "Salep ₺70"]],
]

static func ids() -> Array:
	return LIST.map(func(r: Array) -> String: return r[0])

static func entry(id: String) -> Array:
	for r in LIST:
		if r[0] == id: return r
	return []

static func colours(r: Array) -> Dictionary:
	# Instance colours multiply the linear albedo: convert the sRGB palette.
	return {"wall": Color(r[7]).srgb_to_linear(), "accent": Color(r[8]).srgb_to_linear(), "seat": Color(r[9]).srgb_to_linear()}

## Corridor midrises that hold restaurants, in catalogue order (entries 3..15).
static func corridor_buildings() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for b in CityLayout.buildings():
		if b.type == "midrise" and not (int(b.id) in KEEP_SHOPS): result.append(b)
	return result

## Catalogue entry of the restaurant occupying a CityLayout midrise, or [].
static func entry_for_building(b: Dictionary) -> Array:
	if b.get("type", "") != "midrise" or int(b.id) in KEEP_SHOPS: return []
	var k := 0
	for other in CityLayout.buildings():
		if other.type != "midrise" or int(other.id) in KEEP_SHOPS: continue
		if int(other.id) == int(b.id): return LIST[3 + k]
		k += 1
	return []

## Interior frame of a corridor restaurant: origin at the facade centre on the ground,
## +z towards the street. The restaurant spans bays 0 .. bays-2 (the last bay is the lobby).
static func frame(b: Dictionary) -> Transform3D:
	return Transform3D(Basis(Vector3.UP, b.yaw), b.front)

static func restaurant_width(b: Dictionary) -> float:
	return (int(b.bays) - 1) * 4.0

## Local x of the restaurant's centre line and of its entrance bay.
static func centre_x(b: Dictionary) -> float:
	return -int(b.bays) * 2.0 + restaurant_width(b) * 0.5

static func entrance_bay(b: Dictionary) -> int:
	@warning_ignore("integer_division")
	return (int(b.bays) - 1) / 2

static func bay_x(b: Dictionary, i: int) -> float:
	return -int(b.bays) * 2.0 + 2.0 + i * 4.0

## Courier pickup point in front of the pickup shelf (local), counter customer side.
static func pickup_local(b: Dictionary) -> Vector3:
	return Vector3(bay_x(b, entrance_bay(b)) + 3.2, 1.0, -6.85)

## World pickup positions for corridor restaurants (CityCatalog pickups 8..20).
static func corridor_pickups() -> Array:
	var result: Array = []
	for b in corridor_buildings(): result.append(frame(b) * pickup_local(b))
	return result

## Point on the street sidewalk in front of the restaurant door (world).
static func door_outside(b: Dictionary) -> Vector3:
	return frame(b) * Vector3(bay_x(b, entrance_bay(b)), 0, 3.0)
