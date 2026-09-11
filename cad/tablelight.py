#!/usr/bin/env python3
"""
TableLight - parametric 3D-printable, battery powered WLED table lamp.

Generates all printable parts as STL (binary) into cad/stl/ plus preview
renders into docs/images/.  Pure Python: trimesh + manifold3d for booleans,
matplotlib for previews.

    pip install trimesh manifold3d numpy matplotlib
    python3 cad/tablelight.py            # STLs + previews
    python3 cad/tablelight.py --no-render

Layout (classic "Poldina" style rechargeable table lamp):
    * flat honeycomb base disc  - holds the PCB, 1-2 x 18650, USB-C, power switch
    * thin stem                 - carries the wires, screws to the base deck and into the head
    * down-firing cone shade    - opaque cone, LED ring(s) under the white top plate shine onto the table
    * white top plate           - hides the capacitive touch pad

Coordinate system (all mm):
    Z = 0 is the top surface of the base "deck" (top face of the base disc).
    The base body hangs BELOW z=0, stem / shade / head rise ABOVE it.
    X/Y origin is the lamp axis.

Every dimension that another part or the PCB depends on lives in the
PARAMETERS block so the enclosure, the PCB outline (hardware/pcb/) and the
docs stay in sync.
"""
import argparse
import math
import os
import sys

import numpy as np
import trimesh
from trimesh.transformations import rotation_matrix as rotm

# ----------------------------------------------------------------------------
# PARAMETERS
# ----------------------------------------------------------------------------
P = dict(
    # --- base disc -----------------------------------------------------------
    base_r_out=59.0,          # outer radius (Ø118 mm)
    base_wall=2.5,            # side wall thickness
    base_height=36.0,         # deck top (z=0) to bottom edge
    deck_t=3.5,               # deck (top plate) thickness
    base_top_chamfer=3.0,     # chamfer on the deck outer edge (makes the puck look slimmer)
    base_bot_chamfer=0.8,     # elephant-foot relief on the bottom edge
    hex_R=5.0,                # honeycomb: hexagon circumradius (flat-to-flat 8.66 mm)
    hex_gap=1.6,              # rib between cells
    hex_depth=1.5,            # cell recess depth into the deck top
    hex_r_min=22.0,           # honeycomb annulus (outside the stem flange ...
    hex_r_max=46.0,           # ... inside the plain outer rim where the PCB bosses are)

    # --- PCB (round, Ø110) ----------------------------------------------------
    pcb_r=55.0,
    pcb_t=1.6,
    pcb_hole_r=50.0,          # 4 mounting holes at 45/135/225/315 deg
    pcb_hole_d=3.2,
    pcb_boss_d=7.5,
    pcb_boss_h=5.0,           # standoff: deck underside -> PCB top (solder) face
    pcb_slot=(14.0, 6.0),     # wire slot in the PCB centre (X x Y), between the two 18650 holders
    insert_d=4.0,             # M3 heat-set insert hole (Ø4.6 x 4-5.7 mm inserts)
    insert_depth=6.0,

    # --- bottom plate -------------------------------------------------------
    plate_t=3.0,
    plate_clear=0.3,
    plate_boss_r=53.0,
    plate_boss_d=8.0,
    plate_boss_h=10.0,
    plate_boss_start_deg=22.5,  # offset from the PCB bosses so the PCB screws stay reachable
    foot_d=10.5, foot_recess=0.6, foot_r=44.0,

    # --- wall openings (angles: 0 = +X, -90 = -Y, CCW from +X, lamp top view) ---
    usb_angle=-90.0,
    usb_w=13.0, usb_h=7.5,    # opening admits the plug over-mould (receptacle is ~3 mm behind the outer face)
    usb_center_below_pcb=1.63,
    sw_angle=-120.0,          # power switch: opposite side of the USB from the charge LEDs
    sw_w=9.0, sw_h=4.0,
    sw_center_below_pcb=2.6,
    led_angles=(-66.0, -61.0),
    led_hole_d=2.5,
    led_center_below_pcb=1.0,

    # --- stem -------------------------------------------------------------------
    stem_od=22.0,
    stem_bore=17.0,           # wires + JST-PH plug pass through
    stem_len=230.0,           # tube length above the flange (print height = stem_len + flange_t)
    flange_d=40.0, flange_t=6.0, flange_chamfer=1.5,
    flange_screw_r=14.5,      # 4 x M3 inserts at 45 deg diagonals (screwed from below through the deck)
    deck_wire_hole_d=12.0,    # under the stem bore
    stem_screw_d=2.6,         # 2 radial self-tapping holes at the stem top (head plate M3 screws)
    stem_screw_from_top=7.0,
    stem_insert=13.0,         # how far the stem enters the head socket

    # --- head plate (white top) -------------------------------------------------
    head_r=52.0,              # Ø104 top, flush with the cone top
    head_t=5.0,
    head_chamfer=1.5,
    skirt_h=10.0,             # skirt inside the cone top
    skirt_clear=0.3,
    socket_od=30.0, socket_depth=15.0, socket_clear=0.2,
    socket_notch_w=6.0, socket_notch_h=5.0,     # wire entry from the ring channels into the bore
    pad_d=20.0, pad_recess=3.0,                 # touch foil recess above the bore (leaves head_t - 3 = 2 mm)
    ring_out=(35.7, 43.7),    # channel radii for a 24-LED ring  (Ø72 ID / Ø86.5 OD, 'Chinese' WS2812B/SK6812 ring)
    ring_in=(26.2, 34.3),     # channel radii for an optional 16-LED ring (Ø53/Ø68) or Adafruit 24-ring (Ø52.3/Ø65.5)
    ring_depth=2.5,
    ring_groove_w=4.0,        # radial wire grooves from the channels to the socket

    # --- cone shade -------------------------------------------------------------
    cone_r_bot=70.0,          # Ø140 at the open bottom
    cone_r_top=52.0,          # Ø104 at the top (= head_r)
    cone_h=120.0,
    cone_wall=1.6,
    cone_screw_n=3,           # radial M3 screws through the cone into the head skirt
    cone_screw_d=3.4,
    cone_screw_from_top=5.0,
    nub_from_top=14.0,        # diffuser rests on 3 nubs this far below the cone top
    nub_size=1.5, nub_h=3.0,
    diffuser_t=1.2, diffuser_clear=0.4, diffuser_hole_d=24.0,
)

