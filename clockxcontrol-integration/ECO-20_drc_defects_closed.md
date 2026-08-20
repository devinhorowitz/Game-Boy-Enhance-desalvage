# ECO-20 — the two open DRC defects, closed

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

**Board:** one 2.368 mm `GND` track added on `F.Cu`; all six fiducials relocated and unpaired.
**New:** `scripts/place_fiducials.py` — the site search, sharing its geometry with check [13].
**Changed:** `scripts/build_board.py`, `scripts/geom.py`, `scripts/render_board.py`,
`scripts/check_consistency.py`, `scripts/check_drc.py`, `scripts/test_checks.py`
**Raised by:** the user — *"fix the fiducials and U1 pad 39"*.

| | before | after |
|---|---|---|
| unconnected pads DRC finds on this fork | **1** | **0** |
| new violations at positions MouseBiteLabs' board does not have | 69 | **55** |
| …of those, anything but silkscreen and library nits | **14** | **1**, by design |

MouseBiteLabs' own AGBM-02, re-poured through the identical process, has 695 violations and
**0** unconnected items. This fork now matches him on the number that matters.

---

## 20.1 `U1` pin 39 had no ground, and it was ours

`U1` is the salvaged CPU. Pin 39 is a `GND` pin, and on MouseBiteLabs' board nothing routes to
it — the `F.Cu` `GND` pour reaches in from the left and merges with the land. ECO-6's
`/CPU/TP8` route to `MOD1` walks diagonally past that pad's lower-left corner and cuts the
corridor off.

Measured on the shipped board, not estimated:

```
TP8 copper to pad 39 copper, closest approach : 0.3594 mm at (73.372, -46.628)
what a pour sliver needs to survive there     : 0.200  zone clearance to TP8 (foreign net)
                                              + 0.200  the zone's own min_thickness
                                              = 0.400 mm
```

**Forty-one microns short.** ECO-19 §19.5 reported this as *0.988 mm* — that figure was not
the pad-to-track distance and it is corrected here.

The failure mode is nastier than a plain open. KiCad keeps a fill island that touches a pad, so
the pour still puts copper on pin 39; it is simply an island, joined to nothing else on the
board. **The pad looks connected in every render and in every plot.** Only a connectivity
engine sees it, which is why nothing in this repository could — check [13] measures how far
apart copper is, and here nothing is too close to anything.

### Why the route was not simply moved

On `TP8`'s other flank the `Net-(RA1A-R1.1)` track is **0.2644 mm** away against a 0.200 mm
rule: 64 µm of slack, and the prize for spending it would be a 0.2 mm hair of poured copper
serving as a CPU ground return. Underneath, `B.Cu` is three tracks — `/CPU/~{OE}_{RAM}`,
`SW` and `/CPU/MD_{0}` — on 0.451 mm centres, so the gaps between them are **0.201 mm** and
there is no via site either.

### What was done instead

The connection stops depending on the pour. **2.368 mm of `F.Cu`, 0.25 mm wide, from pin 39 to
`C15` pad 2** — the ground side of the CPU's own decoupling capacitor, and the nearest copper
that is unambiguously part of the plane. The tightest thing it passes is `U1` pin 40 at
**0.225 mm**. DRC on the re-poured board: **1 unconnected item → 0, and not one new violation
anywhere.**

## 20.2 The fiducials were placed against one constraint out of five

ECO-14 §14.3 chose all six spots by maximising distance to **hard copper** — tracks, vias and
pads — wrote the resulting clear radii into a comment, and stated *"each is ≥ 3.0 mm from the
board edge."* That sentence was produced by `geom.edge_segments()`, which read four of
Edge.Cuts' five primitive types.

| Fiducial | What ECO-14 believed | What KiCad's DRC said |
|---|---|---|
| `FID1`, `FID4` | 2.390 mm clear | **0.000 mm to `BT1`'s plated `GND` pad**, 5 mask bridges with the battery terminal, inside a keepout |
| `FID2`, `FID5` | 1.800 mm clear | **inside** the 1.2 mm shell hole at (110.91, −56.85); `FID2` also inside a keepout |
| `FID3`, `FID6` | 2.399 mm clear | 0.000 mm to the outline — 0.082 mm from the rim of the hole at (30.50, −70.68) |

Four blind spots, each now closed in `geom.py`:

1. **`gr_circle` on `Edge.Cuts`.** Thirteen of them: the shell's screw and standoff holes. Plus
   two `fp_circle` **inside footprints** — `SW1`'s switch shaft and `VR2`'s volume wheel — which
   a top-level-only scan misses entirely. `edge_segments()` went from 243 chords to 1,569, and
   `gr_rect` now yields four sides rather than the one diagonal the old code produced.
2. **Keepout zones.** This board has **64**; 16 live inside footprints at indent 2, and **four
   are drawn as a single full-circle arc carrying no `(xy)` vertex at all** — including the one
   ringing the very hole `FID2` was sitting in. An `(xy)`-only reader returns an empty vertex
   list for those and they vanish silently.
3. **Soldermask apertures, as filled regions.** `BT1`'s mask graphics on the front; the two
   7.5 × 5 mm `B.Mask` polygons over the cartridge-edge contacts on the back. A boundary-distance
   test calls a point *inside* one of those polygons "0.9 mm of clearance".
4. **That a mark on the front does not care what the back is doing.** ECO-14 kept the six as
   three coincident front/back pairs, so every site had to be clear on both layers at once.
   That is not a requirement — front and back register independently — and it was expensive:

   | | sites the board will accept, 0.25 mm grid |
   |---|---|
   | as coincident pairs | 492 |
   | front alone | **3,659** |
   | back alone | **6,327** |

   **None of the six spots finally chosen is legal on the other side.** The pairing was costing
   every mark real margin and buying nothing.

