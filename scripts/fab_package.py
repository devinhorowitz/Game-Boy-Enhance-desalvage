#!/usr/bin/env python3
"""fab_package.py -- the zip you upload to PCBWay.

    python3 scripts/fab_package.py            # build it
    python3 scripts/fab_package.py --check    # rebuild in memory, compare, write nothing

THE ONE THING THAT MATTERS HERE

**The committed board's zone fill is MouseBiteLabs' own, from before this fork added any
copper.** That is deliberate -- check [14] exists so "we did not re-pour" stays checkable --
but it means GERBERS PLOTTED FROM THE COMMITTED FILE WOULD SHORT. 22 objects this fork adds
sit inside a foreign-net pour that the stale fill has not been recomputed around.

So this script never plots the committed board. It re-pours a throwaway copy first, exactly
as the assembled renders and the DRC do, and everything downstream comes off that copy.

AND IT REFUSES TO BUILD A BOARD THAT DOES NOT PASS DRC

A fab package is the expensive artifact: by the time a mistake surfaces it is on a panel.
So the DRC runs on the re-poured copy BEFORE anything is plotted, against MouseBiteLabs'
own project rules, diffed against his board by violation position -- and a single unledgered
violation aborts the build. There is no --force.

WHAT GOES IN THE ZIP

    gerbers/         F.Cu In1.Cu In2.Cu B.Cu, both masks, both silks, both pastes, Edge.Cuts
                     RS-274X with Protel extensions (.GTL/.G1/.G2/.GBL/...), 6-digit
    drill/           Excellon, millimetres, PTH and NPTH in separate files, plus a map
    assembly/        the position file and the BOM, straight out of pcbway-assembly/generated
    ORDER.txt        stackup, thickness, layer count, the four counts the assembly quote
                     form asks for, and the things a human has to tell them

DETERMINISM

Gerbers carry a creation timestamp and the generator's version string, so two runs are never
byte-identical. `--check` therefore compares CONTENT with those two lines stripped, which is
reproducible, and the manifest additionally records the SHA of the board and base the package
was plotted from -- the same honest gate the renders use.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom                                                      # noqa: E402
import kisexp                                                    # noqa: E402

# render_assembled and render_board are imported INSIDE the functions that need them, not
# here. render_board pulls in Pillow at module scope, and CI deliberately installs neither
# Pillow nor KiCad -- so a module-level import would make merely IMPORTING this file fail on
# the runner. Check [21] imports it for order_spec(), which needs nothing but a regex and
# MouseBiteLabs' README, and that has to keep working on a bare machine.

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "clockxcontrol-integration" / "board" / "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb"
GEN = ROOT / "pcbway-assembly" / "generated"
OUT = ROOT / "pcbway-assembly" / "fab" / "agbm-02-cxc-pcbway.zip"
MANIFEST = ROOT / "pcbway-assembly" / "fab" / "fab-manifest.json"

# THE ZIP THAT ACTUALLY GOES IN PCBWAY'S "PCB FILE" BOX, AND WHY IT IS A SECOND FILE.
# The full package above is the record: gerbers and drill in folders, plus the assembly
# CSVs and the order sheet. PCBWay's file review rejected it with "there is no drill file
# included in your design" -- with both .drl files present and valid Excellon, sitting in
# drill/. Their intake reads the archive flat, so a drill file one directory down is a
# drill file it never sees. The fix is not to argue: it is to hand them the shape every
# fab house expects -- FABRICATION DATA ONLY, NO FOLDERS.
UPLOAD = ROOT / "pcbway-assembly" / "fab" / "agbm-02-cxc-gerbers.zip"

# The drill MAPS are deliberately not in the upload. They are human-readable plots of where
# the holes are, they carry a .gbr extension, and a .gbr that is not a real layer is exactly
# what makes a viewer report a layer count nobody can explain. They stay in the record.
#
# NEITHER IS THE .gbrjob, AND THAT ONE IS NOT TIDINESS. It declares BoardThickness 1.2 and
# Finish "None"; this board is ordered at 1.0 mm with ENIG. Its layer identification is
# redundant -- the Protel extensions already say which file is which -- so the only thing it
# would add to the upload is two values that contradict the order form, in a file a fab's
# intake may well read in preference to a human. Out it goes, and check [21] fails if any
# file in the upload ever declares a thickness that disagrees with the spec again.
_MAP_SUFFIX = "_map.gbr"
_UPLOAD_EXCLUDE = (_MAP_SUFFIX, ".gbrjob")

# Protel extensions, because every fab house on earth reads them without being told which
# file is which. The inner layers are .g1/.g2 in KiCad's protel mapping.
PLOT_LAYERS = ("F.Cu,In1.Cu,In2.Cu,B.Cu,"
               "F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts")

# Files copied in from the generated buy documents. bom_split.py owns them; this script only
# carries them, so the package cannot disagree with what check [12] already gates.
ASSEMBLY_MEMBERS = (
    ("agbm-02-cxc-cpl.csv", "assembly/agbm-02-cxc-cpl.csv"),
    ("agbm-02-cxc-pcbway-assembly.csv", "assembly/agbm-02-cxc-bom.csv"),
    ("agbm-02-cxc-not-populated.csv", "assembly/agbm-02-cxc-do-not-populate.csv"),
)

# WHAT MOVES BETWEEN TWO IDENTICAL RUNS. Every one of these describes the generator or the
# clock, not the board, and every one of them appears in a different syntax per format:
#
#   gerber   %TF.CreationDate,...*%  %TF.GenerationSoftware,...*%
#            G04 Created by KiCad (PCBNEW 10.0.5) date 2026-08-21 14:06:35*
#   drill    ; DRILL file KiCad 10.0.5 date ...      ; #@! TF.CreationDate,...
#   gbrjob   JSON: Header.CreationDate, Header.GenerationSoftware.Version
#
# The first pass at this stripped only the two %TF lines and declared the package
# non-reproducible when every file still differed. A normaliser that silently under-matches
# is worse than none: it turns "I cannot compare these" into "these are different".
_VOLATILE_LINE = re.compile(
    rb"(?mi)^.*(?:TF\.CreationDate|TF\.GenerationSoftware|Created by KiCad"
    rb"|DRILL file KiCad).*\r?\n")


def _normalise(name: str, data: bytes) -> bytes:
    """The same board plotted twice has to compare equal, so take out the clock and the
    version string. Nothing that describes copper is touched."""
    if name.lower().endswith(".gbrjob"):
        try:
            d = json.loads(data)
            d.get("Header", {}).pop("CreationDate", None)
            d.get("Header", {}).get("GenerationSoftware", {}).pop("Version", None)
            return json.dumps(d, sort_keys=True, indent=1).encode()
        except ValueError:
            return data
    return _VOLATILE_LINE.sub(b"", data)


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-3:] or ["(no output)"]
        raise SystemExit("fab_package: " + cmd[2] + " failed:\n  " + "\n  ".join(tail))


# HIS README IS THE ORDER, NOT THE KICAD STACKUP. They disagree, and the disagreement is
# the kind that gets caught after the boards arrive: AGBM-02's KiCad file carries
# `(general (thickness 1.2))` and a stackup whose layers sum to 1.2 mm, while MouseBiteLabs'
# own README -- for AGBM-01, AGBM-02 and AGBM-11 alike -- says to order 1.0 mm. The stackup
# is a drawing aid he never adjusted; the README is what he tells people to buy, and a GBA
# shell is what decides. The first version of this sheet read the stackup and would have
# ordered 1.2 mm boards.
HIS_README = ROOT / "AGBM-02 (AA Batteries)" / "README.md"
_SPEC_LINE = re.compile(r"^-\s*(Thickness|Layers|Surface Finish)\s*:\s*(.+?)\s*$", re.M)


def order_spec() -> dict:
    """What MouseBiteLabs tells people to order, read off his own README."""
    txt = HIS_README.read_text(encoding="utf-8")
    head = txt.split("## Board Characteristics", 1)
    if len(head) < 2:
        raise SystemExit("fab_package: MouseBiteLabs' README has no 'Board Characteristics' "
                         "section any more -- the order spec cannot be read, and guessing it "
                         "is how you get 1.2 mm boards")
    spec = {k.lower().replace(" ", "_"): v for k, v in _SPEC_LINE.findall(head[1])}
    for want in ("thickness", "layers", "surface_finish"):
        if want not in spec:
            raise SystemExit(f"fab_package: his README no longer states {want!r}")
    return spec


def stackup(board: str) -> dict:
    """What the KiCad file says, so the sheet can flag where it differs from the order."""
    st = re.search(r"\(stackup\b(.*?)\n\t\t\)\n", board, re.S)
    st = st.group(1) if st else ""
    cu = re.findall(r'\(layer "([^"]+)"\s*\(type "copper"\)', st)
    thick = re.search(r"\(general\b.*?\(thickness ([\d.]+)\)", board, re.S)
    return {"copper_layers": len(cu),
            "board_thickness_mm": float(thick.group(1)) if thick else None}


def build(workdir: Path, verbose: bool = True) -> dict:
    """Re-pour, DRC, plot, drill. Returns {archive-path: bytes}."""
    board_text = BOARD.read_text(encoding="utf-8")
    pcb = workdir / "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb"
    pcb.write_text(board_text, encoding="utf-8", newline="")
    # HIS rules travel with the board, or KiCad silently falls back to its own defaults.
    (workdir / f"{pcb.stem}.kicad_pro").write_text(_project(), encoding="utf-8", newline="")

    say = (lambda m: print("  " + m)) if verbose else (lambda m: None)
    import render_assembled as R
    say(R.refill_zones(pcb))

    # ---- the gate that has to pass before a single aperture is plotted ----------------
    import check_drc
    ours = check_drc.drc(pcb.read_text(encoding="utf-8"), "fab")
    base = check_drc.drc(geom.base(), "base")
    from collections import Counter
    # Diff by POSITION, the same way check_drc does: a violation his board already has at
    # the same spot is his, not ours. Consume one occurrence per match so a doubled
    # violation on our side still counts as new.
    fb = Counter(check_drc.fingerprint(v) for v in base["violations"])
    new = []
    for v in ours["violations"]:
        f = check_drc.fingerprint(v)
        if fb[f] > 0:
            fb[f] -= 1
        else:
            new.append(v)
    unconnected = ours.get("unconnected_items", [])
    allowed = dict(check_drc.KNOWN_NEW)
    seen = Counter(v["type"] for v in new)
    bad = [f"{t} x{n}" for t, n in sorted(seen.items())
           if n > (allowed.get(t, (0, ""))[0])]
    if bad or len(unconnected) > len(check_drc.KNOWN_UNCONNECTED):
        raise SystemExit(
            "fab_package: REFUSING TO BUILD. The re-poured board does not pass DRC against\n"
            "  MouseBiteLabs' own rules with only the ledgered exceptions.\n"
            f"  unledgered: {', '.join(bad) or 'none'}\n"
            f"  unconnected: {len(unconnected)} (ledger allows "
            f"{len(check_drc.KNOWN_UNCONNECTED)})\n"
            "  Fix the board, or ledger the violation in check_drc.KNOWN_NEW with a reason.")
    say(f"DRC on the re-poured copy: {len(ours['violations'])} violation(s), "
        f"{len(new)} not on his board, all ledgered; {len(unconnected)} unconnected")

    # ---- plot -------------------------------------------------------------------------
    gdir, ddir = workdir / "g", workdir / "d"
    gdir.mkdir(); ddir.mkdir()
    _run(["kicad-cli", "pcb", "export", "gerbers", "--output", str(gdir),
          "--layers", PLOT_LAYERS, "--precision", "6", "--check-zones",
          "--subtract-soldermask", "--use-drill-file-origin", str(pcb)])
    _run(["kicad-cli", "pcb", "export", "drill", "--output", str(ddir),
          "--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th",
          "--excellon-zeros-format", "decimal", "--drill-origin", "plot",
          "--generate-map", "--map-format", "gerberx2", str(pcb)])

    members: dict[str, bytes] = {}
    for f in sorted(gdir.iterdir()):
        members[f"gerbers/{f.name}"] = f.read_bytes()
    for f in sorted(ddir.iterdir()):
        members[f"drill/{f.name}"] = f.read_bytes()
    if not any(k.lower().endswith((".gtl", ".gbr")) for k in members):
        raise SystemExit("fab_package: the plot produced no copper gerber")
    for src, dst in ASSEMBLY_MEMBERS:
        members[dst] = (GEN / src).read_bytes()
    members["ORDER.txt"] = order_sheet(board_text, members).encode("utf-8")
    say(f"{len(members)} member(s): {sum(len(v) for v in members.values()):,} bytes")
    return members


def _project() -> str:
    import check_drc
    return check_drc.project_file()


def fab_facts(board_text: str) -> dict:
    """The PCBWay form asks for numbers the gerbers cannot carry. Measure them off the
    board rather than eyeballing the design, because every one is a price tier or a
    rejection: declare a tier tighter than you need and you overpay, looser and DFM
    bounces it."""
    import collections
    seg = collections.Counter(
        float(m.group(1)) for m in
        re.finditer(r"\(segment\b(?:(?!\(segment)[\s\S])*?\(width ([\d.]+)\)", board_text))
    drills = collections.Counter(
        float(m.group(1)) for m in
        re.finditer(r"\(via\b(?:(?!\(via)[\s\S])*?\(drill ([\d.]+)\)", board_text))
    pads = re.findall(r"\(drill ([\d.]+)\)", board_text)
    xs, ys = [], []
    for x0, y0, x1, y1 in geom.edge_segments(board_text):
        xs += [x0, x1]; ys += [y0, y1]
    st = re.search(r"\(stackup\b(.*?)\n\t\t\)\n", board_text, re.S)
    cu = re.findall(r'\(layer "([^"]+)"\s*\(type "copper"\)\s*\(thickness ([\d.]+)\)',
                    st.group(1) if st else "")
    return {"size_x": max(xs) - min(xs), "size_y": max(ys) - min(ys),
            "min_track_mm": min(seg), "min_drill_mm": min(float(d) for d in pads),
            "via_drill_mm": min(drills), "vias": sum(drills.values()),
            "copper_mm": {n: float(t) for n, t in cu}}


# What PCBWay's assembly quote actually asks for, and why each is measured rather than
# counted by eye. "Fine pitch" is 0.65 mm because that is the coarsest pitch on this board
# that still needs a stencil-and-reflow process rather than a hand iron.
FINE_PITCH_MM = 0.65


def _pad_geometry(fp):
    """[(kind, x, y)] for one footprint, in its own local coordinates.

    Local coordinates are the point: rotation cancels out of a pitch, and every question
    below is about the footprint's internal shape, not where it sits on the board.
    """
    out = []
    for blk in kisexp.pad_blocks(fp.body):
        head = re.match(r'\(pad "[^"]*" (\S+) ', blk)
        at = re.search(r"\(at (-?[\d.]+) (-?[\d.]+)", blk)
        if head and at:
            out.append((head.group(1), float(at.group(1)), float(at.group(2))))
    return out


def _bands(vals, tol=0.05):
    """Cluster near-equal coordinates. -> [(centre, [indices])]."""
    out = []
    for i, v in sorted(enumerate(vals), key=lambda p: p[1]):
        if out and abs(v - out[-1][0]) <= tol:
            out[-1][1].append(i)
        else:
            out.append([v, [i]])
    return [(c, idx) for c, idx in out]


def _even(centres, tol=0.05):
    """True if these band centres are evenly spaced -- the signature of a pad ARRAY."""
    gaps = [b - a for a, b in zip(centres, centres[1:])]
    return len(gaps) >= 2 and max(gaps) - min(gaps) <= tol


def _package_shape(pads):
    """-> ("bga" | "quad" | "dual" | "discrete", lead_pitch_mm).

    THE FOUR-EDGE TEST IS WRONG AND U2 IS WHY. Asking "are there pads near all four edges
    of the bounding box?" calls U2 a QFP, because the corner pads of its two lead columns
    sit on the y-extremes. What separates a quad package from a dual one is not where the
    pads are but WHICH WAY THE LEAD ROWS RUN: a QFP has rows along both axes, a TSOP or
    TSSOP or VSON has rows along one. Count the rows, not the edges.

    AND THE FILLED-GRID TEST IS WRONG FOR THE SAME PART. U2's 96 pads sit in 4 columns of
    24, which is exactly rows x cols -- a "perfectly filled grid" by cell arithmetic, and
    it is not a BGA. What makes an array an array is that BOTH axes are evenly spaced.
    U2's four columns are 1.76, 13.79 and 3.87 mm apart, because they are two lead frames
    of different width sharing one land, so it fails on x and is correctly a dual package.

    Pitch is measured ALONG a lead row, never as the nearest pad-to-pad distance on the
    footprint: the nearest neighbour of a pad is often the pad opposite it in the other
    row, which reported EM1's 0.65 mm choke as a 0.013 mm part.
    """
    if len(pads) < 3:
        return "discrete", 0.0
    xs = [p[1] for p in pads]
    ys = [p[2] for p in pads]
    xb, yb = _bands(xs), _bands(ys)
    # A LEAD ROW IS NOT MERELY THREE PADS SHARING A COORDINATE. U2 again: each of its 24
    # y-bands holds one pad from each of its 4 columns, so a bare count test reads 24
    # horizontal "rows" and calls the part a QFP. A lead row is collinear AND EVENLY
    # SPACED -- U2's four columns sit 1.76, 13.79 and 3.87 mm apart and fail that at once,
    # while U1's bottom row of 38 pads on a uniform 0.5 mm passes.
    def _lead_rows(bands, along):
        out = []
        for c, idx in bands:
            if len(idx) >= 3 and _even(sorted(along[i] for i in idx)):
                out.append((c, idx))
        return out
    cols = _lead_rows(xb, ys)   # rows running along y
    rows = _lead_rows(yb, xs)   # rows running along x
    pitches = []
    for _, idx in cols:
        run = sorted(ys[i] for i in idx)
        pitches += [b - a for a, b in zip(run, run[1:]) if b - a > 0.01]
    for _, idx in rows:
        run = sorted(xs[i] for i in idx)
        pitches += [b - a for a, b in zip(run, run[1:]) if b - a > 0.01]
    pitch = min(pitches) if pitches else 0.0
    if (len(xb) >= 3 and len(yb) >= 3
            and _even([c for c, _ in xb]) and _even([c for c, _ in yb])):
        return "bga", pitch
    if cols and rows:
        return "quad", pitch
    if cols or rows:
        return "dual", pitch
    return "discrete", pitch


# What makes a two-terminal part polarity-critical, read off the distributor description
# rather than guessed from the reference prefix. A "C" can be a ceramic or a tantalum.
_POLARISED = re.compile(r"tantalum|polari[sz]ed|\bLED\b|\bdiode\b", re.I)


def _silk_points(fp):
    """Every silkscreen VERTEX in a footprint, text excluded. -> [(x, y)] local coords.

    Text is excluded here because the reference designator is silkscreen too and sits off
    to one side of nearly every part, so counting it would make every footprint look
    asymmetric. That exclusion is safe ONLY because a separate pass reads polarity glyphs
    off the board -- see polarity_risk(). It was not safe when this function was the whole
    test, and it is the reason three marked capacitors were reported as unmarked.
    """
    out = []
    for m in re.finditer(r"\(fp_(\w+)\b", fp.body):
        i, d = m.start(), 0
        for j in range(i, len(fp.body)):
            if fp.body[j] == "(":
                d += 1
            elif fp.body[j] == ")":
                d -= 1
                if d == 0:
                    break
        blk = fp.body[i:j + 1]
        if "SilkS" in blk and not blk.startswith("(fp_text"):
            out += [(round(float(a), 3), round(float(b), 3)) for a, b in re.findall(
                r"\((?:start|end|center|mid|xy) (-?[\d.]+) (-?[\d.]+)\)", blk)]
    return sorted(out)


# A polarity glyph is a "+" (or a "-"), drawn as free silkscreen text BESIDE a part rather
# than inside its footprint -- which is how a designer marks polarity without editing a
# shared library footprint. Anything further than this from the part belongs to another one.
POLARITY_GLYPHS = ("+", "-")
GLYPH_RADIUS_MM = 5.0


def polarity_marks(board_text: str) -> list:
    """[(glyph, x, y, layer)] -- every free silkscreen +/- on the board."""
    out = []
    for m in re.finditer(r"\n\t\(gr_text\b", board_text):
        i, d = m.start() + 1, 0
        for j in range(i, len(board_text)):
            if board_text[j] == "(":
                d += 1
            elif board_text[j] == ")":
                d -= 1
                if d == 0:
                    break
        blk = board_text[i:j + 1]
        t = re.search(r'\(gr_text\s+"([^"]*)"', blk)
        at = re.search(r"\(at (-?[\d.]+) (-?[\d.]+)", blk)
        lay = re.search(r'\(layer "([^"]+)"', blk)
        if t and at and lay and t.group(1).strip() in POLARITY_GLYPHS:
            out.append((t.group(1).strip(), float(at.group(1)), float(at.group(2)),
                        lay.group(1)))
    return out


def _pad_globals(fp):
    """{pad_number: (x, y)} in BOARD coordinates, footprint rotation applied."""
    fx, fy, rot = fp.at
    a = math.radians(-rot)
    out = {}
    for blk in kisexp.pad_blocks(fp.body):
        num = re.match(r'\(pad "([^"]*)"', blk)
        at = re.search(r"\(at (-?[\d.]+) (-?[\d.]+)", blk)
        if num and at:
            lx, ly = float(at.group(1)), float(at.group(2))
            out[num.group(1)] = (fx + lx * math.cos(a) - ly * math.sin(a),
                                 fy + lx * math.sin(a) + ly * math.cos(a))
    return out


def polarity_risk(board_text: str, described: dict) -> list:
    """Polarised parts and how the board indicates which way round they go.

    -> [(ref, mpn, verdict, detail)] where verdict is "marked" or "UNMARKED".

    THE FIRST VERSION OF THIS ONLY LOOKED INSIDE THE FOOTPRINT, and reported CP1, CP2 and
    CP3 as carrying no polarity mark at all. They carry one each: a "+" in free silkscreen
    beside pin 1, 1.825 mm from it, and CP2's sits on the opposite side of the part because
    CP2 is rotated 180 degrees. That is the normal way to mark polarity without editing a
    shared library footprint, and a reader that only opens the footprint cannot see it.
    The order sheet said "NO POLARITY MARK ANYWHERE ON THE BOARD" on the strength of it.

    So the test now asks the question that actually matters. Not "is the land symmetric?"
    -- it is, on every chip-scale polarised part ever made -- but "can the orientation be
    recovered from the board?", and if it can, WHICH END the mark identifies. A "+" beside
    the cathode is worse than no "+" at all, so that is an error here, not a pass.
    """
    marks = polarity_marks(board_text)
    out = []
    for fp in kisexp.footprints(board_text):
        if not fp.placed or fp.ref not in described or not fp.at:
            continue
        mpn, desc = described[fp.ref]
        if not _POLARISED.search(desc):
            continue
        pads = _pad_globals(fp)
        if len(pads) != 2 or "1" not in pads:
            continue
        side = "B.SilkS" if fp.layer == "B.Cu" else "F.SilkS"
        # SOURCE ONE: a glyph beside the part. SOURCE TWO: the footprint's own silkscreen
        # drawn asymmetrically -- the bracket a SOD land puts round the cathode, the
        # triangle-and-bar an LED land draws. Either one tells an assembler which way round
        # the part goes, and a part needs only one of them. Checking just the second is
        # what called three marked capacitors unmarked; checking just the first would call
        # four marked diodes unmarked. Both, or the answer is wrong somewhere.
        near = sorted(
            ((math.dist((fp.at[0], fp.at[1]), (x, y)), g, x, y)
             for g, x, y, lay in marks
             if lay == side and math.dist((fp.at[0], fp.at[1]), (x, y)) <= GLYPH_RADIUS_MM),
            key=lambda r: r[0])
        silk = _silk_points(fp)
        shaped = silk and silk != sorted((-x, y) for x, y in silk)
        if near:
            _d, glyph, gx, gy = near[0]
            d1 = math.dist(pads["1"], (gx, gy))
            d2 = math.dist(pads[sorted(k for k in pads if k != "1")[0]], (gx, gy))
            anode = (glyph == "+" and d1 < d2) or (glyph == "-" and d2 < d1)
            out.append((fp.ref, mpn, "marked" if anode else "UNMARKED",
                        f"'{glyph}' on {side}, {d1:.2f} mm from pad 1, {d2:.2f} mm from pad 2"
                        + ("" if anode else " -- THE MARK IS AT THE WRONG END")))
        elif shaped:
            out.append((fp.ref, mpn, "marked",
                        f"the land's own silkscreen is asymmetric ({len(silk)} vertices, "
                        "not mirror-equal) and shows which end is which"))
        else:
            out.append((fp.ref, mpn, "UNMARKED",
                        f"no polarity glyph within {GLYPH_RADIUS_MM:.0f} mm on {side}, and "
                        "the footprint's own silkscreen is mirror-symmetric"))
    return sorted(out)


def described_parts() -> dict:
    """{ref: (mpn, description)} from the resolved BOM. Descriptions are the distributor's
    own words, which is what makes "is this polarised?" a fact rather than a guess."""
    path = ROOT / "pcbway-assembly" / "resolved-mpns.json"
    try:
        res = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for e in res.get("entries", []):
        blurb = " ".join(str(e.get(k) or "") for k in ("desc", "note", "value"))
        for ref in e.get("refs", []):
            out[ref] = (e.get("mpn") or "", blurb)
    return out


def order_risk() -> list:
    """[(refs, mpn, guidance, fetched_on)] for buy lines dry at both distributors.

    STOCK IS NOT WRITTEN INTO THIS SHEET AND THAT IS DELIBERATE -- check_stock.py's own
    rule is that a frozen figure reads as current and is not. What IS durable, and what
    the person placing the order actually needs, is WHICH lines were dry when the data was
    fetched and whether a substitute exists at all: one of these is a reel change and the
    other has no equivalent in the market.
    """
    path = ROOT / "pcbway-assembly" / "resolved-mpns.json"
    try:
        res = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for e in res.get("entries", []):
        stocks = [(e.get(d) or {}).get("stock") for d in ("digikey", "mouser")]
        if [s for s in stocks if isinstance(s, int)] and not any(stocks):
                out.append((" ".join(e["refs"]), e.get("mpn") or "",
                        (e.get("alternate") or "").strip(),
                        res.get("generated_utc", "?")))
    return sorted(out)


def assembly_counts(board_text: str) -> dict:
    """The four counts PCBWay's assembly form asks for, off the board and the BOM.

    They are on the form because they price the job: unique parts sets the feeder count,
    BGA/QFP decides whether the run needs X-ray, and through-hole decides whether it needs
    a second, manual process at all. Getting one wrong is a requote, so derive each from
    the artifact rather than typing a remembered number -- swap a footprint and the sheet
    moves with it.
    """
    every = list(kisexp.footprints(board_text))
    placed = [fp for fp in every if fp.placed]
    # The parts a human still has to solder. Named, not counted, because "0 through-hole"
    # on the form is only true of the ASSEMBLY scope and an assembler reading it should be
    # told immediately which real parts are waiting on the far side of that boundary.
    unplaced_th = sorted(
        f.ref for f in every
        if not f.placed and any(k == "thru_hole" for k, _, _ in _pad_geometry(f)))
    smd, thru, quad, bga, fine = [], [], [], [], []
    for fp in placed:
        pads = _pad_geometry(fp)
        (thru if any(k == "thru_hole" for k, _, _ in pads) else smd).append(fp.ref)
        shape, pitch = _package_shape(pads)
        if shape == "bga":
            bga.append(fp.ref)
        elif shape == "quad":
            quad.append(fp.ref)
        if pitch and pitch <= FINE_PITCH_MM + 1e-9:
            fine.append((fp.ref, fp.name.split(":")[-1], pitch,
                         "top" if fp.layer == "F.Cu" else "bottom"))
    with open(GEN / "agbm-02-cxc-pcbway-assembly.csv", newline="", encoding="utf-8") as fh:
        bom = list(csv.DictReader(fh))
    return {"placements": len(placed), "smd": sorted(smd), "through_hole": sorted(thru),
            "unplaced_through_hole": unplaced_th,
            "quad": sorted(quad), "bga": sorted(bga),
            "fine_pitch": sorted(fine, key=lambda r: (r[2], r[0])),
            "bom_lines": len(bom), "unique_mpns": len({r["mpn"] for r in bom})}


def npth_owners(board_text: str) -> list:
    """[(ref, footprint, n_holes, diameter_mm)] for every part with non-plated holes.

    WRITTEN BECAUSE THE SHEET GOT THIS WRONG. It said the NPTH file "carries the shell
    mounting holes". It does not: the shell holes are cut out of Edge.Cuts by the router,
    and the NPTH file's two 1.8 mm holes are the locating pegs on the underside of P3, the
    CUI SJ-3524-SMT headphone jack. The conclusion was right -- the file is not optional --
    but the reason was invented, and a fab told "these are enclosure holes" has been told
    something false about a part it is about to drill around.
    """
    out = []
    for fp in kisexp.footprints(board_text):
        holes = [re.search(r"\(drill ([\d.]+)\)", blk) for blk in kisexp.pad_blocks(fp.body)
                 if "np_thru_hole" in blk]
        holes = [float(m.group(1)) for m in holes if m]
        if holes:
            out.append((fp.ref, fp.name.split(":")[-1], len(holes), min(holes), max(holes)))
    return sorted(out)


def order_sheet(board_text: str, members: dict) -> str:
    s = stackup(board_text)
    # COUNT WITH A CSV READER, NOT BY SPLITTING ON NEWLINES. The BOM's note column carries
    # multi-line quoted text, so a naive split reported 70 lines where there are 68 -- a
    # number this sheet then hands to the assembler as the size of their job.
    def _rows(name):
        with open(GEN / name, newline="", encoding="utf-8") as fh:
            return sum(1 for _ in csv.DictReader(fh))
    n_cpl = _rows("agbm-02-cxc-cpl.csv")
    n_bom = _rows("agbm-02-cxc-pcbway-assembly.csv")
    n_dnp = _rows("agbm-02-cxc-not-populated.csv")
    gerbers = sorted(k.split("/")[-1] for k in members if k.startswith("gerbers/"))
    drills = sorted(k.split("/")[-1] for k in members if k.startswith("drill/"))
    spec = order_spec()
    st = stackup(board_text)
    f = fab_facts(board_text)
    a = assembly_counts(board_text)
    described = described_parts()
    pol = polarity_risk(board_text, described)
    unmarked = [r for r in pol if r[2] != "marked"]
    # The sheet says whichever of these is TRUE, and the loud version is reserved for when
    # something really is unmarked. An earlier revision printed the loud version
    # unconditionally, on a board where every polarised part is marked -- which is how a
    # fab ends up being told, in capitals, something the board contradicts.
    if unmarked:
        polar_head = ("PARTS THAT MUST GO IN ONE WAY ROUND AND THE BOARD DOES NOT SAY WHICH.\n"
                      "     A machine reads the position file's rotation; if that is wrong these go\n"
                      "     in backwards and nothing downstream catches it. Confirm before the run:")
        polar_list = "".join(f"\n       {r:5s} {m:26s} {why}" for r, m, _v, why in unmarked)
    else:
        polar_head = (f"All {len(pol)} polarised part(s) on this board are marked, and the\n"
                      "     mark is at the correct end of each. Nothing here needs a special\n"
                      "     instruction -- this is the list so it can be checked against the board:")
        polar_list = "".join(f"\n       {r:5s} {m:26s} {why}" for r, m, _v, why in pol)
    risk = order_risk()
    # The repo's own note on each of these runs to a paragraph of provenance -- which
    # revision closed which blocker, what a superseded sentence used to say. A fab does not
    # need the history, only the decision, so take the head of it and point at the README
    # for the rest. Splitting on ". " before a capital keeps "$1.14" and "-TR" intact.
    def _head(text, n=2):
        parts = re.split(r"(?<=[a-z)\d])\.\s+(?=[A-Z0-9])", text)
        out = ". ".join(parts[:n]).strip()
        return (out + ("." if out and not out.endswith(".") else "")
                + (" Full reasoning: pcbway-assembly/README.md section 3."
                   if len(parts) > n else ""))
    risk_list = "\n".join(
        f"  {refs} -- {mpn}\n     dry at BOTH distributors when the parts were last "
        f"resolved ({when}).\n"
        + textwrap.fill(_head(guidance), 92, initial_indent="     ", subsequent_indent="     ")
        for refs, mpn, guidance, when in risk) or "  (none)"
    n_smd, n_thru = len(a["smd"]), len(a["through_hole"])
    n_bgaqfp, n_fine = len(a["bga"]) + len(a["quad"]), len(a["fine_pitch"])
    uth = a["unplaced_through_hole"]
    named = [r for r in uth if not r.startswith("TP")]
    n_uth, n_uth_named, uth_named = len(uth), len(named), ", ".join(named)
    front = [r for r, _, _, sd in a["fine_pitch"] if sd == "top"]
    front_refs = " and ".join(front) if len(front) < 3 else ", ".join(front)
    npth_list = "".join(
        f"\n    {r:5s} {nm:28s} {n} hole(s) at "
        + (f"{lo:.2f} mm" if lo == hi else f"{lo:.2f}-{hi:.2f} mm")
        for r, nm, n, lo, hi in npth_owners(board_text)) or "\n    (none)"
    fine_list = "".join(f"\n                            {r:5s} {nm:34s} {pt:.2f} mm  {sd}"
                        for r, nm, pt, sd in a["fine_pitch"])
    # Say WHY the two numbers differ rather than leaving a reader to wonder whether one of
    # them is a miscount. Naming the part is what makes it checkable.
    dupnote = ""
    if a["unique_mpns"] != a["bom_lines"]:
        import collections as _c
        with open(GEN / "agbm-02-cxc-pcbway-assembly.csv", newline="", encoding="utf-8") as fh:
            vals = _c.defaultdict(list)
            for r in csv.DictReader(fh):
                vals[r["mpn"]].append(r["value"])
        dup = sorted(m for m, v in vals.items() if len(v) > 1)
        pad = "\n" + " " * 26
        dupnote = (pad + "They differ because " + ", ".join(dup) + " appears on more" +
                   pad + "than one line -- same part, different schematic value strings" +
                   pad + "(" + "; ".join(" / ".join(vals[m]) for m in dup) + ")." +
                   " ONE FEEDER, not two.")
    finish = spec["surface_finish"].replace("**", "")
    # The stackup and his README disagree about thickness. Say so, loudly, rather than
    # picking one silently -- the .gbrjob in this same package declares the stackup's
    # number, so anything reading that instead of this sheet will see 1.2.
    mismatch = ""
    if st["board_thickness_mm"] and abs(
            st["board_thickness_mm"] - float(spec["thickness"].rstrip("m").rstrip("m"))) > 0.001:
        mismatch = f"""
  !! THE KICAD STACKUP SAYS {st['board_thickness_mm']} mm AND IT IS WRONG FOR ORDERING.
     MouseBiteLabs' own README for this board says {spec['thickness']}, and so do his
     READMEs for AGBM-01 and AGBM-11. The stackup is a drawing aid he never adjusted; the
     shell is what decides. The .gbrjob included with these gerbers repeats the stackup's
     number, so if anything upstream reads that file instead of this sheet, override it.
     ORDER {spec['thickness']}.
