#!/usr/bin/env python3
"""kicad10.py -- ship a KiCad 10 copy of the board, and prove it is the same copper.

    python3 scripts/kicad10.py            # convert, verify, write the companion board
    python3 scripts/kicad10.py --check    # verify the committed pair, no KiCad needed

WHY THERE ARE TWO BOARDS

MouseBiteLabs' AGBM-02 is a KiCad 9 file (version 20241229) and `build_board.py` produces
this fork by splicing text into it, which is what lets check [1] assert the shipped board
rebuilds BYTE-FOR-BYTE from his committed zip. That property is the spine of this
repository: every other check is only worth what it is worth because the board is a pure
function of inputs that are all in git.

KiCad 10 (version 20260206) cannot be produced that way, because it is not a superset --
it is a different encoding of the same design:

    KiCad 9                          KiCad 10
    (net 12)                         (net "/CPU/TP8")          on segments and vias
    (net 12 "/CPU/TP8")              (net "/CPU/TP8")          on pads
    a (net N "name") table at top    no table at all
    -                                (capping) (covering) (plugging) on every via

So the KiCad 9 board stays the source of truth and the KiCad 10 file is a DERIVED
ARTIFACT, exactly like the renders: generated here, committed, and gated. What follows is
the gate, and it runs on TEXT ALONE so CI can enforce it on a runner with no KiCad.

WHAT "THE SAME COPPER" HAS TO MEAN

Not byte equality, and not segment-for-segment equality either: KiCad 10 MERGES COLLINEAR
TRACKS on load. Converting this board turns 3,554 segments into roughly 3,240 without
moving any copper -- and a naive comparison reads that as 314 deleted tracks, which is
precisely the wrong conclusion the ECO-22 investigation nearly reached.

So tracks are compared by COVERAGE. Every segment is grouped by (layer, net, and the
infinite line it lies on), projected onto that line, and the intervals merged into maximal
runs. Two boards match when their run sets are identical -- which is invariant under
merging and splitting, and still catches a track that moved, changed net, changed layer,
changed width, or disappeared.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp                                                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD9 = os.path.join(ROOT, "clockxcontrol-integration", "board",
                      "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb")
BOARD10 = os.path.join(ROOT, "clockxcontrol-integration", "board",
                       "AGBM-02_AA_1-1_GBE-plus-CXC_kicad10.kicad_pcb")
Q = 4                      # 0.1 um -- finer than any fab tolerance, coarser than float noise


# ------------------------------------------------------------------ format-neutral reads
def version(board):
    m = re.search(r'\(version (\d+)\)', board)
    return int(m.group(1)) if m else 0


def _netname(tok, table):
    """`12` -> the table's name for it; `"GND"` -> GND. One function, both formats."""
    return tok[1:-1] if tok.startswith('"') else table.get(int(tok), tok)


_NET_TOK = r'("(?:[^"\\]|\\.)*"|\d+)'
_SEG = re.compile(
    r'\n\t\(segment\n\t\t\(start ([-\d.]+) ([-\d.]+)\)\n\t\t\(end ([-\d.]+) ([-\d.]+)\)\n'
    r'\t\t\(width ([\d.]+)\)\n\t\t\(layer "([^"]+)"\)\n\t\t\(net ' + _NET_TOK + r'\)')
_VIA = re.compile(r'\n\t\(via\n\t\t\(at ([-\d.]+) ([-\d.]+)\)([\s\S]{0,900}?)\n\t\)')
_PADNET = re.compile(r'\(net (?:\d+ )?("(?:[^"\\]|\\.)*")\)')


def table(board):
    return {int(n): nm for n, nm in re.findall(r'\n\t\(net (\d+) "([^"]*)"\)', board)}


def tracks(board):
    t = table(board)
    out = []
    for a, b, c, d, w, lay, n in _SEG.findall(board):
        out.append((float(a), float(b), float(c), float(d), float(w), lay, _netname(n, t)))
    if not out and "\n\t(segment" in board:
        raise ValueError(f"version {version(board)}: saw segments, parsed none")
    return out