SECTIONS = 128   # facets on round features
HERE = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(HERE, "stl")
IMG_DIR = os.path.join(HERE, "..", "docs", "images")


# ----------------------------------------------------------------------------
# primitives / helpers
# ----------------------------------------------------------------------------
def _fix(m):
    """Make a mesh a proper positive volume (revolve() may come out inverted)."""
    if m.volume < 0:
        m.invert()
    return m


def cyl(r, h, z0, x=0.0, y=0.0, sections=SECTIONS):
    m = trimesh.creation.cylinder(radius=r, height=h, sections=sections)
    m.apply_translation([x, y, z0 + h / 2.0])
    return m


def box(sx, sy, sz, cx=0.0, cy=0.0, z0=0.0):
    m = trimesh.creation.box(extents=[sx, sy, sz])
    m.apply_translation([cx, cy, z0 + sz / 2.0])
    return m


def revolve(profile_rz, sections=SECTIONS):
    """Revolve a closed (r, z) polygon around the Z axis."""
    m = trimesh.creation.revolve(np.asarray(profile_rz, float), sections=sections)
    return _fix(m)


def frustum(r_bottom, r_top, h, z0, x=0.0, y=0.0):
    prof = [[0, z0], [r_bottom, z0], [r_top, z0 + h], [0, z0 + h]]
    m = revolve(prof)
    m.apply_translation([x, y, 0])
    return m


def ring(r_in, r_out, h, z0, sections=SECTIONS):
    """Annular ring (tube) - built from two cylinders because revolve() of an
    off-axis profile does not produce a closed volume."""
    return difference(cyl(r_out, h, z0, 0, 0, sections), [cyl(r_in, h + 2, z0 - 1, 0, 0, sections)])


def chamfered_square_prism(w, h, z0, chamfer, cx=0.0, cy=0.0):
    """Square prism (w x w x h) with 45 deg chamfered vertical edges."""
    hw = w / 2.0
    c = chamfer
    pts = np.array([
        [-hw + c, -hw], [hw - c, -hw], [hw, -hw + c], [hw, hw - c],
        [hw - c, hw], [-hw + c, hw], [-hw, hw - c], [-hw, -hw + c],
    ])
    from shapely.geometry import Polygon
    m = trimesh.creation.extrude_polygon(Polygon(pts), h)
    m.apply_translation([cx, cy, z0])
    return m


