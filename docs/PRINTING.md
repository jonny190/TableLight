# TableLight - printing guide

All STLs in `cad/stl/` are exported in their print orientation with Z = build direction and the part
resting on Z = 0. No supports are needed for any part.

| Part | Orientation (as exported) | Layer | Walls | Infill | Notes |
|---|---|---|---|---|---|
| `base_shell.stl` | upside down: honeycomb deck on the bed, walls up | 0.2 mm | 3 (1.2 mm) | 15 % | The deck face is the visible top of the base; the 1.5 mm hexagon pockets print as walls rising from the bed and come out crisp on a smooth sheet. The four bottom-plate bosses have 45 deg cones so they need no support. The USB-C / switch slots are short horizontal bridges (13 mm max). |
| `base_bottom_plate.stl` | flat, outer face down | 0.2 mm | 3 | 20 % | Screw-head and foot recesses face the bed. |
| `stem.stl` | upright, flange on the bed | 0.2 mm | 3 | any (it is a tube) | 236 mm tall, Ø22: slow the outer wall to ~40 mm/s above 150 mm, enable Z-hop, use a brim if adhesion is marginal. The two Ø2.6 screw holes near the top are self-tapped by the M3 head screws. Needs 240 mm of Z travel - reduce `stem_len` in `cad/tablelight.py` if you have less. |
| `head_plate.stl` | upside down: white top face on the bed, skirt and socket pointing up | 0.2 mm | 3 | 20 % | White PLA. The ring channels and the touch recess face up and need no support. 20 mm tall as printed. |
| `cone_shade.stl` | upright, wide end on the bed | 0.2 mm (0.16 for a smoother surface) | 3 perimeters, **0 top layers, 0 infill** | - | Plain 1.6 mm wall cone leaning 8.5 deg inward - also fine in **vase mode** with a 0.8 mm line (then the 3 screw holes are lost: drill them, or glue the cone to the skirt). Three 1.5 mm nubs inside near the top hold the diffuser; they are tiny overhangs and print fine. Print black for the look in the reference render, or white/light grey for 20-30 % more light on the table. |
| `head_diffuser.stl` | flat | 0.2 mm | 3 | 100 % (it is 1.2 mm) | Natural/white translucent PLA or PETG. It flexes past the nubs on the way in. |

## Materials

* Base, plate, stem, cone: PLA is fine (nothing in the base gets hot: worst case ~2 W in the charger for a
  few minutes, ~1 W in the boost at full brightness). Dark colours hide the electronics through the switch slot.
* Head plate: white, opaque. It is the visible top; a matte white looks closest to the render.
* Diffuser: translucent. The LEDs sit 12 mm above it, so hotspots are soft; 4 perimeters or 0.16 mm layers
  if you want it even smoother.

## Tolerances built into the model

| Interface | Nominal clearance |
|---|---|
| Head skirt inside the cone top | 0.3 mm radial |
| Stem in the head socket | 0.2 mm radial (friction fit + 2 screws) |
| Diffuser disc in the cone | 0.4 mm radial at the nub height |
| PCB (Ø110) in the base cavity (Ø113) | 1.5 mm radial |
| Bottom plate in the shell | 0.3 mm radial |
| Heat-set insert holes | Ø4.0 mm, 6 mm deep |
| Screw clearance holes | Ø3.4 mm |

If your printer runs tight, scale nothing - edit `skirt_clear`, `socket_clear`, `diffuser_clear` or
`plate_clear` in `cad/tablelight.py` and regenerate.

## Heat-set inserts (12 x M3)

* 4 in the deck bosses inside the base shell (for the PCB screws) - insert from below.
* 4 in the stem flange - insert from below (the flange is 6 mm thick: use 4-5 mm long inserts here).
* 4 in the shell's bottom bosses (for the bottom plate) - insert from below.

Push straight; the bosses are 7.5-8 mm in diameter so a bit of melt bulge is fine. Let them cool before
loading. The five black M3 x 6 screws for the cone and the head socket are self-tapping into Ø2.6 holes - no
inserts.