### Where they went

`python3 scripts/place_fiducials.py --grid 0.25` prints exactly these, and prints them again
from the board they are already on — the search skips the fiducials, so it does not chase its
own tail. Margins are from the mark's **centre**, so compare them against the 1.0 mm mask
window rather than the 0.5 mm copper dot; "—" means nothing of that kind within 9 mm.

| | side | position | edge | keepout | copper | mask | courtyard |
|---|---|---|---|---|---|---|---|
| `FID1` | front | (100.50, −3.50) | 3.12 | — | 2.26 | — | — |
| `FID2` | front | (103.75, −58.50) | — | — | 1.84 | — | 2.22 |
| `FID3` | front | (24.25, −55.75) | 2.94 | 2.71 | 2.00 | — | 4.58 |
| `FID4` | back | (127.75, −19.50) | 3.31 | 4.59 | 2.26 | — | — |
| `FID5` | back | (94.75, −66.50) | 2.85 | — | 1.80 | — | 2.72 |
| `FID6` | back | (11.50, −16.00) | 3.58 | — | 2.15 | — | 5.84 |

Both triangles stay deliberately scalene, so a machine cannot register the panel 180° out:
**front 55.1 / 79.5 / 92.4 mm, 2,182 mm²; back 57.4 / 97.4 / 116.3 mm, 2,790 mm².**

There is **no legal site anywhere in the board's upper right.** The CPU, the RAM and the LCD
connector leave nothing with a 1.1 mm clear radius on both sides, and that is stated here rather
than hidden inside a triangle that quietly avoids the region.

## 20.3 The numbers are now a gate, not a paragraph

ECO-14's margins were prose. Thirty numbers, asserted once, never recomputed — and four of them
were wrong the day they were written. So:

* `geom.site_model()` / `geom.site_margins()` measure all five axes from the board.
* `scripts/place_fiducials.py` **searches** with them.
* Check **[13]** **re-measures** the six chosen spots with them and fails if any margin moves
  by more than 5 µm, or drops below the floor it was chosen against.

The tool and the gate cannot disagree about what "legal" means, because they are the same code.
`scripts/test_checks.py` went from 21 cases to 25: one per newly-modelled axis, plus a second
edge case because `gr_circle` at the top level and `fp_circle` inside `SW1` are separate blind
spots. Four of the five move a mark back to a spot ECO-14 or ECO-20 actually shipped. The case
runner also gained an **expected-reason** field, because check [13] now fails on *any* fiducial
move and "caught" alone would not distinguish a keepout case from an edge case — five cases that
all fire for the same reason are one case wearing five hats. The courtyard case is the only one
KiCad would not have caught for us: that axis has no DRC rule behind it.

## 20.4 Five bugs this turned up in our own tooling

**`geom.swallowed()` read eight fields from a nine-field tuple.** ECO-18 gave `collect()` a
ninth — the pad's own rotation — and this call site was never updated. It had never run: it
only executes when an **added pad** lands inside a **foreign pour**, and until the fiducials
moved, none did. A crash on a path nothing had ever taken.

**`render_board` had the same unpack in three places**, and one of them mattered on its own:
`paint()` drew every pad from the stored `(size w h)` as though it were width-by-height in
**board** axes. **345 of this board's 956 pads carry their own 90° or 270° rotation** — every
fine-pitch QFP and SOP side row — so a quarter of the lands in the 2D renders were drawn across
the wrong axis. `U1` pin 39 was drawn 0.3 mm wide and 1.25 tall where it is physically 1.25 by
0.3. A picture whose whole job is to show what size and orientation each land really is.
`Canvas.roundrect()` now takes the angle; the 24 pads at 1.25°, 15.25°, 21°, 111°, 285.25° and
343° are drawn as rotated polygons.

**The CPL's y datum moved 12.7 µm.** `_board_origin()` takes the extreme of the outline, and
polygonising arcs properly found a point 0.0127 mm further out than the old three-point chord
chain. All 180 lines shift by exactly that and nothing else changes. Far below any fab's
tolerance, and more correct than what shipped.

**`check_drc.py`'s ledger had a line that was two defects.** The seven `solder_mask_bridge`
violations were described as "`FID1`'s mask aperture bridges `BT1`" — six of them were, and the
seventh was `FID5` sitting in the cartridge-contact mask opening on the back. A count that
matches for the wrong reason.

**The shipped package's contents list stopped at ECO-14.** `pack_board.MEMBERS` had not been
extended since, so the zip's own `README.md` linked forward to **five ECOs the zip did not
contain** — including ECO-14 §14.6 and ECO-19, which carry the *do not plot Gerbers from this
file without re-pouring* warning. A deliverable whose index points outside the deliverable.
Fixed; the package went from 26 members to 32.

## 20.5 The ledger empties, and that is a checkable event

`check_drc.py`'s `KNOWN_NEW` loses four entries and `KNOWN_UNCONNECTED` empties. Leaving any of
them in would have **failed the run**: the check reports `0 new, ledger says N -- FIXED? remove
its line`. A fix has to be recorded in the same commit as the fix, exactly as a regression would
be. What remains is silkscreen, text height, library-comparison nits on board-only footprints,
and the one `courtyards_overlap` ECO-19 put there on purpose.

## 20.6 Verification

* `python3 scripts/build_board.py --check` — byte-identical rebuild
* `python3 scripts/check_consistency.py` — **0 errors**, 2 pre-existing warnings
* `python3 scripts/test_checks.py` — **25 cases, 0 blind**
* `python3 scripts/check_drc.py` — **55 new violations, 0 unconnected**, every one ledgered
* `python3 scripts/place_fiducials.py --grid 0.25` — reproduces all six spots from the board
  they are already on
