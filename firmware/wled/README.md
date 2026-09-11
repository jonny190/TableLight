# WLED firmware notes

* `platformio_override.ini` - drop into a WLED checkout to build the `tablelight` environment with this
  board's pin defaults and the Battery usermod. Verified against the WLED 0.15 build-flag names
  (`DATA_PINS`, `RLYPIN`, `BTNPIN`, `BTNTYPE`, `USERMOD_BATTERY_*`); if a future WLED renames one, the compiler
  will tell you and the equivalent setting can always be made in the web UI (`docs/WLED_SETUP.md`).
* No custom code is required. Everything the lamp does (touch toggle, LED rail switching, 2D effects,
  battery readout) is stock WLED functionality configured for these pins. The LED count default is 24 (one ring); set 40 in the UI if you fit the second ring.
