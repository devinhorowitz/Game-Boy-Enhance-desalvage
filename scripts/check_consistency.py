#!/usr/bin/env python3
"""check_consistency.py -- drift guard for the AGBM-01 ClockxControl fork.

    python3 scripts/check_consistency.py          # run every check
    python3 scripts/check_consistency.py -v       # also print what each check saw

Cross-checks the documents against the board they describe, so a change to one that is
not mirrored in the other fails loudly instead of rotting.

  [1]  REPRODUCIBLE   -- scripts/build_board.py rebuilds the shipped board byte-for-byte
                         from the committed ECO-5 base.                     [ERROR]
  [2]  PACKAGE PARITY -- every document inside the shipped zip is byte-identical to its
                         copy in the tree.                                  [ERROR]
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
  [10] BLOCKER LEDGER -- the two ECO-7 blockers are still open, exactly as documented.
                         GOES RED WHEN THEY ARE FIXED -- see the check.     [ERROR]
  [11] STRUCTURE      -- the board parses, parens balance, no duplicate refdes. [ERROR]
  [12] ASSEMBLY SPLIT -- nothing reaches the pick-and-place without a BOM line to buy it,
                         nothing is on both buy documents, and the generated buy documents
                         are what a fresh run produces.                     [ERROR]

Exit: nonzero if any ERROR-level check fails. Warnings do not fail the build.
Needs: python3 and the standard library. Nothing else -- no KiCad, no pip, no container.

WHERE THIS CAME FROM

The shape is borrowed wholesale from SOLAR-GLOW's `scripts/check_consistency.py`: numbered
checks, an `err`/`warn`/`ok` accumulator, and -- the part that actually matters -- the
EXCLUSION-LEDGER DISCIPLINE. Where there is no second source of truth to compare against,
the check carries a SNAPSHOT with a reason on every line. A deliberate change updates the
snapshot in the same commit; an undeliberate one stops being invisible. Checks [4], [9]
and [10] are that shape.

Check [10] is the sharper version of it, also borrowed: a check that goes RED WHEN THE BUG
IS FIXED. ECO-7 documents two unrouted nets as blockers. When someone routes them, the
board and the document disagree -- and the check fails, forcing the document to be
corrected in the same commit that fixes the board. A blocker that gets quietly fixed and
leaves its scary paragraph behind is how a repository starts lying about itself.
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
ZIP = os.path.join(ROOT, "clockxcontrol-integration", "board", "agbm-01-clockxcontrol.zip")
ZIP_ROOT = "agbm-01-clockxcontrol"
BOARD_MEMBER = f"{ZIP_ROOT}/AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb"
MPNS = os.path.join(ROOT, "pcbway-assembly", "resolved-mpns.json")
ECO8_DOC = os.path.join(ROOT, "clockxcontrol-integration", "ECO-8_component_swaps.md")
ECO10_DOC = os.path.join(ROOT, "clockxcontrol-integration", "ECO-10_precision_pass.md")
ECO11_DOC = os.path.join(ROOT, "clockxcontrol-integration", "ECO-11_gate_drive_and_D1.md")

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
    for label, doc_path, gen in (("ECO-8", ECO8_DOC, build_board.ECO8),
                                 ("ECO-10", ECO10_DOC, build_board.ECO10),
                                 ("ECO-11", ECO11_DOC, build_board.ECO11)):
        _check_one_eco(label, doc_path, gen)


# An ECO document records the change IT made and is not wrong when a later ECO moves the
# same part again -- ECO-8 took R23 to 1.69M and ECO-10 then took that to 169k, and both
# statements are true. So each ECO's table is checked against its own generator list, and
# the BOARD is checked only against where the whole chain ends up.
def _eco_chain_final():
    out = {}
    for lst in (build_board.ECO8, build_board.ECO10, build_board.ECO11):
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
BASE_ZIP_REF = "agbm-01-ram-desalvage.zip::agbm-01-ram-desalvage/AGBM-01_AA_1-2_GBE-plus.kicad_pcb"


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
    r"^AGB-(SRAM|CPU)$": "salvaged part, no orderable number",
}

# Pairs where the Value and the MPN deliberately differ AND the difference is a KNOWN,
# TRACKED DEFECT rather than a naming convention. Each names where it is tracked, and the
# check asserts that the tracking document still says so -- a ledger entry that outlives
# its tracking is the silence this whole file exists to prevent. Fix the board and the
# entry goes stale, which the check also reports.
KNOWN_DEFECT_PNS = {
    ("CSS-1310B", "CSS-1310TB"):
        ("SW1's schematic Value is an incomplete Nidec ordering code; the orderable part "
         "is CSS-1310TB. Tracked in pcbway-assembly/README.md as a BOM defect to fix "
         "before an order.", "pcbway-assembly/README.md", "CSS-1310TB"),
    # Found 2026-08-19 by the MPN resolution, and predicted before that by the power
    # review's verifier: "the BOM value strings '2N3904'/'2N3906' on SOT-23 pads are
    # themselves a part-number/package mismatch nobody flagged." 2N3904 and 2N3906 are
    # TO-92 part numbers. There is no 2N3904 in SOT-23 -- the SOT-23 part is MMBT3904,
    # which is exactly what the schematic's own Digi-Key link buys. The Value is wrong and
    # the link is right, the same shape as SW1 and P3.
    ("2N3904", "MMBT3904LT1G"):
        ("Q1's board Value is the TO-92 part number on SOT-23 pads. The schematic's link "
         "buys MMBT3904LT1G, which is the SOT-23 part. Tracked in "
         "pcbway-assembly/README.md.", "pcbway-assembly/README.md", "MMBT3904LT1G"),
    ("2N3906", "MMBT3906LT1G"):
        ("Q3's board Value is the TO-92 part number on SOT-23 pads. The schematic's link "
         "buys MMBT3906LT1G, which is the SOT-23 part. Tracked in "
         "pcbway-assembly/README.md.", "pcbway-assembly/README.md", "MMBT3906LT1G"),
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
    bad, ledgered, matched, defects = [], 0, 0, 0
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
        if (val, mpn) in KNOWN_DEFECT_PNS:
            why, doc, token = KNOWN_DEFECT_PNS[(val, mpn)]
            try:
                tracked_still = token in open(os.path.join(ROOT, doc), encoding="utf-8").read()
            except OSError:
                tracked_still = False
            if tracked_still:
                warn(f"{e['refs']}: KNOWN OPEN DEFECT -- {why}")
                defects += 1
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
           f"{defects} known open defect(s)")


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
    "AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb":
        "the deliverable board -- inside clockxcontrol-integration/board/"
        "agbm-01-clockxcontrol.zip, and rebuildable with scripts/build_board.py. Cited by "
        "basename throughout the ECOs because that is its name inside the package",
    "AGBM-01_AA_1-2_GBE-plus.kicad_pcb":
        "the ECO-5 base board -- inside agbm-01-ram-desalvage.zip at the repo root",
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
    orphan = sorted(f for f in files
                    if f.startswith("clockxcontrol-integration/render/")
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
    "FID2": (106.25, -57.25, "fiducial pair moved out from under the module"),
    "FID5": (106.25, -57.25, "same pair"),
    "MOD1": (91.95, -44.95, "module centre, rev B -- shifted west out of the R3/TP114 "
                            "cluster; ECO-6 section 6.7 is what that cost"),
    "TP83": (97.9, -37.95, "CLK wire pad. y is -37.95 and not -38.6: KiCad's y grows "
                           "DOWNWARD, and at -38.6 the 1.2 mm pad overlaps the module "
                           "body by 0.25 mm at its radius"),
    "TP84": (99.45, -37.95, "V+ wire pad"),
    "TP85": (101.0, -37.95, "V- wire pad"),
    "JP3":  (45.0, -64.2, "CK1 isolation jumper -- OPEN for a crystal build, BRIDGED for "
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
                "clockxcontrol-integration/ECO-8_component_swaps.md",
                "power-review/README.md",
                "pcbway-assembly/README.md")
STOCK_REF = ("AGBM-01 (AA Batteries)/AGBM-01_Design Files.zip", "AGBM-01_AA_1-2.kicad_pcb")


def check_blockers():
    print("[10] the two ECO-7 blockers are still open (RED means they were FIXED)")
    b = board()
    nets = kisexp.net_table(b)
    if nets.get(VDD2_NET) != "VDD2":
        err(f"net {VDD2_NET} is {nets.get(VDD2_NET)!r}, not VDD2 -- this check's "
            f"assumption moved; re-derive it before trusting anything below")
        return

    # --- blocker 1: U2 pin 37 has no path to VDD2 ---------------------------------
    east = [(x, y) for x, y, n in kisexp.vias(b) if n == VDD2_NET and x > VDD2_EAST_LIMIT]
    if east:
        err(f"U2 PIN 37 MAY NOW HAVE A SUPPLY: {len(east)} VDD2 via(s) east of "
            f"x={VDD2_EAST_LIMIT} ({', '.join(f'({x},{y})' for x, y in east[:4])}). ECO-7 "
            f"says there are none. If you routed it, that is good news -- now correct the "
            f"blocker sections in: " + ", ".join(BLOCKER_DOCS))
    else:
        ok(f"U2 pin 37 still unsupplied -- no VDD2 via east of x={VDD2_EAST_LIMIT}")

    # --- blocker 2: Net-(Q5B-G) is routed, but in two pieces ----------------------
    num = next((n for n, nm in nets.items() if nm == BROKEN_NET), None)
    if num is None:
        err(f"{BROKEN_NET} is not in the board's net table any more -- ECO-7 describes it")
        return
    islands = sorted(kisexp.net_islands(b, num), key=len)
    if islands == sorted(BROKEN_ISLANDS, key=len):
        ok(f"{BROKEN_NET} still broken into {len(islands)} islands "
           f"({' | '.join(', '.join(i) for i in islands)}) -- the via at "
           f"{MISSING_VIA} is still absent")
    elif len(islands) == 1:
        err(f"{BROKEN_NET} IS NOW WHOLE ({', '.join(islands[0])}). ECO-7 says the "
            f"supervisor cannot reach Q5B's gate and the low-battery LED is dead. If you "
            f"fixed it, correct the blocker sections in: " + ", ".join(BLOCKER_DOCS))
    else:
        err(f"{BROKEN_NET} is broken differently than ECO-7 records: "
            f"{[list(i) for i in islands]} instead of {BROKEN_ISLANDS}. Re-derive the "
            f"blocker before trusting the documents.")

    # The reference this fork diverged from. Diffing against it is what turned "the net
    # is open" into "ECO-5 deleted one via at a known coordinate", so the check keeps the
    # comparison rather than trusting the conclusion.
    zpath = os.path.join(ROOT, STOCK_REF[0])
    if not os.path.exists(zpath):
        warn(f"stock board not in the tree ({STOCK_REF[0]}) -- the divergence half of "
             f"this check did not run")
        return
    try:
        stock = kisexp.load(f"{zpath}::{STOCK_REF[1]}")
        s_num = next(n for n, nm in kisexp.net_table(stock).items() if nm == BROKEN_NET)
        s_islands = kisexp.net_islands(stock, s_num)
        s_vias = [(x, y) for x, y, n in kisexp.vias(stock) if n == s_num]
    except Exception as e:                                        # noqa: BLE001
        warn(f"could not read the stock board: {type(e).__name__}: {e}")
        return
    if len(s_islands) != 1:
        err(f"the STOCK MouseBiteLabs board also has {BROKEN_NET} in {len(s_islands)} "
            f"pieces -- ECO-7 blames ECO-5 for the break, and that would be wrong")
    elif MISSING_VIA not in [(round(x, 4), round(y, 4)) for x, y in s_vias]:
        err(f"the stock board has no via at {MISSING_VIA} either -- the documented cause "
            f"of the break does not hold; re-derive it")
    else:
        ok(f"stock board has {BROKEN_NET} whole with a via at {MISSING_VIA}; this fork "
           f"does not -- the break is ECO-5's, exactly as ECO-7 records")


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
    for fn in (check_reproducible, check_package_parity, check_eco8_ledger,
               check_dnp_ledger, check_bom_vs_board, check_supplier_pns,
               check_cited_paths, check_doc_imagery, check_module_window,
               check_blockers, check_structure, check_assembly_split):
        fn()
    print(f"\n== {len(errors)} error(s), {len(warnings)} warning(s) ==")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