def rounded_slot(w, h, depth, cx=0.0, cy=0.0, cz=0.0):
    """Slot with fully rounded ends in the XZ plane, extruded along Y (depth).
    w along X, h along Z (h is the diameter of the round ends)."""
    r = h / 2.0
    parts = [box(max(w - h, 0.01), depth, h, cx, cy, cz - r)]
    for sx in (-1, 1):
        c = trimesh.creation.cylinder(radius=r, height=depth, sections=48)
        c.apply_transform(rotm(math.pi / 2, [1, 0, 0]))   # axis along Y
        c.apply_translation([cx + sx * (w / 2.0 - r), cy, cz])
        parts.append(c)
    return union(parts)


def rot_z(m, deg):
    m.apply_transform(rotm(math.radians(deg), [0, 0, 1]))
    return m


def union(meshes):
    meshes = [m for m in meshes if m is not None]
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.boolean.union(meshes, engine="manifold")


def difference(a, cutters):
    if not cutters:
        return a
    return trimesh.boolean.difference([a] + list(cutters), engine="manifold")


def wall_cutter(angle_deg, w, h, z_center, r_in, r_out, rounded=True):
    """A cutter that goes radially through the shell wall at a given angle.
    Built along +Y (angle +90) then rotated so e.g. angle -90 == -Y direction."""
    depth = (r_out - r_in) + 6.0
    yc = (r_in + r_out) / 2.0
    if rounded:
        c = rounded_slot(w, h, depth, 0, yc, z_center)
    else:
        c = box(w, depth, h, 0, yc, z_center - h / 2.0)
    return rot_z(c, angle_deg - 90.0)


def four_positions(radius, start_deg=45.0):
    return [(radius * math.cos(math.radians(start_deg + k * 90)),
             radius * math.sin(math.radians(start_deg + k * 90))) for k in range(4)]


# ----------------------------------------------------------------------------
# derived dimensions shared with docs / PCB
# ----------------------------------------------------------------------------
def derived(p=P):
    d = {}
    d["base_r_in"] = p["base_r_out"] - p["base_wall"]
    d["pcb_top_z"] = -(p["deck_t"] + p["pcb_boss_h"])            # PCB top (solder) face
    d["pcb_comp_z"] = d["pcb_top_z"] - p["pcb_t"]                # component face (faces DOWN)
    d["usb_z"] = d["pcb_comp_z"] - p["usb_center_below_pcb"]
    d["sw_z"] = d["pcb_comp_z"] - p["sw_center_below_pcb"]
    d["led_z"] = d["pcb_comp_z"] - p["led_center_below_pcb"]
    d["plate_top_z"] = -(p["base_height"] - p["plate_t"])
    d["plate_r"] = d["base_r_in"] - p["plate_clear"]
    d["max_component_h"] = (d["pcb_comp_z"] - d["plate_top_z"]) - 1.0
    d["plate_boss_keepout_z"] = d["plate_top_z"] + p["plate_boss_h"] + p["plate_boss_d"] / 2
    d["plate_boss_keepout_h"] = d["pcb_comp_z"] - d["plate_boss_keepout_z"]
    # stem / head stack
    d["stem_top_z"] = p["flange_t"] + p["stem_len"]
    d["head_z0"] = d["stem_top_z"] + (p["socket_depth"] - p["stem_insert"])   # head plate underside
    d["head_top_z"] = d["head_z0"] + p["head_t"]
    d["cone_top_z"] = d["head_z0"]
    d["cone_z0"] = d["cone_top_z"] - p["cone_h"]
    d["cone_slope"] = (p["cone_r_bot"] - p["cone_r_top"]) / p["cone_h"]
    d["cone_r_in_top"] = p["cone_r_top"] - p["cone_wall"]
    d["skirt_r_out"] = d["cone_r_in_top"] - p["skirt_clear"]
    d["skirt_r_in"] = p["ring_out"][1] + 0.6
    d["diffuser_z"] = d["cone_top_z"] - p["nub_from_top"]
    d["diffuser_r"] = d["cone_r_in_top"] + d["cone_slope"] * p["nub_from_top"] - p["diffuser_clear"]
    d["visible_stem"] = d["cone_z0"]                             # deck top -> cone bottom edge
    d["lamp_height"] = d["head_top_z"] + p["base_height"]
    return d


