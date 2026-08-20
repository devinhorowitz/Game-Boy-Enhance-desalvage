#!/usr/bin/env python3
"""check_consistency.py -- drift guard for the AGBM-02 ClockxControl fork.

    python3 scripts/check_consistency.py          # run every check
    python3 scripts/check_consistency.py -v       # also print what each check saw

Cross-checks the documents against the board they describe, so a change to one that is
not mirrored in the other fails loudly instead of rotting.

  [1]  REPRODUCIBLE   -- scripts/build_board.py rebuilds the shipped board byte-for-byte
                         from MouseBiteLabs' committed AGBM-02.                     [ERROR]
  [2]  PACKAGE PARITY -- every document inside the shipped zip is byte-identical to its
                         copy in the tree.                                  [ERROR]
  [2b] LIB FOOTPRINT  -- the shipped ClockxControl_GBA_GBC.kicad_mod is what the board's
                         own MOD1 block derives to -- not a hand-kept second copy of it.
                                                                            [ERROR]
  [3]  ECO-8 LEDGER   -- the swap table in ECO-8 names the same eleven refs, the same old
                         values and the same new values as the generator and the board.
                                                                            [ERROR]
  [4]  DNP LEDGER     -- exactly the parts ECO-7 says are DNP are DNP.      [ERROR]
  [5]  BOM vs BOARD   -- every ref in resolved-mpns.json exists on the board and carries
                         the Value that file claims for it.                 [ERROR]
  [6]  SUPPLIER P/N   -- every MPN in resolved-mpns.json is one a distributor number
                         could plausibly buy, or is ledgered.               [ERROR]
  [7]  CITED PATHS    -- every path any .md cites exists, is marked historical in its own
                         sentence, or carries a reason in EXPECTED_ABSENT.  [ERROR]
  [8]  DOC IMAGERY    -- every image any .md displays exists in the tree.   [ERROR]
  [9]  MODULE WINDOW  -- the component-free window ECO-6 exists to create is still
                         component-free, and the parts it moved are where it put them.
                                                                            [ERROR]
  [10] BLOCKER LEDGER -- both former ECO-7 blockers are CLOSED by the ECO-13 rebase.
                         GOES RED IF EITHER COMES BACK -- see the check.    [ERROR]
  [11] STRUCTURE      -- the board parses, parens balance, no duplicate refdes. [ERROR]
  [12] ASSEMBLY SPLIT -- nothing reaches the pick-and-place without a BOM line to buy it,
                         nothing is on both buy documents, and the generated buy documents
                         are what a fresh run produces.                     [ERROR]
  [13] REAL GEOMETRY  -- the copper this fork ADDS clears MouseBiteLabs' by the project's
                         own netclass rule, the fiducials are readable, and the module
                         physically FITS its same-side neighbours.           [ERROR]
  [14] ZONE FILL      -- the fill is still MouseBiteLabs' stock fill, so gerbers plotted
                         from this file would short, and the LEDGERED set of 19 objects the
                         stale fill swallows is still exactly that set.
                         GOES RED WHEN RE-POURED.                            [ERROR]
  [15] RENDERS        -- every 2D PNG in render/ re-renders, pixel for pixel, from the
                         board committed beside it; the assembled raytraces are present and
                         their bodies resolved.                              [ERROR]
  [16] UPSTREAM LINKS -- every Digi-Key link in MouseBiteLabs' schematic is resolved, and
                         every buy line that departs from one says why.      [ERROR]

Exit: nonzero if any ERROR-level check fails. Warnings do not fail the build.
Needs: python3 and the standard library. Nothing else -- no KiCad, no pip, no container.

WHERE THIS CAME FROM

The shape is borrowed wholesale from SOLAR-GLOW's `scripts/check_consistency.py`: numbered
checks, an `err`/`warn`/`ok` accumulator, and -- the part that actually matters -- the
EXCLUSION-LEDGER DISCIPLINE. Where there is no second source of truth to compare against,
the check carries a SNAPSHOT with a reason on every line. A deliberate change updates the
snapshot in the same commit; an undeliberate one stops being invisible. Checks [4], [9]
and [10] are that shape.

Checks [10] and [14] are the sharper version of it, also borrowed: A CHECK THAT GOES RED
WHEN THE STATE IT DESCRIBES CHANGES. [10] guarded two blockers as open; the ECO-13 rebase
closed both and [10] fired, forcing four documents to be corrected in the same commit --
then it was inverted, and now guards them as closed. [14] does the same for the stale zone
fill: three documents say "re-pour before fab", and the day someone does, those paragraphs
become wrong. A blocker that gets quietly fixed and leaves its scary paragraph behind is how
a repository starts lying about itself.

Checks [13] and [14] also close a gap the first twelve shared: they were all TOPOLOGICAL --
what exists, what it is called, what it connects to -- and none could measure a distance or
read a pour. That is how a 0.1632 mm clearance violation and six unreadable fiducials
shipped past all of them. scripts/geom.py is the arithmetic they were missing.
"""
from __future__ import annotations

