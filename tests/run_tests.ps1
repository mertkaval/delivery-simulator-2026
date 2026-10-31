# Headless suites, then the rendered audits (GPU needed). -HeadlessOnly stops after the headless
# suites (CI runners have no GPU).
param([string]$Godot = 'C:\Godot\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64_console.exe', [switch]$HeadlessOnly)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path $PSScriptRoot -Parent
foreach ($testFile in @('asset_budget_test.gd', 'economy_smoke.gd', 'dispatch_test.gd', 'regression.gd', 'city_test.gd', 'lifestyle_test.gd', 'street_grid_test.gd', 'citykit_test.gd', 'bicycle_steering_test.gd', 'car_steering_test.gd', 'ace11_drive_test.gd', 'traffic_long_vehicle_test.gd', 'prop_placement_test.gd', 'landscape_test.gd', 'higgsfield_housing.gd', 'downtown_gameplay.gd', 'urban_access.gd', 'delivery_flow_test.gd', 'cedar_house_test.gd', 'main_menu_test.gd', 'tutorial_test.gd', 'easy_delivery_test.gd', 'traffic_signal_test.gd', 'npc_life_test.gd', 'monuments_test.gd', 'audio_test.gd', 'house_conflict_test.gd', 'third_person_test.gd', 'kerb_step_test.gd', 'courier_actions_test.gd', 'prop_collision_test.gd', 'cityforge_test.gd', 'port_halden_game_test.gd')) {
    $result = & $Godot --headless --path $projectPath --quit-after 30000 --script "res://tests/$testFile" 2>&1
    $status = $LASTEXITCODE
    $result | Write-Output
    if ($status -ne 0 -or ($result -match 'SCRIPT ERROR|ERROR:|FAIL:') -or -not ($result -match 'PASS|: [0-9]+ checks, 0 failures|REGRESSION:.*0 failures|URBAN ACCESS: 0 failures|MAIN MENU: [0-9]+ checks, 0 failures|TUTORIAL PASS: [0-9]+ checks, 0 failures|AUDIO: [0-9]+ checks, 0 failures|HOUSE CONFLICT PASS: [0-9]+ checks, 0 failures|PROP COLLISION PASS: [0-9]+ checks, 0 failures')) {
        throw "Test failed: $testFile"
    }
}

# The same Port Halden suites on the roads-only city (assets/cityforge_roads: the city the game plays by default)
$roadsCity = 'res://assets/cityforge_roads/'
foreach ($testFile in @('cityforge_test.gd', 'port_halden_game_test.gd')) {
    $result = & $Godot --headless --path $projectPath --quit-after 30000 --script "res://tests/$testFile" -- $roadsCity 2>&1
    $status = $LASTEXITCODE
    $result | Write-Output
    if ($status -ne 0 -or ($result -match 'SCRIPT ERROR|ERROR:|FAIL:') -or -not ($result -match ': [0-9]+ checks, 0 failures')) {
        throw "Test failed: $testFile (roads city)"
    }
}

if ($HeadlessOnly) {
    Write-Output 'HEADLESS SUITES PASS'
    return
}

# Rendered audits (MultiMesh instance transforms only exist with a renderer): the city-wide
# z-fighting / overlap / piercing / decal-lift / LOD conflict audit of the non-residential city.
foreach ($testFile in @('city_conflict_test.gd')) {
    $result = & $Godot --path $projectPath --quit-after 3000 --script "res://tests/$testFile" 2>&1
    $status = $LASTEXITCODE
    $result | Write-Output
    if ($status -ne 0 -or ($result -match 'SCRIPT ERROR|FAIL:') -or -not ($result -match 'CITY CONFLICT PASS')) {
        throw "Test failed: $testFile"
    }
}

# Port Halden's Mert Road Studio streets: loaded in place of CityForge's, solid on every street and sidewalk
# (trimesh collision from imported meshes needs a renderer).
foreach ($testFile in @('port_halden_streets_test.gd')) {
    $result = & $Godot --path $projectPath --quit-after 6000 --script "res://tests/$testFile" 2>&1
    $status = $LASTEXITCODE
    $result | Write-Output
    if ($status -ne 0 -or ($result -match 'SCRIPT ERROR|FAIL:') -or -not ($result -match 'PORT_HALDEN_STREETS: [0-9]+ checks, 0 failures')) {
        throw "Test failed: $testFile"
    }
}

# ... and on the roads-only city
$result = & $Godot --path $projectPath --quit-after 6000 --script "res://tests/port_halden_streets_test.gd" -- $roadsCity 2>&1
$status = $LASTEXITCODE
$result | Write-Output
if ($status -ne 0 -or ($result -match 'SCRIPT ERROR|FAIL:') -or -not ($result -match 'PORT_HALDEN_STREETS: [0-9]+ checks, 0 failures')) {
    throw "Test failed: port_halden_streets_test.gd (roads city)"
}

# Frame-time / boot / video-memory budgets of the real game on the reference machine (rendered): the classic city,
# then the roads-only Port Halden the game plays by default.
foreach ($cityArgs in @(@(), @('--', $roadsCity))) {
    $result = & $Godot --path $projectPath --quit-after 6000 --script "res://tests/perf_budget_test.gd" @cityArgs 2>&1
    $status = $LASTEXITCODE
    $result | Write-Output
    if ($status -ne 0 -or ($result -match 'SCRIPT ERROR|FAIL:') -or -not ($result -match 'PERF BUDGET PASS')) {
        throw "Test failed: perf_budget_test.gd $cityArgs"
    }
}
