#!/usr/bin/env python3
"""test_checks.py -- prove the drift guard can actually fail.

    python3 scripts/test_checks.py

A check that has never gone red is not known to work; it may be reading nothing, matching
nothing, or looking at the wrong file. That is not hypothetical here -- while this suite
was being written, `kisexp` parsed the upstream board to ZERO footprints (CRLF, and every
matcher anchors on "\\n\\t"), and every check reading it passed vacuously while producing a
confident wrong conclusion. SOLAR-GLOW's check [20] guards against the same thing by
re-classifying its own historical failures every run and failing if either stops going red.

Each case below mutates the board IN MEMORY, runs one check against the mutation, and
asserts the check errors. Nothing on disk is touched.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_consistency as cc                                   # noqa: E402

VIA_AT_THE_BREAK = (
    '\n\t(via\n\t\t(at 100.8 -62.15)\n\t\t(size 0.7)\n\t\t(drill 0.3)\n'
    '\t\t(layers "F.Cu" "B.Cu")\n\t\t(net 225)\n'
    '\t\t(uuid "00000000-0000-0000-0000-000000000000")\n\t)')


def _run(fn, board):
    cc.errors.clear()
    cc.warnings.clear()
    cc._board_cache["b"] = board
    with contextlib.redirect_stdout(io.StringIO()) as s:
        fn()
    return list(cc.errors), s.getvalue()


def main():
    good = cc.board()
    # the final Value of the first ref the ECO chain touches -- whatever it is today
    import build_board
    chain = {r: n for lst in (build_board.ECO8, build_board.ECO10)
             for r, f, _o, n in lst if f == "Value"}
    VICTIM = chain["R23"]
    k = good.rstrip().rfind("\n)")
    m = re.search(r'\(footprint "[^"]+"\n\t\t\(layer "F\.Cu"\)\n\t\t\(uuid "[^"]+"\)\n'
                  r'\t\t\(at ([-\d.]+) ([-\d.]+)', good)

    cases = [
        # The mutated value is pulled from the generator rather than typed here, so an ECO
        # that moves a part cannot silently turn these cases into no-ops. Two of them did
        # exactly that when ECO-10 rescaled R23 from 1.69M to 169k, and the "BLIND" guard
        # below is what said so.
        ("[1]  a hand-edited board no longer rebuilds",
         cc.check_reproducible,
         good.replace(f'(property "Value" "{VICTIM}"', '(property "Value" "12345"', 1)),
        ("[3]  an ECO table and the board disagree",
         cc.check_eco8_ledger,
         good.replace(f'(property "Value" "{VICTIM}"', '(property "Value" "12345"', 1)),
        ("[4]  a stray DNP flag",
         cc.check_dnp_ledger,
         good.replace("(attr smd)", "(attr smd dnp)", 1)),
        ("[5]  the board's Value drifts from the buy list",
         cc.check_bom_vs_board,
         good.replace('(property "Value" "0805L110SLYR"',
                      '(property "Value" "0805L075SLYR"', 1)),
        ("[9]  a part lands inside the module window",
         cc.check_module_window,
         good.replace(f"(at {m.group(1)} {m.group(2)}", "(at 91.95 -44.95", 1)),
        # The one that matters most: restoring the via ECO-5 deleted makes the net whole,
        # which makes four documents wrong. The check must say so.
        ("[10] the Net-(Q5B-G) blocker gets FIXED",
         cc.check_blockers,
         good[:k] + VIA_AT_THE_BREAK + good[k:]),
        ("[11] a duplicate reference designator",
         cc.check_structure,
         good.replace('(property "Reference" "R23"',
                      '(property "Reference" "R24"', 1)),
    ]

    # [12] is tested separately: it reads the board through bom_split, not through the
    # cache, so the mutation has to be injected there instead.
    import bom_split
    stripped = good.replace("(attr smd exclude_from_bom exclude_from_pos_files)",
                            "(attr smd exclude_from_bom)", 1)
    extra_failed = 0
    if stripped == good:
        print("  BLIND:  [12] the mutation found nothing to strip -- ECO-9's flags moved")
        extra_failed += 1
    else:
        _asm, _hand, _none, _cpl, probs = bom_split.build(board=stripped)
        if probs:
            print("  ok:     [12] a hand-buy part left in the position file -> caught")
        else:
            print("  BLIND:  [12] a hand-buy part left in the position file -> NOT caught. "
                  "The machine would be asked to place a part it was never sold.")
            extra_failed += 1

    failures = extra_failed
    for label, fn, mutated in cases:
        if mutated == good:
            print(f"  BLIND:  {label} -- the mutation did not change the board, so this "
                  f"case proves nothing")
            failures += 1
            continue
        errs, _out = _run(fn, mutated)
        if errs:
            print(f"  ok:     {label} -> caught")
        else:
            print(f"  BLIND:  {label} -> the check did NOT fire. It is reading nothing, "
                  f"or reading the wrong thing.")
            failures += 1

    cc._board_cache["b"] = good
    errs, _ = _run(cc.check_reproducible, good)
    if errs:
        print("  BLIND:  the unmutated board does not pass -- every result above is suspect")
        failures += 1
    else:
        print("  ok:     the unmutated board still passes")

    print(f"\n== {len(cases) + 1} cases, {failures} blind ==")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
