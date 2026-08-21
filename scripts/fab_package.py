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
    ORDER.txt        stackup, thickness, layer count and the things a human has to tell them

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
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom                                                      # noqa: E402
import render_assembled as R                                     # noqa: E402
import render_board as _rb                                       # noqa: E402
import kisexp                                                    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "clockxcontrol-integration" / "board" / "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb"
GEN = ROOT / "pcbway-assembly" / "generated"
OUT = ROOT / "pcbway-assembly" / "fab" / "agbm-02-cxc-pcbway.zip"
MANIFEST = ROOT / "pcbway-assembly" / "fab" / "fab-manifest.json"

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

BOARD
  Outline ............... in Edge.Cuts. It includes 13 shell holes and two routed openings
                          INSIDE footprints (SW1's switch shaft, VR2's wheel), so the
                          router has to follow Edge.Cuts, not the bounding box
  Castellations ......... none
  Edge plating .......... none

GERBERS ({len(gerbers)} files, RS-274X, 6-digit, Protel extensions)
  .GTL / .G1 / .G2 / .GBL ... copper, top to bottom
  .GTS / .GBS ............... solder mask
  .GTO / .GBO ............... silkscreen
  .GTP / .GBP ............... solder paste (stencil)
  .GM1 ...................... board outline (Edge.Cuts)

DRILL ({len(drills)} files, Excellon, millimetres)
  PTH and NPTH are SEPARATE files. The NPTH file is not optional -- it carries the shell
  mounting holes.

ASSEMBLY
  Side .................. both. The fine-pitch work is on the BACK.
  Placements ............ {n_cpl}   (assembly/agbm-02-cxc-cpl.csv)
  BOM lines ............. {n_bom}   (assembly/agbm-02-cxc-bom.csv)
  Do not populate ....... {n_dnp} lines (assembly/agbm-02-cxc-do-not-populate.csv)
  Rotation .............. KiCad convention, byte-identical to `kicad-cli pcb export pos`.
                          Origin is the lower-left corner of the outline, X right, Y up.

THINGS A HUMAN HAS TO TELL THEM
  1. CP1, CP2 and CP3 are POLARISED TANTALUMS ON A SYMMETRIC LAND WITH NO POLARITY MARK
     anywhere on the board. If the line reads the rotation wrong, all three go in backwards
     and nothing on the board says so. Confirm orientation before the run.
  2. Parts on the do-not-populate list are not all jumpers and test pads. P1 (cartridge
     slot) and P4 (link port) are real parts the builder fits by hand afterwards.
  3. U1's land takes a SALVAGED AGB CPU and is not on the BOM at all, because no
     distributor sells one. U2 is an ordinary orderable part and is on the BOM.
  4. Two solder jumpers (JP2, JP3) are closed by hand after assembly, and only if the
     CY62157EV30LL is fitted. Leave them open otherwise.

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


def write_zip(members: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for k in sorted(members):
            zi = zipfile.ZipInfo(k, date_time=(2026, 8, 21, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, members[k])


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
        print(f"ok: the shipped package is what this board plots to ({len(have)} members, "
              f"content {d})")
        return 0
    write_zip(members, OUT)
    MANIFEST.write_text(json.dumps(
        {"content": d,
         "members": sorted(members),
         "source": _rb.source_digest(kisexp.load(str(BOARD)), geom.base()),
         "kicad": subprocess.run(["kicad-cli", "version"], capture_output=True,
                                 text=True).stdout.strip()},
        indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes, "
          f"{len(members)} members, content {d})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
