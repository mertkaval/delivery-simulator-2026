extends SceneTree

func _init() -> void:
	var s := DeliverySession.new()
	assert(not s.dispatch(10))
	s.tick(8)
	assert(s.dispatch(10))
	assert(not s.dispatch(10))
	s.tick(31)
	assert(s.order.state == "EXPIRED")
	assert(s.next_offer > s.clock)
	var old := s.snapshot()
	var restored := DeliverySession.new()
	assert(restored.restore(old))
	assert(restored.next_offer == s.next_offer)
	assert(restored.random_seed == s.random_seed)
	s.calendar_minutes = 23 * 60
	s.tick(200)
	assert(not s.dispatch(10))
	s.calendar_minutes = 12 * 60
	s.online = false
	assert(not s.dispatch(10))
	s.online = true
	assert(s.dispatch(10))
	assert(s.accept())
	s.calendar_minutes = 23 * 60
	assert(s.pickup(s.restaurant_id(), 1).begins_with("Bag secured"))
	s.calendar_minutes = 0
	s.tick(60)
	assert(is_equal_approx(s.calendar_minutes, 10.0))
	print("DISPATCH PASS: timing, expiry, offline, closure, accepted-job protection, saved schedule, calendar ratio")
	quit()
