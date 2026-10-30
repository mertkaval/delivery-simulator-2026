# Research notes: junction trimming and junction merging (2026-10-29)

These notes are a research summary gathered by a subagent from public sources. They inform phase C of
[READY.md](READY.md). Re-verify any constant marked SUM before relying on it.

Tags:
- **SRC**: read in the source code.
- **DOC**: from the official documentation.
- **SUM**: a large file summarised by the fetch tool (not read line by line).
- **INF**: our own inference.

## Trimming rule used by four tools (osm2streets, OSM2World, streets-gl, SUMO)

All four compute the trim the same way:

1. Offset the full-width edges of both neighbouring approaches.
2. Intersect them.
3. Project the crossing point perpendicularly onto each road's centre line.
4. Each road takes its largest candidate trim.

None of them derive the trim from a corner fillet. Our trim reached only as far as the fillet rings, so at acute angles
the sidewalks still overlapped past the trims.

- **osm2streets** `trim_to_corners`
  ([geometry/general_case.rs](https://github.com/a-b-street/osm2streets/blob/main/osm2streets/src/geometry/general_case.rs)),
  SRC:
  - It uses the full road width, sidewalks included.
  - It intersects the facing edge polylines of each pair of clockwise-adjacent roads.
  - It projects the crossing back onto the centre line, keeping the larger trim per side.
- **OSM2World** `calculateJunctionNodeEffects`
  ([NetworkCalculator.java](https://github.com/tordanik/OSM2World/blob/master/core/src/main/java/org/osm2world/world/network/NetworkCalculator.java)),
  SRC:
  - It intersects the edge lines of adjacent segments.
  - It treats edges within 10 degrees of each other as parallel.
  - The farthest-back projection becomes the cut.
  - Segments that end up invalid are dropped as "broken".
- **streets-gl**
  ([IntersectionPolygonBuilder.ts](https://github.com/StrandedKitty/streets-gl/blob/HEAD/src/lib/road-graph/IntersectionPolygonBuilder.ts)),
  SRC:
  - The same rule, with the edges extended 16 m.
  - Each crossing is copied straight across the road; the farthest hit is the trim.
- **SUMO netconvert** (NBNodeShapeComputer.cpp), SUM: the crossing distance plus a corner radius (default 4 m;
  small radius 1.5 m).

## Merging close junctions

- **osm2streets**, SRC:
  - After the real trims, a road with `trim_start + trim_end > length` is flagged as internal.
  - That road is collapsed and its two junctions merged
    ([collapse_short_road.rs](https://github.com/a-b-street/osm2streets/blob/main/osm2streets/src/operations/collapse_short_road.rs)).
  - The passes repeat.
  - Older versions merged when the trimmed length was under 5 m.
- **SUMO**, DOC: joins junctions when the centre-to-centre length is under 10 m (`junctions.join-dist`).
- **CityEngine**, DOC: collapses the segments behind conflicting node shapes, repeating until no conflicts remain.

## Design guidance on acute intersections (DOC / secondary)

- AASHTO / FHWA: 60 degrees gives most of the benefit of a right angle, and 75-90 degrees is desirable.
- [Iowa DOT 6A-8](https://iowadot.gov/design-manual/chapter-6-geometric-design/6a-8-intersection-alignment-and-realignment):
  - 60-120 degrees is acceptable and 75-90 desirable.
  - Below 60 degrees, realign: curve the minor road toward 90 degrees, or split it into offset T-junctions.

## Recommended rules for MRS (INF; still to be verified by our own sweeps)

- **Trim.** For each neighbour B and each layer l (asphalt edge, kerb, sidewalk back):
  - `trim_A = max(d_l + max(R_l, 0) * cot(theta / 2))`, where `d_l` is where the two layer-l edges cross, projected onto A.
  - For straight approaches, `d_l = (h_B,l + h_A,l cos theta) / sin theta`.
- **Merge.** Merge two junctions when `L - trim_start - trim_end < X` (X: a crossing plus a kerb return, about 5 m).
  Recompute the trims and repeat until nothing changes.
- **Angle limit.** The tool's limit comes from our own sweeps (READY.md), not from these sources. These sources
  suggest a floor near 60 degrees with a warning below 75.
