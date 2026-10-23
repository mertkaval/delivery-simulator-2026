"""The townspeople of Delivery Simulator 2026: one spec per reference image in
reference_images/characters/. Built by tools/npc/build_npc.py (MPFB body + garments.py).

body.macros: MPFB macros (gender 0 female .. 1 male; age 0.5 = 25 y, 0.65 ~ 38 y, 0.77 ~ 55 y,
0.88 ~ 70 y; muscle / weight / proportions 0..1; ethnic mix). body.height in metres.
hair.style: fade | classic | crop | buzz | curly_short | bun_high | bun_low | ponytail | mpfb:<asset>.
face: beard none | stubble | short | full | moustache; age (creases), undereye.
outfit: [(garment, args)] for garments.Outfit (top, jacket, vest, apron, trousers, belt, shoes).
role / work / home: used in the game (assets/people/people.json) for daily routines and clips.
"""

BLACK_HAIR = dict(dark=(8, 7, 7), light=(40, 34, 30))
DARK_BROWN = dict(dark=(16, 11, 8), light=(70, 50, 36))
BROWN = dict(dark=(30, 20, 13), light=(98, 70, 48))
AUBURN = dict(dark=(48, 18, 8), light=(150, 76, 40))
BLONDE = dict(dark=(92, 70, 40), light=(205, 175, 120))
GREY = dict(dark=(90, 88, 86), light=(200, 198, 194))
SALT_PEPPER = dict(dark=(40, 38, 36), light=(150, 146, 140))

