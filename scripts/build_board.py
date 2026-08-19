#!/usr/bin/env python3
"""build_board.py -- regenerate the ClockxControl board from committed sources.

    python3 scripts/build_board.py                 # write the board
    python3 scripts/build_board.py --check         # build in memory, diff, write nothing
    python3 scripts/build_board.py -o /tmp/x.pcb   # build somewhere else

WHY THIS EXISTS

Until this file landed, the shipped board was the output of a script that lived in a
scratch directory and was never committed. ECO-8 said so in its own section 8.6 -- "the
script is not in the repository" -- which meant the deliverable could not be rebuilt by
anyone, including its author, and no gate could tell whether the committed board was
still the one the ECOs describe. Every number in ECO-6, ECO-7 and ECO-8 was a claim about
a binary blob nobody could re-derive.

This is SOLAR-GLOW's `Generated/` doctrine applied here: the artifact is a FUNCTION of
committed inputs, so it can be rebuilt, diffed, and gated. Its inputs are

    agbm-01-ram-desalvage.zip   the ECO-5 base board, already committed at repo root
    scripts/routes.json         the frozen ECO-6 routing
    the ECO tables below        every deliberate edit, one line each

and its output is byte-identical to `AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb` inside
`clockxcontrol-integration/board/agbm-01-clockxcontrol.zip`. Consistency check [1] asserts
exactly that, which is what makes the ECO documents auditable rather than decorative.

WHAT IT DOES, IN ECO ORDER

    ECO-6  move C7 out of the module window; move the FID2/FID5 fiducial pair; drop the
           two VDD2 stitching vias the R landing lands on; add the ClockxControl land
           pattern, the three wire pads (TP83/84/85), TP82 and the CK1 isolation jumper
           JP3; add the CXC_CLK net and route everything.
    ECO-7  mark X1/C3/C4 DNP -- the ClockxControl drives CK1 directly, so an assembly
           house must not fit the crystal or its load caps.
    ECO-8  thirteen Value/Description edits from the power review. No copper.

EVERY EDIT ASSERTS ITS OWN PRECONDITION. A replacement whose target string is missing, or
present more than once, fails the build instead of silently producing a different board.
That is the property that lets check [1] mean something.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_ZIP = os.path.join(ROOT, "agbm-01-ram-desalvage.zip")
BASE_MEMBER = "agbm-01-ram-desalvage/AGBM-01_AA_1-2_GBE-plus.kicad_pcb"
ROUTES = os.path.join(ROOT, "scripts", "routes.json")
SHIPPED_ZIP = os.path.join(ROOT, "clockxcontrol-integration", "board",
                           "agbm-01-clockxcontrol.zip")
SHIPPED_MEMBER = "agbm-01-clockxcontrol/AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb"
OUT = os.path.join(ROOT, "clockxcontrol-integration", "board",
                   "AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb")

# --- ECO-6 geometry ------------------------------------------------------------------
# The module body is 18.65 x 12.00 mm; MOD_X/MOD_Y is its centre. rev B moved it west out
# of the R3/TP114 cluster -- ECO-6 section 6.7 is the accounting for what that cost.
MOD_X, MOD_Y = 91.95, -44.95
C7_FROM, C7_TO = "(at 91.9 -41.1 180)", "(at 93.1 -37.4 180)"
FID_FROM, FID_TO = "(at 89.0 -48.0)", "(at 106.25 -57.25)"
DROP_VIAS = [(84.4, -45.9), (85.4, -45.9)]          # both on net 8 (VDD2)
VDD2_NET = 8
# The three button landings the module's plated through-holes solder down onto.
PADS = [("1", 4.525, 1.0, 71, "/CPU/TP2", "SEL"),
        ("2", 7.025, 3.5, 13, "/CPU/TP9", "L"),
        ("3", 7.025, 1.0, 12, "/CPU/TP8", "R")]
GHOSTS = [(4.525, 3.5), (4.525, -1.5), (7.025, -1.5)]   # F.Fab marks for the unused holes
LABELS = [("SEL", 3.0, 1.0), ("L", 8.5, 3.5), ("R", 8.5, 1.0)]
# The wire pads. y = -37.95, not -38.6: at -38.6 the 1.2 mm pads overlap the module body
# by 0.25 mm at their radius. KiCad's y grows DOWNWARD, which is the sign error that
# nearly shipped this row underneath the module.
WIRE_PADS = [("TP83", 97.9, -37.95, "CXC_CLK", "CLK", "CXC CLK wire"),
             ("TP84", 99.45, -37.95, "VDD3", "V+", "CXC V+ wire"),
             ("TP85", 101.0, -37.95, "GND", "V-", "CXC V- wire")]

# --- ECO-7: the crystal network is not fitted on a ClockxControl build ----------------
DNP_REFS = ("X1", "C3", "C4")

# --- ECO-8: the drop-in part swaps ---------------------------------------------------
# ref, field, old, new. Documented in clockxcontrol-integration/ECO-8_component_swaps.md;
# consistency check [3] holds that document's table and this list to the same values, so
# neither can drift from the other or from the board.
ECO8 = [
    ("U7",   "Value",       "TLV9364",       "TLV9064IPWR"),
    ("R23",  "Value",       "1.78M",         "1.69M"),
    ("DL1",  "Value",       "150060VS75000", "150060GS75000"),
    ("R25",  "Value",       "3.3k",          "22k"),
    ("PTC1", "Value",       "0467001.NR",    "0805L110SLYR"),
    ("PTC1", "Description", "0805L050WR",
     "PPTC resettable fuse, Littelfuse Low Rho, 1.10 A hold / 1.80 A trip, 6 Vdc, 0805"),
    ("F1",   "Value",       "0467001.NR",    "F0805B2R00FSTR"),
    ("F1",   "Description", "0805L050WR",
     "Fast-acting thin-film chip fuse, 2.00 A, 63 V, 0805"),
    ("R15",  "Value",       "10k",           "100k"),
    ("R16",  "Value",       "10k",           "100k"),
    ("R11",  "Value",       "1k",            "10k"),
    ("R24",  "Value",       "100k",          "1M"),
    ("R65",  "Value",       "100k",          "470k"),
]


def uid(seed):
    """Deterministic UUIDs. A random uuid4 per run would make the board unreproducible
    and check [1] impossible; these are a hash of a stable seed instead."""
    h = hashlib.sha1(("cxc-eco6:" + seed).encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def build():
    raw = zipfile.ZipFile(BASE_ZIP).read(BASE_MEMBER).decode("utf-8")
    # LINE ENDINGS ARE PART OF THE ARTIFACT. The ECO-5 base carries exactly ONE stray
    # CRLF, at the very end of the file -- the last `)\r\n`. The original generator read
    # the board with a text-mode open(), whose universal-newline translation silently
    # normalised it, so the shipped board is LF-throughout and one character shorter than
    # its input. Doing it implicitly is how a .kicad_pcb ends up alternating line endings
    # between saves; doing it here, deliberately, is what makes the rebuild byte-stable.
    # The count is asserted so that a base board with different line endings fails the
    # build instead of quietly producing a board that no longer matches the ECOs.
    crlf = raw.count("\r\n")
    if crlf != 1 or not raw.endswith(")\r\n"):
        raise AssertionError(
            f"base board line endings changed: {crlf} CRLF (expected exactly 1, at EOF). "
            "Normalisation is deliberate -- see the comment here before adjusting it.")
    txt = raw.replace("\r\n", "\n")
    orig_len = len(txt)
    R = json.load(open(ROUTES))

    def fp_span(ref):
        i = 0
        while True:
            i = txt.find("\n\t(footprint ", i)
            if i < 0:
                raise KeyError(f"{ref}: no such footprint on the board")
            j = txt.find("\n\t)\n", i + 1)
            b = txt[i + 1:j + 4]
            m = re.search(r'\(property "Reference" "([^"]+)"', b)
            if m and m.group(1) == ref:
                return (i + 1, j + 4, b)
            i = j + 1

    def replace_in(ref, old, new, what):
        nonlocal txt
        s, e, b = fp_span(ref)
        n = b.count(old)
        if n != 1:
            raise AssertionError(f"{ref}: {what} -- expected 1x {old!r}, found {n}")
        txt = txt[:s] + b.replace(old, new, 1) + txt[e:]

    # ---------- ECO-6.1  C7 out of the module window -------------------------------
    replace_in("C7", C7_FROM, C7_TO, "C7 relocation")

    # ---------- ECO-6.2  the fiducial pair out from under the module ----------------
    for ref in ("FID2", "FID5"):
        replace_in(ref, FID_FROM, FID_TO, "fiducial relocation")

    # ---------- ECO-6.3  drop the two VDD2 stitching vias under the R landing -------
    for ox, oy in DROP_VIAS:
        pat = re.compile(r"\n\t\(via\n\t\t\(at " + re.escape(f"{ox:g} {oy:g}")
                         + r"\).*?\n\t\)", re.S)
        m = pat.search(txt)
        if not m:
            raise AssertionError(f"via {ox},{oy} not found")
        if f"(net {VDD2_NET})" not in m.group(0):
            raise AssertionError(f"via {ox},{oy} is not on VDD2 -- refusing to drop it")
        txt = txt[:m.start()] + txt[m.end():]

    # ---------- ECO-7  the crystal network is not fitted ----------------------------
    for ref in DNP_REFS:
        replace_in(ref, "(attr smd)", "(attr smd dnp)", "DNP flag")

    # ---------- ECO-8  the drop-in part swaps --------------------------------------
    for ref, field, old, new in ECO8:
        replace_in(ref, f'(property "{field}" "{old}"',
                   f'(property "{field}" "{new}"', f"{field} swap")

    # ---------- ECO-6.4  the new footprints ----------------------------------------
    ghost = "".join(f'''\t\t(fp_circle
\t\t\t(center {cx} {cy})
\t\t\t(end {cx + 0.635} {cy})
\t\t\t(stroke (width 0.1) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid(f'ghost{k}')}")
\t\t)
''' for k, (cx, cy) in enumerate(GHOSTS))
    labels = "".join(f'''\t\t(fp_text user "{lab}"
\t\t\t(at {lx} {ly} 180)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('lbl' + lab)}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 0.7 0.7)
\t\t\t\t\t(thickness 0.12)
\t\t\t\t)
\t\t\t)
\t\t)
''' for lab, lx, ly in LABELS)
    padblocks = "".join(f'''\t\t(pad "{num}" smd circle
\t\t\t(at {x} {y} 180)
\t\t\t(size 1.27 1.27)
\t\t\t(layers "F.Cu" "F.Mask")
\t\t\t(solder_mask_margin 0.0635)
\t\t\t(net {net} "{nm}")
\t\t\t(pintype "passive")
\t\t\t(uuid "{uid('modpad' + num)}")
\t\t)
''' for num, x, y, net, nm, _lab in PADS)
    MOD = f'''\t(footprint "ClockxControl_GBA_GBC"
\t\t(layer "F.Cu")
\t\t(uuid "{uid('mod1')}")
\t\t(at {MOD_X} {MOD_Y} 180)
\t\t(descr "insideGadgets GBA/GBC ClockxControl mezzanine landing pattern. Module floats flat on this footprint; its plated through-hole pads are filled with solder from above to bond it to these pads. Geometry from MouseBiteLabs DMGC-CPU-01 rev 2.5.")
\t\t(tags "clockxcontrol insidegadgets mezzanine")
\t\t(attr smd exclude_from_bom)
\t\t(property "Reference" "MOD1"
\t\t\t(at 0 -7.4 180)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('modref')}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1 1)
\t\t\t\t\t(thickness 0.15)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Value" "ClockxControl"
\t\t\t(at 0 7.4 180)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid('modval')}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1 1)
\t\t\t\t\t(thickness 0.15)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(fp_text user "CLOCKXCONTROL"
\t\t\t(at 0 0 180)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('modtext')}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.05 1.05)
\t\t\t\t\t(thickness 0.2)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(fp_rect
\t\t\t(start -9.325 -6)
\t\t\t(end 9.325 6)
\t\t\t(stroke (width 0.2) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('modsilk')}")
\t\t)
\t\t(fp_rect
\t\t\t(start -9.325 -6)
\t\t\t(end 9.325 6)
\t\t\t(stroke (width 0.1) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid('modfab')}")
\t\t)
\t\t(fp_rect
\t\t\t(start -9.575 -6.25)
\t\t\t(end 9.575 6.25)
\t\t\t(stroke (width 0.05) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.CrtYd")
\t\t\t(uuid "{uid('modcrt')}")
\t\t)
{ghost}{labels}{padblocks}\t\t(embedded_fonts no)
\t)
'''

    def tp(ref, x, y, dia, net, netname, silk, val, sx=0.0, sy=1.5):
        return f'''\t(footprint "Bucketmouse:TestPoint_Pad_D1.0mm"
\t\t(layer "F.Cu")
\t\t(uuid "{uid('fp' + ref)}")
\t\t(at {x} {y})
\t\t(descr "ClockxControl mezzanine landing - position is photo-derived, verify against a physical module")
\t\t(tags "clockxcontrol landing")
\t\t(attr exclude_from_bom)
\t\t(property "Reference" "{ref}"
\t\t\t(at 0 -1.6 0)
\t\t\t(layer "F.SilkS")
\t\t\t(hide yes)
\t\t\t(uuid "{uid('ref' + ref)}")
\t\t\t(effects (font (size 1 1.1) (thickness 0.175)))
\t\t)
\t\t(property "Value" "{val}"
\t\t\t(at 0 1.6 0)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid('val' + ref)}")
\t\t\t(effects (font (size 1 1.1) (thickness 0.175)))
\t\t)
\t\t(fp_text user "{silk}"
\t\t\t(at {sx} {sy} 0)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('silk' + ref)}")
\t\t\t(effects (font (size 0.7 0.7) (thickness 0.12)))
\t\t)
\t\t(pad "1" smd circle
\t\t\t(at 0 0)
\t\t\t(size {dia} {dia})
\t\t\t(layers "F.Cu" "F.Mask")
\t\t\t(net {net} "{netname}")
\t\t\t(pintype "passive")
\t\t\t(uuid "{uid('pad' + ref)}")
\t\t)
\t\t(embedded_fonts no)
\t)
'''

    # (A TP82 'CXC V- wire' landing at (102, -41) was drafted here and NEVER SPLICED
    # into the board -- the original generator built the block and then left it out of
    # the final concatenation. Consistency check [9] found it by looking for a
    # footprint its own placement snapshot named. Dead code deleted 2026-08-19 rather
    # than revived: TP85 already lands V- 1.0 mm from the module edge, and a second
    # GND pad 4 mm further east buys nothing.)


    # ---------- ECO-6.5  the CXC_CLK net -------------------------------------------
    mnet = max(int(n) for n in re.findall(r'\n\t\(net (\d+) "', txt))
    NEWNET = mnet + 1
    lastnet = list(re.finditer(r'\n\t\(net \d+ "[^"]*"\)', txt))[-1]
    txt = txt[:lastnet.end()] + f'\n\t(net {NEWNET} "CXC_CLK")' + txt[lastnet.end():]

    NETNO = {"CXC_CLK": NEWNET, "VDD3": 10, "VDD35": 5, "GND": 2}
    LANDINGS = "".join(
        tp(ref, x, y, 1.2, NETNO[net], net, silk, val, sx=0.0, sy=1.35)
        for ref, x, y, net, silk, val in WIRE_PADS)

    JP3 = f'''\t(footprint "CXC:SolderJumper_2_Open"
\t\t(layer "F.Cu")
\t\t(uuid "{uid('jp3')}")
\t\t(at 45 -64.2)
\t\t(descr "CK1 isolation jumper for the ClockxControl CLK run. LEAVE OPEN for a crystal build; BRIDGE when populating the ClockxControl.")
\t\t(tags "solder jumper open")
\t\t(attr smd exclude_from_bom)
\t\t(property "Reference" "JP3"
\t\t\t(at 0 -1.6 0)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('jp3ref')}")
\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15)))
\t\t)
\t\t(property "Value" "CXC CLK"
\t\t\t(at 0 1.7 0)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid('jp3val')}")
\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15)))
\t\t)
\t\t(fp_rect
\t\t\t(start -1.35 -0.95)
\t\t\t(end 1.35 0.95)
\t\t\t(stroke (width 0.12) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('jp3silk')}")
\t\t)
\t\t(pad "1" smd circle
\t\t\t(at -0.65 0)
\t\t\t(size 1.05 1.05)
\t\t\t(layers "F.Cu" "F.Mask")
\t\t\t(net 3 "/CPU/CK1")
\t\t\t(pintype "passive")
\t\t\t(uuid "{uid('jp3p1')}")
\t\t)
\t\t(pad "2" smd circle
\t\t\t(at 0.65 0)
\t\t\t(size 1.05 1.05)
\t\t\t(layers "F.Cu" "F.Mask")
\t\t\t(net {NEWNET} "CXC_CLK")
\t\t\t(pintype "passive")
\t\t\t(uuid "{uid('jp3p2')}")
\t\t)
\t\t(embedded_fonts no)
\t)
'''

    # ---------- ECO-6.6  copper ----------------------------------------------------
    E, X = R["eco6"], R["eco6_extra"]
    segs, vias = [], []

    def add(net, runs, vs=()):
        for lay, pts in runs:
            for i in range(len(pts) - 1):
                if pts[i] == pts[i + 1]:
                    continue
                segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], lay, net))
        for (vx, vy) in vs:
            vias.append((vx, vy, net))

    for key in ("12", "71", "13"):                      # the three button landings
        add(int(key), E[key]["runs"], E[key]["vias"])
    add(NEWNET, E["CXC_CLK"]["runs"], E["CXC_CLK"]["vias"])
    add(NEWNET, [("F.Cu", [[97.9, -38.6], [97.9, -37.95]])])   # tail to the moved pad row
    vdd3 = [list(r) for r in E["VDD3"]["runs"]]
    vdd3[0] = ("F.Cu", [[99.45, -37.95], [99.25, -37.85], [99.25, -35.9]])
    add(10, vdd3, E["VDD3"]["vias"])
    add(2, [("F.Cu", [[101.0, -37.95], [100.2, -37.15], [100.2, -35.3]])])
    add(5, [("F.Cu", [[93.875, -37.4], [93.5, -37.2]])])       # C7's VDD35 pad
    add(2, [("F.Cu", [[92.325, -37.4], [93.3, -38.7]])], [(93.3, -38.7)])
    add(3, X["CK1"]["runs"], X["CK1"]["vias"])                 # JP3 pad 1 -> crystal node

    seg_txt = "".join(f'''\t(segment
\t\t(start {x0} {y0})
\t\t(end {x1} {y1})
\t\t(width 0.25)
\t\t(layer "{lay}")
\t\t(net {n})
\t\t(uuid "{uid(f'seg{i}')}")
\t)
''' for i, (x0, y0, x1, y1, lay, n) in enumerate(segs))
    via_txt = "".join(f'''\t(via
\t\t(at {x} {y})
\t\t(size 0.7)
\t\t(drill 0.3)
\t\t(layers "F.Cu" "B.Cu")
\t\t(net {n})
\t\t(uuid "{uid(f'via{i}')}")
\t)
''' for i, (x, y, n) in enumerate(vias))

    k = txt.rstrip().rfind("\n)")
    if k <= 0:
        raise AssertionError("board has no closing paren")
    txt = txt[:k + 1] + MOD + LANDINGS + JP3 + seg_txt + via_txt + txt[k + 1:]
    return txt, dict(orig_len=orig_len, new_len=len(txt), segs=len(segs),
                     vias=len(vias), net=NEWNET)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="build in memory and diff against the shipped board; write nothing")
    ap.add_argument("-o", "--out", default=OUT)
    a = ap.parse_args()
    txt, st = build()
    print(f"built {st['orig_len']} -> {st['new_len']} chars "
          f"(+{st['new_len'] - st['orig_len']}); {st['segs']} segments, {st['vias']} vias, "
          f"6 footprints, net {st['net']} CXC_CLK")
    if a.check:
        try:
            want = zipfile.ZipFile(SHIPPED_ZIP).read(SHIPPED_MEMBER).decode("utf-8")
        except (OSError, KeyError) as e:
            sys.exit(f"FAIL: cannot read the shipped board -- {type(e).__name__}: {e}")
        if txt == want:
            print("ok: rebuild is byte-identical to the shipped board")
            return 0
        sys.exit(f"FAIL: rebuild differs from the shipped board "
                 f"({len(txt)} vs {len(want)} chars). Regenerate and repack, or explain "
                 f"the difference in the ECO that made it.")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