D = derived()


# ----------------------------------------------------------------------------
# PARTS
# ----------------------------------------------------------------------------
def hex_pattern_cutter(p=P):
    """Honeycomb pockets for the deck top: pointy-top hexagons on a triangular lattice."""
    from shapely.geometry import Polygon
    Rh, g = p["hex_R"], p["hex_gap"]
    s = math.sqrt(3) * Rh + g                    # centre spacing (uniform rib width g)
    hexes = []
    n = int(p["hex_r_max"] / s) + 2
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            cx = s * (i + j / 2.0)
            cy = s * math.sqrt(3) / 2.0 * j
            rc = math.hypot(cx, cy)
            if rc + Rh > p["hex_r_max"] or rc - Rh < p["hex_r_min"]:
                continue
            pts = [(cx + Rh * math.cos(math.radians(90 + 60 * k)), cy + Rh * math.sin(math.radians(90 + 60 * k))) for k in range(6)]
            h = trimesh.creation.extrude_polygon(Polygon(pts), p["hex_depth"] + 1.0)
            h.apply_translation([0, 0, -p["hex_depth"]])
            hexes.append(h)
    return union(hexes), len(hexes)


def make_base_shell(p=P, d=D):
    R, Ri = p["base_r_out"], d["base_r_in"]
    H, T = p["base_height"], p["deck_t"]
    c1, c2 = p["base_top_chamfer"], p["base_bot_chamfer"]
    body = revolve([[0, 0], [R - c1, 0], [R, -c1], [R, -H + c2], [R - c2, -H], [0, -H]])
    shell = difference(body, [cyl(Ri, H - T + 1.0, -H - 1.0)])

    adds = []
    for (x, y) in four_positions(p["pcb_hole_r"]):
        adds.append(cyl(p["pcb_boss_d"] / 2, p["pcb_boss_h"] + 0.5, -T - p["pcb_boss_h"], x, y, 48))
    bh, zb = p["plate_boss_h"], d["plate_top_z"]
    for (x, y) in four_positions(p["plate_boss_r"], p["plate_boss_start_deg"]):
        adds.append(cyl(p["plate_boss_d"] / 2, bh, zb, x, y, 48))
        adds.append(frustum(p["plate_boss_d"] / 2, 0.01, p["plate_boss_d"] / 2, zb + bh, x, y))
    shell = union([shell] + adds)

    cuts = []
    for (x, y) in four_positions(p["pcb_hole_r"]):
        cuts.append(cyl(p["insert_d"] / 2, p["insert_depth"], -T - p["pcb_boss_h"] - 0.01, x, y, 32))
    for (x, y) in four_positions(p["plate_boss_r"], p["plate_boss_start_deg"]):
        cuts.append(cyl(p["insert_d"] / 2, p["insert_depth"], zb - 0.01, x, y, 32))
    # honeycomb
    hexes, _ = hex_pattern_cutter(p)
    cuts.append(hexes)
    # stem wire hole + 4 stem flange screw holes
    cuts.append(cyl(p["deck_wire_hole_d"] / 2, T + 2, -T - 1, 0, 0, 64))
    for (x, y) in four_positions(p["flange_screw_r"]):
        cuts.append(cyl(3.4 / 2, T + 2, -T - 1, x, y, 32))
    # wall openings
    cuts.append(wall_cutter(p["usb_angle"], p["usb_w"], p["usb_h"], d["usb_z"], Ri, R))
    cuts.append(wall_cutter(p["sw_angle"], p["sw_w"], p["sw_h"], d["sw_z"], Ri, R))
    for a in p["led_angles"]:
        cuts.append(wall_cutter(a, p["led_hole_d"], p["led_hole_d"], d["led_z"], Ri, R))
    return difference(shell, cuts)


def make_bottom_plate(p=P, d=D):
    plate = cyl(d["plate_r"], p["plate_t"], d["plate_top_z"])
    cuts = []
    for (x, y) in four_positions(p["plate_boss_r"], p["plate_boss_start_deg"]):
        cuts.append(cyl(3.4 / 2, p["plate_t"] + 2, d["plate_top_z"] - 1, x, y, 32))
        cuts.append(cyl(6.4 / 2, 1.0, d["plate_top_z"] - p["plate_t"] - 0.01, x, y, 32))
    for (x, y) in four_positions(p["foot_r"], start_deg=0.0):
        cuts.append(cyl(p["foot_d"] / 2, p["foot_recess"], d["plate_top_z"] - p["plate_t"] - 0.01, x, y, 48))
    return difference(plate, cuts)


