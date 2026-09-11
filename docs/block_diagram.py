#!/usr/bin/env python3
"""Draws the TableLight electronics block diagram (docs/images/block_diagram.svg + .png)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "images")

fig, ax = plt.subplots(figsize=(14, 8.5), dpi=110)
ax.set_xlim(0, 140); ax.set_ylim(0, 85); ax.axis("off")

COL = {"pwr": "#fde9b0", "ctl": "#cfe2f3", "io": "#d9ead3", "prot": "#f4cccc", "ext": "#eeeeee"}


def block(x, y, w, h, title, sub="", kind="pwr"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=COL[kind], ec="#333", lw=1.2))
    ax.text(x + w / 2, y + h / 2 + (2.2 if sub else 0), title, ha="center", va="center", fontsize=10, weight="bold")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 2.6, sub, ha="center", va="center", fontsize=7.5, color="#333")
    return (x, y, w, h)


def arrow(p, q, label="", color="#222", lw=1.6, style="-|>", ls="-", off=(0, 1.2)):
    ax.annotate("", q, p, arrowprops=dict(arrowstyle=style, color=color, lw=lw, ls=ls, shrinkA=0, shrinkB=0))
    if label:
        mx, my = (p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1]
        ax.text(mx, my, label, fontsize=7.5, ha="center", va="bottom", color=color,
                bbox=dict(fc="white", ec="none", pad=0.4))


def R(b): return (b[0] + b[2], b[1] + b[3] / 2)
def Lf(b): return (b[0], b[1] + b[3] / 2)
def Tp(b): return (b[0] + b[2] / 2, b[1] + b[3])
def Bt(b): return (b[0] + b[2] / 2, b[1])


# --- power chain (top row) ---
usb = block(2, 66, 16, 12, "J1 USB-C", "5 V in + data\n5.1k CC pull-downs", "ext")
chg = block(24, 66, 18, 12, "U2 TP4056", "1 A Li-ion charger\nD3/D4 status LEDs")
pack = block(48, 66, 20, 12, "1S pack", "1 or 2 x 18650\nin PARALLEL (BT1, BT2, J5)", "prot")
prot = block(74, 66, 18, 12, "U3 DW01A\n+ Q1 FS8205A", "OV / UV / OC / short\nprotection", "prot")
share = block(48, 48, 20, 11, "Load sharing", "D1 SS34 (USB->VSYS)\nQ2 AO4407A (BAT->VSYS)")
boost = block(74, 48, 18, 11, "U4 MT3608", "boost -> +5.1 V\nL1 4.7 uH, D2 SS34")
lsw = block(98, 48, 18, 11, "Q3 AO3401A", "LED rail switch\nQ4 2N7002 driver")
strip = block(122, 44, 16, 19, "LED ring(s)", "24-LED ring (+16 opt.)\nSK6812 RGBW / WS2812B\nin the head, 5 V, <= 1.2 A", "io")
ldo = block(74, 30, 18, 11, "U5 AP2112K", "LDO 3.3 V 600 mA\nEN = SW1 power switch")
sw1 = block(48, 30, 20, 11, "SW1 slide switch", "ON: SYS_EN = VSYS\nOFF: ~80 uA total drain", "ext")

arrow(R(usb), Lf(chg), "VBUS")
arrow(R(chg), Lf(pack), "BAT+")
arrow(R(pack), Lf(prot), "CELL-", off=(0, -3.2))
arrow(Bt(chg), (chg[0] + chg[2] / 2, 53.5), "", style="-")
arrow((chg[0] + chg[2] / 2, 53.5), Lf(share), "VBUS")
arrow(Bt(pack), Tp(share), "BAT+")
arrow(R(share), Lf(boost), "VSYS")
arrow(R(boost), Lf(lsw), "+5V")
arrow(R(lsw), (122, 53.5), "VLED")
arrow((66, share[1]), (66, 44), "", style="-")
arrow((66, 44), (71, 44), "", style="-")
arrow((71, 44), (71, 38), "", style="-")
arrow((71, 38), (74, 38), "VSYS", off=(-1, 0.8))
arrow(R(sw1), (74, 33), "SYS_EN", off=(0, -3.2))

# --- control (bottom row) ---
esp = block(48, 6, 30, 16, "U1 ESP32-WROOM-32E", "WLED firmware\nIO2 LED data - IO16 LED_EN - IO4 touch (T0)\nIO35 VBAT sense - IO34 VBUS detect", "ctl")
uart = block(8, 8, 20, 12, "U6 CH340C", "USB-UART @3.3 V\nQ5/Q6 auto-reset (DTR/RTS)\nSW2 RESET, SW3 BOOT", "ctl")
shift = block(98, 8, 18, 11, "U7 74AHCT1G125", "3.3 -> 5 V data\nOE# = LED switch state", "ctl")
touch = block(122, 6, 16, 14, "Touch pad", "Ø18 copper foil under\nthe white head plate (J3)", "io")
sense = block(8, 26, 30, 9, "Sensing", "R14/R15 100k/100k VBAT -> IO35\nR16/R17 100k/100k VBUS -> IO34", "ctl")
exp = block(8, 40, 30, 9, "J4 expansion header", "3V3 GND IO25 IO26 IO32 IO33\n(IR receiver, extra buttons, sensors)", "ext")

arrow(Bt(ldo), (esp[0] + esp[2] / 2 + 8, esp[1] + esp[3]), "3V3")
arrow((4, usb[1]), (4, 16), "", style="-")
ax.text(3.2, 40, "USB D+/D-", fontsize=7.5, rotation=90, ha="right", va="center", bbox=dict(fc="white", ec="none", pad=0.3))
arrow((4, 16), (uart[0], 16), "", style="-|>")
arrow((uart[0] + uart[2], 10), (esp[0], 10), "UART0 / EN / IO0", style="<|-|>")
arrow(R(esp), Lf(shift), "IO2", off=(0, 1.2))
arrow(R(shift), (122, 13.5), "DATA", off=(0, 1.2))
arrow(Tp(shift), Bt(lsw), "nLED_EN", style="-", ls="--", color="#666")
arrow((esp[0] + esp[2] - 6, esp[1] + esp[3]), (esp[0] + esp[2] - 6, 44), "", style="-", color="#666", ls="--")
arrow((esp[0] + esp[2] - 6, 44), (98, 44), "", style="-", color="#666", ls="--")
arrow((98, 44), (107, 44), "IO16 LED_EN -> boost EN + LED switch", style="-", color="#666", ls="--", off=(-12, 1.0))
arrow((107, 44), (107, 48), "", style="-|>", color="#666", ls="--")
arrow((83, 44), (83, 48), "", style="-|>", color="#666", ls="--")
arrow((72, esp[1]), (72, 3), "", style="-"); arrow((72, 3), (130, 3), "IO4 (T0) - capacitive touch", style="-", off=(0, 0.3)); arrow((130, 3), (130, touch[1]), "", style="-|>")
arrow(R(sense), (42, 30.5), "IO35 / IO34", style="-", off=(0, 1.2))
arrow((42, 30.5), (42, 14), "", style="-"); arrow((42, 14), (esp[0], 14), "", style="-|>")
arrow(R(exp), (45, 44.5), "", style="-"); arrow((45, 44.5), (45, 18), "", style="-"); arrow((45, 18), (esp[0], 18), "", style="-|>")

ax.text(70, 82.5, "TableLight - controller PCB block diagram", fontsize=14, weight="bold", ha="center")
ax.text(70, 79.5, "single USB-C for charging AND flashing WLED - 1S Li-ion, 1 or 2 cells - true LED-off via relay pin - ESP32 native capacitive touch",
        fontsize=9, ha="center", color="#444")
fig.savefig(os.path.join(OUT, "block_diagram.svg"), bbox_inches="tight")
fig.savefig(os.path.join(OUT, "block_diagram.png"), bbox_inches="tight", facecolor="white")
print("block_diagram.svg/.png written")
