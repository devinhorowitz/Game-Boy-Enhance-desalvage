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

# THE REBASE INVERTED THIS CASE. On the AGBM-01 base Net-(Q5B-G) was BROKEN, so the
# mutation ADDED the missing via and check [10] had to notice the blocker was fixed. On AGBM-02
# the net is WHOLE and check [10] asserts that, so the mutation now DELETES the via that joins
# it -- (100.8, -62.15) on net 224, the same coordinate that base removed the first time
# -- and the check has to notice the net came apart.
BREAK_THE_NET = re.compile(
    r'\n\t\(via\n\t\t\(at 100\.8 -62\.15\)(?:(?!\n\t\()[\s\S])*?\n\t\)')


def _run(fn, board):
    cc.errors.clear()
    cc.warnings.clear()
    cc._board_cache["b"] = board
    with contextlib.redirect_stdout(io.StringIO()) as s:
        fn()
    return list(cc.errors), s.getvalue(), list(cc.warnings)


# A CHECK THAT DECLINES TO RUN IS NOT THE SAME AS A CHECK THAT READS NOTHING, and this file
# could not tell them apart until 2026-08-20. Two of the checks need something the gate
# deliberately does not install -- [15] needs Pillow, [18] needs kicad-footprints -- and on a
# bare runner each says so and returns. Their mutation cases then reported BLIND,
# `test_checks.py` exited 1, and CI went red on every commit from that point onward
# while every local run was green. Seven commits of a red build nobody looked at.
#
# The distinction is the check's OWN announcement. `check_consistency` warns with this
# phrase, and a stated reason, exactly where it gives up; a check that silently matches
# nothing produces no such warning and is still BLIND. So a skip has to be EARNED by the
# check saying why -- and it is printed and counted separately, because "25 cases, 0
# blind, 2 not run here" must never be mistaken for full coverage.
_DECLINED = "did not run"


