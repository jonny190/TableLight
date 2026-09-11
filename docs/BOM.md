# TableLight - Bill of Materials

Prices are rough 2026 hobby-quantity estimates (GBP) to help budgeting; check current suppliers.
The PCB component list with reference designators is generated in `hardware/pcb/bom_pcb.csv`.

## 1. Printed parts

| Part | File | Qty | Material | Approx. filament |
|---|---|---|---|---|
| Base shell (honeycomb disc) | `cad/stl/base_shell.stl` | 1 | PLA or PETG, opaque (black like the render) | 64 cm3 (~80 g) |
| Base bottom plate | `cad/stl/base_bottom_plate.stl` | 1 | same as shell | 30 cm3 (~37 g) |
| Stem | `cad/stl/stem.stl` | 1 | same as shell | 41 cm3 (~51 g) |
| Head plate (white top) | `cad/stl/head_plate.stl` | 1 | white PLA | 54 cm3 (~67 g) |
| Cone shade | `cad/stl/cone_shade.stl` | 1 | same as shell outside; white inside would be brighter (see PRINTING.md) | 73 cm3 (~90 g) |
| Head diffuser | `cad/stl/head_diffuser.stl` | 1 | natural / white translucent PLA or PETG | 10 cm3 (~12 g) |

Total ~340 g of filament (~£8).

## 2. Electronics - custom PCB path

| Item | Qty | Notes | Est. |
|---|---|---|---|
| TableLight controller PCB, Ø110 mm, 2 layer, 1.6 mm | 1 (min order 5) | `hardware/pcb/` - order from JLCPCB/PCBWay/Aisler with `outline.dxf`; optional SMD assembly | £5-£40 |
| PCB components (SMD + THT) | 1 set | full list in `hardware/pcb/bom_pcb.csv`; ~£12 as a one-off kit from LCSC/Mouser, key parts below | £12-£18 |
| - ESP32-WROOM-32E-N4 | 1 | WLED-supported module with native capacitive touch | |
| - TP4056 + DW01A + FS8205A | 1 each | charger + 1S protection | |
| - MT3608 + 4.7 uH / 4 A inductor + 2 x SS34 | 1 set | 5.1 V boost + load-share/boost diodes | |
| - AO4407A (SOIC-8) + AO3401A + 2N7002 | 1 each | load-share P-FET, LED rail switch, driver | |
| - AP2112K-3.3, CH340C, SN74AHCT1G125, USBLC6-2SC6 | 1 each | LDO, USB-UART, level shifter, ESD (ESD optional) | |
| - USB-C receptacle 16 pin (HRO TYPE-C-31-M-12) | 1 | top-mount | |
| - 18650 PCB holder (Keystone 1042 or BH-18650-PC) | 2 | fit one or both | |
| - C&K OS102011MA1QN1 slide switch, 2 x TL3342 tactile | 1 + 2 | power / RESET / BOOT | |
| - JST-PH 2.0 mm headers: 3 pin x1, 2 pin x2; 1x6 2.54 mm header | | LED, touch, alt. battery, expansion | |
| - passives 0603/0805, 100 uF 6.3 V SMD electrolytic, 2 x 0603 LEDs | | see CSV | |
| 18650 Li-ion cell, flat top, unprotected, e.g. Samsung INR18650-35E / LG MJ1 (3400-3500 mAh) | 1 or 2 | buy from a reputable seller; both cells identical if using two | £5-£7 each |
| LED ring, 24 x SK6812 RGBW (RGB + warm/neutral white) or WS2812B, 5 V, OD 86 mm / ID 72 mm | 1 | the common "24-bit WS2812B ring"; RGBW gives proper white for a lamp | £4-£7 |
| LED ring, 16 LED, OD 68 mm / ID 53 mm (or Adafruit NeoPixel Ring 24, OD 65.5 mm) | 0-1 | optional second ring in the inner channel (+16 LEDs, wired in series) | £3-£6 |
| Copper foil tape, self-adhesive, >= 20 mm wide | ~30 mm | touch pad disc Ø18 under the head plate | £3 (roll) |
| JST-PH pigtails: 3 pin x1, 2 pin x1 (300 mm leads) | 1 each | or crimp your own; leads must reach through the 236 mm stem | £2 |
| Silicone wire 26 AWG, 3 colours | ~1.5 m | ring-to-ring jumpers + touch wire | £3 |

## 3. Hardware

| Item | Qty | Where |
|---|---|---|
| M3 heat-set insert, Ø4.6 x 4-5.7 mm (hole Ø4.0) | 12 | 4 deck bosses (PCB), 4 stem flange, 4 shell bosses (bottom plate) |
| M3 x 6 mm pan/button head screw | 4 | PCB to deck bosses |
| M3 x 8 mm pan head screw | 8 | stem to deck (through the deck from below), bottom plate to shell |
| M3 x 6 mm button head screw, black | 5 | 3 x cone shade to head skirt (radial, self-tapping into Ø2.6 holes), 2 x head socket to stem |
| Rubber feet, self-adhesive, Ø10 x 3 mm | 4 | bottom plate recesses |
| Double-sided foam tape (1 mm) | small | LED ring(s) into the head channels |
| Kapton or electrical tape | small | over the touch pad foil / wire retention |

## 4. Tools

Soldering iron (heat-set insert tip helps), flush cutters, small Phillips driver, tweezers, USB-C cable
that carries data (not charge-only), a 5 V / 2 A+ USB-C supply.

## 5. Approximate total

Filament £8 + PCB and components £20-£55 + cells £5-£14 + rings/wire/foil £12-£20 + hardware £6
= **about £50-£100** for one lamp (the PCB minimum order covers five boards).

## Alternative without a custom PCB

The base is designed around the custom Ø110 board (the USB-C, switch and LED openings, the mounting
bosses and the centre wire slot are placed for it). A module-based build (ESP32 dev board + TP4056 module
+ MT3608 module + TTP223 touch module + 2 wire-lead 18650 holders) is electrically equivalent but does not
fit the Ø113 x 23 mm cavity as-is: you would raise `base_height` in `cad/tablelight.py` by ~15 mm and print a
custom tray. The wiring is the same as the block diagram: TP4056 OUT -> MT3608 IN -> 5 V, TP4056 OUT -> dev
board 5V/VIN pin (its LDO), GPIO2 data through a 330 R, TTP223 OUT to a GPIO configured as a WLED button.