import argparse
import json
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
ECO8_DOC = os.path.join(ROOT, "clockxcontrol-integration", "ECO-8_component_swaps.md")
ECO10_DOC = os.path.join(ROOT, "clockxcontrol-integration", "ECO-10_precision_pass.md")
ECO11_DOC = os.path.join(ROOT, "clockxcontrol-integration", "ECO-11_gate_drive_and_D1.md")
ECO12_DOC = os.path.join(ROOT, "clockxcontrol-integration",
                         "ECO-12_wiki_audit_corrections.md")

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
    return set(out.stdout.split("\n")) - {""}


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
        f"hand-edited -- in which case the ECOs no longer describe it -- or the "
        f"generator changed without repacking. Run build_board.py then pack_board.py.")


# =====================================================================================
# [2] the shipped zip and the tree hold the same documents
# =====================================================================================
def check_package_parity():
    print("[2] every document in the shipped zip matches its copy in the tree")
    pairs = {
        f"{ZIP_ROOT}/README.md": "clockxcontrol-integration/README.md",
        f"{ZIP_ROOT}/ECO-6_clockxcontrol_footprint.md":
            "clockxcontrol-integration/ECO-6_clockxcontrol_footprint.md",
        f"{ZIP_ROOT}/ECO-7_u2_supply_and_dnp.md":
            "clockxcontrol-integration/ECO-7_u2_supply_and_dnp.md",
        f"{ZIP_ROOT}/ECO-8_component_swaps.md":
            "clockxcontrol-integration/ECO-8_component_swaps.md",
        f"{ZIP_ROOT}/ECO-9_assembly_split.md":
            "clockxcontrol-integration/ECO-9_assembly_split.md",
        f"{ZIP_ROOT}/ECO-10_precision_pass.md":
            "clockxcontrol-integration/ECO-10_precision_pass.md",
        f"{ZIP_ROOT}/ECO-11_gate_drive_and_D1.md":
            "clockxcontrol-integration/ECO-11_gate_drive_and_D1.md",
        f"{ZIP_ROOT}/ClockxControl_GBA_GBC.kicad_mod":
            "clockxcontrol-integration/footprint/ClockxControl_GBA_GBC.kicad_mod",
    }
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
# [3] ECO-8's own table is the ledger for the swaps
# =====================================================================================
def check_eco8_ledger():
    """Every ECO whose table names a Value change is held to the generator and the board."""
    # ECO-10 and ECO-12 changed only Values that the LTC3527 or the stale AGBM-01
    # annotation carried, and neither exists on the AGBM-02 base -- their generator lists
    # are empty and their documents no longer hold a swap table. ECO-13 section 13.4 is
    # the record of why. They are asserted empty here so that adding a row to either
    # without re-listing it below fails loudly instead of going unchecked.
    for label, gen in (("ECO-10", build_board.ECO10), ("ECO-12", build_board.ECO12)):
        if gen:
            err(f"{label} has Value swaps again but is not in check [3]'s list -- add it")
    for label, doc_path, gen in (("ECO-8", ECO8_DOC, build_board.ECO8),
                                 ("ECO-11", ECO11_DOC, build_board.ECO11)):
        _check_one_eco(label, doc_path, gen)


# An ECO document records the change IT made and is not wrong when a later ECO moves the
# same part again -- ECO-8 took R23 to 1.69M and ECO-10 then took that to 169k, and both
# statements are true. So each ECO's table is checked against its own generator list, and
# the BOARD is checked only against where the whole chain ends up.
def _eco_chain_final():
    out = {}
    for lst in (build_board.ECO8, build_board.ECO10, build_board.ECO11,
                build_board.ECO12):  # 10 and 12 are empty on the AGBM-02 base
        for ref, field, _o, n in lst:
            if field == "Value":
                out[ref] = n
    return out