def vias(board):
    t = table(board)
    out = set()
    for x, y, body in _VIA.findall(board):
        n = re.search(r'\(net ' + _NET_TOK + r'\)', body)
        sz = re.search(r'\(size ([\d.]+)\)', body)
        dr = re.search(r'\(drill ([\d.]+)\)', body)
        out.add((round(float(x), Q), round(float(y), Q),
                 float(sz.group(1)) if sz else 0.0, float(dr.group(1)) if dr else 0.0,
                 _netname(n.group(1), t) if n else "?"))
    if not out and "\n\t(via" in board:
        raise ValueError(f"version {version(board)}: saw vias, parsed none")
    return out


def footprints(board):
    """{ref: (value, at, layer, attrs, name, frozenset(pads))} with pad nets as NAMES."""
    t = table(board)
    out = {}
    for fp in kisexp.footprints(board):
        if not fp.at:
            continue
        pads = set()
        for blk in kisexp.pad_blocks(fp.body):
            num = re.match(r'\(pad "([^"]*)"', blk).group(1)
            at = re.search(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk)
            sz = re.search(r'\(size ([\d.]+) ([\d.]+)\)', blk)
            lay = re.search(r'\(layers ([^)]*)\)', blk)
            nm = _PADNET.search(blk)
            # KiCad 10 writes `(drill 1 (offset 0 0))` where 9 writes `(drill 1)`, and
            # an oval hole is `(drill oval 0.6 1.2)` in both. Do NOT anchor on the closing
            # paren: that reads every KiCad 10 through-hole pad as drill-less, which looks
            # exactly like six pads having lost their holes.
            drl = re.search(r'\(drill (?:oval )?([\d.]+)(?: ([\d.]+))?', blk)
            pads.add((num,
                      round(float(at.group(1)), Q), round(float(at.group(2)), Q),
                      round(float(at.group(3) or 0), Q),
                      round(float(sz.group(1)), Q) if sz else 0.0,
                      round(float(sz.group(2)), Q) if sz else 0.0,
                      lay.group(1) if lay else "",
                      nm.group(1)[1:-1] if nm else None,
                      (round(float(drl.group(1)), Q),
                       round(float(drl.group(2)), Q) if drl and drl.group(2) else 0.0)
                      if drl else (0.0, 0.0)))
        out[fp.ref] = (fp.value, tuple(round(v, Q) for v in fp.at), fp.layer,
                       tuple(sorted(fp.attr)), fp.name, frozenset(pads))
    return out


# ------------------------------------------------------------------- coverage comparison
def runs(board):
    """{(layer, net, line): [(from, to, width), ...]} -- maximal collinear runs.

    Invariant under KiCad 10's collinear merging, which is the whole point: the same copper
    yields the same runs whether it is stored as one segment or six.
    """
    lines = {}
    for x0, y0, x1, y1, w, lay, net in tracks(board):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L == 0:
            continue
        ux, uy = dx / L, dy / L
        if (ux < 0) or (ux == 0 and uy < 0):        # canonical direction, both senses equal
            ux, uy = -ux, -uy
        off = round(ux * y0 - uy * x0, Q)           # signed distance from the origin
        key = (lay, net, round(ux, Q), round(uy, Q), off, round(w, Q))
        t0, t1 = ux * x0 + uy * y0, ux * x1 + uy * y1
        lines.setdefault(key, []).append((min(t0, t1), max(t0, t1)))
    out = {}
    for key, spans in lines.items():
        spans.sort()
        merged = [list(spans[0])]
        for a, b in spans[1:]:
            if a <= merged[-1][1] + 10 ** -Q:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        out[key] = tuple((round(a, Q), round(b, Q)) for a, b in merged)
    return out


_GRAPH_LAYERS = ("SilkS", "Fab", "CrtYd", "Mask", "Paste", "Adhes", "Dwgs", "Cmts", "Eco")

# THE THIRD NUMBER. `(at 0 0 180)` carries a ROTATION, and an `(at x y)` pattern anchored on
# the closing paren matches NOTHING against it. Every fp_text on this board is placed with a
# rotation, so the first version of graphics() extracted an EMPTY position for all of them --
# and two texts in different places both became `()` and compared equal. That is how
# `CLOCKXCONTROL` moving 2.5 mm out from under MouseBiteLabs' silkscreen survived both an
# ad-hoc diff and the gate written to catch precisely that.
#
# Third time this repository has been bitten by a reader that returns nothing and reads as
# "no difference" -- after the CRLF parse and the KiCad 10 net format. So `text` items are
# now REQUIRED to yield a position, and rotation is captured rather than discarded: a label
# turned 180 degrees is a different label.
_PT = r'\((?:xy|start|mid|end|center|at) ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)'


