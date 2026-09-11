# TableLight - WLED setup

## Firmware

Two options:

1. **Stock WLED (ESP32 build) from the web installer** - everything works (LEDs, touch button, relay pin)
   except the battery percentage.
2. **Custom build with the Battery usermod** - copy `firmware/wled/platformio_override.ini` into a WLED
   source checkout and build the `tablelight` environment (`pio run -e tablelight`). This adds the battery
   readout to the UI and MQTT/Home Assistant and bakes in the pin defaults below.

Flashing: plug the lamp's USB-C into the computer (data cable!). The CH340C shows up as a serial port; the
auto-reset circuit means esptool / the web installer need no button presses. If a board ever refuses: hold
BOOT (SW3), tap RESET (SW2), release BOOT, flash.

## Settings -> LED preferences

| Setting | Value | Why |
|---|---|---|
| LED type | SK6812 RGBW (or WS2812B if that is what your ring is) | |
| Colour order | GRB (check with a red-only test) | |
| Length | **24** (40 with the optional inner ring) | |
| GPIO | **2** | LED_DATA, level shifted to 5 V on the board |
| Enable automatic brightness limiter | on, **1200 mA** | boost converter and protection headroom |
| LED voltage / mA per LED | 5 V, 55 mA | for the limiter |
| Relay GPIO | **16**, active high, *not* inverted | LED_EN: powers the 5 V LED rail only while the light is on |
| Auto-off / turn LEDs off after | as you like | with the relay pin the ring draws nothing when off |

With two rings, make segment 0 = LEDs 0-23 (outer) and segment 1 = LEDs 24-39 (inner) so you can run a
warm white outer ring with a coloured accent in the middle, or map them as a 2-ring "2D" via segment groups.

## Settings -> LED preferences -> Buttons

| Button | GPIO | Type |
|---|---|---|
| Button 0 | **4** | **Touch (capacitive)** |
| Touch threshold | start at 32 (default); lower = more sensitive | 2 mm of PLA over a Ø18 pad usually needs 20-30 |

Touch actions are the WLED defaults: short press = toggle, long press = brightness ramp, double = preset.
Tune the threshold until a fingertip on the white top toggles reliably but a hand near the lamp does not.
Typical raw values through 2 mm plastic with this pad: ~60-70 untouched, ~20-30 touched.

## Battery usermod (custom build only)

| Setting | Value |
|---|---|
| Battery type | Li-ion |
| Measurement pin | **35** |
| Voltage multiplier / calibration | 2.0 (100k/100k divider) - then trim so the reading matches a multimeter on the cell |
| Min / max voltage | 3.0 V / 4.2 V |
| Read interval | 30 s |
| Auto-off when low | 5 % (recommended - the DW01 cuts at 2.4 V, lower than you want for cell life) |

## Other pins on the board

| GPIO | Function |
|---|---|
| 34 | VBUS present (1 = USB plugged in). Usable for a "charging" preset via a small usermod; unused by stock WLED |
| 25, 26, 32, 33 | free on the expansion header J4 (IR receiver on 25 is a common addition) |
| 0, 1, 3, EN | BOOT / UART / RESET - do not reassign |

## Recommended presets

* "Lamp": solid warm white via the W channel, 70 % -> about 0.8 A, 5 h on two 3500 mAh cells.
* "Cosy": Candle Multi, 30 % -> ~12 h.
* "Night": solid 2200 K, 8 %, auto-off 30 min.
