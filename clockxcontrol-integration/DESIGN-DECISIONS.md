# ClockxControl on AGBM-02 — the design decisions

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

This fork adds an **insideGadgets ClockxControl** overclocker mezzanine to MouseBiteLabs'
AGBM-02, and adjusts a handful of parts around it. Everything here is a decision that
constrains a future change. Anything that was only a record of *how* the work went has been
removed — the gates in `scripts/` are the durable version of that, because they re-derive
their numbers from the board on every run instead of asserting them once in prose.

**The board is generated, never hand-edited.** `scripts/build_board.py` splices this fork's
copper into MouseBiteLabs' committed `.kicad_pcb`, and check [1] proves the shipped file
rebuilds from his zip byte for byte. Edit the generator, not the board.

---

## 1. Where the module sits, and the one part that had to move

The module lies flat and needs a **component-free 18.65 × 12 mm window**. Floating over
tented vias and traces is fine — MouseBiteLabs' own DMG Color footprint sits over a via
field — but a component body is not.

* **The back is unavailable.** A `B.Cu` rule area at `x 33.1…105.1, y −54.2…−32.2` forbids
  pads and footprints: the game pak sits there. Tracks and vias *are* allowed through it,
  which the routing uses.
* **On the front exactly one window exists**, and exactly one part stood in it. Ranking every
  legal placement by collisions gave `82.3…100.9, −50.8…−38.8`, blocked only by `C7`. The
  runners-up were "on top of `U1`" and "on top of `U2`".

`MOD1` centres at **(91.95, −44.95)**. `C7` — a 0603 0.1 µF cart-rail bypass — moves from
**(91.9, −41.1)** to **(93.1, −37.4)**, which puts its `VDD35` pad 2.4 mm from `P1` pin `C1`,
closer than the 6.3 mm it had before.

![The front, with the module window](render/agbm02_hero_top.png)

<sub>The `CLOCKXCONTROL` outline between the RAM and the cartridge connector is that window.
`MOD1` carries no 3D model, so what you see is the silkscreen and the three landings, not a
module body.</sub>

## 2. `C7` and `C7A` are the same land in two places, and only one is ever populated

Moving `C7` would have made this a **side-grade**: third-party mods that solder to `C7` where
it has always been would lose their landmark. `C7` sits at (91.9, −41.1) on **both** AGBM-01
and AGBM-02 — byte-identical across two revisions of MouseBiteLabs' own design, which is
exactly what an outside mod keys off.

So the stock land is restored as **`C7A`**, unpopulated, at the original coordinate. It is
2.15 mm inside `MOD1`'s body, so a *populated* 0603 there fouls a module lying on the board;
bare, it is copper and mask — and the module already lies over **22** of MouseBiteLabs' own
vias, with 4 more exactly on the body edge. A module floating over tented copper is the
condition his own DMG Color footprint ships in.

> **Populate `C7` for a ClockxControl build. Populate `C7A` for a stock build that needs the
> landmark. Never both.**

Their reference designators are deliberately moved apart — `C7` to (−1.7944, 1.5128), `C7A`
to (3.1524, −0.6124) — because both footprints inherit the same stock offset and would
otherwise print on top of each other. On a pair whose entire purpose is *populate exactly one
of these*, the silkscreen has to say which land you are looking at.

`C7A`'s courtyard overlaps `MOD1`'s by design. It is the one DRC violation this fork adds.

## 3. Routing, and the clock jumper

Three of the module's pads solder down onto landings; `CLK`, `V+` and `V−` are hole-less pads
wired to `TP83`/`TP84`/`TP85` (3.8 / 5.9 / 4.7 mm of wire). **`JP4`** is the `CK1` isolation
jumper: **open for a crystal build, bridged for a ClockxControl build.**

`U1` pin 39 is a `GND` pin that MouseBiteLabs feeds from the pour alone, and this fork's
`/CPU/TP8` route walks past its lower-left corner **0.3594 mm** away where a pour sliver needs
0.400 (0.2 zone clearance + 0.2 `min_thickness`). Forty-one microns short, and the fill still
puts copper on the pad — KiCad keeps an island that touches one — so the land *looks*
connected while being joined to nothing. Pin 39 now has **2.368 mm of `F.Cu` to `C15` pad 2**,
the ground side of the CPU's own decoupling cap. Clearance to pin 40 is 0.225 mm.

`VDD3`'s tail reaches `P1` pad `S1` on `B.Cu` directly rather than through a via. `P1.S1` is
`thru_hole` on `*.Cu` — already on every layer — and the via that used to make the transition
sat **0.468 mm** from `S1`'s 1.0 mm hole against a 0.5 mm `min_hole_to_hole`. Hole-to-hole is
a drill rule, so both being `VDD3` bought nothing. Along the new corridor `B.Cu` clears
foreign copper by 0.826 mm where `F.Cu` cleared by 0.168.

## 4. The clock is 3.3 V and the pin sits in a 2.5 V domain — by insideGadgets' design

