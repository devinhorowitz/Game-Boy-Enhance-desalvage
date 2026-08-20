#!/usr/bin/env python3
"""check_drc.py -- run KiCad's own DRC on a re-poured copy, and diff it against the base.

    python3 scripts/check_drc.py            # full report
    python3 scripts/check_drc.py --quiet    # just the verdict
    python3 scripts/check_drc.py --json OUT # keep the raw reports

WHY A DIFF AND NOT A COUNT

MouseBiteLabs' own AGBM-02, re-poured and run through the same DRC, has 695 violations and
0 unconnected items. Most are silkscreen overlaps and footprint-library nits on a design
that is hand-built and has never needed to be DRC-clean. A gate that demanded zero would
fail on his board before it ever looked at ours, and would be switched off within a week.

So the question this asks is the only one that is actually about this fork: **what does our
copper add that his does not have?** Every violation is fingerprinted by type and position,
the base's multiset is subtracted, and what remains is ours.

WHY IT HAS TO RE-POUR FIRST

The committed board carries MouseBiteLabs' stored fill, from before this fork added any
copper -- check [14] exists to say so. DRC on that fill would report the board as it cannot
be built. The copy is re-poured with pcbnew, exactly as ECO-16's renders are, and the
committed board stays stale on purpose.

WHAT THIS FOUND THAT NOTHING ELSE COULD

Check [13] measures copper-to-copper distance and knows nothing about keepout zones,
board-edge rules, soldermask bridging, or whether a pour still REACHES a pad. This board has
64 mechanical keepout zones. The first run turned up two defects that had been shipping:

  * the six fiducials ECO-14 placed sit on a battery terminal, in shell holes and inside
    keepout zones -- placed by a search that only knew about hard copper;
  * U1 pad 39 [GND] has no ground connection at all, because ECO-6's /CPU/TP8 route runs
    0.3594 mm from its copper where a pour sliver needs 0.400 to survive.

ECO-20 fixed both, so both are gone from the ledger below -- and the ledger is written so
that a FIX breaks the check just as loudly as a regression: leave a line in after the
violation stops happening and the run fails with "0 new, ledger says N -- FIXED? remove its
line". That is deliberate. The dangerous state for a file like this is a stale entry that
quietly excuses something nobody has looked at in months.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geom                                                      # noqa: E402
import render_assembled as R                                     # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Violations this fork adds and has not yet fixed, each with the reason it is still here.
# A fingerprint is (type, x-tuple, y-tuple) -- position, so a fix has to move the thing
# rather than renumber it. Fix one and this file must lose its line in the same commit.
KNOWN_NEW = {
    "courtyards_overlap": (
        1, "ECO-19: C7A's courtyard overlaps MOD1's body BY DESIGN. The stock C7 land is "
           "restored inside the module window, DNP, so mods that solder to C7 where "
           "MouseBiteLabs has always kept it still have their landmark. Exactly one of "
           "C7 / C7A is ever populated."),
}
# ECO-22 EMPTIED THE REST OF THIS TABLE, and not by fixing 53 things. Four lines here --
# silk_overlap 25, silk_over_copper 12, lib_footprint_issues 11, text_height 6 -- were
# never violations of this board's rules at all. They were violations of KiCad's DEFAULT
# rules, which is what ran because drc() wrote the board into a directory with no project
# file. MouseBiteLabs sets all four to `ignore` in the .kicad_pro he has shipped since
# AGBM-01. Reading his project instead of guessing at it took the fork's contribution from
# "55 new violations" to ONE, and that one is deliberate.
# MouseBiteLabs' board has 0 unconnected items and so, since ECO-20, does this one. An
# entry here is an unconnected pad this fork is choosing to live with; there are none.
KNOWN_UNCONNECTED: dict[str, str] = {}


def project_file() -> str:
    """MouseBiteLabs' own .kicad_pro, out of the base zip.

    THE SINGLE MOST CONSEQUENTIAL LINE IN THIS FILE, AND IT WAS MISSING UNTIL ECO-22.
    KiCad reads its design rules from the PROJECT, not the board. This function used to
    write the board into an empty temp directory, so every run silently fell back to
    KiCad's built-in defaults -- a different rule set from the one the board is designed
    to, in both directions:

        rule                     his .kicad_pro   KiCad default   effect of getting it wrong
        min_hole_to_hole              0.5              0.25       hid a real drill collision
        min_clearance                 0.15             0.0
        min_track_width               0.1525           0.2
        min_via_diameter              0.4              0.5
        silk_overlap             IGNORE           warning         199 phantom violations
        lib_footprint_issues     IGNORE           warning         199 phantom violations
        text_height              IGNORE           warning          40 phantom violations
        silk_over_copper         IGNORE           warning          39 phantom violations

    Under the defaults this fork looked like it added 55 violations to a 695-violation
    board. Under the rules the board is actually designed to, MouseBiteLabs' AGBM-02 has
    203 and this fork has 204 -- and the one it adds is ECO-19's deliberate C7A courtyard.
    The 489-violation difference is almost entirely checks HE TURNED OFF.
    """
    with zipfile.ZipFile(ROOT / "AGBM-02 (AA Batteries)" / "AGBM-02 Design Files.zip") as z:
        return z.read("AGBM-02 Design Files/AGBM-02_AA_1-1.kicad_pro").decode("utf-8")


def drc(board_text: str, tag: str, keep: Path | None = None) -> dict:
    """Re-pour a throwaway copy of `board_text` and return KiCad's DRC report."""
    with tempfile.TemporaryDirectory() as td:
        pcb = Path(td) / f"{tag}.kicad_pcb"
        pcb.write_text(board_text, encoding="utf-8", newline="")
        # The project has to sit beside the board and share its stem, or KiCad ignores it.
        (Path(td) / f"{tag}.kicad_pro").write_text(project_file(), encoding="utf-8",
                                                   newline="")
        R.refill_zones(pcb)
        out = Path(td) / f"{tag}.json"
        r = subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json",
                            "--severity-all", "-o", str(out), str(pcb)],
                           capture_output=True, text=True)
        if not out.exists():
            raise RuntimeError((r.stderr or r.stdout).strip()[-300:])
        rep = json.loads(out.read_text(encoding="utf-8"))
    if keep:
        keep.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    return rep