"""
    return f"""AGBM-02 + ClockxControl -- PCBWay order sheet
=============================================

Generated by scripts/fab_package.py from the board in this repository. Do not hand-edit;
regenerate instead. The three order options below are read from MouseBiteLabs' own
"Board Characteristics" section, not inferred from the KiCad file.

ORDER OPTIONS -- these must be set on the form; the gerbers cannot carry them
  Thickness ............. {spec['thickness']}
  Layers ................ {spec['layers']}
  Surface finish ........ {finish}
{mismatch}
  For this fork specifically, treat ENIG as REQUIRED: the board keeps its membrane
  contacts for the D-pad and buttons, so the HASL exception does not apply unless you are
  also fitting tactile switches.

MEASURED OFF THE BOARD -- the rest of the form
  Size (single) ......... {f['size_x']:.2f} x {f['size_y']:.2f} mm
  Material .............. FR-4. Let PCBWay apply their free TG150 upgrade
  Min track/spacing ..... 6/6 mil. The narrowest track is {f['min_track_mm']:.4f} mm
                          ({f['min_track_mm'] / 0.0254:.2f} mil) and the FFC lands sit on a
                          0.200 mm gap, so 8/8 mil is a hair too tight to declare
  Min hole size ......... {f['min_drill_mm']:.2f} mm  -> pick the 0.3 mm tier
  Finished copper ....... 1 oz outer, 1 oz inner ({', '.join(f'{k} {v}' for k, v in
                          sorted(f['copper_mm'].items()))} mm)
  Via process ........... TENTING VIAS. All {f['vias']} vias are already tented in the mask
                          gerbers -- zero apertures over any of them -- which matters
                          because the ClockxControl lies flat over 25 of them
  Impedance control ..... none
  Castellations ......... none
  Edge plating .......... none
  Edge connector ........ no. P1 is a through-hole cartridge socket, not a gold finger

