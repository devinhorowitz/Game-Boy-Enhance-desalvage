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

    AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip
                                MouseBiteLabs' AGBM-02, UNMODIFIED. His newest board.
    scripts/routes.json         the frozen ECO-6 routing
    the ECO tables below        every deliberate edit, one line each

and its output is byte-identical to `AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb` inside
`clockxcontrol-integration/board/agbm-02-clockxcontrol.zip`. Consistency check [1] asserts
exactly that, which is what makes the ECO documents auditable rather than decorative.

WHAT IT DOES, IN ECO ORDER

    ECO-6  move C7 out of the module window; ADD six fiducials (MouseBiteLabs ships
           none -- he hand-builds); drop the two VDD2 stitching vias the R landing lands
           on; add the ClockxControl land pattern, the three wire pads (TP83/84/85) and
           the CK1 isolation jumper JP4 -- JP4 and not JP3, because JP2 and JP3 are HIS
           RAM straps on AGBM-02; add the CXC_CLK net and route everything.
    ECO-7  mark X1/C3/C4 DNP -- the ClockxControl drives CK1 directly, so an assembly
           house must not fit the crystal or its load caps.
    ECO-8  eleven Value/Description edits from the power review. No copper. Three of
           the original thirteen are already done upstream on AGBM-02 -- see ECO-13.
    ECO-9  mark the parts a pick-and-place cannot handle `exclude_from_bom` +
           `exclude_from_pos_files`, so the board itself says what a machine can buy
           and place. No copper either -- attributes only.
    ECO-10 the precision pass. On AGBM-02 it changes NO Value -- its LTC3527 divider
           work went with the LTC3527; its part-number work lives in mpn_overrides.json.
    ECO-12 the wiki audit. Also NO Value on this base: AGBM-02 already carries the
           R3/R4/R64 the AGBM-01 PCB had stale.
    ECO-13 the rebase itself.
    ECO-14 the ClockxControl audit on the new base -- and the open question that the
           module is powered at VDD3 = 3.3 V while the pin it drives sits in the
           VDD2 = 2.5 V domain.
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
import textwrap
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
FOOTPRINT_OUT = os.path.join(ROOT, "clockxcontrol-integration", "footprint",
                             "ClockxControl_GBA_GBC.kicad_mod")

# --- ECO-6 geometry ------------------------------------------------------------------
# The module body is 18.65 x 12.00 mm; MOD_X/MOD_Y is its centre. rev B moved it west out
# of the R3/TP114 cluster -- ECO-6 section 6.7 is the accounting for what that cost.
MOD_X, MOD_Y = 91.95, -44.95
C7_FROM, C7_TO = "(at 91.9 -41.1 180)", "(at 93.1 -37.4 180)"

