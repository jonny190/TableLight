#!/usr/bin/env python3
"""
TableLight controller PCB - circuit definition (single source of truth).

Written with SKiDL so the same Python object graph produces:
  * tablelight.net      KiCad netlist -> pcbnew: File > Import Netlist (footprints pre-assigned)
  * bom_pcb.csv         PCB bill of materials
  * SCHEMATIC.md        human readable schematic: every net and every pin it touches

    pip install skidl        (plus: rich simp_sexp ply)
    python3 hardware/pcb/tablelight_netlist.py

Design summary
--------------
1S Li-ion (1 or 2 x 18650 in PARALLEL) -> protected pack (DW01A + FS8205A)
USB-C 5 V in (5.1k CC pull-downs, works with C-C cables) -> TP4056 1 A charger
Load sharing: Schottky from VBUS to VSYS, P-FET (AO4407A) from pack to VSYS
   -> LEDs/ESP run from USB while charging; the charger sees only the cell.
VSYS -> MT3608 boost -> +5V (LED rail for the 24 (+16) LED rings, WLED current limit 1.2 A)
        -> AO3401A high-side switch -> VLED  (WLED "relay pin" GPIO16, true off)
VSYS -> AP2112K-3.3 LDO (EN = slide switch) -> 3V3 for the ESP32-WROOM-32E
USB data -> CH340C (3.3 V mode) -> UART0 with DTR/RTS auto-reset -> flash WLED over the same USB-C
74AHCT1G125 level shifter 3.3 -> 5 V for the LED data line (OE tied to the LED power switch)
ESP32 native capacitive touch on GPIO4 (T0) -> copper pad under the white head plate
Battery voltage divider -> GPIO35 for the WLED Battery usermod; VBUS detect -> GPIO34
"""
import csv
import logging
import os
from collections import defaultdict

from skidl import (ERC, SKIDL, TEMPLATE, KICAD8, Net, Part, Pin, generate_netlist, set_default_tool)

set_default_tool(KICAD8)
HERE = os.path.dirname(os.path.abspath(__file__))


class _DropTagNoise(logging.Filter):
    """SKiDL warns about auto-generated hierarchy tags for every part; irrelevant for a flat netlist."""
    def filter(self, record):
        msg = record.getMessage()
        return not ("tag" in msg and ("Random tag" in msg or "Missing tag" in msg))


for _name in ("skidl", "skidl.erc"):
    logging.getLogger(_name).addFilter(_DropTagNoise())

T = Pin.types
PAS, IN, OUT, PWR, PWO, BI, OC, NC = T.PASSIVE, T.INPUT, T.OUTPUT, T.PWRIN, T.PWROUT, T.BIDIR, T.OPENCOLL, T.NOCONNECT


def tmpl(name, prefix, footprint, pins, **fields):
    """Create a part template with explicit pins (num, name, type)."""
    p = Part(tool=SKIDL, name=name, ref_prefix=prefix, dest=TEMPLATE, footprint=footprint, **fields)
    for num, pname, ptype in pins:
        p += Pin(num=str(num), name=pname, func=ptype)
    return p


# ----------------------------------------------------------------------------
# part templates (footprint names are from the standard KiCad 8 libraries)
# ----------------------------------------------------------------------------
R = tmpl("R", "R", "Resistor_SMD:R_0603_1608Metric", [(1, "1", PAS), (2, "2", PAS)], description="Resistor 0603 1%")
C = tmpl("C", "C", "Capacitor_SMD:C_0603_1608Metric", [(1, "1", PAS), (2, "2", PAS)], description="Capacitor 0603 X7R")
C0805 = tmpl("C", "C", "Capacitor_SMD:C_0805_2012Metric", [(1, "1", PAS), (2, "2", PAS)], description="Capacitor 0805 X5R")
CP = tmpl("C_Polarized", "C", "Capacitor_SMD:CP_Elec_6.3x5.4", [(1, "+", PAS), (2, "-", PAS)], description="Electrolytic / polymer cap SMD 6.3x5.4")
D_SMA = tmpl("D_Schottky", "D", "Diode_SMD:D_SMA", [(1, "K", PAS), (2, "A", PAS)], description="Schottky diode SMA")
LED = tmpl("LED", "D", "LED_SMD:LED_0603_1608Metric", [(1, "K", PAS), (2, "A", PAS)], description="LED 0603")
L = tmpl("L", "L", "Inductor_SMD:L_Bourns_SRN6045", [(1, "1", PAS), (2, "2", PAS)], description="Power inductor 6x6 mm shielded")

