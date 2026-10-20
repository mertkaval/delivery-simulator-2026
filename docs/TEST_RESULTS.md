# Test results

## City expansion

City suite added to the runner: sidewalk path bounds, all 12 address raycasts, three physical restaurant counters, restaurant-specific order ownership and save validation, traffic count, red crossing stop, green resume, and obstacle stop before player. All existing regression/economy/dispatch suites rerun. Daylight city and Market Noodles views captured and inspected with Forward+ on the local RTX 3070 Laptop GPU. Realistic art quality, long traffic soak and performance targets remain unverified.

## Current regression pass

Run `powershell -File tests/run_tests.ps1` from the project. The runner fails on engine errors, failed checks, missing success output or nonzero exit; each process has a frame limit so assertion failures cannot hang forever.

Economy and dispatch suites pass. The expanded regression suite covers malformed interaction distances, carrying save/reload, twenty repeated delivery attempts, backup recovery, preserved corrupt primary, invalid upgrades/fractional currency, mount alignment, independent riding look, moving/stopped dismount, paused phone clock, kitchen route exit, and physical interaction rays at all six doors. Save tests use uniquely named files and remove only their own fixtures.

Headless tests exercise logic and physics; they do not establish enjoyable bicycle handling or city-wide obstacle-free routing. Real rendering is checked separately by `tests/capture_ui.gd`.

## Version 0.2 UI and simulation

- Godot 4.7.2 headless import: passed without script errors.
- `tests/dispatch_test.gd`: passed delayed dispatch, one pending offer, expiry cooldown, offline/closed blocking, accepted pickup after closing, persisted schedule/seed, and 10:1 game-time ratio.
- Existing scene smoke: passed physical pickup and correct-door delivery; now deliberately skips user save writes.
- `tests/capture_ui.gd`: rendered title, incoming-offer phone and nighttime HUD with the actual Forward+ D3D12 renderer on RTX 3070 Laptop GPU. Screenshots inspected for map visibility, title separation, phone layout and nighttime illumination.
- Timing is provisional design tuning. Long-duration balance and independent gameplay navigation testing remain outstanding.

## Scene smoke test

- Build: local workspace, Godot 4.7.2 stable
- Command: `Godot_v4.7.2-stable_win64_console.exe --headless --path . --quit-after 120 -- --smoke-test`
- Scenario: start session, raycast pickup counter, secure matching bag, raycast destination door, complete delivery, verify wallet and save
- Result: PASS
- Evidence: `SCENE SMOKE PASS: real raycast pickup, correct door, receipt, autosave`

## Editor import check

- Command: `Godot_v4.7.2-stable_win64_console.exe --headless --path . --editor --quit`
- Result: PASS; all scripts registered and project imported without parser errors.

## Still unverified

Visual readability, controller support, frame-time budget, bicycle handling, and save recovery on a full Windows restart require owner playtesting in the running window.