BOARD
  Outline ............... in Edge.Cuts. It includes 13 shell holes and two routed openings
                          INSIDE footprints (SW1's switch shaft, VR2's wheel), so the
                          router has to follow Edge.Cuts, not the bounding box

WHICH FILE YOU ACTUALLY UPLOAD
  This archive is the RECORD. The file that goes in PCBWay's "PCB file" box is the other
  one, agbm-02-cxc-gerbers.zip: the same gerbers and the same two drill files, FLAT, with
  no folders and nothing but fabrication data in it.

  That is not a preference. The first upload was this archive, and it came back as "there
  is no drill file included in your design" -- with both .drl files present, valid Excellon,
  sitting one directory down in drill/. Intake reads the archive flat. A drill file in a
  folder is a drill file nobody sees.

  The BOM and the position file go in the ASSEMBLY upload on the order form, not in the
  PCB file. They are in assembly/ here so the record is complete.

GERBERS ({len(gerbers)} files, RS-274X, 6-digit, Protel extensions)
  .GTL / .G1 / .G2 / .GBL ... copper, top to bottom
  .GTS / .GBS ............... solder mask
  .GTO / .GBO ............... silkscreen
  .GTP / .GBP ............... solder paste (stencil)
  .GM1 ...................... board outline (Edge.Cuts)