def _pts(body, kind, where):
    out = tuple((round(float(a), Q), round(float(b), Q), round(float(c or 0), Q))
                for a, b, c in re.findall(_PT, body))
    if kind == "text" and not out:
        raise ValueError(
            f"{where}: a text item parsed to NO position. A blind reader here reports every "
            f"text on the board as unchanged, so this refuses to compare rather than return "
            f"a false match.")
    return out


def graphics(board):
    """Everything that is NOT copper: silkscreen, fab, courtyard, mask, and the placement
    of every Reference and Value.

    ECO-25 ADDED THIS, AFTER SHIPPING A GATE THAT COULD NOT SEE A SILKSCREEN MOVE. The
    original compare() checked footprints, pads, vias and track coverage, and was described
    as proving "the same board". It proved the same COPPER. A user moved two refdes labels
    and hid three more in KiCad, and every comparison in this repository -- including the
    one written to catch exactly this -- reported the boards identical.

    Silkscreen is not cosmetic on a board somebody has to hand-assemble: it is how the
    builder knows which of C7 and C7A they are looking at, and those two are the same land
    in two places. Footprint graphics stay in LOCAL coordinates, so a footprint that moved
    is caught by the footprint comparison rather than reported twice here.
    """
    out = {"props": {}, "fp": {}, "top": []}
    for fp in kisexp.footprints(board):
        if not fp.at:
            continue
        for m in re.finditer(
                r'\(property "(Reference|Value)" "([^"]*)"\s*\n\s*\(at ([-\d.]+) ([-\d.]+)'
                r'(?: ([-\d.]+))?\)([\s\S]{0,300}?)\n\t\t\)', fp.body):
            tail = m.group(6)
            lay = re.search(r'\(layer "([^"]+)"\)', tail)
            out["props"][(fp.ref, m.group(1))] = (
                m.group(2), round(float(m.group(3)), Q), round(float(m.group(4)), Q),
                round(float(m.group(5) or 0), Q), lay.group(1) if lay else "",
                "(hide yes)" in tail)
        items = []
        for m in re.finditer(r'\(fp_(line|rect|poly|circle|arc|text)\b([\s\S]{0,4000}?)\n\t\t\)',
                             fp.body):
            lay = re.search(r'\(layer "([^"]+)"\)', m.group(2))
            if not lay or not any(k in lay.group(1) for k in _GRAPH_LAYERS):
                continue
            items.append((m.group(1), lay.group(1),
                          _pts(m.group(2), m.group(1), f"{fp.ref} fp_{m.group(1)}")))
        if items:
            out["fp"][fp.ref] = tuple(sorted(items))
    for m in re.finditer(r'\n\t\(gr_(line|rect|poly|circle|arc|text)\b([\s\S]{0,40000}?)\n\t\)',
                         board):
        lay = re.search(r'\(layer "([^"]+)"\)', m.group(2))
        if not lay or not any(k in lay.group(1) for k in _GRAPH_LAYERS):
            continue
        out["top"].append((m.group(1), lay.group(1),
                           _pts(m.group(2), m.group(1), f"top-level gr_{m.group(1)}")))
    out["top"] = sorted(out["top"])
    return out


