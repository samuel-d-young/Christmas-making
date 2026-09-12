#!/usr/bin/env python3
"""Generate Glowforge-ready Christmas stocking SVGs for a 300 x 300 mm plywood sheet.

Output (all 300 x 300 mm artboards, 1 SVG user unit == 1 mm):

    svg/stocking-large.svg      one stocking, as big as the sheet allows
    svg/stocking-pair.svg       two stockings nested head-to-toe
    svg/stocking-ornaments.svg  six smaller stockings for kids to decorate

Colour convention in every file:

    #FF0000 (red)   stroke, no fill -> CUT
    #0000FF (blue)  stroke, no fill -> SCORE

Run:  python3 generate_stockings.py
"""

from __future__ import annotations

import math
import os

# --------------------------------------------------------------------------
# Sheet / machine constants
# --------------------------------------------------------------------------

SHEET = 300.0               # the plywood is 300 x 300 mm
MARGIN = 10.0               # keep art off the edges (Aura prints 292 x 292 mm)
SAFE = SHEET - 2 * MARGIN   # 280 x 280 mm of usable artboard
CLEARANCE = 5.0             # minimum gap between neighbouring cut lines, mm

CUT = "#FF0000"
SCORE = "#0000FF"
STROKE_W = 0.1              # thin stroke; the laser cuts the path centreline

# --------------------------------------------------------------------------
# The stocking outline
#
# Drawn once in its own millimetre "design space": toe pointing right, y down,
# heel at x = 0, sole at the bottom.  Every placed copy is a scaled/translated
# transform of this one path, so the shape only ever has to be right once.
#
# Named segments so the decorative score lines can be anchored to real points
# on the outline rather than to guessed coordinates.
# --------------------------------------------------------------------------

OUTLINE = [
    # --- cuff: a wide band with a gently bowed top edge, notched in at the
    # bottom on both sides.  The overhang and the notch are what make this
    # read as a Christmas stocking rather than a sock. ---
    ("cuff-top",   "C", (18, 6), (60, 0), (116, 0), (150, 5)),
    ("corner-tr",  "C", (150, 5), (154, 6), (156, 9), (156, 15)),
    ("cuff-right", "C", (156, 15), (157, 30), (157, 46), (156, 60)),
    ("notch-r",    "C", (156, 60), (156, 68), (149, 72), (141, 72)),
    ("shoulder-r", "C", (141, 72), (137, 72), (136, 77), (136, 82)),
    # --- leg: narrower than the cuff, easing into the ankle ---
    ("leg-front",  "C", (136, 82), (138, 122), (130, 160), (128, 196)),
    # --- foot: reaches well forward of the leg, big rounded toe ---
    ("instep",     "C", (128, 196), (127, 222), (144, 242), (176, 250)),
    ("toe-upper",  "C", (176, 250), (192, 254), (200, 262), (199, 274)),
    ("toe-tip",    "C", (199, 274), (198, 288), (186, 300), (166, 301)),
    ("sole-toe",   "C", (166, 301), (142, 302), (120, 294), (98, 293)),
    ("sole-heel",  "C", (98, 293), (78, 292), (56, 301), (38, 301)),
    ("heel-under", "C", (38, 301), (18, 301), (0, 288), (0, 264)),
    ("heel-back",  "C", (0, 264), (0, 234), (36, 218), (36, 186)),
    ("leg-back",   "C", (36, 186), (36, 140), (34, 110), (34, 82)),
    ("shoulder-l", "C", (34, 82), (34, 77), (31, 72), (27, 72)),
    ("notch-l",    "C", (27, 72), (19, 72), (12, 68), (12, 60)),
    ("cuff-left",  "C", (12, 60), (11, 46), (11, 30), (12, 15)),
    ("corner-tl",  "C", (12, 15), (12, 9), (14, 6), (18, 6)),
]

CUFF_Y = 84.0                       # closes off the cuff band for painting
HANG_HOLE_Y = 30.0                  # height of the ribbon hole within the cuff
HANG_HOLE_DIA = 10.0

