#!/usr/bin/env python3
"""pack_board.py -- rebuild the deliverable package from the tree.

    python3 scripts/pack_board.py            # rebuild the zip
    python3 scripts/pack_board.py --check    # report what would change, write nothing

The package is a GENERATED ARTIFACT, not a hand-maintained one. Every file in it is a
copy of something in the tree, plus the board that `scripts/build_board.py` produces, so
the zip can never be a revision apart from what the repository says -- which is what
consistency check [2] asserts.

Zip archives are not byte-reproducible (member timestamps and the compressor's choices
both move), so this writes with a FIXED timestamp and deflate level. Two runs over an
unchanged tree therefore produce the same bytes, and `git status` stays quiet instead of
showing a zip that "changed" because it was rebuilt.
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_board                                               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CXC = os.path.join(ROOT, "clockxcontrol-integration")
ZIP = os.path.join(CXC, "board", "agbm-02-clockxcontrol.zip")
STEM = "agbm-02-clockxcontrol"
# A fixed DOS timestamp. Anything constant does; this is the ECO-6 landing date.
FIXED = (2026, 8, 18, 0, 0, 0)

MEMBERS = [
    ("ClockxControl_GBA_GBC.kicad_mod", "footprint/ClockxControl_GBA_GBC.kicad_mod"),
    ("README.md", "README.md"),
    ("DESIGN-DECISIONS.md", "DESIGN-DECISIONS.md"),
]


def contents():
    """{member name: bytes} -- everything the package should hold."""
    out = {}
    for member, rel in MEMBERS:
        out[f"{STEM}/{member}"] = open(os.path.join(CXC, rel), "rb").read()
    rdir = os.path.join(CXC, "render")
    for name in sorted(os.listdir(rdir)):
        if name.endswith(".png"):
            out[f"{STEM}/render/{name}"] = open(os.path.join(rdir, name), "rb").read()
    board, _st = build_board.build()
    out[f"{STEM}/AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb"] = board.encode("utf-8")
    # ECO-22: THE PROJECT FILE SHIPS WITH THE BOARD, because KiCad keeps the design rules
    # in the project and not in the .kicad_pcb. Open this board without it and KiCad falls
    # back to its own defaults -- which report ~710 violations on a board that has 204
    # against the rules it is actually designed to, because MouseBiteLabs sets silk_overlap,
    # silk_over_copper, text_height, lib_footprint_issues, lib_footprint_mismatch and
    # silk_edge_clearance to `ignore` and runs min_hole_to_hole at 0.5 rather than 0.25.
    # It is HIS file, taken from the base zip unmodified, so it cannot drift from the rules
    # check_drc.py gates against: both read the same bytes from the same place.
    import check_drc
    out[f"{STEM}/AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pro"] = check_drc.project_file().encode("utf-8")
    # ECO-23: the KiCad 10 companion ships beside the KiCad 9 board. KiCad 9 cannot open a
    # version-20260206 file at all ("Failed to load board"), and KiCad 10 opening the 9 file
    # would silently rewrite it on save -- so whichever KiCad the recipient has, one of these
    # two opens clean and untouched. Check [19] proves they are the same copper.
    import kicad10
    out[f"{STEM}/AGBM-02_AA_1-1_GBE-plus-CXC_kicad10.kicad_pcb"] = \
        open(kicad10.BOARD10, "rb").read()
    # ...with his rules under ITS stem too, or KiCad looks for a project that is not there
    # and falls back to defaults -- which is the whole failure ECO-22 was about.
    out[f"{STEM}/AGBM-02_AA_1-1_GBE-plus-CXC_kicad10.kicad_pro"] = \
        check_drc.project_file().encode("utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    want = contents()
    if a.check:
        try:
            z = zipfile.ZipFile(ZIP)
            have = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
        except OSError as e:
            sys.exit(f"FAIL: cannot read {ZIP}: {e}")
        added = sorted(set(want) - set(have))
        gone = sorted(set(have) - set(want))
        changed = sorted(n for n in set(want) & set(have) if want[n] != have[n])
        if not (added or gone or changed):
            print(f"ok: package matches the tree ({len(want)} members)")
            return 0
        for n in added:
            print(f"  + {n}")
        for n in gone:
            print(f"  - {n}")
        for n in changed:
            print(f"  ~ {n} ({len(have[n])} -> {len(want[n])} bytes)")
        sys.exit("FAIL: package is stale -- run scripts/pack_board.py")
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in sorted(want):
            info = zipfile.ZipInfo(name, date_time=FIXED)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, want[name])
    print(f"wrote {ZIP} ({len(want)} members, {os.path.getsize(ZIP)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
