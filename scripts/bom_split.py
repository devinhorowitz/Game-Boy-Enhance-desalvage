#!/usr/bin/env python3
"""bom_split.py -- split the design into the two buy documents an order actually needs.

    python3 scripts/bom_split.py                 # write them into Generated/fabdocs/
    python3 scripts/bom_split.py --check         # build in memory, report, write nothing
    python3 scripts/bom_split.py --boards 5      # quantities for a five-board run

WHY THIS EXISTS

A build of this board is two purchases that go to different places:

  1. THE ASSEMBLY BOM + CPL -> PCBWay. Everything the machine buys and places.
  2. THE HAND-BUY LIST -> your own cart. Everything else: the salvaged CPU and SRAM,
     the cartridge slot and link port and their 44 through-hole pins, the headphone
     jack, the speaker, the volume pot, and the ClockxControl module.

Before this, neither existed as a generated artifact, and the split lived in a prose
table in `pcbway-assembly/README.md`. That table was right, but nothing held the board to
it -- so the board still asked a pick-and-place to buy and place **the salvaged CPU**,
which nobody sells at any price, and five parts with through-hole pads.

WHERE THE TRUTH COMES FROM

Borrowed wholesale from SOLAR-GLOW's `scripts/bom_split.py`, including the rule that
matters most: **a part moves between the two documents by changing the DESIGN, never by
editing a list.** Classification is read off the board's own attributes --

    on board, not BOM-excluded, not DNP   ->  ASSEMBLY   (PCBWay buys and places it)
    on board, BOM-excluded, not DNP       ->  HAND-BUY   (you buy it and solder it)
    DNP, or a no-part footprint           ->  neither    (fiducials, jumpers, test pads)

-- and ECO-9 is what made those attributes true. The hand-solder set is itself derived:
any through-hole pad, plus the two salvage-only parts, which cannot be derived because a
salvaged QFP is byte-identical in the file to a new one. See `build_board.py`.

MPNs come from `pcbway-assembly/resolved-mpns.json`. Lines with no resolved MPN are
emitted with an empty MPN column and counted loudly, because an assembly BOM with holes
in it is not an order, and pretending otherwise is how you get a substitution desk
choosing your parts.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_board                                               # noqa: E402
import kisexp                                                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP = os.path.join(ROOT, "clockxcontrol-integration", "board", "agbm-01-clockxcontrol.zip")
MEMBER = "agbm-01-clockxcontrol/AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb"
MPNS = os.path.join(ROOT, "pcbway-assembly", "resolved-mpns.json")
OUTDIR = os.path.join(ROOT, "pcbway-assembly", "generated")
STEM = "agbm-01-cxc"

# --- footprints that are copper, not parts -------------------------------------------
# BOM-excluded but nothing to buy. Matched on the footprint LIBRARY NAME, so a new
# fiducial or test pad is classified correctly without touching this file.
NO_PART_FAMILIES = {
    "Fiducial": "optical alignment target -- copper and mask, no part",
    "TestPoint": "bare pad for a probe",
    "SolderJumper": "copper, closed with solder",
    "LOGO": "silkscreen artwork",
}

# --- things with no footprint at all --------------------------------------------------
# The exclusion-ledger shape: anything here is hand-maintained, so each line needs a
# reason. It is EMPTY on purpose. Every item this build needs that is not on the board --
# the shell, the screen kit, the battery contacts if you fit them -- is a choice the
# builder makes, not a design output, and inventing sourcing for parts nobody has picked
# would be worse than an empty table. The ClockxControl is NOT here: MOD1 is a real
# footprint carrying `exclude_from_bom`, so it derives into the hand-buy list like
# everything else.
OFF_BOARD = []


def _mpn_index():
    """{refdes: entry} from resolved-mpns.json."""
    try:
        entries = json.load(open(MPNS, encoding="utf-8"))["entries"]
    except (OSError, ValueError, KeyError):
        return {}
    idx = {}
    for e in entries:
        for ref in e["refs"]:
            idx[ref] = e
    return idx


def classify(fp):
    """'assembly' | 'hand' | 'none', and why."""
    if fp.dnp:
        return "none", "DNP"
    fam = fp.name.split(":")[-1]
    for key, why in NO_PART_FAMILIES.items():
        if key.lower() in fam.lower():
            return "none", why
    if fp.bom_excluded:
        # The reason lives in ECO-9's tables, in the generator, so the buy document and
        # the board's flags cannot give different accounts of the same decision.
        why = (build_board.SALVAGE_ONLY.get(fp.ref)
               or build_board.THRU_HOLE_REASONS.get(fp.ref)
               or ("ClockxControl mezzanine -- its plated holes are filled with solder "
                   "from above onto the pads below; no pick-and-place does that"
                   if fp.ref == "MOD1" else
                   "BOM-excluded on the board with no ECO-9 reason -- add one"))
        return "hand", why
    return "assembly", ""


def build(boards=1, board=None):
    """(assembly, hand, none, cpl, problems) -- the whole split, as plain dicts.

    `board` overrides the shipped board with an in-memory one. Only scripts/test_checks.py
    uses it, to prove check [12] can actually fail.
    """
    if board is None:
        board = kisexp.load(f"{ZIP}::{MEMBER}")
    idx = _mpn_index()
    rows = {"assembly": {}, "hand": {}, "none": {}}
    cpl, problems = [], []

    for fp in kisexp.footprints(board):
        if "*" in fp.ref or fp.ref == "?":
            continue
        kind, why = classify(fp)
        e = idx.get(fp.ref, {})
        key = (fp.value, fp.name, e.get("mpn", ""))
        row = rows[kind].setdefault(key, {
            "refs": [], "value": fp.value, "footprint": fp.name,
            "mpn": e.get("mpn", ""), "mfr": e.get("mfr", ""),
            "status": e.get("status", ""), "stock": e.get("stock", ""),
            "note": e.get("eco", "") or e.get("flag", "") or why,
        })
        row["refs"].append(fp.ref)

        if kind == "assembly":
            if not e.get("mpn"):
                row["unresolved"] = True
            if fp.at is None:
                problems.append(f"{fp.ref}: no placement -- cannot go in the CPL")
            else:
                cpl.append({"ref": fp.ref, "value": fp.value, "footprint": fp.name,
                            "x": round(fp.at[0], 4), "y": round(fp.at[1], 4),
                            "rot": round(fp.at[2], 2),
                            "layer": "top" if fp.layer == "F.Cu" else "bottom"})
        # A part a machine is asked to PLACE but not to BUY is a consignment, and this
        # board has none -- so if one appears it is almost certainly a mistake.
        if kind == "hand" and fp.placed:
            problems.append(f"{fp.ref}: hand-buy but still in the position file -- the "
                            f"machine will try to place a part it was never sold")

    out = {}
    for kind in rows:
        out[kind] = sorted(
            ({**r, "refs": sorted(r["refs"]),
              "qty": len(r["refs"]) * boards} for r in rows[kind].values()),
            key=lambda r: (r["refs"][0][:2], len(r["refs"]), r["refs"][0]))
    for item in OFF_BOARD:
        out["hand"].append({**item, "qty": item["qty"] * boards})
    return out["assembly"], out["hand"], out["none"], cpl, problems


_FIELDS = ["refs", "qty", "value", "mpn", "mfr", "footprint", "status", "stock", "note"]


def _csv(rows, fields=_FIELDS):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        row = dict(r)
        if isinstance(row.get("refs"), list):
            row["refs"] = " ".join(row["refs"])
        w.writerow(row)
    return buf.getvalue()


def _handbuy_md(hand, boards):
    L = [f"# Hand-buy list — {STEM}",
         "",
         "**Generated by `scripts/bom_split.py`. Do not edit.** Every line is here because",
         "the board says so: `exclude_from_bom` and not DNP. A part moves onto or off this",
         "list by changing the design — see [ECO-9](../clockxcontrol-integration/"
         "ECO-9_assembly_split.md).",
         "",
         f"Quantities are for **{boards} board(s)**.",
         "",
         "| Refs | Qty | Value | MPN | Manufacturer | Why it is not on the assembly line |",
         "|---|---|---|---|---|---|"]
    for r in hand:
        L.append(f"| `{' '.join(r['refs'])}` | {r['qty']} | {r['value']} | "
                 f"{r['mpn'] or '—'} | {r['mfr'] or '—'} | {r['note'] or '—'} |")
    L += ["", "## What this list is not", "",
          "It does not include the shell, the screen kit, the battery contacts or the",
          "cartridge you intend to play. Those are build choices, not design outputs, and",
          "`OFF_BOARD` in the generator is empty on purpose rather than carrying invented",
          "sourcing for parts nobody has picked yet.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="build and report; write nothing")
    ap.add_argument("--boards", type=int, default=1)
    a = ap.parse_args()

    asm, hand, none, cpl, problems = build(a.boards)
    print(f"assembly : {len(asm):3d} lines, {sum(r['qty'] for r in asm):4d} parts "
          f"-> PCBWay buys and places")
    print(f"hand-buy : {len(hand):3d} lines, {sum(r['qty'] for r in hand):4d} parts "
          f"-> your cart, your iron")
    print(f"neither  : {len(none):3d} lines, {sum(r['qty'] for r in none):4d} footprints "
          f"-> DNP, fiducials, jumpers, test pads")
    print(f"CPL      : {len(cpl):3d} placements")
    unresolved = [r for r in asm if r.get("unresolved")]
    if unresolved:
        n = sum(r["qty"] for r in unresolved)
        print(f"\n{len(unresolved)} of {len(asm)} assembly lines ({n} of "
              f"{sum(r['qty'] for r in asm)} parts) have NO RESOLVED MPN. An assembly BOM "
              f"with holes in it is not an order -- a substitution desk would be choosing "
              f"your parts:")
        for r in unresolved[:10]:
            print(f"   {r['value']:12s} x{r['qty']:<3d} {' '.join(r['refs'][:8])}"
                  + (" ..." if len(r["refs"]) > 8 else ""))
        if len(unresolved) > 10:
            print(f"   ... and {len(unresolved) - 10} more lines")
    for p in problems:
        print("   PROBLEM: " + p)

    if a.check:
        return 1 if problems else 0

    os.makedirs(OUTDIR, exist_ok=True)
    writes = {
        f"{STEM}-pcbway-assembly.csv": _csv(asm),
        f"{STEM}-handbuy.csv": _csv(hand),
        f"{STEM}-handbuy.md": _handbuy_md(hand, a.boards),
        f"{STEM}-cpl.csv": _csv(cpl, ["ref", "value", "footprint",
                                      "x", "y", "rot", "layer"]),
        f"{STEM}-not-populated.csv": _csv(none),
    }
    for name, text in writes.items():
        with open(os.path.join(OUTDIR, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print(f"  wrote {os.path.relpath(os.path.join(OUTDIR, name), ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
