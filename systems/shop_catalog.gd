class_name ShopCatalog
extends RefCounted
const ITEMS = {
	"helmet": {"name": "Cycle helmet", "price": 2800, "shop": "equipment", "description": "Wear a protective helmet while riding."},
	"gloves": {"name": "Riding gloves", "price": 1800, "shop": "equipment", "description": "Padded grips reduce riding fatigue by 15%."},
	"lights": {"name": "Rechargeable lights", "price": 2400, "shop": "equipment", "description": "A working headlight for evening deliveries."},
	"delivery_bag": {"name": "Insulated delivery bag", "price": 3500, "shop": "equipment", "description": "Black thermal courier backpack with a reflective band and a front flap that drops open. Foil-lined shelves: top bay for food bags · middle halves for drinks & desserts · bottom drawer for pizza. Press F to open it. Keeps food hot: +30 s before tips drop."},
	"backpack": {"name": "Courier backpack", "price": 4500, "shop": "equipment", "description": "Reduces walking fatigue by 20%."},
	"commuter_bike": {"name": "Commuter bicycle", "price": 32000, "shop": "bikes", "description": "A geared city bicycle. Top speed: 25 km/h."},
	"scooter": {"name": "Electric scooter", "price": 89000, "shop": "scooters", "description": "Quiet electric transport. Top speed: 32 km/h."},
	"sedan": {"name": "Jetta GLI sedan", "price": 0, "shop": "cars", "description": "Sporty compact sedan, free for now. Drive it: W/S, A/D or mouse steer, Space brake. 43 km/h."},
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

static func is_car(id: String) -> bool: return id in CityAssets.CAR_TYPES
static func is_vehicle(id: String) -> bool: return id in ["bicycle", "commuter_bike", "scooter"] or is_car(id)
static func vehicle_asset(id: String) -> String: return "bicycle" if id in ["bicycle", "commuter_bike"] else id
static func speed(id: String) -> float: return 12.0 if is_car(id) else {"bicycle": 5.0, "commuter_bike": 7.0, "scooter": 9.0}.get(id, 5.0)
