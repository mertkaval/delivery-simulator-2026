"""Map the game's sound names to the ElevenLabs sounds and level-match them to the mix.

The game asks CityAudio for a sound by name ("door_knock", "tyre_roll", ...). BANK below says
which ElevenLabs files play for each name (a sliced set picks a random take per play). Each
name gets a trim in dB so its short-term loudness (loudest 300 ms RMS) matches the sfx_forge
sound it replaces, which is what the game's volumes were tuned with; new names without a forge
sound are matched to a reference sound or a target loudness instead.

Writes systems/sound_bank.gd. Names not in BANK keep playing assets/audio/sfx/<name>.wav.

usage: python bank.py
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
EL = os.path.join(PROJECT, "assets", "audio", "elevenlabs")
FORGE = os.path.join(PROJECT, "assets", "audio", "sfx")
OUT = os.path.join(PROJECT, "systems", "sound_bank.gd")
sys.path.insert(0, HERE)
from generate import read_wav  # noqa: E402

# name -> (ElevenLabs files or sliced sets, level reference)
# A reference is a forge sound name (match its loudness) or a number (target loudness, dBFS).
BANK = {
    # footsteps (sliced sets: one random take per step)
    "footstep_concrete": (["footsteps/fs_concrete_walk*", "footsteps/fs_asphalt_walk*"], "footstep_concrete"),
    "footstep_run": (["footsteps/fs_asphalt_run*"], "footstep_concrete"),
    "footstep_grass": (["footsteps/fs_grass_walk*"], "footstep_grass"),
    "footstep_wood": (["footsteps/fs_wood_walk*"], "footstep_wood"),
    "footstep_interior": (["footsteps/fs_tile_walk*"], "footstep_interior"),
    "footstep_gravel": (["footsteps/fs_gravel_walk*"], "footstep_gravel"),
    "jump_land": (["footsteps/jump_land*"], "footstep_concrete"),
    # bicycle
    "bike_chain": (["bicycle/bike_pedal_loop"], "bike_chain"),
    "bike_freewheel": (["bicycle/bike_coast_loop"], "bike_freewheel"),
    "tyre_roll": (["bicycle/bike_tyre_roll_loop"], "tyre_roll"),
    "bike_wind": (["bicycle/bike_wind_loop"], "wind_soft"),
    "brake_squeal": (["bicycle/bike_brake"], "brake_squeal"),
    "bike_bell": (["bicycle/bike_bell"], "bike_bell"),
    "bike_mount": (["bicycle/bike_mount"], "package_place"),
    "bike_dismount": (["bicycle/bike_kickstand_down"], "package_place"),
    # ambience
    "city_ambience": (["ambience/amb_city_day_loop"], "city_ambience"),
    "park_ambience": (["ambience/amb_park_loop"], "park_ambience"),
    "restaurant_ambience": (["ambience/amb_restaurant_loop"], "restaurant_ambience"),
    "crickets": (["ambience/amb_night_loop"], "crickets"),
    "rain": (["ambience/rain_light_loop"], "rain"),
    "rain_heavy": (["ambience/rain_heavy_loop"], "rain_heavy"),
    "wind": (["ambience/wind_gust_loop"], "wind"),
    "fountain_water": (["ambience/fountain_loop"], "fountain_water"),
    "house_tone": (["ambience/house_room_tone_loop"], -30.0),
    "thunder": (["ambience/thunder"], -16.0),
    # traffic and streets
    "ped_signal_walk": (["traffic/ped_signal_walk_loop"], "ped_signal_walk"),
    "ped_signal_wait": (["traffic/ped_signal_wait_loop"], "ped_signal_wait"),
    "horn_honk": (["traffic/car_horn_short"], "horn_honk"),
    "horn_long": (["traffic/car_horn_angry"], "horn_honk"),
    "air_brake_hiss": (["traffic/bus_air_brake"], "air_brake_hiss"),
    "shop_door_chime": (["store/shop_door_bell"], "shop_door_chime"),
    "cutlery_clink": (["life/cutlery_clinks*"], "cutlery_clink"),
    "dog_bark": (["life/dog_bark*"], "dog_bark"),
    # phone and delivery app
    "phone_raise": (["phone/phone_out_pocket"], "phone_raise"),
    "phone_tap": (["phone/phone_tap"], "phone_tap"),
    "phone_unlock": (["phone/phone_unlock"], "phone_unlock"),
    "app_locked": (["phone/app_locked"], "app_locked"),
    "notify_order": (["phone/phone_new_order"], "notify_order"),
    "ui_notification": (["phone/phone_new_order"], "ui_notification"),
    "ui_accept": (["phone/phone_accept"], "ui_accept"),
    "ui_reject": (["phone/phone_decline"], "ui_reject"),
    # store
    "kiosk_click": (["store/kiosk_click*"], "kiosk_click"),
    "cart_add": (["store/cart_add"], "cart_add"),
    "cart_remove": (["store/cart_remove"], "cart_remove"),
    "purchase_complete": (["store/purchase_receipt"], "purchase_complete"),
    "not_enough_money": (["store/not_enough_money"], "app_locked"),
    "cash_register": (["ui/money_earned"], "cash_register"),
    # packages, bag, doors
    "item_pickup": (["packages/paper_bag_pickup"], "item_pickup"),
    "package_drop": (["packages/paper_bag_set_down"], "package_drop"),
    "package_place": (["bag/package_into_bag"], "package_place"),
    "package_out_of_bag": (["bag/package_out_of_bag"], "package_place"),
    "bag_zip": (["bag/bag_zip"], "bag_zip"),
    "bag_off_shoulder": (["bag/bag_off_shoulder"], "package_place"),
    "bag_on_shoulder": (["bag/bag_on_shoulder"], "package_place"),
    "bag_velcro_open": (["bag/bag_velcro_open"], "bag_zip"),
    "bag_flap_close": (["bag/bag_flap_close"], "bag_zip"),
    "door_knock": (["doors/door_knock_wood"], "door_knock"),
    "doorbell": (["doors/doorbell_dingdong"], "doorbell"),
    "door_open": (["doors/front_door_open"], "door_open"),
    "door_close": (["doors/front_door_close"], "door_open"),
    "photo_shutter": (["doors/photo_shutter"], "photo_shutter"),
    # UI and progression
    "delivery_complete": (["ui/delivery_complete"], "delivery_complete"),
    "delivery_success": (["ui/delivery_complete"], "delivery_success"),
    "coins": (["ui/tip_coins"], "coins"),
    "step_complete": (["ui/task_complete"], "step_complete"),
    "mission_complete": (["ui/mission_complete"], "mission_complete"),
    "ui_hover": (["ui/ui_hover"], "phone_tap"),
    "ui_click": (["ui/ui_click"], "phone_tap"),
    "ui_back": (["ui/ui_back"], "phone_tap"),
    "save_game": (["ui/save_game"], "step_complete"),
    "day_start": (["ui/day_start"], "step_complete"),
}
MAX_BOOST = 6.0
LOOPS = {"bike_chain", "bike_freewheel", "tyre_roll", "bike_wind", "city_ambience", "park_ambience",
         "restaurant_ambience", "crickets", "rain", "rain_heavy", "wind", "fountain_water", "house_tone",
         "ped_signal_walk", "ped_signal_wait"}


def loudness(path):
    """Loudest 300 ms RMS in dBFS (mono mix)."""
    with open(path, "rb") as fh:
        samples, rate = read_wav(fh.read())
    m = samples.mean(axis=1)
    win = int(0.3 * rate)
    if len(m) <= win:
        return 20 * np.log10(np.sqrt((m ** 2).mean()) + 1e-9)
    sq = np.concatenate([[0.0], np.cumsum(m.astype(np.float64) ** 2)])
    rms = np.sqrt((sq[win:] - sq[:-win]) / win)
    return 20 * np.log10(rms.max() + 1e-9)


def expand(pattern):
    if pattern.endswith("*"):
        files = sorted(glob.glob(os.path.join(EL, pattern[:-1] + "_[0-9][0-9].wav")))
    else:
        files = [os.path.join(EL, pattern + ".wav")]
    missing = [f for f in files if not os.path.exists(f)]
    if missing or not files:
        raise SystemExit(f"missing ElevenLabs file for {pattern}")
    return files


def main():
    lines = []
    for name, (patterns, ref) in BANK.items():
        files = [f for p in patterns for f in expand(p)]
        have = float(np.mean([loudness(f) for f in files]))
        want = ref if isinstance(ref, float) else loudness(os.path.join(FORGE, ref + ".wav"))
        # Files peak at -6 dBFS (generate.py --normalize), so a boost past +6 dB would clip.
        trim = round(min(want - have, MAX_BOOST), 1)
        res = ["res://" + os.path.relpath(f, PROJECT).replace(os.sep, "/") for f in files]
        lines.append(f'\t"{name}": {{"trim": {trim:.1f}, "loop": {"true" if name in LOOPS else "false"}, "files": [\n'
                     + ",\n".join(f'\t\t"{r}"' for r in res) + "]},")
        print(f"{name:22s} {len(files):2d} file(s)  {have:6.1f} -> {want:6.1f} dBFS  trim {trim:+.1f} dB")
    body = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f'''class_name SoundBank
extends RefCounted
## Generated by tools/elevenlabs_sfx/bank.py - do not edit by hand.
## The ElevenLabs sounds (assets/audio/elevenlabs) behind CityAudio's sound names. "files" with
## several entries are takes of one sound (a random one plays each time); "trim" (dB) matches the
## sound's loudness to the sfx_forge sound it replaced, so the game's mix volumes still apply.
## Names missing here play assets/audio/sfx/<name>.wav.

const BANK := {{
{body}
}}
''')
    print(f"wrote {os.path.relpath(OUT, PROJECT)} ({len(BANK)} names)")


if __name__ == "__main__":
    main()