def make_stem(p=P, d=D):
    fr, ft, fc = p["flange_d"] / 2, p["flange_t"], p["flange_chamfer"]
    flange = revolve([[0, 0], [fr, 0], [fr, ft - fc], [fr - fc, ft], [0, ft]])
    tube = cyl(p["stem_od"] / 2, p["stem_len"] + 0.01, ft - 0.01, 0, 0, 96)
    stem = union([flange, tube])
    cuts = [cyl(p["stem_bore"] / 2, ft + p["stem_len"] + 4, -2, 0, 0, 96)]
    for (x, y) in four_positions(p["flange_screw_r"]):
        cuts.append(cyl(p["insert_d"] / 2, min(p["insert_depth"], ft - 0.8), -0.01, x, y, 32))
    zs = d["stem_top_z"] - p["stem_screw_from_top"]
    for ang in (0.0, 180.0):
        c = trimesh.creation.cylinder(radius=p["stem_screw_d"] / 2, height=p["stem_od"], sections=24)
        c.apply_transform(rotm(math.pi / 2, [0, 1, 0]))          # along X
        c.apply_translation([p["stem_od"] / 2, 0, zs])
        cuts.append(rot_z(c, ang))
    return difference(stem, cuts)


def make_head_plate(p=P, d=D):
    z0, T, R, c = d["head_z0"], p["head_t"], p["head_r"], p["head_chamfer"]
    plate = revolve([[0, z0], [R, z0], [R, z0 + T - c], [R - c, z0 + T], [0, z0 + T]])
    parts = [plate,
             ring(d["skirt_r_in"], d["skirt_r_out"], p["skirt_h"] + 0.01, z0 - p["skirt_h"]),
             cyl(p["socket_od"] / 2, p["socket_depth"] + 0.01, z0 - p["socket_depth"], 0, 0, 64)]
    head = union(parts)
    cuts = []
    # stem socket bore + touch pad recess above it
    cuts.append(cyl(p["stem_od"] / 2 + p["socket_clear"], p["socket_depth"] + 1, z0 - p["socket_depth"] - 1, 0, 0, 96))
    cuts.append(cyl(p["pad_d"] / 2, p["pad_recess"] + 0.5, z0 - 0.5, 0, 0, 64))
    # LED ring channels (underside) + radial wire grooves to the socket
    for (ri, ro) in (p["ring_out"], p["ring_in"]):
        cuts.append(ring(ri, ro, p["ring_depth"] + 1, z0 - 1))
    cuts.append(box(p["ring_out"][1] - p["stem_od"] / 2 + 1, p["ring_groove_w"], p["ring_depth"] - 0.5 + 1,
                    (p["ring_out"][1] + p["stem_od"] / 2) / 2, 0, z0 - 1))
    # wire notch through the socket wall (under the plate, on the +X side where the groove is)
    cuts.append(box(p["socket_od"] / 2 + 1, p["socket_notch_w"], p["socket_notch_h"] + 1, p["socket_od"] / 4 + 0.5, 0, z0 - p["socket_notch_h"]))
    # 2 radial screw holes through the socket wall (aligned with the stem holes)
    zs = d["stem_top_z"] - p["stem_screw_from_top"]
    for ang in (90.0, 270.0):
        cc = trimesh.creation.cylinder(radius=3.4 / 2, height=p["socket_od"] / 2 + 2, sections=24)
        cc.apply_transform(rotm(math.pi / 2, [0, 1, 0]))
        cc.apply_translation([(p["socket_od"] / 2 + 2) / 2 + p["stem_od"] / 2 - 1, 0, zs])
        cuts.append(rot_z(cc, ang))
    # 3 radial self-tapping holes in the skirt for the cone screws
    zc = d["cone_top_z"] - p["cone_screw_from_top"]
    for k in range(p["cone_screw_n"]):
        cc = trimesh.creation.cylinder(radius=2.6 / 2, height=6.0, sections=24)
        cc.apply_transform(rotm(math.pi / 2, [0, 1, 0]))
        cc.apply_translation([d["skirt_r_out"] - 3.0 + 0.5, 0, zc])
        cuts.append(rot_z(cc, 90.0 + 360.0 * k / p["cone_screw_n"]))
    return difference(head, cuts)


