#!/usr/bin/env python3
"""Generate 'Zac' and 'Jake' layered name hangers for the wall, for a
Glowforge Aura on a 300 x 300 mm sheet.

Each name is two layers: the name in red script, glued onto a green backing
that follows the letters with an even border.  The backing ties every letter
together, so the red name can be as delicate as the script wants.  Two
ribbon holes in the backing, set either side of the balance point, let it
hang level.

One file per layer per name, each a 300 x 300 mm artboard (1 SVG unit == 1 mm):

    svg/<name>-green.svg   the backing        (cut from green stock)
    svg/<name>-red.svg     the name           (cut from red stock)

Both layers sit in their glued-up positions, so the files double as a
placement guide.  Colour convention: #FF0000 stroke -> CUT.

Needs:  pip install uharfbuzz fonttools skia-pathops shapely
Run:    python3 generate_name_hangers.py
"""

from __future__ import annotations

import os
import sys

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "door-sign"))
sys.path.insert(0, os.path.join(HERE, "..", "earrings"))

from generate_door_sign import GREAT_VIBES, weld          # noqa: E402
from generate_earrings import parts, poly_d                # noqa: E402
from scripttext import text_geometry                       # noqa: E402

SVG_DIR = os.path.join(HERE, "svg")
PREVIEW_DIR = os.path.join(HERE, "preview")

NAMES = ["Zac", "Jake"]

SHEET = 300.0
MARGIN = 10.0
CX = SHEET / 2
CUT = "#FF0000"
STROKE_W = 0.1

NAME_W = 240.0              # ink width of the longest name; the others share its scale
NAME_GROW = 0.5             # thicken script hairlines so they survive in ply
BORDER = 6.0                # green showing round the red letters
HOLE_DIA = 5.0              # ribbon holes
HOLE_TAB = 7.0              # radius of the tab carrying each hole
HOLE_DROP = 40.0            # how far below the very top a ribbon hole may sit


def name_layer(name):
    """The name as one welded red piece, centred on the sheet."""
    longest, _ = text_geometry(GREAT_VIBES, max(NAMES, key=len), 40.0)
    s = NAME_W / (longest.bounds[2] - longest.bounds[0])
    g, _ = text_geometry(GREAT_VIBES, name, 40.0)
    g = affinity.scale(g, s, s, origin=(0, 0))
    x0, y0, x1, y1 = g.bounds
    g = affinity.translate(g, CX - (x0 + x1) / 2, SHEET / 2 - (y0 + y1) / 2 + 6)
    return weld(g.buffer(NAME_GROW, quad_segs=8))


def top_at(geom, x):
    col = geom.intersection(LineString([(x, -10), (x, SHEET + 10)]))
    return min(y for seg in parts(col) for _, y in seg.coords)


def backing_layer(red):
    """Even border round the letters, holes filled, plus two ribbon tabs."""
    back = red.buffer(BORDER, quad_segs=16)
    back = unary_union([Polygon(p.exterior) for p in parts(back)])
    back, _ = weld(back, width=8.0)

    # Holes either side of the balance point of both layers together, as far
    # apart as they can go while both still sit near the top edge.
    cx = (red.centroid.x * red.area + back.centroid.x * back.area) / (red.area + back.area)
    top = back.bounds[1]
    half = max(d for d in range(10, int(back.bounds[2] - back.bounds[0]) // 2)
               if back.intersects(LineString([(cx - d, -10), (cx - d, SHEET)]))
               and back.intersects(LineString([(cx + d, -10), (cx + d, SHEET)]))
               and max(top_at(back, cx - d), top_at(back, cx + d)) - top <= HOLE_DROP)
    holes, tabs = [], []
    for x in (cx - half, cx + half):
        c = Point(x, top_at(back, x) - 1.0)
        tabs.append(c.buffer(HOLE_TAB, quad_segs=24))
        holes.append(c.buffer(HOLE_DIA / 2, quad_segs=24))
    back = unary_union([back, *tabs]).buffer(2.0).buffer(-2.0)      # blend tabs in
    return back.difference(unary_union(holes)), holes


def svg_doc(title, body):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET:g}mm" height="{SHEET:g}mm" '
            f'viewBox="0 0 {SHEET:g} {SHEET:g}">\n  <title>{title}</title>\n{body}\n</svg>\n')


def cut(geom):
    return f'  <path d="{poly_d(geom)}" fill="none" stroke="{CUT}" stroke-width="{STROKE_W}"/>'


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    for name in NAMES:
        key = name.lower()
        red, ties = name_layer(name)
        green, holes = backing_layer(red)

        with open(os.path.join(SVG_DIR, f"{key}-green.svg"), "w") as fh:
            fh.write(svg_doc(f"{name} name hanger - green layer (backing)", cut(green)))
        with open(os.path.join(SVG_DIR, f"{key}-red.svg"), "w") as fh:
            fh.write(svg_doc(f"{name} name hanger - red layer (name)", cut(red)))

        # Preview: glued up, hung from a ribbon through both holes.
        (hx0, hy0), (hx1, hy1) = [h.centroid.coords[0] for h in holes]
        peak = min(hy0, hy1) - 30
        shadow = affinity.translate(red, 1.0, 1.4)
        body = (f'  <rect width="{SHEET:g}" height="{SHEET:g}" fill="#faf7f2"/>\n'
                f'  <path d="M{hx0:.1f},{hy0:.1f} L{(hx0 + hx1) / 2:.1f},{peak:.1f} '
                f'L{hx1:.1f},{hy1:.1f}" fill="none" stroke="#b8932f" stroke-width="1.4"/>\n'
                f'  <path d="{poly_d(green)}" fill="#2e7d4f" fill-rule="evenodd" stroke="#1d5234" '
                f'stroke-width="0.6"/>\n'
                f'  <path d="{poly_d(shadow)}" fill="#000" opacity="0.28" fill-rule="evenodd"/>\n'
                f'  <path d="{poly_d(red)}" fill="#c8262c" fill-rule="evenodd" stroke="#8a1418" '
                f'stroke-width="0.6"/>')
        with open(os.path.join(PREVIEW_DIR, f"{key}.svg"), "w") as fh:
            fh.write(svg_doc(f"{name} name hanger", body))

        x0, y0, x1, y1 = green.bounds
        edge = min(x0, y0, SHEET - x1, SHEET - y1)
        clear = min(h.distance(red) for h in holes)
        print(f"{key}.svg   backing {x1 - x0:5.1f} x {y1 - y0:5.1f} mm  sheet edge {edge:4.1f} mm  "
              f"name ties {ties}  pieces {len(parts(green))}+{len(parts(red))}  "
              f"hole to letters {clear:4.1f} mm")
        assert edge >= MARGIN - 0.01, f"{name}: art inside the margin"
        assert len(parts(green)) == 1 and len(parts(red)) == 1, f"{name}: a layer fell apart"
        assert red.difference(green).area < 0.01, f"{name}: name overhangs the backing"
        assert clear >= 2.0, f"{name}: ribbon hole under the letters"


if __name__ == "__main__":
    main()