ESP32 = tmpl("ESP32-WROOM-32E", "U", "RF_Module:ESP32-WROOM-32E", [
    (1, "GND", PWR), (2, "3V3", PWR), (3, "EN", IN), (4, "SENSOR_VP", IN), (5, "SENSOR_VN", IN),
    (6, "IO34", IN), (7, "IO35", IN), (8, "IO32", BI), (9, "IO33", BI), (10, "IO25", BI),
    (11, "IO26", BI), (12, "IO27", BI), (13, "IO14", BI), (14, "IO12", BI), (15, "GND", PWR),
    (16, "IO13", BI), (17, "NC", NC), (18, "NC", NC), (19, "NC", NC), (20, "NC", NC),
    (21, "NC", NC), (22, "NC", NC), (23, "IO15", BI), (24, "IO2", BI), (25, "IO0", BI),
    (26, "IO4", BI), (27, "IO16", BI), (28, "IO17", BI), (29, "IO5", BI), (30, "IO18", BI),
    (31, "IO19", BI), (32, "NC", NC), (33, "IO21", BI), (34, "RXD0", BI), (35, "TXD0", BI),
    (36, "IO22", BI), (37, "IO23", BI), (38, "GND", PWR), (39, "GND", PWR)],
    description="ESP32-WROOM-32E-N4 WiFi/BT module, 4 MB flash", mpn="ESP32-WROOM-32E-N4")

TP4056 = tmpl("TP4056", "U", "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm", [
    (1, "TEMP", IN), (2, "PROG", PAS), (3, "GND", PWR), (4, "VCC", PWR), (5, "BAT", PWO),
    (6, "STDBY", OC), (7, "CHRG", OC), (8, "CE", IN), (9, "EP", PWR)],
    description="1 A linear Li-ion charger, ESOP-8", mpn="TP4056")

DW01 = tmpl("DW01A", "U", "Package_TO_SOT_SMD:SOT-23-6", [
    (1, "OD", OUT), (2, "CS", IN), (3, "OC", OUT), (4, "TD", IN), (5, "VCC", PWR), (6, "GND", PWR)],
    description="1S Li-ion protection IC", mpn="DW01A-G")

FS8205 = tmpl("FS8205A", "Q", "Package_SO:TSSOP-8_4.4x3mm_P0.65mm", [
    (1, "S1", PAS), (2, "G1", IN), (3, "S2", PAS), (4, "G2", IN), (5, "D2", PAS), (6, "D2", PAS), (7, "D1", PAS), (8, "D1", PAS)],
    description="Dual N-MOSFET common drain, 20 V, 6 A (battery protection)", mpn="FS8205A")

MT3608 = tmpl("MT3608", "U", "Package_TO_SOT_SMD:SOT-23-6", [
    (1, "SW", PAS), (2, "GND", PWR), (3, "FB", IN), (4, "EN", IN), (5, "IN", PWR), (6, "NC", NC)],
    description="Boost converter 2-24 V in, 1.2 MHz, 4 A switch", mpn="MT3608")

AP2112 = tmpl("AP2112K-3.3", "U", "Package_TO_SOT_SMD:SOT-23-5", [
    (1, "VIN", PWR), (2, "GND", PWR), (3, "EN", IN), (4, "NC", NC), (5, "VOUT", PWO)],
    description="LDO 3.3 V 600 mA low dropout", mpn="AP2112K-3.3TRG1")

