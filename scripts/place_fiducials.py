#!/usr/bin/env python3
"""place_fiducials.py -- find six fiducial sites this board will actually accept.

    python3 scripts/place_fiducials.py            # search and print the best two triangles
    python3 scripts/place_fiducials.py --grid 0.5 # coarser and faster

This is a TOOL, not a gate. It produced the coordinates in build_board.FIDUCIALS; check
[13] re-measures those six spots and fails if any margin moves. Both call the same
geom.site_model / geom.site_margins, so the search and the gate cannot disagree about
what "legal" means -- which is the whole reason this file exists.

WHY THE FIRST SEARCH WAS WRONG, twice over.

An earlier pass maximised distance to HARD COPPER alone. That is not the constraint set.
A fiducial has to satisfy FIVE separate things at once, and KiCad's DRC checks four of them:

  edge     the board outline INCLUDING its 13 gr_circle shell holes and the two fp_circle
           openings inside SW1 and VR2. Two of the earlier marks were in holes.
  keepout  this board has 64 keepout zones, 30 of which forbid a pad or a footprint. Four
           are drawn as one full-circle arc and carry no (xy) vertex at all.
  copper   tracks, vias and pads ON THE MARK'S OWN LAYER -- inside the 1.0 mm mask window
           any copper at all destroys the contrast the camera is looking for.
  mask     other soldermask apertures, as FILLED REGIONS. Merge with one and the fab sees
           a single opening spanning two nets.
  crtyd    courtyards, so no part body ends up over the mark.

And the fifth thing, which is not a constraint but an assumption that pass made for free: that
the six have to be three coincident front/back PAIRS. They do not. Front and back register
independently. Dropping that assumption takes this board from 492 legal sites to 3,655 on
the front and 6,324 on the back, and none of the six spots finally chosen is legal on the
other side -- so the pairing was costing every mark real margin and buying nothing.
"""
from __future__ import annotations

import argparse
import itertools
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom                                                       # noqa: E402
import kisexp                                                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = (f"{ROOT}/clockxcontrol-integration/board/"
         "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb")

# Floors, in mm from the mark's CENTRE. The mask window is 1.0 mm across the radius, so
# every one of these is "the window plus something". They are deliberately well above what
# DRC would pass -- a fiducial that only just clears is a fiducial that stops clearing the
# next time a track moves.
FLOOR = {"edge": 2.0,       # DRC's own rule would pass 1.0 (0.5 pad + 0.5 edge clearance)
         "keepout": 1.0,    # DRC would pass 0.5
         "copper": 1.1,     # 1.0 is where the mask apertures touch
         "mask": 1.5,       # 1.0 is where the mask apertures touch
         "crtyd": 1.0}      # no DRC rule at all -- this one is judgement
MIN_SIDE, MIN_SPREAD, MIN_HEIGHT = 45.0, 12.0, 28.0


def score(m):
    """How much room the tightest of the five margins has to spare. Bigger is better."""
    return round(min(m[k] - v for k, v in FLOOR.items()), 4)


def search(M, layer, step):
    out = []
    x = 0.0
    while x < 132.0:
        y = -73.0
        while y < 0.0:
            m = geom.site_margins(M, round(x, 3), round(y, 3), layer)
            if m["on_board"] and all(m[k] >= v for k, v in FLOOR.items()):
                out.append((round(x, 3), round(y, 3), m, score(m)))
            y += step
        x += step
    return out


def triangles(sites, floor):
    """The biggest deliberately-scalene triangle whose worst mark still has `floor` spare.

    SCALENE ON PURPOSE. Three marks in an isoceles or equilateral arrangement let a machine
    register the panel rotated; sides that differ by more than MIN_SPREAD cannot.
    """
    best_of = {}
    for x, y, m, s in sites:
        k = (round(x / 3), round(y / 3))
        if k not in best_of or s > best_of[k][3]:
            best_of[k] = (x, y, m, s)
    P = [t for t in best_of.values() if t[3] >= floor]
    d = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])          # noqa: E731
    best = None
    for a, b, c in itertools.combinations(P, 3):
        L = sorted([d(a, b), d(b, c), d(a, c)])
        if L[0] < MIN_SIDE or L[1] - L[0] < MIN_SPREAD or L[2] - L[1] < MIN_SPREAD:
            continue
        ar = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2
        if 2 * ar / L[2] < MIN_HEIGHT:
            continue
        if best is None or ar > best[0]:
            best = (ar, L, (a, b, c))
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--grid", type=float, default=0.25, help="search step in mm")
    ap.add_argument("--floor", type=float, default=0.7,
                    help="minimum spare margin, in mm, for every mark in the triangle")
    a = ap.parse_args()

    b = kisexp.load(BOARD)
    fids = {fp.ref for fp in kisexp.footprints(b) if fp.ref.startswith("FID")}
    M = geom.site_model(b, skip=fids)
    print(f"searching with FID{'/'.join(sorted(f[3:] for f in fids))} removed, "
          f"{a.grid} mm grid, floors {FLOOR}")
    for layer, refs in (("F.Cu", "front"), ("B.Cu", "back")):
        sites = search(M, layer, a.grid)
        print(f"\n{refs} ({layer}): {len(sites)} legal site(s)")
        got = triangles(sites, a.floor)
        if not got:
            print(f"  no scalene triangle with {a.floor} mm spare everywhere")
            continue
        ar, L, tri = got
        print(f"  best: {ar:.0f} mm2, sides {'/'.join(f'{v:.1f}' for v in L)} mm, "
              f"height {2 * ar / L[2]:.1f} mm")
        for x, y, m, s in sorted(tri, key=lambda t: (t[1], t[0])):
            print(f"    ({x:8.3f},{y:8.3f})  spare {s:5.3f}  " +
                  "  ".join(f"{k} {m[k]:5.2f}" for k in ("edge", "keepout", "copper",
                                                         "mask", "crtyd")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