def make_cone_shade(p=P, d=D):
    z0, h = d["cone_z0"], p["cone_h"]
    outer = frustum(p["cone_r_bot"], p["cone_r_top"], h, z0)
    s = d["cone_slope"]
    inner = frustum(p["cone_r_bot"] - p["cone_wall"] + s, d["cone_r_in_top"] - s, h + 2, z0 - 1)
    cone = difference(outer, [inner])
    # 3 nubs that hold the diffuser disc
    adds = []
    zn = d["diffuser_z"] - p["nub_h"]
    r_in_nub = d["cone_r_in_top"] + s * (p["nub_from_top"] + p["nub_h"] / 2)
    for k in range(3):
        b = box(p["nub_size"] + 1.0, 4.0, p["nub_h"], r_in_nub - p["nub_size"] / 2 + 0.5, 0, zn)
        adds.append(rot_z(b, 30.0 + 120.0 * k))
    cone = union([cone] + adds)
    cuts = []
    zc = d["cone_top_z"] - p["cone_screw_from_top"]
    for k in range(p["cone_screw_n"]):
        cc = trimesh.creation.cylinder(radius=p["cone_screw_d"] / 2, height=8.0, sections=24)
        cc.apply_transform(rotm(math.pi / 2, [0, 1, 0]))
        cc.apply_translation([p["cone_r_top"] - 0.5, 0, zc])
        cuts.append(rot_z(cc, 90.0 + 360.0 * k / p["cone_screw_n"]))
    return difference(cone, cuts)


def make_head_diffuser(p=P, d=D):
    disc = cyl(d["diffuser_r"], p["diffuser_t"], d["diffuser_z"])
    return difference(disc, [cyl(p["diffuser_hole_d"] / 2, p["diffuser_t"] + 2, d["diffuser_z"] - 1, 0, 0, 64)])


