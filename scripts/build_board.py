#!/usr/bin/env python3
"""build_board.py -- regenerate the ClockxControl board from committed sources.

    python3 scripts/build_board.py                 # write the board
    python3 scripts/build_board.py --check         # build in memory, diff, write nothing
    python3 scripts/build_board.py -o /tmp/x.pcb   # build somewhere else

WHY THIS EXISTS

Until this file landed, the shipped board was the output of a script that lived in a
scratch directory and was never committed. ECO-8 said so in its own section 8.6 -- "the
script is not in the repository" -- which meant the deliverable could not be rebuilt by
anyone, including its author, and no gate could tell whether the committed board was
still the one the ECOs describe. Every number in ECO-6, ECO-7 and ECO-8 was a claim about
a binary blob nobody could re-derive.

This is SOLAR-GLOW's `Generated/` doctrine applied here: the artifact is a FUNCTION of
committed inputs, so it can be rebuilt, diffed, and gated. Its inputs are

    agbm-01-ram-desalvage.zip   the ECO-5 base board, already committed at repo root
    scripts/routes.json         the frozen ECO-6 routing
    the ECO tables below        every deliberate edit, one line each

and its output is byte-identical to `AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb` inside
`clockxcontrol-integration/board/agbm-01-clockxcontrol.zip`. Consistency check [1] asserts
exactly that, which is what makes the ECO documents auditable rather than decorative.

WHAT IT DOES, IN ECO ORDER

    ECO-6  move C7 out of the module window; move the FID2/FID5 fiducial pair; drop the
           two VDD2 stitching vias the R landing lands on; add the ClockxControl land
           pattern, the three wire pads (TP83/84/85), TP82 and the CK1 isolation jumper
           JP3; add the CXC_CLK net and route everything.
    ECO-7  mark X1/C3/C4 DNP -- the ClockxControl drives CK1 directly, so an assembly
           house must not fit the crystal or its load caps.
    ECO-8  thirteen Value/Description edits from the power review. No copper.
    ECO-9  mark the parts a pick-and-place cannot handle `exclude_from_bom` +
           `exclude_from_pos_files`, so the board itself says what a machine can buy
           and place. No copper either -- attributes only.
    ECO-10 rescale both LTC3527 feedback dividers 10x down, same ratios, so the
           converter's own FB input current stops being the dominant rail error. Six
           Values, no copper.
    ECO-11 Q9 and Q10 to a logic-level FET, because the NDC7002N's worst-case gate
           threshold is ABOVE the gate drive those two are given. Two Values, no copper.

EVERY EDIT ASSERTS ITS OWN PRECONDITION. A replacement whose target string is missing, or
present more than once, fails the build instead of silently producing a different board.
That is the property that lets check [1] mean something.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# --- ECO-13: the base is MouseBiteLabs' AGBM-02, unmodified --------------------------
# It was the ECO-5 AGBM-01 desalvage until 2026-08-19. ECO-5 was OUR footprint work, which
# MouseBiteLabs never saw and never used; AGBM-02 is his, and it already carries the
# CY62157 land, the MA17 and /BYTE straps, and a front-shell fit he physically verified.
# See clockxcontrol-integration/ECO-13_rebase_onto_agbm02.md.
BASE_ZIP = os.path.join(ROOT, "AGBM-02 (AA Batteries)", "AGBM-02 Design Files.zip")
BASE_MEMBER = "AGBM-02 Design Files/AGBM-02_AA_1-1.kicad_pcb"
ROUTES = os.path.join(ROOT, "scripts", "routes.json")
SHIPPED_ZIP = os.path.join(ROOT, "clockxcontrol-integration", "board",
                           "agbm-02-clockxcontrol.zip")
SHIPPED_MEMBER = "agbm-02-clockxcontrol/AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb"
OUT = os.path.join(ROOT, "clockxcontrol-integration", "board",
                   "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb")

# --- ECO-6 geometry ------------------------------------------------------------------
# The module body is 18.65 x 12.00 mm; MOD_X/MOD_Y is its centre. rev B moved it west out
# of the R3/TP114 cluster -- ECO-6 section 6.7 is the accounting for what that cost.
MOD_X, MOD_Y = 91.95, -44.95
C7_FROM, C7_TO = "(at 91.9 -41.1 180)", "(at 93.1 -37.4 180)"
DROP_VIAS = [(84.4, -45.9), (85.4, -45.9)]          # both on VDD2
# FIDUCIALS ARE OURS, NOT MOUSEBITELABS'. Neither AGBM-01 nor AGBM-02 carries a single
# one -- he hand-builds, and a hand builder does not need optical registration. A
# pick-and-place does, so ECO-9's whole premise needs them. ECO-5 added six and ECO-6 then
# moved a pair out from under the module; on this base they are simply placed clear of it
# to begin with. Three per side in a deliberately asymmetric triangle so the machine cannot
# register the panel 180 degrees out. Each spot was clearance-checked against AGBM-02.
FIDUCIALS = [("FID1", 26.0, -8.0, "F.Cu"), ("FID4", 26.0, -8.0, "B.Cu"),
             ("FID3", 33.0, -69.0, "F.Cu"), ("FID6", 33.0, -69.0, "B.Cu"),
             ("FID2", 106.25, -57.25, "F.Cu"), ("FID5", 106.25, -57.25, "B.Cu")]
# The three button landings the module's plated through-holes solder down onto.
PADS = [("1", 4.525, 1.0, 71, "/CPU/TP2", "SEL"),
        ("2", 7.025, 3.5, 13, "/CPU/TP9", "L"),
        ("3", 7.025, 1.0, 12, "/CPU/TP8", "R")]
GHOSTS = [(4.525, 3.5), (4.525, -1.5), (7.025, -1.5)]   # F.Fab marks for the unused holes
LABELS = [("SEL", 3.0, 1.0), ("L", 8.5, 3.5), ("R", 8.5, 1.0)]
# The wire pads. y = -37.95, not -38.6: at -38.6 the 1.2 mm pads overlap the module body
# by 0.25 mm at their radius. KiCad's y grows DOWNWARD, which is the sign error that
# nearly shipped this row underneath the module.
WIRE_PADS = [("TP83", 97.9, -37.95, "CXC_CLK", "CLK", "CXC CLK wire"),
             ("TP84", 99.45, -37.95, "VDD3", "V+", "CXC V+ wire"),
             ("TP85", 101.0, -37.95, "GND", "V-", "CXC V- wire")]

# --- ECO-7: the crystal network is not fitted on a ClockxControl build ----------------
DNP_REFS = ("X1", "C3", "C4")

# --- ECO-8: the drop-in part swaps ---------------------------------------------------
# ref, field, old, new. Documented in clockxcontrol-integration/ECO-8_component_swaps.md;
# consistency check [3] holds that document's table and this list to the same values, so
# neither can drift from the other or from the board.
# ON THE AGBM-02 BASE, THREE OF ECO-8's THIRTEEN ROWS ARE ALREADY DONE UPSTREAM:
#   F1    Value  -- AGBM-02 already reads F0805B2R00FSTR. ECO-8's BOM fix was right and
#                   MouseBiteLabs made the same fix; nothing left for us to change.
#   PTC1  Value  -- AGBM-02 already reads 0805L075SLYR, not the stale "0467001.NR". The
#                   ANNOTATION is fixed upstream, but the ENGINEERING finding stands: that
#                   part derates to 0.55 A hold at 40 C, below the load. So the swap
#                   remains, from a different starting value.
#   R23   Value  -- the ref does not exist on AGBM-02. It was the LTC3527's VOUT3 feedback
#                   leg, and AGBM-02 has no LTC3527. ECO-12 section 12.2 had already
#                   reverted this change; the rebase deletes it outright.
# Both Description rows survive: AGBM-02 still carries the legacy "0805L050WR" string on
# PTC1 and F1 alike, exactly as AGBM-01 and AGBM-11 do.
ECO8 = [
    ("U7",   "Value",       "TLV9364",       "TLV9064IPWR"),
    ("DL1",  "Value",       "150060VS75000", "150060GS75000"),
    ("R25",  "Value",       "3.3k",          "22k"),
    ("PTC1", "Value",       "0805L075SLYR",  "0805L110SLYR"),
    ("PTC1", "Description", "0805L050WR",
     "PPTC resettable fuse, Littelfuse Low Rho, 1.10 A hold / 1.80 A trip, 6 Vdc, 0805"),
    ("F1",   "Description", "0805L050WR",
     "Fast-acting thin-film chip fuse, 2.00 A, 63 V, 0805"),
    ("R15",  "Value",       "10k",           "100k"),
    ("R16",  "Value",       "10k",           "100k"),
    ("R11",  "Value",       "1k",            "10k"),
    ("R24",  "Value",       "100k",          "1M"),
    ("R65",  "Value",       "100k",          "470k"),
]

# --- ECO-10: the precision pass -- NO Value swaps survive the rebase -------------------
# On AGBM-01, ECO-10's headline was rescaling both LTC3527 feedback dividers 10x down,
# because the converter's own 50 nA max FB input current was moving VOUT3 by +/-85 mV --
# more than the resistors' tolerance, and more than the 108 mV ECO-8 had trimmed off that
# rail to save power. It was the right finding about the wrong converter.
#
# AGBM-02 has no LTC3527. R21, R22, R23, R55, C40 and C41 -- every leg of both dividers and
# both feedforward caps -- DO NOT EXIST on this base. Twin TPS63802s set their rails
# elsewhere, so the entire divider analysis, and ECO-12 section 12.2 which reverted part of
# it, are deleted by the rebase rather than carried.
#
# ECO-10's OTHER work survives untouched, because none of it is a Value change: the audio
# filter's 0.1% +/-25 ppm thin film, the 25 V AEC-Q200 decoupling, and the supervisor
# divider legs are all PART-NUMBER choices, and they live in scripts/mpn_overrides.json
# against references AGBM-02 carries at identical positions.
ECO10 = []

# --- ECO-11: the brownout latch is not guaranteed to arm --------------------------------
# NDC7002N gate threshold, read off onsemi's own table: VGS(th) = 1.0 min / 1.9 typ /
# **2.5 V max** at VDS = VGS, ID = 250 uA. There is no RDS(on) specification below
# VGS = 4.5 V at all. Now the gate drive those two parts actually get:
#
#   Q10A  must pull /~MR down through the TPS3840's 100 kOhm INTERNAL MR pull-up
#         (datasheet: "Manual reset internal pull-up resistance ... 100 kOhm"), i.e. sink
#         ~14 uA, with VGS = SW - Vce(sat) ~= 2.0 V at the 2.07 V trip point.
#   Q10B  run state, VGS = 0.990 x SW -- 2.05 V at the trip, 3.17 V on a fresh pack.
#   Q9B   low-battery state, gate = /D1A ~= 3.0 V after ECO-8's InGaN LED raised the
#         forward drop; it must pass DL2's ~165 uA through R10.
#
# A worst-case NDC7002N is at or BELOW its own threshold in all three, and the threshold is
# defined as the VGS that produces 250 uA. Sub-threshold conduction falls a decade every
# 60-100 mV, so half a volt short is five to eight decades short. The latch does not arm and
# the low-battery LED does not light. It is worse cold: VGS(th) has a negative tempco, so a
# cold console pushes a TYPICAL part into the same place.
#
# FDC6301N: VGS(th) = 0.65 / 0.85 / **1.5 V max**, same SUPERSOT-6 / TSOT-23-6 land, same
# pin assignment. Every one of those nodes gains at least 0.5 V of worst-case overdrive.
#
# THE ONE OBJECTION, AND WHY IT DOES NOT HOLD. The FDC6301N's gate rating is asymmetric,
# -0.5 to +8 V, against the NDC7002N's 20 V. Q10A is the only node that ever sees a negative
# VGS: at power-up /EN rises through R11 while Q10A's gate is still held down by R17, so
# VGS goes to about -SW. But the datasheet's own feature list reads "Gate-Source Zener for
# ESD Ruggedness. >6 kV Human Body Model" -- the part carries an integrated clamp, which
# forward-conducts at ~-0.7 V with the current set by R16. ECO-8 raised R16 from 10k to
# 100k, so that clamp current is (3.2-0.7)/100k = 25 uA. This is what the Zener is for.
#
# Headroom: FDC6301N is 25 V / 0.22 A against a 5.0 V maximum VDS anywhere here and drain
# currents of 14 uA (Q10A), ~41 uA (Q10B), 124 uA (Q9A's LED after ECO-8) and ~165 uA (Q9B).
# Three orders of margin. RDS(on) 5 Ohm max at VGS = 2.7 V costs Q9A 0.6 mV.
#
# Q2, Q5 and Q7 keep the NDC7002N, deliberately: Q5's gates are driven to VOUT5 = 5.0 V so
# there is no margin problem to fix, and Q2/Q7 switch display signals from U16 where the
# worst-case overdrive is already 0.73 V and where changing RDS(on) and Ciss would be an
# unanalysed timing risk bought for no stated benefit.
ECO11 = [
    ("Q9",  "Value", "NDC7002N", "FDC6301N"),
    ("Q10", "Value", "NDC7002N", "FDC6301N"),
]

# --- ECO-12: the wiki audit -- NO Value swaps survive the rebase either -----------------
# ECO-12 section 12.1 corrected R3/R4/R64 on AGBM-01 from a stale PCB annotation (1k/10k/
# 100k) to the values MouseBiteLabs' schematic, both AA README BOMs and his AGBM-02 PCB all
# carry (5.1k/33k/200k) -- the values that put the low-battery trip at 2.309 V and the
# blink at 2.102 V, matching the wiki and his own build-guide Test 4.
#
# AGBM-02 ALREADY CARRIES THEM. The stale annotation was an AGBM-01 artifact and he fixed
# it on the newer board; that is what made the wiki audit's case in the first place. So the
# corrections are now INHERITED, not applied, and the assertion further down verifies them
# against the base rather than against our own edit -- which is strictly stronger, because
# it fails if UPSTREAM ever drifts.
#
# Section 12.2 (R23, VOUT3 back to 3.336 V) goes with the LTC3527. The part-number half of
# ECO-12 -- R3/R4 to Susumu RG1608 0.1%, R63 onto the same film as its partner R58 -- is
# unaffected and still lives in scripts/mpn_overrides.json.
ECO12 = []


# --- ECO-9: the board should say what a machine can actually place --------------------
# Until this, the board asked a pick-and-place to buy and place 179 parts -- including the
# SALVAGED CPU and SRAM, which nobody sells at any price, and five parts with through-hole
# pads, which a reflow line does not do. A BOM and a CPL generated from that describe a
# build that cannot happen, and PCBWay would either quote the unbuyable parts or bounce
# the order.
#
# So the split is encoded in the DESIGN, which is the whole point of the rule
# `scripts/bom_split.py` runs on: a part moves between "the machine buys and places it"
# and "you hand-solder it" by changing the board, never by editing a list.
#
# THE RULE IS MECHANICAL, not a hand-list. A part is hand-soldered if either:
#   (a) it has ANY through-hole pad -- read off the board, no maintenance; or
#   (b) it is in SALVAGE_ONLY below, which cannot be derived because a salvaged QFP is
#       byte-identical in the file to a new one.
# `np_thru_hole` (a plain mounting hole, no plating) does NOT count -- it is a hole, not
# a joint.
SALVAGE_ONLY = {
    "U1": "AGB-CPU, 128-pin QFP recovered from a donor board. The schematic's own Source "
          "field reads 'Salvage'. Not orderable at any price, so it cannot be on an "
          "assembly BOM; hand-fit after the reflow.",
}
# U2 IS NO LONGER HERE, AND THAT IS THE POINT OF THE REBASE. On the AGBM-01 base it was a
# salvaged AGB-SRAM, and ECO-5 was OUR unverified attempt to let a CY62157EV30LL stand in
# for it. AGBM-02 carries MouseBiteLabs' own dual land, so U2 is an ORDERABLE PART -- the
# machine buys it and places it, and a build needs exactly one chip off a donor: the CPU.
# His Required Parts page says so outright: "For the AGBM-02 and AGBM-12, you *only* need
# the CPU."
#
# TWO HAND STEPS COME WITH IT, and no assembly line performs either. Both must be left OPEN
# if you populate a salvaged OEM AGB-SRAM instead, which this land still accepts:
#   JP2  bridge to tie U2 pin 17 (MA17) to GND
#   JP3  bridge to tie U2 pin 47 (/BYTE) to VDD2 for x16 word mode
# Those are MouseBiteLabs' jumpers with MouseBiteLabs' numbering, documented on his Feature
# Configurations wiki page. OUR ClockxControl clock jumper is JP4 -- it was JP3 on the
# AGBM-01 base, where nothing else claimed the name.
# Parts whose through-hole pads make them hand-solder by rule (a). Listed only so the
# generator can state WHY in one place; membership is still derived from the pads.
THRU_HOLE_REASONS = {
    "P1":  "AGB cartridge slot, 36 through-hole pins",
    "P3":  "CUI SJ-3524-SMT headphone jack -- 4 SMD + 4 through-hole signal pins and 2 "
           "unplated posts, so a selective-solder or hand step either way",
    "P4":  "AGB link port, 8 through-hole pins",
    "SP1": "speaker, 2 through-hole pads and a wired mechanical part",
    "VR2": "Alps RK10J12R0A0B volume pot -- 7 SMD pads plus 2 through-hole anchors",
}
# NOT hand-soldered, and worth recording because they look like they should be:
#   P2   42 SMD pads, an FFC connector -- a machine's job
#   SW1  5 SMD pads
#   VR1  3 SMD pads
#   BT1, SW2, SW3  already DNP in the ECO-5 base
#
# MOD1 carries the same pair, set where its footprint is built rather than here: the
# ClockxControl is a mezzanine whose plated holes are filled with solder FROM ABOVE
# onto the pads below. No pick-and-place operation does that. It was
# `exclude_from_bom` only until bom_split noticed it was still in the position file
# -- a part the machine had never been sold and could not have placed if it had been.
#
# IF YOU CONSIGN THE CPU AND SRAM TO PCBWAY INSTEAD of fitting them yourself, take U1 and
# U2 out of SALVAGE_ONLY: they go back into the position file (the machine places them)
# while staying off the assembly BOM (you still supply the parts). That is one of the four
# open build decisions in pcbway-assembly/README.md, and this is the switch for it.


def uid(seed):
    """Deterministic UUIDs. A random uuid4 per run would make the board unreproducible
    and check [1] impossible; these are a hash of a stable seed instead."""
    h = hashlib.sha1(("cxc-eco6:" + seed).encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def build():
    raw = zipfile.ZipFile(BASE_ZIP).read(BASE_MEMBER).decode("utf-8")
    # LINE ENDINGS ARE PART OF THE ARTIFACT, and the rebase changed them completely. The
    # ECO-5 base carried exactly ONE stray CRLF, at the very end of the file; MouseBiteLabs'
    # AGBM-02 as he saves it is CRLF THROUGHOUT -- 273,525 of them. Normalising to LF here,
    # deliberately and once, is what makes the rebuild byte-stable; doing it implicitly with
    # a text-mode open() is how a .kicad_pcb ends up alternating line endings between saves.
    # The shape is asserted so that a base board with different line endings fails the build
    # instead of quietly producing a board that no longer matches the ECOs.
    crlf, lf_only = raw.count("\r\n"), raw.count("\n") - raw.count("\r\n")
    if lf_only or crlf < 100000 or not raw.endswith(")\r\n"):
        raise AssertionError(
            f"base board line endings changed: {crlf} CRLF and {lf_only} bare LF. AGBM-02 "
            "ships CRLF THROUGHOUT (the ECO-5 base carried exactly one, at EOF), so this "
            "expects a fully-CRLF file. Normalisation is deliberate -- see the comment.")
    txt = raw.replace("\r\n", "\n")
    orig_len = len(txt)
    R = json.load(open(ROUTES))

    # NETS ARE RESOLVED BY NAME. They used to be typed in as numbers -- VDD2 was 8, GND 2,
    # /CPU/TP2 was 71 -- which is fine until the base board changes underneath them, at
    # which point every one of those literals silently points at a DIFFERENT net and the
    # generator cheerfully routes the clock line into a power plane. On this rebase all
    # eight happen to have kept their numbers, which is exactly the kind of luck that hides
    # the bug rather than preventing it. So: look them up, and fail loudly if one is gone.
    NET = {name: int(num) for num, name in re.findall(r'\n\t\(net (\d+) "([^"]*)"\)', txt)}
    for want in ("GND", "VDD2", "VDD3", "VDD35", "/CPU/CK1",
                 "/CPU/TP2", "/CPU/TP8", "/CPU/TP9"):
        if want not in NET:
            raise AssertionError(
                f"the base board has no net named {want!r}. Every ECO-6 route and every "
                "landing pad is anchored to a net NAME; refusing to guess a number.")
    if "CXC_CLK" in NET:
        raise AssertionError("the base board already declares CXC_CLK -- ECO-6 creates it")
    VDD2_NET = NET["VDD2"]

    def fp_span(ref):
        i = 0
        while True:
            i = txt.find("\n\t(footprint ", i)
            if i < 0:
                raise KeyError(f"{ref}: no such footprint on the board")
            j = txt.find("\n\t)\n", i + 1)
            b = txt[i + 1:j + 4]
            m = re.search(r'\(property "Reference" "([^"]+)"', b)
            if m and m.group(1) == ref:
                return (i + 1, j + 4, b)
            i = j + 1

    def replace_in(ref, old, new, what):
        nonlocal txt
        s, e, b = fp_span(ref)
        n = b.count(old)
        if n != 1:
            raise AssertionError(f"{ref}: {what} -- expected 1x {old!r}, found {n}")
        txt = txt[:s] + b.replace(old, new, 1) + txt[e:]

    # ---------- ECO-6.1  C7 out of the module window -------------------------------
    replace_in("C7", C7_FROM, C7_TO, "C7 relocation")

    # ---------- ECO-6.3  drop the two VDD2 stitching vias under the R landing -------
    for ox, oy in DROP_VIAS:
        pat = re.compile(r"\n\t\(via\n\t\t\(at " + re.escape(f"{ox:g} {oy:g}")
                         + r"\).*?\n\t\)", re.S)
        m = pat.search(txt)
        if not m:
            raise AssertionError(f"via {ox},{oy} not found")
        if f"(net {VDD2_NET})" not in m.group(0):
            raise AssertionError(f"via {ox},{oy} is not on VDD2 -- refusing to drop it")
        txt = txt[:m.start()] + txt[m.end():]

    # ---------- ECO-7  the crystal network is not fitted ----------------------------
    for ref in DNP_REFS:
        replace_in(ref, "(attr smd)", "(attr smd dnp)", "DNP flag")

    # ---------- ECO-8 / ECO-10 / ECO-11  the part swaps ------------------------------
    for ref, field, old, new in ECO8 + ECO10 + ECO11 + ECO12:  # 10/12 empty on this base
        replace_in(ref, f'(property "{field}" "{old}"',
                   f'(property "{field}" "{new}"', f"{field} swap")
    # ---------- the thresholds this board is FOR -------------------------------------
    # These used to be literals. Now they are READ OFF THE BOARD, which is strictly
    # stronger: on the AGBM-01 base these values were ours to set, so asserting our own
    # numbers proved something; on AGBM-02 they are MouseBiteLabs' and INHERITED, so the
    # only assertion worth making is that the board in front of us still produces the
    # thresholds he published. This fails if UPSTREAM drifts, which a literal never would.
    #
    # 2.00 V is the TPS3840DL20's threshold. The targets are his own figures, from the wiki
    # ("The low battery LED turns on when the voltage passes 2.3V ... begins blinking when
    # the voltage passes 2.1V") and from the build guide's Test 4, which sweeps 2 V to 3 V
    # looking for exactly them. See wiki-audit/README.md.
    def rval(ref):
        """The board's Value for a resistor, in ohms."""
        v = re.search(r'\(property "Value" "([^"]+)"', fp_span(ref)[2]).group(1)
        m = re.fullmatch(r"([\d.]+)([kM]?)", v)
        if not m:
            raise AssertionError(f"{ref}: Value {v!r} is not a plain resistance")
        return float(m.group(1)) * {"": 1, "k": 1e3, "M": 1e6}[m.group(2)]

    # THE TWO MAIN RAILS, and a nice piece of self-verification. AGBM-02's converters are
    # twin TPS63802s: U13 makes VOUT3 (R72/R73 on Net-(U13-FB), R72 to VOUT3) and U5 makes
    # VOUT5 (R59/R60 on Net-(U5-FB)) -- both read off the netlist, not assumed.
    #
    # We do not need the datasheet's feedback reference to check these. Solve each divider
    # for the reference that would produce its intended rail:
    #     820k/91k for 5.0 V  ->  0.4995 V
    #     510k/91k for 3.3 V  ->  0.4997 V
    # Two independent dividers agreeing on one reference to 0.04% is not a coincidence, so
    # the reference is 0.5 V and both rails land where they should. Asserting the AGREEMENT
    # is stronger than asserting a number typed in from a PDF: it fails if either divider
    # moves, and it cannot be fooled by a transcription error.
    refs = [rail / (1 + rval(t) / rval(b))
            for t, b, rail in (("R59", "R60", 5.0), ("R72", "R73", 3.3))]
    if abs(refs[0] - refs[1]) > 0.002:
        raise AssertionError(
            f"the two TPS63802 dividers no longer imply one feedback reference: "
            f"VOUT5's says {refs[0]:.4f} V, VOUT3's says {refs[1]:.4f} V. One of them "
            f"moved, so one of the rails is not where this fork thinks it is.")
    vref_tps = sum(refs) / 2
    if not 0.49 < vref_tps < 0.51:
        raise AssertionError(f"implied TPS63802 reference is {vref_tps:.4f} V, not ~0.5 V")

    for name, vref, top, bot, want in (
            ("U10 low-battery trip", 2.00, rval("R3"),  rval("R4"),  2.309),
            ("U17 blink trip",       2.00, rval("R58"), rval("R63"), 2.102)):
        got = vref * (1 + top / bot)
        if abs(got - want) > 0.002:
            raise AssertionError(
                f"{name}: the board's divider gives {got:.4f} V, not the {want} V "
                f"MouseBiteLabs publishes ({top:g} / {bot:g} ohm)")
    # The 555's blink rate, same reasoning. R64 with C44 = 1 uF in the OUT-to-RC astable
    # KiCad's netlist shows (R64 between OUT and the tied TRIG/THRES node): T = 2*ln2*R*C.
    blink = 1.0 / (2 * 0.6931 * rval("R64") * 1e-6)
    if not 3.5 < blink < 3.7:
        raise AssertionError(f"critical-battery blink rate is {blink:.2f} Hz, not ~3.6 Hz")

    # ---------- ECO-9  what a machine cannot place -----------------------------------
    hand = dict(THRU_HOLE_REASONS)
    hand.update(SALVAGE_ONLY)
    derived = set()
    for ref in sorted(hand):
        s, e, bfp = fp_span(ref)
        has_th = '" thru_hole ' in bfp
        if ref not in SALVAGE_ONLY and not has_th:
            raise AssertionError(
                f"{ref}: listed as through-hole but the board has no thru_hole pad. The "
                f"rule is mechanical -- fix the list or the board, do not paper over it.")
        if "(attr " not in bfp:
            raise AssertionError(f"{ref}: no (attr ...) line to extend")
        line_start = bfp.index("(attr ")
        line_end = bfp.index(")", line_start)
        cur = bfp[line_start + 6:line_end].split()
        for flag in ("exclude_from_bom", "exclude_from_pos_files"):
            if flag not in cur:
                cur.append(flag)
        nb = bfp[:line_start] + "(attr " + " ".join(cur) + bfp[line_end:]
        txt = txt[:s] + nb + txt[e:]
        derived.add(ref)
    # Nothing else on the board may carry a through-hole pad and still be machine-placed.
    # This is the rule checking itself: if a future ECO adds a through-hole part, the
    # build fails here rather than quietly shipping a CPL a machine cannot execute.
    i2 = 0
    stragglers = []
    while True:
        i2 = txt.find("\n\t(footprint ", i2)
        if i2 < 0:
            break
        j2 = txt.find("\n\t)\n", i2 + 1)
        bfp = txt[i2 + 1:j2 + 4]
        m2 = re.search(r'\(property "Reference" "([^"]+)"', bfp)
        am = re.search(r"\(attr ([^)]*)\)", bfp)
        flags = set(am.group(1).split()) if am else set()
        if (m2 and '" thru_hole ' in bfp and "dnp" not in flags
                and "exclude_from_pos_files" not in flags and "*" not in m2.group(1)):
            stragglers.append(m2.group(1))
        i2 = j2 + 1
    if stragglers:
        raise AssertionError(
            "footprint(s) with a through-hole pad are still in the position file: "
            + ", ".join(sorted(stragglers))
            + " -- add them to THRU_HOLE_REASONS, or mark them DNP.")

    # ---------- ECO-6.4  the new footprints ----------------------------------------
    ghost = "".join(f'''\t\t(fp_circle
\t\t\t(center {cx} {cy})
\t\t\t(end {cx + 0.635} {cy})
\t\t\t(stroke (width 0.1) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid(f'ghost{k}')}")
\t\t)
''' for k, (cx, cy) in enumerate(GHOSTS))
    labels = "".join(f'''\t\t(fp_text user "{lab}"
\t\t\t(at {lx} {ly} 180)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('lbl' + lab)}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 0.7 0.7)
\t\t\t\t\t(thickness 0.12)
\t\t\t\t)
\t\t\t)
\t\t)
''' for lab, lx, ly in LABELS)
    padblocks = "".join(f'''\t\t(pad "{num}" smd circle
\t\t\t(at {x} {y} 180)
\t\t\t(size 1.27 1.27)
\t\t\t(layers "F.Cu" "F.Mask")
\t\t\t(solder_mask_margin 0.0635)
\t\t\t(net {net} "{nm}")
\t\t\t(pintype "passive")
\t\t\t(uuid "{uid('modpad' + num)}")
\t\t)
''' for num, x, y, net, nm, _lab in PADS)
    MOD = f'''\t(footprint "ClockxControl_GBA_GBC"
\t\t(layer "F.Cu")
\t\t(uuid "{uid('mod1')}")
\t\t(at {MOD_X} {MOD_Y} 180)
\t\t(descr "insideGadgets GBA/GBC ClockxControl mezzanine landing pattern. Module floats flat on this footprint; its plated through-hole pads are filled with solder from above to bond it to these pads. Geometry from MouseBiteLabs DMGC-CPU-01 rev 2.5.")
\t\t(tags "clockxcontrol insidegadgets mezzanine")
\t\t(attr smd exclude_from_bom exclude_from_pos_files)
\t\t(property "Reference" "MOD1"
\t\t\t(at 0 -7.4 180)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('modref')}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1 1)
\t\t\t\t\t(thickness 0.15)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Value" "ClockxControl"
\t\t\t(at 0 7.4 180)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid('modval')}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1 1)
\t\t\t\t\t(thickness 0.15)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(fp_text user "CLOCKXCONTROL"
\t\t\t(at 0 0 180)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('modtext')}")
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.05 1.05)
\t\t\t\t\t(thickness 0.2)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(fp_rect
\t\t\t(start -9.325 -6)
\t\t\t(end 9.325 6)
\t\t\t(stroke (width 0.2) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('modsilk')}")
\t\t)
\t\t(fp_rect
\t\t\t(start -9.325 -6)
\t\t\t(end 9.325 6)
\t\t\t(stroke (width 0.1) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid('modfab')}")
\t\t)
\t\t(fp_rect
\t\t\t(start -9.575 -6.25)
\t\t\t(end 9.575 6.25)
\t\t\t(stroke (width 0.05) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.CrtYd")
\t\t\t(uuid "{uid('modcrt')}")
\t\t)
{ghost}{labels}{padblocks}\t\t(embedded_fonts no)
\t)
'''

    def tp(ref, x, y, dia, net, netname, silk, val, sx=0.0, sy=1.5):
        return f'''\t(footprint "Bucketmouse:TestPoint_Pad_D1.0mm"
\t\t(layer "F.Cu")
\t\t(uuid "{uid('fp' + ref)}")
\t\t(at {x} {y})
\t\t(descr "ClockxControl mezzanine landing - position is photo-derived, verify against a physical module")
\t\t(tags "clockxcontrol landing")
\t\t(attr exclude_from_bom)
\t\t(property "Reference" "{ref}"
\t\t\t(at 0 -1.6 0)
\t\t\t(layer "F.SilkS")
\t\t\t(hide yes)
\t\t\t(uuid "{uid('ref' + ref)}")
\t\t\t(effects (font (size 1 1.1) (thickness 0.175)))
\t\t)
\t\t(property "Value" "{val}"
\t\t\t(at 0 1.6 0)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid('val' + ref)}")
\t\t\t(effects (font (size 1 1.1) (thickness 0.175)))
\t\t)
\t\t(fp_text user "{silk}"
\t\t\t(at {sx} {sy} 0)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('silk' + ref)}")
\t\t\t(effects (font (size 0.7 0.7) (thickness 0.12)))
\t\t)
\t\t(pad "1" smd circle
\t\t\t(at 0 0)
\t\t\t(size {dia} {dia})
\t\t\t(layers "F.Cu" "F.Mask")
\t\t\t(net {net} "{netname}")
\t\t\t(pintype "passive")
\t\t\t(uuid "{uid('pad' + ref)}")
\t\t)
\t\t(embedded_fonts no)
\t)
'''

    # (A TP82 'CXC V- wire' landing at (102, -41) was drafted here and NEVER SPLICED
    # into the board -- the original generator built the block and then left it out of
    # the final concatenation. Consistency check [9] found it by looking for a
    # footprint its own placement snapshot named. Dead code deleted 2026-08-19 rather
    # than revived: TP85 already lands V- 1.0 mm from the module edge, and a second
    # GND pad 4 mm further east buys nothing.)


    # ---------- ECO-6.2  fiducials, because a machine needs to see the board ---------
    FIDS = "".join(f'''\t(footprint "Fiducial:Fiducial_1mm_Mask2mm"
\t\t(layer "{lay}")
\t\t(uuid "{uid('fid' + ref)}")
\t\t(at {x} {y})
\t\t(descr "Optical registration target for pick-and-place. Not a MouseBiteLabs part -- neither AGBM-01 nor AGBM-02 carries fiducials, because he hand-builds.")
\t\t(tags "fiducial")
\t\t(attr exclude_from_bom exclude_from_pos_files)
\t\t(property "Reference" "{ref}"
\t\t\t(at 0 -1.6 0)
\t\t\t(layer "{'F' if lay == 'F.Cu' else 'B'}.SilkS")
\t\t\t(hide yes)
\t\t\t(uuid "{uid('fidref' + ref)}")
\t\t\t(effects (font (size 1 1) (thickness 0.15)))
\t\t)
\t\t(property "Value" "Fiducial"
\t\t\t(at 0 1.6 0)
\t\t\t(layer "{'F' if lay == 'F.Cu' else 'B'}.Fab")
\t\t\t(hide yes)
\t\t\t(uuid "{uid('fidval' + ref)}")
\t\t\t(effects (font (size 1 1) (thickness 0.15)))
\t\t)
\t\t(pad "1" smd circle
\t\t\t(at 0 0)
\t\t\t(size 1 1)
\t\t\t(layers "{lay}" "{'F' if lay == 'F.Cu' else 'B'}.Mask")
\t\t\t(solder_mask_margin 0.5)
\t\t\t(uuid "{uid('fidpad' + ref)}")
\t\t)
\t\t(embedded_fonts no)
\t)
''' for ref, x, y, lay in FIDUCIALS)

    # ---------- ECO-6.5  the CXC_CLK net -------------------------------------------
    mnet = max(int(n) for n in re.findall(r'\n\t\(net (\d+) "', txt))
    NEWNET = mnet + 1
    lastnet = list(re.finditer(r'\n\t\(net \d+ "[^"]*"\)', txt))[-1]
    txt = txt[:lastnet.end()] + f'\n\t(net {NEWNET} "CXC_CLK")' + txt[lastnet.end():]

    NET["CXC_CLK"] = NEWNET
    NETNO = NET
    LANDINGS = "".join(
        tp(ref, x, y, 1.2, NETNO[net], net, silk, val, sx=0.0, sy=1.35)
        for ref, x, y, net, silk, val in WIRE_PADS)

    JP4 = f'''\t(footprint "CXC:SolderJumper_2_Open"
\t\t(layer "F.Cu")
\t\t(uuid "{uid('jp4')}")
\t\t(at 45 -64.2)
\t\t(descr "CK1 isolation jumper for the ClockxControl CLK run. Numbered JP4 because JP2 and JP3 are MouseBiteLabs' own RAM straps on AGBM-02. LEAVE OPEN for a crystal build; BRIDGE when populating the ClockxControl.")
\t\t(tags "solder jumper open")
\t\t(attr smd exclude_from_bom)
\t\t(property "Reference" "JP4"
\t\t\t(at 0 -1.6 0)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('jp4ref')}")
\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15)))
\t\t)
\t\t(property "Value" "CXC CLK"
\t\t\t(at 0 1.7 0)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "{uid('jp4val')}")
\t\t\t(effects (font (size 0.8 0.8) (thickness 0.15)))
\t\t)
\t\t(fp_rect
\t\t\t(start -1.35 -0.95)
\t\t\t(end 1.35 0.95)
\t\t\t(stroke (width 0.12) (type solid))
\t\t\t(fill no)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "{uid('jp4silk')}")
\t\t)
\t\t(pad "1" smd circle
\t\t\t(at -0.65 0)
\t\t\t(size 1.05 1.05)
\t\t\t(layers "F.Cu" "F.Mask")
\t\t\t(net {NET["/CPU/CK1"]} "/CPU/CK1")
\t\t\t(pintype "passive")
\t\t\t(uuid "{uid('jp4p1')}")
\t\t)
\t\t(pad "2" smd circle
\t\t\t(at 0.65 0)
\t\t\t(size 1.05 1.05)
\t\t\t(layers "F.Cu" "F.Mask")
\t\t\t(net {NEWNET} "CXC_CLK")
\t\t\t(pintype "passive")
\t\t\t(uuid "{uid('jp4p2')}")
\t\t)
\t\t(embedded_fonts no)
\t)
'''

    # ---------- ECO-6.6  copper ----------------------------------------------------
    E, X = R["eco6"], R["eco6_extra"]
    segs, vias = [], []

    def add(net, runs, vs=()):
        for lay, pts in runs:
            for i in range(len(pts) - 1):
                if pts[i] == pts[i + 1]:
                    continue
                segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], lay, net))
        for (vx, vy) in vs:
            vias.append((vx, vy, net))

    # routes.json keys the three button landings by the net NUMBER they had on the
    # AGBM-01 base. Map each through the name it stood for, so the file stays readable
    # and the number stops being load-bearing.
    for key, netname in (("12", "/CPU/TP8"), ("71", "/CPU/TP2"), ("13", "/CPU/TP9")):
        if NET[netname] != int(key):
            raise AssertionError(
                f"routes.json calls {netname} net {key}; this base says {NET[netname]}. "
                "Re-key routes.json before trusting these runs.")
        add(NET[netname], E[key]["runs"], E[key]["vias"])
    add(NEWNET, E["CXC_CLK"]["runs"], E["CXC_CLK"]["vias"])
    add(NEWNET, [("F.Cu", [[97.9, -38.6], [97.9, -37.95]])])   # tail to the moved pad row
    vdd3 = [list(r) for r in E["VDD3"]["runs"]]
    vdd3[0] = ("F.Cu", [[99.45, -37.95], [99.25, -37.85], [99.25, -35.9]])
    add(NET["VDD3"], vdd3, E["VDD3"]["vias"])
    add(NET["GND"], [("F.Cu", [[101.0, -37.95], [100.2, -37.15], [100.2, -35.3]])])
    add(NET["VDD35"], [("F.Cu", [[93.875, -37.4], [93.5, -37.2]])])   # C7's VDD35 pad
    add(NET["GND"], [("F.Cu", [[92.325, -37.4], [93.3, -38.7]])], [(93.3, -38.7)])
    add(NET["/CPU/CK1"], X["CK1"]["runs"], X["CK1"]["vias"])                 # JP4 pad 1 -> crystal node

    seg_txt = "".join(f'''\t(segment
\t\t(start {x0} {y0})
\t\t(end {x1} {y1})
\t\t(width 0.25)
\t\t(layer "{lay}")
\t\t(net {n})
\t\t(uuid "{uid(f'seg{i}')}")
\t)
''' for i, (x0, y0, x1, y1, lay, n) in enumerate(segs))
    via_txt = "".join(f'''\t(via
\t\t(at {x} {y})
\t\t(size 0.7)
\t\t(drill 0.3)
\t\t(layers "F.Cu" "B.Cu")
\t\t(net {n})
\t\t(uuid "{uid(f'via{i}')}")
\t)
''' for i, (x, y, n) in enumerate(vias))

    k = txt.rstrip().rfind("\n)")
    if k <= 0:
        raise AssertionError("board has no closing paren")
    txt = txt[:k + 1] + MOD + LANDINGS + FIDS + JP4 + seg_txt + via_txt + txt[k + 1:]
    return txt, dict(orig_len=orig_len, new_len=len(txt), segs=len(segs),
                     vias=len(vias), net=NEWNET, hand=sorted(derived))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="build in memory and diff against the shipped board; write nothing")
    ap.add_argument("-o", "--out", default=OUT)
    a = ap.parse_args()
    txt, st = build()
    print(f"built {st['orig_len']} -> {st['new_len']} chars "
          f"(+{st['new_len'] - st['orig_len']}); {st['segs']} segments, {st['vias']} vias, "
          f"6 footprints, net {st['net']} CXC_CLK; "
          f"hand-solder set {', '.join(st['hand'])}")
    if a.check:
        try:
            want = zipfile.ZipFile(SHIPPED_ZIP).read(SHIPPED_MEMBER).decode("utf-8")
        except (OSError, KeyError) as e:
            sys.exit(f"FAIL: cannot read the shipped board -- {type(e).__name__}: {e}")
        if txt == want:
            print("ok: rebuild is byte-identical to the shipped board")
            return 0
        sys.exit(f"FAIL: rebuild differs from the shipped board "
                 f"({len(txt)} vs {len(want)} chars). Regenerate and repack, or explain "
                 f"the difference in the ECO that made it.")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