def compare(b9, b10):
    """[] if the two boards carry the same copper, else a list of human-readable diffs."""
    bad = []
    f9, f10 = footprints(b9), footprints(b10)
    for ref in sorted(set(f9) | set(f10)):
        if ref not in f10:
            bad.append(f"footprint {ref} is missing from the KiCad 10 copy")
        elif ref not in f9:
            bad.append(f"footprint {ref} appears only in the KiCad 10 copy")
        elif f9[ref] != f10[ref]:
            a, b = f9[ref], f10[ref]
            for i, lab in enumerate(("value", "at", "layer", "attr", "name")):
                if a[i] != b[i]:
                    bad.append(f"{ref}.{lab}: {a[i]!r} -> {b[i]!r}")
            if a[5] != b[5]:
                bad.append(f"{ref}: {len(a[5] - b[5])} pad(s) changed "
                           f"(e.g. {sorted(a[5] - b[5])[:1]} -> {sorted(b[5] - a[5])[:1]})")
    v9, v10 = vias(b9), vias(b10)
    for v in sorted(v9 - v10):
        bad.append(f"via gone from the KiCad 10 copy: {v}")
    for v in sorted(v10 - v9):
        bad.append(f"via only in the KiCad 10 copy: {v}")
    r9, r10 = runs(b9), runs(b10)
    for k in sorted(set(r9) | set(r10), key=str):
        if r9.get(k) != r10.get(k):
            lay, net, ux, uy, off, w = k
            bad.append(f"track coverage differs on {lay} {net} w={w}: "
                       f"{r9.get(k)} -> {r10.get(k)}")
    g9, g10 = graphics(b9), graphics(b10)
    for k in sorted(set(g9["props"]) | set(g10["props"]), key=str):
        if g9["props"].get(k) != g10["props"].get(k):
            bad.append(f"{k[0]} {k[1]} text placement differs: "
                       f"{g9['props'].get(k)} -> {g10['props'].get(k)}")
    for ref in sorted(set(g9["fp"]) | set(g10["fp"])):
        if g9["fp"].get(ref) != g10["fp"].get(ref):
            a, b = set(g9["fp"].get(ref, ())), set(g10["fp"].get(ref, ()))
            bad.append(f"{ref}: non-copper graphics differ "
                       f"({len(a - b)} only in KiCad 9, {len(b - a)} only in KiCad 10)")
    if g9["top"] != g10["top"]:
        a, b = set(g9["top"]), set(g10["top"])
        bad.append(f"top-level non-copper graphics differ "
                   f"({len(a - b)} only in KiCad 9, {len(b - a)} only in KiCad 10)")
    return bad


# ----------------------------------------------------------------------------- the build
def convert(src=BOARD9, dst=BOARD10):
    """KiCad 9 board -> KiCad 10 board, via pcbnew. Needs KiCad 10 installed."""
    import pcbnew
    if not pcbnew.GetBuildVersion().startswith("10."):
        raise SystemExit(f"this needs KiCad 10; pcbnew reports {pcbnew.GetBuildVersion()}")
    b = pcbnew.LoadBoard(src)
    pcbnew.SaveBoard(dst, b)
    # SaveBoard ALSO drops a .kicad_pro and a .kicad_prl beside the board, and the .kicad_pro
    # it writes is a FRESH KICAD 10 DEFAULT -- min_hole_to_hole 0.25 against his 0.5,
    # min_clearance 0.0 against his 0.15, and six of his `ignore` severities promoted to
    # `warning`. That is the precise file that made this board look like it had 710
    # violations when it has 204. Shipping the KiCad 10 board next to it would hand the
    # recipient the same wrong answer, so it is overwritten with HIS project immediately.
    # The .prl is per-user UI state (open layers, zoom) and is not a deliverable at all.
    import check_drc
    stem = os.path.splitext(dst)[0]
    with open(stem + ".kicad_pro", "w", encoding="utf-8", newline="") as f:
        f.write(check_drc.project_file())
    if os.path.exists(stem + ".kicad_prl"):
        os.remove(stem + ".kicad_prl")
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the committed pair without converting (no KiCad needed)")
    a = ap.parse_args()
    if not a.check:
        convert()
        print(f"wrote {os.path.relpath(BOARD10, ROOT)}")
    if not os.path.exists(BOARD10):
        print("kicad10: the KiCad 10 companion is missing -- run without --check",
              file=sys.stderr)
        return 1
    b9, b10 = kisexp.load(BOARD9), kisexp.load(BOARD10)
    print(f"KiCad  9 board: version {version(b9)}, {len(tracks(b9))} segment(s), "
          f"{len(vias(b9))} via(s), {len(footprints(b9))} footprint(s)")
    print(f"KiCad 10 board: version {version(b10)}, {len(tracks(b10))} segment(s), "
          f"{len(vias(b10))} via(s), {len(footprints(b10))} footprint(s)")
    bad = compare(b9, b10)
    if bad:
        print(f"\nFAIL: {len(bad)} difference(s) between the two boards:", file=sys.stderr)
        for d in bad[:25]:
            print("  " + d, file=sys.stderr)
        return 1
    g = graphics(b9)
    print(f"ok: identical -- {len(runs(b9))} collinear track run(s), every footprint, pad, "
          f"via and net the same, and {len(g['props'])} text placement(s) + "
          f"{sum(len(v) for v in g['fp'].values()) + len(g['top'])} non-copper graphic(s) "
          f"match too")
    return 0


if __name__ == "__main__":
    sys.exit(main())
