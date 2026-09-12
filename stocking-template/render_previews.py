#!/usr/bin/env python3
"""Render svg/*.svg to preview/*.png so the repo shows what gets cut.

The laser files use 0.1 mm hairlines, which all but disappear in a small
raster, so the preview thickens the strokes and draws the edge of the sheet.
Needs one of: rsvg-convert, inkscape, or a Chromium/Chrome binary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

SIZE = 1000                 # preview edge, pixels
PREVIEW_STROKE = 0.55       # mm, purely cosmetic

HERE = os.path.dirname(os.path.abspath(__file__))
SVG_DIR = os.path.join(HERE, "svg")
OUT_DIR = os.path.join(HERE, "preview")

CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
    "chromium", "chromium-browser", "google-chrome", "chrome",
]


def find_chrome():
    for cand in CHROME_CANDIDATES:
        if not cand:
            continue
        path = cand if os.path.isfile(cand) else shutil.which(cand)
        if path:
            return path
    for root in ("/opt/pw-browsers",):
        for dirpath, _dirs, files in os.walk(root):
            for name in ("headless_shell", "chrome"):
                if name in files:
                    return os.path.join(dirpath, name)
    return None


def thicken(svg_text):
    """Fatten the hairlines and draw the sheet edge, for display only."""
    svg_text = svg_text.replace('stroke-width="0.1"', f'stroke-width="{PREVIEW_STROKE}"')
    sheet = ('  <rect x="0.25" y="0.25" width="299.5" height="299.5" fill="none" '
             'stroke="#c9c9c9" stroke-width="0.5" stroke-dasharray="3 2"/>\n')
    marker = "</title>\n"
    idx = svg_text.index(marker) + len(marker)
    return svg_text[:idx] + sheet + svg_text[idx:]


def render(svg_path, png_path):
    with open(svg_path) as fh:
        svg = thicken(fh.read())

    with tempfile.TemporaryDirectory() as tmp:
        tmp_svg = os.path.join(tmp, "preview.svg")
        with open(tmp_svg, "w") as fh:
            fh.write(svg)

        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-w", str(SIZE), "-h", str(SIZE),
                            "-b", "white", "-o", png_path, tmp_svg], check=True)
            return "rsvg-convert"

        if shutil.which("inkscape"):
            subprocess.run(["inkscape", tmp_svg, "-w", str(SIZE), "-h", str(SIZE),
                            "-b", "white", "-o", png_path], check=True)
            return "inkscape"

        chrome = find_chrome()
        if not chrome:
            raise SystemExit("no renderer found (rsvg-convert, inkscape or chromium)")

        html = os.path.join(tmp, "wrap.html")
        with open(html, "w") as fh:
            fh.write("<style>html,body{margin:0;background:#fff}"
                     f"img{{display:block;width:{SIZE}px;height:{SIZE}px}}</style>"
                     f'<img src="file://{tmp_svg}">')
        subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                        "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--default-background-color=FFFFFFFF",
                        f"--window-size={SIZE},{SIZE}",
                        f"--screenshot={png_path}", f"file://{html}"],
                       check=True, capture_output=True)
        return os.path.basename(chrome)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    names = sorted(n for n in os.listdir(SVG_DIR) if n.endswith(".svg"))
    if not names:
        sys.exit("no SVGs in svg/ - run generate_stockings.py first")
    for name in names:
        png = os.path.join(OUT_DIR, name[:-4] + ".png")
        engine = render(os.path.join(SVG_DIR, name), png)
        print(f"{name:26s} -> preview/{os.path.basename(png)}  ({engine})")


if __name__ == "__main__":
    main()
