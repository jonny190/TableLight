#!/usr/bin/env python3
"""
TableLight PCB - board outline + placement constraints, derived from the enclosure CAD.

Reads the parameters of cad/tablelight.py so the PCB and the printed base can never drift apart.

Outputs (in this directory):
  outline.dxf      Edge.Cuts geometry (Ø100 board + Ø10 wire cut-out) and reference layers -> KiCad: File > Import > Graphics
  placement.svg/.png   placement drawing with keep-outs, connector positions and orientation
  PLACEMENT.md     the same numbers as a table, in KiCad coordinates (origin = board centre, Y down)

All drawings are viewed FROM THE COMPONENT SIDE.  In the lamp the component side faces DOWN,
so this view is the mirror image of the lamp seen from above (X is flipped).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "cad"))
import tablelight as cad  # noqa: E402

P, D = cad.P, cad.D


def lamp_to_view(x, y):
    """lamp top-view coords -> component-side view coords (mirror X)."""
    return (-x, y)


def lamp_angle_to_view(a):
    return 180.0 - a


def polar(r, deg):
    return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))


# ----------------------------------------------------------------------------
# geometry (component-side view, Y up, mm, origin = board centre)
# ----------------------------------------------------------------------------
R = P["pcb_r"]
holes = [polar(P["pcb_hole_r"], 45 + 90 * k) for k in range(4)]
slot_w, slot_h = P["pcb_slot"]          # centre wire slot (X x Y), under the stem bore
boss_keepouts = [polar(P["plate_boss_r"], lamp_angle_to_view(P["plate_boss_start_deg"] + 90 * k)) for k in range(4)]
boss_keepout_r = P["plate_boss_d"] / 2 + 1.0
usb_face_y = -(R + 1.0)            # receptacle face overhangs the board edge by 1 mm
usb_w, usb_depth = 8.94, 7.35
usb_body = (-usb_w / 2, usb_face_y, usb_w, usb_depth)      # x, y, w, h
sw_angle_v = lamp_angle_to_view(P["sw_angle"])
sw_pos = polar(R - 4.5, sw_angle_v)
led_pos = [polar(R - 3.0, lamp_angle_to_view(a)) for a in P["led_angles"]]
esp_w, esp_h = 18.0, 25.5
esp_ant_h = 6.0                    # antenna zone at the +Y end of the module: no copper on any layer
holder_l, holder_w = 87.6, 21.7      # Keystone 1042 footprint bounding box
holder_gap = slot_h + 2.0               # holders straddle the wire slot with 1 mm margin each side
holder_centers = [(0.0, holder_gap / 2 + holder_w / 2), (0.0, -(holder_gap / 2 + holder_w / 2))]
esp_center = (0.0, holder_centers[0][1] + holder_w / 2 + 0.5 + esp_h / 2)
j23_pos = [(-22.0, -29.0), (22.0, -29.0)]  # LED ring / touch connectors (wires run to the centre slot along the holder edge)

max_part_h = D["max_component_h"]
boss_zone_h = D["plate_boss_keepout_h"]


def write_dxf(path):
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.layers.add("Edge.Cuts", color=1)
    doc.layers.add("Ref.Holes", color=3)
    doc.layers.add("Placement", color=5)
    doc.layers.add("Keepout", color=6)
    msp = doc.modelspace()
    msp.add_circle((0, 0), R, dxfattribs={"layer": "Edge.Cuts"})
    hw, hh = slot_w / 2 - slot_h / 2, slot_h / 2     # rounded slot: two arcs + two lines
    msp.add_line((-hw, hh), (hw, hh), dxfattribs={"layer": "Edge.Cuts"})
    msp.add_line((-hw, -hh), (hw, -hh), dxfattribs={"layer": "Edge.Cuts"})
    msp.add_arc((hw, 0), hh, -90, 90, dxfattribs={"layer": "Edge.Cuts"})
    msp.add_arc((-hw, 0), hh, 90, 270, dxfattribs={"layer": "Edge.Cuts"})
    for (x, y) in holes:
        msp.add_circle((x, y), P["pcb_hole_d"] / 2, dxfattribs={"layer": "Ref.Holes"})
    for (x, y) in boss_keepouts:
        msp.add_circle((x, y), boss_keepout_r, dxfattribs={"layer": "Keepout"})
    x, y, w, h = usb_body
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": "Placement"})
    cx, cy = esp_center
    msp.add_lwpolyline([(cx - esp_w / 2, cy - esp_h / 2), (cx + esp_w / 2, cy - esp_h / 2), (cx + esp_w / 2, cy + esp_h / 2), (cx - esp_w / 2, cy + esp_h / 2)],
                       close=True, dxfattribs={"layer": "Placement"})
    ay = cy + esp_h / 2 - esp_ant_h
    msp.add_lwpolyline([(cx - esp_w / 2, ay), (cx + esp_w / 2, ay), (cx + esp_w / 2, cy + esp_h / 2), (cx - esp_w / 2, cy + esp_h / 2)],
                       close=True, dxfattribs={"layer": "Keepout"})
    for (hx, hy) in holder_centers:
        msp.add_lwpolyline([(hx - holder_l / 2, hy - holder_w / 2), (hx + holder_l / 2, hy - holder_w / 2),
                            (hx + holder_l / 2, hy + holder_w / 2), (hx - holder_l / 2, hy + holder_w / 2)],
                           close=True, dxfattribs={"layer": "Placement"})
    msp.add_circle(sw_pos, 2.0, dxfattribs={"layer": "Placement"})
    for (lx, ly) in led_pos:
        msp.add_circle((lx, ly), 1.0, dxfattribs={"layer": "Placement"})
    doc.saveas(path)


def write_placement_drawing(svg_path, png_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle, Wedge

    fig, ax = plt.subplots(figsize=(9, 9), dpi=120)
    ax.add_patch(Circle((0, 0), R, fill=False, lw=2, ec="#222"))
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((-slot_w / 2 + slot_h / 2, -slot_h / 2 + slot_h / 2), slot_w - slot_h, 0.001,
                                boxstyle="round,pad=%.2f" % (slot_h / 2), fill=False, lw=1.5, ec="#222"))
    ax.annotate("wire slot %.0f x %.0f\n(LED ring + touch wires\ndown the stem)" % (slot_w, slot_h), (slot_w / 2, 0), (0, -60), ha="center", va="top", fontsize=8,
                arrowprops=dict(arrowstyle="-", lw=0.6, connectionstyle="arc3,rad=0.3"))
    for (x, y) in holes:
        ax.add_patch(Circle((x, y), P["pcb_hole_d"] / 2, fill=False, lw=1.2, ec="#222"))
        ax.add_patch(Circle((x, y), P["pcb_boss_d"] / 2, fill=False, lw=0.6, ls="--", ec="#888"))
    ax.text(holes[0][0] + 5, holes[0][1] + 6, "H1-H4: M3, r = %.0f mm\n(dashed = deck boss Ø%.1f)" % (P["pcb_hole_r"], P["pcb_boss_d"]), fontsize=8)
    for (x, y) in boss_keepouts:
        ax.add_patch(Circle((x, y), boss_keepout_r, color="#e06666", alpha=0.35, lw=0))
    ax.text(-64, 58, "red: bottom-plate bosses -\nno parts taller than %.0f mm" % boss_zone_h, fontsize=8, color="#a33", ha="left", va="top")
    # USB
    x, y, w, h = usb_body
    ax.add_patch(Rectangle((x, y), w, h, color="#4a86e8", alpha=0.6))
    ax.text(0, y + h + 1.5, "J1 USB-C\n(face overhangs edge 1 mm)", ha="center", va="bottom", fontsize=8)
    # ESP32
    cx, cy = esp_center
    ax.add_patch(Rectangle((cx - esp_w / 2, cy - esp_h / 2), esp_w, esp_h, color="#6aa84f", alpha=0.5))
    ax.add_patch(Rectangle((cx - esp_w / 2, cy + esp_h / 2 - esp_ant_h), esp_w, esp_ant_h, color="#e06666", alpha=0.35, lw=0))
    ax.text(cx, cy - 2, "U1 ESP32-\nWROOM-32E", ha="center", va="center", fontsize=8)
    ax.text(cx - esp_w / 2 - 1, cy + esp_h / 2 - 3, "antenna -> board edge\nno copper under it", fontsize=7, va="center", ha="right")
    # holders
    for i, (hx, hy) in enumerate(holder_centers):
        ax.add_patch(Rectangle((hx - holder_l / 2, hy - holder_w / 2), holder_l, holder_w, color="#f1c232", alpha=0.45))
        ax.text(hx, hy, "BT%d  18650 holder (Keystone 1042)%s" % (i + 1, "" if i == 0 else "  - optional 2nd cell"), ha="center", va="center", fontsize=8)
        ax.text(hx - holder_l / 2 + 3, hy, "+", ha="center", va="center", fontsize=12, weight="bold")
        ax.text(hx + holder_l / 2 - 3, hy, "-", ha="center", va="center", fontsize=12, weight="bold")
    # switch, LEDs
    ax.add_patch(Circle(sw_pos, 2.2, color="#999"))
    ax.annotate("SW1 power slide switch\nactuator points outward", sw_pos, (-42, -60), fontsize=8, ha="center", arrowprops=dict(arrowstyle="-", lw=0.6))
    for (lx, ly), lab in zip(led_pos, ("D3 CHRG", "D4 STDBY")):
        ax.add_patch(Circle((lx, ly), 1.0, color="#c00"))
    ax.annotate("D3/D4 charge LEDs\n(behind Ø2.5 light holes)", led_pos[1], (40, -60), fontsize=8, ha="center",
                arrowprops=dict(arrowstyle="-", lw=0.6))
    for (jx, jy), lab in zip(j23_pos, ("J2 LED\nring", "J3\ntouch")):
        ax.add_patch(Rectangle((jx - 4, jy - 2.5), 8, 5, color="#999", alpha=0.8))
        ax.text(jx, jy, lab, ha="center", va="center", fontsize=7)
    # zones
    zones = [(-30, -40, "charger TP4056\nDW01A + FS8205A\nQ2 load-share"), (30, -40, "boost MT3608\nL1, D2, C4-C7\nQ3/Q4 LED switch"),
             (-40, -29, "U6 CH340C\nSW2/SW3"), (40, -29, "U5 LDO 3V3\nJ4 EXP, J5")]
    for (zx, zy, txt) in zones:
        ax.text(zx, zy, txt, ha="center", va="center", fontsize=7.5, color="#333",
                bbox=dict(boxstyle="round,pad=0.3", fc="#f3f3f3", ec="#bbb", lw=0.6))
    ax.set_xlim(-66, 66); ax.set_ylim(-70, 64)
    ax.set_aspect("equal")
    ax.set_title("TableLight PCB placement constraints (the routed board is kicad/tablelight.kicad_pcb)\nØ%.0f mm, viewed from the COMPONENT side (faces down in the lamp)\n"
                 "max part height %.0f mm (%.0f mm inside red zones); solder side faces the deck, %.0f mm clearance" %
                 (2 * R, max_part_h, boss_zone_h, P["pcb_boss_h"]), fontsize=9)
    ax.set_xlabel("X (mm)  -  mirror of lamp X"); ax.set_ylabel("Y (mm)")
    ax.grid(True, lw=0.3, alpha=0.5)
    fig.tight_layout()
    fig.savefig(svg_path); fig.savefig(png_path)
    plt.close(fig)


def write_placement_md(path):
    def k(pt):
        return f"({pt[0]:+.2f}, {-pt[1]:+.2f})"
    lines = [
        "# TableLight PCB - placement constraints (KiCad coordinates)\n",
        "Origin = board centre. KiCad Y axis points DOWN, so KiCad (x, y) = (x_view, -y_view). Viewed from the component side.\n",
        f"Generated from `cad/tablelight.py` parameters by `board_outline.py`.\n",
        "| Item | KiCad (x, y) mm | Size / notes |", "|---|---|---|",
        f"| Board outline | (0, 0) | circle Ø{2*R:.0f} mm (`outline.dxf`, layer Edge.Cuts) |",
        f"| Wire slot | (0, 0) | {slot_w:.0f} x {slot_h:.0f} mm rounded slot in the board centre (under the Ø{P['deck_wire_hole_d']:.0f} deck hole / stem bore); keep 1 mm copper clearance |",
    ]
    for i, h in enumerate(holes, 1):
        lines.append(f"| H{i} mounting hole | {k(h)} | Ø{P['pcb_hole_d']} mm; deck boss Ø{P['pcb_boss_d']} mm lands on the SOLDER side around it |")
    x, y, w, h = usb_body
    lines.append(f"| J1 USB-C body | {k((0, y + h/2))} | receptacle mating face at y_view = {y:.1f} (1 mm past the edge), pointing -Y |")
    lines.append(f"| SW1 slide switch | {k(sw_pos)} | actuator radially outward at {sw_angle_v:.0f} deg (view); base slot {P['sw_w']}x{P['sw_h']} mm |")
    for (lx, ly), lab in zip(led_pos, ("D3 CHRG", "D4 STDBY")):
        lines.append(f"| {lab} LED | {k((lx, ly))} | at board edge, light hole Ø{P['led_hole_d']} in the base wall |")
    lines.append(f"| U1 ESP32 module | {k(esp_center)} | {esp_w}x{esp_h} mm, antenna toward +Y_view (board edge); antenna zone {esp_ant_h} mm: no copper |")
    lines.append(f"| Stem flange screw heads (solder side) | r = {P['flange_screw_r']} mm at 45/135/225/315 deg | M3 heads sit in the {P['pcb_boss_h']:.0f} mm gap above the board: keep the solder side flat there (no tall THT leads) |")
    for i, hc in enumerate(holder_centers, 1):
        lines.append(f"| BT{i} 18650 holder | {k(hc)} | {holder_l}x{holder_w} mm, long axis along X, '+' (pad 1) toward -X_view |")
    for (jx, jy), lab in zip(j23_pos, ("J2 LED ring", "J3 touch")):
        lines.append(f"| {lab} | {k((jx, jy))} | JST-PH; wires run along the holder edge to the centre slot |")
    for i, b in enumerate(boss_keepouts, 1):
        lines.append(f"| Boss keep-out {i} | {k(b)} | Ø{2*boss_keepout_r:.0f} mm zone: parts taller than {boss_zone_h:.0f} mm not allowed here |")
    lines += ["", f"* Max component height anywhere on the component side: **{max_part_h:.0f} mm** (bottom plate is {abs(D['plate_top_z'] - D['pcb_comp_z']):.1f} mm below the component face).",
              f"* Solder side: {P['pcb_boss_h']:.0f} mm clearance to the deck. Keep THT pins trimmed below 3 mm.",
              "* Antenna zone: keep the +Y edge of the module flush with, or overhanging, the board edge and copper-free on all layers.",
              "* Thermals: pour a large copper area (both sides, stitched) under the TP4056 EP and around D1/Q2; the enclosure is closed PLA.",
              "* Battery holders carry up to ~2.5 A: use >= 1.5 mm traces or pours for BAT+, CELL-, GND, VSYS, +5V, VLED."]
    open(path, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    write_dxf(os.path.join(HERE, "outline.dxf"))
    write_placement_drawing(os.path.join(HERE, "placement.svg"), os.path.join(HERE, "..", "..", "docs", "images", "pcb_placement.png"))
    write_placement_md(os.path.join(HERE, "PLACEMENT.md"))
    print("outline.dxf, placement.svg, PLACEMENT.md written")
