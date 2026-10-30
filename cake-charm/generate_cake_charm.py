#!/usr/bin/env python3
"""Generate a 'the Van Middelkoops' cake charm: a flat script name that
presses onto the front of a cake.

Same Great Vibes script as the door sign and name hangers.  Every word sits
on a fine swash underline, so the whole charm is one piece: easy to place,
and nothing to lose in the icing.

Two layouts, each its own file (1 SVG unit == 1 mm):

    svg/charm-one-line.svg   the Van Middelkoops, on one line
    svg/charm-stacked.svg    a small 'the' tucked over the V of Van Middelkoops

Colour convention: #FF0000 stroke -> CUT.

Needs:  pip install uharfbuzz fonttools skia-pathops shapely
Run:    python3 generate_cake_charm.py
"""

from __future__ import annotations

import os
import sys

from shapely import affinity
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "door-sign"))

from generate_door_sign import GREAT_VIBES, bezier, parts, poly_d, swash, weld   # noqa: E402
from scripttext import text_geometry                                            # noqa: E402

SVG_DIR = os.path.join(HERE, "svg")
PREVIEW_DIR = os.path.join(HERE, "preview")

CHARM_W = 125.0             # finished width of the charm, mm: fits the front of a 6-8" cake
GROW = 0.45                 # thicken the script's hairlines so the acrylic survives handling
WORD_GAP = 0.32             # space between words, as a fraction of the font size
RAIL_DROP = 0.6             # underline sits this far below the baseline, mm
PAD = 5.0                   # artboard margin
MIN_FEATURE = 1.0           # thinnest acrylic we report on


def words_line(words, size, x=0.0, baseline=0.0):
    """Lay words out with a real gap between them (the font's own space is
    so narrow the words run together once thickened)."""
    out = []
    for w in words:
        g, _ = text_geometry(GREAT_VIBES, w, size)
        x0, _, x1, _ = g.bounds
        out.append(affinity.translate(g, x - x0, baseline))
        x += (x1 - x0) + WORD_GAP * size
    return unary_union(out)


def underline(x0, x1, y):
    """Fine swash under the words: barely bowed, tapering at both ends."""
    w = x1 - x0
    path = bezier((x0, y - 0.6), (x0 + w * 0.3, y + 1.4), (x0 + w * 0.7, y + 1.4), (x1, y - 0.6), 160)
    return swash(path, 1.5, 0.9)


def finish(letters, rail_from, rail_to, baseline):
    """Thicken, add the underline, weld into one piece, scale to CHARM_W."""
    art = unary_union([letters.buffer(GROW, quad_segs=8),
                       underline(rail_from, rail_to, baseline + RAIL_DROP)])
    art, ties = weld(art, width=1.2)
    x0, y0, x1, y1 = art.bounds
    s = CHARM_W / (x1 - x0)
    art = affinity.scale(art, s, s, origin=(x0, y0))
    return affinity.translate(art, PAD - x0, PAD - y0), ties


def one_line():
    size = 20.0
    letters = words_line(["the", "Van", "Middelkoops"], size)
    x0, _, x1, _ = letters.bounds
    return finish(letters, x0 + 1.0, x1 - 0.5, 0.0)


def stacked():
    size = 20.0
    main = words_line(["Van", "Middelkoops"], size)
    mx0, my0, mx1, _ = main.bounds
    the, _ = text_geometry(GREAT_VIBES, "the", size * 0.7)
    tx0, _, tx1, ty1 = the.bounds
    # 'the' sits on the V's top-left flourish, overlapping it like the
    # stacked 'Happy Birthday' in the reference photo.
    the = affinity.translate(the, mx0 + 1.0 - tx0, my0 + 2.2)
    letters = unary_union([main, the])
    return finish(letters, mx0 + 4.0, mx1 - 0.5, 0.0)


def thin_area(geom):
    r = MIN_FEATURE / 2
    return geom.difference(geom.buffer(-r, quad_segs=6).buffer(r, quad_segs=6)).area


def svg_doc(w, h, title, body):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}mm" height="{h:.1f}mm" '
            f'viewBox="0 0 {w:.1f} {h:.1f}">\n  <title>{title}</title>\n{body}\n</svg>\n')


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    for key, title, build in (("charm-one-line", "the Van Middelkoops - one line", one_line),
                              ("charm-stacked", "the Van Middelkoops - stacked", stacked)):
        art, ties = build()
        _, _, x1, y1 = art.bounds
        w, h = x1 + PAD, y1 + PAD
        with open(os.path.join(SVG_DIR, f"{key}.svg"), "w") as fh:
            fh.write(svg_doc(w, h, title, f'  <path d="{poly_d(art)}" fill="none" '
                                          f'stroke="#FF0000" stroke-width="0.1"/>'))
        # Preview: gold mirror acrylic on white buttercream.
        with open(os.path.join(PREVIEW_DIR, f"{key}.svg"), "w") as fh:
            fh.write(svg_doc(w, h, title,
                             f'  <rect width="{w:.1f}" height="{h:.1f}" fill="#f6f2ea"/>\n'
                             f'  <path d="{poly_d(affinity.translate(art, 0.3, 0.45))}" '
                             f'fill="#000" opacity="0.18" fill-rule="evenodd"/>\n'
                             f'  <path d="{poly_d(art)}" fill="#c9a54a" stroke="#8a6d22" '
                             f'stroke-width="0.12" fill-rule="evenodd"/>'))
        print(f"{key}.svg  {x1 - PAD:5.1f} x {y1 - PAD:4.1f} mm  pieces {len(parts(art))}  "
              f"ties {ties}  under {MIN_FEATURE} mm: {thin_area(art):.1f} mm2")
        assert len(parts(art)) == 1, f"{key}: fell apart"


if __name__ == "__main__":
    main()