def _check_one_eco(label, doc_path, gen):
    print(f"[3] {label}'s swap table matches the generator and the board")
    final = _eco_chain_final()
    try:
        doc = open(doc_path, encoding="utf-8").read()
    except OSError as e:
        err(f"cannot read {label}: {e}")
        return
    # | `U7` | `TLV9364` | **`TLV9064IPWR`** | correctness | ... |
    row = re.compile(r"^\|\s*`(\w+)`\s*\|\s*\**`([^`]+)`\**\s*\|\s*\**`([^`]+)`\**\s*\|",
                     re.M)
    doc_rows = {ref: (was, now) for ref, was, now in row.findall(doc)}
    gen_rows = {ref: (o, n) for ref, field, o, n in gen if field == "Value"}
    if not doc_rows:
        err(f"{label} has no parseable swap table -- check [3] cannot gate anything")
        return
    fps = kisexp.by_ref(board())
    bad = []
    for ref, (o, n) in gen_rows.items():
        if ref not in doc_rows:
            bad.append(f"{ref}: in the generator, absent from {label}'s table")
            continue
        d_old, d_new = doc_rows[ref]
        if (d_old, d_new) != (o, n):
            bad.append(f"{ref}: {label} says {d_old!r}->{d_new!r}, generator says "
                       f"{o!r}->{n!r}")
        if ref not in fps:
            bad.append(f"{ref}: not on the board")
        elif fps[ref].value != final.get(ref, n):
            bad.append(f"{ref}: board Value is {fps[ref].value!r}, the ECO chain ends at "
                       f"{final.get(ref, n)!r}")
        note(f"{ref}: {o} -> {n}"
             + (f" (later superseded to {final[ref]})" if final.get(ref) != n else ""))
    for ref in set(doc_rows) - set(gen_rows):
        bad.append(f"{ref}: in {label}'s table, not in the generator")
    if bad:
        err("ECO-8, the generator and the board disagree: " + "; ".join(sorted(bad)))
    else:
        ok(f"{len(gen_rows)} Value swaps agree across ECO-8, the generator and the board")