CH340 = tmpl("CH340C", "U", "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", [
    (1, "GND", PWR), (2, "TXD", OUT), (3, "RXD", IN), (4, "V3", PWR), (5, "UD+", BI), (6, "UD-", BI),
    (7, "XI", NC), (8, "XO", NC), (9, "CTS#", IN), (10, "DSR#", IN), (11, "RI#", IN), (12, "DCD#", IN),
    (13, "DTR#", OUT), (14, "RTS#", OUT), (15, "R232", IN), (16, "VCC", PWR)],
    description="USB-UART bridge, internal oscillator", mpn="CH340C")

AHCT125 = tmpl("74AHCT1G125", "U", "Package_TO_SOT_SMD:SOT-23-5", [
    (1, "OE#", IN), (2, "A", IN), (3, "GND", PWR), (4, "Y", OUT), (5, "VCC", PWR)],
    description="Single bus buffer, 3.3->5 V level shift for LED data", mpn="SN74AHCT1G125DBVR")

USBLC6 = tmpl("USBLC6-2SC6", "U", "Package_TO_SOT_SMD:SOT-23-6", [
    (1, "IO1", PAS), (2, "GND", PWR), (3, "IO2", PAS), (4, "IO2", PAS), (5, "VBUS", PWR), (6, "IO1", PAS)],
    description="USB ESD protection (optional)", mpn="USBLC6-2SC6")

PFET8 = tmpl("Q_PMOS_SOIC8", "Q", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", [
    (1, "S", PAS), (2, "S", PAS), (3, "S", PAS), (4, "G", IN), (5, "D", PAS), (6, "D", PAS), (7, "D", PAS), (8, "D", PAS)],
    description="P-MOSFET -30 V 12 A 12 mOhm (load sharing)", mpn="AO4407A")
PFET = tmpl("Q_PMOS_SOT23", "Q", "Package_TO_SOT_SMD:SOT-23", [(1, "G", IN), (2, "S", PAS), (3, "D", PAS)],
            description="P-MOSFET -30 V 4 A (LED rail switch)", mpn="AO3401A")
NFET = tmpl("Q_NMOS_SOT23", "Q", "Package_TO_SOT_SMD:SOT-23", [(1, "G", IN), (2, "S", PAS), (3, "D", PAS)],
            description="N-MOSFET 60 V 300 mA", mpn="2N7002")
NPN = tmpl("Q_NPN_SOT23", "Q", "Package_TO_SOT_SMD:SOT-23", [(1, "B", IN), (2, "E", PAS), (3, "C", PAS)],
           description="NPN transistor (auto-reset)", mpn="MMBT3904")

USBC = tmpl("USB_C_Receptacle_16P", "J", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", [
    ("A1", "GND", PWR), ("A4", "VBUS", PWR), ("A5", "CC1", BI), ("A6", "D+", BI), ("A7", "D-", BI), ("A8", "SBU1", NC),
    ("A9", "VBUS", PWR), ("A12", "GND", PWR), ("B1", "GND", PWR), ("B4", "VBUS", PWR), ("B5", "CC2", BI),
    ("B6", "D+", BI), ("B7", "D-", BI), ("B8", "SBU2", NC), ("B9", "VBUS", PWR), ("B12", "GND", PWR), ("S1", "SHIELD", PAS)],
    description="USB-C receptacle 16 pin, top mount", mpn="HRO TYPE-C-31-M-12")
JST3 = tmpl("Conn_JST_PH_3", "J", "Connector_JST:JST_PH_B3B-PH-K_1x03_P2.00mm_Vertical", [(1, "1", PAS), (2, "2", PAS), (3, "3", PAS)],
            description="JST PH 2.0 mm 3 pin", mpn="B3B-PH-K-S")
JST2 = tmpl("Conn_JST_PH_2", "J", "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", [(1, "1", PAS), (2, "2", PAS)],
            description="JST PH 2.0 mm 2 pin", mpn="B2B-PH-K-S")
HDR6 = tmpl("Conn_01x06", "J", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
            [(i, str(i), PAS) for i in range(1, 7)], description="Pin header 1x6 2.54 mm (expansion)", mpn="generic")