# Score lines anchored to (segment name, t) points on the outline, with the
# two Bezier handles given as offsets from those anchors.
HEEL_SCORE = (("heel-back", 0.30), (24, 12), ("sole-heel", 0.72), (-6, -26))
TOE_SCORE = (("sole-toe", 0.15), (18, -4), ("toe-upper", 0.35), (3, 16))

FLATTEN_STEPS = 48                  # samples per cubic when measuring


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def cubic_point(p0, c1, c2, p1, t):
    u = 1.0 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * p0[0] + b * c1[0] + c * c2[0] + d * p1[0],
            a * p0[1] + b * c1[1] + c * c2[1] + d * p1[1])


def geometry(segments):
    """Strip the names off a named-segment list."""
    return [(s[1],) + tuple(s[2:]) for s in segments]


def point_on(name, t):
    """A point on the named outline segment at parameter t."""
    for seg in OUTLINE:
        if seg[0] == name:
            if seg[1] == "L":
                (ax, ay), (bx, by) = seg[2], seg[3]
                return (ax + t * (bx - ax), ay + t * (by - ay))
            return cubic_point(seg[2], seg[3], seg[4], seg[5], t)
    raise KeyError(name)


def score_curve(spec):
    """Build a one-segment cubic between two anchor points on the outline."""
    (a_name, a_t), (a_dx, a_dy), (b_name, b_t), (b_dx, b_dy) = spec
    a = point_on(a_name, a_t)
    b = point_on(b_name, b_t)
    return [("C", a, (a[0] + a_dx, a[1] + a_dy), (b[0] + b_dx, b[1] + b_dy), b)]


def flatten(segments, steps=FLATTEN_STEPS):
    """Turn a geometry segment list into a polyline."""
    pts = [segments[0][1]]
    for seg in segments:
        if seg[0] == "L":
            pts.append(seg[2])
        else:
            _, p0, c1, c2, p1 = seg
            for i in range(1, steps + 1):
                pts.append(cubic_point(p0, c1, c2, p1, i / steps))
    return pts


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def centroid_x(points):
    """Area-weighted centroid x of a closed polygon."""
    area = cx = 0.0
    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
        cross = ax * by - bx * ay
        area += cross
        cx += (ax + bx) * cross
    return cx / (3.0 * area)


BASE = geometry(OUTLINE)
BASE_BBOX = bbox(flatten(BASE))
# The foot sticks out to one side, so a hole in the middle of the cuff would
# hang crooked.  Putting it over the centre of mass makes the piece hang level.
HANG_HOLE_CENTRE = (centroid_x(flatten(BASE)), HANG_HOLE_Y)
BASE_W = BASE_BBOX[2] - BASE_BBOX[0]
BASE_H = BASE_BBOX[3] - BASE_BBOX[1]


def make_placer(scale, dx, dy, rotate180=False):
    """A point transform for one placed copy.

    Design-space coordinates are normalised so the outline's bounding box
    starts at (0, 0), optionally rotated a half turn, then scaled and moved so
    that the copy's bounding box top-left lands on (dx, dy).
    """
    x0, y0 = BASE_BBOX[0], BASE_BBOX[1]

    def place(pt):
        x, y = pt[0] - x0, pt[1] - y0
        if rotate180:
            x, y = BASE_W - x, BASE_H - y
        return (dx + x * scale, dy + y * scale)

    return place


def transform_segments(segments, place):
    return [(seg[0],) + tuple(place(p) for p in seg[1:]) for seg in segments]


# --------------------------------------------------------------------------
# Clearance checking - proves the nested layouts really do not overlap
# --------------------------------------------------------------------------

def outline_polygon(place, steps=FLATTEN_STEPS):
    return [place(p) for p in flatten(BASE, steps)]


def seg_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(px - qx, py - qy)


def min_gap(poly_a, poly_b):
    """Smallest distance between two placed outlines, in mm."""
    best = float("inf")
    edges_b = list(zip(poly_b, poly_b[1:] + poly_b[:1]))
    for px, py in poly_a:
        for (ax, ay), (bx, by) in edges_b:
            d = seg_distance(px, py, ax, ay, bx, by)
            if d < best:
                best = d
    return best


