class_name ShopCatalog
extends RefCounted
## Everything the store computers sell. "features" are the bullet points on the product card;
## "supply" items are consumables bought by quantity (up to "max") and carried, used with keys 1/2.
const ITEMS = {
	"budget_phone": {"name": "Nova A3 budget smartphone", "price": 2500, "shop": "equipment", "description": "A cheap, sturdy Android phone. Runs the CourierNow delivery app.",
		"features": ["6.1\" screen, 2-day battery", "CourierNow delivery app", "Maps & wallet built in", "Splash resistant"]},
	"water_bottle": {"name": "Water bottle 0.5 L", "price": 150, "shop": "equipment", "supply": true, "max": 6, "description": "Drink on the go (key 1).",
		"features": ["+45% water", "Fits a side pocket", "Buy up to 6"]},
	"energy_bar": {"name": "Oat & date energy bar", "price": 250, "shop": "equipment", "supply": true, "max": 6, "description": "A quick snack between orders (key 2).",
		"features": ["+30% food", "+10% energy", "Buy up to 6"]},
	"bicycle": {"name": "City bicycle (gray)", "price": 12000, "shop": "bikes", "description": "A light gray 7-speed city bike. Your first ride: faster than walking, no fuel. Top speed 18 km/h.",
		"features": ["7-speed hub, disc brakes", "Top speed 18 km/h", "Fits the delivery backpack", "Free bell"]},
	"helmet": {"name": "Cycle helmet", "price": 2800, "shop": "equipment", "description": "Wear a protective helmet while riding."},
	"gloves": {"name": "Riding gloves", "price": 1800, "shop": "equipment", "description": "Padded grips reduce riding fatigue by 15%."},
	"lights": {"name": "Rechargeable lights", "price": 2400, "shop": "equipment", "description": "A working headlight for evening deliveries."},
	"delivery_bag": {"name": "Insulated delivery bag", "price": 3500, "shop": "equipment", "description": "Black thermal courier backpack with a reflective band and a front flap that drops open. Foil-lined shelves: top bay for food bags · middle halves for drinks & desserts · bottom drawer for pizza. Press F to open it. Keeps food hot: +30 s before tips drop."},
	"backpack": {"name": "Courier backpack", "price": 4500, "shop": "equipment", "description": "Reduces walking fatigue by 20%."},
	"commuter_bike": {"name": "Commuter bicycle", "price": 32000, "shop": "bikes", "description": "A geared city bicycle. Top speed: 25 km/h."},
	"scooter": {"name": "Electric scooter", "price": 89000, "shop": "scooters", "description": "Quiet electric transport. Top speed: 32 km/h."},
	"sedan": {"name": "Jetta GLI sedan", "price": 260000, "shop": "cars", "description": "Sporty compact sedan. Drive it: W/S, A/D or mouse steer, Space brake. 43 km/h."},
	"ace11": {"name": "Ace 11 city hatchback", "price": 145000, "shop": "cars", "description": "A small five-door for tight streets and easy parking. 3.8 m long. 43 km/h."},
	"hatchback": {"name": "Compact hatchback", "price": 195000, "shop": "cars", "description": "Short wheelbase for smaller streets. 43 km/h."},
	"suv": {"name": "Family crossover", "price": 315000, "shop": "cars", "description": "A wider, taller vehicle with a larger turning space."},
	"van": {"name": "Delivery van", "price": 285000, "shop": "cars", "description": "A high-roof delivery vehicle. Allow room when parking."},
	"pickup": {"name": "Utility pickup", "price": 295000, "shop": "cars", "description": "Long wheelbase and open cargo bed. 43 km/h."},
}
const CONSUMABLES = {
	"meal": {"name": "Fresh sandwich", "price": 650},
	"water": {"name": "Bottle of water", "price": 150},
	"wc": {"name": "Public washroom", "price": 0},
}
const LOCATIONS = {
	"equipment": Vector3(-92, 0, -32),
	"bikes": Vector3(92, 0, 22),
	"cars": Vector3(-92, 0, 22),
	"scooters": Vector3(92, 0, -32),
}
const TITLES = {"equipment": "TRAIL & TOOL", "bikes": "CEDAR CYCLES", "cars": "NORTHSIDE MOTORS", "scooters": "VOLT SCOOTERS"}

## Product card bullets (falls back to the description).
static func features(id: String) -> Array:
	var item: Dictionary = ITEMS.get(id, {})
	if item.has("features"): return item.features
	return [str(item.get("description", ""))]

static func is_supply(id: String) -> bool:
	return bool((ITEMS.get(id, {}) as Dictionary).get("supply", false))

static func max_qty(id: String) -> int:
	return int((ITEMS.get(id, {}) as Dictionary).get("max", 1))

static func is_car(id: String) -> bool: return id in CityAssets.CAR_TYPES
static func is_vehicle(id: String) -> bool: return id in ["bicycle", "commuter_bike", "scooter"] or is_car(id)
static func vehicle_asset(id: String) -> String: return "bicycle" if id in ["bicycle", "commuter_bike"] else id
static func speed(id: String) -> float: return 12.0 if is_car(id) else {"bicycle": 5.0, "commuter_bike": 7.0, "scooter": 9.0}.get(id, 5.0)