DRILL ({len(drills)} files, Excellon, millimetres)
  PTH and NPTH are SEPARATE files, and the NPTH file is NOT OPTIONAL:{npth_list}
  Those are locating pegs on the underside of the part, not enclosure holes -- the shell
  holes are cut out of Edge.Cuts by the router. Drop the NPTH file and the jack has nothing
  to seat into.

ASSEMBLY
  Side .................. both. Most of the fine-pitch work is on the BACK; {front_refs}
                          are the exceptions and sit on the front.
  Placements ............ {n_cpl}   (assembly/agbm-02-cxc-cpl.csv)
  BOM lines ............. {n_bom}   (assembly/agbm-02-cxc-bom.csv)
  Do not populate ....... {n_dnp} lines (assembly/agbm-02-cxc-do-not-populate.csv)
  Rotation .............. KiCad convention, byte-identical to `kicad-cli pcb export pos`.
                          Origin is the lower-left corner of the outline, X right, Y up.

  -- the four numbers the assembly quote form asks for, measured, not remembered --
  Unique parts .......... {a['unique_mpns']} distinct manufacturer part numbers across {a['bom_lines']} BOM lines.{dupnote}
  SMD parts ............. {n_smd} -- EVERY placement. Not one part in the assembly scope
                          has a through-hole pad.
  Through-hole parts .... {n_thru}. The board does have through-hole pads -- {n_uth} footprints carry
                          them, {n_uth_named} of them real parts and the rest test points -- but every
                          one is on the do-not-populate list and is fitted by hand
                          afterwards. Nothing on this order needs selective solder or a
                          wave. The {n_uth_named}: {uth_named}.
  BGA / QFP parts ....... {n_bgaqfp}. There is no BGA anywhere on this board, and the only quad
                          flat pack is U1, the QFP-128 AGB CPU -- which is a SALVAGED part,
                          excluded from both the BOM and the position file, and never
                          touched by the line.
  Fine pitch ............ {n_fine} placements at {FINE_PITCH_MM} mm or finer:{fine_list}
                          U2 is the one to look at twice. Its land carries TWO overlapping
                          TSOP-48 patterns, 96 pads for a 48-pin part, so that a salvaged
                          AGB SRAM and the ordered CY62157EV30LL-45ZXIT both fit. Only the
                          OUTER pair is pasted -- 48 apertures there, none on the inner
                          pair -- so the stencil already says which land takes the part.
                          Follow the paste layer.

