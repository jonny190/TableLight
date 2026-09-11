#!/usr/bin/env python3
"""
TableLight controller PCB - board generator (KiCad 7 pcbnew Python API).

Builds hardware/pcb/kicad/tablelight.kicad_pcb from:
  * the circuit in tablelight_netlist.py (SKiDL)          -> footprints + nets
  * the enclosure parameters in cad/tablelight.py         -> outline, holes, connector positions
  * the PLACEMENT table below                             -> component positions
then autoroutes with freerouting (Specctra DSN/SES round trip), pours GND on both
layers, runs DRC and exports the PCBWay fabrication package (Gerbers, drill, BOM, CPL).

    python3 hardware/pcb/build_board.py --stage place      # board with footprints + nets, no tracks
    python3 hardware/pcb/build_board.py --stage route      # + freerouting (needs java + freerouting.jar)
    python3 hardware/pcb/build_board.py --stage finish     # + zones, DRC, fab exports  (default: all)

Coordinates: KiCad convention, mm, origin = board centre, +Y DOWN, components on F.Cu.
In the lamp the component side faces DOWN, so this view is the mirror image of the base seen from above.
The USB-C is at +Y here (lamp -Y), the ESP32 antenna at -Y (lamp +Y).
"""
import argparse
import csv
import glob
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile

import pcbnew
from pcbnew import VECTOR2I, FromMM

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "cad"))
sys.path.insert(0, HERE)
import tablelight as cad  # noqa: E402

P, D = cad.P, cad.D
KICAD_DIR = os.path.join(HERE, "kicad")
FAB_DIR = os.path.join(HERE, "fab")
PCB_PATH = os.path.join(KICAD_DIR, "tablelight.kicad_pcb")
FP_LIB_DIR = "/usr/share/kicad/footprints"
FREEROUTING_JAR = os.environ.get("FREEROUTING_JAR", os.path.join(HERE, "tools", "freerouting.jar"))

BOARD_R = P["pcb_r"]
SLOT_W, SLOT_H = P["pcb_slot"]

# net classes -----------------------------------------------------------------
POWER_NETS = {"BAT+", "CELL-", "PROT_FET_D", "VSYS", "+5V", "VLED", "VBUS", "BOOST_SW"}
TRACK_DEFAULT, TRACK_POWER = 0.25, 0.8
CLEARANCE = 0.2
VIA_D, VIA_DRILL = 0.7, 0.35


def mm(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def polar(r, deg):
    return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))


def lamp_angle_to_kicad(a):
    """lamp top-view angle -> KiCad angle (view from component side, Y down):
    mirror X (view) then flip Y (KiCad) == rotate by 180 - a then negate y == angle -(180 - a) ... simplified:"""
    x, y = math.cos(math.radians(a)), math.sin(math.radians(a))
    xv, yv = -x, y          # mirror X: lamp top view -> component-side view
    xk, yk = xv, -yv        # KiCad Y down
    return math.degrees(math.atan2(yk, xk))


# -----------------------------------------------------------------------------
# PLACEMENT  ref -> (x, y, rotation_deg)   [KiCad mm, F.Cu]
# -----------------------------------------------------------------------------
USB_ANG = lamp_angle_to_kicad(P["usb_angle"])          # 90 deg -> +Y
SW_ANG = lamp_angle_to_kicad(P["sw_angle"])
LED_ANGS = [lamp_angle_to_kicad(a) for a in P["led_angles"]]
HOLDER_Y = SLOT_H / 2 + 1.0 + 20.8 / 2                 # 14.4 -> holder courtyards y 3.5 .. 25.3

ESP_Y = -38.0            # footprint origin; module body spans y -53.8 .. -28.2, antenna end at the board edge
USB_Y = 56.0 - 3.7       # mating face 1 mm past the board edge (r = 55)
SW_R = 49.25             # slide switch: pins at this radius, body toward the edge, actuator through the wall slot

