#!/usr/bin/env python3
"""Outline-only gem drop earrings: teardrop bail, round link and faceted gem
merged into one silhouette, with no internal lines.  Cut as a pair.

    svg/gem-outline.svg   both earrings, #FF0000 stroke -> CUT

Run:  python3 generate_gem_outline.py
"""

from __future__ import annotations

import os

from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from generate_earrings import PAIR_GAP, SHEET_PAD, layer_svg, soften

HEIGHT = 50.0               # top of the bail to the bottom of the gem, mm


def gem_drop():
    """Traced from the reference drawing's 472 px grid, then scaled to HEIGHT."""
    bail = unary_union([Point(235, 134).buffer(20, quad_segs=24),
                        Polygon([(215, 136), (255, 136), (243, 212), (228, 212)])])
    bail = unary_union([bail, Point(235.5, 210).buffer(7.5, quad_segs=16)])
    link = Point(235.5, 221).buffer(9.5, quad_segs=24)
    gem = Polygon([(213, 230), (258, 230), (301, 291), (256, 357), (214, 357), (169, 291)])
    # A stem through bail, link and gem: the drawing's circles only touch,
    # and a touching point would snap.
    stem = box(230, 200, 241, 238)
    shape = unary_union([bail, link, stem, gem.buffer(0.5)])
    x0, y0, x1, y1 = shape.bounds
    s = HEIGHT / (y1 - y0)
    shape = affinity.scale(shape, s, s, origin=(0, 0))
    x0, y0, x1, _ = shape.bounds
    return soften(affinity.translate(shape, -(x0 + x1) / 2, -y0), 0.6)


def main():
    piece = gem_drop()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg", "gem-outline.svg")
    with open(out, "w") as fh:
        fh.write(layer_svg(piece, [], piece.bounds, "Gem drop earrings - outline only"))
    x0, y0, x1, y1 = piece.bounds
    print(f"gem-outline.svg  {x1 - x0:.1f} x {y1 - y0:.1f} mm each, pair of 2, "
          f"{len(piece.interiors)} internal cuts")


if __name__ == "__main__":
    main()