BATT = tmpl("BatteryHolder_18650", "BT", "Battery:BatteryHolder_Keystone_1042_1x18650", [(1, "+", PAS), (2, "-", PAS)],
            description="18650 PCB-mount holder", mpn="Keystone 1042 (or BH-18650-PC equiv.)")
SW_SLIDE = tmpl("SW_SPDT_Slide", "SW", "Button_Switch_THT:SW_Slide_1P2T_CK_OS102011MA1Q", [(1, "1", PAS), (2, "COM", PAS), (3, "3", PAS)],
                description="Slide switch SPDT right-angle THT (power)", mpn="C&K OS102011MA1QN1")
SW_TACT = tmpl("SW_Push", "SW", "Button_Switch_SMD:SW_SPST_TL3342", [(1, "1", PAS), (2, "2", PAS)],
               description="Tactile switch 3x6x2.5 mm SMD", mpn="TL3342 / TS-1187A")
MH = tmpl("MountingHole", "H", "MountingHole:MountingHole_3.2mm_M3", [], description="M3 mounting hole (r=45 mm, 45/135/225/315 deg)", mpn="-")

# ----------------------------------------------------------------------------
# nets
# ----------------------------------------------------------------------------
GND = Net("GND")
VBUS = Net("VBUS")
BATP = Net("BAT+")           # cell(s) positive == protected pack positive
CELLN = Net("CELL-")         # raw cell negative (before protection FETs)
FETD = Net("PROT_FET_D")     # common drain node of FS8205A
VSYS = Net("VSYS")           # load-shared rail: VBUS-0.4 V when USB present, else pack
V5 = Net("+5V")              # boost output
VLED = Net("VLED")           # switched LED rail
V3 = Net("3V3")
CC1, CC2 = Net("CC1"), Net("CC2")
DP, DM = Net("USB_D+"), Net("USB_D-")
CHRG, STDBY = Net("CHRG"), Net("STDBY")
DW_VCC, DW_CS = Net("DW01_VCC"), Net("DW01_CS")
OD, OC_ = Net("DW01_OD"), Net("DW01_OC")
SWN, FB = Net("BOOST_SW"), Net("BOOST_FB")
LED_EN = Net("LED_EN")       # GPIO16 (WLED relay pin, active high)
nLED_EN = Net("nLED_EN")     # gate of the LED P-FET / OE# of level shifter
LED_DATA = Net("LED_DATA")   # GPIO2, 3.3 V
LED_DATA5 = Net("LED_DATA_5V")
LED_OUT = Net("LED_DOUT")
TOUCH = Net("TOUCH")         # GPIO4 / T0
TOUCH_PAD = Net("TOUCH_PAD")
VBAT_S, VBUS_D = Net("VBAT_SENSE"), Net("VBUS_DET")
EN, IO0 = Net("EN"), Net("IO0")
TX, RX = Net("U0TXD"), Net("U0RXD")   # named from the ESP32 side
DTR, RTS = Net("DTR"), Net("RTS")
DTR_B, RTS_B = Net("DTR_B"), Net("RTS_B")
SYS_EN = Net("SYS_EN")
IO25, IO26, IO32, IO33 = Net("IO25"), Net("IO26"), Net("IO32"), Net("IO33")

# ----------------------------------------------------------------------------
# USB-C input, ESD, charger, status LEDs
# ----------------------------------------------------------------------------
J1 = USBC(ref="J1", value="USB-C 16P")
GND += J1["A1"], J1["A12"], J1["B1"], J1["B12"], J1["S1"]
VBUS += J1["A4"], J1["A9"], J1["B4"], J1["B9"]
CC1 += J1["A5"]; CC2 += J1["B5"]
DP += J1["A6"], J1["B6"]; DM += J1["A7"], J1["B7"]
R1 = R(ref="R1", value="5.1k", remark="CC1 Rd -> sink advertises 5 V device"); CC1 += R1[1]; GND += R1[2]
R2 = R(ref="R2", value="5.1k", remark="CC2 Rd"); CC2 += R2[1]; GND += R2[2]
U8 = USBLC6(ref="U8", value="USBLC6-2SC6", remark="optional ESD protection")
DP += U8[1], U8[6]; DM += U8[3], U8[4]; VBUS += U8[5]; GND += U8[2]