# ----------------------------------------------------------------------------
# preview rendering
# ----------------------------------------------------------------------------
def _hex2rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def render(parts, colors, out_png, elev=22, azim=-55, title=None):
    """Shaded preview: all parts merged into ONE collection so painter's-algorithm
    depth sorting works across parts; simple Lambert shading from a fixed light."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    tris, cols = [], []
    light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    for name, m in parts.items():
        m = m.subdivide_to_size(max_edge=7.0, max_iter=12)   # small triangles => sane depth sorting
        base = _hex2rgb(colors.get(name, "#cccccc"))
        shade = 0.45 + 0.55 * np.clip(m.face_normals @ light, 0, 1)
        tris.append(m.vertices[m.faces])
        cols.append(np.c_[base[None, :] * shade[:, None], np.ones(len(m.faces))])
    tris = np.concatenate(tris); cols = np.concatenate(cols)

    fig = plt.figure(figsize=(7, 8), dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    pc = Poly3DCollection(tris, facecolors=cols, edgecolors="none", zsort="average")
    ax.add_collection3d(pc)
    lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
    ctr, span = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(ctr[0] - span, ctr[0] + span)
    ax.set_ylim(ctr[1] - span, ctr[1] + span)
    ax.set_zlim(ctr[2] - span, ctr[2] + span)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_proj_type("persp", focal_length=1.2)
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)


def render_section(parts, colors, out_png):
    """True 2D cross-section through the lamp axis (plane X=0): Y horizontal, Z vertical."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 12), dpi=120)
    for name, m in parts.items():
        sec = m.section(plane_origin=[0, 0, 0], plane_normal=[1, 0, 0])
        if sec is None:
            continue
        planar, T = sec.to_2D()          # 3D = T @ [x2d, y2d, 0, 1]
        def to_yz(coords):
            c = np.asarray(coords)
            h = np.c_[c, np.zeros(len(c)), np.ones(len(c))] @ T.T
            return h[:, 1], h[:, 2]
        for poly in planar.polygons_full:
            ys, zs = to_yz(poly.exterior.coords)
            ax.fill(ys, zs, color=colors.get(name, "#cccccc"), alpha=0.9, lw=0.6, ec="k")
            for hole in poly.interiors:
                hy, hz = to_yz(hole.coords)
                ax.fill(hy, hz, color="white", lw=0.6, ec="k")
    ax.set_aspect("equal")
    ax.set_title("Section through lamp axis (plane X = 0)")
    ax.grid(True, lw=0.3, alpha=0.4)
    ax.set_xlabel("Y (mm)")
    ax.set_ylabel("Z (mm)  (0 = deck top surface)")
    fig.tight_layout()
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()
    os.makedirs(STL_DIR, exist_ok=True)
    os.makedirs(IMG_DIR, exist_ok=True)

    builders = {
        "base_shell": make_base_shell,
        "base_bottom_plate": make_bottom_plate,
        "stem": make_stem,
        "head_plate": make_head_plate,
        "cone_shade": make_cone_shade,
        "head_diffuser": make_head_diffuser,
    }
    # print orientation (STL files are exported ready to print: Z up = build direction, part on Z=0)
    flip = lambda m: m.apply_transform(rotm(math.pi, [1, 0, 0]))
    print_orient = {"base_shell": flip, "head_plate": flip}       # visible top faces on the bed
    parts, ok = {}, True
    for name, fn in builders.items():
        m = fn()
        if not (m.is_watertight and m.is_volume and m.volume > 0):
            print(f"!! {name}: NOT a valid volume (watertight={m.is_watertight}, volume={m.volume:.1f})")
            ok = False
        parts[name] = m
        e = m.copy()
        if name in print_orient:
            print_orient[name](e)
        e.apply_translation([0, 0, -e.bounds[0][2]])
        e.export(os.path.join(STL_DIR, f"{name}.stl"))
        bb = e.extents
        print(f"{name:18s} faces={len(m.faces):6d}  vol={m.volume/1000:7.1f} cm3  print bbox={bb[0]:.1f} x {bb[1]:.1f} x {bb[2]:.1f} mm  watertight={m.is_watertight}")
    print(f"lamp: Ø{2*P['base_r_out']:.0f} base, shade Ø{2*P['cone_r_bot']:.0f}->Ø{2*P['cone_r_top']:.0f}, "
          f"visible stem {D['visible_stem']:.0f} mm, overall height {D['lamp_height']:.0f} mm")

    if not args.no_render:
        colors = {"base_shell": "#2e3440", "base_bottom_plate": "#4c566a", "stem": "#2e3440",
                  "head_plate": "#f4f4f2", "cone_shade": "#2e3440", "head_diffuser": "#e5e9f0"}
        exploded, offs = {}, {"base_bottom_plate": -35, "base_shell": 0, "stem": 20, "head_diffuser": 55, "cone_shade": 75, "head_plate": 120}
        for n, m in parts.items():
            e = m.copy(); e.apply_translation([0, 0, offs[n]]); exploded[n] = e
        render(exploded, colors, os.path.join(IMG_DIR, "exploded.png"), title="TableLight - exploded view")
        render(parts, colors, os.path.join(IMG_DIR, "assembled.png"), title="TableLight - assembled")
        render_section(parts, colors, os.path.join(IMG_DIR, "section.png"))
        light = {"base_shell": "#8a94a8", "stem": "#8a94a8", "cone_shade": "#8a94a8", "head_plate": "#f4f4f2"}
        render({"base_shell": parts["base_shell"]}, light, os.path.join(IMG_DIR, "base_shell.png"), elev=35, title="base_shell (honeycomb deck)")
        render({"base_shell": parts["base_shell"]}, light, os.path.join(IMG_DIR, "base_shell_bottom.png"), elev=-35, title="base_shell (from below)")
        render({"head_plate": parts["head_plate"]}, light, os.path.join(IMG_DIR, "head_plate_bottom.png"), elev=-40, title="head_plate (underside: LED ring channels, stem socket)")
        render({"cone_shade": parts["cone_shade"]}, light, os.path.join(IMG_DIR, "cone_shade.png"), elev=20, title="cone_shade")
        render({"stem": parts["stem"]}, light, os.path.join(IMG_DIR, "stem.png"), elev=20, title="stem")
        render({"base_bottom_plate": parts["base_bottom_plate"]}, colors, os.path.join(IMG_DIR, "base_bottom_plate.png"), elev=-35, title="base_bottom_plate (from below)")

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