# --- ECO-19: the stock C7 land comes back, unpopulated ---------------------------------
# ECO-6 moved C7 out of the module window because it was the one part standing in it. That
# made this board a SIDE-GRADE rather than an upgrade: third-party mods that solder to C7
# where it has always been lose their landmark, and a board that gains an overclocker by
# giving up compatibility with everything else is a trade, not an improvement.
#
# C7 sits at (91.9, -41.1) on AGBM-01 AND on AGBM-02 -- byte-identical across two revisions
# of MouseBiteLabs' own design, per wiki-audit/README.md. A position that stable is exactly
# what an outside mod keys off.
#
# So the land goes back, DNP, as `C7A`. Three facts make this nearly free:
#
#   1. ECO-6 §6.1: "C7 had no tracks attached on the original board -- both pads were fed by
#      pours". Restoring the land needs NO routing. The VDD35 and GND pours already cover
#      both pad centres -- verified against the stored fill.
#   2. The nearest copper THIS FORK adds is 2.778 mm away. Nothing to clear.
#   3. DNP means ECO-17 strips its paste automatically, so no aperture lands under a module.
#
# THE TWO ARE MUTUALLY EXCLUSIVE AND THAT IS THE POINT. C7A's land is 2.15 mm inside MOD1's
# body, so a POPULATED 0603 there fouls a module lying on the board. Populate C7 (the moved
# one) for a ClockxControl build, or C7A for a stock build that needs the landmark -- never
# both. Bare, the land is copper and mask, flush with everything else the module already
# sits over: 25 of MouseBiteLabs' own vias are under that body already.
C7A_REF = "C7A"
DROP_VIAS = [(84.4, -45.9), (85.4, -45.9)]          # both on VDD2
# FIDUCIALS ARE OURS, NOT MOUSEBITELABS'. Neither AGBM-01 nor AGBM-02 carries a single
# one -- he hand-builds, and a hand builder does not need optical registration. A
# pick-and-place does, so ECO-9's whole premise needs them. ECO-5 added six and ECO-6 then
# moved a pair out from under the module; on this base they are simply placed clear of it
# to begin with. Three per side in a deliberately asymmetric triangle so the machine cannot
# register the panel 180 degrees out. Each spot was clearance-checked against AGBM-02.
# ECO-14 placed all six and ECO-20 replaced them, because ECO-14's search was blind in
# four directions at once and said so with confidence. It modelled HARD COPPER -- tracks,
# vias, pads -- and nothing else, so it never saw:
#   * Edge.Cuts circles. 13 of this board's outline items are gr_circle -- the shell's
#     screw and standoff holes -- and two more are fp_circle INSIDE SW1 and VR2, routed
#     openings for the switch shaft and the volume wheel. FID2/FID5 landed inside the
#     1.2 mm hole at (110.91, -56.85) and FID3/FID6 straddled the rim of the one at
#     (30.50, -70.68), while ECO-14 wrote "each is >= 3.0 mm from the board edge".
#   * this board's 64 keepout zones -- four of which are drawn as a single full-circle arc
#     carrying no (xy) vertex at all. FID1 and FID2 sat inside two of them.
#   * soldermask apertures. FID1's 2 mm window merged with BT1's, the battery terminal:
#     seven bridge violations and 0.000 mm to BT1's plated GND pad, 4.5 mm from the
#     fiducial centre, because that terminal's pad is nothing like a circle. The two
#     7.5 x 5 mm B.Mask polygons over the cartridge contacts are the same trap on the back.
#   * that a mark on the FRONT does not care what the BACK is doing. ECO-14 kept the six
#     as three coincident pairs, so every site had to be clear on both layers at once.
#     Dropping that gives the search 3,655 legal front sites and 6,324 back ones instead
#     of 492, and none of the six spots below is legal on the other side -- the pairs were
#     costing real margin for nothing. Front and back register independently anyway.
# KiCad's own DRC found every one of these the first time it was run, in ECO-19. The spots
# below come from a search that models all of it, and each was confirmed by re-running that
# DRC. Margins in mm -- "(none)" means nothing of that kind within 9 mm:
#     FID1  (100.50,  -3.50) F   edge 3.12  keepout (none)  copper 2.26  mask (none)  crtyd (none)
#     FID2  (103.75, -58.50) F   edge(none) keepout (none)  copper 1.84  mask (none)  crtyd 2.22
#     FID3  ( 24.25, -55.75) F   edge 2.94  keepout  2.71   copper 2.00  mask (none)  crtyd 4.58
#     FID4  (127.75, -19.50) B   edge 3.31  keepout  4.59   copper 2.26  mask (none)  crtyd (none)
#     FID5  ( 94.75, -66.50) B   edge 2.85  keepout (none)  copper 1.80  mask (none)  crtyd 2.72
#     FID6  ( 11.50, -16.00) B   edge 3.58  keepout (none)  copper 2.15  mask (none)  crtyd 5.84
# "copper" is the clear radius from centre to the nearest track, via or pad ON THAT LAYER;
# the mask window is 1.0 mm, so all six show bare substrate right out to the aperture.
# Both triangles stay deliberately scalene, so a machine cannot register the panel 180
# degrees out: front 55.1/79.5/92.4 mm and 2182 mm2, back 57.4/97.4/116.3 mm and 2790 mm2.
# These are not hand-picked. `python3 scripts/place_fiducials.py --grid 0.25` prints exactly
# these six, and prints them again from the board they are already on -- the search skips
# the fiducials, so it does not chase its own tail. check [13] recomputes all thirty numbers
# in the table above and fails if any of them moves by more than 5 um.
FIDUCIALS = [("FID1", 100.5, -3.5, "F.Cu"), ("FID2", 103.75, -58.5, "F.Cu"),
             ("FID3", 24.25, -55.75, "F.Cu"), ("FID4", 127.75, -19.5, "B.Cu"),
             ("FID5", 94.75, -66.5, "B.Cu"), ("FID6", 11.5, -16.0, "B.Cu")]