U2 = TP4056(ref="U2", value="TP4056")
VBUS += U2["VCC"], U2["CE"]
GND += U2["GND"], U2["EP"], U2["TEMP"]
BATP += U2["BAT"]
R3 = R(ref="R3", value="1.2k", remark="PROG: 1.2k = 1.0 A charge; use 2k for 0.58 A (weak USB ports)"); U2["PROG"] += R3[1]; GND += R3[2]
C1 = C0805(ref="C1", value="10uF 10V"); VBUS += C1[1]; GND += C1[2]
C2 = C0805(ref="C2", value="10uF 10V"); BATP += C2[1]; GND += C2[2]
D3 = LED(ref="D3", value="RED", remark="CHRG: on while charging"); CHRG += D3["K"]
D4 = LED(ref="D4", value="GREEN", remark="STDBY: on when charge complete"); STDBY += D4["K"]
R4 = R(ref="R4", value="1k"); VBUS += R4[1]; D3["A"] += R4[2]
R5 = R(ref="R5", value="1k"); VBUS += R5[1]; D4["A"] += R5[2]
CHRG += U2["CHRG"]; STDBY += U2["STDBY"]

# ----------------------------------------------------------------------------
# battery pack: 2 x 18650 in parallel (fit 1 or 2) + DW01A/FS8205A protection
# ----------------------------------------------------------------------------
BT1 = BATT(ref="BT1", value="18650"); BT2 = BATT(ref="BT2", value="18650 (optional 2nd cell)")
J5 = JST2(ref="J5", value="BAT ALT", remark="alternative: wire-lead holder / pouch cell, parallel to BT1/BT2")
for b in (BT1, BT2):
    BATP += b["+"]; CELLN += b["-"]
BATP += J5[1]; CELLN += J5[2]

U3 = DW01(ref="U3", value="DW01A")
Q1 = FS8205(ref="Q1", value="FS8205A")
R6 = R(ref="R6", value="100R", remark="DW01 VCC filter"); BATP += R6[1]; DW_VCC += R6[2], U3["VCC"]
C3 = C(ref="C3", value="100nF"); DW_VCC += C3[1]; CELLN += C3[2]
CELLN += U3["GND"], U3["TD"], Q1["S1"]
R7 = R(ref="R7", value="1k", remark="DW01 CS sense"); GND += R7[1]; DW_CS += R7[2], U3["CS"]
OD += U3["OD"], Q1["G1"]          # discharge FET (source at CELL-)
OC_ += U3["OC"], Q1["G2"]         # charge FET (source at GND)
GND += Q1["S2"]
FETD += Q1[5], Q1[6], Q1[7], Q1[8]

# ----------------------------------------------------------------------------
# load sharing: VBUS -> D1 -> VSYS ; BAT+ -> Q2 (P-FET, gate = VBUS) -> VSYS
# ----------------------------------------------------------------------------
D1 = D_SMA(ref="D1", value="SS34", remark="USB -> VSYS"); VBUS += D1["A"]; VSYS += D1["K"]
Q2 = PFET8(ref="Q2", value="AO4407A", remark="load-share P-FET; off while USB present")
BATP += Q2[5], Q2[6], Q2[7], Q2[8]
VSYS += Q2[1], Q2[2], Q2[3]
VBUS += Q2["G"]
R8 = R(ref="R8", value="100k", remark="VBUS bleed / Q2 gate pull-down"); VBUS += R8[1]; GND += R8[2]