def verify(places, hole_dia):
    """Return (min gap between parts, min distance to the sheet edge)."""
    polys = [outline_polygon(place) for place, _ in places]
    gap = float("inf")
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            gap = min(gap, min_gap(polys[i], polys[j]))

    edge = float("inf")
    for poly in polys:
        for x, y in poly:
            edge = min(edge, x, y, SHEET - x, SHEET - y)

    # the ribbon hole must keep enough wood between it and the top edge
    bridge = float("inf")
    for place, scale in places:
        cx, cy = place(HANG_HOLE_CENTRE)
        r = hole_dia * scale / 2
        poly = outline_polygon(place)
        d = min(seg_distance(cx, cy, ax, ay, bx, by)
                for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]))
        bridge = min(bridge, d - r)
    return gap, edge, bridge


# --------------------------------------------------------------------------
# SVG output
# --------------------------------------------------------------------------

def fmt(v):
    return f"{v:.3f}".rstrip("0").rstrip(".")


def path_d(segments, close=True):
    parts = [f"M {fmt(segments[0][1][0])} {fmt(segments[0][1][1])}"]
    for seg in segments:
        if seg[0] == "L":
            parts.append(f"L {fmt(seg[2][0])} {fmt(seg[2][1])}")
        else:
            _, _p0, c1, c2, p1 = seg
            parts.append("C {} {} {} {} {} {}".format(
                fmt(c1[0]), fmt(c1[1]), fmt(c2[0]), fmt(c2[1]),
                fmt(p1[0]), fmt(p1[1])))
    if close:
        parts.append("Z")
    return " ".join(parts)


def svg_document(body, title, note, sizes):
    measure = "  ".join(f"{w:.1f} x {h:.1f} mm" for w, h in sizes[:1])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- {title}
     {note}
     Sheet 300 x 300 mm.  1 SVG user unit = 1 mm.
     Scale check after import: one stocking measures {measure}.
     RED  #FF0000 strokes  = CUT
     BLUE #0000FF strokes  = SCORE
     Generated by generate_stockings.py - regenerate rather than hand-edit. -->