# The three button landings the module's plated through-holes solder down onto.
# Net NAMES, not numbers. The numbers used to be literals here (71/13/12) and were the
# last place in this file where a net was named by its number -- WIRE_PADS and JP4 both go
# through NET[]. On the AGBM-02 rebase all three happened to keep their numbers, which is
# the kind of luck that hides a bug rather than preventing it: had one moved, the module's
# L button would have soldered onto whatever net inherited 13.
PADS = [("1", 4.525, 1.0, "/CPU/TP2", "SEL"),
        ("2", 7.025, 3.5, "/CPU/TP9", "L"),
        ("3", 7.025, 1.0, "/CPU/TP8", "R")]
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


# --- ECO-17: solder paste must agree with the placement list -------------------------
# ECO-9 encoded WHO PLACES WHAT in the board's attributes. The paste layer never got the
# memo. A stencil is cut from F.Paste/B.Paste and knows nothing about `dnp` or
# `exclude_from_pos_files`, so paste is deposited on every aperture and reflowed whether a
# part lands on it or not. On this board that was 194 pads across twelve parts nobody
# places:
#
#   U1   128 pads. The SALVAGED CPU, hand-fitted after the reflow. 128 apertures at 0.5 mm
#        pitch reflow into 128 solder bumps on a fine-pitch land, which then has to be
#        wicked clean before the CPU it was meant for can be seated.
#   SW4/SW5/SW6  the A/B, Start-Select and D-pad footprints. These are DUAL-PURPOSE: each
#        carries the Alps tact-switch land AND THE MEMBRANE CONTACT PADS. A default build
#        uses the rubber membrane, so they are `dnp` -- and paste on a membrane contact
#        reflows into a bump on the flat gold surface the rubber pad has to sit on. This
#        is the one that actually ruins a board.
#   P3, VR2   hand-soldered, so their SMD pads get bumps too.
#   C3, C4, X1   the crystal network ECO-7 marks DNP for ClockxControl builds.
#   JP1   a solder jumper that is meant to be OPEN. Paste bridges it CLOSED on reflow.
#   R70, R71   DNP.
#
# THE RULE IS MECHANICAL, like ECO-9's: a pad keeps its paste aperture only if the machine
# is going to put a part on it. "Not placed" is read off the board -- `dnp` or
# `exclude_from_pos_files` -- never from a hand-list here.
PASTE_KEEP_NOTES = {
    "MOD1": "no paste to begin with: its plated holes are filled from above onto the pads "
            "below, which is why ECO-9 makes it hand-solder in the first place",
    "SP1":  "no paste to begin with, two through-hole pads",
}