# ----------------------------------------------------------------------------
# boost VSYS -> +5V (MT3608, 5.1 V) and switched LED rail
# ----------------------------------------------------------------------------
U4 = MT3608(ref="U4", value="MT3608")
VSYS += U4["IN"]; GND += U4["GND"]
L1 = L(ref="L1", value="4.7uH 4A", remark="e.g. Bourns SRN6045TA-4R7Y or any 6x6 shielded, Isat >= 4 A"); VSYS += L1[1]; SWN += L1[2], U4["SW"]
D2 = D_SMA(ref="D2", value="SS34"); SWN += D2["A"]; V5 += D2["K"]
R9 = R(ref="R9", value="75k", remark="FB divider: Vout = 0.6*(1+75/10) = 5.1 V"); V5 += R9[1]; FB += R9[2], U4["FB"]
R10 = R(ref="R10", value="10k"); FB += R10[1]; GND += R10[2]
for ref in ("C4", "C5"):
    c = C0805(ref=ref, value="22uF 10V"); VSYS += c[1]; GND += c[2]
for ref in ("C6", "C7"):
    c = C0805(ref=ref, value="22uF 10V"); V5 += c[1]; GND += c[2]
LED_EN += U4["EN"]

Q3 = PFET(ref="Q3", value="AO3401A", remark="LED rail switch"); V5 += Q3["S"]; VLED += Q3["D"]; nLED_EN += Q3["G"]
R12 = R(ref="R12", value="10k", remark="Q3 gate pull-up"); V5 += R12[1]; nLED_EN += R12[2]
Q4 = NFET(ref="Q4", value="2N7002", remark="inverts LED_EN for Q3"); LED_EN += Q4["G"]; GND += Q4["S"]; nLED_EN += Q4["D"]
R11 = R(ref="R11", value="100k", remark="LED_EN pull-down: LEDs off during boot"); LED_EN += R11[1]; GND += R11[2]
C8 = CP(ref="C8", value="100uF 6.3V", remark="LED rail bulk"); VLED += C8["+"]; GND += C8["-"]

# ----------------------------------------------------------------------------
# 3.3 V LDO + power switch
# ----------------------------------------------------------------------------
U5 = AP2112(ref="U5", value="AP2112K-3.3")
VSYS += U5["VIN"]; GND += U5["GND"]; V3 += U5["VOUT"]; SYS_EN += U5["EN"]
C9 = C(ref="C9", value="1uF"); VSYS += C9[1]; GND += C9[2]
C10 = C0805(ref="C10", value="10uF 10V"); V3 += C10[1]; GND += C10[2]
SW1 = SW_SLIDE(ref="SW1", value="POWER", remark="ON = SYS_EN high; only switches the LDO enable (tiny current)")
SYS_EN += SW1["COM"]; VSYS += SW1[1]; GND += SW1[3]

# ----------------------------------------------------------------------------
# ESP32 + decoupling + buttons + touch + sensing + expansion
# ----------------------------------------------------------------------------
U1 = ESP32(ref="U1", value="ESP32-WROOM-32E-N4")
GND += U1[1], U1[15], U1[38], U1[39]
V3 += U1["3V3"]
C11 = C(ref="C11", value="100nF"); V3 += C11[1]; GND += C11[2]
C12 = C0805(ref="C12", value="10uF 10V"); V3 += C12[1]; GND += C12[2]
EN += U1["EN"]; IO0 += U1["IO0"]
R18 = R(ref="R18", value="10k"); V3 += R18[1]; EN += R18[2]
C13 = C(ref="C13", value="1uF", remark="EN reset delay"); EN += C13[1]; GND += C13[2]
R19 = R(ref="R19", value="10k"); V3 += R19[1]; IO0 += R19[2]
SW2 = SW_TACT(ref="SW2", value="RESET"); EN += SW2[1]; GND += SW2[2]
SW3 = SW_TACT(ref="SW3", value="BOOT"); IO0 += SW3[1]; GND += SW3[2]

LED_DATA += U1["IO2"]
LED_EN += U1["IO16"]
TOUCH += U1["IO4"]
VBAT_S += U1["IO35"]
VBUS_D += U1["IO34"]
TX += U1["TXD0"]; RX += U1["RXD0"]
IO25 += U1["IO25"]; IO26 += U1["IO26"]; IO32 += U1["IO32"]; IO33 += U1["IO33"]
# unused module pins left open (SKiDL NC marker)
for pn in (4, 5, 12, 13, 14, 16, 23, 28, 29, 30, 31, 33, 36, 37):
    U1[pn] += Net.fetch("NC_" + str(pn))  # explicit no-connect stubs (dropped by ERC as single-pin nets)

