#!/usr/bin/env python3
"""Generate 'Merry Christmas from the Youngs' front-door pieces for a
Glowforge Aura on a 300 x 300 mm sheet.

Three concepts, every one a 300 x 300 mm artboard (1 SVG unit == 1 mm):

    svg/door-script.svg   freestanding script, welded together by a swash
    svg/door-wreath.svg   script welded across a wreath ring with holly
    svg/door-bauble.svg   bauble-shaped plaque with the script engraved

Colour convention, matching stocking-template:

    #FF0000 (red)   stroke, no fill -> CUT
    #0000FF (blue)  stroke, no fill -> SCORE
    #000000 (black) fill            -> ENGRAVE

preview/*.svg are display copies (wood fill, thick lines) for the README.

Needs:  pip install uharfbuzz fonttools skia-pathops shapely
Run:    python3 generate_door_sign.py
"""

from __future__ import annotations

import math
import os

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

from scripttext import text_geometry

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
SVG_DIR = os.path.join(HERE, "svg")
PREVIEW_DIR = os.path.join(HERE, "preview")

# --------------------------------------------------------------------------
# Sheet / machine constants
# --------------------------------------------------------------------------

SHEET = 300.0
MARGIN = 10.0               # Aura prints within ~292 x 292 mm
CX = SHEET / 2

CUT = "#FF0000"
SCORE = "#0000FF"
ENGRAVE = "#000000"
STROKE_W = 0.1

# Script hairlines are too fine to survive in 3 mm ply, so every cut letter is
# grown outward by this much before welding.  Engraved text is left as drawn.
CUT_TEXT_GROW = 0.5
BRIDGE_W = 2.2              # width of the ties that join loose letters
MIN_FEATURE = 1.6           # thinnest wood we are happy with in 3 mm ply

GREAT_VIBES = os.path.join(FONTS, "GreatVibes-Regular.ttf")
PINYON = os.path.join(FONTS, "PinyonScript-Regular.ttf")
PARISIENNE = os.path.join(FONTS, "Parisienne-Regular.ttf")

LINE_1 = "Merry Christmas"
LINE_2 = "from the Youngs"


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def text_line(font, text, width, cx, baseline):
    """One line of script scaled to an exact ink width, centred on cx."""
    geom, _ = text_geometry(font, text, 40.0)
    x0, _, x1, _ = geom.bounds
    s = width / (x1 - x0)
    geom = affinity.scale(geom, s, s, origin=(0, 0))
    x0, _, x1, _ = geom.bounds
    return affinity.translate(geom, cx - (x0 + x1) / 2, baseline)