# --- ECO-17b: U2 carries TWO nested land patterns, and only one may be pasted ---------
# MouseBiteLabs' `AGB-SRAM_2` is a dual land: every one of the 48 pins has TWO pads on the
# same net, an inner and an outer, so one footprint accepts either RAM.
#
#   INNER  centres +/-6.690 / +7.100, tip span 15.34 mm -> TSOP-I-48 12.4x12mm, the
#          SALVAGED OEM AGB-SRAM.
#   OUTER  centres -8.450 / +10.967, tip span 20.950 mm -> TSOP-I-48 18.4x12mm. Identical
#          to three decimals to KiCad's own TSOP-I-48_18.4x12mm_P0.5mm, which is the
#          package Digi-Key lists for the CY62157EV30LL-45ZXIT ("48-TSOP I").
#
# Pasting both is not a redundant belt-and-braces: the inner pads of ADJACENT PINS sit
# 0.5 mm apart with a 0.2 mm gap and carry DIFFERENT nets (MA15, MA14, ...). Paste on the
# unused pattern reflows UNDER THE BODY of the chip that is fitted, where a bridge between
# two address lines cannot be inspected and cannot be reworked.
#
# So exactly one pattern is pasted, chosen by which RAM the BOM buys. Flip this and the
# JP2/JP3 straps together -- MouseBiteLabs' wiki: both bridged for the CY62157EV30LL, both
# left open for a salvaged OEM part.
RAM_FITTED = "CY62157EV30LL"          # or "salvage" for an OEM AGB-SRAM off a donor board
U2_PATTERN_X = {                       # pad centre x -> which RAM that column belongs to
    -6.690: "salvage",  7.100: "salvage",
    -8.450: "CY62157EV30LL", 10.9675: "CY62157EV30LL",
}
# ...and the BODY has to match the land, or every assembled render shows the wrong chip.
# The footprint origin is not the package centre for either pattern, so the model carries
# an offset: the midpoint of the two columns it belongs to.
U2_MODEL = {
    "salvage":       ("TSOP-I-48_12.4x12mm_P0.5mm", (-6.690 + 7.100) / 2),
    "CY62157EV30LL": ("TSOP-I-48_18.4x12mm_P0.5mm", (-8.450 + 10.9675) / 2),
}