# =====================================================================================
# [4] the DNP set is exactly what ECO-7 says it is
# =====================================================================================
# The ECO-5 base board already ships 49 DNP footprints -- MouseBiteLabs marks every test
# point, the battery contacts, the trigger switches, the logos and the alternate-build
# resistors "do not place". So the truth to compare against is the BASE BOARD, not a
# hand-typed list: this fork's DNP set must be exactly the inherited set plus the three
# parts ECO-7 adds. That way a stray flag on either side goes red, and the check needs no
# maintenance when upstream changes its mind.
#
# Only ECO-7's own additions need a reason here, and each carries one.
DNP_ADDED = {
    "X1": "ECO-7: the ClockxControl drives CK1 directly, so the 4.194304 MHz crystal "
          "must be absent on a module build",
    "C3": "ECO-7: 27p load cap, sits straight on CK1",
    "C4": "ECO-7: 33p -- NOT dangling with X1 gone. It stays tied to CK2 through R41 "
          "2.2k, so it loads the CPU's XOUT node. ECO-6 said 'dangling' and was wrong; "
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
    err("the shipped .kicad_mod is NOT what the board's MOD1 derives to. Before ECO-14 "
        "these drifted unnoticed -- the library labelled the landings 1/2/3 where the "
        "board says SEL/L/R, its centre text was 1.2 against 1.05, and its reference read "
        "MOD. Anyone re-importing the library got a different part from the one this fork "
        "verified. Run scripts/build_board.py, which regenerates it.")


def check_dnp_ledger():
    print("[4] the DNP set is the ECO-5 base's, plus exactly what ECO-7 adds")
    try:
        base = kisexp.load(os.path.join(ROOT, BASE_ZIP_REF.split("::")[0])
                           + "::" + BASE_ZIP_REF.split("::")[1])
    except (OSError, KeyError, ValueError) as e:
        err(f"cannot read the ECO-5 base: {type(e).__name__}: {e}")
        return
    inherited = {fp.ref for fp in kisexp.footprints(base) if fp.dnp}
    got = {fp.ref for fp in kisexp.footprints(board()) if fp.dnp}
    want = inherited | set(DNP_ADDED)
    extra, missing = sorted(got - want), sorted(want - got)
    if extra:
        err("footprint(s) marked DNP that neither the ECO-5 base nor ECO-7 accounts for "
            "-- add a reasoned line to DNP_ADDED in the same commit, or un-flag them: "
            + ", ".join(extra))
    if missing:
        err("expected DNP and the board disagrees: " + ", ".join(missing))
    if not extra and not missing:
        ok(f"{len(inherited)} inherited from the ECO-5 base + "
           f"{len(DNP_ADDED)} from ECO-7 ({', '.join(sorted(DNP_ADDED))})")


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
                         "AGB-SRAM land takes either a donor chip or, since ECO-13, a "
                         "CY62157EV30LL that the MPN names",
    # ECO-13: AGBM-02 states the CHOICE in the Value field rather than picking for you.
    # Z57/Z58 read "100p or 0 ohm" because the hotkey pair is configurable -- capacitors
    # make L+R+Start+A/B fake a screen kit's touch input, resistors or jumpers make them
    # act as button inputs for an external mod. MouseBiteLabs' Feature Configurations page
    # is the instruction; this fork does not get to decide it for the builder, so the BOM
    # buys the capacitor and pcbway-assembly/README.md carries it as a build decision.
    r"^100p or 0 ohm$": "configurable hotkey part -- see ECO-13 and Feature Configurations",
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
# [16] and ECO-15 -- so it could not see that its "discoveries" were already his answers.
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
    # people learn to ignore. But it must be SAID. Until ECO-15 the shipped BOM carried no
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
    "AGBM-01_AA_1-2.kicad_sch":
        "the upstream schematic -- inside 'AGBM-01 (AA Batteries)/AGBM-01_Design Files.zip', "
        "not loose in the tree. ECO-8 section 8.5 cites it as the file to edit, which is "
        "correct: you unzip it, edit it, and the fork keeps shipping a .kicad_pcb",
    "Audio.kicad_sch": "same archive -- the audio sheet the U7 and VR2 sourcing came from",
    "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb":
        "the deliverable board -- inside clockxcontrol-integration/board/"
        "agbm-02-clockxcontrol.zip, and rebuildable with scripts/build_board.py. Cited by "
        "basename throughout the ECOs because that is its name inside the package",
    "AGBM-01_AA_1-2.kicad_pcb":
        "MouseBiteLabs' AGBM-01 board -- inside 'AGBM-01 (AA Batteries)/AGBM-01_Design "
        "Files.zip'. Cited by basename when comparing save dates and layouts across his "
        "three boards",
    "AGBM_LiPo_1-3.kicad_pcb":
        "MouseBiteLabs' AGBM-11 board -- inside 'AGBM-11 (Lithium-ion)/AGBM-11 Design "
        "Files.zip'. Same reason",
    "IMG_6317.jpg":
        "insideGadgets' own GBA installation photo, at shop.insidegadgets.com/wp-content/"
        "uploads/2019/11/IMG_6317.jpg. ECO-14 section 14.1 cites it as the evidence that "
        "'GBA SI' in their wiring list is a typo for the pad silkscreened S1 -- the red V+ "
        "wire is soldered to it. NOT vendored into this repository: it is their "
        "copyrighted image, so it is cited by URL and left where it lives",
    "AGBM-02_AA_1-1.kicad_pcb":
        "the base board -- inside 'AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip', "
        "MouseBiteLabs' own file, unmodified since ECO-13",
    # ECO-13 culled these. They are cited only to say what was removed, which is a
    # sentence the history rule already allows -- but they are named in TABLES, where
    # there is no prose to carry the explanation, so they are ledgered here instead.
    "AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb":
        "the PREVIOUS deliverable board, on the AGBM-01 base. Culled by ECO-13; in git "
        "history only. Named in ECO-13's was/now table",
    "AGBM-01_AA_1-2_GBE-plus.kicad_pcb":
        "the ECO-5 base board. Culled by ECO-13 -- ECO-5 was our own footprint work, "
        "superseded by MouseBiteLabs' AGBM-02. Git history only",
    "agbm-01-ram-desalvage.zip":
        "ECO-5's package. Culled by ECO-13; git history only",
    "agbm-01-clockxcontrol.zip":
        "the PREVIOUS output package, on the AGBM-01 base. Culled by ECO-13; git history "
        "only",
    "Files.zip":
        "a false positive -- the bare-path regex clips "
        "'AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip' at its last space. The real "
        "archive is in the tree; only this fragment is not",
    "patch5.py": "the pre-ECO-8 generator, superseded by scripts/build_board.py",
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
# [9] the window ECO-6 exists to create is still empty
# =====================================================================================
# ECO-6's entire feasibility claim is that relocating ONE 0603 opens an 18.65 x 12.00 mm
# component-free window on the front side below the RAM. Nothing else in this repo would
# notice a part being dropped back into it, and DRC would not either -- a footprint whose
# courtyard clears its neighbours can still sit exactly where the module has to go.
#
# The module body is the fp_rect at +/-9.325 x +/-6.000 about MOD1's origin.
WINDOW_HALF_X, WINDOW_HALF_Y = 9.325, 6.0
WINDOW_OCCUPANTS = {"MOD1"}          # the module itself, and nothing else
# The parts ECO-6 moved, and where it put them. A deliberate move updates this table in
# the same commit -- the exclusion-ledger shape.
PLACED = {
    "C7":   (93.1, -37.4, "moved out of the window; pad 1 (VDD35) now lands on the left"),
    # ECO-14 moved all three pairs off MouseBiteLabs' copper -- the inherited AGBM-01 spots
    # were never checked against AGBM-02's tracks and vias. Clear radius to the nearest hard
    # copper is in the second field of each reason.
    "FID1": (28.1, -9.6, "fiducial, front. 2.390 mm clear (was 1.064 at 26.0,-8.0). "
                         "Fiducials are OURS -- neither of MouseBiteLabs' boards carries "
                         "one, because he hand-builds"),
    "FID4": (28.1, -9.6, "same spot, back -- 2.390 mm clear"),
    "FID3": (31.0, -69.5, "fiducial, front. 2.399 mm clear; the old (33.0,-69.0) sat "
                          "0.768 mm from a GND via, inside its own 1.0 mm mask window"),
    "FID6": (31.0, -69.5, "same spot, back -- 2.478 mm clear"),
    "FID2": (110.85, -57.65, "fiducial, front. 1.800 mm clear (was 1.337). The tightest of "
                             "the three; that corner is dense"),
    "FID5": (110.85, -57.65, "same spot, back -- 1.918 mm clear"),
    "MOD1": (91.95, -44.95, "module centre, rev B -- shifted west out of the R3/TP114 "
                            "cluster; ECO-6 section 6.7 is what that cost"),
    "TP83": (97.9, -37.95, "CLK wire pad. y is -37.95 and not -38.6: KiCad's y grows "
                           "DOWNWARD, and at -38.6 the 1.2 mm pad overlaps the module "
                           "body by 0.25 mm at its radius"),
    "TP84": (99.45, -37.95, "V+ wire pad"),
    "TP85": (101.0, -37.95, "V- wire pad"),
    "JP4":  (45.0, -64.2, "CK1 isolation jumper -- OPEN for a crystal build, BRIDGED for "
                          "a ClockxControl build"),
}


def check_module_window():
    print("[9] the ECO-6 module window is still component-free, and its parts have not moved")
    fps = kisexp.by_ref(board())
    if "MOD1" not in fps or fps["MOD1"].at is None:
        err("MOD1 is not on the board -- the whole ECO-6 window claim is unverifiable")
        return
    mx, my, _ = fps["MOD1"].at
    intruders = []
    for fp in fps.values():
        if fp.ref in WINDOW_OCCUPANTS or fp.at is None or fp.layer != "F.Cu":
            continue
        dx, dy = abs(fp.at[0] - mx), abs(fp.at[1] - my)
        if dx <= WINDOW_HALF_X and dy <= WINDOW_HALF_Y:
            intruders.append(f"{fp.ref} ({fp.value}) at {fp.at[0]},{fp.at[1]}")
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
    if intruders:
        err(f"footprint origin(s) inside the {2 * WINDOW_HALF_X} x {2 * WINDOW_HALF_Y} mm "
            f"module window -- the module physically cannot go on: " + ", ".join(intruders))
    if moved:
        err("ECO-6 placement has drifted from the snapshot -- a deliberate move updates "
            "PLACED in this file in the same commit, and re-runs the clearance analysis "
            "in ECO-6 section 6.7: " + "; ".join(moved))
    if not intruders and not moved:
        ok(f"window clear, all {len(PLACED)} ECO-6 placements on their snapshotted spot")


# =====================================================================================
# [10] the ECO-7 blockers are still blockers
# =====================================================================================
# THIS CHECK GOES RED WHEN THE BUGS ARE FIXED. That is deliberate, and it is the point.
#
# ECO-7 and both READMEs carry a prominent "the board is not fabricable" section resting
# on two facts about copper. When somebody opens KiCad and routes them, the board becomes
# fabricable and every one of those paragraphs becomes a lie -- with nothing to notice.
# So the facts are asserted here: fix the board, this check fails, and the failure names
# the documents that have to be corrected in the same commit.
VDD2_NET = 8            # from the board's own net table; asserted below
VDD2_EAST_LIMIT = 93.0  # ECO-7: "there is no VDD2 via anywhere with x > 93"
BROKEN_NET = "Net-(Q5B-G)"
# The two islands ECO-5 left behind, and the via site that used to join them. Both come
# from the STOCK MouseBiteLabs board, which routes this net whole -- so unlike the VDD2
# blocker there is a known-good reference to diff against, and this check does.
BROKEN_ISLANDS = [["U17.1"], ["Q5.3", "R66.2"]]
MISSING_VIA = (100.8, -62.15)
BLOCKER_DOCS = ("clockxcontrol-integration/ECO-7_u2_supply_and_dnp.md",
                "clockxcontrol-integration/ECO-13_rebase_onto_agbm02.md")


# =====================================================================================
# [10] BOTH ECO-7 BLOCKERS ARE CLOSED. RED MEANS ONE CAME BACK.
# =====================================================================================
# This check used to assert the OPPOSITE: that both blockers were still open, and it went
# red if either got fixed, so that four documents claiming "not fabricable" could not
# quietly become wrong. On 2026-08-19 it fired, on both, for the best possible reason --
# ECO-13 rebased the fork onto MouseBiteLabs' AGBM-02 and BOTH BLOCKERS WERE ECO-5's OWN
# DAMAGE. ECO-5 is gone, so they are gone.
#
# The check is kept, inverted, rather than deleted. What it guards now is that nothing
# re-introduces them: a future ECO that starts deleting vias around U2 to make room for
# something will trip it, which is exactly how they arose the first time.
def check_blockers():
    print("[10] both former ECO-7 blockers are CLOSED (RED means one came back)")
    b = board()
    nets = kisexp.net_table(b)
    vdd2 = next((n for n, nm in nets.items() if nm == "VDD2"), None)
    if vdd2 is None:
        err("the board has no VDD2 net -- this check cannot verify U2's supply")
        return

    # --- former blocker 1: U2 pin 37's VDD2 supply --------------------------------
    # On the ECO-5 base there was NO VDD2 via anywhere east of x=93, because ECO-5 had
    # deleted two of them to clear its third pad column. On AGBM-02 pin 37 lands on the
    # x=10.97 column -- a stock column the OEM RAM uses too -- and the vias are present.
    east = [(x, y) for x, y, n in kisexp.vias(b) if n == vdd2 and x > VDD2_EAST_LIMIT]
    if east:
        ok(f"U2 pin 37's supply is back: {len(east)} VDD2 via(s) east of "
           f"x={VDD2_EAST_LIMIT} ({', '.join(f'({x},{y})' for x, y in east[:4])})")
    else:
        err(f"U2 PIN 37 HAS LOST ITS SUPPLY AGAIN -- no VDD2 via east of "
            f"x={VDD2_EAST_LIMIT}. This was ECO-5's defect and the rebase closed it; if an "
            f"ECO has re-opened it, say so in: " + ", ".join(BLOCKER_DOCS))

    # --- former blocker 2: Net-(Q5B-G) whole --------------------------------------
    num = next((n for n, nm in nets.items() if nm == BROKEN_NET), None)
    if num is None:
        err(f"{BROKEN_NET} is not in the board's net table any more -- ECO-7 describes it")
        return
    islands = kisexp.net_islands(b, num)
    if len(islands) == 1:
        ok(f"{BROKEN_NET} is whole ({', '.join(sorted(islands[0]))}) -- the supervisor "
           f"reaches Q5B's gate and the low-battery LED works")
    else:
        err(f"{BROKEN_NET} IS BROKEN INTO {len(islands)} ISLANDS AGAIN "
            f"({' | '.join(', '.join(sorted(i)) for i in islands)}). On the ECO-5 base this "
            f"was caused by a deleted via at {MISSING_VIA}; the low-battery LED is dead "
            f"while it holds. Record it in: " + ", ".join(BLOCKER_DOCS))

    # The base this fork sits on. Diffing against it is what proved the break was ECO-5's
    # and not MouseBiteLabs', so the check keeps comparing rather than trusting a memory.
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
# connects to. None of them could measure a distance, and that is exactly how ECO-6 shipped
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


# MOD1's mechanical neighbourhood, snapshotted with a reason per line. Nothing measured
# this before: every gate was about copper, and whether the module physically FITS rested on
# a table in ECO-6 §6.6 taken off a render that turned out to be pre-rebase. The figures did
# survive the rebase -- all four of ECO-6's courtyard rows reproduce to three decimals -- but
# nothing was holding them there.
#
# Same-side only. A sweep that ignores which side a part is on puts C12 at 0.055 mm, which
# reads like a collision; C12 is on B.Cu, 1.6 mm of FR4 away.
MODULE_GAPS = (
    # This fork's own wire pads, placed deliberately just clear of the body so the three
    # wires stay short (3.8 / 5.9 / 4.7 mm per ECO-6 §6.5). Tightest on the board, on purpose.
    ("TP83", "pad",   0.400),
    ("TP84", "pad",   0.400),
    ("TP85", "pad",   0.400),
    # MouseBiteLabs' parts. U2 is the RAM the window sits below -- a package edge, not a
    # hand-soldered joint, which is why 0.55 mm is acceptable here and would not be on a
    # part someone has to get an iron onto.
    ("U2",   "crtyd", 0.550),
    # C7 is the 0603 ECO-6 MOVES to open the window. This is the gap AFTER the move.
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

    # --- every via ECO-6 adds, against everything MouseBiteLabs already routed ----------
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
    # Found by the first assembled render (ECO-16): MouseBiteLabs' AGBM-02 parks an
    # unannotated HC49 crystal footprint -- ref "REF**", zero pads, a leftover reference for
    # the crystal option ECO-7 marks DNP -- at (8.89, -81.888), NINE MILLIMETRES above the
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
            + ". Update MODULE_GAPS and ECO-6 §6.6's clearance table in the same commit.")
    else:
        floor = min(d for _r, _bs, d in gaps)
        ok(f"MOD1 fits: {len(gaps)} same-side neighbour(s) all where the ledger says, "
           f"tightest {floor:.3f} mm ({gaps[0][0]}, {gaps[0][1]})")
        if floor < GAP_FLOOR:
            err(f"MOD1's tightest neighbour is {floor:.3f} mm, under the {GAP_FLOOR} mm "
                f"floor this project set for a module edge")

    # --- the fiducials have to be READABLE, which is a contrast problem ----------------
    fps = kisexp.by_ref(b)
    fids = sorted(r for r in fps if r.startswith("FID"))
    if not fids:
        err("no fiducials on the board -- ECO-6 adds six; a pick-and-place needs them")
        return
    problems = []
    for ref in fids:
        fp = fps[ref]
        if fp.at is None:
            problems.append(f"{ref}: no placement")
            continue
        if FIDUCIAL_PAD_CLEARANCE not in fp.body:
            problems.append(f"{ref}: no {FIDUCIAL_PAD_CLEARANCE} on its pad -- a re-pour "
                            f"will flood the mask window with GND")
        w = geom.worst(fp.at[0], fp.at[1], 0.0, [fp.layer], segs, vias, pads,
                       ignore=(f"{ref}.1",))
        if w and w[0][0] < FIDUCIAL_WINDOW:
            problems.append(f"{ref} at ({fp.at[0]},{fp.at[1]}): {w[0][0]:.3f} mm to "
                            f"{w[0][1]} -- inside its own {FIDUCIAL_WINDOW} mm mask window")
        else:
            note(f"{ref} ({fp.layer}): {w[0][0]:.3f} mm clear")
    if problems:
        err("fiducial(s) a vision system cannot read: " + "; ".join(problems))
    else:
        ok(f"all {len(fids)} fiducials clear of hard copper and their pours held back")


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
FILL_DOCS = ("clockxcontrol-integration/ECO-6_clockxcontrol_footprint.md",
             "clockxcontrol-integration/ECO-14_clock_domain_and_audit_fixes.md",
             "pcbway-assembly/README.md")

# The hazard set, snapshotted with a reason per line. Measured AT EACH PAD, on the layers
# that pad occupies, against that pad's own net -- see geom.swallowed(). Every entry here
# is a real net-to-net overlap in the shipped file that a re-pour removes.
FILL_HAZARD = (
    # C7 is MouseBiteLabs' part, not this fork's. ECO-6 MOVES it out of the module window,
    # and the spot it moves to puts its GND pad inside the VDD35 pour. A rule keyed on
    # "is this refdes new?" cannot see this line; that is why the key is geometry.
    ("C7.2",   "GND",       "VDD35"),
    # The two fiducials that sit on the GND pour. They are meant to -- a fiducial wants an
    # even background -- and the (clearance 0.55) override from ECO-14 §14.3 holds the
    # copper back so the mask window reads. Listed because they are still overlaps.
    ("FID1.1", "<netless>", "GND"),
    ("FID4.1", "<netless>", "GND"),
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
    # Every via ECO-6 adds. All nine, on the rails they cross.
    ("via (47.5,-59.5)",   "CXC_CLK",  "GND+VDD5"),
    ("via (55.15,-53.25)", "/CPU/TP9", "GND+VDD2+VDD3"),
    ("via (55.65,-49.65)", "/CPU/TP2", "GND+VDD3"),
    ("via (79.85,-41.1)",  "/CPU/TP2", "GND"),
    ("via (83.25,-39.6)",  "/CPU/TP9", "GND"),
    ("via (93.3,-38.7)",   "GND",      "VDD35"),
    ("via (97.1,-34.1)",   "VDD3",     "AGND+VAUD"),
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
    # The first version of this counted footprints whose REFDES was new, tested at the
    # footprint ORIGIN, on fp.layer, against the net of pad 1. Three approximations, and a
    # blind spot underneath them: a part MouseBiteLabs already had, which ECO-6 MOVED, has
    # an old refdes and new copper, so the rule skipped it. C7 is exactly that part, and at
    # the spot ECO-6 moved it to, C7.2 lands in the VDD35 pour. It reported 15; the truth
    # is 19. geom.swallowed() is now the one implementation, shared with the renderer.
    have = geom.swallowed(b, base)
    if set(have) != set(FILL_HAZARD):
        gone = sorted(set(FILL_HAZARD) - set(have))
        new_ = sorted(set(have) - set(FILL_HAZARD))
        err(f"the stale-fill hazard set has CHANGED ({len(FILL_HAZARD)} -> {len(have)}). "
            + (f"no longer swallowed: {gone}. " if gone else "")
            + (f"newly swallowed: {new_}. " if new_ else "")
            + "If copper moved, update FILL_HAZARD in the same commit and say why in the "
              "ECO. If the fill was re-poured, so should these documents be: "
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
# ECO-6 §6.6 said the views in render/ came from "a renderer built against the board file
# directly". That renderer was never committed, so what shipped was a set of PNGs with no
# generator. When ECO-13 rebased the fork from AGBM-01 onto AGBM-02, every render went on
# describing a board this repository no longer contains -- and nothing noticed, because
# their git blob SHAs were identical before and after. ECO-14 §14.5 caught it by hand.
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


def check_renders():
    print("[15] every render is what the committed board re-renders to")
    try:
        import render_board
        from PIL import Image
        import PIL
    except ImportError as e:
        warn(f"Pillow unavailable ({e}) -- check [15] did not run")
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
            + "ungenerated PNG is how the pre-rebase AGBM-01 images survived four ECOs")


# =====================================================================================
# [16] MouseBiteLabs' own part choices are read, and disagreeing with one is deliberate
# =====================================================================================
# Every symbol in the upstream schematic carries a (property "Source" ...) Digi-Key link.
# That link is the ONLY record of which part MouseBiteLabs actually picked for a generic
# value like "22u" -- the Value field is a symbol name, not an orderable code. scripts/
# link_mpn.json resolves those links.
#
# It was built from AGBM-01 and survived the ECO-13 rebase untouched: 30 of AGBM-02's 57
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
        # An ECO that CHANGES THE VALUE makes the link's part the wrong part by definition;
        # check [3] already ledgers every one of those, so this is not a sourcing decision.
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
           f"part it departs from; {revalued} more are value changes check [3] owns")


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
# ECO-9 the board asked a machine to buy and place the SALVAGED CPU, and `MOD1` sat in the
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
            f"{bom_split.STEM}-cpl.csv": bom_split._csv(
                cpl, ["ref", "value", "footprint", "x", "y", "rot", "layer"]),
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


def main():
    global verbose
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-v", "--verbose", action="store_true")
    verbose = ap.parse_args().verbose
    for fn in (check_reproducible, check_package_parity, check_library_footprint,
               check_eco8_ledger,
               check_dnp_ledger, check_bom_vs_board, check_supplier_pns,
               check_cited_paths, check_doc_imagery, check_module_window,
               check_blockers, check_structure, check_assembly_split,
               check_geometry, check_zone_fill, check_renders,
               check_upstream_links):
        fn()
    print(f"\n== {len(errors)} error(s), {len(warnings)} warning(s) ==")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