THINGS A HUMAN HAS TO TELL THEM
  1. POLARITY. {polar_head}{polar_list}
     CP1-CP3 are the ones to confirm on a first article anyway: they are 100 uF tantalums,
     they fail SHORTED when reversed, and the land underneath them is symmetric -- so if the
     rotation in the position file is ever read against the wrong end, the silkscreen "+" is
     the only thing that disagrees, and no electrical test before power-on will catch it.
  2. Parts on the do-not-populate list are not all jumpers and test pads. P1 (cartridge
     slot) and P4 (link port) are real parts the builder fits by hand afterwards.
  3. U1's land takes a SALVAGED AGB CPU and is not on the BOM at all, because no
     distributor sells one. U2 is an ordinary orderable part and is on the BOM.
  4. Two solder jumpers (JP2, JP3) are closed by hand after assembly, and only if the
     CY62157EV30LL is fitted. Leave them open otherwise.

PARTS THAT MAY NOT BE ORDERABLE
{risk_list}
  Every figure above carries the date it was fetched, because an undated stock number reads
  as current and is not. Re-run scripts/check_stock.py before placing the order. Both lines
  are MouseBiteLabs' own parts, not fork substitutions -- an availability problem in the
  base design, and check [6] in this repository warns for as long as either stays dry.