PLACEMENT = {
    # --- mounting holes (deck bosses) -------------------------------------------------
    **{f"H{i+1}": (*polar(P["pcb_hole_r"], 45 + 90 * i), 0) for i in range(4)},
    # --- battery holders: long axis along X; pad 1 ('+') toward -X -----------------------
    "BT1": (0, -HOLDER_Y, 0),
    "BT2": (0, HOLDER_Y, 0),
    # --- ESP32 + support (top region, y < -25) -----------------------------------------
    "U1": (0, ESP_Y, 0),
    "C11": (-12.5, -46.0, 90), "C12": (-12.5, -42.5, 90),      # 3V3 decoupling next to pin 2
    "R18": (-12.5, -39.0, 90), "C13": (-12.5, -35.5, 90),      # EN pull-up + RC
    "R19": (12.5, -29.5, 90),                                  # IO0 pull-up (pin 25)
    "R22": (12.5, -33.5, 90),                                  # touch series (pin 26, IO4)
    "R14": (-16.0, -40.0, 90), "R15": (-19.0, -40.0, 90), "C16": (-22.0, -40.0, 90),   # VBAT divider -> IO35 (pin 7)
    "R16": (-16.0, -36.5, 90), "R17": (-19.0, -36.5, 90), "C17": (-22.0, -36.5, 90),   # VBUS detect -> IO34 (pin 6)
    "U5": (20.0, -33.0, 0), "C9": (16.5, -36.5, 0), "C10": (23.5, -36.5, 0),           # 3.3 V LDO
    "U7": (30.0, -30.0, 0), "C15": (30.0, -33.5, 0), "R13": (34.5, -30.0, 90),         # level shifter
    "J4": (-16.5, -30.0, 270),                                                        # expansion header (origin = pin 1; pins run toward -X)
    "SW2": (-27.0, -37.0, 0), "SW3": (-37.5, -28.5, 0),                                 # RESET / BOOT
    # --- side connectors, wires run between the holders into the centre slot --------------
    "J2": (48.5, 4.0, 90), "J3": (-48.5, -4.0, 90), "J5": (-47.0, 17.0, 90),
    "C8": (47.5, -12.0, 90),
    # --- USB-C, ESD, UART, auto-reset, buttons (bottom-left) ---------------------------------
    "J1": (0, USB_Y, 0),
    "R1": (5.5, 43.0, 0), "R2": (5.5, 45.0, 0), "C1": (9.5, 47.0, 0),
    "U8": (-6.0, 44.5, 0),
    "U6": (-13.5, 42.0, 0), "C14": (-8.5, 37.5, 90),
    "Q5": (-21.5, 44.0, 0), "Q6": (-21.5, 40.0, 0), "R20": (-27.5, 40.0, 90), "R21": (-27.5, 37.0, 90),
    "D3": (*polar(52.5, LED_ANGS[0]), LED_ANGS[0] + 90), "D4": (*polar(52.5, LED_ANGS[1]), LED_ANGS[1] + 90),
    "R4": (-29.0, 42.5, 90), "R5": (-31.5, 40.5, 90),
    # --- protection at the '-' end ... (left, near the BT pad 2 side is +X; CELL- pads are pad 2 at +X!) ---
    "Q1": (-41.5, 28.5, 0), "U3": (-34.0, 28.0, 0),
    "R6": (-30.0, 28.0, 90), "C3": (-27.5, 28.0, 90), "R7": (-25.0, 28.0, 90),
    # --- charger + load share ----------------------------------------------------------------
    "U2": (13.0, 42.0, 0), "R3": (8.0, 37.5, 90), "C2": (15.0, 47.5, 0),
    "D1": (12.5, 35.0, 0), "Q2": (12.5, 30.0, 0), "R8": (20.0, 29.0, 90),
    # --- boost + LED rail switch (right) -----------------------------------------------------
    "U4": (46.0, 24.0, 0), "L1": (47.3, 16.0, 90), "D2": (41.0, 27.5, 0),
    "R9": (34.0, 28.5, 90), "R10": (36.0, 28.5, 90),
    "C4": (40.5, 31.5, 0), "C5": (40.5, 33.5, 0), "C6": (28.0, 33.0, 0), "C7": (28.0, 35.0, 0),
    "Q3": (23.5, 33.0, 0), "Q4": (19.0, 33.0, 0), "R11": (19.0, 36.5, 0), "R12": (23.5, 36.5, 0),
    "SW1": None,   # computed: pins centred at polar(SW_R, SW_ANG), actuator outward
}


