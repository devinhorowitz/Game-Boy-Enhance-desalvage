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


def _repour(board):
    """Stand in for a KiCad `Fill All Zones`: change one vertex inside the FIRST stored
    filled_polygon. Perturbing any old `(xy ...)` is not enough -- zone OUTLINES use the
    same token and they are not what check [14] digests."""
    import geom
    m = geom._FILL.search(board)
    if not m:
        return board
    blk = m.group(0)
    new = blk.replace("(xy ", "(xy 0.001 0.001) (xy ", 1)
    return board[:m.start()] + new + board[m.end():]


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
        # ECO-20 gave check [13] four axes it never had: the board outline INCLUDING its
        # shell holes, keepout zones, soldermask apertures as filled regions, and
        # courtyards. One case per axis, each moving a mark back to a spot ECO-14 actually
        # shipped -- so these are not invented failures, they are the real ones.
        ("[13] a fiducial lands back on a shell-hole rim (gr_circle)",
         cc.check_geometry,
         good.replace("(at 24.25 -55.75)", "(at 31.0 -69.5)", 1), "edge 0.082"),
        # A SEPARATE BLIND SPOT FROM THE ONE ABOVE. SW1 and VR2 each carry an Edge.Cuts
        # circle INSIDE the footprint -- the switch shaft and the volume wheel -- and a
        # top-level-only scan sees neither. This spot is where ECO-20's first attempt at
        # FID1 went, with geom reporting 2.80 mm of edge clearance and DRC 0.2145.
        ("[13] a fiducial lands in SW1's routed shaft opening (fp_circle)",
         cc.check_geometry,
         good.replace("(at 100.5 -3.5)", "(at 11.75 -12.75)", 1), "edge 0.716"),
        ("[13] a fiducial lands back inside a keepout zone",
         cc.check_geometry,
         good.replace("(at 103.75 -58.5)", "(at 110.85 -57.65)", 1), "keepout -1.194"),
        ("[13] a fiducial lands back inside the cartridge mask aperture",
         cc.check_geometry,
         good.replace("(at 94.75 -66.5)", "(at 110.85 -57.65)", 1), "mask -1.850"),
        # The courtyard axis has no DRC rule behind it, so this is the one case KiCad would
        # not catch for us. (84.5, -51.5) is 2.415 mm from the nearest copper and 9 mm from
        # everything else -- it fails on the component body alone, and on nothing else.
        ("[13] a fiducial ends up under a component body",
         cc.check_geometry,
         good.replace("(at 103.75 -58.5)", "(at 84.5 -51.5)", 1), "crtyd 0.010"),
        ("[13] a fiducial loses the clearance that holds the pour back",
         cc.check_geometry,
         good.replace("(clearance 0.55)", "", 1)),
        # [13] also gates MECHANICAL fit as of this pass -- whether the module physically
        # clears its same-side neighbours. Nothing measured that before: every gate was
        # about copper. Nudging C7 back toward the module closes the 0.820 mm gap ECO-6
        # opened by moving it, which is the exact regression the ledger exists to catch.
        ("[13] C7 drifts back toward the module body",
         cc.check_geometry,
         good.replace("(at 93.1 -37.4 180)", "(at 93.1 -38.4 180)", 1)),
        # [2b] the shipped .kicad_mod must stay DERIVED from the board. Editing the library
        # copy by hand is precisely the drift that let it fall out of step for four ECOs.
        ("[2b] the board's MOD1 changes and the library copy does not",
         cc.check_library_footprint,
         good.replace('"CLOCKXCONTROL"', '"CLOCKXCONTROLX"', 1)),
        # [17] paste vs placement, ECO-17. Two ways it rots, and the second is the one that
        # would ruin a board: restoring an aperture on a membrane contact, and pasting U2's
        # unused land so solder reflows under the body of the RAM that IS fitted.
        ("[17] paste comes back on a DNP membrane-contact pad",
         cc.check_paste,
         good.replace('(at -7.395 2.78)\n\t\t\t(size 0.3 0.3)\n\t\t\t(layers "F.Cu" "F.Mask")',
                      '(at -7.395 2.78)\n\t\t\t(size 0.3 0.3)\n\t\t\t(layers "F.Cu" "F.Mask" "F.Paste")', 1)),
        ("[17] U2's unused land pattern gets pasted again",
         cc.check_paste,
         good.replace('(at -6.69 -5.75)\n\t\t\t(size 1.525 0.3)\n\t\t\t(layers "F.Cu" "F.Mask")',
                      '(at -6.69 -5.75)\n\t\t\t(size 1.525 0.3)\n\t\t\t(layers "F.Cu" "F.Mask" "F.Paste")', 1)),
        # [18] is the rotation-convention gate. Two ways it rots: a footprint whose pin 1
        # moves off the stock library's corner (so `rot` stops meaning what a fab assumes),
        # and a CPL rotation that stops matching kicad-cli's own export.
        ("[18] a footprint's pin 1 moves off the stock corner",
         cc.check_rotation_convention,
         good.replace('(pad "1" smd roundrect\n\t\t\t(at -1.1375 -0.95)',
                      '(pad "1" smd roundrect\n\t\t\t(at -1.1375 0.95)', 1)),
        # [14] guards the stale zone fill and is built to go RED the day someone re-pours,
        # because three documents say "re-pour before fab" and become wrong at that moment.
        # The mutation stands in for a re-pour: perturb one fill vertex so the signature
        # changes, exactly as a real Fill All Zones would.
        ("[14] the zone fill gets recomputed",
         cc.check_zone_fill,
         _repour(good)),
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
    extra_cases = 0
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

    # [14]'s hazard set is LEDGERED as of this pass, because the first version of it
    # miscounted (footprint origin, pad 1's net, refdes-keyed) and nothing noticed. Sliding
    # TP83 north takes it out of the GND pour, which changes the set the ledger pins.
    cases.append(("[14] an added pad leaves the pour the ledger has it in",
                  cc.check_zone_fill,
                  good.replace("(at 97.9 -37.95)", "(at 97.9 -30.0)", 1)))
    # [15] is the render gate. Any board change at all must make the committed PNGs stale;
    # if it does not, the renderer is not actually reading the board.
    cases.append(("[15] the board moves and the renders do not",
                  cc.check_renders,
                  good.replace("(at 91.95 -44.95 180)", "(at 91.95 -45.35 180)", 1)))

    # [16] reads MouseBiteLabs' own Source links. Two ways it can rot, one case each.
    # These mutate the JSON on disk rather than the board, so they restore it afterwards.
    import json, shutil, tempfile
    LINKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "link_mpn.json")
    OVERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mpn_overrides.json")

    def _json_case(label, path, mutate):
        keep = io.open(path, encoding="utf-8").read()
        try:
            d = json.loads(keep)
            mutate(d)
            io.open(path, "w", encoding="utf-8", newline="").write(json.dumps(d, indent=1))
            errs, _ = _run(cc.check_upstream_links, good)
            print(f"  {'ok:     ' if errs else 'BLIND:  '}{label}"
                  f"{' -> caught' if errs else ' -> the check did NOT fire'}")
            return 0 if errs else 1
        finally:
            io.open(path, "w", encoding="utf-8", newline="").write(keep)

    extra_cases += 1
    extra_failed += _json_case(
        "[16] a link in MouseBiteLabs' schematic goes unresolved", LINKS,
        lambda d: d["links"].pop(sorted(d["links"])[0]))
    # SELF-SELECTING TARGET. Two earlier attempts proved nothing: "the first entry with an
    # upstream" landed on a line whose value an ECO had changed (which [16] hands to check
    # [3] and skips), and CP1 stopped being a divergence at all the moment ECO-15 put it
    # back on MouseBiteLabs' part. So find a line that [16] is ACTUALLY counting right now
    # -- same value on both sides, upstream recorded -- and strip its ledger.
    def _pick_diverging():
        import check_stock, kisexp
        links = json.loads(io.open(LINKS, encoding="utf-8").read())["links"]
        srcs = check_stock.schematic_sources()
        vals = {r: fp.value for r, fp in kisexp.by_ref(cc.board()).items()}
        for e in json.loads(io.open(OVERS, encoding="utf-8").read())["entries"]:
            if not e.get("upstream"):
                continue
            for r in e["refs"]:
                L = links.get(srcs.get(r, ""))
                if L and L["mpn"] != e["mpn"] and vals.get(r) in (L.get("expect") or "").split("/"):
                    return r
        return None

    extra_cases += 1
    _victim = _pick_diverging()
    if not _victim:
        print("  BLIND:  [16] no same-value divergence exists to mutate -- case proves nothing")
        extra_failed += 1
    else:
        def _strip(d):
            e = next(x for x in d["entries"] if _victim in x["refs"])
            e.pop("upstream", None)
            e.pop("eco", None)
            e.pop("flag", None)
        extra_failed += _json_case(
            f"[16] {_victim} silently stops matching his part", OVERS, _strip)

    failures = extra_failed
    for case in cases:
        label, fn, mutated = case[:3]
        # A FOURTH ELEMENT MAKES THE CASE PROVE SOMETHING SPECIFIC. Check [13] pins every
        # fiducial margin to a ledger, so ANY move of ANY mark fails it -- which means
        # "caught" alone cannot tell a keepout case from an edge case, and four cases that
        # all fire for the same reason are one case wearing four hats. Where a case exists
        # to prove one axis is modelled, name a phrase the error has to contain.
        want = case[3] if len(case) > 3 else None
        if mutated == good:
            print(f"  BLIND:  {label} -- the mutation did not change the board, so this "
                  f"case proves nothing")
            failures += 1
            continue
        errs, _out = _run(fn, mutated)
        if errs and (want is None or any(want in e for e in errs)):
            print(f"  ok:     {label} -> caught")
        elif errs:
            print(f"  BLIND:  {label} -> the check fired, but not for the reason this case "
                  f"exists to prove ({want!r} is not in the message). It would pass even if "
                  f"that axis were not modelled at all.")
            failures += 1
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

    # +1 for the unmutated control, +extra_cases for the ones that mutate JSON on disk and
    # so run outside `cases`. Reporting len(cases)+1 under-counted the suite by two.
    print(f"\n== {len(cases) + 1 + extra_cases} cases, {failures} blind ==")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