def bezier(p0, p1, p2, p3, n=120):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def swash(points, w_mid, w_end):
    """A calligraphic stroke along a polyline: fat in the middle, fine at the ends."""
    left, right = [], []
    n = len(points)
    for i, (x, y) in enumerate(points):
        a = points[max(i - 1, 0)]
        b = points[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        t = i / (n - 1)
        hw = (w_end + (w_mid - w_end) * math.sin(math.pi * t) ** 1.5) / 2
        left.append((x + nx * hw, y + ny * hw))
        right.append((x - nx * hw, y - ny * hw))
    return Polygon(left + right[::-1]).buffer(0)


def holly_leaf(cx, cy, length, angle_deg, width_ratio=0.42, spikes=3):
    """Holly leaf with `spikes` points down each side and a pointed tip.

    Built along +x from its stem at the origin, then rotated and placed so the
    stem sits at (cx, cy).  Edges between spikes bow inward, which is what
    reads as holly rather than as a generic leaf.
    """
    half = length * width_ratio / 2
    ts = [k / (spikes + 1) for k in range(spikes + 2)]   # stem .. tip
    def edge(sign):
        pts = []
        for k in range(len(ts) - 1):
            t0, t1 = ts[k], ts[k + 1]
            w0 = 0.0 if k == 0 else half * math.sin(math.pi * t0) ** 0.7
            w1 = 0.0 if k + 1 == len(ts) - 1 else half * math.sin(math.pi * t1) ** 0.7
            p0 = (t0 * length, sign * w0)
            p2 = (t1 * length, sign * w1)
            mid_w = 0.55 * (w0 + w1) / 2 + 0.25 * half * math.sin(math.pi * (t0 + t1) / 2)
            p1 = ((t0 + t1) / 2 * length, sign * mid_w)
            for j in range(12):
                u = j / 12
                pts.append(((1 - u) ** 2 * p0[0] + 2 * u * (1 - u) * p1[0] + u * u * p2[0],
                            (1 - u) ** 2 * p0[1] + 2 * u * (1 - u) * p1[1] + u * u * p2[1]))
        pts.append((length, 0.0))
        return pts

    upper = edge(-1)
    lower = edge(1)
    leaf = Polygon(upper + lower[::-1][1:]).buffer(0)
    vein = LineString([(length * 0.08, 0), (length * 0.86, 0)])
    leaf = affinity.translate(affinity.rotate(leaf, angle_deg, origin=(0, 0)), cx, cy)
    vein = affinity.translate(affinity.rotate(vein, angle_deg, origin=(0, 0)), cx, cy)
    return leaf, vein


def parts(geom):
    return list(getattr(geom, "geoms", [geom]))


def weld(geom, width=BRIDGE_W):
    """Join every loose island to the main body with a short tie.

    Ties run between nearest points and bite 0.6 mm into both sides so they
    weld rather than kiss.  Returns (one polygon, number of ties added).
    """
    pieces = sorted(parts(geom), key=lambda p: -p.area)
    body, rest, ties = pieces[0], pieces[1:], 0
    while rest:
        rest.sort(key=body.distance)
        p = rest.pop(0)
        a, b = nearest_points(body, p)
        dx, dy = b.x - a.x, b.y - a.y
        ln = math.hypot(dx, dy) or 1.0
        ux, uy = dx / ln, dy / ln
        tie = LineString([(a.x - ux * 0.6, a.y - uy * 0.6), (b.x + ux * 0.6, b.y + uy * 0.6)])
        body = unary_union([body, p, tie.buffer(width / 2, quad_segs=6)])
        ties += 1
    return body, ties


def hang_tab(geom, x_lo, x_hi, r_out=4.8, r_hole=2.0):
    """Ribbon tab on the highest point of the art between x_lo and x_hi.

    Put it over the centroid and the piece hangs level from one ribbon.
    """
    window = geom.intersection(box(x_lo, 0, x_hi, SHEET))
    top = min(parts(window), key=lambda p: p.bounds[1])
    ys = [(y, x) for x, y in top.exterior.coords if x_lo <= x <= x_hi]
    y, x = min(ys)
    c = Point(x, y + 1.5)
    return c.buffer(r_out, quad_segs=16), c.buffer(r_hole, quad_segs=16)


def thinnest_report(geom):
    """Area of wood thinner than MIN_FEATURE, found by a morphological opening."""
    r = MIN_FEATURE / 2
    opened = geom.buffer(-r, quad_segs=6).buffer(r, quad_segs=6)
    return geom.difference(opened).area


def ring(cx, cy, r_out, r_in):
    return Point(cx, cy).buffer(r_out, quad_segs=64).difference(Point(cx, cy).buffer(r_in, quad_segs=64))


# --------------------------------------------------------------------------
# SVG output
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
        for seg in getattr(ln, "geoms", [ln]):
            out.append("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in seg.coords))
    return " ".join(out)


def write_svg(name, title, cut=None, score=(), engrave=None, preview=False):
    if preview:
        wood, char, groove = "#d9b38c", "#5a3a22", "#8a5a36"
        body = [f'  <rect width="{SHEET:g}" height="{SHEET:g}" fill="#ffffff"/>',
                f'  <rect x="0.25" y="0.25" width="299.5" height="299.5" fill="none" '
                f'stroke="#c9c9c9" stroke-width="0.5" stroke-dasharray="3 2"/>']
        if cut is not None:
            body.append(f'  <path d="{poly_d(cut)}" fill="{wood}" fill-rule="evenodd" '
                        f'stroke="{char}" stroke-width="0.45"/>')
        if score:
            body.append(f'  <path d="{line_d(score)}" fill="none" stroke="{groove}" '
                        f'stroke-width="0.5" stroke-linecap="round"/>')
        if engrave is not None:
            body.append(f'  <path d="{poly_d(engrave)}" fill="{char}" fill-rule="evenodd"/>')
    else:
        body = []
        if cut is not None:
            body.append(f'  <g id="cut"><path d="{poly_d(cut)}" fill="none" stroke="{CUT}" '
                        f'stroke-width="{STROKE_W}"/></g>')
        if score:
            body.append(f'  <g id="score"><path d="{line_d(score)}" fill="none" stroke="{SCORE}" '
                        f'stroke-width="{STROKE_W}"/></g>')
        if engrave is not None:
            body.append(f'  <g id="engrave"><path d="{poly_d(engrave)}" fill="{ENGRAVE}" '
                        f'fill-rule="evenodd" stroke="none"/></g>')
    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET:g}mm" height="{SHEET:g}mm" '
           f'viewBox="0 0 {SHEET:g} {SHEET:g}">\n'
           f'  <title>{title}</title>\n' + "\n".join(body) + "\n</svg>\n")
    folder = PREVIEW_DIR if preview else SVG_DIR
    with open(os.path.join(folder, name), "w") as fh:
        fh.write(svg)


