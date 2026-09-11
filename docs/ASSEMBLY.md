# TableLight - assembly

Coordinate reference: the CAD origin is the centre of the base deck (top face of the base disc). "Down" is
toward the bottom plate. The PCB hangs under the deck with its components facing DOWN, so everything
electrical is reachable by removing the bottom plate. The wires from the head run down the stem, through
the Ø12 deck hole and the 14 x 6 slot in the PCB centre to the connectors on the component side.

## 0. Before you start

* PCB assembled and bench-tested (`hardware/pcb/README.md`, "bring-up").
* WLED flashed and configured (`docs/WLED_SETUP.md`) - easier before the board is inside the base.
* Heat-set inserts fitted (`docs/PRINTING.md`): 4 deck bosses, 4 stem flange, 4 shell bosses.

## 1. Head: LED ring(s) and touch pad

1. Solder three 300 mm silicone leads (5V, GND, DIN) to the 24-LED ring's input pads. If you use the optional
   16-LED inner ring, first wire 24-ring DOUT / 5V / GND to the 16-ring DIN / 5V / GND with 40 mm jumpers.
2. Turn the head plate upside down. The two circular channels are 2.5 mm deep. Put 1 mm double-sided foam
   tape on the back of the ring(s), lay the input pads over the **radial wire groove** (the 4 mm slot running
   from the outer channel to the central socket) and press the ring(s) in, LEDs facing out (down when fitted).
3. Route the three leads along the groove, through the **notch in the socket wall**, and let them hang out of
   the socket bore.
4. Cut a **Ø18 copper foil disc**, solder a 300 mm wire to it first, then stick it into the **Ø20 recess at the
   top of the socket bore**. Cover with Kapton. That wire also goes down the bore.
5. Bench test the ring(s) from the PCB before going further.

## 2. Head: shade and diffuser

1. Push the diffuser disc into the cone from the wide end, up past the three nubs (it flexes) until it rests
   on them, 14 mm below the top edge. Its Ø24 centre hole is for the stem.
2. Drop the head plate onto the cone: the skirt enters the cone top, the Ø104 lip sits flush on the rim.
   Rotate until the three Ø3.4 holes in the cone line up with the three Ø2.6 holes in the skirt and drive
   **3 x M3 x 6 black button-head screws** (they self-tap into the skirt).

## 3. Stem

1. Feed the four wires (5V, GND, DIN, TOUCH) from the head through the stem, flange end last.
2. Push the stem into the head socket until it bottoms (13 mm in). Its two Ø2.6 holes align with the two
   Ø3.4 holes in the socket boss; drive **2 x M3 x 6** through the boss into the stem.
3. Crimp / solder the **3-pin JST-PH** (5V, GND, DIN) and the **2-pin JST-PH** (TOUCH, blank) on the wire ends.

## 4. Base

1. Stand the stem on the deck, flange centred over the Ø12 hole, wires hanging through. From underneath drive
   **4 x M3 x 8** through the deck holes into the flange inserts.
2. Hold the PCB under the deck, components facing down, **USB-C toward the −Y wall opening**. Pass the two
   plugs through the 14 x 6 slot and plug them into J2 (LED) and J3 (touch).
3. Slide the board up so the USB-C receptacle enters its slot and the slide switch actuator enters its slot;
   fit **4 x M3 x 6** through the PCB holes into the deck bosses. Check the USB-C opening is central on the
   receptacle and the two charge LEDs sit behind their Ø2.5 holes.
4. Insert **1 or 2 x 18650** (same model, same charge state), positive toward the "+" marked ends of the
   holders (both holders are in parallel).
5. Screw the **bottom plate** on with **4 x M3 x 8** into the shell bosses; stick the **4 rubber feet** into
   their recesses.

## 5. First light

Slide switch ON. Plug in USB-C: red LED = charging, green = full. Touch the white top: WLED toggles. The
light falls through the diffuser onto the table; the cone stays dark outside.

## Wiring summary

| From | To | Wire |
|---|---|---|
| J2.1 VLED | 24-ring 5V | red, 300 mm |
| J2.2 GND | 24-ring GND | black, 300 mm |
| J2.3 DATA | 24-ring DIN | any, 300 mm |
| 24-ring DOUT / 5V / GND | 16-ring DIN / 5V / GND (optional) | 3 x 40 mm inside the head |
| J3.1 TOUCH_PAD | copper disc in the socket recess | 1 wire, 300 mm (twist it with the GND wire) |

## Servicing

Four bottom-plate screws: batteries, connectors, RESET/BOOT buttons and the expansion header are all on the
exposed component side. Two socket screws release the whole head from the stem; three cone screws release the
shade from the head plate.
