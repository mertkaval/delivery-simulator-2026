# Asset licences and attributions

Every third-party asset in the game, where it came from, its licence and what it is used for.
Sketchfab metadata (title, author, licence, URL) is read from each downloaded GLB's `asset.extras`
by `tools/asset_ledger.py` (see "Keeping this file current"). Last checked 2026-10-23.

## What the licences require

| Licence | Commercial use | Obligations |
|---|---|---|
| **CC BY 4.0** (49 Sketchfab models) | Yes | Credit the author, link the model and the licence, say if it was changed (all were converted / re-textured / optimised). In-game credits + this file satisfy it. |
| **Sketchfab Standard** (2 models) | Yes, inside the game | **No redistribution of the asset itself.** The game's GitHub repository is public, so the converted files (`assets/sketchup/props/plants/`, `assets/interiors/restaurant/food_bar_counter*`) and the raw downloads are currently downloadable by anyone. Make the repository private, or replace these two models. |
| **CC0 1.0** (Quaternius, MakeHuman / MPFB assets) | Yes | None (credit appreciated). |
| Own / AI-generated work (owner's statement) | Yes | None. |

## Sketchfab models

| Model | Author | Licence | Used for |
|---|---|---|---|
| [Ace '11 - Low Poly model](https://sketchfab.com/3d-models/ace-11-low-poly-model-055ff8a21b8d4d279debca089e2fafcd) | [Daniel Zhabotinsky](https://sketchfab.com/DanielZhabotinsky) | CC BY 4.0 | civil fleet vehicle (tools/prepare_civil_vehicles.py) |
| [Baked goods](https://sketchfab.com/3d-models/baked-goods-d1ae09e3cb8343bc8790b15928452906) | [Rigsters](https://sketchfab.com/rigsters) | CC BY 4.0 | bakery interior dressing (prepare_interiors.py) |
| [Black Walnut Tree](https://sketchfab.com/3d-models/black-walnut-tree-c504c5ba66f54d3ea30c0e9bb57a8ab5) | [gwangju_inmunstory](https://sketchfab.com/gwangju_inmunstory) | CC BY 4.0 | landscape trees (prepare_landscape.py) |
| [Busto de Ataturk](https://sketchfab.com/3d-models/busto-de-ataturk-55ee465fd1ea4b788c76105a425f0802) | [Artur Coelho](https://sketchfab.com/coelhoelectrico) | CC BY 4.0 | monument (prepare_monuments.py) |
| [car for games unity](https://sketchfab.com/3d-models/car-for-games-unity-4d9bbde680fe41349d7ad2b4672a720b) | [Unity](https://sketchfab.com/shahabahmed) | CC BY 4.0 | traffic car (prepare_sketchup_assets.py) |
| [Casual Male 3D Character – T-Pose](https://sketchfab.com/3d-models/casual-male-3d-character-t-pose-61c5547e918f4e9797b59184a4062858) | [sthaarpit](https://sketchfab.com/sthaarpit) | CC BY 4.0 | legacy pedestrian (fallback only) |
| [Character with Clothes](https://sketchfab.com/3d-models/character-with-clothes-32751cc4a17d4c31a3809f16637d2150) | [sapenton8821](https://sketchfab.com/sapenton8821) | CC BY 4.0 | legacy pedestrian `clothed_man` (fallback only) |
| [chevrolet camero car](https://sketchfab.com/3d-models/chevrolet-camero-car-8afcef6b8d4e4d729f70963ac33e8a79) | [shindedhirendra780](https://sketchfab.com/shindedhirendra780) | CC BY 4.0 | traffic car (prepare_sketchup_assets.py) |
| [Decor Shelf](https://sketchfab.com/3d-models/decor-shelf-c95459b91940496b8caf443a6ec788b7) | [fath1234](https://sketchfab.com/fath1234) | CC BY 4.0 | interior dressing (prepare_interiors.py) |
| [Duplex House](https://sketchfab.com/3d-models/duplex-house-9bce4b9490ce43b18900e2e99e8ebe66) | [jimbogies](https://sketchfab.com/jimbogies) | CC BY 4.0 | neighbourhood house type (prepare_new_houses.py) |
| [Eric Rigged 001 - Rigged 3D Business Man](https://sketchfab.com/3d-models/eric-rigged-001-rigged-3d-business-man-a46bc9f67aaa415bb4f3241eef900e7f) | [Renderpeople](https://sketchfab.com/renderpeople) | CC BY 4.0 | legacy pedestrian (fallback only) |
| [Female Character With Casual Clothing](https://sketchfab.com/3d-models/female-character-with-casual-clothing-622a56e7f30446b694f59245d3b01bcc) | [mahensanketh](https://sketchfab.com/mahensanketh) | CC BY 4.0 | legacy pedestrian (fallback only) |
| [Flower Model](https://sketchfab.com/3d-models/flower-model-1f6363f709c1465e89c38c9d5b2453c4) | [Truong Arch](https://sketchfab.com/kiemtruongkts) | CC BY 4.0 | landscape planting (prepare_landscape.py) |
| [Food bar](https://sketchfab.com/3d-models/food-bar-185f1a75e0e8452ea7c013730e973cd0) | [Katydid](https://sketchfab.com/Katydid.) | **Sketchfab Standard** | restaurant food-bar counter (prepare_interiors.py) |
| [Fountain with three putts, Brno Lužánky](https://sketchfab.com/3d-models/fountain-with-three-putts-brno-luzanky-430b9e5354484860b8b41505e9b63298) | [3dhdscan](https://sketchfab.com/3dhdscan) | CC BY 4.0 | park fountain (prepare_monuments.py) |
| [Generic civil service vehicles pack](https://sketchfab.com/3d-models/generic-civil-service-vehicles-pack-8ff2a13f30914932a70c7950cfa58465) | [Comrade1280](https://sketchfab.com/comrade1280) | CC BY 4.0 | civil service fleet (prepare_civil_vehicles.py) |
| [Generic passenger car pack](https://sketchfab.com/3d-models/generic-passenger-car-pack-20f9af9b8a404d5cb022ac6fe87f21f5) | [Comrade1280](https://sketchfab.com/comrade1280) | CC BY 4.0 | traffic cars (prepare_sketchup_assets.py) |
| [Geranium Flowering Plants Free](https://sketchfab.com/3d-models/geranium-flowering-plants-free-01fa24aac87f4b62bd51c36c55c297d6) | [Nicholas-3D](https://sketchfab.com/Nicholas01) | CC BY 4.0 | planters / yard planting (prepare_prop_packs.py, prepare_yard_planting.py) |
| [Goat Simulator Mobile NPC 2 Tracksuit](https://sketchfab.com/3d-models/goat-simulator-mobile-npc-2-tracksuit-c812449137b645e089643a60fdefde73) | [belugadachicken](https://sketchfab.com/belugadachicken) | CC BY 4.0 | legacy pedestrian `tracksuit_man` (fallback only) |
| [House](https://sketchfab.com/3d-models/house-be18892d167f40d9bb4d7dcae0eb0573) | [Fishboe](https://sketchfab.com/ministephen) | CC BY 4.0 | neighbourhood house type (prepare_new_houses.py) |
| [Kitchen Decor Pack](https://sketchfab.com/3d-models/kitchen-decor-pack-173a93db2b174410ac28093e3ed223fc) | [Visthétique](https://sketchfab.com/visthetique) | CC BY 4.0 | kitchen dressing (prepare_interiors.py) |
| [Low Poly Forest Tree Pack](https://sketchfab.com/3d-models/low-poly-forest-tree-pack-5ff5a51e74324845a4e4905f182dfb2b) | [99.Miles](https://sketchfab.com/99.Miles) | CC BY 4.0 | forest horizon trees (prepare_landscape.py) |
| [Low poly plants pack](https://sketchfab.com/3d-models/low-poly-plants-pack-6ae038082e8347deb2061bb47013770c) | [assetfactory](https://sketchfab.com/assetfactory) | **Sketchfab Standard** | street planters `assets/sketchup/props/plants` (prepare_prop_packs.py) |
| [Low Poly PSX Style Restaurant Props - Asset Pack](https://sketchfab.com/3d-models/low-poly-psx-style-restaurant-props-asset-pack-888fbeb6cc0a476faa9c2ba7bcfdd93e) | [keywizzz](https://sketchfab.com/keywizzz) | CC BY 4.0 | restaurant props (prepare_prop_packs.py) |
| [Low Poly Tree Scene Free](https://sketchfab.com/3d-models/low-poly-tree-scene-free-89daa5e21f0d4f08a59dba0d566e88bd) | [Nicholas-3D](https://sketchfab.com/Nicholas01) | CC BY 4.0 | landscape trees (prepare_landscape.py) |
| [Male Character In Caual Clothing](https://sketchfab.com/3d-models/male-character-in-caual-clothing-24ad029f3a094a679bc0b0b109ee40e3) | [mahensanketh](https://sketchfab.com/mahensanketh) | CC BY 4.0 | legacy pedestrian (fallback only) |
| [Maple Trees](https://sketchfab.com/3d-models/maple-trees-9f51e08e56cd4e44b35fd02a3ad8d3a6) | [Jagobo](https://sketchfab.com/Jagobo) | CC BY 4.0 | landscape trees (prepare_landscape.py) |
| [Model- Anim- Talking Visio Win](https://sketchfab.com/3d-models/model-anim-talking-visio-win-471d7bfc18134d38b5e619eaf098867f) | [TG13730](https://sketchfab.com/TG13730) | CC BY 4.0 | talking clip for the door customer (prepare_player.py) |
| [Mustafa Ataturk](https://sketchfab.com/3d-models/mustafa-ataturk-977b82ff366e40dfb2ee3183d5cb24da) | [statuevision](https://sketchfab.com/statuevision) | CC BY 4.0 | monument (prepare_monuments.py) |
| [Mustafa Kemal Ataturk Horse Statue](https://sketchfab.com/3d-models/mustafa-kemal-ataturk-horse-statue-f594ea55bb7c4a94ad9330e4679942e8) | [mrahmet](https://sketchfab.com/ahmetusta827) | CC BY 4.0 | equestrian monument (prepare_monuments.py) |
| [NPC](https://sketchfab.com/3d-models/npc-d2ebd003e49e4e7ba5a381ee2c63df3c) | [Dr Nor Hafizah Adnan](https://sketchfab.com/norhafizah) | CC BY 4.0 | legacy pedestrian (fallback only) |
| [NPC 2](https://sketchfab.com/3d-models/npc-2-60c4d56cbd794cf0819b629818b0da62) | [Dr Nor Hafizah Adnan](https://sketchfab.com/norhafizah) | CC BY 4.0 | legacy pedestrian (fallback only) |
| [Open Arms in the Park](https://sketchfab.com/3d-models/open-arms-in-the-park-1d65922c53c8497caf698bf6611d7fa4) | [Zizian1987](https://sketchfab.com/493caf85284a49b4a090c9c6eb1935) | CC BY 4.0 | park statue (prepare_monuments.py) |
| [Optimized Potted Plants](https://sketchfab.com/3d-models/optimized-potted-plants-967b4bf23fac4098993776fcfc2d3318) | [Nicholas-3D](https://sketchfab.com/Nicholas01) | CC BY 4.0 | potted plants (prepare_prop_packs.py) |
| [Park Stretch](https://sketchfab.com/3d-models/park-stretch-2f9651294cc54d52b74f7e0989dc18cd) | [Zizian1987](https://sketchfab.com/493caf85284a49b4a090c9c6eb1935) | CC BY 4.0 | park fitness equipment (prepare_monuments.py) |
| [PBR Street Props Pack (Game Ready)](https://sketchfab.com/3d-models/pbr-street-props-pack-game-ready-8013d8e6af4645d1a7c3d5b24054bfc8) | [MadeByYeshe](https://sketchfab.com/MadeByYeshe) | CC BY 4.0 | street furniture (prepare_prop_packs.py) |
| [Platano Tree](https://sketchfab.com/3d-models/platano-tree-ef48485b7c534acc905c0d9964c5fe7c) | [gelmi.com.br](https://sketchfab.com/rodrigogelmi) | CC BY 4.0 | street trees (prepare_landscape.py) |
| [Police car](https://sketchfab.com/3d-models/police-car-9166b13b6ae341f4bfc093edb71d74f4) | [Mateusz Woliński](https://sketchfab.com/jeandiz) | CC BY 4.0 | police traffic car (prepare_sketchup_assets.py) |
| [Road pack (not including the road)](https://sketchfab.com/3d-models/road-pack-not-including-the-road-021707f910d04907ab576c856a749628) | [drcrazzie](https://sketchfab.com/drcrazzie) | CC BY 4.0 | road props: signs, barriers, cones (prepare_prop_packs.py) |
| [Security Guard – Rigged 3D Model](https://sketchfab.com/3d-models/security-guard-rigged-3d-model-1e3307732bbf4453b30f021bfec5bcaf) | [Q.SARDOR](https://sketchfab.com/qsardor57913) | CC BY 4.0 | legacy guard (fallback only) |
| [Sofa Set](https://sketchfab.com/3d-models/sofa-set-4230c38118dc41878ddf79ea06bac33c) | [budakbina](https://sketchfab.com/budakbina) | CC BY 4.0 | Cedar House living room (prepare_interiors.py) |
| [Sophia Animated 003 - Animated 3D Woman](https://sketchfab.com/3d-models/sophia-animated-003-animated-3d-woman-dc448c3be0e74f96a55fb475a13433cf) | [Renderpeople](https://sketchfab.com/renderpeople) | CC BY 4.0 | legacy pedestrian (fallback only) |
| [Statue in Hyde Park London](https://sketchfab.com/3d-models/statue-in-hyde-park-london-c105d36047dd43dc8d597d80fd842249) | [artfletch](https://sketchfab.com/artfletch) | CC BY 4.0 | park statue (prepare_monuments.py) |
| [Street Basketball Court](https://sketchfab.com/3d-models/street-basketball-court-2dfc6954e40e4eb3b064192fe158f995) | [Arsen Ismailov](https://sketchfab.com/fdgasd7) | CC BY 4.0 | sports court (prepare_monuments.py) |
| [Stylized Plant Pots Set – 3DModel FBX + Textures](https://sketchfab.com/3d-models/stylized-plant-pots-set-3dmodel-fbx-textures-0d0a6c8960f84e6fa226fba2c03a2c57) | [Solcito Kawaii 3D](https://sketchfab.com/solcito3D) | CC BY 4.0 | interior plant pots (prepare_interiors.py) |
| [Suburban House](https://sketchfab.com/3d-models/suburban-house-efcc220c62f641d29a1480e8b221c7b3) | [Bogdan Strielecki](https://sketchfab.com/strielecki) | CC BY 4.0 | neighbourhood house type (prepare_new_houses.py) |
| [Trailer Park Props](https://sketchfab.com/3d-models/trailer-park-props-009a2ada8f874aa2bb643a60f2fbcae4) | [Elbolillo](https://sketchfab.com/Elbolilloduro) | CC BY 4.0 | yard props (prepare_interiors.py) |
| [Tree](https://sketchfab.com/3d-models/tree-b5183be5d2d447f09b9dab247808b010) | [zackmillot](https://sketchfab.com/zackmillot) | CC BY 4.0 | landscape tree (prepare_landscape.py) |
| [Tree Animate](https://sketchfab.com/3d-models/tree-animate-f0f9eb5e6c104bbb8e1f41c97019e6f2) | [RandyGF](https://sketchfab.com/RandyGF) | CC BY 4.0 | landscape tree (prepare_landscape.py) |
| [Tv Unit](https://sketchfab.com/3d-models/tv-unit-0074168f4dd64836823667ea871d13ba) | [projectkaizen](https://sketchfab.com/project_kaizen) | CC BY 4.0 | Cedar House living room (prepare_interiors.py) |
| [Woman Riding A Gray Bicycle](https://sketchfab.com/3d-models/woman-riding-a-gray-bicycle-0dd180eb11424e7ba64ce93c6dddb60b) | [restore50](https://sketchfab.com/restore50) | CC BY 4.0 | player / NPC bicycle `assets/bicycles/gray_bicycle.glb` and its rider |

"Legacy pedestrian (fallback only)": converted people used only when `assets/people/people.json`
is missing; the townspeople are the MPFB characters below.

## Other sources

| Asset | Source | Licence | Notes |
|---|---|---|---|
| Townspeople NPC01–NPC37, courier v3 (`assets/people/`, `assets/player/courier.glb`) | Built in Blender with [MPFB 2](https://static.makehumancommunity.org/mpfb.html) / MakeHuman assets, garments and textures from `tools/npc/` | MakeHuman/MPFB assets **CC0**; our scripts and outputs are own work | The MPFB add-on itself (GPL-3) is a tool and is not shipped. |
| Character reference sheets (`reference_images/`) | AI-generated | Owner: free for commercial use | Not shipped (Godot-ignored, not committed). |
| Universal Animation Library 1 & 2 (`assets/animations/ual/`) | [Quaternius](https://quaternius.com) | **CC0 1.0** (`assets/animations/ual/LICENSE.txt`) | Locomotion / sitting / kneeling clips. |
| Higgsfield houses and bicycle (`world/higgsfield/`) | Higgsfield 3D (AI) | Owner: free for commercial use | Provenance: `world/higgsfield/PROVENANCE.md`, `docs/HIGGSFIELD_HOUSING_REPORT.md`. |
| Procedural props, buildings, roads, sounds (`tools/`, `sfx_forge`) | Own work | — | |
| ElevenLabs sound effects (`assets/audio/elevenlabs/`) | ElevenLabs text-to-sound | **Check before release:** the free plan does not allow commercial use and requires attribution | Generate again on a paid plan (or replace) before a commercial release. |
| Courier v1 (`assets/player/archive/v1_mixamo/`, Godot-ignored) | Adobe Mixamo (Ch42, Jog Forward) | Mixamo terms: free in projects; the raw character must not be redistributed on its own | Archived and unused; remove from the public repository or make it private. |
| Door customer (`assets/player/customer_avaturn.glb`) | Avaturn avatar | Avaturn terms of use | Fallback only (the townspeople replace it). |
| Volkswagen Jetta GLI 2025 (`assets/vehicles/jetta_gli_2025/`, source `volkswagen-jetta-gli-2025/`) | **Source not recorded** | **Unknown — please confirm** | No metadata in the GLB. Also a real brand and model name: a commercial release may need a generic name and badges. |
| `sketchup_assets/car_model.glb` → repaired car (`assets/vehicles/repaired_car/`) | Supplied by the owner, **source not recorded** | **Unknown — please confirm** | |

## Credits text (for the in-game credits screen)

Models from Sketchfab, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/),
converted and optimised for this game: see the table above for every title and author.
Animations: Universal Animation Library by Quaternius (CC0). Characters made with MakeHuman /
MPFB assets (CC0).

## Keeping this file current

New downloads: drop the GLB in `sketchup_assets/` or `source_assets/incoming_*`, then run
`python tools/asset_ledger.py` — it lists every GLB's embedded Sketchfab title, author, licence
and URL and flags anything that is not CC BY / CC0 or has no metadata.
