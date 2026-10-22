"""Rebuild the downtown fire escape (world/downtown/assets/fire_escape.glb + _far) with the urban
kit's own helpers (build_urban_kit.py / build_city_assets.py), leaving every other kit asset as is.

The original stair ran from the landing 2.5 m back *into* the building (z -0.1 .. -2.52), through
the facade and any neighbour behind it. The stair now climbs along the facade inside the landing's
footprint, and two brackets tie the landing back to the wall (it floated 0.4 m off it).

blender --background --factory-startup --python tools/rebuild_fire_escape.py
"""
import os

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "world", "downtown")
SRC = os.path.join(HERE, "build_urban_kit.py")
code = open(SRC, encoding="utf-8-sig").read()
# Keep the header (helpers, materials, save()) and stop before the first module is built.
header = code.split("\ndef frame(")[0]
# The helpers resolve their output folder from __file__: run them as the urban kit would.
__file__ = SRC
exec(compile(header, SRC, "exec"), globals())

clear()
# Landing: grate bars from 0.4 to 1.5 m out, guard rails at both ends and along the front.
for x in [-1, 1]: tube('Escape rail', [(x, .1, .4), (x, 1.1, .4), (x, 1.1, 1.5), (x, .1, 1.5)], .024, METAL, 8)
tube('Escape rail', [(-1, 1.1, 1.5), (1, 1.1, 1.5)], .024, METAL, 8)
for z in [.4 + i * .1 for i in range(12)]: panel('Fire escape grate', (0, 0, z), (2.2, .04, .04), METAL, .006)
# Wall brackets under the landing, from 6.5 cm off the wall: the facade's floor bands, frame rails
# and sills stand up to 6 cm proud there and the tubes ran through them.
for x in [-.9, .9]: tube('Escape bracket', [(x, -.04, 0.065), (x, -.04, .46)], .03, METAL, 8)
# Stair along the facade (x), 0.5 m wide in the middle of the landing, 12 risers of 0.22 m.
for i in range(1, 13): panel('Stair tread', (-.95 + .158 * i, .22 * i, 1.1), (.16, .05, .5), METAL, .008)
for z in [.84, 1.36]: tube('Stair stringer', [(-1.0, 0.0, z), (.95, 2.65, z)], .035, METAL, 8)
save('fire_escape')
