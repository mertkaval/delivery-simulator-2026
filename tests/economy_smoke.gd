extends SceneTree

func _init() -> void:
	var session := DeliverySession.new()
	session.offer(10.0)
	assert(session.order.quote == 600 + int(round((session.order.pickup_distance + session.order.distance) * 0.2)))
	assert(session.accept())
	assert(session.pickup("wrong_restaurant", 1.0).contains("not your pickup"))
	assert(session.order.state == "ACCEPTED")
	assert(session.pickup("cedar_kitchen", 1.0).contains("Bag secured"))
	assert(session.deliver(4, 1.0).contains("Wrong address"))
	assert(session.order.state == "CARRYING")
	var result := session.deliver(0, 1.0)
	assert(result.contains("DELIVERY COMPLETE"))
	var paid := session.wallet
	assert(paid > session.order.quote)
	assert(session.deliver(0, 1.0).contains("no delivery bag"))
	assert(session.wallet == paid)
	var save := session.snapshot()
	save.player = {"position": [0.0, 0.0, 0.0], "yaw": 0.0}
	assert(DeliverySave.valid_envelope(save))
	print("ECONOMY SMOKE PASS: guards, payout idempotency, and save invariants")
	quit()
