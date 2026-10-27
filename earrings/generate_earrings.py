#!/usr/bin/env python3
"""Generate two-layer Christmas tree earrings for a Glowforge Aura.

Six designs, each cut as a mirrored pair.  Five are a green tree with a
smaller red piece glued on top; the sixth turns that round: a whole red car
is the backing and the green tree glues onto it.  Each layer is cut from its
own material, so every design gets one file per colour:

    svg/<design>-green.svg   the green layer of both earrings
    svg/<design>-red.svg     the red layer of both earrings

Artboards are in real millimetres (1 SVG unit == 1 mm).  Colour convention,
matching the rest of this repo:

    #FF0000 (red)   stroke, no fill -> CUT
    #0000FF (blue)  stroke, no fill -> SCORE (detail lines on the car)

preview/*.svg are display copies with the layers stacked and coloured, plus a
jump ring and ear wire, so you can see the finished earring.

Needs:  pip install shapely
Run:    python3 generate_earrings.py
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
SVG_DIR = os.path.join(HERE, "svg")
PREVIEW_DIR = os.path.join(HERE, "preview")

CUT = "#FF0000"
SCORE = "#0000FF"
STROKE_W = 0.1

# --------------------------------------------------------------------------
# Earring constants (mm)
# --------------------------------------------------------------------------

HOLE_DIA = 1.6              # takes a 5-6 mm jump ring in 0.7-0.8 mm wire
HOLE_Y = 2.6                # hole centre below the top of the backing
HOLE_BOSS = 2.6             # radius of wood kept round the hole: 1.8 mm wall
MIN_FEATURE = 1.5           # thinnest wood we accept in either layer
CORNER_R = 0.5              # every convex corner is rounded at least this much

KEYRING_H = 60.0            # the car keyring, top to bottom
KEY_HOLE_DIA = 5.0          # takes a split ring
KEY_BOSS = 5.5              # 3 mm of wood round the split-ring hole

PAIR_GAP = 8.0              # space between the two earrings of a pair
SHEET_PAD = 5.0             # margin round the pair on the artboard

COLOURS = {                 # display only: (fill, edge, score)
    "green": ("#2e7d4f", "#1d5234", "#1d5234"),
    "red": ("#c8262c", "#8a1418", "#8a1418"),
}


@dataclass
class Earring:
    """One earring in its own frame: hole at (0, HOLE_Y), y down."""
    base: object                    # backing layer, carries the hole
    top: object                     # smaller layer glued on top
    base_colour: str = "green"
    top_colour: str = "red"
    base_score: list = field(default_factory=list)
    top_score: list = field(default_factory=list)
    hole_dia: float = HOLE_DIA
    hole_y: float = HOLE_Y


# --------------------------------------------------------------------------
# Shape helpers
# --------------------------------------------------------------------------

def soften(geom, r=CORNER_R):
    """Round every convex corner: a laser-cut point that sharp just chars off."""
    return geom.buffer(-r, quad_segs=8).buffer(r, quad_segs=8)


def parts(geom):
    return list(getattr(geom, "geoms", [geom]))


def tiered_tree(tiers, height, width, trunk_w=5.0, trunk_h=4.5, lift=2.2):
    """Classic fir: stacked triangles whose bottom edges bow up between the tips."""
    shapes = []
    tier_h = height / (tiers * 0.72 + 0.28)
    for i in range(tiers):
        top = i * tier_h * 0.72
        bot = top + tier_h
        half = width / 2 * (0.52 + 0.48 * (i + 1) / tiers)
        pts = [(0, top)]
        for k in range(21):                       # bottom edge, right to left
            u = k / 20
            pts.append((half - 2 * half * u, bot - lift * math.sin(math.pi * u)))
        shapes.append(Polygon(pts))
    trunk = box(-trunk_w / 2, height - lift - 1.5, trunk_w / 2, height + trunk_h)
    return unary_union([*shapes, trunk])


def smooth_tree(height, width, trunk_w=4.5, trunk_h=4.0):
    """Modern tree: one slender triangle with softly rounded corners."""
    tri = Polygon([(0, 0), (width / 2, height), (-width / 2, height)])
    tri = tri.buffer(-1.6, join_style="round").buffer(1.6, quad_segs=12)
    trunk = box(-trunk_w / 2, height - 1.5, trunk_w / 2, height + trunk_h)
    return unary_union([tri, trunk])


def soft_tree(tiers, height, width, step=0.5, tip_r=1.1, lift=0.8, trunk_w=5.0, trunk_h=4.5):
    """Halfway between smooth_tree and tiered_tree: tiers that only step in part
    way, with rounded branch tips, so the outline stays close to one triangle.

    `step` is how far each tier pulls in at its top (0 = smooth triangle,
    1 = fully pointy fir).
    """
    env = lambda y: width / 2 * y / height           # the smooth triangle's half-width
    tier_h = height / tiers
    shapes = [Polygon([(0, 0), (env(tier_h), tier_h), (-env(tier_h), tier_h)])]
    for i in range(1, tiers):
        top, bot = i * tier_h - max(1.2, lift + 0.4), (i + 1) * tier_h
        top_half = env(top) * (1 - step)
        pts = [(-top_half, top), (top_half, top)]
        for k in range(21):                       # bottom edge, right to left
            u = k / 20
            x = env(bot) - 2 * env(bot) * u
            pts.append((x, bot - lift * math.sin(math.pi * u)))
        shapes.append(Polygon(pts))
    trunk = box(-trunk_w / 2, height - lift - 1.5, trunk_w / 2, height + trunk_h)
    return soften(unary_union([*shapes, trunk]), tip_r)


def half_width_at(geom, y):
    """Half the narrower side of `geom` along the horizontal line at height y."""
    cut = geom.intersection(LineString([(-100, y), (100, y)]))
    xs = [x for seg in parts(cut) for x, _ in seg.coords]
    return min(-min(xs), max(xs))


def swag_path(tree, ys, inset, sag):
    """Garland draped side to side down the tree, sagging between the sides."""
    pts, side = [], -1
    for a, b in zip(ys, ys[1:]):
        x0 = side * (half_width_at(tree, a) - inset)
        x1 = -side * (half_width_at(tree, b) - inset)
        for k in range(0 if not pts else 1, 25):
            u = k / 24
            pts.append((x0 + (x1 - x0) * u, a + (b - a) * u + sag * math.sin(math.pi * u)))
        side = -side
    return pts


def star(cx, cy, r_out, r_in_ratio=0.45, points=5):
    pts = []
    for k in range(points * 2):
        r = r_out if k % 2 == 0 else r_out * r_in_ratio
        a = -math.pi / 2 + k * math.pi / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return Polygon(pts)


def heart(cx, cy, size):
    """Heart about `size` mm wide, centred on (cx, cy)."""
    pts = []
    for k in range(120):
        t = 2 * math.pi * k / 120
        pts.append((16 * math.sin(t) ** 3,
                    -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))))
    h = Polygon(pts)
    x0, _, x1, _ = h.bounds
    h = affinity.scale(h, size / (x1 - x0), size / (x1 - x0), origin=(0, 0))
    x0, y0, x1, y1 = h.bounds
    return affinity.translate(h, cx - (x0 + x1) / 2, cy - (y0 + y1) / 2)


def teardrop(length, width):
    """A bow loop along +x: pinched at the knot, round at the far end."""
    pts = []
    for k in range(60):
        t = 2 * math.pi * k / 60
        pts.append((length / 2 * (1 - math.cos(t)),
                    width / 2 * math.sin(t) * math.sin(t / 2) ** 0.6))
    return Polygon(pts).buffer(0)


def tree_with_hole(green, red):
    """Green tree is the backing: give it a boss and hole at its tip."""
    boss = Point(0, HOLE_Y).buffer(HOLE_BOSS, quad_segs=16)
    return Earring(base=soften(unary_union([green, boss])), top=red)


# --------------------------------------------------------------------------
# The designs
# --------------------------------------------------------------------------

def garland():
    """Tiered fir wrapped in a red ribbon garland."""
    tree = tiered_tree(3, 38, 30)
    path = swag_path(tree, [10.5, 16.5, 22.5, 28.5, 34.0], inset=2.4, sag=2.4)
    ribbon = LineString(path).buffer(0.95, cap_style="round", quad_segs=8)
    return tree_with_hole(tree, ribbon)


def bow():
    """Sleek modern tree with a red bow tied near the top."""
    tree = smooth_tree(40, 28)
    cy = 14.0
    loops = [affinity.translate(affinity.rotate(teardrop(6.2, 5.0), a, origin=(0, 0)), 0, cy)
             for a in (-160, -20)]
    tails = [LineString([(0, cy), (s * 3.0, cy + 6.0)]).buffer(0.95, cap_style="flat")
             for s in (-1, 1)]
    knot = Point(0, cy).buffer(1.8, quad_segs=12)
    return tree_with_hole(tree, soften(unary_union([*loops, *tails, knot]), 0.35))


def star_topper():
    """Softly tiered tree with a red star crowning the top."""
    tree = soft_tree(4, 40, 30)
    topper = soften(star(0, HOLE_Y + 2.5, 7.4, 0.48), 0.4)
    # Green carries on under the star, just inside its edge, so the whole star
    # glues down instead of overhanging the narrow tip.
    under = topper.buffer(-0.6, join_style="round")
    return tree_with_hole(unary_union([tree, under]), topper)


def heart_tree():
    """Tiered fir with a red heart at its centre."""
    tree = tiered_tree(3, 38, 30, lift=1.4)
    return tree_with_hole(tree, heart(0, 23.0, 10.5))


def baubles():
    """Tiered fir strung with a red bead garland."""
    tree = tiered_tree(4, 40, 31, lift=1.8)
    line = LineString(swag_path(tree, [12.0, 19.5, 27.0, 34.5], inset=3.0, sag=2.6))
    string = line.buffer(0.85, cap_style="round", quad_segs=8)
    beads = [Point(line.interpolate(d, normalized=True).coords[0]).buffer(1.8, quad_segs=12)
             for d in (0.0, 0.1667, 0.3333, 0.5, 0.6667, 0.8333, 1.0)]
    return tree_with_hole(tree, unary_union([string, *beads]))


def car_keyring():
    """Keyring: red car with a green tree strapped to its roof (standing up).

    Drawn in the reference picture's pixel grid (472 px square), then scaled
    to KEYRING_H.  The red layer is the whole car plus the tree's exact
    outline, so the green tree glues down flush to the very edges.  The two
    roof straps are solid red: they are what joins tree and car into one
    backing piece.
    """
    def poly(pts, r=0.0):
        p = Polygon(pts)
        return p.buffer(-r, join_style="round").buffer(r, quad_segs=8) if r else p

    body = poly([(85, 8), (138, 8), (160, 14), (174, 34), (180, 70), (180, 445),
                 (174, 460), (160, 465), (85, 465)], r=6)
    cabin = poly([(176, 95), (262, 176), (275, 200), (275, 330), (262, 352), (176, 412)], r=8)
    wheels = [Point(87, y).buffer(40, quad_segs=24) for y in (93, 378)]
    tiers = [poly([(347, 8), (405, 150), (289, 150)]),
             poly([(347, 62), (412, 298), (275, 298)]),
             poly([(347, 165), (425, 392), (268, 392)])]
    trunk = box(331, 380, 363, 465)
    tree = unary_union([*tiers, trunk])

    # Score lines: window, pillar, door split, side crease, handles, hubs, straps.
    window = poly([(186, 112), (255, 182), (265, 202), (265, 328), (255, 346), (186, 395)], r=6)
    details = [window.exterior,
               LineString([(186, 260), (265, 260)]),
               LineString([(85, 260), (176, 260)]),
               LineString([(125, 18), (125, 455)]),
               box(141, 205, 157, 235).exterior, box(141, 330, 157, 360).exterior,
               *[Point(87, y).buffer(17, quad_segs=16).exterior for y in (93, 378)]]
    straps = [LineString([(262, 192), (408, 220)]).buffer(10, cap_style="round"),
              LineString([(262, 338), (408, 314)]).buffer(10, cap_style="round")]

    s = KEYRING_H / 457
    def mm(g):
        return affinity.scale(g, s, s, origin=(0, 0))
    tree_mm = soften(mm(tree))
    # Only the bridge from roof to tree is solid; it tucks under the green.
    bridges = [mm(st.intersection(box(0, 0, 330, 472))) for st in straps]
    red = soften(unary_union([mm(body), mm(cabin), *map(mm, wheels), tree_mm, *bridges]))
    tree_mm = tree_mm.intersection(red)
    strap_mm = [mm(st).exterior for st in straps]
    red_score = [mm(d) for d in details]
    green_score = [st.intersection(tree_mm.buffer(-0.4)) for st in strap_mm]

    # Hang from directly above the balance point (both layers counted), so it
    # hangs straight.  That lands in the dip over the cabin, so a tab carries
    # the hole up out of it.
    both = [(red.centroid, red.area), (tree_mm.centroid, tree_mm.area)]
    cx = sum(c.x * a for c, a in both) / sum(a for _, a in both)
    col = red.intersection(LineString([(cx, -50), (cx, 100)]))
    y_top = min(y for seg in parts(col) for _, y in seg.coords)
    hole = (cx, y_top - 1.5)
    tab = unary_union([Point(*hole).buffer(KEY_BOSS, quad_segs=16),
                       box(cx - KEY_BOSS, hole[1], cx + KEY_BOSS, y_top + 4)])
    # Fill the slivers of air boxed in by roof, straps and tree: cut out they
    # would just be thin, charred slots.  The ring hole is drilled later.
    red = Polygon(soften(unary_union([red, tab])).exterior)
    tree_mm = tree_mm.difference(Point(*hole).buffer(KEY_BOSS + 0.4))
    red_score = [g.difference(tab.buffer(0.6)) for g in red_score]

    hole_y = KEY_BOSS
    shift = lambda g: affinity.translate(g, -hole[0], hole_y - hole[1])
    return Earring(base=shift(red), top=shift(tree_mm), base_colour="red", top_colour="green",
                   base_score=[shift(g) for g in red_score if not g.is_empty],
                   top_score=[shift(g) for g in green_score if not g.is_empty],
                   hole_dia=KEY_HOLE_DIA, hole_y=hole_y)


DESIGNS = [
    ("garland", "Ribbon garland", garland),
    ("bow", "Bow", bow),
    ("star", "Star topper", star_topper),
    ("heart", "Heart", heart_tree),
    ("baubles", "Bauble string", baubles),
]


def drill(e):
    hole = Point(0, e.hole_y).buffer(e.hole_dia / 2, quad_segs=16)
    e.base = e.base.difference(hole)
    if e.top.intersects(hole):
        e.top = e.top.difference(hole)
    return e


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def thin_area(geom):
    """Wood narrower than MIN_FEATURE, by morphological opening."""
    r = MIN_FEATURE / 2
    return geom.difference(geom.buffer(-r, quad_segs=6).buffer(r, quad_segs=6)).area


def check(name, e):
    glue = e.top.intersection(e.base).area / e.top.area
    x0, y0, x1, y1 = unary_union([e.base, e.top]).bounds
    print(f"{name:11s} {x1 - x0:4.1f} x {y1 - y0:4.1f} mm   "
          f"pieces {len(parts(e.base))}+{len(parts(e.top))}   top glued down {glue:4.0%}   "
          f"thin wood {thin_area(e.base):3.1f} + {thin_area(e.top):3.1f} mm2")
    assert len(parts(e.base)) == 1 and len(parts(e.top)) == 1, f"{name}: a layer fell apart"
    wall = (Point(0, e.hole_y).buffer(e.hole_dia / 2 + MIN_FEATURE)
            .difference(Point(0, e.hole_y).buffer(e.hole_dia / 2 + 0.01)))
    assert wall.difference(e.base).area < 0.05, f"{name}: hole too close to the edge"


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def ring_d(coords):
    pts = list(coords)
    return "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pts[:-1]) + " Z"


def poly_d(geom):
    out = []
    for p in parts(geom):
        out.append(ring_d(p.exterior.coords))
        out.extend(ring_d(i.coords) for i in p.interiors)
    return " ".join(out)


def line_d(lines):
    out = []
    for ln in lines:
        for seg in parts(ln):
            if seg.geom_type == "LinearRing" or seg.is_closed:
                out.append(ring_d(seg.coords))
            else:
                out.append("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in seg.coords))
    return " ".join(out)


def mirror(g):
    return affinity.scale(g, -1, 1, origin=(0, 0))


def svg_doc(w, h, title, body):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}mm" height="{h:.1f}mm" '
            f'viewBox="0 0 {w:.1f} {h:.1f}">\n  <title>{title}</title>\n{body}\n</svg>\n')


def layer_svg(geom, score, bounds, title, pair=True):
    """One material's layer: a pair of earrings (second mirrored), or one piece."""
    x0, y0, x1, y1 = bounds
    w = x1 - x0
    place = [lambda g: affinity.translate(g, SHEET_PAD - x0, SHEET_PAD - y0)]
    if pair:
        place.append(lambda g: affinity.translate(mirror(g), SHEET_PAD + w + PAIR_GAP + x1,
                                                  SHEET_PAD - y0))
    body = [f'  <g id="cut"><path d="{poly_d(unary_union([p(geom) for p in place]))}" '
            f'fill="none" stroke="{CUT}" stroke-width="{STROKE_W}"/></g>']
    if score:
        lines = [p(g) for p in place for g in score]
        body.append(f'  <g id="score"><path d="{line_d(lines)}" fill="none" stroke="{SCORE}" '
                    f'stroke-width="{STROKE_W}"/></g>')
    width = len(place) * w + (len(place) - 1) * PAIR_GAP + 2 * SHEET_PAD
    return svg_doc(width, (y1 - y0) + 2 * SHEET_PAD, title, "\n".join(body))