def emit(name, title, **layers):
    write_svg(name, title, **layers)
    write_svg(name, title, preview=True, **layers)


def report(name, cut, ties=0, engrave=None):
    x0, y0, x1, y1 = (cut if cut is not None else engrave).bounds
    edge = min(x0, y0, SHEET - x1, SHEET - y1)
    msg = f"{name:25s} {x1 - x0:5.1f} x {y1 - y0:5.1f} mm  sheet edge {edge:4.1f} mm"
    if cut is not None:
        msg += f"  pieces {len(parts(cut))}  ties {ties:2d}  thin wood {thinnest_report(cut):4.1f} mm2"
    print(msg)
    assert edge >= MARGIN - 0.01, f"{name}: art is inside the {MARGIN} mm margin"
    if cut is not None:
        assert len(parts(cut)) == 1, f"{name}: cut art fell apart into {len(parts(cut))} pieces"


# --------------------------------------------------------------------------
# Concept 1: freestanding script, held together by one swash
# --------------------------------------------------------------------------

def door_script():
    l1 = text_line(GREAT_VIBES, LINE_1, 272, CX, 128)
    l2 = text_line(GREAT_VIBES, LINE_2, 182, CX + 12, 170)
    letters = unary_union([l1, l2]).buffer(CUT_TEXT_GROW, quad_segs=8)

    # The swash leaves the foot of the M, dips under the second line through
    # its descenders, and lifts back up to finish under the last s.
    path = bezier((30, 131), (60, 196), (215, 202), (279, 128))
    flourish = swash(path, 3.8, 1.9)

    art, ties = weld(unary_union([letters, flourish]))
    tab, hole = hang_tab(art, art.centroid.x - 4, art.centroid.x + 4)
    art = unary_union([art, tab]).difference(hole)
    return art, ties


# --------------------------------------------------------------------------
# Concept 2: script welded across a wreath ring, holly at the foot
# --------------------------------------------------------------------------

WREATH_CY, WREATH_R_OUT, WREATH_R_IN = 146.0, 134.0, 123.0
HANG_HOLE_DIA = 5.0         # ribbon hole through both layers, top of the band


def wreath_hang_hole():
    band_mid = (WREATH_R_OUT + WREATH_R_IN) / 2
    return Point(CX, WREATH_CY - band_mid).buffer(HANG_HOLE_DIA / 2, quad_segs=24)


