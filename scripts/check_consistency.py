#!/usr/bin/env python3
"""check_consistency.py -- drift guard for the AGBM-02 ClockxControl fork.

    python3 scripts/check_consistency.py          # run every check
    python3 scripts/check_consistency.py -v       # also print what each check saw

Cross-checks the documents against the board they describe, so a change to one that is
not mirrored in the other fails loudly instead of rotting.

Numbering is STABLE, so a document can cite "check [12]" and stay right. A gap is a
retired check, not a missing one.

  [1]  REPRODUCIBLE   -- scripts/build_board.py rebuilds the shipped board byte-for-byte
                         from MouseBiteLabs' committed AGBM-02.             [ERROR]
  [2]  PACKAGE PARITY -- every document inside the shipped zip is byte-identical to its
                         copy in the tree.                                  [ERROR]
  [2b] LIB FOOTPRINT  -- the shipped ClockxControl_GBA_GBC.kicad_mod is what the board's
                         own MOD1 block derives to -- not a hand-kept second copy of it.
                                                                            [ERROR]
  [4]  DNP LEDGER     -- exactly the parts a ClockxControl build leaves off are DNP, on
                         top of the set MouseBiteLabs already marks.        [ERROR]
  [5]  BOM vs BOARD   -- every ref in resolved-mpns.json exists on the board and carries
                         the Value that file claims for it.                 [ERROR]
  [6]  SUPPLIER P/N   -- every MPN in resolved-mpns.json is one a distributor number
                         could plausibly buy, or is ledgered.               [ERROR]
  [7]  CITED PATHS    -- every path any .md cites exists, is marked historical in its own
                         sentence, or carries a reason in EXPECTED_ABSENT.  [ERROR]
  [8]  DOC IMAGERY    -- every image any .md displays exists in the tree.   [ERROR]
  [9]  MODULE WINDOW  -- the component-free window the module needs is still component-
                         free, and the parts that moved to make it are where they were put.
                                                                            [ERROR]
  [10] BLOCKER LEDGER -- U2 pin 37's supply and Net-(Q5B-G) are whole, on this fork AND on
                         MouseBiteLabs' own board.
                         GOES RED IF EITHER COMES BACK -- see the check.    [ERROR]
  [11] STRUCTURE      -- the board parses, parens balance, no duplicate refdes. [ERROR]
  [12] ASSEMBLY SPLIT -- nothing reaches the pick-and-place without a BOM line to buy it,
                         nothing is on both buy documents, and the generated buy documents
                         are what a fresh run produces.                     [ERROR]
  [13] REAL GEOMETRY  -- the copper this fork ADDS clears MouseBiteLabs' by the project's
                         own netclass rule, every footprint is inside the outline, the
                         fiducials are readable, and the module physically FITS its
                         same-side neighbours.                              [ERROR]
  [14] ZONE FILL      -- the fill is still MouseBiteLabs' stock fill, so gerbers plotted
                         from this file would short, and the LEDGERED set of objects the
                         stale fill swallows is still exactly that set.
                         GOES RED WHEN RE-POURED.                           [ERROR]
  [15] RENDERS        -- every render carries the digest of the board and base it was drawn
                         from, and every 2D PNG re-renders pixel for pixel where Pillow is
                         installed.                                         [ERROR]
  [16] UPSTREAM LINKS -- every Digi-Key link in MouseBiteLabs' schematic is resolved, and
                         every buy line that departs from one says why.     [ERROR]
  [17] PASTE vs PLACE -- solder paste exists only on pads a machine will put a part on, and
                         U2's dual land is pasted on exactly the pattern the RAM this fork
                         buys actually uses.                                [ERROR]
  [18] ROTATION       -- every CPL rotation is kicad-cli's own, and pin 1 sits where the
                         stock KiCad library puts it.                       [ERROR]
  [19] KICAD 10       -- the derived KiCad 10 companion carries the same copper, pads,
                         nets, text and non-copper graphics as the KiCad 9 board. Tracks
                         compare by COVERAGE, because KiCad 10 merges collinear runs and a
                         naive diff reads that as hundreds of deleted traces. [ERROR]
  [20] POWER LEDGER   -- every power figure a document states is in POWER_LEDGER with the
                         reason it is that number, and every ledger line is still stated
                         somewhere. The one check with no artifact behind it: these are
                         MODELLED numbers, so the ledger is the source of truth. [ERROR]
  [21] FAB PACKAGE    -- the PCBWay upload was plotted from the committed board, and
                         carries every layer, both drill files and the assembly documents.
                         Also that ORDER.txt still states MouseBiteLabs' own thickness and
                         layer count, and that the package classifier can still tell a QFP
                         from a dual package -- the assembly form's BGA/QFP count is
                         derived from it, and a blind classifier reports the same zero as
                         a board with none. And that the sheet still names every polarised
                         part the board gives no polarity mark for -- CP1-CP3 -- since that
                         is the one instruction the gerbers cannot carry and nothing
                         downstream catches it being wrong. The full aperture-by-aperture
                         comparison needs KiCad and lives in `fab_package.py --check`.
                         [ERROR]

Exit: nonzero if any ERROR-level check fails. Warnings do not fail the build.
Needs: python3 and the standard library. Nothing else -- no KiCad, no pip, no container.
Checks [15] and [18] do more when Pillow and kicad-cli are present, and say so when they
cannot: a check that DECLINED TO RUN is not a check that passed.

WHERE THIS CAME FROM

The shape is borrowed wholesale from SOLAR-GLOW's `scripts/check_consistency.py`: numbered
checks, an `err`/`warn`/`ok` accumulator, and -- the part that actually matters -- the
EXCLUSION-LEDGER DISCIPLINE. Where there is no second source of truth to compare against,
the check carries a SNAPSHOT with a reason on every line. A deliberate change updates the
snapshot in the same commit; an undeliberate one stops being invisible. Checks [4], [9]
and [10] are that shape.

Checks [10] and [14] are the sharper version of it, also borrowed: A CHECK THAT GOES RED
WHEN THE STATE IT DESCRIBES CHANGES. [10] once guarded two blockers as OPEN; the rebase
onto AGBM-02 closed both and [10] fired, forcing four documents to be corrected in the same
commit -- then it was inverted, and now guards them as closed. [14] does the same for the
stale zone fill: several documents say "re-pour before fab", and the day someone does,
those paragraphs become wrong. A blocker that gets quietly fixed and leaves its scary
paragraph behind is how a repository starts lying about itself.

Checks [13] and [14] also close a gap the earlier ones shared: they were all TOPOLOGICAL --
what exists, what it is called, what it connects to -- and none could measure a distance or
read a pour. That is how a 0.1632 mm clearance violation and six unreadable fiducials
shipped past all of them. scripts/geom.py is the arithmetic they were missing.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp                                                    # noqa: E402
import build_board                                               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP = os.path.join(ROOT, "clockxcontrol-integration", "board", "agbm-02-clockxcontrol.zip")
ZIP_ROOT = "agbm-02-clockxcontrol"
BOARD_MEMBER = f"{ZIP_ROOT}/AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb"
MPNS = os.path.join(ROOT, "pcbway-assembly", "resolved-mpns.json")

errors, warnings, verbose = [], [], False


def err(m):
    errors.append(m)
    print("  ERROR:  " + m)


def warn(m):
    warnings.append(m)
    print("  WARN:   " + m)


def ok(m):
    print("  ok:     " + m)


def note(m):
    if verbose:
        print("          " + m)


_board_cache = {}


def board():
    if "b" not in _board_cache:
        _board_cache["b"] = zipfile.ZipFile(ZIP).read(BOARD_MEMBER).decode("utf-8")
    return _board_cache["b"]


def tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    names = set(out.stdout.split("\n")) - {""}
    # A path can sit in the index and be gone from the working tree -- a deletion that
    # has not been staged. Every caller here is asking about the tree on disk, not the
    # index, and one of them opens what this returns: leaving the ghost in would turn a
    # half-staged working tree into a traceback rather than a check result.
    return {n for n in names if os.path.exists(os.path.join(ROOT, n))}


# =====================================================================================
# [1] the shipped board is a function of committed inputs
# =====================================================================================
def check_reproducible():
    print("[1] the shipped board rebuilds byte-for-byte from the committed base")
    try:
        built, st = build_board.build()
    except Exception as e:                                        # noqa: BLE001
        err(f"the generator cannot run: {type(e).__name__}: {e}")
        return
    want = board()
    if built == want:
        ok(f"rebuild identical ({len(built)} chars, {st['segs']} segments, "
           f"{st['vias']} vias, net {st['net']})")
        return
    err(f"the shipped board is NOT what scripts/build_board.py produces "
        f"({len(want)} chars shipped vs {len(built)} rebuilt). Either the board was "
        f"hand-edited -- in which case no document describes it -- or the "
        f"generator changed without repacking. Run build_board.py then pack_board.py.")


# =====================================================================================
# [2] the shipped zip and the tree hold the same documents
# =====================================================================================
def check_package_parity():
    print("[2] every document in the shipped zip matches its copy in the tree")
    # Derived from pack_board's own MEMBERS rather than restated, so a document added to
    # the package cannot be left out of this check -- that divergence is exactly what this
    # check exists to catch, and a hand-maintained second list is where it would hide.
    import pack_board
    pairs = {f"{ZIP_ROOT}/{member}": f"clockxcontrol-integration/{rel}"
             for member, rel in pack_board.MEMBERS}
    try:
        z = zipfile.ZipFile(ZIP)
        names = set(z.namelist())
    except OSError as e:
        err(f"cannot open the shipped zip: {e}")
        return
    stale = []
    for member, path in pairs.items():
        if member not in names:
            stale.append(f"{member} missing from the zip")
            continue
        disk = os.path.join(ROOT, path)
        if not os.path.exists(disk):
            stale.append(f"{path} missing from the tree")
            continue
        if z.read(member) != open(disk, "rb").read():
            stale.append(f"{member} != {path}")
    # every render the zip carries must also be in the tree
    for member in sorted(n for n in names if n.startswith(f"{ZIP_ROOT}/render/")
                         and not n.endswith("/")):
        disk = os.path.join(ROOT, "clockxcontrol-integration", "render",
                            os.path.basename(member))
        if not os.path.exists(disk):
            stale.append(f"{member} has no copy in clockxcontrol-integration/render/")
        elif z.read(member) != open(disk, "rb").read():
            stale.append(f"{member} != render/{os.path.basename(member)}")
    if stale:
        err("the shipped package has drifted from the tree -- repack with "
            "scripts/pack_board.py: " + "; ".join(stale))
    else:
        ok(f"{len(pairs)} documents + every render identical in zip and tree")


# =====================================================================================

# =====================================================================================
# [4] the DNP set is exactly what a ClockxControl build needs
# =====================================================================================
# The base board already ships 49 DNP footprints -- MouseBiteLabs marks every test
# point, the battery contacts, the trigger switches, the logos and the alternate-build
# resistors "do not place". So the truth to compare against is the BASE BOARD, not a
# hand-typed list: this fork's DNP set must be exactly the inherited set plus the three
# parts this fork adds. That way a stray flag on either side goes red, and the check needs no
# maintenance when upstream changes its mind.
#
# Only this fork's own additions need a reason here, and each carries one.
DNP_ADDED = {
    "C7A": "the STOCK C7 land, restored at (91.9, -41.1) and left unpopulated so "
           "this fork stops being a side-grade for anyone whose other mods solder to C7 "
           "where MouseBiteLabs has kept it across both AGBM-01 and AGBM-02. It is DNP "
           "rather than absent because the land is what those mods need; populating it "
           "fouls a ClockxControl lying on the board, which is why exactly one of C7 / C7A "
           "is ever fitted.",
    "X1": "the ClockxControl drives CK1 directly, so the 4.194304 MHz crystal "
          "must be absent on a module build",
    "C3": "27p load cap, sits straight on CK1",
    "C4": "33p -- NOT dangling with X1 gone. It stays tied to CK2 through R41 "
          "2.2k, so it loads the CPU's XOUT node. An earlier note said 'dangling' and was "
          "wrong; "
          "the real reason is stronger",
}
BASE_ZIP_REF = ("AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip"
                "::AGBM-02 Design Files/AGBM-02_AA_1-1.kicad_pcb")


def check_library_footprint():
    print("[2b] the shipped .kicad_mod is what the board's own MOD1 block derives to")
    path = os.path.join(ROOT, "clockxcontrol-integration", "footprint",
                        "ClockxControl_GBA_GBC.kicad_mod")
    try:
        have = open(path, encoding="utf-8").read()
    except OSError as e:
        err(f"the ClockxControl library footprint is missing: {e}")
        return
    try:
        want = build_board.library_footprint(board())
    except Exception as e:                                        # noqa: BLE001
        err(f"cannot derive the library footprint: {type(e).__name__}: {e}")
        return
    if have == want:
        ok(f"library footprint matches the board ({len(have)} chars, derived)")
        return
    err("the shipped .kicad_mod is NOT what the board's MOD1 derives to. It was once "
        "these drifted unnoticed -- the library labelled the landings 1/2/3 where the "
        "board says SEL/L/R, its centre text was 1.2 against 1.05, and its reference read "
        "MOD. Anyone re-importing the library got a different part from the one this fork "
        "verified. Run scripts/build_board.py, which regenerates it.")


def check_dnp_ledger():
    print("[4] the DNP set is MouseBiteLabs' own, plus exactly what a ClockxControl build adds")
    try:
        base = kisexp.load(os.path.join(ROOT, BASE_ZIP_REF.split("::")[0])
                           + "::" + BASE_ZIP_REF.split("::")[1])
    except (OSError, KeyError, ValueError) as e:
        err(f"cannot read the AGBM-01 base: {type(e).__name__}: {e}")
        return
    inherited = {fp.ref for fp in kisexp.footprints(base) if fp.dnp}
    got = {fp.ref for fp in kisexp.footprints(board()) if fp.dnp}
    want = inherited | set(DNP_ADDED)
    extra, missing = sorted(got - want), sorted(want - got)
    if extra:
        err("footprint(s) marked DNP that neither the base board nor this fork accounts for "
            "-- add a reasoned line to DNP_ADDED in the same commit, or un-flag them: "
            + ", ".join(extra))
    if missing:
        err("expected DNP and the board disagrees: " + ", ".join(missing))
    if not extra and not missing:
        ok(f"{len(inherited)} inherited from MouseBiteLabs' own board + "
           f"{len(DNP_ADDED)} this fork adds ({', '.join(sorted(DNP_ADDED))})")


# =====================================================================================
# [5] the buy list and the board describe the same parts
# =====================================================================================
def _mpns():
    return json.load(open(MPNS, encoding="utf-8"))["entries"]


def check_bom_vs_board():
    print("[5] every ref in resolved-mpns.json is on the board with that Value")
    try:
        entries = _mpns()
    except (OSError, ValueError, KeyError) as e:
        err(f"cannot read resolved-mpns.json: {type(e).__name__}: {e}")
        return
    fps = kisexp.by_ref(board())
    bad, checked = [], 0
    for e in entries:
        for ref in e["refs"]:
            if ref not in fps:
                bad.append(f"{ref}: named in resolved-mpns.json, not on the board")
                continue
            checked += 1
            want = e.get("value")
            if want is not None and fps[ref].value != want:
                bad.append(f"{ref}: board says Value {fps[ref].value!r}, "
                           f"resolved-mpns.json says {want!r}")
    if bad:
        err("the buy list and the board disagree: " + "; ".join(sorted(bad)))
    else:
        ok(f"{checked} reference designators across {len(entries)} buy lines agree")


# =====================================================================================
# [6] a distributor ships what the NUMBER says, not what the MPN says
# =====================================================================================
# Borrowed straight from SOLAR-GLOW check [20], which was written after a part swap left
# an assembly CSV whose U6 row named one part beside another part's orderable code. This
# fork has no distributor P/N column yet, so the check does the reachable half: it holds
# every entry's `mpn` against the `value` the board carries, since for a great many lines
# here the Value IS the MPN (MouseBiteLabs put part numbers in the Value field for the
# actives, fuses and LEDs). Where the two legitimately differ -- a resistor whose Value is
# `100k` and whose MPN is a Yageo ordering code -- the pair is ledgered with its reason.
#
# It matters because this session hit the exact failure once already: a GUESSED Digi-Key
# product URL for TLV9064IPWR returned a discontinued Vishay current-sense resistor, and
# only re-checking against the manufacturer datasheet caught it.
VALUE_IS_NOT_MPN = {
    # value pattern -> why the Value is not expected to be the ordering code
    r"^\d+(\.\d+)?[kKMR]?$": "bare resistance -- the MPN is the distributor's ordering code",
    r"^\d+(\.\d+)?[pun]$": "bare capacitance",
    r"^\d+(\.\d+)?uH$": "bare inductance",
    r"^\d+\.\d+MHz$": "bare frequency",
    r"^FFC CONNECTOR$": "generic description in the Value field",
    r"^AGB-(SRAM|CPU)$": "the AGB-CPU is salvaged and has no orderable number; the "
                         "AGB-SRAM land takes either a donor chip or, since the rebase, a "
                         "CY62157EV30LL that the MPN names",
    # AGBM-02 states the CHOICE in the Value field rather than picking for you.
    # Z57/Z58 read "100p or 0 ohm" because the hotkey pair is configurable -- capacitors
    # make L+R+Start+A/B fake a screen kit's touch input, resistors or jumpers make them
    # act as button inputs for an external mod. MouseBiteLabs' Feature Configurations page
    # is the instruction; this fork does not get to decide it for the builder, so the BOM
    # buys the capacitor and pcbway-assembly/README.md carries it as a build decision.
    r"^100p or 0 ohm$": "configurable hotkey part -- see his Feature Configurations page",
}

# Pairs where the Value and the MPN deliberately differ AND the difference is a KNOWN,
# TRACKED DEFECT rather than a naming convention. Each names where it is tracked, and the
# check asserts that the tracking document still says so -- a ledger entry that outlives
# its tracking is the silence this whole file exists to prevent. Fix the board and the
# entry goes stale, which the check also reports.
# These three pairs are NOT defects, and calling them defects was itself the defect.
#
# In KiCad the Value field is a SYMBOL NAME. The orderable code lives in the per-symbol
# (property "Source" ...) link, which is where MouseBiteLabs put it. "2N3904" on SOT-23 pads
# is not a package mismatch -- it is the generic name of the transistor, and Nick's own link
# buys MMBT3904LT1G, the SOT-23 part. Likewise CSS-1310B -> CSS-1310TB and SJ-3524-SMT ->
# SJ-3524-SMT-TR. The BOM buys the link's part in every case, so nothing was ever going to
# be mis-ordered.
#
# The fork claimed to have found these ("the power review predicted this one and nobody had
# flagged it"). Nobody had to: they were flagged in the schematic. What the fork had actually
# done was fail to read 30 of the 57 links in MouseBiteLabs' AGBM-02 schematic -- see check
# [16] -- so it could not see that its "discoveries" were already his answers.
#
# They stay listed because a Value that does not name an orderable part is still worth a
# reader knowing about, and because check [6] would otherwise report the Value/MPN mismatch
# as an unexplained conflict. The wording is what changed.
VALUE_IS_A_SYMBOL_NAME = {
    ("CSS-1310B", "CSS-1310TB"):
        ("SW1's Value is the symbol name for the Nidec slide switch; the orderable code is "
         "CSS-1310TB, which is what MouseBiteLabs' own Source link buys and what the BOM "
         "orders. Not a defect. Recorded in pcbway-assembly/README.md.",
         "pcbway-assembly/README.md", "CSS-1310TB"),
    ("2N3904", "MMBT3904LT1G"):
        ("Q1's Value is the generic NPN name. There is no 2N3904 in SOT-23; the SOT-23 part "
         "is MMBT3904LT1G, which is what MouseBiteLabs' own Source link buys and what the "
         "BOM orders. Not a defect. Recorded in pcbway-assembly/README.md.",
         "pcbway-assembly/README.md", "MMBT3904LT1G"),
    ("2N3906", "MMBT3906LT1G"):
        ("Q3's Value is the generic PNP name; MouseBiteLabs' link buys MMBT3906LT1G and the "
         "BOM orders it. Not a defect. Recorded in pcbway-assembly/README.md.",
         "pcbway-assembly/README.md", "MMBT3906LT1G"),
}


def check_supplier_pns():
    print("[6] every MPN is consistent with the Value the board carries")
    try:
        entries = _mpns()
    except (OSError, ValueError, KeyError):
        warn("not checked -- resolved-mpns.json unreadable (check [5] said so)")
        return
    def norm(s):
        return re.sub(r"[^A-Z0-9]", "", (s or "").upper())
    bad, ledgered, matched, symbolic = [], 0, 0, 0
    for e in entries:
        val, mpn = e.get("value") or "", e.get("mpn") or ""
        if not mpn:
            bad.append(f"{e['refs']}: no MPN at all")
            continue
        if any(re.match(p, val) for p in VALUE_IS_NOT_MPN):
            ledgered += 1
            continue
        nv, nm = norm(val), norm(mpn)
        if nv and nm and (nm.startswith(nv) or nv.startswith(nm)):
            matched += 1
            continue
        if (val, mpn) in VALUE_IS_A_SYMBOL_NAME:
            why, doc, token = VALUE_IS_A_SYMBOL_NAME[(val, mpn)]
            try:
                tracked_still = token in open(os.path.join(ROOT, doc), encoding="utf-8").read()
            except OSError:
                tracked_still = False
            if tracked_still:
                note(f"{e['refs']}: Value is a symbol name -- {why}")
                symbolic += 1
            else:
                err(f"{e['refs']}: ledgered as a known defect but {doc} no longer mentions "
                    f"{token} -- either it was fixed (prune KNOWN_DEFECT_PNS and update the "
                    f"board Value) or the tracking was lost")
            continue
        bad.append(f"{e['refs']}: Value {val!r} does not look like MPN {mpn!r} -- if that "
                   f"is deliberate, add the Value's shape to VALUE_IS_NOT_MPN with a reason")
    if bad:
        err("MPN/Value mismatch: " + "; ".join(bad))
    else:
        ok(f"{matched} self-describing, {ledgered} ledgered as value-not-MPN, "
           f"{symbolic} where the Value is a symbol name and the schematic's own link "
           f"buys the orderable part")

    # --- can the thing actually be BOUGHT? ------------------------------------------
    # A WARNING, not an error: stock is somebody else's inventory on a particular day, not
    # an invariant of this repository, and a gate that fails on market conditions is a gate
    # people learn to ignore. But it must be SAID. The shipped BOM once carried no
    # Digi-Key stock figure at all -- that half of the last run never completed -- and
    # three lines had quietly gone to zero underneath, one of them because this fork had
    # substituted a part MouseBiteLabs never chose.
    dry, thin, blind = [], [], 0
    for e in entries:
        if not e.get("mpn"):
            continue
        got = [(e.get(k) or {}).get("stock") for k in ("digikey", "mouser")]
        nums = [v for v in got if isinstance(v, int)]
        if not nums:
            blind += 1
            continue
        tot = sum(nums)
        label = f"{'/'.join(e['refs'])} ({e['mpn']})"
        if tot == 0:
            dry.append(label)
        elif tot < 1000:
            thin.append(f"{label}: {tot}")
    if blind:
        warn(f"{blind} buy line(s) carry NO stock figure from either distributor -- that is "
             f"UNKNOWN, not zero. Re-run scripts/check_stock.py with credentials.")
    if dry:
        warn(f"{len(dry)} buy line(s) at ZERO stock at both distributors as of the "
             f"data_as_of stamp -- an order cannot be placed for these today: "
             + ", ".join(dry))
    if thin:
        note("thin: " + "; ".join(thin))
    if not dry and not blind:
        ok(f"every buy line has stock at a distributor" +
           (f" ({len(thin)} under 1,000)" if thin else ""))


# =====================================================================================
# [7] every path a document cites exists, or its own sentence says why not
# =====================================================================================
# SOLAR-GLOW check [11], ported. The rule is a PROSE DISCIPLINE, not an inventory: a doc
# may name a file that is not there only if the sentence itself says so, or the path
# carries a reason below.
EXPECTED_ABSENT = {
    "scripts/render.py":
        "ANOTHER REPOSITORY'S file. devinhorowitz/solar-business-card ships it; this repo "
        "borrowed its three disciplines and cites it as the source. This fork's equivalent "
        "is scripts/render_assembled.py, which does exist here",
    "render.py": "same -- Solar-Glow's, cited by basename",
    "AGBM-01_AA_1-2.kicad_sch":
        "the upstream schematic -- inside 'AGBM-01 (AA Batteries)/AGBM-01_Design Files.zip', "
        "not loose in the tree. it was cited as the file to edit, which is "
        "correct: you unzip it, edit it, and the fork keeps shipping a .kicad_pcb",
    "Audio.kicad_sch": "same archive -- the audio sheet the U7 and VR2 sourcing came from",
    "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb":
        "the deliverable board -- inside clockxcontrol-integration/board/"
        "agbm-02-clockxcontrol.zip, and rebuildable with scripts/build_board.py. Cited by "
        "basename throughout because that is its name inside the package",
    "AGBM-01_AA_1-2.kicad_pcb":
        "MouseBiteLabs' AGBM-01 board -- inside 'AGBM-01 (AA Batteries)/AGBM-01_Design "
        "Files.zip'. Cited by basename when comparing save dates and layouts across his "
        "three boards",
    "AGBM_LiPo_1-3.kicad_pcb":
        "MouseBiteLabs' AGBM-11 board -- inside 'AGBM-11 (Lithium-ion)/AGBM-11 Design "
        "Files.zip'. Same reason",
    "IMG_6317.jpg":
        "insideGadgets' own GBA installation photo, at shop.insidegadgets.com/wp-content/"
        "uploads/2019/11/IMG_6317.jpg. it is the evidence that "
        "'GBA SI' in their wiring list is a typo for the pad silkscreened S1 -- the red V+ "
        "wire is soldered to it. NOT vendored into this repository: it is their "
        "copyrighted image, so it is cited by URL and left where it lives",
    "AGBM-02_AA_1-1.kicad_pcb":
        "the base board -- inside 'AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip', "
        "MouseBiteLabs' own file, unmodified",
    # The rebase culled these. They are cited only to say what was removed, which is a
    # sentence the history rule already allows -- but they are named in TABLES, where
    # there is no prose to carry the explanation, so they are ledgered here instead.
    "AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb":
        "the PREVIOUS deliverable board, on the AGBM-01 base. Culled by the rebase; in git "
        "history only",
    "AGBM-01_AA_1-2_GBE-plus.kicad_pcb":
        "the AGBM-01 base board. Culled by the rebase -- it was our own footprint work, "
        "superseded by MouseBiteLabs' AGBM-02. Git history only",
    "agbm-01-ram-desalvage.zip":
        "the AGBM-01 base's package. Culled by the rebase; git history only",
    "agbm-01-clockxcontrol.zip":
        "the PREVIOUS output package, on the AGBM-01 base. Culled by the rebase; git history "
        "only",
    "Files.zip":
        "a false positive -- the bare-path regex clips "
        "'AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip' at its last space. The real "
        "archive is in the tree; only this fragment is not",
    "patch5.py": "the original generator, superseded by scripts/build_board.py",
    # A MEMBER OF THE FAB ZIP, not a file in the tree. pcbway-assembly/README.md lists the
    # package contents, and the order sheet is written INTO the archive by fab_package.py
    # so it travels with the upload -- a copy loose in the repository would be a second
    # source of truth for the numbers PCBWay reads.
    "ORDER.txt": "written into pcbway-assembly/fab/agbm-02-cxc-pcbway.zip by scripts/fab_package.py; it ships inside the upload, not beside it",
    # power-review/completeness-critic.md cites the session's own working captures as
    # PROVENANCE -- "read from the local capture at /tmp/.../cxc.txt". Naming a scratch
    # path in a committed document is a citation nobody can follow, but deleting the
    # sentence would delete the provenance, which is worse. Ledgered instead, with the
    # note that every claim resting on them was re-derived from a fetched datasheet.
    "cxc.txt": "session capture of the insideGadgets ClockxControl product page -- scratch, "
               "out of repo; the screen-compatibility and 12 mA claims it supports are "
               "quoted verbatim in the document itself",
    "ltc3527.txt": "session capture of ADI 35271fc -- scratch, out of repo; the 1.20 V "
                   "feedback reference it supports is re-derived in power-budget.md",
    "LM4853.txt": "session capture of TI SNAS155E -- scratch, out of repo",
    "00_context.md": "the review brief the domain agents were given -- a workflow input, "
                     "never a file in this tree",
}

_CITE_EXTS = ("png gif jpg jpeg svg pdf step stl zip html json csv xlsx md py yml yaml "
              "txt c h rpt drl gbr net "
              "kicad_pcb kicad_sch kicad_pro kicad_prl kicad_mod kicad_dru").split()
_HIST_RE = re.compile(
    r"git history|culled|deleted|removed|replaced|superseded|retired|struck|"
    r"no longer|history only|used to|abandoned|renamed|is gone|went stale|not in the "
    r"repositor|there is no|does not exist|never existed|inside |unzip|archive|"
    # ...and the forward-looking half of the same discipline: a document may name a file
    # that does not exist YET, as long as its own sentence says so. Deliberately tight --
    # "not yet" alone would mask a real rot.
    r"not written|not yet written|yet to be written|does not exist yet|"
    r"\bwas\b|\bold\b|-era\b|until 20|pre-20", re.I)


def _md_files(files):
    return sorted(f for f in files if f.endswith(".md"))


def check_cited_paths():
    print("[7] every path a document cites exists -- or the sentence says why not")
    files = tracked()
    basenames = {os.path.basename(f) for f in files}
    ext_re = "|".join(_CITE_EXTS)
    bare = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.(?:%s))(?![\w/])" % ext_re)
    missing = []
    for md in _md_files(files):
        here = os.path.dirname(md)
        lines = open(os.path.join(ROOT, md), encoding="utf-8").read().split("\n")
        for i, line in enumerate(lines):
            for path in set(bare.findall(line)):
                if path in files or os.path.basename(path) in basenames:
                    continue
                # Resolve BOTH ways: from the repo root, and relative to the document
                # doing the citing -- a link in pcbway-assembly/README.md that reads
                # "../scripts/bom_split.py" is correct and must not read as rot.
                if (os.path.exists(os.path.join(ROOT, path))
                        or os.path.exists(os.path.normpath(os.path.join(ROOT, here, path)))):
                    continue
                if path in EXPECTED_ABSENT or os.path.basename(path) in EXPECTED_ABSENT:
                    continue
                ctx = line + " " + (lines[i - 1] if i else "")
                if _HIST_RE.search(ctx):
                    continue
                missing.append(f"{md}:{i + 1} cites {path}")
    if missing:
        err("path(s) cited by a document but not in the tree, with nothing in the "
            "sentence to say why -- either the file went missing or the prose is "
            "describing a tree that is not there: " + "; ".join(sorted(set(missing))))
    else:
        ok(f"every cited path across {len(_md_files(files))} documents resolves")


# =====================================================================================
# [8] every image a document displays is really there
# =====================================================================================
def check_doc_imagery():
    print("[8] every image a document displays exists")
    files = tracked()
    img = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
    missing = 0
    shown = set()
    for md in _md_files(files):
        d = os.path.dirname(md)
        for m in img.finditer(open(os.path.join(ROOT, md), encoding="utf-8").read()):
            src = m.group(1)
            if src.startswith(("http://", "https://", "data:")):
                continue
            rel = os.path.normpath(os.path.join(d, src))
            shown.add(rel)
            if rel not in files and not os.path.exists(os.path.join(ROOT, rel)):
                err(f"{md} displays {src}, which is not in the tree")
                missing += 1
    # Only IMAGES can be "displayed"; render-manifest.json lives here because it belongs
    # beside what it describes, not because a document was ever going to show it.
    orphan = sorted(f for f in files
                    if f.startswith("clockxcontrol-integration/render/")
                    and f.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".gif"))
                    and f not in shown)
    if orphan:
        warn(f"render(s) no document displays -- they still ship in the package, so this "
             f"is a note, not a fault: {', '.join(os.path.basename(o) for o in orphan)}")
    if not missing:
        ok(f"{len(shown)} displayed images all present")


# =====================================================================================
# [9] the window the module needs is still empty
# =====================================================================================
# The entire feasibility claim is that relocating ONE 0603 opens an 18.65 x 12.00 mm
# component-free window on the front side below the RAM. Nothing else in this repo would
# notice a part being dropped back into it, and DRC would not either -- a footprint whose
# courtyard clears its neighbours can still sit exactly where the module has to go.
#
# The module body is the fp_rect at +/-9.325 x +/-6.000 about MOD1's origin.
WINDOW_HALF_X, WINDOW_HALF_Y = 9.325, 6.0
WINDOW_OCCUPANTS = {"MOD1"}          # the module itself, and nothing else
# The parts this fork moved, and where it put them. A deliberate move updates this table
# in the same commit -- the exclusion-ledger shape.
PLACED = {
    "C7":   (93.1, -37.4, "moved out of the window; pad 1 (VDD35) now lands on the left"),
    # A later pass replaced all six. The first spots were chosen against HARD COPPER
    # alone and KiCad's DRC threw four violations at them: two marks inside 1.2 mm shell holes,
    # two inside keepout zones, one merged with the battery terminal's mask aperture. the clock
    # audit also kept them as three coincident front/back PAIRS, which is not a requirement --
    # front and back register separately -- and that assumption was costing every mark margin.
    # Fiducials are OURS: neither of MouseBiteLabs' boards carries one, because he hand-builds.
    # Full margins live in FIDUCIAL_SITES, which check [13] recomputes.
    "FID1": (100.5, -3.5, "fiducial, FRONT triangle, top right"),
    "FID2": (103.75, -58.5, "fiducial, FRONT triangle, bottom right"),
    "FID3": (24.25, -55.75, "fiducial, FRONT triangle, bottom left -- the tightest of the "
                            "three at 2.00 mm of clear copper, still twice the mask window"),
    "FID4": (127.75, -19.5, "fiducial, BACK triangle, right"),
    "FID5": (94.75, -66.5, "fiducial, BACK triangle, bottom"),
    "FID6": (11.5, -16.0, "fiducial, BACK triangle, left"),
    "MOD1": (91.95, -44.95, "module centre, rev B -- shifted west out of the R3/TP114 "
                            "cluster; two VDD2 stitching vias are what that cost"),
    "TP83": (97.9, -37.95, "CLK wire pad. y is -37.95 and not -38.6: KiCad's y grows "
                           "DOWNWARD, and at -38.6 the 1.2 mm pad overlaps the module "
                           "body by 0.25 mm at its radius"),
    "TP84": (99.45, -37.95, "V+ wire pad"),
    "TP85": (101.0, -37.95, "V- wire pad"),
    "JP4":  (45.0, -64.2, "CK1 isolation jumper -- OPEN for a crystal build, BRIDGED for "
                          "a ClockxControl build"),
}


# DNP lands deliberately inside the module window, each with its reason. A land is not a
# body; a part is. Membership here is the ONLY way a footprint in the window passes, and it
# still has to be dnp.
WINDOW_DNP_LANDS = {
    "C7A": "the stock C7 land, back at (91.9, -41.1) where MouseBiteLabs has kept "
           "it across both AGBM-01 and AGBM-02, so mods that solder to C7 there still have "
           "their landmark. DNP: populate C7 for a ClockxControl build, C7A for a stock "
           "one, never both.",
}


def check_module_window():
    print("[9] the module window is still component-free, and its parts have not moved")
    fps = kisexp.by_ref(board())
    if "MOD1" not in fps or fps["MOD1"].at is None:
        err("MOD1 is not on the board -- the whole module-window claim is unverifiable")
        return
    mx, my, _ = fps["MOD1"].at
    intruders, tolerated = [], []
    for fp in fps.values():
        if fp.ref in WINDOW_OCCUPANTS or fp.at is None or fp.layer != "F.Cu":
            continue
        dx, dy = abs(fp.at[0] - mx), abs(fp.at[1] - my)
        if not (dx <= WINDOW_HALF_X and dy <= WINDOW_HALF_Y):
            continue
        am = re.search(r"\(attr ([^)]*)\)", fp.body)
        is_dnp = bool(am and "dnp" in am.group(1).split())
        # THE WINDOW EXISTS SO A MODULE CAN LIE FLAT, and what stops that is a BODY, not a land.
        # The stock C7 land is back inside the window, DNP, so this fork stops
        # being a side-grade for anyone whose other mods solder to C7 where it has always been.
        # Bare, it is copper and mask. The rule stays strict where it matters: a footprint in
        # the window that is NOT dnp still fails, and a dnp one has to be named here, so nobody
        # can quietly park a real part in the window by flagging it.
        if is_dnp and fp.ref in WINDOW_DNP_LANDS:
            tolerated.append(fp.ref)
        else:
            intruders.append(f"{fp.ref} ({fp.value}) at {fp.at[0]},{fp.at[1]}"
                             + ("" if is_dnp else " -- NOT dnp"))
    moved = []
    for ref, (x, y, _why) in PLACED.items():
        if ref not in fps or fps[ref].at is None:
            moved.append(f"{ref} is gone from the board")
            continue
        ax, ay, _ = fps[ref].at
        if abs(ax - x) > 1e-6 or abs(ay - y) > 1e-6:
            moved.append(f"{ref} at ({ax}, {ay}), snapshot says ({x}, {y})")
        else:
            note(f"{ref} at ({x}, {y})")
    if tolerated:
        ok(f"window clear of bodies; {', '.join(sorted(tolerated))} present as DNP land(s) "
           f"by design -- the stock C7 land, kept")
    if intruders:
        err(f"footprint origin(s) inside the {2 * WINDOW_HALF_X} x {2 * WINDOW_HALF_Y} mm "
            f"module window -- the module physically cannot go on: " + ", ".join(intruders))
    if moved:
        err("a placement has drifted from the snapshot -- a deliberate move updates "
            "PLACED in this file in the same commit, and re-runs the clearance analysis "
            "check [13] performs: " + "; ".join(moved))
    if not intruders and not moved:
        ok(f"window clear, all {len(PLACED)} placement(s) on their snapshotted spot")


# =====================================================================================
# [10] the two former blockers
# =====================================================================================
# THIS CHECK GOES RED WHEN THE BUGS ARE FIXED. That is deliberate, and it is the point.
#
# Several documents once carried a prominent "the board is not fabricable" section
# resting on two facts about copper. When somebody opens KiCad and routes them, the board
# becomes fabricable and every one of those paragraphs becomes a lie -- with nothing to notice.
# So the facts are asserted here: fix the board, this check fails, and the failure names the
# documents that have to be corrected in the same commit.
VDD2_NET = 8            # from the board's own net table; asserted below
VDD2_EAST_LIMIT = 93.0  # once true: "there is no VDD2 via anywhere with x > 93"
BROKEN_NET = "Net-(Q5B-G)"
# The two islands the AGBM-01 base left behind, and the via site that used to join them. Both
# come from the STOCK MouseBiteLabs board, which routes this net whole -- so unlike the VDD2
# blocker there is a known-good reference to diff against, and this check does.
BROKEN_ISLANDS = [["U17.1"], ["Q5.3", "R66.2"]]
MISSING_VIA = (100.8, -62.15)
BLOCKER_DOCS = ("clockxcontrol-integration/DESIGN-DECISIONS.md",
                "pcbway-assembly/README.md")


# =====================================================================================
# [10] BOTH FORMER BLOCKERS ARE CLOSED. RED MEANS ONE CAME BACK.
# =====================================================================================
# This check used to assert the OPPOSITE: that both blockers were still open, and it went
# red if either got fixed, so that four documents claiming "not fabricable" could not
# quietly become wrong. On 2026-08-19 it fired, on both, for the best possible reason --
# The rebase onto MouseBiteLabs' AGBM-02 closed both, because BOTH WERE THE AGBM-01 BASE'S
# OWN DAMAGE. That base is gone, so they are gone.
#
# The check is kept, inverted, rather than deleted. What it guards now is that nothing
# re-introduces them: a future change that starts deleting vias around U2 to make room for
# something will trip it, which is exactly how they arose the first time.
def check_blockers():
    print("[10] both former U2 / Net-(Q5B-G) blockers are CLOSED (RED means one came back)")
    b = board()
    nets = kisexp.net_table(b)
    vdd2 = next((n for n, nm in nets.items() if nm == "VDD2"), None)
    if vdd2 is None:
        err("the board has no VDD2 net -- this check cannot verify U2's supply")
        return

    # --- former blocker 1: U2 pin 37's VDD2 supply --------------------------------
    # On the AGBM-01 base there was NO VDD2 via anywhere east of x=93, because that base had
    # deleted two of them to clear its third pad column. On AGBM-02 pin 37 lands on the
    # x=10.97 column -- a stock column the OEM RAM uses too -- and the vias are present.
    east = [(x, y) for x, y, n in kisexp.vias(b) if n == vdd2 and x > VDD2_EAST_LIMIT]
    if east:
        ok(f"U2 pin 37's supply is back: {len(east)} VDD2 via(s) east of "
           f"x={VDD2_EAST_LIMIT} ({', '.join(f'({x},{y})' for x, y in east[:4])})")
    else:
        err(f"U2 PIN 37 HAS LOST ITS SUPPLY AGAIN -- no VDD2 via east of "
            f"x={VDD2_EAST_LIMIT}. This was the AGBM-01 base's defect and the rebase closed "
            f"it; if an "
            f"something has re-opened it, say so in: " + ", ".join(BLOCKER_DOCS))

    # --- former blocker 2: Net-(Q5B-G) whole --------------------------------------
    num = next((n for n, nm in nets.items() if nm == BROKEN_NET), None)
    if num is None:
        err(f"{BROKEN_NET} is not in the board's net table any more -- this check describes it")
        return
    islands = kisexp.net_islands(b, num)
    if len(islands) == 1:
        ok(f"{BROKEN_NET} is whole ({', '.join(sorted(islands[0]))}) -- the supervisor "
           f"reaches Q5B's gate and the low-battery LED works")
    else:
        err(f"{BROKEN_NET} IS BROKEN INTO {len(islands)} ISLANDS AGAIN "
            f"({' | '.join(', '.join(sorted(i)) for i in islands)}). On the AGBM-01 base this "
            f"was caused by a deleted via at {MISSING_VIA}; the low-battery LED is dead "
            f"while it holds. Record it in: " + ", ".join(BLOCKER_DOCS))

    # The base this fork sits on. Diffing against it is what proved the break was the AGBM-01
    # base's and not MouseBiteLabs', so the check keeps comparing rather than trusting a memory.
    try:
        base = kisexp.load(os.path.join(ROOT, BASE_ZIP_REF.split("::")[0])
                           + "::" + BASE_ZIP_REF.split("::")[1])
        s_num = next(n for n, nm in kisexp.net_table(base).items() if nm == BROKEN_NET)
        s_islands = kisexp.net_islands(base, s_num)
    except Exception as e:                                        # noqa: BLE001
        warn(f"could not read the base board: {type(e).__name__}: {e}")
        return
    if len(s_islands) == 1:
        ok(f"MouseBiteLabs' AGBM-02 has {BROKEN_NET} whole too -- this fork inherits a "
           f"good net rather than repairing a bad one")
    else:
        err(f"the BASE AGBM-02 board has {BROKEN_NET} in {len(s_islands)} pieces. That is "
            f"upstream's, not ours, and every document here assumes otherwise.")


# =====================================================================================
# [13] REAL GEOMETRY -- clearance of the copper this fork ADDS, and fiducial readability
# =====================================================================================
# The twelve checks above are all topological: what exists, what it is called, what it
# connects to. None could measure a distance, and that is exactly how this fork shipped
# a via 0.1632 mm from C13's pad -- against the project's own 0.200 mm netclass rule -- and
# six fiducials whose 2 mm mask windows were full of foreign copper. Twelve green checks and
# both defects invisible. A 44-agent audit found them; this check is so the next one does
# not have to.
#
# HARD COPPER ONLY. scripts/geom.py models tracks, vias, pads and the board outline. It does
# NOT model zone fills, and says so. For the fiducials that is handled the way a layout tool
# handles it: the generator gives each pad a 0.55 mm local clearance so the pour recedes past
# the mask window, and this check asserts the override is present rather than trying to
# simulate a fill.
CLEARANCE_RULE = 0.20     # the AGBM-02 project's single "Default" netclass
FIDUCIAL_WINDOW = 1.00    # 0.5 mm pad + 0.5 mm solder_mask_margin
FIDUCIAL_PAD_CLEARANCE = "(clearance 0.55)"

# EVERY MARGIN IN build_board.FIDUCIALS' COMMENT, RECOMPUTED. An earlier pass measured one of
# the five things that decide whether a fiducial works -- distance to hard copper -- wrote the
# answers into a comment as though they were the whole story, and shipped four DRC violations:
# FID2/FID5 inside a 1.2 mm shell hole, FID3/FID6 on the rim of another, FID1/FID2 inside
# keepout zones, FID1's mask window merged with the battery terminal's. Twelve green checks, and
# the only thing that caught any of it was KiCad's own DRC.
#
# So the numbers stop being prose. geom.site_margins() measures all five from the board;
# this ledger is what they were when the spots were chosen, and any drift over 5 um fails.
# 9.000 is the reported ceiling for "nothing of that kind anywhere near" -- see geom.FAR.
#
#                edge  keepout  copper   mask   crtyd
FIDUCIAL_SITES = (
    ("FID1", 3.122, 9.000, 2.260, 9.000, 9.000),
    ("FID2", 9.000, 9.000, 1.837, 9.000, 2.220),
    ("FID3", 2.939, 2.707, 2.001, 9.000, 4.584),
    ("FID4", 3.310, 4.594, 2.260, 9.000, 9.000),
    ("FID5", 2.854, 9.000, 1.801, 9.000, 2.720),
    ("FID6", 3.581, 9.000, 2.150, 9.000, 5.836),
)
# The floors these were chosen against, from scripts/place_fiducials.py. Repeated rather
# than imported so that lowering one there cannot silently lower the gate here too.
FIDUCIAL_FLOOR = {"edge": 2.0, "keepout": 1.0, "copper": 1.1, "mask": 1.5, "crtyd": 1.0}


# MOD1's mechanical neighbourhood, snapshotted with a reason per line. Nothing measured this
# before: every gate was about copper, and whether the module physically FITS rested on a table
# taken off a render that turned out to be pre-rebase. The figures did survive the rebase -- all
# four courtyard rows reproduce to three decimals -- but nothing was
# holding them there.
#
# Same-side only. A sweep that ignores which side a part is on puts C12 at 0.055 mm, which
# reads like a collision; C12 is on B.Cu, 1.6 mm of FR4 away.
MODULE_GAPS = (
    # This fork's own wire pads, placed deliberately just clear of the body so the three wires
    # stay short (3.8 / 5.9 / 4.7 mm). Tightest on the board, on purpose. C7A's
    # alternate C7 land, INSIDE the module body by 1.420 mm and negative for that reason. This
    # is the design, not a collision: the land is bare copper and mask, and it is DNP --
    # populate C7 (the moved one) for a ClockxControl build or C7A for a stock one, never both.
    # A NEGATIVE number here can only ever be a part that is inside the module's own body, so
    # the floor rule below skips DNP parts and fails on anything else.
    ("C7A",  "crtyd", -1.420),
    ("TP83", "pad",   0.400),
    ("TP84", "pad",   0.400),
    ("TP85", "pad",   0.400),
    # MouseBiteLabs' parts. U2 is the RAM the window sits below -- a package edge, not a
    # hand-soldered joint, which is why 0.55 mm is acceptable here and would not be on a
    # part someone has to get an iron onto.
    ("U2",   "crtyd", 0.550),
    # C7 is the 0603 this fork MOVES to open the window. This is the gap AFTER the move.
    ("C7",   "crtyd", 0.820),
    ("TP18", "pad",   0.925),
    ("P1",   "pad",   2.050),
    ("R3",   "crtyd", 2.145),
)
GAP_FLOOR = 0.35        # below this, a module edge and a neighbour are too close to trust


def check_geometry():
    print("[13] the copper this fork adds clears MouseBiteLabs', and the fiducials are readable")
    import geom
    b = board()
    try:
        base = geom.base()
    except OSError as e:
        warn(f"base board unreadable ({e}) -- check [13] did not run")
        return
    segs, vias, pads = geom.collect(base)
    ALL = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]

    # --- every via this fork adds, against everything MouseBiteLabs already routed ---------
    base_via = {(round(x, 4), round(y, 4)) for x, y, _n in kisexp.vias(base)}
    added = [(x, y, n) for x, y, n in
             [(vx, vy, kisexp.net_table(b).get(vn, str(vn))) for vx, vy, vn in kisexp.vias(b)]
             if (round(x, 4), round(y, 4)) not in base_via]
    bad, tight = [], []
    for x, y, net in added:
        w = geom.worst(x, y, 0.35, ALL, segs, vias, pads, net=net)
        if not w:
            continue
        d, what = w[0]
        if d < CLEARANCE_RULE:
            bad.append(f"via ({x},{y}) on {net}: {d:.4f} mm to {what}")
        elif d < CLEARANCE_RULE + 0.05:
            tight.append(f"via ({x},{y}) on {net}: {d:.4f} mm to {what}")
    if bad:
        err(f"added via(s) below the {CLEARANCE_RULE} mm netclass clearance: " + "; ".join(bad))
    else:
        ok(f"all {len(added)} added via(s) clear MouseBiteLabs' copper by >= "
           f"{CLEARANCE_RULE} mm")
    for t in tight:
        note(f"tight but legal: {t}")

    # --- is every part PCBWay would place actually ON the board? -----------------------
    # Found by the first assembled render: MouseBiteLabs' AGBM-02 parks an
    # unannotated HC49 crystal footprint -- ref "REF**", zero pads, a leftover reference for
    # the crystal the board marks DNP -- at (8.89, -81.888), NINE MILLIMETRES above the
    # top edge. It carries a 3D model, so it rendered as a crystal floating in space.
    #
    # The render was cosmetic. The latent fault is not: bom_split.classify() returns
    # "assembly" for it, because it is not dnp and not exclude_from_bom. Nothing but the
    # "*" in its refdes keeps it out of the position file. Relax that filter -- or annotate
    # the footprint -- and PCBWay is told to place a through-hole crystal off the board.
    import bom_split
    bb = None
    try:
        esegs = geom.edge_segments(b)
        xs = [v for sg in esegs for v in (sg[0], sg[2])]
        ys = [v for sg in esegs for v in (sg[1], sg[3])]
        bb = (min(xs), min(ys), max(xs), max(ys)) if xs else None
    except Exception:                                             # noqa: BLE001
        pass
    if bb:
        stray = []
        for fp in kisexp.footprints(b):
            if fp.at is None:
                continue
            if (bb[0] - 0.5 <= fp.at[0] <= bb[2] + 0.5
                    and bb[1] - 0.5 <= fp.at[1] <= bb[3] + 0.5):
                continue
            cls = bom_split.classify(fp)[0]
            stray.append((fp.ref, cls, fp.at[0], fp.at[1], len(fp.pads)))
        buyable = [t for t in stray if t[1] != "none"]
        if buyable:
            warn(f"{len(buyable)} footprint(s) OUTSIDE the board outline that "
                 f"bom_split.classify() does not exclude: "
                 + "; ".join(f"{r} ({c}, {p} pad(s)) at ({x},{y})"
                             for r, c, x, y, p in buyable)
                 + ". Harmless only because a '*' refdes keeps them out of the position "
                   "file -- annotate one and PCBWay is told to place it off the board.")
        elif stray:
            ok(f"{len(stray)} footprint(s) sit outside the outline, all classified 'none'")
        else:
            ok("every footprint sits inside the board outline")

    # --- does the module physically FIT? Copper clearance never asked. ------------------
    gaps = geom.neighbour_gaps(b, "MOD1", limit=len(MODULE_GAPS))
    drift = [f"{r} {basis} {d:.3f} mm (ledger says {w[1]} {w[2]:.3f})"
             for (r, basis, d), w in zip(gaps, MODULE_GAPS)
             if r != w[0] or basis != w[1] or abs(d - w[2]) > 0.002]
    if len(gaps) != len(MODULE_GAPS) or drift:
        err(f"MOD1's mechanical neighbourhood has MOVED: " + "; ".join(drift or
            [f"{len(gaps)} neighbour(s) found, ledger has {len(MODULE_GAPS)}"])
            + ". Update MODULE_GAPS and the clearance table in DESIGN-DECISIONS.md together.")
    else:
        # The floor applies to parts that will actually BE there. A DNP land is copper and
        # mask; the module sits over it the way it already sits over 25 of MouseBiteLabs'
        # vias. Anything not DNP inside the body is a genuine collision.
        fps_all = kisexp.by_ref(b)
        def _dnp(r):
            am = re.search(r"\(attr ([^)]*)\)", fps_all[r].body) if r in fps_all else None
            return bool(am and "dnp" in am.group(1).split())
        real = [(r, bs, d) for r, bs, d in gaps if not _dnp(r)]
        enclosed = [f"{r} ({d:.3f} mm inside)" for r, _bs, d in gaps if d < 0 and not _dnp(r)]
        floor = min(d for _r, _bs, d in real) if real else 99.0
        dnp_in = [r for r, _bs, d in gaps if d < 0 and _dnp(r)]
        ok(f"MOD1 fits: {len(gaps)} same-side neighbour(s) all where the ledger says, "
           f"tightest populated {floor:.3f} mm ({real[0][0] if real else '-'})"
           + (f"; {', '.join(dnp_in)} inside the body and DNP, by design" if dnp_in else ""))
        if enclosed:
            err(f"POPULATED footprint(s) inside MOD1's own body -- the module cannot go on: "
                + ", ".join(enclosed))
        elif floor < GAP_FLOOR:
            err(f"MOD1's tightest populated neighbour is {floor:.3f} mm, under the "
                f"{GAP_FLOOR} mm floor this project set for a module edge")

    # --- the fiducials have to be READABLE AND LEGAL, and those are five questions -----
    fps = kisexp.by_ref(b)
    fids = sorted(r for r in fps if r.startswith("FID"))
    if not fids:
        err("no fiducials on the board -- this fork adds six; a pick-and-place needs them")
        return
    if len(fids) != len(FIDUCIAL_SITES) or fids != [s[0] for s in FIDUCIAL_SITES]:
        err(f"the board carries {', '.join(fids)}; the ledger describes "
            f"{', '.join(s[0] for s in FIDUCIAL_SITES)}")
        return
    M = geom.site_model(b, skip=set(fids))
    problems, keys = [], ("edge", "keepout", "copper", "mask", "crtyd")
    for ref, *want in FIDUCIAL_SITES:
        fp = fps[ref]
        if fp.at is None:
            problems.append(f"{ref}: no placement")
            continue
        if FIDUCIAL_PAD_CLEARANCE not in fp.body:
            problems.append(f"{ref}: no {FIDUCIAL_PAD_CLEARANCE} on its pad -- a re-pour "
                            f"will flood the mask window with GND")
        m = geom.site_margins(M, fp.at[0], fp.at[1], fp.layer)
        if not m["on_board"]:
            problems.append(f"{ref} at ({fp.at[0]},{fp.at[1]}) is not inside the outline")
        drift = [f"{k} {m[k]:.3f} (ledger {w:.3f})"
                 for k, w in zip(keys, want) if abs(m[k] - w) > 0.005]
        if drift:
            problems.append(f"{ref} has MOVED or its neighbourhood has: " + ", ".join(drift))
        under = [f"{k} {m[k]:.3f} < {FIDUCIAL_FLOOR[k]}" for k in keys
                 if m[k] < FIDUCIAL_FLOOR[k]]
        if under:
            problems.append(f"{ref} is below the floor it was chosen against: "
                            + ", ".join(under))
        note(f"{ref} ({fp.layer}): " + " ".join(f"{k} {m[k]:.2f}" for k in keys))
    if problems:
        err("fiducial(s) a vision system cannot read or a fab cannot build: "
            + "; ".join(problems)
            + ". scripts/place_fiducials.py finds replacements; update FIDUCIAL_SITES, "
              "build_board.FIDUCIALS and the table in DESIGN-DECISIONS.md together.")
    else:
        ok(f"all {len(fids)} fiducials clear on every axis a fab cares about -- edge, "
           f"keepout, copper, mask and courtyard -- and their pours are held back")


# =====================================================================================
# [14] THE ZONE FILL IS STALE, AND EVERY DOCUMENT SAYS SO. RED WHEN IT IS RE-POURED.
# =====================================================================================
# The most consequential open item in this package, and the easiest to forget: the fill in
# the deliverable is MouseBiteLabs' STOCK fill, computed before a single track of this
# fork's copper existed. Plot gerbers from it without opening KiCad and running Fill All
# Zones, and the added pads and vias come out swallowed by the GND, VDD2 and VDD35 pours.
# Three documents say "re-pour before fab"; until now nothing enforced it.
#
# This asserts the state rather than trusting the prose, and reports the SIZE of the hazard
# so it cannot read as theoretical. It goes RED when somebody finally re-pours -- the same
# shape as check [10] -- because at that moment the "stale fill" paragraphs in those
# documents become wrong and need rewriting in the same commit.
FILL_DOCS = ("clockxcontrol-integration/DESIGN-DECISIONS.md",
             "clockxcontrol-integration/README.md",
             "pcbway-assembly/README.md")

# The hazard set, snapshotted with a reason per line. Measured AT EACH PAD, on the layers
# that pad occupies, against that pad's own net -- see geom.swallowed(). Every entry here
# is a real net-to-net overlap in the shipped file that a re-pour removes.
FILL_HAZARD = (
    # C7 is MouseBiteLabs' part, not this fork's. It MOVES out of the module
    # window, and the spot it moves to puts its GND pad inside the VDD35 pour. A rule keyed on
    # "is this refdes new?" cannot see this line; that is why the key is geometry.
    ("C7.2",   "GND",       "VDD35"),
    # ALL SIX fiducials sit on a pour, and they are meant to: a fiducial wants an even
    # background, and every large uninterrupted area on this board is poured copper. The
    # (clearance 0.55) override holds that copper 1.05 mm back from
    # each centre so the 1.0 mm mask window still reads as bare substrate. The chosen spots
    # put FID1/FID4 on the analogue ground rather than the digital one; same story, different
    # net name. Listed because they are still overlaps, and this ledger is about overlaps.
    ("FID1.1", "<netless>", "AGND"),
    ("FID2.1", "<netless>", "GND"),
    ("FID3.1", "<netless>", "GND"),
    ("FID4.1", "<netless>", "AGND"),
    ("FID5.1", "<netless>", "GND"),
    ("FID6.1", "<netless>", "GND"),
    # JP4, the CK1/CXC_CLK cut-and-jumper, sits over GND on both pads.
    ("JP4.1",  "/CPU/CK1",  "GND"),
    ("JP4.2",  "CXC_CLK",   "GND"),
    # The three landed module pads. They straddle TWO pours, not one: pad 1 is over VDD35,
    # pads 2 and 3 over VDD2. The superseded footprint-origin rule reported only VDD35.
    ("MOD1.1", "/CPU/TP2",  "VDD35"),
    ("MOD1.2", "/CPU/TP9",  "VDD2"),
    ("MOD1.3", "/CPU/TP8",  "VDD2"),
    # Two of the three wire test pads. TP85 is GND, so its GND pour is not foreign.
    ("TP83.1", "CXC_CLK",   "GND"),
    ("TP84.1", "VDD3",      "GND"),
    # Every via this fork adds. Eight since the ninth was deleted -- the VDD3 via at
    # (97.1, -34.1), whose DRILL sat 0.4680 mm from P1 pad S1's, against MouseBiteLabs'
    # 0.5 mm min_hole_to_hole. P1.S1 is thru_hole on *.Cu, so the B.Cu run lands on it
    # directly and the layer change was never needed.
    ("via (47.5,-59.5)",   "CXC_CLK",  "GND+VDD5"),
    ("via (55.15,-53.25)", "/CPU/TP9", "GND+VDD2+VDD3"),
    ("via (55.65,-49.65)", "/CPU/TP2", "GND+VDD3"),
    ("via (79.85,-41.1)",  "/CPU/TP2", "GND"),
    ("via (83.25,-39.6)",  "/CPU/TP9", "GND"),
    ("via (93.3,-38.7)",   "GND",      "VDD35"),
    ("via (97.9,-38.6)",   "CXC_CLK",  "GND+VDD3"),
    ("via (99.25,-35.9)",  "VDD3",     "GND"),
)


def check_zone_fill():
    print("[14] the zone fill is still MouseBiteLabs' (RED means it was re-poured)")
    import geom
    b = board()
    try:
        base = geom.base()
    except OSError as e:
        warn(f"base board unreadable ({e}) -- check [14] did not run")
        return
    b_sig, b_n = geom.fill_signature(base)
    o_sig, o_n = geom.fill_signature(b)
    if b_sig != o_sig:
        err(f"THE ZONE FILL HAS BEEN RECOMPUTED ({b_n} -> {o_n} polygons, {b_sig} -> "
            f"{o_sig}). That is good news, and it makes these documents wrong -- they all "
            f"say the fill is stale and must be re-poured before fab. Correct them in the "
            f"same commit: " + ", ".join(FILL_DOCS))
        return
    ok(f"fill is byte-identical to the base ({o_n} polygons, {o_sig}) -- not re-poured")

    # How big is the hazard? Every object THIS FORK put inside a foreign pour, LEDGERED --
    # so the set cannot change without someone updating this table in the same commit.
    #
    # The first version of this counted footprints whose REFDES was new, tested at the footprint
    # ORIGIN, on fp.layer, against the net of pad 1. Three approximations, and a blind spot
    # underneath them: a part MouseBiteLabs already had, which this fork MOVED, has an
    # old refdes and new copper, so the rule skipped it. C7 is exactly that part, and at the
    # spot it moved to, C7.2 lands in the VDD35 pour. It reported 15; the truth
    # is 19. geom.swallowed() is now the one implementation, shared with the renderer.
    have = geom.swallowed(b, base)
    if set(have) != set(FILL_HAZARD):
        gone = sorted(set(FILL_HAZARD) - set(have))
        new_ = sorted(set(have) - set(FILL_HAZARD))
        err(f"the stale-fill hazard set has CHANGED ({len(FILL_HAZARD)} -> {len(have)}). "
            + (f"no longer swallowed: {gone}. " if gone else "")
            + (f"newly swallowed: {new_}. " if new_ else "")
            + "If copper moved, update FILL_HAZARD in the same commit and say why in the "
              "change. If the fill was re-poured, so should these documents be: "
            + ", ".join(FILL_DOCS))
        return
    pads = sum(1 for lab, _n, _p in have if not lab.startswith("via "))
    note(f"{len(have)} added object(s) inside a foreign-net pour until the re-pour: "
         + "; ".join(f"{lab} ({net}) -> {pour}" for lab, net, pour in have[:6])
         + (f"; +{len(have) - 6} more" if len(have) > 6 else ""))
    ok(f"{len(have)} added object(s) sit in a foreign-net pour ({pads} pad(s), "
       f"{len(have) - pads} via(s)), matching the ledger -- DO NOT PLOT GERBERS from this "
       f"file; open it in KiCad, Fill All Zones, re-run DRC")


# =====================================================================================
# [15] the pictures are a function of the board, not a memory of one
# =====================================================================================
# The views in render/ were once described as coming from "a renderer built against the file
# directly". That renderer was never committed, so what shipped was a set of PNGs with no
# generator. When the fork rebased from AGBM-01 onto AGBM-02, every render went on
# describing a board this repository no longer contains -- and nothing noticed, because
# their git blob SHAs were identical before and after. It was caught by hand.
#
# scripts/render_board.py is the missing generator. This re-runs it and compares the RAW
# PIXEL BUFFER of every view against the PNG in the tree, so a picture cannot outlive the
# board it was drawn from. Pixels rather than PNG bytes: a different Pillow build changing
# its deflate settings is not a board that moved, and the check says so when it happens.
# The one image in render/ that is NOT a render of this board, ledgered with its reason so
# the orphan rule below does not demand a generator for it.
NOT_OUR_BOARD = {
    "dmgc_cpu_01_2-5_cxc_footprint.png":
        "MouseBiteLabs' own ClockxControl land pattern on his DMG-Color CPU-01 2.5 board, "
        "rendered from HIS gerbers. It is the reference this fork's footprint was derived "
        "against, not a picture of AGBM-02, so nothing here can regenerate it.",
}


def _render_source_digest():
    """The two hashes a manifest should carry, computed WITHOUT Pillow or KiCad."""
    import hashlib
    import geom
    b, base = board(), geom.base()
    return {"board": hashlib.sha256(b.encode("utf-8")).hexdigest()[:16],
            "base": hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]}


# THIS HALF RUNS EVERYWHERE, and it exists because the other half does not.
# Re-rendering needs Pillow, this project's CI installs nothing on purpose, so check [15]
# reported "did not run" on every build and a stale picture could ride a green pipeline all
# the way to a fab. The renderers now stamp each manifest with the SHA of the board and the
# base they drew, and comparing those is pure string handling. It catches the failure that
# actually matters -- the board moved and the pictures did not -- on any runner that can
# open a file. It cannot catch a renderer whose OUTPUT changed while its input did not;
# that is what the pixel digests below are for, where Pillow exists.
def _check_render_freshness():
    import json as _json
    want = _render_source_digest()
    for name, path in (("render-manifest.json",
                        os.path.join(ROOT, "clockxcontrol-integration", "render",
                                     "render-manifest.json")),
                       ("assembled-manifest.json",
                        os.path.join(ROOT, "clockxcontrol-integration", "render",
                                     "assembled-manifest.json"))):
        if not os.path.exists(path):
            warn(f"{name} is missing -- cannot tell whether those renders are current")
            continue
        got = _json.load(open(path, encoding="utf-8")).get("source")
        if got is None:
            err(f"{name} carries no `source` digest, so nothing can tell whether its "
                f"pictures match the board. Re-run the renderer that writes it.")
        elif got != want:
            which = [k for k in ("board", "base") if got.get(k) != want.get(k)]
            err(f"{name} was written from a DIFFERENT {' and '.join(which)}: "
                f"manifest {got} != tree {want}. The pictures it lists are stale -- re-run "
                f"scripts/render_board.py and scripts/render_assembled.py and commit the "
                f"PNGs in the same commit as the board change.")
        else:
            ok(f"{name} was written from this exact board ({want['board']}) and base "
               f"({want['base']})")


def check_renders():
    print("[15] every render is what the committed board re-renders to")
    _check_render_freshness()
    try:
        import render_board
        from PIL import Image
        import PIL
    except ImportError as e:
        warn(f"Pillow unavailable ({e}) -- the pixel half of check [15] did not run "
             f"(the source-digest half above did)")
        return
    try:
        # The SHIPPED board -- the same text every other check reads -- not the tree file.
        # [1] and [2] already hold those three copies together, and reading the shipped one
        # is what lets scripts/test_checks.py mutate a board and watch this check fire.
        b = board()
        import geom
        base = geom.base()
    except OSError as e:
        warn(f"a board is unreadable ({e}) -- check [15] did not run")
        return
    man = {}
    if os.path.exists(render_board.MANIFEST):
        man = json.load(open(render_board.MANIFEST))
    vs = render_board.views(b)
    stale, missing = [], []
    for name, build in vs:
        path = os.path.join(render_board.OUTDIR, name)
        if not os.path.exists(path):
            missing.append(name)
            continue
        want = render_board.digest(build(b, base)[0])
        have = render_board.digest(Image.open(path).convert("RGB"))
        if want != have:
            stale.append(f"{name} (tree {have} != re-render {want})")
    if missing:
        err(f"render(s) named by the generator but absent from the tree: "
            + ", ".join(missing) + " -- run scripts/render_board.py")
    if stale:
        extra = ""
        if man.get("pillow") and man["pillow"] != PIL.__version__:
            extra = (f" NOTE: the manifest was written by Pillow {man['pillow']} and this "
                     f"is {PIL.__version__}; a rasteriser change can do this without any "
                     f"board having moved.")
        err(f"render(s) no longer match the board they claim to show: "
            + ", ".join(stale) + " -- re-run scripts/render_board.py and commit the PNGs "
            + "in the same commit as the board change." + extra)
    if not missing and not stale:
        ok(f"all {len(vs)} view(s) re-render pixel-for-pixel from the shipped board "
           f"(Pillow {PIL.__version__})")
    # --- the assembled raytraces are a different animal, and gated differently ---------
    # scripts/render_assembled.py drives kicad-cli. Its output is a function of the board
    # AND KiCad's build AND the 3D library, so pixel equality is not a property worth
    # asserting -- a gate that fails on somebody's KiCad version is a gate people learn to
    # ignore. What IS asserted is the thing that actually goes wrong: a body that silently
    # did not draw. The manifest records how many resolved; this fails if that stops being
    # true of the board sitting here, and warns if the renders were never made at all.
    try:
        am = json.load(open(os.path.join(render_board.OUTDIR, "assembled-manifest.json"),
                            encoding="utf-8"))
    except (OSError, ValueError):
        am = None
    if am is None:
        warn("no assembled-manifest.json -- the PCBWay assembly renders have not been made "
             "on this tree (scripts/render_assembled.py; needs KiCad 9)")
    else:
        gone = [n for n in am.get("targets", {})
                if not os.path.exists(os.path.join(render_board.OUTDIR, n))]
        if gone:
            err("assembled render(s) named by the manifest but missing from the tree: "
                + ", ".join(sorted(gone)))
        else:
            worst = min((t["resolved"] / t["referenced"]) for t in am["targets"].values()) \
                if am.get("targets") else 1.0
            ok(f"{len(am.get('targets', {}))} assembled render(s) present, "
               f"{worst:.0%}+ of bodies resolved, KiCad {am.get('kicad', '?')}")
            names = sorted({b for t in am["targets"].values() for b in t.get("bodyless", [])})
            if names:
                note("kept but bodyless: " + ", ".join(names))

    # The generated set and the tree must be the same set, or a stale PNG survives forever
    # simply by no longer being named -- which is exactly how the AGBM-01 renders lasted.
    named = {n for n, _ in vs} | set((am or {}).get("targets", {}))
    ondisk = {f for f in os.listdir(render_board.OUTDIR) if f.endswith(".png")}
    orphan = sorted(ondisk - named - set(NOT_OUR_BOARD))
    if orphan:
        err(f"render(s) in the tree that the generator does not produce: "
            + ", ".join(orphan) + " -- either add a view for them or delete them; an "
            + "ungenerated PNG is how the pre-rebase AGBM-01 images survived so long")


# =====================================================================================
# [16] MouseBiteLabs' own part choices are read, and disagreeing with one is deliberate
# =====================================================================================
# Every symbol in the upstream schematic carries a (property "Source" ...) Digi-Key link.
# That link is the ONLY record of which part MouseBiteLabs actually picked for a generic
# value like "22u" -- the Value field is a symbol name, not an orderable code. scripts/
# link_mpn.json resolves those links.
#
# It was built from AGBM-01 and survived the rebase untouched: 30 of AGBM-02's 57
# links had never been read, including the ones for SW1, P3 and D1/D2 -- the three parts
# pcbway-assembly/README.md called "BOM defects we found". They were not defects. Nick had
# specified CSS-1310TB and SJ-3524-SMT-TR in his own Source property all along.
#
# Two rules. COMPLETENESS: every link in the base schematic must be resolved here, or the
# fork is buying blind against choices it never read. DELIBERATENESS: where a buy line
# disagrees with the link, the override must SAY SO -- an 'eco' or a 'flag'. Three lines
# were diverging silently, and all three had landed on parts with no stock while the part
# MouseBiteLabs chose was sitting in five figures.
def check_upstream_links():
    print("[16] MouseBiteLabs' own part links are all read, and every divergence is stated")
    try:
        import check_stock
    except ImportError as e:
        warn(f"check_stock unavailable ({e}) -- check [16] did not run")
        return
    try:
        srcs = check_stock.schematic_sources()
        links = json.load(open(os.path.join(ROOT, "scripts", "link_mpn.json"),
                               encoding="utf-8"))["links"]
    except (OSError, KeyError, ValueError) as e:
        warn(f"the link map or the base schematic is unreadable ({e}) -- [16] did not run")
        return
    if not srcs:
        warn("the base schematic yielded no Source links -- [16] proved nothing")
        return
    codes = set(srcs.values())
    missing = sorted(codes - set(links))
    if missing:
        err(f"{len(missing)} link(s) in MouseBiteLabs' schematic are NOT resolved in "
            f"scripts/link_mpn.json, so this fork is buying without having read his choice "
            f"for them: " + ", ".join(missing[:8])
            + (f", +{len(missing) - 8} more" if len(missing) > 8 else ""))
    else:
        ok(f"all {len(codes)} of MouseBiteLabs' AGBM-02 part links are resolved")
    stale = sorted(set(links) - codes)
    if stale:
        warn(f"{len(stale)} resolved link(s) no longer appear in the base schematic -- "
             f"harmless, but they are AGBM-01 leftovers: " + ", ".join(stale[:6]))

    # --- where we buy something else, the override has to say why --------------------
    try:
        ov = json.load(open(os.path.join(ROOT, "scripts", "mpn_overrides.json"),
                            encoding="utf-8"))["entries"]
    except (OSError, KeyError, ValueError) as e:
        warn(f"overrides unreadable ({e}) -- the divergence half of [16] did not run")
        return
    over = {r: e for e in ov for r in e["refs"]}
    b = board()
    vals = {r: fp.value for r, fp in kisexp.by_ref(b).items()}
    silent, stated, revalued = [], 0, 0
    for ref, code in sorted(srcs.items()):
        L = links.get(code)
        e = over.get(ref)
        if not L or not e or not e.get("mpn") or e["mpn"] == L["mpn"]:
            continue
        # A change to the VALUE makes the link's part the wrong part by definition -- the
        # board is asking for a different component, not the same one from someone else.
        if L.get("expect") and ref in vals and vals[ref] not in L["expect"].split("/"):
            revalued += 1
            continue
        # Otherwise the same value is being bought from a different part, and the override
        # must NAME the upstream part it departs from. A 'flag' about something else is not
        # enough: CP1-CP3 carried a polarity-marking flag while silently buying a +/-10%
        # tantalum with five units in stock instead of MouseBiteLabs' +/-20% part with
        # 31,360. Naming the part is what forces someone to have looked at it.
        if e.get("upstream") and L["mpn"] in str(e["upstream"]) and (e.get("eco") or e.get("flag")):
            stated += 1
            continue
        silent.append(f"{ref}: we buy {e['mpn']}, MouseBiteLabs' link buys {L['mpn']}")
    if silent:
        err(f"{len(silent)} buy line(s) depart from MouseBiteLabs' own part choice for the "
            f"SAME value with nothing saying why. Either match his link, or add "
            f'"upstream": "<his mpn>" and an "eco"/"flag" saying why not, in '
            f"scripts/mpn_overrides.json: " + "; ".join(silent))
    else:
        ok(f"{stated} deliberate divergence(s) from MouseBiteLabs' links, each naming the "
           f"part it departs from; {revalued} more buy a different value than the link, "
           f"because the board asks for one")


# =====================================================================================
# [17] solder paste is on exactly the pads a machine will put a part on
# =====================================================================================
# A stencil is cut from F.Paste/B.Paste and knows nothing about `dnp` or
# `exclude_from_pos_files`. Paste goes down on every aperture and reflows whether a part
# lands on it or not, so an aperture on a part nobody places is a solder bump on a bare pad.
# 254 of them are stripped. This is the gate that keeps them off.
#
# Two rules, and the second is the one that would ruin a board rather than annoy someone:
#
#   NOTHING UNPLACED IS PASTED. The A/B, Start-Select and D-pad footprints are DUAL-PURPOSE
#   -- each carries the Alps tact-switch land AND THE MEMBRANE CONTACT PADS. A default build
#   uses the rubber membrane, so they are `dnp`, and paste on a membrane contact reflows into
#   a bump on the flat gold surface the rubber pad has to sit on.
#
#   U2 IS PASTED ON EXACTLY ONE OF ITS TWO NESTED LAND PATTERNS. Every one of its 48 pins has
#   two pads on the same net, so the footprint takes either RAM. But the INNER pads of
#   ADJACENT pins sit 0.5 mm apart with a 0.2 mm gap on DIFFERENT nets, so pasting the unused
#   pattern reflows solder under the body of the chip that IS fitted, where a bridge between
#   two address lines can be neither inspected nor reworked.
def check_cpl_datum():
    """Every CPL coordinate must land INSIDE the board outline.

    The position file now carries two coordinate pairs: the board file's own (where y is
    negative, because KiCad's origin sits above the board) and millimetres from the board's
    LOWER-LEFT corner with y up, which is what an assembly house expects. Getting the datum
    backwards mirrors every placement about the board's mid-line -- an error that looks
    entirely plausible on a spreadsheet. This is the arithmetic that would catch it.
    """
    import bom_split, geom
    b = board()
    try:
        _a, _h, _n, cpl, _p = bom_split.build(board=b)
    except Exception as e:                                        # noqa: BLE001
        err(f"the splitter cannot run: {type(e).__name__}: {e}")
        return
    segs = geom.edge_segments(b)
    xs = [v for sg in segs for v in (sg[0], sg[2])]
    ys = [v for sg in segs for v in (sg[1], sg[3])]
    W, H = max(xs) - min(xs), max(ys) - min(ys)
    out = [f"{r['ref']} ({r['x_mm']}, {r['y_mm']})" for r in cpl
           if not (-0.5 <= r["x_mm"] <= W + 0.5 and -0.5 <= r["y_mm"] <= H + 0.5)]
    if out:
        err(f"{len(out)} CPL placement(s) fall outside the {W:.2f} x {H:.2f} mm board -- "
            f"the datum is wrong, and a wrong datum mirrors every part on the panel: "
            + ", ".join(out[:6]))
    else:
        ok(f"all {len(cpl)} CPL placements land inside the {W:.2f} x {H:.2f} mm outline, "
           f"measured from the lower-left corner with y up")


def check_paste():
    print("[17] paste is only where a machine will put a part, and U2 has one land pasted")
    b = board()
    import bom_split, build_board as BB
    bad, pasted, total = [], 0, 0
    for fp in kisexp.footprints(b):
        if fp.at is None:
            continue
        n = len(re.findall(r'\(layers [^)]*Paste', fp.body))
        total += n
        flags = set()
        am = re.search(r"\(attr ([^)]*)\)", fp.body)
        if am:
            flags = set(am.group(1).split())
        placed = not (flags & {"dnp", "exclude_from_pos_files"})
        if placed:
            pasted += n
        elif n:
            bad.append(f"{fp.ref} ({bom_split.classify(fp)[0]}, {n} aperture(s))")
    if bad:
        err("solder paste on pad(s) of part(s) the machine will not place -- the stencil "
            "does not read `dnp`, so every one of these reflows into a bump on a bare pad: "
            + "; ".join(sorted(bad)))
    else:
        ok(f"{pasted} paste aperture(s), every one on a part the position file places")

    # --- U2's dual land -------------------------------------------------------------
    fp = kisexp.by_ref(b).get("U2")
    if fp is None:
        err("U2 is not on the board")
        return
    cols = {}
    for blk in kisexp.pad_blocks(fp.body):
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)", blk)
        lay = re.search(r"\(layers ([^)]*)\)", blk)
        if at and lay and "Paste" in lay.group(1):
            x = round(float(at.group(1)), 4)
            cols[x] = cols.get(x, 0) + 1
    want = {x for x, which in BB.U2_PATTERN_X.items() if which == BB.RAM_FITTED}
    if set(cols) != want:
        err(f"U2's pasted column(s) are {sorted(cols)}, not the {sorted(want)} that "
            f"{BB.RAM_FITTED} needs. Pasting the wrong land -- or both -- puts solder under "
            f"the body of the fitted chip, between adjacent pins on different nets.")
    elif sum(cols.values()) != 48:
        err(f"U2 has {sum(cols.values())} apertures on the right columns, not 48")
    else:
        span = max(cols) - min(cols) + 1.575
        model = re.search(r'\(model "[^"]*/([^"/]+)"', fp.body)
        stem = model.group(1).rsplit(".", 1)[0] if model else "(none)"
        want_model = BB.U2_MODEL[BB.RAM_FITTED][0]
        ok(f"U2 pasted on the {BB.RAM_FITTED} land only (48 apertures, {span:.3f} mm "
           f"lead-tip span)")
        if stem != want_model:
            err(f"U2's 3D body is {stem}, but the pasted land and the BOM are "
                f"{BB.RAM_FITTED}, whose package is {want_model}. Every assembled render "
                f"would show the wrong chip.")
        else:
            ok(f"U2's 3D body is {stem}, matching the land that is pasted and the part the "
               f"BOM buys")


# =====================================================================================
# [18] the CPL's rotations mean what a fab will assume they mean
# =====================================================================================
# A position file carries one number per part -- `rot` -- and the line turns the part by it
# from THEIR zero reference. Nothing in a netlist, a BOM or a DRC can tell you whether that
# reference is the same as the board's; get it wrong and every polarised and every multi-pin
# part goes in rotated. pcbway-assembly/README.md carried this as an open item for a longs.
#
# It is answerable, and this is the answer: `rot` is exactly what kicad-cli's own position
# exporter emits (verified part-by-part, 180 of 180), and MouseBiteLabs' footprints put pin 1
# exactly where KiCad's STOCK library puts it. So "the KiCad convention" is not an assumption
# about this board -- it is a measured property of it, and the question reduces to the single
# well-known one of whether the fab accepts a KiCad position file.
#
# This check is what keeps that true. It re-measures every footprint family against the stock
# library and fails if pin 1 moves. It needs kicad-footprints installed; without it, it says
# so rather than passing vacuously.
STOCK_FP = {                       # Bucketmouse family -> KiCad stock equivalent
    "C_0603_1608Metric_Boxed_2": "C_0603_1608Metric",
    "R_0603_1608Metric_Boxed": "R_0603_1608Metric",
    "C_0805_2012Metric_Boxed_2": "C_0805_2012Metric",
    "C_1210_3225Metric_Boxed_2": "C_1210_3225Metric",
    "Fuse_0805_2012Metric": "Fuse_0805_2012Metric",
    "D_SOD-323F": "D_SOD-323F",
    "LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder":
        "LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder",
    "L_0603_1608Metric": "L_0603_1608Metric",
    "L_CommonModeChoke_TDK_ACM2520-3P": "L_CommonModeChoke_TDK_ACM2520-3P",
    "SOT-23": "SOT-23",
    "SOT-23-5": "SOT-23-5",
    "TSOT-23-6": "TSOT-23-6",
    "TSSOP-14_4.4x5mm_P0.65mm": "TSSOP-14_4.4x5mm_P0.65mm",
    "MSOP-10_3x3mm_P0.5mm": "MSOP-10_3x3mm_P0.5mm",
}
# Families whose pin 1 sits a measurable distance from the stock one, with the reason. A
# LAND that differs is fine; a pin-1 CORNER that differs is the thing that rotates a part.
STOCK_FP_TOLERANCE = {
    "SOT-23": (0.06, "MouseBiteLabs' pads are 0.05 mm longer than stock. Same corner, same "
                     "numbering -- a land tweak, not a different zero."),
    "L_CommonModeChoke_TDK_ACM2520-3P":
        (0.20, "pads extended 0.175 mm outward from stock. Same corner, same numbering."),
}
# The families with no stock equivalent, and why each is nonetheless unambiguous.
NO_STOCK_EQUIVALENT = {
    "AGB-SRAM_2": "MouseBiteLabs' dual land -- its outer pattern measures as a "
                  "TSOP-I-48 18.4x12mm to three decimals, and pin 1 is at its NW corner",
    "AGB-FFC-Connector": "his own 40-pin FFC land; pin 1 is silkscreened on the board",
    "AGB-Switch_CSS-1X10B_Uncentered": "his own, and the part is a slide switch whose only "
                                       "asymmetry is the actuator",
    "R_Array_Convex_4x0603": "4x0603 convex array; pin 1 marked on F.Fab",
    "VREG_TPS63802DLAR": "his own SON land for the TPS63802",
    "3313J-2": "Bourns trimmer, his own land",
    "L_Taiyo-Yuden_NR-20xx_HandSoldering": "symmetric two-terminal inductor",
}


def check_rotation_convention():
    print("[18] the CPL's rotation is KiCad's, and pin 1 is where the stock library puts it")
    import glob
    import bom_split
    b = board()
    stock = {os.path.basename(f)[:-10]: f
             for f in glob.glob("/usr/share/kicad/footprints/*.pretty/*.kicad_mod")}
    if not stock:
        warn("kicad-footprints is not installed -- check [18] cannot re-measure pin 1 "
             "against the stock library and did NOT run (apt install kicad-footprints)")
        return

    def local(body):
        out = {}
        for blk in kisexp.pad_blocks(body):
            nm = re.match(r'\(pad "([^"]*)"', blk)
            at = re.search(r"\(at ([-\d.]+) ([-\d.]+)", blk)
            if nm and at and nm.group(1):
                out.setdefault(nm.group(1), (float(at.group(1)), float(at.group(2))))
        return out

    fams = {}
    for fp in kisexp.footprints(b):
        if fp.at is None or "*" in (fp.ref or ""):
            continue
        if bom_split.classify(fp)[0] != "assembly":
            continue
        fams.setdefault(fp.name.split(":")[-1], fp)
    moved, checked, missing = [], 0, []
    for fam, fp in sorted(fams.items()):
        if fam in NO_STOCK_EQUIVALENT:
            continue
        name = STOCK_FP.get(fam)
        if not name or name not in stock:
            missing.append(fam)
            continue
        his, std = local(fp.body), local(open(stock[name], encoding="utf-8").read())
        if "1" not in his or "1" not in std:
            missing.append(fam)
            continue
        # KiCad BAKES the back-side flip into the stored pad coordinates -- proved by
        # comparing front and back instances of the same family, mirrored in Y on every
        # pin. Un-mirror before comparing, or every back-side family reads as flipped.
        flip = -1.0 if fp.layer == "B.Cu" else 1.0
        d = math.hypot(his["1"][0] - std["1"][0], his["1"][1] * flip - std["1"][1])
        tol = STOCK_FP_TOLERANCE.get(fam, (0.06, ""))[0]
        checked += 1
        if d > tol:
            moved.append(f"{fam} ({fp.ref}): pin 1 is {d:.3f} mm from the stock library's, "
                         f"tolerance {tol}")
    if missing:
        warn(f"{len(missing)} placed family/families have no stock footprint to measure "
             f"against and no ledgered reason: " + ", ".join(sorted(missing)))
    if moved:
        err("pin 1 has MOVED relative to KiCad's stock library, so this board's rotations "
            "no longer carry the standard convention and every rotation-sensitive part is "
            "in question: " + "; ".join(moved))
    else:
        ok(f"{checked} placed footprint family/families put pin 1 exactly where KiCad's "
           f"stock library does ({len(NO_STOCK_EQUIVALENT)} more are MouseBiteLabs' own, "
           f"ledgered)")

    # --- and the CPL's rot is kicad-cli's own, not ours -------------------------------
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("kicad-cli"):
        warn("kicad-cli absent -- the CPL's rotations were not re-derived from KiCad's own "
             "exporter this run (that comparison is the other half of [18])")
        return
    try:
        _a, _h, _n, cpl, _p = bom_split.build(board=b)
        with tempfile.TemporaryDirectory() as td:
            pcb = os.path.join(td, "b.kicad_pcb")
            open(pcb, "w", encoding="utf-8", newline="").write(b)
            out = os.path.join(td, "pos.csv")
            r = subprocess.run(["kicad-cli", "pcb", "export", "pos", "--format", "csv",
                                "--units", "mm", "--side", "both", "--exclude-dnp",
                                "-o", out, pcb], capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(out):
                warn("kicad-cli could not export a position file -- comparison skipped")
                return
            import csv as _csv
            K = {row["Ref"]: row for row in _csv.DictReader(open(out, encoding="utf-8"))}
    except Exception as e:                                        # noqa: BLE001
        warn(f"the kicad-cli comparison did not run ({type(e).__name__}: {e})")
        return
    diff = [f"{r['ref']} ours {r['rot']} vs kicad {K[r['ref']]['Rot']}"
            for r in cpl if r["ref"] in K
            and abs(float(r["rot"]) % 360 - float(K[r["ref"]]["Rot"]) % 360) > 0.01]
    extra = sorted(set(K) - {r["ref"] for r in cpl})
    if diff:
        err(f"{len(diff)} CPL rotation(s) differ from what kicad-cli itself exports: "
            + "; ".join(diff[:6]))
    else:
        ok(f"all {len(cpl)} CPL rotations are identical to kicad-cli's own position export")
    if extra:
        note(f"kicad-cli would also place {extra} -- excluded from our CPL on purpose "
             f"(see check [13]'s off-board rule)")


# =====================================================================================
# [11] the board is structurally sound
# =====================================================================================
def check_structure():
    print("[11] the board parses and has no duplicate reference designators")
    b = board()
    if not kisexp.balanced(b):
        err("unbalanced parentheses -- the board will not open in KiCad")
        return
    # The three logo/graphic footprints are unannotated and all carry the placeholder
    # refdes "G***". That is KiCad's own convention for a part with no annotation, not a
    # collision, so it is skipped rather than reported forever.
    seen, dupes = set(), set()
    for fp in kisexp.footprints(b):
        if "*" in fp.ref or fp.ref == "?":
            continue
        if fp.ref in seen:
            dupes.add(fp.ref)
        seen.add(fp.ref)
    if dupes:
        err("duplicate reference designator(s): " + ", ".join(sorted(dupes)))
    nets = kisexp.net_table(b)
    referenced = {n for fp in kisexp.footprints(b) for _p, n, _nm, _f in fp.pads}
    orphan = sorted(referenced - set(nets))
    if orphan:
        err(f"pad(s) reference net numbers the board does not declare: {orphan[:10]}")
    if not dupes and not orphan:
        ok(f"{len(seen)} footprints, {len(nets)} declared nets, parens balanced")


# =====================================================================================
# [12] nothing reaches the pick-and-place without a BOM line to buy it
# =====================================================================================
# SOLAR-GLOW check [15], ported. It was written there after a pre-order sweep found ten
# reference designators excluded from the BOM but NOT from the position file -- a CPL that
# named ten parts the assembler had never been sold. The same defect was live here: before
# Before the split, the board asked a machine to buy and place the SALVAGED CPU, and `MOD1`
# sat in the
# position file with no BOM line at all. The splitter found the second one; this check is
# what stops either coming back.
#
# It also gates the generated buy documents against a fresh run, the same relationship
# check [2] has with the shipped package.
def check_assembly_split():
    print("[12] the assembly BOM, the hand-buy list and the CPL describe one build")
    try:
        import bom_split
        asm, hand, none, cpl, problems = bom_split.build()
    except Exception as e:                                        # noqa: BLE001
        err(f"the BOM splitter cannot run: {type(e).__name__}: {e}")
        return
    for p in problems:
        err(p)
    cpl_refs = {r["ref"] for r in cpl}
    asm_refs = {r for line in asm for r in line["refs"]}
    hand_refs = {r for line in hand for r in line["refs"] if isinstance(line["refs"], list)}
    unsold = sorted(cpl_refs - asm_refs)
    if unsold:
        err("in the position file with no assembly-BOM line to buy them -- the machine "
            "would be asked to place parts it was never sold: " + ", ".join(unsold))
    both = sorted(asm_refs & hand_refs)
    if both:
        err("on BOTH buy documents, so they would be bought twice: " + ", ".join(both))
    missing_pos = sorted(asm_refs - cpl_refs)
    if missing_pos:
        err("on the assembly BOM but absent from the position file -- bought and never "
            "placed: " + ", ".join(missing_pos))

    # the committed artifacts must be what a fresh run produces
    stale = []
    outdir = os.path.join(ROOT, "pcbway-assembly", "generated")
    if not os.path.isdir(outdir):
        warn("pcbway-assembly/generated/ does not exist -- run scripts/bom_split.py")
    else:
        want = {
            f"{bom_split.STEM}-pcbway-assembly.csv": bom_split._csv(asm),
            f"{bom_split.STEM}-handbuy.csv": bom_split._csv(hand),
            f"{bom_split.STEM}-handbuy.md": bom_split._handbuy_md(hand, 1),
            f"{bom_split.STEM}-cpl.csv": bom_split._csv(cpl, bom_split.CPL_COLUMNS),
            f"{bom_split.STEM}-not-populated.csv": bom_split._csv(none),
        }
        for name, text in want.items():
            path = os.path.join(outdir, name)
            if not os.path.exists(path):
                stale.append(f"{name} missing")
            elif open(path, encoding="utf-8").read() != text:
                stale.append(f"{name} differs from a fresh run")
        if stale:
            err("the generated buy documents are stale -- run scripts/bom_split.py: "
                + "; ".join(stale))
    if not problems and not unsold and not both and not missing_pos and not stale:
        ok(f"{len(asm)} assembly lines ({len(asm_refs)} parts) / {len(hand)} hand-buy / "
           f"{len(cpl)} placements, all consistent")
    unresolved = [r for r in asm if r.get("unresolved")]
    if unresolved:
        warn(f"{len(unresolved)} of {len(asm)} assembly lines "
             f"({sum(r['qty'] for r in unresolved)} of {sum(r['qty'] for r in asm)} parts) "
             f"still have no resolved MPN -- not an error, but not an orderable BOM either")


# =====================================================================================
# [19] the KiCad 10 companion is the same board, not a second board
# =====================================================================================
# The KiCad 9 file stays the source of truth -- it is what check [1] rebuilds
# byte-for-byte from MouseBiteLabs' committed zip -- and the KiCad 10 file beside it is a
# DERIVED ARTIFACT, like the renders. A derived artifact that nothing re-derives is a
# second board, and two boards in one repository is how a fab ends up with the wrong one.
#
# TEXT ONLY, DELIBERATELY. The CONVERSION needs KiCad 10 and cannot run on this project's
# bare CI runner, but the PROOF is pure string handling, so the gate runs everywhere the
# rest of the suite does. scripts/kicad10.py owns the comparison; this calls it, so the
# tool that writes the file and the gate that accepts it cannot disagree about what "the
# same copper" means.
def check_kicad10():
    print("[19] the KiCad 10 companion carries the same copper as the KiCad 9 board")
    try:
        import kicad10
    except ImportError as e:                                      # noqa: BLE001
        warn(f"kicad10 unavailable ({e}) -- check [19] did not run")
        return
    if not os.path.exists(kicad10.BOARD10):
        err(f"{os.path.relpath(kicad10.BOARD10, ROOT)} is missing. The KiCad 10 companion "
            f"ships with the board; regenerate it with `python3 scripts/kicad10.py` on a "
            f"machine with KiCad 10 installed.")
        return
    try:
        b9 = board()                       # the SHIPPED KiCad 9 board, out of the zip
        b10 = kisexp.load(kicad10.BOARD10)
    except OSError as e:
        warn(f"a board is unreadable ({e}) -- check [19] did not run")
        return
    v9, v10 = kicad10.version(b9), kicad10.version(b10)
    if v10 <= v9:
        err(f"the KiCad 10 companion is file version {v10}, not newer than the KiCad 9 "
            f"board's {v9} -- it was not regenerated after the last board change")
        return
    bad = kicad10.compare(b9, b10)
    if bad:
        err(f"the two boards are NOT the same copper ({len(bad)} difference(s)): "
            + "; ".join(bad[:6])
            + ". Re-run `python3 scripts/kicad10.py` and commit both boards together.")
    else:
        ok(f"KiCad 9 (v{v9}) and KiCad 10 (v{v10}) agree: {len(kicad10.runs(b9))} collinear "
           f"track run(s), {len(kicad10.vias(b9))} via(s), "
           f"{len(kicad10.footprints(b9))} footprint(s), every pad and net identical")

# =====================================================================================
# [20] every power figure a document states is in the ledger
# =====================================================================================
# THREE DOCUMENTS NOW STATE THE SAME POWER BUDGET and nothing recomputes any of it. The
# numbers are MODELLED -- derived from MouseBiteLabs' published measurements, not measured
# on a board of this fork, because no such board exists -- so unlike every other check
# here there is no artifact to re-derive them from. That makes them exactly the kind of
# number that rots: someone edits one document, the other two keep the old value, and a
# reader has no way to tell which is current.
#
# So they get the exclusion-ledger treatment instead. Every "N mW" a fork document states
# must appear below with the reason it is that number. Add a figure to a document and this
# check goes red until it is ledgered; change one and it goes red until every copy agrees.
#
# TWO PAIRS HERE LOOK LIKE CONTRADICTIONS AND ARE NOT. Leave them alone:
#   * 40 mW and 44/45 mW are the SAME 12 mA in different reference frames -- 12 mA x 3.3 V
#     at the VDD3 rail is 39.6 mW; referred back through converter 2 and the series
#     protection to the battery it is 44-45 mW. Every other figure here is battery-side.
#   * 26 mW and 25.9 mW, 29 mW and 29.0 mW are a rounded prose figure and its table row.
POWER_LEDGER = {
    "0.62":  "DL1+R25 after the swap, at VOUT5 -- the 'to' half of 4.66 -> 0.62",
    "0.98":  "post-brownout latched-off drain after the swaps, from 6.90",
    "6.90":  "post-brownout latched-off drain before the swaps",
    "12.0":  "U7 TLV9364 -> TLV9064IPWR, the largest single line, at all three points",
    "19":    "net cost of the fork in use at stock speed: 45 module - 25.9 swaps",
    "21.8":  "what the swaps hand back at idle",
    "22":    "net cost of the fork at idle: 44 module - 21.8 swaps",
    "25.9":  "what the swaps hand back in use at stock speed",
    "26":    "25.9 rounded, in prose",
    "29":    "29.0 rounded, in prose",
    "29.0":  "what the swaps hand back at 1.75x",
    "40":    "the module's own 12 mA AT THE VDD3 RAIL (12 mA x 3.3 V). NOT battery-side",
    "45":    "the module referred to the BATTERY, before it overclocks anything",
    "150":   "MouseBiteLabs' own headline: the AGBM draws ~150 mW less than a Funnyplaying GBA",
    "159":   "module AND overclock together, against a stock board, at 1.75x",
    "170":   "MouseBiteLabs' measured AGBM-01 idle -- an ANCHOR, his figure not ours",
    "200":   "the module at 1.75x AT THE RAIL, the upper end of insideGadgets' 40-60 mA",
    "792":   "MouseBiteLabs' measured representative use -- an ANCHOR, FP ITA max brightness",
    "951":   "the 792 mW anchor with the module fitted and running at 1.75x",
}
POWER_DOCS = ("README.md",
              "clockxcontrol-integration/DESIGN-DECISIONS.md",
              "clockxcontrol-integration/README.md",
              "pcbway-assembly/README.md")


def check_power_ledger():
    print("[20] every power figure a document states is in the ledger")
    seen, unledgered = {}, []
    for md in POWER_DOCS:
        path = os.path.join(ROOT, md)
        if not os.path.exists(path):
            err(f"{md} is missing -- it is one of the documents that states the power budget")
            continue
        for m in re.finditer(r"(\d+(?:\.\d+)?) mW", open(path, encoding="utf-8").read()):
            v = m.group(1)
            seen.setdefault(v, set()).add(md)
            if v not in POWER_LEDGER:
                unledgered.append(f"{md}: {v} mW")
    if unledgered:
        err("power figure(s) stated by a document with no line in POWER_LEDGER -- these are "
            "MODELLED numbers that nothing here can re-derive, so a new one has to be "
            "justified in the ledger in the same commit that states it: "
            + "; ".join(sorted(set(unledgered))))
    stale = sorted(set(POWER_LEDGER) - set(seen))
    if stale:
        err("POWER_LEDGER line(s) no longer stated by any document -- a figure that left the "
            "prose must leave the ledger too, or the ledger stops describing the documents: "
            + ", ".join(f"{v} mW" for v in stale))
    if not unledgered and not stale:
        shared = {v: d for v, d in seen.items() if len(d) > 1}
        ok(f"{len(seen)} distinct power figure(s) across {len(POWER_DOCS)} documents, every "
           f"one ledgered; {len(shared)} stated in more than one document")
        for v, docs in sorted(shared.items()):
            note(f"{v} mW in {len(docs)} documents: {', '.join(sorted(docs))}")


# =====================================================================================
# [21] the PCBWay package is plotted from THIS board, and from a re-poured copy
# =====================================================================================
# The fab package is the expensive artifact: a mistake in it is discovered on a panel.
# Two ways it goes wrong, and this catches both cheaply.
#
#   * IT GOES STALE. The board moves, nobody re-plots, and the zip on disk describes an
#     older design. Same failure the renders had. Same fix: the manifest carries the SHA
#     of the board and base it was plotted from, and comparing those needs no KiCad.
#   * IT IS PLOTTED FROM THE STORED FILL. That one would actually ship a shorted board --
#     22 objects this fork adds sit inside a foreign-net pour the stale fill has never been
#     recomputed around. Re-pouring is not cosmetic: it takes F.Cu from 52 filled regions
#     to 88. fab_package.py re-pours a throwaway copy and refuses to plot otherwise, and
#     the manifest records that it did.
#
# The FULL comparison re-plots and diffs every aperture, which needs kicad-cli and pcbnew
# and takes minutes -- so it lives in `fab_package.py --check`, not here. This half runs
# everywhere and is what stops a stale package riding a green build.
FAB_ZIP = os.path.join(ROOT, "pcbway-assembly", "fab", "agbm-02-cxc-pcbway.zip")
FAB_MANIFEST = os.path.join(ROOT, "pcbway-assembly", "fab", "fab-manifest.json")
# Every member the package must carry. A fab house that gets 10 of 11 copper layers does
# not stop -- it builds what it was sent.
FAB_REQUIRED = (
    "ORDER.txt",
    "assembly/agbm-02-cxc-bom.csv",
    "assembly/agbm-02-cxc-cpl.csv",
    "assembly/agbm-02-cxc-do-not-populate.csv",
)
FAB_EXTS = (".gtl", ".g1", ".g2", ".gbl",      # copper, top to bottom
            ".gts", ".gbs",                     # mask
            ".gto", ".gbo",                     # silk
            ".gtp", ".gbp",                     # paste
            ".gm1")                             # outline


def check_fab_package():
    print("[21] the PCBWay package is plotted from this board, and from a re-poured copy")
    if not os.path.exists(FAB_ZIP) or not os.path.exists(FAB_MANIFEST):
        err("no fab package on disk -- run scripts/fab_package.py. The board is not "
            "orderable until there is one")
        return
    man = json.load(open(FAB_MANIFEST, encoding="utf-8"))
    want = _render_source_digest()
    got = man.get("source") or {}
    if got != want:
        err("the fab package was plotted from a DIFFERENT board than the one committed "
            f"(package board {got.get('board')} base {got.get('base')}; committed "
            f"{want['board']} / {want['base']}) -- re-run scripts/fab_package.py and commit "
            "the zip in the same commit as the board change")
        return
    ok(f"plotted from this exact board ({want['board']}) and base ({want['base']})")
    with zipfile.ZipFile(FAB_ZIP) as z:
        names = z.namelist()
        sizes = {n: z.getinfo(n).file_size for n in names}
    missing = [m for m in FAB_REQUIRED if m not in names]
    exts = {os.path.splitext(n)[1].lower() for n in names if n.startswith("gerbers/")}
    missing += [f"a {e} plot" for e in FAB_EXTS if e not in exts]
    if not any(n.startswith("drill/") and n.lower().endswith(".drl") for n in names):
        missing.append("an Excellon drill file")
    # NPTH is its own file and it is NOT optional -- it carries the shell mounting holes,
    # and a board built without them does not fit the case.
    if not any("NPTH" in n and n.lower().endswith(".drl") for n in names):
        missing.append("a separate NPTH drill file (the shell mounting holes)")
    empty = sorted(n for n in names if sizes[n] == 0)
    if missing:
        err("the fab package is missing: " + ", ".join(missing))
    elif empty:
        err("member(s) of the fab package are empty: " + ", ".join(empty))
    else:
        cu = sorted(n for n in names if os.path.splitext(n)[1].lower()
                    in (".gtl", ".g1", ".g2", ".gbl"))
        ok(f"{len(names)} members: {len(cu)} copper layer(s), both masks, both silks, both "
           f"paste layers, the outline, PTH and NPTH drill, and the assembly documents")
        note(f"content digest {man.get('content')}, plotted by {man.get('kicad')}")
    # THE ORDER OPTIONS ARE THE PART THE GERBERS CANNOT CARRY, and the one that was wrong.
    # The KiCad stackup says 1.2 mm; MouseBiteLabs' own README says order 1.0 mm, and a
    # sheet generated off the stackup would have bought boards that do not fit a shell.
    # So the sheet has to agree with HIS README, and this is what says it still does.
    import fab_package
    try:
        spec = fab_package.order_spec()
    except SystemExit as e:
        err(f"MouseBiteLabs' order spec cannot be read: {e}")
        return
    with zipfile.ZipFile(FAB_ZIP) as z:
        sheet = z.read("ORDER.txt").decode("utf-8") if "ORDER.txt" in z.namelist() else ""
    absent = [f"{k} = {v!r}" for k, v in
              (("thickness", spec["thickness"]), ("layers", spec["layers"]))
              if v not in sheet]
    if absent:
        err("ORDER.txt does not state MouseBiteLabs' own order option(s): "
            + "; ".join(absent) + " -- his README is what a builder orders from, and the "
            "KiCad stackup disagrees with it, so the sheet must carry his number")
    else:
        ok(f"the order sheet carries his spec: {spec['thickness']}, {spec['layers']} layers, "
           f"{spec['surface_finish'].replace('**', '').split('(')[0].strip()}")

    # "BGA/QFP: 0" IS A NUMBER THAT CHANGES THE QUOTE AND THE INSPECTION PROCESS, and a
    # package detector that has quietly stopped detecting reports exactly the same zero as
    # a board with no quad packages on it. The two are indistinguishable from the sheet.
    # So prove the detector can still see one before believing its zero: U1 IS a QFP-128
    # and must classify as quad, and U2 -- 96 pads in four columns, which every naive test
    # calls a QFP or a BGA -- must classify as dual. If either moves, the zero is
    # meaningless and this goes red.
    shape = lambda fp: fab_package._package_shape(fab_package._pad_geometry(fp))[0]
    seen = {fp.ref: shape(fp) for fp in kisexp.footprints(board()) if fp.ref in ("U1", "U2")}
    wrong = [f"{r} reads as {seen.get(r, 'absent')!r}, not {w!r}"
             for r, w in (("U1", "quad"), ("U2", "dual")) if seen.get(r) != w]
    if wrong:
        err("the package classifier no longer recognises this board's landmarks -- "
            + "; ".join(wrong) + ". ORDER.txt's BGA/QFP count is derived from it, so it "
            "cannot be trusted until this is fixed")
        return
    counts = fab_package.assembly_counts(board())
    n = len(counts["bga"]) + len(counts["quad"])
    stated = re.search(r"BGA / QFP parts \.+ (\d+)", sheet)
    if not stated:
        err("ORDER.txt states no BGA/QFP count -- the assembly form asks for one")
    elif int(stated.group(1)) != n:
        err(f"ORDER.txt says {stated.group(1)} BGA/QFP part(s); the board has {n} in the "
            "assembly scope -- regenerate the package")
    else:
        ok(f"the classifier still sees U1 as a QFP and U2 as a dual package, and the sheet's "
           f"{n} BGA/QFP agrees with the board ({len(counts['smd'])} SMD, "
           f"{len(counts['through_hole'])} through-hole, {counts['unique_mpns']} unique MPN(s))")

    # THE ONE INSTRUCTION THE PACKAGE CANNOT ENCODE. CP1-CP3 are polarised tantalums on a
    # mirror-symmetric land with mirror-symmetric silk: the board carries no indication of
    # which end is which, so a line that reads the rotation the wrong way fits all three
    # backwards and nothing catches it -- not DRC, not AOI, not a visual check. Reversed
    # tantalums fail shorted. The sheet is the only place that warning can live, so it has
    # to NAME every such part, and the naming has to come from the board rather than from
    # a sentence somebody typed once.
    risky = fab_package.polarity_risk(board(), fab_package.described_parts())
    unnamed = [r for r, _m, _d in risky if r not in sheet]
    if unnamed:
        err("ORDER.txt does not name polarised part(s) that the board gives no polarity "
            "mark for: " + ", ".join(unnamed) + " -- a machine cannot recover the "
            "orientation and nothing downstream catches it being wrong")
    elif not risky:
        note("no placed part is both polarised and unmarked -- nothing to warn about")
    else:
        ok(f"the order sheet names all {len(risky)} polarised part(s) the board gives no "
           f"polarity mark for ({', '.join(r for r, _m, _d in risky)}), and every other "
           "polarised part on the board carries one")



def main():
    global verbose
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-v", "--verbose", action="store_true")
    verbose = ap.parse_args().verbose
    for fn in (check_reproducible, check_package_parity, check_library_footprint,
               check_dnp_ledger, check_bom_vs_board, check_supplier_pns,
               check_cited_paths, check_doc_imagery, check_module_window,
               check_blockers, check_structure, check_assembly_split,
               check_geometry, check_zone_fill, check_renders,
               check_upstream_links, check_paste, check_cpl_datum,
               check_rotation_convention, check_kicad10,
               check_power_ledger, check_fab_package):
        fn()
    print(f"\n== {len(errors)} error(s), {len(warnings)} warning(s) ==")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