# -----------------------------------------------------------------------------
def load_circuit():
    """Import the SKiDL design; returns (parts, nets) of the default circuit."""
    import logging
    logging.disable(logging.WARNING)
    import tablelight_netlist as tn
    circ = tn.U1.circuit
    return circ.parts, circ.nets


def place_switch(fp):
    """Slide switch: pin row centred at polar(SW_R, SW_ANG), body (local +Y) pointing radially outward."""
    tx, ty = polar(SW_R, SW_ANG)
    best = None
    for rot in range(0, 360, 5):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(mm(0, 0))
        p2 = [pd for pd in fp.Pads() if pd.GetNumber() == "2"][0].GetPosition()
        # body centre local (2.0, 2.0) -> where is it after rotation? use courtyard bbox centre
        bb = fp.GetBoundingBox(False, False)
        cx, cy = bb.GetCenter().x / 1e6, bb.GetCenter().y / 1e6
        # translate so pad 2 lands on target
        dx, dy = tx - p2.x / 1e6, ty - p2.y / 1e6
        bx, by = cx + dx, cy + dy
        outward = (bx * tx + by * ty) / (SW_R)  # projection of body centre onto the radial direction
        tang = abs(bx * (-math.sin(math.radians(SW_ANG))) + by * math.cos(math.radians(SW_ANG)))
        score = outward - 5 * tang
        if best is None or score > best[0]:
            best = (score, rot, dx, dy)
    _, rot, dx, dy = best
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(mm(dx, dy))


def fp_lib_path(libname):
    p = os.path.join(FP_LIB_DIR, libname + ".pretty")
    if not os.path.isdir(p):
        raise FileNotFoundError(p)
    return p