Resolved against the vendor's own documentation: **this fork does what insideGadgets
specifies, on the net they specify.** It is recorded here because it looks like a defect
until you check, and it will look like one again to the next reader.

## 5. What a machine places, and what you solder by hand

The hand-solder set is **derived, not listed**. A part is hand-soldered if either:

* it has any **through-hole pad** — read off the board, no maintenance; or
* it is in `SALVAGE_ONLY`, which is one entry: **`U1`, the AGB-CPU**, recovered from a donor
  board. The schematic's own Source field reads *Salvage*. Not orderable at any price, so it
  cannot sit on an assembly BOM.

`np_thru_hole` does not count — an unplated mounting hole is a hole, not a joint. The
generator then checks its own rule: it sweeps every footprint after applying the flags and
**fails the build** if a part with a through-hole pad is still in the position file and not
DNP. The parts it flags are `P1`, `P3`, `P4`, `SP1`, `VR2` and `U1`.

**That is not the same set as the hand-buy list, and the difference matters when you order.**
A part reaches `generated/agbm-02-cxc-handbuy.csv` only if it is `exclude_from_bom` *and not
DNP*. `P1` (cartridge slot) and `P4` (link port) are **DNP on MouseBiteLabs' own board** — he
marks the aftermarket and mechanical parts that way — so they are flagged out of the assembly
BOM *and* out of the hand-buy list, and appear only in
`generated/agbm-02-cxc-not-populated.csv`. They are still parts a working board needs.
**Read the not-populated list before ordering; it is not all jumpers and test pads.**
The hand-buy list itself is `MOD1`, `P3`, `SP1`, `U1` and `VR2`.

**Solder paste follows the placement list.** Anything the machine will not place gets its
apertures stripped — the salvaged CPU, the membrane contacts, every DNP land — so the stencil
and the pick-and-place describe one build.

## 6. `U2` has two nested land patterns; the BOM buys the bigger part

MouseBiteLabs' `U2` footprint carries a salvage-sized TSOP-I-48 and a larger one nested
inside the same outline. The BOM buys the **`CY62157EV30LL`**, which is the
`TSOP-I-48_18.4x12mm_P0.5mm` land — the *outer* pattern, **20.992 mm** lead-tip span as
check [17] measures it. Only that pattern is pasted; pasting both would reflow solder under
the body of the part that is actually fitted, across pads 0.5 mm apart on different nets.

## 7. Parts changed from MouseBiteLabs' choices

| ref | field | his | ours |
|---|---|---|---|
| `U7` | Value | TLV9364 | TLV9064IPWR |
| `DL1` | Value | 150060VS75000 | 150060GS75000 |
| `R25` | Value | 3.3k | 22k |
| `PTC1` | Value | 0805L075SLYR | 0805L110SLYR |
| `R15`, `R16` | Value | 10k | 100k |
| `R11` | Value | 1k | 10k |
| `R24` | Value | 100k | 1M |
| `R65` | Value | 100k | 470k |
| `Q9`, `Q10` | Value | NDC7002N | FDC6301N |

`Q9`/`Q10` is the one correctness item: on the drive those gates actually get, the latch may
never arm. `Q2`, `Q5` and `Q7` keep the NDC7002N deliberately — `Q5`'s gates are driven to
5.0 V so there is no margin problem, and `Q2`/`Q7` switch display signals where changing
`RDS(on)` and `Ciss` would be an unanalysed timing risk for no stated benefit. `PTC1` and
`F1` also carry corrected **Description** fields: the board shipped a legacy `0805L050WR`
string on both, naming neither part.

The **22 µF line** (`C1`, `C21`, `C42`, `C58`) buys YAGEO `CC0805MKX5R8BB226`, 25 V, in place
of MouseBiteLabs' 16 V `GRT21BR61C226ME13K`. That recovers DC-bias headroom at the cost of
AEC-Q200 and soft termination, which **no 25 V part in this body offers** — every 25 V option
gives those up, and the two Murata soft-termination 25 V parts read zero stock.

These live in `build_board.ECO8` and `build_board.ECO11`, which are the authoritative copies.
The table above is prose; the generator is the source.

## 8. Fiducials

Six, three per side, **not paired** — a front mark does not care what the back is doing, and
dropping that assumption is what makes the search tractable: `scripts/place_fiducials.py`
finds **3,659 legal front sites and 6,327 back** once each side is solved on its own terms.
None of the six chosen is legal on the other side.

A site has to clear five things at once, and four of them are checked by KiCad: the board
outline *including its 13 shell holes and the two routed openings inside `SW1` and `VR2`*,
the board's 64 keepout zones, other soldermask apertures **as filled regions**, hard copper
on the mark's own layer, and courtyards. Both triangles are deliberately scalene so a machine
cannot register the panel 180° out.

