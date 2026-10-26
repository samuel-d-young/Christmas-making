"""Turn a line of script text into welded shapely geometry, in millimetres.

Shaping goes through HarfBuzz so script fonts get their kerning and
contextual joins; outlines are merged with skia-pathops (so overlapping
glyphs weld into one shape) and handed back as shapely polygons, y down.
"""

from __future__ import annotations

import pathops
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from shapely.geometry import Polygon
from shapely.ops import unary_union

FLATTEN_MM = 0.05           # max chord error when flattening curves


class _FlattenPen(BasePen):
    """Collect closed contours as point lists, curves flattened to lines."""

    def __init__(self, tol):
        super().__init__(None)
        self.tol = tol
        self.contours = []
        self._cur = []

    def _moveTo(self, p):
        self._cur = [p]

    def _lineTo(self, p):
        self._cur.append(p)

    def _steps(self, pts):
        length = sum(((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
                     for i in range(len(pts) - 1))
        return max(2, min(64, int((length / self.tol) ** 0.5) + 1))

    def _curveToOne(self, p1, p2, p3):
        p0 = self._getCurrentPoint()
        n = self._steps([p0, p1, p2, p3])
        for i in range(1, n + 1):
            t = i / n
            a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
            self._cur.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                              a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        n = self._steps([p0, p1, p2])
        for i in range(1, n + 1):
            t = i / n
            a, b, c = (1 - t) ** 2, 2 * t * (1 - t), t * t
            self._cur.append((a * p0[0] + b * p1[0] + c * p2[0],
                              a * p0[1] + b * p1[1] + c * p2[1]))

    def _closePath(self):
        if len(self._cur) >= 3:
            self.contours.append(self._cur)
        self._cur = []

    _endPath = _closePath


def text_geometry(font_path, text, size_mm, tracking_mm=0.0):
    """Return (geometry, advance_width_mm) for one line, baseline at y = 0."""
    face = hb.Face(hb.Blob.from_file_path(font_path))
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True, "calt": True})

    tt = TTFont(font_path)
    glyphs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    s = size_mm / tt["head"].unitsPerEm

    path = pathops.Path()
    pen = path.getPen(glyphSet=glyphs)
    x = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs[order[info.codepoint]].draw(
            TransformPen(pen, (s, 0, 0, -s, (x + pos.x_offset) * s + 0.0, -pos.y_offset * s)))
        x += pos.x_advance + tracking_mm / s
    path.simplify()          # resolves overlaps: welded, non-intersecting contours

    flat = _FlattenPen(FLATTEN_MM)
    path.draw(flat)
    # After simplify the rings never cross, so XOR-ing them rebuilds outers and holes.
    geom = Polygon()
    for ring in flat.contours:
        geom = geom.symmetric_difference(Polygon(ring).buffer(0))
    return unary_union(geom), x * s
