# Glass video, segment b: decisions taken without the user

To be merged into `tools/materials/DECISIONS.md` by the docs step. Segment b = `SNKNqHd0AYI` 22:32-34:03
(Textured Glass Wavy, Textured Glass Blobby, Frosted Glass) plus the overview 00:40-02:42 and the setup 03:14-06:10.

| # | decision | reason |
|---|---|---|
| b1 | The specification describes the graphs **built in the tutorial**. The control sets of the purchased project file shown in the overview (Wavy without Gabor Frequency; Blobby with Voronoi Roughness and no noise-roughness controls; Frosted with "Noise ..." names) are recorded as variants only. | the product graphs are never shown inside (class D); the tutorial graphs are fully visible (class A) |
| b2 | Wavy Gabor **Orientation 3D = (0.797, 0.604, 0.0)**, class C. | the value is never displayed as numbers; a Lambert fit of the direction-ball widget gives (0.796, 0.605, -0.009) and (0.799, 0.602, -0.007) on two frames and recovers Blender's default (0.707, 0.707, 0) on the default frame |
| b3 | Colour-ramp greys are converted from the picker's perceptual HSV value with the sRGB EOTF: Blobby stop 1 = 0.448; Frosted stop 0 = 0.0958, stop 1 = 0.4755 (linear). | the picker was in Perceptual mode and ramp colours are stored scene-linear |
| b4 | Interface limits that were never displayed (Blobby Voronoi Detail 0..15, Frosted Detail 2 Factor 0..1) take Blender's socket limits, class C. | their panels were never selected; the twin sockets show these limits |
| b5 | Evidence frames are re-decoded at exact times (listed in `evidence/b/index.json`, `frame_times`); file names use the whole second. | the 1 fps work extraction samples at about N + 0.48 s (ffmpeg fps rounding); exact times keep frames and crops reproducible |
| b6 | Only cited material is kept under `tools/`: 32 full frames (about 34 MB) and 40 labelled crops (about 9 MB). Socket panels from frames that are not kept are stored as labelled crop sheets with their video times. | D7 and "no bulk dumps in tools/" |
| b7 | Node defaults were read once from Blender 5.2.3 headless (factory startup, nothing saved, no scene touched) to tell defaults from edits (Gabor 3D orientation default (sqrt2, sqrt2, 0), Bump Distance default 0.001, Glass BSDF Multiscatter GGX / roughness 0 / IOR 1.5, socket identifiers "Orientation 3D" and "Fac"). | the video shows Blender 5.1.1; the defaults matter for class decisions and for the builder's socket names |
| b8 | Suggested library names `PM_GlassWavy`, `PM_GlassBlobby`, `PM_GlassFrosted` (D3); final names are the builder's call. | D3 naming rule |
| b9 | Flag for the builder: the Gabor Texture has only 2D / 3D modes, so the Wavy needs a D5 adaptation for the 4D torus (seamless) mode. | D5 |
