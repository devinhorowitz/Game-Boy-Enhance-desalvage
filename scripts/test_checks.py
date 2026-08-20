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

# ECO-13 INVERTED THIS CASE. On the ECO-5 base Net-(Q5B-G) was BROKEN, so the mutation
# ADDED the missing via and check [10] had to notice the blocker was fixed. On AGBM-02 the
# net is WHOLE and check [10] asserts that, so the mutation now DELETES the via that joins
# it -- (100.8, -62.15) on net 224, the same coordinate ECO-5 removed the first time -- and
# the check has to notice the net came apart.
BREAK_THE_NET = re.compile(
    r'\n\t\(via\n\t\t\(at 100\.8 -62\.15\)(?:(?!\n\t\()[\s\S])*?\n\t\)')


def _run(fn, board):
    cc.errors.clear()
    cc.warnings.clear()
    cc._board_cache["b"] = board
    with contextlib.redirect_stdout(io.StringIO()) as s:
        fn()
    return list(cc.errors), s.getvalue()


def cc_by_ref():
    import kisexp
    return kisexp.by_ref(cc.board())


def main():
    good = cc.board()
    # WHICH VALUE TO CORRUPT. It has to be the value R23 carries TODAY, at the end of the
    # whole ECO chain -- and it has to be scoped to R23's own footprint, because the chain
    # can land two refs on the same value (ECO-12 put R23 on 178k, which is also R21's).
    # Reading it from cc._eco_chain_final() rather than a literal is what stops an ECO
    # that moves R23 from silently turning these cases into no-ops; the "BLIND" guard
    # below is what caught it the two times it happened, at ECO-10 and again at ECO-12.
    # ECO-13 note: this used to name R23, which does not exist on the AGBM-02 base. Take
    # whichever ref the chain actually ends on, so the case survives the next rebase too.
    chain = cc._eco_chain_final()
    if not chain:
        print("  BLIND:  no ECO in the chain changes a Value -- cases [1] and [3] cannot run")
        return 1
    VICTIM_REF = sorted(chain)[0]
    VICTIM = chain[VICTIM_REF]
    # For the duplicate-refdes case the new name has to be one the board ALREADY carries,
    # or there is no duplicate to find. Take another ref off the board rather than typing
    # one in, so it cannot go stale either.
    OTHER_REF = next(r for r in sorted(cc_by_ref()) if r != VICTIM_REF and "*" not in r)

    def corrupt(ref, prop, was, now, src=None):
        """Replace one property inside ONE named footprint. Returns the board unchanged
        if it cannot find it, which the BLIND guard then reports."""
        src = good if src is None else src
        i = 0
        while True:
            i = src.find("\n\t(footprint ", i)
            if i < 0:
                return src
            j = src.find("\n\t)\n", i + 1)
            b = src[i + 1:j + 4]
            if f'(property "Reference" "{ref}"' in b:
                return src[:i + 1] + b.replace(f'(property "{prop}" "{was}"',
                                               f'(property "{prop}" "{now}"', 1) + src[j + 4:]
            i = j + 1
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
         corrupt(VICTIM_REF, "Value", VICTIM, "12345")),
        ("[3]  an ECO table and the board disagree",
         cc.check_eco8_ledger,
         corrupt(VICTIM_REF, "Value", VICTIM, "12345")),
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
        ("[10] the Net-(Q5B-G) blocker COMES BACK",
         cc.check_blockers,
         BREAK_THE_NET.sub("", good, count=1)),
        # [13] is the geometry gate ECO-14 added. Three mutations, one per way the two
        # defects it was built for could come back.
        ("[13] the CXC_CLK via returns to its 0.1632 mm spot",
         cc.check_geometry,
         good.replace("(at 47.5 -59.5)", "(at 47.45 -59.6)", 1)),
        ("[13] a fiducial lands back on top of a GND via",
         cc.check_geometry,
         good.replace("(at 31.0 -69.5)", "(at 33.0 -69.0)", 1)),
        ("[13] a fiducial loses the clearance that holds the pour back",
         cc.check_geometry,
         good.replace("(clearance 0.55)", "", 1)),
        ("[11] a duplicate reference designator",
         cc.check_structure,
         corrupt(VICTIM_REF, "Reference", VICTIM_REF, OTHER_REF)),
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