R22 = R(ref="R22", value="1k", remark="touch series / ESD; 0R also fine"); TOUCH += R22[1]; TOUCH_PAD += R22[2]
J3 = JST2(ref="J3", value="TOUCH", remark="1 = pad, 2 = GND (optional shield)"); TOUCH_PAD += J3[1]; GND += J3[2]

R14 = R(ref="R14", value="100k", remark="VBAT divider top (x2.0 in WLED battery usermod)"); BATP += R14[1]; VBAT_S += R14[2]
R15 = R(ref="R15", value="100k"); VBAT_S += R15[1]; GND += R15[2]
C16 = C(ref="C16", value="100nF"); VBAT_S += C16[1]; GND += C16[2]
R16 = R(ref="R16", value="100k", remark="VBUS present detect"); VBUS += R16[1]; VBUS_D += R16[2]
R17 = R(ref="R17", value="100k"); VBUS_D += R17[1]; GND += R17[2]
C17 = C(ref="C17", value="100nF"); VBUS_D += C17[1]; GND += C17[2]

J4 = HDR6(ref="J4", value="EXP", remark="3V3 GND IO25 IO26 IO32 IO33 (IR receiver, extra buttons, sensors)")
V3 += J4[1]; GND += J4[2]; IO25 += J4[3]; IO26 += J4[4]; IO32 += J4[5]; IO33 += J4[6]

# ----------------------------------------------------------------------------
# LED data level shift + LED connector
# ----------------------------------------------------------------------------
U7 = AHCT125(ref="U7", value="74AHCT1G125")
V5 += U7["VCC"]; GND += U7["GND"]; LED_DATA += U7["A"]; LED_DATA5 += U7["Y"]; nLED_EN += U7["OE#"]
C15 = C(ref="C15", value="100nF"); V5 += C15[1]; GND += C15[2]
R13 = R(ref="R13", value="330R", remark="LED data series termination"); LED_DATA5 += R13[1]; LED_OUT += R13[2]
J2 = JST3(ref="J2", value="LED RING", remark="1 = VLED (+5V), 2 = GND, 3 = DATA -> LED ring(s) in the head, via the stem"); VLED += J2[1]; GND += J2[2]; LED_OUT += J2[3]

# ----------------------------------------------------------------------------
# USB-UART (CH340C at 3.3 V) + auto-reset
# ----------------------------------------------------------------------------
U6 = CH340(ref="U6", value="CH340C")
V3 += U6["VCC"], U6["V3"]        # V3 tied to VCC => 3.3 V operation
GND += U6["GND"], U6["R232"]
DP += U6["UD+"]; DM += U6["UD-"]
RX += U6["TXD"]                  # CH340 TXD -> ESP RXD0
TX += U6["RXD"]                  # ESP TXD0 -> CH340 RXD
DTR += U6["DTR#"]; RTS += U6["RTS#"]
C14 = C(ref="C14", value="100nF"); V3 += C14[1]; GND += C14[2]
R20 = R(ref="R20", value="12k"); DTR += R20[1]; DTR_B += R20[2]
R21 = R(ref="R21", value="12k"); RTS += R21[1]; RTS_B += R21[2]
Q5 = NPN(ref="Q5", value="MMBT3904", remark="auto-reset: EN"); DTR_B += Q5["B"]; RTS += Q5["E"]; EN += Q5["C"]
Q6 = NPN(ref="Q6", value="MMBT3904", remark="auto-reset: IO0"); RTS_B += Q6["B"]; DTR += Q6["E"]; IO0 += Q6["C"]

# mounting holes (match the enclosure bosses)
for i in range(1, 5):
    MH(ref=f"H{i}", value="M3")