<svg xmlns="http://www.w3.org/2000/svg" version="1.1"
     width="{fmt(SHEET)}mm" height="{fmt(SHEET)}mm"
     viewBox="0 0 {fmt(SHEET)} {fmt(SHEET)}">
  <title>{title}</title>
{body}</svg>
"""


def group(gid, colour, paths, circles=()):
    if not paths and not circles:
        return ""
    lines = [f'  <g id="{gid}" fill="none" stroke="{colour}" '
             f'stroke-width="{fmt(STROKE_W)}" '
             f'stroke-linecap="round" stroke-linejoin="round">']
    for d in paths:
        lines.append(f'    <path d="{d}"/>')
    for cx, cy, r in circles:
        lines.append(f'    <circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}"/>')
    lines.append("  </g>")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# One placed stocking
# --------------------------------------------------------------------------

def cuff_line():
    """Horizontal score across the leg at CUFF_Y, clipped to the outline."""
    poly = flatten(BASE)
    xs = []
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay - CUFF_Y) * (by - CUFF_Y) < 0:
            xs.append(ax + (CUFF_Y - ay) / (by - ay) * (bx - ax))
    xs.sort()
    return [("L", (xs[0], CUFF_Y), (xs[-1], CUFF_Y))]


def stocking(place, scale, hang_hole=True, scores=True, hole_dia=HANG_HOLE_DIA):
    """(cut path, hole circles, score paths) for one placed stocking."""
    cut = path_d(transform_segments(BASE, place))

    circles = []
    if hang_hole:
        cx, cy = place(HANG_HOLE_CENTRE)
        circles.append((cx, cy, hole_dia * scale / 2))

    score_paths = []
    if scores:
        for segs in (cuff_line(), score_curve(HEEL_SCORE), score_curve(TOE_SCORE)):
            score_paths.append(path_d(transform_segments(segs, place), close=False))
    return cut, circles, score_paths


def assemble(places, title, note, hole_dia=HANG_HOLE_DIA):
    cuts, circles, scores, sizes = [], [], [], []
    for place, scale in places:
        cut, ci, sc = stocking(place, scale, hole_dia=hole_dia)
        cuts.append(cut)
        circles.extend(ci)
        scores.extend(sc)
        sizes.append((BASE_W * scale, BASE_H * scale))
    body = group("cut", CUT, cuts, circles) + group("score", SCORE, scores)
    return svg_document(body, title, note, sizes), sizes


# --------------------------------------------------------------------------
# Layouts
# --------------------------------------------------------------------------

def layout_large():
    scale = min(SAFE / BASE_W, SAFE / BASE_H)
    w, h = BASE_W * scale, BASE_H * scale
    place = make_placer(scale, (SHEET - w) / 2, (SHEET - h) / 2)
    return [(place, scale)]


def layout_pair():
    """Two stockings nested head-to-toe, at the largest scale that still
    leaves CLEARANCE mm between them."""
    COARSE = 12         # cheap polygons for the search; exact check comes later

    def slide_in(scale):
        """Smallest x offset for the upside-down copy that keeps CLEARANCE."""
        w = BASE_W * scale
        poly_a = outline_polygon(make_placer(scale, 0.0, 0.0), COARSE)

        def gap_at(dx):
            flipped = make_placer(scale, dx, 0.0, rotate180=True)
            return min_gap(poly_a, outline_polygon(flipped, COARSE))

        hi = SAFE - w
        if hi < 0 or gap_at(hi) < CLEARANCE:
            return None
        lo = 0.0
        for _ in range(16):
            mid = (lo + hi) / 2
            if gap_at(mid) >= CLEARANCE:
                hi = mid
            else:
                lo = mid
        return hi

    best = None
    lo, hi = 0.30, SAFE / BASE_H
    for _ in range(12):
        mid = (lo + hi) / 2
        w = BASE_W * mid
        dx = slide_in(mid) if BASE_H * mid <= SAFE else None
        if dx is not None and dx + w <= SAFE:
            best, lo = (mid, dx, dx + w), mid
        else:
            hi = mid

    scale, dx_b, used_w = best
    ox = (SHEET - used_w) / 2
    oy = (SHEET - BASE_H * scale) / 2
    return [(make_placer(scale, ox, oy), scale),
            (make_placer(scale, ox + dx_b, oy, rotate180=True), scale)]


def layout_ornaments(cols=3, rows=2):
    gap = CLEARANCE + 1.0
    scale = min((SAFE - gap * (cols - 1)) / cols / BASE_W,
                (SAFE - gap * (rows - 1)) / rows / BASE_H)
    w, h = BASE_W * scale, BASE_H * scale
    ox = (SHEET - (cols * w + gap * (cols - 1))) / 2
    oy = (SHEET - (rows * h + gap * (rows - 1))) / 2
    return [(make_placer(scale, ox + c * (w + gap), oy + r * (h + gap)), scale)
            for r in range(rows) for c in range(cols)]


# --------------------------------------------------------------------------

JOBS = [
    ("stocking-large.svg", layout_large, "Large stocking template",
     "One large stocking - the main tracing template / wall hanger.",
     HANG_HOLE_DIA),
    ("stocking-pair.svg", layout_pair, "Stocking pair",
     "Two stockings nested head-to-toe on one sheet.",
     HANG_HOLE_DIA),
    ("stocking-ornaments.svg", layout_ornaments, "Stocking ornaments x6",
     "Six smaller stockings for kids to paint, name and hang.",
     8.0),
]


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")
    os.makedirs(out, exist_ok=True)

    for filename, builder, title, note, hole in JOBS:
        places = builder()
        doc, sizes = assemble(places, title, note, hole_dia=hole)
        with open(os.path.join(out, filename), "w") as fh:
            fh.write(doc)
        w, h = sizes[0]
        gap, edge, bridge = verify(places, hole)
        gap_txt = "n/a  " if gap == float("inf") else f"{gap:5.1f}"
        print(f"{filename:26s} {len(sizes)} up  {w:6.1f} x {h:6.1f} mm   "
              f"part gap {gap_txt} mm   sheet edge {edge:5.1f} mm   "
              f"hole bridge {bridge:5.1f} mm")


if __name__ == "__main__":
    main()