def _declined(warnings):
    """The check's own reason for not running, or None if it ran."""
    for w in warnings:
        if _DECLINED in w.lower():
            return w
    return None


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
    # WHICH VALUE TO CORRUPT. It has to be a value the generator actually sets, read from
    # the generator rather than typed here -- a literal turns this case into a no-op the
    # moment a part changes, which happened twice before the "BLIND" guard below caught it.
    # It comes straight from build_board's own swap tables now; it used to be scraped out of
    # the markdown, which is why those documents had to stay in lockstep with the code.
    import build_board
    chain = {ref: new for ref, field, _old, new in build_board.VALUE_SWAPS + build_board.FET_SWAPS
             if field == "Value"}
    if not chain:
        print("  BLIND:  the generator changes no Value -- case [1] cannot run")
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
        # The mutated value is pulled from the generator rather than typed here, so a change
        # moves a part cannot silently turn these cases into no-ops. Two of them did exactly
        # that when the precision pass rescaled R23 from 1.69M to 169k, and the "BLIND" guard
        # below is what said so.
        ("[1]  a hand-edited board no longer rebuilds",
         cc.check_reproducible,
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
        # The one that matters most: restoring the via that base deleted makes the net
        # whole, which makes four documents wrong. The check must say so.
        ("[10] the Net-(Q5B-G) blocker COMES BACK",
         cc.check_blockers,
         BREAK_THE_NET.sub("", good, count=1)),
        # [13] is the geometry gate. Three mutations, one per way the two
        # defects it was built for could come back.
        ("[13] the CXC_CLK via returns to its 0.1632 mm spot",
         cc.check_geometry,
         good.replace("(at 47.5 -59.5)", "(at 47.45 -59.6)", 1)),
        # Check [13] gained four axes it never had: the board outline INCLUDING its
        # shell holes, keepout zones, soldermask apertures as filled regions, and courtyards.
        # One case per axis, each moving a mark back to a spot that actually shipped once
        # -- so these are not invented failures, they are the real ones.
        ("[13] a fiducial lands back on a shell-hole rim (gr_circle)",
         cc.check_geometry,
         good.replace("(at 24.25 -55.75)", "(at 31.0 -69.5)", 1), "edge 0.082"),
        # A SEPARATE BLIND SPOT FROM THE ONE ABOVE. SW1 and VR2 each carry an Edge.Cuts
        # circle INSIDE the footprint -- the switch shaft and the volume wheel -- and a
        # top-level-only scan sees neither. This spot is where the first attempt at
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
        # [13] also gates MECHANICAL fit as of this pass -- whether the module physically clears
        # its same-side neighbours. Nothing measured that before: every gate was about copper.
        # Nudging C7 back toward the module closes the 0.820 mm gap opened by
        # moving it, which is the exact regression the ledger exists to catch.
        ("[13] C7 drifts back toward the module body",
         cc.check_geometry,
         good.replace("(at 93.1 -37.4 180)", "(at 93.1 -38.4 180)", 1)),
        # [2b] the shipped .kicad_mod must stay DERIVED from the board. Editing the library
        # copy by hand is precisely the drift that let it fall out of step for so long.
        ("[2b] the board's MOD1 changes and the library copy does not",
         cc.check_library_footprint,
         good.replace('"CLOCKXCONTROL"', '"CLOCKXCONTROLX"', 1)),
        # [17] paste vs placement. Two ways it rots, and the second is the one
        # that would ruin a board: restoring an aperture on a membrane contact, and pasting U2's
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
        print("  BLIND:  [12] the mutation found nothing to strip -- the flags moved")
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
    # [15] is the render gate. Any board change at all must make the committed PNGs stale; if it
    # does not, the renderer is not actually reading the board. [19] KiCad 10. The
    # KiCad 10 companion is a DERIVED artifact; if the KiCad 9 board moves and it does not, the
    # repository is carrying two different boards. Moving one track endpoint in the source is
    # exactly that. THE CASE ABOVE MOVES COPPER; THIS ONE MOVES ONLY
    # SILKSCREEN. check [19] shipped comparing footprints, pads, vias and track coverage, and
    # was described as proving "the same board" -- it proved the same COPPER, and a user's five
    # silkscreen edits passed straight through it. A gate is only as wide as the thing it
    # measures. A PROPERTY and a GRAPHIC are different code paths. The
    # case below moves a Reference, which lives in `(property ...)`; this one moves an fp_text,
    # which lives in the footprint's graphics and is the path whose reader was blind -- `(at 0 0
    # 180)` has a rotation, and the position pattern could not match it.
    cases.append(("[19] a silkscreen TEXT moves and the KiCad 10 copy does not",
                  cc.check_kicad10,
                  good.replace("(at -2.538 2.7004 180)", "(at 0 0 180)", 1),
                  "non-copper graphics differ"))
    cases.append(("[19] only the SILKSCREEN moves and the KiCad 10 copy does not",
                  cc.check_kicad10,
                  good.replace("(at -1.7944 1.5128 0)", "(at 0 -1.8 0)", 1),
                  "text placement differs"))
    cases.append(("[19] the KiCad 9 board moves and the KiCad 10 copy does not",
                  cc.check_kicad10,
                  good.replace("(start 38.725 -47.775)", "(start 38.725 -47.875)", 1),
                  "track coverage differs"))
    # PINNED TO THE SOURCE-DIGEST HALF, NOT THE PIXEL HALF. Re-rendering needs Pillow, this
    # project's CI installs nothing, and the pixel half's message therefore does not exist
    # there -- so requiring it would turn this case BLIND on exactly the runner it most
    # needs to work on. "written from a DIFFERENT board" is produced in both environments,
    # and it is the stronger claim: it names WHICH half fired rather than just noting that
    # something did.
    cases.append(("[15] the board moves and the renders do not",
                  cc.check_renders,
                  good.replace("(at 91.95 -44.95 180)", "(at 91.95 -45.35 180)", 1),
                  "written from a DIFFERENT board"))

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
            errs, _, _w = _run(cc.check_upstream_links, good)
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
    # upstream" landed on a line whose value this fork had changed (which [16] hands to check
    # [3] and skips), and CP1 stopped being a divergence at all the moment his own link put it
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

    # [20] is the ONE check with no artifact behind it: the power figures are modelled from
    # MouseBiteLabs' measurements, not derived from the board, so nothing can recompute them
    # and the ledger IS the source of truth. Both directions have to fire -- a figure that
    # appears in prose without a ledger line, and a ledger line no document states any more.
    # Mutating the LEDGER rather than the documents keeps this off the filesystem.
    def _ledger_case(label, mutate):
        keep = dict(cc.POWER_LEDGER)
        try:
            mutate(cc.POWER_LEDGER)
            errs, _, _w = _run(cc.check_power_ledger, good)
            print(f"  {'ok:     ' if errs else 'BLIND:  '}{label}"
                  f"{' -> caught' if errs else ' -> the check did NOT fire'}")
            return 0 if errs else 1
        finally:
            cc.POWER_LEDGER.clear()
            cc.POWER_LEDGER.update(keep)

    extra_cases += 1
    extra_failed += _ledger_case(
        "[20] a document states a power figure with no ledger line",
        lambda d: d.pop(sorted(d)[0]))
    extra_cases += 1
    extra_failed += _ledger_case(
        "[20] a ledger line no document states any more",
        lambda d: d.update({"1234.5": "a figure no document states"}))

    # [21] guards the expensive artifact. Two ways it rots, one case each. Both work on
    # COPIES in a temp directory with cc's paths repointed, so the real package on disk is
    # never touched -- a mutation case must not be able to damage the thing it guards.
    def _fab_case(label, mutate):
        import tempfile, zipfile as _zf
        keepz, keepm = cc.FAB_ZIP, cc.FAB_MANIFEST
        with tempfile.TemporaryDirectory() as td:
            z2, m2 = os.path.join(td, "p.zip"), os.path.join(td, "m.json")
            with _zf.ZipFile(cc.FAB_ZIP) as zin:
                members = {n: zin.read(n) for n in zin.namelist()}
            man = json.loads(io.open(cc.FAB_MANIFEST, encoding="utf-8").read())
            mutate(members, man)
            with _zf.ZipFile(z2, "w") as zout:
                for k in sorted(members):
                    zout.writestr(k, members[k])
            io.open(m2, "w", encoding="utf-8", newline="").write(json.dumps(man))
            cc.FAB_ZIP, cc.FAB_MANIFEST = z2, m2
            try:
                errs, _, _w = _run(cc.check_fab_package, good)
            finally:
                cc.FAB_ZIP, cc.FAB_MANIFEST = keepz, keepm
        print(f"  {'ok:     ' if errs else 'BLIND:  '}{label}"
              f"{' -> caught' if errs else ' -> the check did NOT fire'}")
        return 0 if errs else 1

    def _stale_source(members, man):
        man["source"] = {"board": "0" * 16, "base": "0" * 16}

    def _drop_a_copper_layer(members, man):
        victim = next(k for k in sorted(members) if k.lower().endswith(".g1"))
        members.pop(victim)

    extra_cases += 1
    extra_failed += _fab_case("[21] the package was plotted from a different board", _stale_source)
    extra_cases += 1
    extra_failed += _fab_case("[21] an inner copper layer is missing from the package",
                              _drop_a_copper_layer)

    # THE CASE THAT MATTERS MOST. The first order sheet read the thickness off the KiCad
    # stackup -- 1.2 mm -- when MouseBiteLabs' README says order 1.0 mm. Nothing in the
    # gerbers carries a thickness, so that error survives all the way to a board that does
    # not fit a shell. Strip his number out of the sheet and [21] has to notice.
    def _order_sheet_loses_his_thickness(members, man):
        import fab_package
        t = fab_package.order_spec()["thickness"]
        members["ORDER.txt"] = members["ORDER.txt"].replace(
            t.encode(), b"1.6mm")

    extra_cases += 1
    extra_failed += _fab_case("[21] the order sheet stops stating his thickness",
                              _order_sheet_loses_his_thickness)

    # The assembly form's BGA/QFP count decides whether the run gets X-ray inspection.
    # Move the number away from what the board says and [21] has to notice.
    def _order_sheet_miscounts_qfp(members, man):
        members["ORDER.txt"] = re.sub(
            rb"(BGA / QFP parts \.+ )0", rb"\g<1>2", members["ORDER.txt"])

    extra_cases += 1
    extra_failed += _fab_case("[21] the order sheet miscounts the BGA/QFP parts",
                              _order_sheet_miscounts_qfp)

    # AND THE CASE THE ZERO ITSELF DEPENDS ON. A classifier that has stopped recognising
    # quad packages reports the same "0 BGA/QFP" as a board that has none, so the sheet
    # alone cannot tell them apart. Blind the classifier -- make every package read as a
    # dual -- and [21] must refuse to believe its own zero. If this case ever goes BLIND,
    # the number on the order form has stopped meaning anything.
    def _blind_the_classifier(members, man):
        import fab_package
        keep = fab_package._package_shape
        fab_package._package_shape = lambda pads: ("dual", 0.5)
        _restore.append(lambda: setattr(fab_package, "_package_shape", keep))

    # The polarity warning is the one instruction the gerbers cannot carry: drop a
    # tantalum's refdes out of the sheet and nothing else on the board would ever say it
    # goes in one way round.
    def _order_sheet_drops_a_tantalum(members, man):
        members["ORDER.txt"] = members["ORDER.txt"].replace(b"CP2", b"C__", 1)

    extra_cases += 1
    extra_failed += _fab_case("[21] the order sheet stops naming an unmarked polarised part",
                              _order_sheet_drops_a_tantalum)

    _restore = []
    extra_cases += 1
    try:
        extra_failed += _fab_case("[21] the package classifier stops recognising a QFP",
                                  _blind_the_classifier)
    finally:
        for undo in _restore:
            undo()

    failures, skipped = extra_failed, []
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
        errs, _out, warns = _run(fn, mutated)
        why = None if errs else _declined(warns)
        if why:
            print(f"  SKIP:   {label} -> the check declined to run here: {why}")
            skipped.append(label)
        elif errs and (want is None or any(want in e for e in errs)):
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
    errs, _, _w = _run(cc.check_reproducible, good)
    if errs:
        print("  BLIND:  the unmutated board does not pass -- every result above is suspect")
        failures += 1
    else:
        print("  ok:     the unmutated board still passes")

    # +1 for the unmutated control, +extra_cases for the ones that mutate JSON on disk and
    # so run outside `cases`. Reporting len(cases)+1 under-counted the suite by two.
    tail = f", {len(skipped)} not run here" if skipped else ""
    print(f"\n== {len(cases) + 1 + extra_cases} cases, {failures} blind{tail} ==")
    if skipped:
        print("   NOT FULL COVERAGE. These cases need something this environment does not\n"
              "   have; run them on a machine with Pillow and kicad-footprints installed:")
        for s in skipped:
            print(f"     - {s}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
