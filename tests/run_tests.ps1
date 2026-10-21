param([string]$Godot = 'C:\Godot\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64_console.exe')
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path $PSScriptRoot -Parent
foreach ($testFile in @('economy_smoke.gd', 'dispatch_test.gd', 'regression.gd', 'city_test.gd', 'lifestyle_test.gd', 'street_grid_test.gd', 'citykit_test.gd', 'bicycle_steering_test.gd', 'car_steering_test.gd', 'ace11_drive_test.gd', 'traffic_long_vehicle_test.gd', 'prop_placement_test.gd', 'landscape_test.gd', 'higgsfield_housing.gd', 'downtown_gameplay.gd', 'urban_access.gd', 'delivery_flow_test.gd', 'cedar_house_test.gd', 'main_menu_test.gd', 'tutorial_test.gd', 'traffic_signal_test.gd', 'npc_life_test.gd', 'monuments_test.gd', 'audio_test.gd')) {
    $result = & $Godot --headless --path $projectPath --quit-after 30000 --script "res://tests/$testFile" 2>&1
    $status = $LASTEXITCODE
    $result | Write-Output
    if ($status -ne 0 -or ($result -match 'SCRIPT ERROR|ERROR:|FAIL:') -or -not ($result -match 'PASS|: [0-9]+ checks, 0 failures|REGRESSION:.*0 failures|URBAN ACCESS: 0 failures|MAIN MENU: [0-9]+ checks, 0 failures|TUTORIAL PASS: [0-9]+ checks, 0 failures|AUDIO: [0-9]+ checks, 0 failures')) {
        throw "Test failed: $testFile"
    }
}