def hardware(x, y_hole, keyring=False):
    """Display only: a jump ring and ear wire, or a split ring for the keyring."""
    gold = "#c9a54a"
    if keyring:
        return (f'  <circle cx="{x:.2f}" cy="{y_hole - 10.5:.2f}" r="12" fill="none" '
                f'stroke="#9aa0a6" stroke-width="1.4"/>\n'
                f'  <circle cx="{x:.2f}" cy="{y_hole - 10.5:.2f}" r="12" fill="none" '
                f'stroke="#d5d9dd" stroke-width="0.5"/>')
    return (f'  <circle cx="{x:.2f}" cy="{y_hole - 1.0:.2f}" r="2.6" fill="none" stroke="{gold}" '
            f'stroke-width="0.7"/>\n'
            f'  <path d="M{x:.2f},{y_hole - 3.6:.2f} c0,-2 -1.2,-3 -0.2,-6 c1.2,-3.5 6,-4 7,0.5 '
            f'c0.8,3.5 -1.5,6 -1.5,10" fill="none" stroke="{gold}" stroke-width="0.7" '
            f'stroke-linecap="round"/>\n'
            f'  <circle cx="{x:.2f}" cy="{y_hole - 3.6:.2f}" r="0.9" fill="{gold}"/>')


def stacked_body(e, dx, dy, flip=False):
    """Display only: the top layer glued over the backing, with a drop shadow."""
    f = mirror if flip else (lambda g: g)
    t = lambda g: affinity.translate(f(g), dx, dy)
    out = []
    for geom, score, colour, shadow in ((e.base, e.base_score, e.base_colour, False),
                                        (e.top, e.top_score, e.top_colour, True)):
        fill, edge, groove = COLOURS[colour]
        if shadow:
            out.append(f'  <path d="{poly_d(affinity.translate(t(geom), 0.35, 0.5))}" fill="#000" '
                       f'opacity="0.28" fill-rule="evenodd"/>')
        out.append(f'  <path d="{poly_d(t(geom))}" fill="{fill}" fill-rule="evenodd" '
                   f'stroke="{edge}" stroke-width="0.25"/>')
        if score:
            out.append(f'  <path d="{line_d([t(g) for g in score])}" fill="none" '
                       f'stroke="{groove}" stroke-width="0.3" stroke-linecap="round"/>')
    out.append(hardware(dx, dy + e.hole_y, keyring=e.hole_dia > HOLE_DIA))
    return "\n".join(out)


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    finished = []
    for key, label, build in DESIGNS:
        e = drill(build())
        check(key, e)
        finished.append((key, label, e))

        bounds = unary_union([e.base, e.top]).bounds
        layers = {e.base_colour: (e.base, e.base_score), e.top_colour: (e.top, e.top_score)}
        for colour, (geom, score) in layers.items():
            role = "backing" if colour == e.base_colour else "top"
            with open(os.path.join(SVG_DIR, f"{key}-{colour}.svg"), "w") as fh:
                fh.write(layer_svg(geom, score, bounds,
                                   f"{label} earrings - {colour} layer ({role})"))

        # Preview: the finished pair, mirrored, on their ear wires.
        x0, y0, x1, y1 = bounds
        top = 16.0
        w = 2 * (x1 - x0) + PAIR_GAP + 2 * SHEET_PAD
        h = (y1 - y0) + top + SHEET_PAD
        body = (f'  <rect width="{w:.1f}" height="{h:.1f}" fill="#faf7f2"/>\n'
                + stacked_body(e, SHEET_PAD - x0, top - y0) + "\n"
                + stacked_body(e, w - SHEET_PAD + x0, top - y0, flip=True))
        with open(os.path.join(PREVIEW_DIR, f"{key}.svg"), "w") as fh:
            fh.write(svg_doc(w, h, f"{label} earrings", body))

    # One overview strip of every design, single earring each.
    cell, top, h = 44.0, 16.0, 68.0
    body = [f'  <rect width="{cell * len(finished):.1f}" height="{h}" fill="#faf7f2"/>']
    for i, (key, label, e) in enumerate(finished):
        body.append(stacked_body(e, cell * i + cell / 2, top))
    with open(os.path.join(PREVIEW_DIR, "all-designs.svg"), "w") as fh:
        fh.write(svg_doc(cell * len(finished), h, "Christmas tree earrings", "\n".join(body)))
    return {key: e for key, _, e in finished}