`scripts/place_fiducials.py` finds sites; check [13] re-measures the six chosen ones and
fails if a margin moves by more than 5 µm. There is **no legal site anywhere in the board's
upper right** — the CPU, the RAM and the LCD connector leave nothing with a 1.1 mm clear
radius.

## 9. Read the board's own DRC rules

KiCad keeps design rules in the **project**, not the board. MouseBiteLabs ships a
`.kicad_pro` inside his design zip, and it differs from KiCad's defaults in both directions:
`min_hole_to_hole` 0.5 against 0.25, `min_clearance` 0.15 against 0.0, and
`silk_overlap`, `silk_over_copper`, `text_height`, `lib_footprint_issues`,
`lib_footprint_mismatch` and `silk_edge_clearance` all set to **`ignore`**, plus 113
pre-triaged exclusions.

Open this board without it and KiCad reports several times as many violations, most of them
checks he sets to `ignore`. The deliverable zip ships his project file beside each board for
exactly this reason, and `scripts/check_drc.py` extracts it from his zip rather than trusting
a copy.

Measured against his rules: **his AGBM-02 has 164 violations and 0 unconnected; this fork has
165 and 0.** The one addition is `C7A`'s courtyard, above. The check compares by *position*,
so only a violation at a spot his board does not have counts as this fork's.

## 10. The board ships in two KiCad formats

KiCad 9 cannot open a KiCad 10 file at all, and the two encode nets differently — by number
versus by name, with no net table in the newer one. The **KiCad 9 file is the source of
truth**, because it is what the generator splices into MouseBiteLabs' KiCad 9 base and what
check [1] rebuilds byte for byte. The `_kicad10` file beside it is **derived**, regenerated by
`scripts/kicad10.py`, and check [19] proves the two carry the same copper *and* the same
silkscreen.

Tracks are compared by **coverage**, not segment by segment. KiCad 10 merges collinear runs,
so the same copper can be stored as a different number of segments in the two files and a
naive diff reads that as hundreds of deleted traces. The comparison instead groups by layer,
net, width and the infinite line each segment lies on, then merges intervals — invariant
under merging, and it still catches anything that actually moved. As converted today both
files hold **3,554** segments, collapsing to 3,353 collinear runs; the coverage comparison is
there so that staying equal is not something the check depends on.

## 11. Known-open, deliberately

* **The zone fill in the committed board is MouseBiteLabs' own, from before this fork added
  copper.** Do not plot Gerbers from it. Open it in KiCad, *Fill All Zones*, re-run DRC. The
  gates re-pour a throwaway copy; the committed file stays stale on purpose so that "we did
  not re-pour" is checkable rather than assumed.
* **Two buy lines sit at zero stock** at both distributors: `U14` (MIC1553YM5-TR, no drop-in
  equivalent in SOT-23-5) and `U11`/`U12`/`U18` (TPS22917DBVR — `TPS22917DBVT` is the same die
  on a different reel and is an order-time swap, not an engineering one).
* **Every open item on the module itself** — the lattice-site assignment, the CLK/V+/V− pad
  positions, the 18.65 mm length and the shell fit — is listed in
  [`README.md`](README.md) §7. All four want a physical module and a pair of calipers.

## 12. The base is MouseBiteLabs' August 2026 AGBM-02

This fork does not maintain a copy of his board; it splices its own copper into whatever
`AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip` holds, and check [1] rebuilds the result
byte for byte. So an upstream revision is adopted by refreshing that zip and rebuilding —
nothing is cherry-picked by hand.

His **20 August 2026** upload changed the board only, not the schematic or the project file:

* **`P2`, the 40-pin FFC display connector, has narrower lands** — 40 pads from
  `0.35 × 1.25 mm` to `0.30 × 1.25 mm`, unmoved, on unchanged 0.5 mm pitch. The gap between
  adjacent lands goes **0.15 mm → 0.20 mm**. His own note gives the reason: *"Narrowed pads
  for FFC connector for solderability (and to appease PCBway)."* Against his own rules it
  removes **39 violations** from the base board — 203 → 164 — and the same 39 from this fork.
  The shield land (pad `0`, 1.9 × 4.125 mm) is untouched.
* **`BT1`'s two custom thru-hole pads carry an explicit `(padstack)`** with per-layer
  primitives, where the inner- and back-layer shapes were previously implicit. No pad moved
  and no size changed.
* **An unannotated footprint parked off the board outline is gone.** It used to warn in
  check [13]; the warning went with it.
* **The zone fill was re-poured**, which is his to do — this fork still never re-pours, so
  check [14] compares against the new fill and stays meaningful.

Nothing in this fork's own copper had to move: `P2` is on `B.Cu` at the display end, and
narrowing a land only increases clearance to everything around it.

![The back, with P2 at upper right](render/agbm02_hero_bottom.png)

<sub>`P2` is the connector at upper right. The two banner views are rendered from the same
re-poured throwaway copy as every other assembled view, so neither can show a board this
repository does not ship — the Z rotation is mirrored between them so the pair reads as one
board turned over.</sub>
