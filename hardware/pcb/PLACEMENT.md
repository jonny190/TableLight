# TableLight PCB - placement constraints (KiCad coordinates)

Origin = board centre. KiCad Y axis points DOWN, so KiCad (x, y) = (x_view, -y_view). Viewed from the component side.

Generated from `cad/tablelight.py` parameters by `board_outline.py`.

| Item | KiCad (x, y) mm | Size / notes |
|---|---|---|
| Board outline | (0, 0) | circle Ø110 mm (`outline.dxf`, layer Edge.Cuts) |
| Wire slot | (0, 0) | 14 x 6 mm rounded slot in the board centre (under the Ø12 deck hole / stem bore); keep 1 mm copper clearance |
| H1 mounting hole | (+35.36, -35.36) | Ø3.2 mm; deck boss Ø7.5 mm lands on the SOLDER side around it |
| H2 mounting hole | (-35.36, -35.36) | Ø3.2 mm; deck boss Ø7.5 mm lands on the SOLDER side around it |
| H3 mounting hole | (-35.36, +35.36) | Ø3.2 mm; deck boss Ø7.5 mm lands on the SOLDER side around it |
| H4 mounting hole | (+35.36, +35.36) | Ø3.2 mm; deck boss Ø7.5 mm lands on the SOLDER side around it |
| J1 USB-C body | (+0.00, +52.33) | receptacle mating face at y_view = -56.0 (1 mm past the edge), pointing -Y |
| SW1 slide switch | (-25.25, +43.73) | actuator radially outward at 240 deg (view); base slot 9.0x4.0 mm |
| D3 CHRG LED | (+21.15, +47.50) | at board edge, light hole Ø2.5 in the base wall |
| D4 STDBY LED | (+25.21, +45.48) | at board edge, light hole Ø2.5 in the base wall |
| U1 ESP32 module | (+0.00, -38.05) | 18.0x25.5 mm, antenna toward +Y_view (board edge); antenna zone 6.0 mm: no copper |
| Stem flange screw heads (solder side) | r = 14.5 mm at 45/135/225/315 deg | M3 heads sit in the 5 mm gap above the board: keep the solder side flat there (no tall THT leads) |
| BT1 18650 holder | (+0.00, -14.40) | 77.7x20.8 mm, long axis along X, '+' toward +X_view |
| BT2 18650 holder | (+0.00, +14.40) | 77.7x20.8 mm, long axis along X, '+' toward +X_view |
| J2 LED ring | (-22.00, +29.00) | JST-PH; wires run along the holder edge to the centre slot |
| J3 touch | (+22.00, +29.00) | JST-PH; wires run along the holder edge to the centre slot |
| Boss keep-out 1 | (-48.97, -20.28) | Ø10 mm zone: parts taller than 9 mm not allowed here |
| Boss keep-out 2 | (+20.28, -48.97) | Ø10 mm zone: parts taller than 9 mm not allowed here |
| Boss keep-out 3 | (+48.97, +20.28) | Ø10 mm zone: parts taller than 9 mm not allowed here |
| Boss keep-out 4 | (-20.28, +48.97) | Ø10 mm zone: parts taller than 9 mm not allowed here |

* Max component height anywhere on the component side: **22 mm** (bottom plate is 22.9 mm below the component face).
* Solder side: 5 mm clearance to the deck. Keep THT pins trimmed below 3 mm.
* Antenna zone: keep the +Y edge of the module flush with, or overhanging, the board edge and copper-free on all layers.
* Thermals: pour a large copper area (both sides, stitched) under the TP4056 EP and around D1/Q2; the enclosure is closed PLA.
* Battery holders carry up to ~2.5 A: use >= 1.5 mm traces or pours for BAT+, CELL-, GND, VSYS, +5V, VLED.
