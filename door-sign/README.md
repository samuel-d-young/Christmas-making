# "Merry Christmas from the Youngs": front-door sign

Laser-cut sign for the front door, sized for a **Glowforge Aura on a
300 × 300 mm sheet**, the same setup as [stocking-template](../stocking-template/).

## The chosen design: two-layer wreath

<p align="center"><img src="preview/door-wreath-layered.svg" width="55%" alt="Wreath detail glued onto a painted backing disc"></p>

Two pieces, each cut from its own 300 × 300 mm sheet:

| Layer | File | Size | What it is |
|---|---|---|---|
| Top | [`svg/door-wreath.svg`](svg/door-wreath.svg) | Ø 268 mm | The detail: a ring with scored "ribbon-wrap" marks, holly and berries at the foot, "Merry Christmas" spanning the ring and "from the Youngs" on a rail. **One piece.** |
| Bottom | [`svg/door-wreath-backing.svg`](svg/door-wreath-backing.svg) | Ø 268 mm | A plain disc the same size, so the two edges sit flush. |

Both layers have a **5 mm ribbon hole** in the same spot at the top of the
band. It's how the sign hangs and how you line the layers up.

The top layer is still welded into a single piece, even though the backing
would hold loose letters. One piece is far easier to paint and glue than a
dozen letters and an *i* dot, and it positions itself: once the rim is flush
and the holes line up, everything is where it should be.

### Putting it together

1. **Cut both layers** in 3 mm plywood. The backing is a plain circle and
   cuts quickly. The top layer has a lot of path, so give it time.
2. **Paint before gluing.** Contrast makes it: e.g. a deep green or navy
   backing with a white, cream or gold top layer, as in the preview. Paint
   the backing's edge too.
3. **Glue.** Use exterior-grade wood glue (Titebond II/III or similar) or a
   polyurethane glue, spread thinly on the *back of the top layer* with a
   small brush. Keep it away from the letter edges or it squeezes out
   onto the paint.
4. **Line up.** Push a pencil or a 5 mm dowel through both ribbon holes to
   fix the rotation, then nudge the rim flush all the way round.
5. **Weight it flat** under a board and some books for a few hours.
6. **Seal** with two coats of exterior varnish, including the edges, then
   thread ribbon through the hole to hang.

If you would rather hang it from a door hook than a ribbon, glue a small
sawtooth hanger to the back of the disc instead.

## Earlier concepts

The other two ideas are kept for reference:

| | Concept | Size | How it's made |
|---|---|---|---|
| 1 | [`svg/door-script.svg`](svg/door-script.svg): **Script & swash** | 273 × 94 mm | Freestanding lettering on a calligraphic swash, one piece, one ribbon hole. |
| 3 | [`svg/door-bauble.svg`](svg/door-bauble.svg): **Bauble** | 224 × 265 mm | Bauble-shaped plaque with the lettering engraved. |

<p align="center">
  <img src="preview/door-script.svg" width="32%" alt="Concept 1: freestanding script on a swash">
  <img src="preview/door-wreath.svg" width="32%" alt="Wreath top layer on its own">
  <img src="preview/door-bauble.svg" width="32%" alt="Concept 3: engraved bauble plaque">
</p>

## Lettering

The wreath (and concept 1) uses **Great Vibes**: elegant, with a confident thick-thin
contrast, and its letters join into very few separate pieces, which matters
when you cut script out. Concept 3 uses **Pinyon Script**, a finer copperplate
hand that suits engraving. Any of the three bundled fonts can go on any
concept:

<p align="center"><img src="preview/font-options.svg" width="60%" alt="Great Vibes, Pinyon Script and Parisienne compared"></p>

The fonts are in [`fonts/`](fonts/) under the SIL Open Font License.

## Line colours

| Colour | Hex | Set the step to |
|---|---|---|
| Red | `#FF0000` | **Cut** |
| Blue | `#0000FF` | **Score** |
| Black fill | `#000000` | **Engrave** (concept 3 only) |

## Making cut lettering survive

Script fonts have hairlines thinner than a millimetre, and those snap in ply.
For the cut concepts the generator:

- **grows every letter outward by 0.5 mm** before cutting, so the thinnest
  strokes come out at about 1.5 mm or more after kerf;
- **welds** overlapping letters and joins into one outline, so the laser
  never cuts through a join;
- **ties every loose island** (the *i* dot, a capital that doesn't quite
  touch) to the body with a short 2.2 mm bridge, and refuses to write a file
  unless the result is a single piece.

Each run prints a check:

```
door-script.svg           273.0 x  94.3 mm  sheet edge 13.5 mm  pieces 1  ties  5  thin wood 75.8 mm2
door-wreath.svg           268.0 x 268.0 mm  sheet edge 12.0 mm  pieces 1  ties  4  thin wood 85.7 mm2
door-wreath-backing.svg   268.0 x 268.0 mm  sheet edge 12.0 mm  pieces 1  ties  0  thin wood  0.0 mm2
door-bauble.svg           224.0 x 265.0 mm  sheet edge 15.0 mm  pieces 1  ties  0  thin wood  0.0 mm2
```

*thin wood* is the area narrower than 1.6 mm. On the cut concepts that's
almost all pointed stroke ends and holly spikes, which taper to a point by
design. Even so, **cut the wreath top in 3 mm plywood, not thinner**, and
handle the fresh cut by the ring, not the letters.

## Cutting and finishing

The [stocking-template README](../stocking-template/README.md#cutting-it) has
the full Glowforge walkthrough. In short: upload the SVG, check it reports
the size in the table above, set the colour steps, and test-cut on a scrap
corner first. The Aura is a diode laser, so 3 mm ply is the sweet spot and
expect more than one pass on non-Proofgrade material.

**It's going outdoors**, so seal it. Wipe off the soot, sand lightly, then
paint or stain and finish with two coats of exterior varnish or yacht
varnish, edges included. A porch or a door under a canopy will be kind to it.
Plywood out in the open rain will delaminate within a season.

## Changing the design

```sh
pip install uharfbuzz fonttools skia-pathops shapely
python3 generate_door_sign.py      # rewrites svg/ and preview/
```

The wording lives in `LINE_1` / `LINE_2`, each concept is one function
(`door_wreath` and `door_wreath_backing` for the chosen design), and `CUT_TEXT_GROW`,
`BRIDGE_W`, `MIN_FEATURE` and `HANG_HOLE_DIA` control how robust the cut lettering is.
`scripttext.py` does the font work: HarfBuzz shaping (so the script's joins
and kerning are right) turned into millimetre geometry.