def strip_paste(block, only_x=None):
    """Drop F.Paste/B.Paste from a footprint block's pads. Returns (block, pads_changed).

    `only_x` limits the strip to pads whose local x is in that set, which is how U2's
    unused land pattern is cleared without touching the one being fitted.

    A PASTE-ONLY PAD IS DELETED, NOT EMPTIED. SW6 carries an unnamed `smd circle` on
    `"F.Paste"` and nothing else -- a bare stencil dot with no copper under it. Taking the
    paste layer off that leaves `(layers )`, a pad on no layer at all, which is meaningless
    and which KiCad is under no obligation to keep. If the aperture is the whole pad, the
    pad goes with it.

    Walks pad blocks with balanced parens. The bounded-regex version silently skips a
    `custom` pad whose primitives run long -- and SW4/SW5/SW6, the three footprints this
    exists to clear, are exactly the ones built from custom pads.
    """
    spans = []
    for m in re.finditer(r'\(pad "', block):
        i, d = m.start(), 0
        for j in range(i, len(block)):
            if block[j] == "(":
                d += 1
            elif block[j] == ")":
                d -= 1
                if d == 0:
                    spans.append((i, j + 1))
                    break
    out, last, n = [], 0, 0
    for a, b in spans:
        blk = block[a:b]
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)", blk)
        lay = re.search(r"\(layers ([^)]*)\)", blk)
        if not at or not lay:
            continue
        if only_x is not None and round(float(at.group(1)), 4) not in only_x:
            continue
        keep = [t for t in lay.group(1).split() if "Paste" not in t]
        if len(keep) == len(lay.group(1).split()):
            continue
        before = block[last:a]
        if keep:
            out.append(before)
            out.append(blk[:lay.start(1)] + " ".join(keep) + blk[lay.end(1):])
        else:
            # Paste-only pad: the aperture IS the pad, so drop the whole thing along with
            # the newline and indent that led into it, or the file gains a blank line.
            out.append(before.rstrip("\t").rstrip("\n"))
        last = b
        n += 1
    out.append(block[last:])
    return "".join(out), n


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
    # Take the block BEFORE the move: that copy is the stock land, in its stock place.
    _s7, _e7, c7_stock = fp_span("C7")
    replace_in("C7", C7_FROM, C7_TO, "C7 relocation")

    # ---------- ECO-19  and put the stock land back, unpopulated --------------------
    c7a = c7_stock
    if C7_FROM not in c7a:
        raise AssertionError(f"C7's block does not carry {C7_FROM} -- it has moved upstream")
    # Board-only, like MOD1/JP4/TP83/FID*: no (path/sheetname/sheetfile), or KiCad sees two
    # footprints claiming one schematic symbol and the next netlist import fights over it.
    c7a = re.sub(r'\n\t\t\(path "[^"]*"\)', "", c7a)
    c7a = re.sub(r'\n\t\t\(sheet(name|file) "[^"]*"\)', "", c7a)
    c7a = c7a.replace('(property "Reference" "C7"', f'(property "Reference" "{C7A_REF}"', 1)
    c7a = c7a.replace('(property "Value" "0.1u"',
                      '(property "Value" "0.1u DNP-alt"', 1)
    if "\n\t\t(attr smd)" not in c7a:
        raise AssertionError("C7's (attr smd) line is not where ECO-19 expects it")
    c7a = c7a.replace("\n\t\t(attr smd)",
                      "\n\t\t(attr smd dnp exclude_from_bom exclude_from_pos_files)", 1)
    # Every uuid must be new AND deterministic -- a duplicate makes the file invalid, and a
    # random one makes check [1] impossible.
    seen_u = re.findall(r'\(uuid "([0-9a-f-]+)"\)', c7a)
    for k, u in enumerate(seen_u):
        c7a = c7a.replace(f'(uuid "{u}")', f'(uuid "{uid(f"c7a:{k}:{u}")}")', 1)
    if len(re.findall(r'\(uuid "', c7a)) != len(seen_u):
        raise AssertionError("ECO-19 lost a uuid while re-stamping C7A")
    C7A_BLOCK = c7a

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
''' for num, x, y, nm, _lab in PADS for net in (NET[nm],))
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

    # ECO-14: these carry `exclude_from_pos_files` as well as `exclude_from_bom`. They are
    # WIRE PADS and a SOLDER JUMPER -- a human tins them and lands a wire, and no
    # pick-and-place operation touches either. The generated CPL was already correct without
    # the flag, but only because bom_split.py happens to key off `exclude_from_bom`; the
    # BOARD said something different from what the CPL did, and MouseBiteLabs' own
    # equivalents (TP18, TP80) carry the flag. Now the board says what it means.
    def tp(ref, x, y, dia, net, netname, silk, val, sx=0.0, sy=1.5):
        return f'''\t(footprint "Bucketmouse:TestPoint_Pad_D1.0mm"
\t\t(layer "F.Cu")
\t\t(uuid "{uid('fp' + ref)}")
\t\t(at {x} {y})
\t\t(descr "ClockxControl mezzanine landing - position is photo-derived, verify against a physical module")
\t\t(tags "clockxcontrol landing")
\t\t(attr exclude_from_bom exclude_from_pos_files)
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
    # The (clearance 0.55) on each pad is load-bearing, not decoration. These pads are
    # NETLESS and they sit inside MouseBiteLabs' GND pours; on a re-pour the zone floods
    # right up to them, leaving copper 0.5 + zone_clearance = 0.7 mm from centre -- INSIDE
    # the 1.0 mm mask window (0.5 mm pad + 0.5 mm mask margin). 0.55 mm of local clearance
    # pushes the pour back to 1.05 mm, so the window shows bare substrate and the fiducial
    # is actually readable. Without it, relocating them would have fixed nothing.
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
\t\t\t(clearance 0.55)
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
\t\t(attr smd exclude_from_bom exclude_from_pos_files)
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
    # ---------- ECO-22  the VDD3 tail loses a via it never needed --------------------
    # ECO-6 brought VDD3 across on B.Cu, punched a via at (97.1, -34.1), and ran the last
    # 1.3 mm to P1 pad S1 on F.Cu. That via's DRILL sits 0.4680 mm from S1's own 1.0 mm
    # hole, against MouseBiteLabs' 0.5 mm min_hole_to_hole -- 32 microns short, a DRILL
    # rule, so being on the same net buys nothing. Nothing in this repository had ever
    # seen it: check_drc.py wrote the board to a temp directory with NO PROJECT FILE, so
    # KiCad fell back to its own defaults, where min_hole_to_hole is 0.25.
    #
    # P1 pad S1 is `thru_hole` on `*.Cu`. It is already on every layer, so the B.Cu run
    # can land on it directly and the via is redundant. Measured along the new corridor
    # (97.4, -34.4) -> (96.9, -35.2):
    #     B.Cu  0.8260 mm to the nearest foreign copper (seg VDD5)
    #     F.Cu  0.1679 mm -- which is why ECO-6 went to F.Cu at all, and it was the
    #           wrong trade: it bought 0.30 mm of track clearance for a drill collision.
    # Moving the via instead needs ~0.8 mm of travel to find a legal spot, and the best
    # one clears by 8 microns. Deleting a hole beats relocating one.
    vdd3[1] = ("B.Cu", vdd3[1][1][:-1] + [[96.9, -35.2]])
    del vdd3[2]
    add(NET["VDD3"], vdd3, [v for v in E["VDD3"]["vias"] if list(v) != [97.1, -34.1]])
    add(NET["GND"], [("F.Cu", [[101.0, -37.95], [100.2, -37.15], [100.2, -35.3]])])
    add(NET["VDD35"], [("F.Cu", [[93.875, -37.4], [93.5, -37.2]])])   # C7's VDD35 pad
    add(NET["GND"], [("F.Cu", [[92.325, -37.4], [93.3, -38.7]])], [(93.3, -38.7)])
    add(NET["/CPU/CK1"], X["CK1"]["runs"], X["CK1"]["vias"])                 # JP4 pad 1 -> crystal node

    # ---------- ECO-20  U1 pad 39 gets its ground back ------------------------------
    # MouseBiteLabs' board has ZERO unconnected pads. This fork shipped one, and it was
    # ours: the CPU's pin 39 is a GND pin fed by nothing but the F.Cu pour, and ECO-6's
    # /CPU/TP8 route walks diagonally past its lower-left corner on the way to MOD1.
    #
    #     TP8 copper to pad 39 copper, closest approach : 0.3594 mm at (73.372, -46.628)
    #     what a pour sliver needs to survive there     : 0.2 (zone clearance to TP8)
    #                                                   + 0.2 (the zone's min_thickness)
    #                                                   = 0.400 mm
    #
    # Forty-one microns short. The fill still puts copper on the pad -- KiCad keeps an
    # island that touches a pad -- so the pad LOOKS connected in a render and is not
    # attached to anything else on the board. Widening the corridor is not available:
    # on TP8's other flank the Net-(RA1A-R1.1) track is 0.2644 mm away against a 0.2 mm
    # rule, so there is 0.064 mm of slack to give, and the prize would be a 0.2 mm hair
    # of pour as a CPU ground return. B.Cu under the pad is three tracks at 0.201 mm
    # pitch, so there is no via site either.
    #
    # So the connection stops depending on the pour. 2.37 mm of F.Cu from pin 39 to C15
    # pad 2 -- the ground side of the CPU's own decoupling cap, and the nearest GND
    # copper that is unambiguously part of the plane. Clearance to pad 40, the tightest
    # thing it passes, is 0.225 mm. Verified by KiCad's DRC: unconnected 1 -> 0, with no
    # new violation anywhere on the board.
    add(NET["GND"], [("F.Cu", [[74.34, -47.12], [76.7, -46.925]])])

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
    txt = (txt[:k + 1] + MOD + LANDINGS + FIDS + JP4 + C7A_BLOCK
           + seg_txt + via_txt + txt[k + 1:])

    # ORDER MATTERS, AND IT USED TO BE WRONG. This block ran BEFORE the new footprints
    # were spliced in, so anything added afterwards escaped the rule entirely -- and its
    # own self-check passed, because at that point the offender did not exist yet. MOD1,
    # JP4, TP83-85 and the fiducials happen to carry no paste by construction, so nothing
    # showed until ECO-19 added C7A: a DNP land that came through with both apertures
    # intact. A rule about the finished board has to run on the finished board.
    # ---------- ECO-17  paste follows the placement list ------------------------------
    # ONE PASS over spans collected up front, then a rebuild. An earlier version walked and
    # spliced in the same loop and its indices drifted after each replacement, which made
    # the walk skip a footprint -- SW4, the A/B buttons, still holding all sixteen
    # apertures. The self-check below is what said so.
    if RAM_FITTED not in set(U2_PATTERN_X.values()):
        raise AssertionError(f"RAM_FITTED={RAM_FITTED!r} is not one of "
                             f"{sorted(set(U2_PATTERN_X.values()))}")
    unused_x = {x for x, which in U2_PATTERN_X.items() if which != RAM_FITTED}

    def fp_spans(text):
        out, i = [], 0
        while True:
            i = text.find("\n\t(footprint ", i)
            if i < 0:
                return out
            j = text.find("\n\t)\n", i + 1)
            out.append((i + 1, j + 4))
            i = j + 1

    pieces, last, paste_stripped, paste_refs = [], 0, 0, []
    for a0, b0 in fp_spans(txt):
        bfp = txt[a0:b0]
        m3 = re.search(r'\(property "Reference" "([^"]+)"', bfp)
        ref = m3.group(1) if m3 else "?"
        am3 = re.search(r"\(attr ([^)]*)\)", bfp)
        flags = set(am3.group(1).split()) if am3 else set()
        placed = not (flags & {"dnp", "exclude_from_pos_files"})
        if not placed:
            nb, n = strip_paste(bfp)
        elif ref == "U2":
            nb, n = strip_paste(bfp, only_x=unused_x)
        else:
            nb, n = bfp, 0
        if n:
            paste_stripped += n
            paste_refs.append(f"{ref}({n})")
            pieces.append(txt[last:a0])
            pieces.append(nb)
            last = b0
    pieces.append(txt[last:])
    txt = "".join(pieces)

    # The rule checking itself: no unplaced footprint may still hold an aperture, and U2
    # must hold exactly 48 -- one per pin, on one pattern.
    left = []
    for a0, b0 in fp_spans(txt):
        bfp = txt[a0:b0]
        m3 = re.search(r'\(property "Reference" "([^"]+)"', bfp)
        am3 = re.search(r"\(attr ([^)]*)\)", bfp)
        flags = set(am3.group(1).split()) if am3 else set()
        npaste = len(re.findall(r"\(layers [^)]*Paste", bfp))
        if (flags & {"dnp", "exclude_from_pos_files"}) and npaste:
            left.append(f"{m3.group(1) if m3 else '?'}:{npaste}")
        if m3 and m3.group(1) == "U2" and npaste != 48:
            raise AssertionError(
                f"U2 holds {npaste} paste aperture(s), not the 48 one land pattern needs. "
                f"Pasting both nested patterns puts solder under the body of the fitted "
                f"chip, between adjacent pins on different nets.")
    if left:
        raise AssertionError("paste apertures survive on parts nobody places: "
                             + ", ".join(sorted(left)))

    # ---------- ECO-17c  the 3D body must be the RAM we buy ---------------------------
    # MouseBiteLabs' model names the 12.4 mm package, which is the SALVAGED OEM part -- the
    # right default for his build and the wrong one for ours, because this fork's BOM buys
    # the CY62157EV30LL. Left alone, every "as PCBWay assembles it" render shows a chip two
    # thirds the size of the one that will be on the board.
    want_model, want_off = U2_MODEL[RAM_FITTED]
    s_u2, e_u2, b_u2 = fp_span("U2")
    mm = re.search(r'\(model "([^"]+)"([\s\S]*?)\n\t\t\)', b_u2)
    if not mm:
        raise AssertionError("U2 has no (model ...) block to correct")
    old_stem = os.path.basename(mm.group(1)).rsplit(".", 1)[0]
    if old_stem not in {v[0] for v in U2_MODEL.values()}:
        raise AssertionError(
            f"U2's model is {old_stem!r}, which is neither land pattern's package. "
            f"MouseBiteLabs changed it; re-derive U2_MODEL before trusting this.")
    nb_u2 = b_u2[:mm.start()] + (
        f'(model "{os.path.dirname(mm.group(1))}/{want_model}.wrl"\n'
        f'\t\t\t(offset\n\t\t\t\t(xyz {want_off:g} 0 0)\n\t\t\t)\n'
        f'\t\t\t(scale\n\t\t\t\t(xyz 1 1 1)\n\t\t\t)\n'
        f'\t\t\t(rotate\n\t\t\t\t(xyz 0 0 0)\n\t\t\t)\n\t\t)'
    ) + b_u2[mm.end():]
    txt = txt[:s_u2] + nb_u2 + txt[e_u2:]

    return txt, dict(paste_stripped=paste_stripped, paste_refs=paste_refs,
                     orig_len=orig_len, new_len=len(txt), segs=len(segs),
                     vias=len(vias), net=NEWNET, hand=sorted(derived))


def library_footprint(board_text):
    """Derive clockxcontrol-integration/footprint/ClockxControl_GBA_GBC.kicad_mod
    FROM the board's own MOD1 block, so the two cannot drift.

    ECO-14 found they had. The shipped library file labelled the three landings "1", "2",
    "3" and carried a "pad end" string the board does not have, its centre text was 1.2
    against the board's 1.05, and its reference read "MOD" not "MOD1". Pads and outlines
    agreed, so nothing was wrong on a board built from the .kicad_pcb -- but anyone
    re-importing the library got a different footprint from the one this fork verified,
    and check [2] compares the zip to the tree, never the .kicad_mod to the board.

    Deriving it removes the question. The transform is small and mechanical: drop the
    instance placement, restore the library reference convention, and keep everything
    else exactly as the board has it.
    """
    i = board_text.find('\n\t(footprint "ClockxControl_GBA_GBC"')
    if i < 0:
        raise AssertionError("no ClockxControl footprint on the board to derive from")
    j = board_text.find("\n\t)\n", i + 1)
    blk = board_text[i + 1:j + 3]
    blk = blk.replace("\n\t", "\n").lstrip("\t").rstrip()
    # a library footprint has no instance placement and no board-assigned nets or uuids
    blk = re.sub(r'\n\t\(at [-\d.]+ [-\d.]+ ?[-\d.]*\)', "", blk, count=1)
    blk = re.sub(r'\n\t+\(net \d+ "[^"]*"\)', "", blk)
    # the footprint-level uuid identifies a board INSTANCE, not a library part
    blk = re.sub(r'\n\t\(uuid "[0-9a-f-]+"\)', "", blk, count=1)
    blk = blk.replace('(property "Reference" "MOD1"', '(property "Reference" "REF**"')
    head = ('(footprint "ClockxControl_GBA_GBC"\n'
            '\t(version 20241229)\n'
            '\t(generator "scripts/build_board.py")\n'
            '\t(generator_version "9.0")\n')
    blk = blk.replace('(footprint "ClockxControl_GBA_GBC"\n', head, 1)
    return blk + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="build in memory and diff against the shipped board; write nothing")
    ap.add_argument("-o", "--out", default=OUT)
    ap.add_argument("--no-footprint", action="store_true",
                    help="skip rewriting the derived .kicad_mod library file")
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
    # The library footprint is DERIVED from the board, in the same run, so the two cannot
    # drift. ECO-14 found they had. See library_footprint().
    if not a.no_footprint:
        with open(FOOTPRINT_OUT, "w", encoding="utf-8") as f:
            f.write(library_footprint(txt))
        print(f"wrote {FOOTPRINT_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