def keyring():
    e = drill(car_keyring())
    check("car keyring", e)
    bounds = unary_union([e.base, e.top]).bounds
    for colour, geom, score, role in ((e.base_colour, e.base, e.base_score, "backing"),
                                      (e.top_colour, e.top, e.top_score, "top")):
        with open(os.path.join(SVG_DIR, f"car-keyring-{colour}.svg"), "w") as fh:
            fh.write(layer_svg(geom, score, bounds,
                               f"Tree on the car keyring - {colour} layer ({role})", pair=False))
    x0, y0, x1, y1 = bounds
    top = 28.0
    w, h = (x1 - x0) + 2 * SHEET_PAD, (y1 - y0) + top + SHEET_PAD
    body = (f'  <rect width="{w:.1f}" height="{h:.1f}" fill="#faf7f2"/>\n'
            + stacked_body(e, SHEET_PAD - x0, top - y0))
    with open(os.path.join(PREVIEW_DIR, "car-keyring.svg"), "w") as fh:
        fh.write(svg_doc(w, h, "Tree on the car keyring", body))
    return e


def cut_sheets(pieces):
    """One sheet per colour holding every piece of that colour, side by side.

    `pieces` is a list of (Earring, mirrored) - an earring pair is listed
    twice, once mirrored - so each colour is a single job on the laser.
    """
    for colour in ("green", "red"):
        cuts, scores, x = [], [], SHEET_PAD
        height = 0.0
        for e, flip in pieces:
            geom, score = ((e.base, e.base_score) if e.base_colour == colour
                           else (e.top, e.top_score))
            f = mirror if flip else (lambda g: g)
            x0, y0, x1, y1 = f(geom).bounds
            move = lambda g: affinity.translate(f(g), x - x0, SHEET_PAD - y0)
            cuts.append(move(geom))
            scores.extend(move(g) for g in score)
            x += (x1 - x0) + PAIR_GAP
            height = max(height, y1 - y0)
        body = [f'  <g id="cut"><path d="{poly_d(unary_union(cuts))}" fill="none" '
                f'stroke="{CUT}" stroke-width="{STROKE_W}"/></g>']
        if scores:
            body.append(f'  <g id="score"><path d="{line_d(scores)}" fill="none" '
                        f'stroke="{SCORE}" stroke-width="{STROKE_W}"/></g>')
        w = x - PAIR_GAP + SHEET_PAD
        with open(os.path.join(SVG_DIR, f"cut-sheet-{colour}.svg"), "w") as fh:
            fh.write(svg_doc(w, height + 2 * SHEET_PAD,
                             f"Cut sheet - everything in {colour}: car keyring and star earrings",
                             "\n".join(body)))
        print(f"cut-sheet-{colour}.svg  {w:.1f} x {height + 2 * SHEET_PAD:.1f} mm  "
              f"{len(pieces)} pieces")


if __name__ == "__main__":
    earrings = main()
    car = keyring()
    cut_sheets([(car, False), (earrings["star"], False), (earrings["star"], True)])