def door_wreath():
    cy, r_out, r_in = WREATH_CY, WREATH_R_OUT, WREATH_R_IN
    wreath = ring(CX, cy, r_out, r_in)

    # Ribbon-wrapped look: short scored diagonals all the way round the band,
    # skipped where the holly sits.
    wraps = []
    for k in range(48):
        a = math.radians(k * 7.5)
        if abs(math.degrees(a) - 90) < 34:       # under the holly (y down)
            continue
        p = (CX + (r_in + 2) * math.cos(a), cy + (r_in + 2) * math.sin(a))
        q = (CX + (r_out - 2) * math.cos(a + 0.05), cy + (r_out - 2) * math.sin(a + 0.05))
        wraps.append(LineString([p, q]))

    # Line one is sized so both ends run into the ring and weld to it.
    half_chord = math.sqrt(r_in ** 2 - (cy - 130) ** 2)
    l1 = text_line(GREAT_VIBES, LINE_1, 2 * half_chord + 6, CX, 140)
    l2 = text_line(GREAT_VIBES, LINE_2, 168, CX + 6, 196)
    letters = unary_union([l1, l2]).buffer(CUT_TEXT_GROW, quad_segs=8)

    # A rail from ring to ring that the second line sits on: flat under the
    # words, sweeping up into the ring past either end.
    rail_y = 198.6
    reach = math.sqrt(r_in ** 2 - (rail_y - 14 - cy) ** 2) + 3
    left = bezier((CX - reach, rail_y - 14), (CX - reach + 22, rail_y - 2),
                  (CX - 100, rail_y), (CX - 78, rail_y), 40)
    right = [(2 * CX - x, y) for x, y in left[::-1]]
    flat = [(CX - 78 + 156 * i / 40, rail_y) for i in range(1, 40)]
    rail = swash(left + flat + right, 3.4, 2.4)

    hy = cy + r_out - 6
    leaves, veins = [], []
    for lx, ang, ln in ((CX - 5, 198, 60), (CX + 5, -18, 60), (CX - 4, 220, 44), (CX + 4, -40, 44)):
        leaf, vein = holly_leaf(lx, hy, ln, ang)
        leaves.append(leaf)
        veins.append(vein)
    berries = [Point(CX + dx, hy + dy).buffer(6.5, quad_segs=24)
               for dx, dy in ((-7, -13), (7, -13), (0, -24))]

    # Fill the slivers of air trapped between berries and leaves: they would
    # only burn out as charred specks.
    knot = Point(CX, hy - 9).buffer(6.5, quad_segs=24)
    holly = unary_union([*leaves, *berries, knot])
    holly = unary_union([Polygon(p.exterior) for p in parts(holly)])

    art = unary_union([wreath, letters, rail, holly])
    art, ties = weld(art)
    # Trim to the backing disc so no holly spike overhangs the rim.
    hole = wreath_hang_hole()
    art = art.intersection(Point(CX, cy).buffer(r_out, quad_segs=96)).difference(hole)
    veins = [v.difference(unary_union(berries).buffer(0.8)) for v in veins]
    wraps = [w.intersection(wreath.buffer(-1.2)).difference(art.difference(wreath).buffer(1.0))
              .difference(hole.buffer(1.5)) for w in wraps]
    return art, ties, [w for w in wraps if not w.is_empty] + veins


def door_wreath_backing():
    """Bottom layer: a plain disc the wreath glues onto, flush at the rim."""
    disc = Point(CX, WREATH_CY).buffer(WREATH_R_OUT, quad_segs=96)
    return disc.difference(wreath_hang_hole())


def layered_preview(name, title, top, top_score, backing):
    """Display-only: the wreath glued on a painted backing disc."""
    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET:g}mm" height="{SHEET:g}mm" '
           f'viewBox="0 0 {SHEET:g} {SHEET:g}">\n  <title>{title}</title>\n'
           f'  <rect width="{SHEET:g}" height="{SHEET:g}" fill="#ffffff"/>\n'
           f'  <path d="{poly_d(backing)}" fill="#2f5d46" fill-rule="evenodd" stroke="#1d3a2c" '
           f'stroke-width="0.45"/>\n'
           f'  <path d="{poly_d(top.buffer(0.8).difference(top))}" fill="#000000" opacity="0.25" '
           f'fill-rule="evenodd" transform="translate(0.8 1.2)"/>\n'
           f'  <path d="{poly_d(top)}" fill="#f4efe6" fill-rule="evenodd" stroke="#b9ab95" '
           f'stroke-width="0.35"/>\n'
           f'  <path d="{line_d(top_score)}" fill="none" stroke="#b9ab95" stroke-width="0.5" '
           f'stroke-linecap="round"/>\n</svg>\n')
    with open(os.path.join(PREVIEW_DIR, name), "w") as fh:
        fh.write(svg)