def fingerprint(v: dict) -> tuple:
    items = v.get("items", [])[:2]
    return (v["type"],
            tuple(round(i["pos"]["x"], 2) for i in items),
            tuple(round(i["pos"]["y"], 2) for i in items))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--json", metavar="DIR", help="keep the raw DRC reports here")
    a = ap.parse_args()

    import shutil
    if not shutil.which("kicad-cli"):
        print("check_drc: kicad-cli not found -- needs KiCad 9. NOT RUN.", file=sys.stderr)
        return 2
    try:
        import pcbnew                                             # noqa: F401
    except ImportError:
        print("check_drc: the pcbnew module is missing, so the copy cannot be re-poured. "
              "DRC on the stored fill would describe a board that cannot be built. NOT RUN.",
              file=sys.stderr)
        return 2

    keep = Path(a.json) if a.json else None
    if keep:
        keep.mkdir(parents=True, exist_ok=True)
    ours = drc(R.BOARD.read_text(encoding="utf-8"), "ours",
               keep / "drc_ours.json" if keep else None)
    base = drc(geom.base(), "base", keep / "drc_base.json" if keep else None)

    fb = Counter(fingerprint(v) for v in base["violations"])
    seen, new = Counter(), []
    for v in ours["violations"]:
        k = fingerprint(v)
        seen[k] += 1
        if seen[k] > fb.get(k, 0):
            new.append(v)
    by_type = Counter(v["type"] for v in new)

    base_un = {u["items"][0]["description"].split(" on ")[0]
               for u in base.get("unconnected_items", []) if u.get("items")}
    new_un = [u for u in ours.get("unconnected_items", [])
              if u.get("items")
              and u["items"][0]["description"].split(" on ")[0] not in base_un]

    print(f"MouseBiteLabs' AGBM-02, re-poured : {len(base['violations']):4d} violations, "
          f"{len(base.get('unconnected_items', [])):2d} unconnected")
    print(f"this fork, re-poured             : {len(ours['violations']):4d} violations, "
          f"{len(ours.get('unconnected_items', [])):2d} unconnected")
    print(f"NEW, at positions his board does not have: {len(new)} violation(s), "
          f"{len(new_un)} unconnected\n")

    bad = []
    for t, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
        want, why = KNOWN_NEW.get(t, (0, ""))
        mark = "ok " if n == want else "!! "
        if n != want:
            bad.append(f"{t}: {n} new, ledger says {want}")
        if not a.quiet:
            print(f"  {mark}{n:4d}  {t}")
            if why:
                for line in (why[i:i + 84] for i in range(0, len(why), 84)):
                    print(f"          {line}")
    for t, (want, _why) in KNOWN_NEW.items():
        if t not in by_type and want:
            bad.append(f"{t}: 0 new, ledger says {want} -- FIXED? remove its line")

    if not a.quiet:
        print()
    for u in new_un:
        who = u["items"][0]["description"].split(" on ")[0]
        why = KNOWN_UNCONNECTED.get(who)
        print(f"  {'ok ' if why else '!! '}unconnected: {who}")
        if why and not a.quiet:
            print(f"          {why}")
        if not why:
            bad.append(f"unconnected item not in the ledger: {who}")
    for who in KNOWN_UNCONNECTED:
        if not any(u["items"][0]["description"].startswith(who) for u in new_un):
            bad.append(f"unconnected {who} is GONE -- fixed? remove its line")

    print()
    if bad:
        print("DRC LEDGER MISMATCH:", file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        return 1
    print(f"ok: every new violation and unconnected item is ledgered "
          f"({len(new)} violation(s), {len(new_un)} unconnected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