# ----------------------------------------------------------------------------
# outputs
# ----------------------------------------------------------------------------
default_circuit = U1.circuit   # the implicit circuit every part above was added to


def write_bom(path):
    groups = defaultdict(list)
    for p in default_circuit.parts:
        key = (p.value, getattr(p, "footprint", ""), getattr(p, "mpn", ""), getattr(p, "description", ""))
        groups[key].append(p)
    rows = []
    for (val, fp, mpn, desc), parts in groups.items():
        refs = sorted((p.ref for p in parts), key=lambda r: (r.rstrip("0123456789"), int("".join(ch for ch in r if ch.isdigit()) or 0)))
        notes = "; ".join(sorted({getattr(p, "remark", "") for p in parts if getattr(p, "remark", "")}))
        rows.append([", ".join(refs), len(parts), val, desc, mpn, fp.split(":")[-1], notes])
    rows.sort(key=lambda r: (r[0].split(",")[0].rstrip("0123456789"), int("".join(ch for ch in r[0].split(",")[0] if ch.isdigit()) or 0)))
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Refs", "Qty", "Value", "Description", "MPN / example part", "Footprint", "Notes"])
        w.writerows(rows)
    return rows


def write_schematic_md(path, bom_rows):
    def pinlabel(pin):
        return f"{pin.part.ref}.{pin.num}" + (f" ({pin.name})" if pin.name not in (pin.num, "1", "2") else "")

    nets = sorted((n for n in default_circuit.nets if len(n.pins) > 1 and not n.name.startswith("NC_")),
                  key=lambda n: (-len(n.pins), n.name))
    with open(path, "w") as f:
        f.write("# TableLight controller PCB - schematic (net list form)\n\n")
        f.write("Generated by `tablelight_netlist.py`. The block diagram is in `../../docs/images/block_diagram.svg`; "
                "the design rationale is in `README.md` next to this file. Import `tablelight.net` into KiCad pcbnew "
                "(File > Import Netlist) to get all footprints with ratsnest, then lay the board out on `outline.dxf`.\n\n")
        f.write("## Nets\n\n| Net | Pins | Connected pins |\n|---|---|---|\n")
        for n in nets:
            pins = sorted(n.pins, key=lambda p: (p.part.ref.rstrip("0123456789"), int("".join(ch for ch in p.part.ref if ch.isdigit()) or 0), str(p.num)))
            f.write(f"| `{n.name}` | {len(pins)} | " + ", ".join(pinlabel(p) for p in pins) + " |\n")
        f.write("\n## Components\n\n| Refs | Qty | Value | Description | MPN / example | Footprint | Notes |\n|---|---|---|---|---|---|---|\n")
        for r in bom_rows:
            f.write("| " + " | ".join(str(x) for x in r) + " |\n")
        f.write("\n## Per-component pin connections\n\n")
        parts = sorted(default_circuit.parts, key=lambda p: (p.ref.rstrip("0123456789"), int("".join(ch for ch in p.ref if ch.isdigit()) or 0)))
        for p in parts:
            if not p.pins:
                continue
            f.write(f"### {p.ref} - {p.value} ({getattr(p, 'description', '')})\n\n| Pin | Name | Net |\n|---|---|---|\n")
            for pin in sorted(p.pins, key=lambda q: (len(str(q.num)), str(q.num))):
                netname = pin.net.name if pin.net is not None else "-"
                if netname.startswith("NC_"):
                    netname = "(no connect)"
                f.write(f"| {pin.num} | {pin.name} | `{netname}` |\n")
            f.write("\n")


if __name__ == "__main__":
    ERC()
    generate_netlist(file_=os.path.join(HERE, "tablelight.net"))
    rows = write_bom(os.path.join(HERE, "bom_pcb.csv"))
    write_schematic_md(os.path.join(HERE, "SCHEMATIC.md"), rows)
    n_parts = len([p for p in default_circuit.parts])
    n_nets = len([n for n in default_circuit.nets if len(n.pins) > 1])
    print(f"parts={n_parts} nets={n_nets} -> tablelight.net, bom_pcb.csv, SCHEMATIC.md")