PEOPLE = {
    "concierge": dict(
        name="NPC03_Concierge", ref="Apartment Concierge T-Pose Reference-4.png", role="concierge",
        body=dict(macros=dict(gender=0.0, age=0.62, muscle=0.4, weight=0.42, proportions=0.6, asian=0.92, caucasian=0.08),
                  targets={"mouth/mouth-scale-horiz-decr": 0.1},
                  skin="young_asian_female", tint=(0.97, 0.92, 0.88), gamma=1.0, eyes="darkbrown", brows="eyebrow011", height=1.62),
        hair=dict(style="bun_low", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(beard="none", age=0.35, undereye=0.25, lips_mul=(0.92, 0.72, 0.74), lips_desat=0.1),
        outfit=[
            ("top", dict(name="Shirt", color=(244, 242, 236), sleeve="long", neck="collar", hem="tucked", weave="twill", heather=0.02,
                         placket="shirt", cuffs=True, rough=0.75, sheen=0.25)),
            ("trousers", dict(color=(46, 46, 50), kind="slacks", width=0.06, taper=0.012)),
            ("jacket", dict(name="Blazer", color=(48, 48, 52), open=True, opening=(0.06, 0.04, 0.085), lapels=True, pockets="flap",
                            buttons=1, weave="twill", heather=0.04, rough=0.72)),
            ("scarf", dict(color=(120, 22, 36))),
            ("shoes", dict(kind="pump", color=(14, 14, 15))),
        ]),
    "construction_worker": dict(
        name="NPC04_ConstructionWorker", ref="Construction Worker in Orange Safety Vest-7.png", role="construction",
        body=dict(macros=dict(gender=1.0, age=0.6, muscle=0.62, weight=0.58, proportions=0.6, african=0.92, caucasian=0.08),
                  targets={"head/head-round": 0.2, "nose/nose-flaring-incr": 0.3, "chin/chin-width-incr": 0.2},
                  skin="young_african_male", tint=(0.9, 0.86, 0.84), eyes="darkbrown", brows="eyebrow001", height=1.8),
        hair=dict(style="buzz", **BLACK_HAIR), brows=dict(paint=0.0, **BLACK_HAIR),
        face=dict(beard="short", beard_rgb=(10, 8, 7), age=0.35, undereye=0.3, lips_mul=(0.95, 0.85, 0.85), lips_desat=0.2),
        outfit=[
            ("top", dict(name="Polo", color=(28, 36, 62), sleeve="short", neck="collar", hem="untucked", weave="knit", placket="polo",
                         heather=0.05, buttons_rgb=(30, 30, 34))),
            ("trousers", dict(color=(150, 120, 80), kind="cargo", cargo=True, width=0.074, taper=0.006, weave="twill")),
            ("vest", dict(color=(255, 78, 0), kind="hivis", stripes=(188, 190, 192))),
            ("belt", dict(color=(30, 24, 20))),
            ("shoes", dict(kind="boot", color=(84, 56, 34))),
        ]),
    "chef": dict(
        name="NPC05_Chef", ref="Restaurant chef in studio T-pose-6.png", role="chef",
        body=dict(macros=dict(gender=0.0, age=0.6, muscle=0.5, weight=0.5, proportions=0.6, african=0.9, caucasian=0.1),
                  targets={"nose/nose-flaring-incr": 0.2}, skin="young_african_female", tint=(0.88, 0.82, 0.8), eyes="darkbrown",
                  brows="eyebrow006", height=1.68),
        hair=dict(style="bun_high", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(beard="none", age=0.35, undereye=0.25, lips_mul=(0.88, 0.78, 0.78), lips_desat=0.2),
        outfit=[
            ("trousers", dict(color=(22, 22, 24), kind="slacks", crease=False, width=0.066)),
            ("top", dict(name="ChefCoat", color=(246, 246, 244), sleeve="long", neck="mock", hem="long", weave="twill", heather=0.015,
                         placket="double", buttons_rgb=(30, 30, 32), cuffs=True, fit=0.004, rough=0.8)),
            ("apron", dict(color=(40, 40, 42), kind="waist", length="knee", pocket=False)),
            ("shoes", dict(kind="dress", color=(16, 16, 17))),
        ]),
    "jogger_man": dict(
        name="NPC06_VancouverJogger", ref="T-Pose Vancouver Jogger Reference-1.png", role="jogger",
        body=dict(macros=dict(gender=1.0, age=0.5, muscle=0.7, weight=0.4, proportions=0.65, caucasian=0.45, african=0.25, asian=0.3),
                  targets={"stomach/stomach-pregnant-decr": 0.4}, skin="young_caucasian_male", tint=(0.86, 0.74, 0.62), gamma=1.1,
                  eyes="darkbrown", brows="eyebrow008", height=1.78),
        hair=dict(style="crop", **BLACK_HAIR), brows=dict(paint=0.2, **BLACK_HAIR),
        face=dict(beard="stubble", age=0.2, undereye=0.2, lips_mul=(0.9, 0.8, 0.78), lips_desat=0.3),
        outfit=[
            ("top", dict(name="RunTee", color=(30, 90, 210), sleeve="short", neck="crew", hem="untucked", weave="knit", heather=0.04,
                         sheen=0.45, rough=0.7)),
            ("trousers", dict(color=(24, 24, 26), kind="running_shorts", weave="twill", rough=0.9)),
            ("shoes", dict(kind="runner", color=(110, 112, 116), sole=(230, 230, 232), sock=(235, 235, 235), sock_height=0.1)),
        ]),
}


# ------------------------------------------------------------------ compact helpers for the rest
def body(g, age, h, skin, eth, muscle=0.5, weight=0.5, prop=0.6, tint=None, gamma=1.0, eyes="darkbrown", brows=None, targets=None):
    m = dict(gender=g, age=age, muscle=muscle, weight=weight, proportions=prop)
    m.update(eth)
    d = dict(macros=m, skin=skin, eyes=eyes, height=h, targets=targets or {})
    if tint: d.update(tint=tint, gamma=gamma)
    if brows: d["brows"] = brows
    return d


def back_text(img, dz=0.05, w=0.3, h=0.075):
    return dict(side="back", anchor="chest", centre=(0.0, dz), size=(w, h), image=img)


def chest(img, x=0.085, dz=0.1, w=0.07, h=0.07, round_=False):
    return dict(side="front", anchor="chest", centre=(x, dz), size=(w, h), image=img, round_=round_)


def arm(img, side="arm_l", dz=-0.07, s=0.075):
    return dict(side=side, anchor="shoulder", centre=(0.0, dz), size=(s, s), image=img, round_=True)


ASIAN = dict(asian=0.92, caucasian=0.08)
AFRICAN = dict(african=0.92, caucasian=0.08)
EURO = dict(caucasian=0.95, asian=0.03, african=0.02)
SOUTH_ASIAN = dict(caucasian=0.55, african=0.15, asian=0.3)
LATIN = dict(caucasian=0.7, african=0.1, asian=0.2)
MIDEAST = dict(caucasian=0.82, african=0.03, asian=0.15)

PEOPLE.update({
    "courier_woman": dict(
        name="NPC07_BikeCourier", ref="Athletic Vancouver courier in T-pose-6.png", role="bike_courier",
        body=body(0.0, 0.52, 1.7, "young_african_female", AFRICAN, muscle=0.66, weight=0.38, prop=0.7, tint=(0.9, 0.84, 0.82)),
        hair=dict(style="bun_high", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(age=0.2, undereye=0.2, lips_mul=(0.88, 0.78, 0.78)),
        outfit=[("top", dict(name="Jersey", color=(18, 160, 190), sleeve="long", neck="mock", hem="untucked", zip=True, weave="knit",
                             sheen=0.45, rough=0.65, cuffs=True)),
                ("trousers", dict(color=(28, 28, 30), kind="leggings", weave="knit", rough=0.7)),
                ("shoes", dict(kind="trainer", color=(26, 26, 28), sole=(40, 40, 42), sock=(30, 30, 32), sock_height=0.09))]),
    "jogger_woman": dict(
        name="NPC08_AuburnJogger", ref="Auburn-haired jogger in T-pose-3.png", role="jogger",
        body=body(0.0, 0.54, 1.66, "young_caucasian_female", EURO, muscle=0.6, weight=0.4, prop=0.68, tint=(1.0, 0.95, 0.92)),
        hair=dict(style="ponytail", **AUBURN), brows=dict(dark=(60, 30, 18), light=(130, 80, 50)),
        face=dict(age=0.2, undereye=0.2, lips_mul=(0.95, 0.8, 0.8)),
        outfit=[("top", dict(name="RunTee", color=(232, 110, 100), sleeve="short", neck="crew", hem="untucked", weave="knit", sheen=0.4, rough=0.7)),
                ("trousers", dict(color=(56, 56, 60), kind="leggings", weave="knit", rough=0.75)),
                ("shoes", dict(kind="sneaker", color=(238, 238, 240), sole=(245, 245, 245), sock=(240, 240, 240), sock_height=0.09))]),
    "baker": dict(
        name="NPC09_Baker", ref="Bakery worker in neutral T-pose-9.png", role="baker",
        body=body(1.0, 0.8, 1.75, "middleage_caucasian_male", EURO, muscle=0.5, weight=0.6, tint=(1.0, 0.94, 0.9)),
        hair=dict(style="classic", **GREY), brows=dict(dark=(80, 78, 76), light=(170, 168, 164)),
        face=dict(beard="stubble", beard_rgb=(120, 118, 114), age=0.75, undereye=0.45),
        outfit=[("top", dict(name="Shirt", color=(236, 228, 210), sleeve="elbow", neck="collar", hem="tucked", weave="twill", placket="shirt",
                             heather=0.03, rough=0.8)),
                ("trousers", dict(color=(60, 60, 62), kind="work", width=0.07)),
                ("apron", dict(color=(70, 100, 150), kind="bib", length="knee", strap_rgb=(60, 88, 135))),
                ("shoes", dict(kind="brown_dress", color=(92, 60, 36)))]),
    "barista": dict(
        name="NPC10_Barista", ref="Café Barista in T-Pose-5.png", role="barista",
        body=body(0.0, 0.56, 1.64, "young_caucasian_female", LATIN, weight=0.45, tint=(0.95, 0.85, 0.75), gamma=1.05),
        hair=dict(style="bun_high", **DARK_BROWN), brows=dict(**DARK_BROWN),
        face=dict(age=0.25, undereye=0.25, lips_mul=(0.92, 0.78, 0.76)),
        outfit=[("top", dict(name="Tee", color=(140, 152, 128), sleeve="short", neck="crew", hem="tucked", weave="knit")),
                ("trousers", dict(color=(28, 28, 30), kind="jeans", width=0.06)),
                ("apron", dict(color=(140, 92, 50), kind="bib", length="knee", strap_rgb=(110, 72, 40))),
                ("shoes", dict(kind="trainer", color=(24, 24, 26), sole=(230, 230, 230), sock_height=0.09))]),
    "student_woman": dict(
        name="NPC11_CollegeStudent", ref="College student in neutral T-pose-5.png", role="student",
        body=body(0.0, 0.46, 1.62, "young_caucasian_female", SOUTH_ASIAN, weight=0.42, tint=(0.88, 0.76, 0.64), gamma=1.1),
        hair=dict(style="bun_high", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(age=0.15, undereye=0.3, lips_mul=(0.9, 0.78, 0.76)),
        outfit=[("top", dict(name="Sweater", color=(232, 178, 40), sleeve="long", neck="crew", hem="untucked", weave="knit", heather=0.08,
                             cuffs=True, hem_rib=True, fit=0.002, rough=0.92)),
                ("trousers", dict(color=(40, 56, 92), kind="jeans", width=0.062)),
                ("shoes", dict(kind="trainer", color=(24, 24, 26), sole=(240, 240, 240), sock_height=0.09))]),
    "dog_walker": dict(
        name="NPC12_DogWalker", ref="Dog walker T-pose reference-2.png", role="dog_walker",
        body=body(0.0, 0.7, 1.66, "middleage_caucasian_female", EURO, weight=0.5, tint=(1.0, 0.93, 0.88)),
        hair=dict(style="ponytail", **BROWN), brows=dict(**BROWN),
        face=dict(age=0.5, undereye=0.35),
        outfit=[("top", dict(name="Tee", color=(230, 226, 214), sleeve="short", neck="crew", hem="tucked", weave="knit")),
                ("trousers", dict(color=(46, 70, 112), kind="jeans", width=0.066)),
                ("jacket", dict(name="Fleece", color=(36, 70, 52), zip=True, collar="stand", weave="knit", heather=0.1, rough=0.95,
                                pockets="welt", hem_rib=False)),
                ("shoes", dict(kind="boot", color=(96, 68, 44)))]),
    "doner_worker": dict(
        name="NPC13_DonerWorker", ref="Doner Shop Worker in T-Pose-4.png", role="doner",
        body=body(1.0, 0.58, 1.77, "young_caucasian_male", MIDEAST, muscle=0.55, weight=0.52, tint=(0.94, 0.84, 0.74), gamma=1.1,
                  brows="eyebrow009"),
        hair=dict(style="fade", **BLACK_HAIR), brows=dict(paint=0.3, **BLACK_HAIR),
        face=dict(beard="short", beard_rgb=(14, 11, 10), age=0.3, undereye=0.45),
        outfit=[("top", dict(name="Tee", color=(244, 244, 242), sleeve="short", neck="crew", hem="tucked", weave="knit", heather=0.02)),
                ("trousers", dict(color=(26, 26, 28), kind="work", width=0.068)),
                ("apron", dict(color=(26, 80, 52), kind="bib", length="knee")),
                ("shoes", dict(kind="dress", color=(18, 18, 19)))]),
    "student_man": dict(
        name="NPC14_EastAsianStudent", ref="East Asian College Student T-Pose Reference-9.png", role="student",
        body=body(1.0, 0.46, 1.74, "young_asian_male", ASIAN, weight=0.42, tint=(1.0, 0.94, 0.88)),
        hair=dict(style="classic", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(age=0.12, undereye=0.25),
        outfit=[("top", dict(name="Sweater", color=(118, 30, 40), sleeve="long", neck="crew", hem="untucked", weave="knit", heather=0.07,
                             cuffs=True, hem_rib=True, fit=0.002, rough=0.92)),
                ("trousers", dict(color=(196, 178, 140), kind="chinos", width=0.066)),
                ("shoes", dict(kind="sneaker", color=(240, 240, 240), sock_height=0.09))]),
    "elderly_man": dict(
        name="NPC15_ElderlyMan", ref="Elderly man in sage sweater T-pose-8.png", role="retiree",
        body=body(1.0, 0.88, 1.72, "old_caucasian_male", EURO, muscle=0.35, weight=0.5, tint=(1.0, 0.95, 0.92)),
        hair=dict(style="classic", **GREY), brows=dict(dark=(150, 148, 144), light=(220, 218, 214)),
        face=dict(age=1.0, undereye=0.6, lips_desat=0.4),
        outfit=[("top", dict(name="Shirt", color=(236, 234, 226), sleeve="long", neck="collar", hem="tucked", weave="twill", placket="shirt")),
                ("trousers", dict(color=(110, 86, 60), kind="slacks", width=0.07)),
                ("top", dict(name="Sweater", color=(128, 140, 108), sleeve="long", neck="crew", hem="untucked", weave="knit", heather=0.08,
                             cuffs=True, hem_rib=True, fit=0.003, offset=0.013, rough=0.92)),
                ("shoes", dict(kind="brown_dress", color=(62, 42, 28)))]),
    "elderly_woman": dict(
        name="NPC16_ElderlyWoman", ref="Elderly woman in neutral T-pose-10.png", role="retiree",
        body=body(0.0, 0.9, 1.56, "old_asian_female", ASIAN, muscle=0.3, weight=0.48, tint=(1.0, 0.95, 0.9)),
        hair=dict(style="curly_short", **GREY), brows=dict(dark=(110, 108, 106), light=(190, 188, 184)),
        face=dict(age=1.0, undereye=0.55, lips_desat=0.4),
        outfit=[("top", dict(name="Blouse", color=(240, 238, 234), sleeve="long", neck="crew", hem="tucked", weave="knit")),
                ("trousers", dict(color=(36, 40, 60), kind="slacks", width=0.066, crease=False)),
                ("jacket", dict(name="Cardigan", color=(168, 148, 186), open=True, opening=(0.07, 0.045, 0.07), weave="knit", heather=0.09,
                                rough=0.92, pockets=None, buttons=0, cuffs=True)),
                ("shoes", dict(kind="sneaker", color=(150, 150, 154), sole=(230, 230, 230), sock_height=0.09))]),
    "delivery_driver": dict(
        name="NPC17_DeliveryDriver", ref="Female Delivery Driver T-Pose-9.png", role="delivery_driver",
        body=body(0.0, 0.7, 1.68, "middleage_caucasian_female", EURO, muscle=0.5, weight=0.5, tint=(1.0, 0.93, 0.88)),
        hair=dict(style="mpfb:bob02", **BLONDE), brows=dict(dark=(90, 70, 44), light=(170, 140, 100)),
        face=dict(age=0.5, undereye=0.35),
        outfit=[("top", dict(name="Polo", color=(26, 34, 62), sleeve="short", neck="collar", hem="tucked", weave="knit", placket="polo",
                             decals=[chest("express_logo", x=0.085, dz=0.1, w=0.1, h=0.025)])),
                ("trousers", dict(color=(56, 56, 58), kind="cargo", cargo=True, width=0.068)),
                ("belt", dict(color=(20, 20, 20))),
                ("shoes", dict(kind="boot", color=(22, 22, 24)))]),
    "road_cyclist": dict(
        name="NPC18_DeliveryCyclist", ref="Front-view cyclist in delivery gear-5.png", role="bike_courier",
        body=body(1.0, 0.52, 1.78, "young_caucasian_male", EURO, muscle=0.62, weight=0.38, prop=0.7, tint=(1.0, 0.94, 0.88)),
        hair=dict(style="classic", **BROWN), brows=dict(**BROWN),
        face=dict(beard="stubble", beard_rgb=(60, 44, 30), age=0.2, undereye=0.25),
        outfit=[("top", dict(name="Jersey", color=(26, 34, 70), sleeve="short", neck="mock", hem="untucked", zip=True, weave="knit", sheen=0.45, rough=0.65)),
                ("trousers", dict(color=(20, 20, 22), kind="bike_shorts", weave="knit", rough=0.65)),
                ("shoes", dict(kind="cycling", color=(18, 18, 20)))]),
    "office_man": dict(
        name="NPC19_OfficeWorkerMan", ref="Male Office Worker in Neutral T-Pose-2.png", role="office",
        body=body(1.0, 0.58, 1.8, "young_african_male", AFRICAN, weight=0.45, tint=(0.88, 0.82, 0.8)),
        hair=dict(style="crop", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(age=0.3, undereye=0.3),
        outfit=[("top", dict(name="Shirt", color=(186, 210, 236), sleeve="long", neck="collar", hem="tucked", weave="twill", placket="shirt", cuffs=True)),
                ("trousers", dict(color=(78, 80, 86), kind="slacks", width=0.066)),
                ("belt", dict(color=(16, 16, 16))),
                ("shoes", dict(kind="dress", color=(14, 14, 15)))]),
    "moto_courier": dict(
        name="NPC20_MotoCourier", ref="Motorcycle courier T-pose reference-8.png", role="moto_courier",
        body=body(1.0, 0.56, 1.76, "young_caucasian_male", LATIN, muscle=0.55, weight=0.5, tint=(0.95, 0.86, 0.76), gamma=1.05),
        hair=dict(style="crop", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(beard="stubble", age=0.3, undereye=0.3),
        outfit=[("trousers", dict(color=(22, 22, 24), kind="cargo", cargo=True, width=0.074, weave="twill")),
                ("jacket", dict(name="MotoJacket", color=(120, 24, 34), zip=True, collar="stand", weave="twill", rough=0.6, sheen=0.1,
                                panels=True, padded=0.012, pockets="welt", length="waist")),
                ("shoes", dict(kind="boot", color=(20, 20, 22)))]),
    "police_woman": dict(
        name="NPC21_PoliceOfficer", ref="Municipal police officer in T-pose-2.png", role="police",
        body=body(0.0, 0.6, 1.7, "young_caucasian_female", LATIN, muscle=0.55, weight=0.45, tint=(0.97, 0.9, 0.82)),
        hair=dict(style="bun_low", **DARK_BROWN), brows=dict(**DARK_BROWN),
        face=dict(age=0.3, undereye=0.3),
        outfit=[("top", dict(name="Uniform", color=(24, 30, 52), sleeve="short", neck="collar", hem="tucked", weave="twill", placket="shirt",
                             pocket=True, epaulettes=True, buttons_rgb=(30, 34, 50),
                             decals=[arm("police_patch", "arm_l"), arm("police_patch", "arm_r"), chest("police_badge", x=0.085, dz=0.12, w=0.05, h=0.055),
                                     back_text("police_back")])),
                ("trousers", dict(color=(24, 30, 52), kind="cargo", cargo=True, width=0.068)),
                ("belt", dict(color=(16, 16, 17), duty=True)),
                ("shoes", dict(kind="boot", color=(14, 14, 15)))]),
    "paramedic": dict(
        name="NPC22_Paramedic", ref="Paramedic in studio T-pose-1.png", role="paramedic",
        body=body(1.0, 0.6, 1.8, "young_african_male", AFRICAN, muscle=0.6, weight=0.5, tint=(0.88, 0.82, 0.8)),
        hair=dict(style="buzz", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(beard="stubble", age=0.3, undereye=0.3),
        outfit=[("top", dict(name="Uniform", color=(26, 34, 64), sleeve="short", neck="collar", hem="tucked", weave="twill", placket="shirt",
                             pocket=True, epaulettes=True, decals=[chest("star_of_life", x=0.085, dz=0.1, w=0.06, h=0.06), back_text("paramedic_back")])),
                ("trousers", dict(color=(26, 34, 64), kind="cargo", cargo=True, width=0.07,
                                  stripes=((200, 202, 205), (0.32, 0.36), 0.025))),
                ("belt", dict(color=(16, 16, 17))),
                ("shoes", dict(kind="boot", color=(14, 14, 15)))]),
    "taxi_driver": dict(
        name="NPC23_TaxiDriver", ref="Realistic Taxi Driver T-Pose Reference-10.png", role="taxi_driver",
        body=body(1.0, 0.8, 1.72, "middleage_caucasian_male", SOUTH_ASIAN, weight=0.62, tint=(0.86, 0.74, 0.62), gamma=1.1),
        hair=dict(style="classic", **SALT_PEPPER), brows=dict(dark=(40, 38, 36), light=(120, 116, 110)),
        face=dict(beard="moustache", beard_rgb=(60, 58, 56), age=0.7, undereye=0.5),
        outfit=[("top", dict(name="Shirt", color=(170, 200, 236), sleeve="short", neck="collar", hem="tucked", weave="twill", placket="shirt", pocket=True)),
                ("trousers", dict(color=(30, 36, 62), kind="slacks", width=0.07)),
                ("belt", dict(color=(20, 18, 16))),
                ("shoes", dict(kind="brown_dress", color=(80, 54, 34)))]),
    "office_woman": dict(
        name="NPC24_OfficeWorkerWoman", ref="Realistic female office worker T-pose-6.png", role="office",
        body=body(0.0, 0.58, 1.66, "young_caucasian_female", LATIN, weight=0.42, tint=(0.98, 0.9, 0.84)),
        hair=dict(style="bun_low", **DARK_BROWN), brows=dict(**DARK_BROWN),
        face=dict(age=0.25, undereye=0.25, lips_mul=(0.9, 0.74, 0.74), lips_desat=0.1),
        outfit=[("top", dict(name="Blouse", color=(240, 230, 214), sleeve="long", neck="vneck", hem="tucked", weave="twill", heather=0.02, sheen=0.5)),
                ("trousers", dict(color=(28, 34, 62), kind="slacks", width=0.06)),
                ("jacket", dict(name="Blazer", color=(28, 34, 62), open=True, opening=(0.065, 0.045, 0.08), lapels=True, pockets="flap", buttons=1)),
                ("shoes", dict(kind="pump", color=(12, 12, 13)))]),
    "middle_aged_man": dict(
        name="NPC25_MiddleAgedMan", ref="Realistic middle-aged man, neutral T-pose-4.png", role="commuter",
        body=body(1.0, 0.74, 1.78, "middleage_caucasian_male", EURO, weight=0.55, tint=(1.0, 0.93, 0.88)),
        hair=dict(style="classic", **BROWN), brows=dict(**BROWN),
        face=dict(beard="stubble", beard_rgb=(70, 54, 40), age=0.55, undereye=0.45),
        outfit=[("top", dict(name="Tee", color=(230, 228, 222), sleeve="short", neck="crew", hem="tucked", weave="knit")),
                ("trousers", dict(color=(190, 168, 126), kind="chinos", width=0.068)),
                ("jacket", dict(name="ZipJacket", color=(28, 38, 64), zip=True, collar="stand", weave="twill", rough=0.7, pockets="welt",
                                hem_rib=True, cuffs=True, length="waist")),
                ("shoes", dict(kind="brown_dress", color=(80, 54, 34)))]),
    "urban_cyclist": dict(
        name="NPC26_UrbanCyclist", ref="Realistic urban cyclist T-pose reference.png", role="cyclist",
        body=body(1.0, 0.52, 1.76, "young_caucasian_male", LATIN, muscle=0.66, weight=0.38, prop=0.7, tint=(0.95, 0.84, 0.74), gamma=1.05),
        hair=dict(style="classic", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(age=0.2, undereye=0.25),
        outfit=[("top", dict(name="Jersey", color=(18, 110, 110), sleeve="short", neck="mock", hem="untucked", zip=True, weave="knit", sheen=0.45, rough=0.65)),
                ("trousers", dict(color=(44, 44, 48), kind="bike_shorts", weave="knit", rough=0.65)),
                ("shoes", dict(kind="trainer", color=(100, 100, 104), sole=(60, 60, 62), sock=(150, 150, 154), sock_height=0.13))]),
    "security_guard": dict(
        name="NPC27_SecurityGuard", ref="Security Guard T-Pose Reference-3.png", role="security",
        body=body(1.0, 0.8, 1.74, "middleage_caucasian_male", LATIN, muscle=0.5, weight=0.62, tint=(0.94, 0.84, 0.74), gamma=1.05),
        hair=dict(style="crop", **SALT_PEPPER), brows=dict(dark=(40, 38, 36), light=(110, 106, 100)),
        face=dict(beard="moustache", beard_rgb=(70, 66, 62), age=0.7, undereye=0.5),
        outfit=[("top", dict(name="Uniform", color=(196, 204, 214), sleeve="short", neck="collar", hem="tucked", weave="twill", placket="shirt",
                             pocket=True, epaulettes=True, decals=[arm("security_patch", "arm_l"), arm("security_patch", "arm_r"), back_text("security_back")])),
                ("trousers", dict(color=(26, 32, 54), kind="slacks", width=0.07)),
                ("belt", dict(color=(16, 16, 17), duty=True)),
                ("shoes", dict(kind="boot", color=(14, 14, 15)))]),
    "cashier": dict(
        name="NPC28_GroceryCashier", ref="Studio grocery cashier in T-pose-8.png", role="cashier",
        body=body(0.0, 0.6, 1.6, "young_asian_female", ASIAN, weight=0.45, tint=(1.0, 0.94, 0.88)),
        hair=dict(style="mpfb:bob01", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(age=0.3, undereye=0.3),
        outfit=[("top", dict(name="Polo", color=(24, 74, 50), sleeve="short", neck="collar", hem="tucked", weave="knit", placket="polo",
                             decals=[chest("market_logo", x=0.085, dz=0.1, w=0.09, h=0.022)])),
                ("trousers", dict(color=(196, 180, 146), kind="chinos", width=0.064)),
                ("belt", dict(color=(16, 16, 16))),
                ("shoes", dict(kind="dress", color=(16, 16, 17)))]),
    "tourist": dict(
        name="NPC29_Tourist", ref="Tourist woman in studio T-pose-7.png", role="tourist",
        body=body(0.0, 0.66, 1.6, "middleage_asian_female", ASIAN, weight=0.45, tint=(1.0, 0.94, 0.88)),
        hair=dict(style="mpfb:bob02", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(age=0.45, undereye=0.35),
        outfit=[("top", dict(name="Shirt", color=(214, 204, 180), sleeve="three_quarter", neck="collar", hem="untucked", weave="twill",
                             placket="shirt", pocket=True)),
                ("trousers", dict(color=(102, 108, 76), kind="cargo", cargo=True, width=0.068)),
                ("shoes", dict(kind="trainer", color=(120, 116, 110), sole=(60, 60, 60), sock_height=0.1))]),
    "server": dict(
        name="NPC30_RestaurantServer", ref="Vancouver Restaurant Server in T-Pose-3.png", role="server",
        body=body(1.0, 0.5, 1.75, "young_asian_male", ASIAN, weight=0.4, tint=(1.0, 0.95, 0.9)),
        hair=dict(style="classic", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(age=0.15, undereye=0.2),
        outfit=[("top", dict(name="Shirt", color=(246, 246, 244), sleeve="long", neck="collar", hem="tucked", weave="twill", placket="shirt", cuffs=True)),
                ("trousers", dict(color=(16, 16, 17), kind="slacks", width=0.064)),
                ("vest", dict(name="Waistcoat", color=(24, 24, 26), kind="waistcoat")),
                ("apron", dict(color=(18, 18, 19), kind="waist", length="knee", pocket=False)),
                ("shoes", dict(kind="dress", color=(10, 10, 11)))]),
    "bus_driver": dict(
        name="NPC31_BusDriver", ref="Vancouver bus driver studio reference-2.png", role="bus_driver",
        body=body(1.0, 0.8, 1.74, "middleage_caucasian_male", SOUTH_ASIAN, weight=0.62, tint=(0.86, 0.74, 0.62), gamma=1.1),
        hair=dict(style="classic", **SALT_PEPPER), brows=dict(dark=(40, 38, 36), light=(120, 116, 110)),
        face=dict(beard="moustache", beard_rgb=(50, 48, 46), age=0.7, undereye=0.5),
        outfit=[("top", dict(name="Uniform", color=(160, 196, 232), sleeve="short", neck="collar", hem="tucked", weave="twill", placket="shirt",
                             pocket=True, epaulettes=True, decals=[chest("transit_chest", x=-0.085, dz=0.11, w=0.07, h=0.018)])),
                ("trousers", dict(color=(26, 32, 58), kind="slacks", width=0.07)),
                ("belt", dict(color=(16, 16, 16))),
                ("shoes", dict(kind="dress", color=(14, 14, 15)))]),
    "parent": dict(
        name="NPC32_Parent", ref="Vancouver parent character in T-pose-4.png", role="parent",
        body=body(1.0, 0.64, 1.8, "young_caucasian_male", EURO, weight=0.5, tint=(1.0, 0.93, 0.88)),
        hair=dict(style="classic", **BROWN), brows=dict(**BROWN),
        face=dict(beard="stubble", beard_rgb=(80, 60, 40), age=0.35, undereye=0.4),
        outfit=[("top", dict(name="Sweater", color=(74, 104, 112), sleeve="long", neck="crew", hem="untucked", weave="knit", heather=0.08,
                             cuffs=True, hem_rib=True, fit=0.002, rough=0.92)),
                ("trousers", dict(color=(186, 156, 112), kind="chinos", width=0.068)),
                ("shoes", dict(kind="sneaker", color=(120, 122, 126), sole=(235, 235, 235), sock_height=0.09))]),
    "pizza_worker": dict(
        name="NPC33_PizzaWorker", ref="Vancouver pizza shop worker T-pose-1.png", role="pizza",
        body=body(0.0, 0.52, 1.64, "young_caucasian_female", LATIN, weight=0.45, tint=(0.96, 0.86, 0.76), gamma=1.05),
        hair=dict(style="ponytail", **DARK_BROWN), brows=dict(**DARK_BROWN),
        face=dict(age=0.2, undereye=0.25),
        outfit=[("top", dict(name="Tee", color=(112, 26, 34), sleeve="short", neck="crew", hem="tucked", weave="knit")),
                ("trousers", dict(color=(20, 20, 22), kind="slacks", width=0.064, crease=False)),
                ("apron", dict(color=(30, 30, 32), kind="waist", length="thigh", pocket=True)),
                ("shoes", dict(kind="dress", color=(14, 14, 15)))]),
    "street_cleaner": dict(
        name="NPC34_StreetCleaner", ref="Vancouver street cleaner in T-pose-10.png", role="street_cleaner",
        body=body(0.0, 0.7, 1.66, "middleage_caucasian_female", EURO, muscle=0.5, weight=0.5, tint=(1.0, 0.93, 0.88)),
        hair=dict(style="ponytail", **BROWN), brows=dict(**BROWN),
        face=dict(age=0.5, undereye=0.4),
        outfit=[("top", dict(name="Shirt", color=(26, 52, 40), sleeve="long", neck="collar", hem="tucked", weave="twill", placket="shirt", cuffs=True)),
                ("trousers", dict(color=(26, 34, 56), kind="cargo", cargo=True, width=0.07)),
                ("vest", dict(color=(200, 240, 20), kind="hivis", stripes=(190, 192, 194), decals=[back_text("crew_back", dz=0.02)])),
                ("shoes", dict(kind="boot", color=(14, 14, 15)))]),
    "warehouse_worker": dict(
        name="NPC35_WarehouseWorker", ref="Warehouse worker in safety vest-5.png", role="warehouse",
        body=body(1.0, 0.54, 1.8, "young_caucasian_male", EURO, muscle=0.62, weight=0.52, tint=(1.0, 0.92, 0.86)),
        hair=dict(style="crop", **AUBURN), brows=dict(dark=(70, 34, 16), light=(150, 90, 50)),
        face=dict(beard="short", beard_rgb=(90, 44, 20), age=0.3, undereye=0.35),
        outfit=[("top", dict(name="Tee", color=(30, 40, 70), sleeve="short", neck="crew", hem="untucked", weave="knit")),
                ("trousers", dict(color=(70, 70, 72), kind="cargo", cargo=True, width=0.074)),
                ("vest", dict(color=(210, 245, 30), kind="hivis", stripes=(190, 192, 194))),
                ("shoes", dict(kind="boot", color=(96, 64, 38)))]),
    "young_man": dict(
        name="NPC36_YoungMan", ref="Young male pedestrian in T-pose-3.png", role="pedestrian",
        body=body(1.0, 0.48, 1.76, "young_caucasian_male", SOUTH_ASIAN, weight=0.45, tint=(0.86, 0.74, 0.62), gamma=1.1),
        hair=dict(style="fade", **BLACK_HAIR), brows=dict(**BLACK_HAIR),
        face=dict(beard="stubble", age=0.15, undereye=0.3),
        outfit=[("top", dict(name="Tee", color=(92, 104, 64), sleeve="short", neck="crew", hem="untucked", weave="knit", heather=0.08)),
                ("trousers", dict(color=(40, 60, 100), kind="jeans", width=0.064)),
                ("shoes", dict(kind="sneaker", color=(130, 132, 136), sole=(240, 240, 240), sock_height=0.09))]),
    "young_woman": dict(
        name="NPC37_YoungWoman", ref="Young woman in neutral T-pose-7.png", role="pedestrian",
        body=body(0.0, 0.5, 1.68, "young_caucasian_female", EURO, weight=0.42, tint=(1.0, 0.94, 0.9)),
        hair=dict(style="mpfb:long01", **BROWN), brows=dict(**BROWN),
        face=dict(age=0.15, undereye=0.2, lips_mul=(0.94, 0.8, 0.8)),
        outfit=[("top", dict(name="LongTee", color=(190, 98, 70), sleeve="long", neck="crew", hem="untucked", weave="knit", heather=0.06, cuffs=True)),
                ("trousers", dict(color=(110, 140, 180), kind="jeans", width=0.062)),
                ("shoes", dict(kind="sneaker", color=(244, 244, 244), sock_height=0.09))]),
})