def add_footprints(board, parts):
    nets = {}

    def net_for(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    fps = {}
    for part in sorted(parts, key=lambda p: p.ref):
        lib, name = part.footprint.split(":")
        fp = pcbnew.FootprintLoad(fp_lib_path(lib), name)
        if fp is None:
            raise RuntimeError(f"footprint not found: {part.footprint}")
        fp.SetReference(part.ref)
        fp.SetValue(str(part.value))
        if part.ref == "SW1":
            place_switch(fp)
        else:
            x, y, rot = PLACEMENT[part.ref]
            fp.SetPosition(mm(x, y))
            fp.SetOrientationDegrees(rot)
        # nets
        for pin in part.pins:
            if pin.net is None or pin.net.name.startswith("NC_"):
                continue
            pads = [pd for pd in fp.Pads() if pd.GetNumber() == str(pin.num)]
            if not pads:
                raise RuntimeError(f"{part.ref}: pad {pin.num} not in footprint {part.footprint}")
            for pd in pads:
                pd.SetNet(net_for(pin.net.name))
        board.Add(fp)
        fps[part.ref] = fp
    return fps, nets


def add_outline(board):
    L = pcbnew.Edge_Cuts
    c = pcbnew.PCB_SHAPE(board)
    c.SetShape(pcbnew.SHAPE_T_CIRCLE)
    c.SetLayer(L)
    c.SetWidth(FromMM(0.1))
    c.SetCenter(mm(0, 0))
    c.SetEnd(mm(BOARD_R, 0))
    board.Add(c)
    # centre wire slot: rounded slot SLOT_W x SLOT_H
    hw, r = SLOT_W / 2 - SLOT_H / 2, SLOT_H / 2
    for sy in (-r, r):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(L); s.SetWidth(FromMM(0.1))
        s.SetStart(mm(-hw, sy)); s.SetEnd(mm(hw, sy))
        board.Add(s)
    for sx, sgn in ((hw, 1), (-hw, -1)):
        a = pcbnew.PCB_SHAPE(board)
        a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetLayer(L); a.SetWidth(FromMM(0.1))
        a.SetArcGeometry(mm(sx, -r), mm(sx + sgn * r, 0), mm(sx, r))
        board.Add(a)


def add_text(board, text, x, y, layer=pcbnew.F_SilkS, size=1.0, rot=0, mirror=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(mm(x, y))
    t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetTextAngleDegrees(rot)
    t.SetMirrored(mirror)
    board.Add(t)


def add_rule_area(board, pts, layers, name):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in layers:
        ls.addLayer(l)
    z.SetLayerSet(ls)
    z.SetZoneName(name)
    ol = z.Outline()
    ol.NewOutline()
    for (x, y) in pts:
        ol.Append(FromMM(x), FromMM(y))
    board.Add(z)


def add_gnd_zones(board, gnd):
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetZoneName(f"GND_{pcbnew.BOARD.GetStandardLayerName(layer)}")
        ol = z.Outline()
        ol.NewOutline()
        n = 72
        for i in range(n):
            x, y = polar(BOARD_R + 1.0, 360.0 * i / n)
            ol.Append(FromMM(x), FromMM(y))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetMinThickness(FromMM(0.25))
        z.SetLocalClearance(FromMM(0.25))
        z.SetThermalReliefGap(FromMM(0.3))
        z.SetThermalReliefSpokeWidth(FromMM(0.4))
        z.SetAssignedPriority(0)
        board.Add(z)


def setup_rules(board):
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = FromMM(0.2)
    ds.m_ViasMinSize = FromMM(0.6)
    ds.m_MinThroughDrill = FromMM(0.2)
    ds.m_MinClearance = FromMM(CLEARANCE)
    ds.m_CopperEdgeClearance = FromMM(0.4)
    ds.m_HoleClearance = FromMM(0.25)
    ds.m_HoleToHoleMin = FromMM(0.5)
    ds.m_SolderMaskExpansion = FromMM(0.05)
    ds.SetCopperLayerCount(2)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(FromMM(CLEARANCE))
    nc.SetTrackWidth(FromMM(TRACK_DEFAULT))
    nc.SetViaDiameter(FromMM(VIA_D))
    nc.SetViaDrill(FromMM(VIA_DRILL))


def build_placed_board():
    parts, _ = load_circuit()
    board = pcbnew.BOARD()
    setup_rules(board)
    fps, nets = add_footprints(board, parts)
    add_outline(board)
    # antenna keep-out: no copper under the module antenna, both layers
    ax, ay0, ay1 = 9.0 + 1.5, ESP_Y - 25.5 / 2 - 1.0, ESP_Y - 25.5 / 2 + 6.0 + 0.5
    add_rule_area(board, [(-ax, ay0), (ax, ay0), (ax, ay1), (-ax, ay1)], [pcbnew.F_Cu, pcbnew.B_Cu], "antenna_keepout")
    # screw-head keep-outs on F.Cu around H1..H4 (M3 heads, r = 4 mm): no tracks/vias/pour under the heads
    for i in range(4):
        cx, cy = polar(P["pcb_hole_r"], 45 + 90 * i)
        pts = [(cx + 4.0 * math.cos(math.radians(t)), cy + 4.0 * math.sin(math.radians(t))) for t in range(0, 360, 15)]
        add_rule_area(board, pts, [pcbnew.F_Cu], f"screw_head_H{i+1}")
    # silkscreen
    add_text(board, "TableLight v1.0", -32.0, -26.8, size=1.0)
    add_text(board, "github.com/jonny190/TableLight", 0, 26.6, size=0.9)
    add_text(board, "1S: 1 or 2 x 18650 in PARALLEL", -24.0, 0.0, size=0.8)
    add_text(board, "same model, same charge state", 24.0, 0.0, size=0.8)
    add_text(board, "USB-C 5V  charge + flash", 0, 39.5, size=0.8)
    add_text(board, "LED", 44.0, 10.5, size=0.8); add_text(board, "TOUCH", -44.0, -10.5, size=0.8)
    add_text(board, "BAT ALT", -40.5, 17.0, size=0.8, rot=90)
    for ref in ("BT1", "BT2"):
        x, y, _ = PLACEMENT[ref]
        add_text(board, "+", x - 46.0, y, size=2.0)
        add_text(board, "-", x + 46.0, y, size=2.0)
    add_text(board, "TableLight v1.0  -  component side faces DOWN in the lamp", 0, 27.0, layer=pcbnew.B_SilkS, size=1.0, mirror=True)
    return board, fps, nets


# -----------------------------------------------------------------------------
def rewrite_dsn_classes(dsn_path):
    """Move the power nets into their own Specctra class with a wider track."""
    txt = open(dsn_path).read()
    m = re.search(r'\(class kicad_default(.*?)\(circuit(.*?)\)\s*\(rule\s*\(width ([\d.]+)\)\s*\(clearance ([\d.]+)\)\s*\)\s*\)', txt, re.S)
    if not m:
        raise RuntimeError("could not find kicad_default class in DSN")
    names_blob, circuit, width, clearance = m.group(1), m.group(2), m.group(3), m.group(4)
    names = re.findall(r'"([^"]+)"|(\S+)', names_blob)
    names = [a or b for a, b in names]
    keep = [n for n in names if n not in POWER_NETS]
    power = [n for n in names if n in POWER_NETS]
    unit = 1000.0 if float(width) > 10 else 1.0   # um vs mm
    def q(n): return f'"{n}"'
    new_default = f'(class kicad_default {" ".join(q(n) for n in keep)}\n      (circuit{circuit})\n      (rule (width {width}) (clearance {clearance}))\n    )'
    new_power = f'\n    (class power {" ".join(q(n) for n in power)}\n      (circuit{circuit})\n      (rule (width {TRACK_POWER*unit:g}) (clearance {clearance}))\n    )'
    txt = txt[:m.start()] + new_default + new_power + txt[m.end():]
    open(dsn_path, "w").write(txt)
    return keep, power


def autoroute(board, workdir, passes=60):
    dsn = os.path.join(workdir, "tablelight.dsn")
    ses = os.path.join(workdir, "tablelight.ses")
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise RuntimeError("DSN export failed")
    rewrite_dsn_classes(dsn)
    if os.path.exists(ses):
        os.remove(ses)
    cmd = ["xvfb-run", "-a", "java", "-Djava.awt.headless=false", "-jar", FREEROUTING_JAR,
           "-de", dsn, "-do", ses, "-mp", str(passes), "-dct", "0", "-oit", "1.0"]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=False, timeout=3600, stdout=open(os.path.join(workdir, "freerouting.log"), "w"), stderr=subprocess.STDOUT)
    if not os.path.exists(ses):
        raise RuntimeError("freerouting produced no SES; see freerouting.log")
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise RuntimeError("SES import failed")


def unrouted_count(board):
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    return conn.GetUnconnectedCount(True) if hasattr(conn, "GetUnconnectedCount") else -1


def run_drc(board, report_path):
    ok = pcbnew.WriteDRCReport(board, report_path, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(report_path).read() if os.path.exists(report_path) else ""
    m = re.search(r"\*\* Found (\d+) DRC violations \*\*", txt)
    u = re.search(r"\*\* Found (\d+) unconnected pads \*\*", txt)
    return ok, int(m.group(1)) if m else -1, int(u.group(1)) if u else -1, txt


def export_fab(pcb_path, out_dir, parts):
    os.makedirs(out_dir, exist_ok=True)
    gerb = os.path.join(out_dir, "gerbers")
    shutil.rmtree(gerb, ignore_errors=True)
    os.makedirs(gerb)
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--layers", layers, "--no-x2", "--no-netlist",
                    "--subtract-soldermask", "--use-drill-file-origin", "-o", gerb + "/", pcb_path], check=True)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--drill-origin", "absolute",
                    "--excellon-units", "mm", "--excellon-zeros-format", "decimal", "--generate-map", "--map-format", "pdf",
                    "-o", gerb + "/", pcb_path], check=True)
    zpath = os.path.join(out_dir, "tablelight-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gerb)):
            z.write(os.path.join(gerb, f), f)
    # pick and place (front only, mm, csv)
    pos_raw = os.path.join(out_dir, "tablelight-pos-raw.csv")
    subprocess.run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "front",
                    "--smd-only", "-o", pos_raw, pcb_path], check=True)
    # PCBWay CPL format: Designator, Mid X, Mid Y, Layer, Rotation
    rows = list(csv.reader(open(pos_raw)))
    hdr = rows[0]
    ix = {h: i for i, h in enumerate(hdr)}
    with open(os.path.join(out_dir, "tablelight-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows[1:]:
            if not r:
                continue
            w.writerow([r[ix["Ref"]], f"{float(r[ix['PosX']]):.3f}mm", f"{float(r[ix['PosY']]):.3f}mm",
                        "Top" if r[ix["Side"]] == "top" else "Bottom", f"{float(r[ix['Rot']]):.1f}"])
    os.remove(pos_raw)
    # PCBWay BOM: Item, Designator, Qty, Manufacturer, MPN, Description, Package, Type
    smd_fp = ("Resistor_SMD", "Capacitor_SMD", "LED_SMD", "Diode_SMD", "Inductor_SMD", "Package_", "RF_Module", "Button_Switch_SMD", "Connector_USB")
    groups = {}
    for p in parts:
        if p.ref.startswith("H"):
            continue
        key = (str(p.value), p.footprint, getattr(p, "mpn", ""), getattr(p, "description", ""))
        groups.setdefault(key, []).append(p.ref)
    with open(os.path.join(out_dir, "tablelight-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Item", "Designator", "Qty", "Manufacturer", "Mfg Part #", "Description / Value", "Package / Footprint", "Type", "Notes"])
        for i, ((val, fp, mpn, desc), refs) in enumerate(sorted(groups.items(), key=lambda kv: kv[1][0]), 1):
            typ = "SMD" if fp.startswith(smd_fp) else "THT"
            w.writerow([i, ",".join(sorted(refs)), len(refs), "", mpn, f"{val} - {desc}", fp.split(":")[1], typ, ""])
    return zpath


def render_previews(pcb_path, out_dir):
    """SVG plots -> PNG previews of both sides."""
    import cairosvg
    for side, layers, name in (("top", "F.Cu,F.SilkS,F.Mask,Edge.Cuts", "pcb_top"), ("bottom", "B.Cu,B.SilkS,Edge.Cuts", "pcb_bottom")):
        svgdir = os.path.join(out_dir, "svg_" + side)
        shutil.rmtree(svgdir, ignore_errors=True)
        os.makedirs(svgdir)
        args = ["kicad-cli", "pcb", "export", "svg", "--layers", layers, "--page-size-mode", "2", "--exclude-drawing-sheet",
                "-o", os.path.join(svgdir, name + ".svg"), pcb_path]
        if side == "bottom":
            args.insert(-2, "--mirror")
        subprocess.run(args, check=True)
        cairosvg.svg2png(url=os.path.join(svgdir, name + ".svg"), write_to=os.path.join(ROOT, "docs", "images", name + ".png"), output_width=1400)
        shutil.rmtree(svgdir, ignore_errors=True)


# -----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["place", "route", "finish"], default="finish")
    ap.add_argument("--passes", type=int, default=60)
    ap.add_argument("--from-routed", action="store_true", help="skip routing: load kicad/tablelight_routed.kicad_pcb")
    args = ap.parse_args()
    os.makedirs(KICAD_DIR, exist_ok=True)
    parts, _ = load_circuit()

    routed_path = os.path.join(KICAD_DIR, "tablelight_routed.kicad_pcb")
    if args.from_routed and os.path.exists(routed_path):
        board = pcbnew.LoadBoard(routed_path)
        nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()} if hasattr(board.GetNetInfo(), "NetsByName") else None
        gnd = board.FindNet("GND")
    else:
        board, fps, nets = build_placed_board()
        gnd = nets["GND"]
        placed_path = os.path.join(KICAD_DIR, "tablelight_placed.kicad_pcb")
        board.Save(placed_path)
        print("placed board ->", placed_path, f"({len(fps)} footprints, {len(nets)} nets)")
        if args.stage == "place":
            board.Save(PCB_PATH)
            return
        autoroute(board, KICAD_DIR, passes=args.passes)
        board.Save(routed_path)
        print("routed board ->", routed_path)
        if args.stage == "route":
            board.Save(PCB_PATH)
            return

    add_gnd_zones(board, gnd)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    board.Save(PCB_PATH)
    ok, nviol, nunconn, txt = run_drc(board, os.path.join(KICAD_DIR, "drc_report.txt"))
    print(f"DRC: violations={nviol} unconnected={nunconn}")
    zpath = export_fab(PCB_PATH, FAB_DIR, parts)
    render_previews(PCB_PATH, KICAD_DIR)
    print("fab package ->", zpath)
    if nviol != 0 or nunconn != 0:
        print(txt[-4000:])
        sys.exit(2)


if __name__ == "__main__":
    main()