# --------------------------------------------------------------------------
# Concept 3: bauble plaque, script engraved
# --------------------------------------------------------------------------

def door_bauble():
    cy, r = 168.0, 112.0
    ball = Point(CX, cy).buffer(r, quad_segs=96)
    cap = box(CX - 22, cy - r - 22, CX + 22, cy - r + 6).buffer(2.5, quad_segs=8)
    loop = ring(CX, cy - r - 30, 11, 5.5)
    loop_hole = Point(CX, cy - r - 30).buffer(5.5, quad_segs=32)
    outline = unary_union([ball, cap, Point(CX, cy - r - 30).buffer(11, quad_segs=32), loop])
    outline = outline.difference(loop_hole)

    score = [Point(CX, cy).buffer(r - 7, quad_segs=96).exterior]
    for x in (-11, 0, 11):                                  # cap ridges
        score.append(LineString([(CX + x, cy - r - 17), (CX + x, cy - r + 2)]))

    # Two zig-zag bands, the classic glass-bauble decoration.
    inner = Point(CX, cy).buffer(r - 7, quad_segs=96)
    for y0, h in ((cy - 74, 12), (cy + 62, 12)):
        score.append(LineString([(0, y0), (SHEET, y0)]).intersection(inner))
        score.append(LineString([(0, y0 + h), (SHEET, y0 + h)]).intersection(inner))
        zz = [(x, y0 + (h if i % 2 else 0)) for i, x in enumerate(range(0, 301, 8))]
        score.append(LineString(zz).intersection(inner))

    l1 = text_line(PINYON, "Merry", 118, CX - 22, cy - 14)
    l2 = text_line(PINYON, "Christmas", 170, CX + 6, cy + 26)
    l3 = text_line(PINYON, LINE_2, 120, CX, cy + 52)
    engrave = unary_union([l1, l2, l3])
    return outline, score, engrave


def font_options():
    """Preview-only sheet comparing the bundled script fonts."""
    rows = []
    for i, (label, font) in enumerate((("Great Vibes", GREAT_VIBES),
                                       ("Pinyon Script", PINYON),
                                       ("Parisienne", PARISIENNE))):
        top = 20 + i * 92
        l1 = text_line(font, LINE_1, 250, CX, top + 46)
        l2 = text_line(font, LINE_2, 160, CX, top + 78)
        rows.append(f'  <text x="12" y="{top + 4}" font-family="sans-serif" font-size="6" '
                    f'fill="#888">{label}</text>')
        rows.append(f'  <path d="{poly_d(unary_union([l1, l2]))}" fill="#5a3a22" fill-rule="evenodd"/>')
    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET:g}mm" height="{SHEET:g}mm" '
           f'viewBox="0 0 {SHEET:g} {SHEET:g}">\n  <title>Script font options</title>\n'
           f'  <rect width="{SHEET:g}" height="{SHEET:g}" fill="#ffffff"/>\n'
           + "\n".join(rows) + "\n</svg>\n")
    with open(os.path.join(PREVIEW_DIR, "font-options.svg"), "w") as fh:
        fh.write(svg)


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    art, ties = door_script()
    emit("door-script.svg", "Merry Christmas from the Youngs - script", cut=art)
    report("door-script.svg", art, ties)

    art, ties, score = door_wreath()
    emit("door-wreath.svg", "Merry Christmas from the Youngs - wreath", cut=art, score=score)
    report("door-wreath.svg", art, ties)

    backing = door_wreath_backing()
    emit("door-wreath-backing.svg", "Merry Christmas from the Youngs - wreath backing", cut=backing)
    report("door-wreath-backing.svg", backing)
    layered_preview("door-wreath-layered.svg", "Wreath on its backing disc", art, score, backing)

    outline, score, engrave = door_bauble()
    emit("door-bauble.svg", "Merry Christmas from the Youngs - bauble",
         cut=outline, score=score, engrave=engrave)
    report("door-bauble.svg", outline)

    font_options()


if __name__ == "__main__":
    main()