WHAT IS NOT IN THIS PACKAGE
  No stencil order, no panel drawing, no impedance control. If the assembler needs a paste
  stencil they can make it from .GTP/.GBP, which are plotted only where a part is actually
  placed -- every DNP land and every membrane contact has had its aperture removed.
"""


def digest(members: dict) -> str:
    h = hashlib.sha256()
    for k in sorted(members):
        h.update(k.encode())
        h.update(hashlib.sha256(_normalise(k, members[k])).digest())
    return h.hexdigest()[:16]


def upload_members(members: dict) -> dict:
    """Fabrication data only, flattened to the archive root. Collisions are fatal.

    Flattening is the whole point, so it has to be checked rather than assumed: two files
    with the same basename in different folders would silently become one, and the one that
    survived would be whichever sorted last. On this board there are none, and if a future
    layer set ever introduced one this raises instead of shipping a package missing a layer.
    """
    out, seen = {}, {}
    for k, v in members.items():
        if not (k.startswith("gerbers/") or k.startswith("drill/")):
            continue
        if k.endswith(_UPLOAD_EXCLUDE):
            continue
        name = k.split("/")[-1]
        if name in seen:
            raise SystemExit(f"fab_package: flattening collides -- {seen[name]} and {k} "
                             f"both become {name}. Rename one before shipping.")
        seen[name] = k
        out[name] = v
    drills = [n for n in out if n.lower().endswith((".drl", ".drd", ".txt"))]
    if not drills:
        raise SystemExit("fab_package: the upload zip has no drill file, which is the exact "
                         "thing PCBWay rejected it for")
    if not any("NPTH" in n for n in drills):
        raise SystemExit("fab_package: the upload zip has no NPTH drill file -- it carries "
                         "P3's locating pegs and the jack cannot seat without them")
    return out


def write_zip(members: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for k in sorted(members):
            zi = zipfile.ZipInfo(k, date_time=(2026, 8, 21, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, members[k])


def _source_digest() -> dict:
    import render_board as _rb
    return _rb.source_digest(kisexp.load(str(BOARD)), geom.base())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not shutil.which("kicad-cli"):
        print("fab_package: kicad-cli not found -- needs KiCad. NOT RUN.", file=sys.stderr)
        return 2
    try:
        import pcbnew                                            # noqa: F401
    except ImportError:
        print("fab_package: the pcbnew module is missing, so the copy cannot be re-poured, "
              "and gerbers off the stored fill would SHORT. NOT RUN.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as td:
        members = build(Path(td), verbose=not a.check)
    d = digest(members)
    if a.check:
        if not OUT.exists():
            print(f"fab_package: {OUT.relative_to(ROOT)} has never been built")
            return 1
        with zipfile.ZipFile(OUT) as z:
            have = {n: z.read(n) for n in z.namelist()}
        if digest(have) != d:
            only_a = sorted(set(members) - set(have))
            only_b = sorted(set(have) - set(members))
            diff = [k for k in sorted(set(members) & set(have))
                    if _normalise(k, members[k]) != _normalise(k, have[k])]
            print("fab_package: the shipped package is NOT what this board plots to."
                  + (f" missing: {only_a}" if only_a else "")
                  + (f" extra: {only_b}" if only_b else "")
                  + (f" changed: {diff}" if diff else ""))
            return 1
        up = upload_members(members)
        if not UPLOAD.exists():
            print(f"fab_package: {UPLOAD.relative_to(ROOT)} has never been built")
            return 1
        with zipfile.ZipFile(UPLOAD) as z:
            have_up = {n: z.read(n) for n in z.namelist()}
        if digest(have_up) != digest(up):
            print("fab_package: the shipped UPLOAD zip is NOT what this board plots to "
                  f"(has {sorted(have_up)}, wants {sorted(up)})")
            return 1
        print(f"ok: the shipped package is what this board plots to ({len(have)} members, "
              f"content {d}); the flat upload zip matches too ({len(have_up)} members, "
              f"content {digest(up)})")
        return 0
    write_zip(members, OUT)
    up = upload_members(members)
    write_zip(up, UPLOAD)
    MANIFEST.write_text(json.dumps(
        {"content": d,
         "members": sorted(members),
         "upload_content": digest(up),
         "upload_members": sorted(up),
         "source": _source_digest(),
         "kicad": subprocess.run(["kicad-cli", "version"], capture_output=True,
                                 text=True).stdout.strip()},
        indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes, "
          f"{len(members)} members, content {d})")
    print(f"wrote {UPLOAD.relative_to(ROOT)} ({UPLOAD.stat().st_size:,} bytes, "
          f"{len(up)} members, flat, content {digest(up)}) <- THIS is the PCB file upload")
    return 0


if __name__ == "__main__":
    sys.exit(main())
