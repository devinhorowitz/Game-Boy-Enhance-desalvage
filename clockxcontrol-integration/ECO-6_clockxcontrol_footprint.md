# ECO-6 — ClockxControl mezzanine footprint (engineering write-up)

Cuts the insideGadgets **GBA ClockxControl** landing pattern into
`AGBM-01_AA_1-2_GBE-plus.kicad_pcb` (the ECO-5 de-salvage board), so the module solders
directly to the AGBM instead of being taped down and wired to six scattered points.

Output board: [`board/agbm-02-clockxcontrol.zip`](board/agbm-02-clockxcontrol.zip) →
`AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb`.

Derivative of MouseBiteLabs Game Boy Enhance (AGBM-01) and Game Boy DMG Color, CC BY-SA 4.0.

> **rev B** — the module has been shifted **1.875 mm west and 0.3 mm south** of where rev A put
> it, to get it out of the crowded `R3` / `TP114` / `TP115` / `U10` cluster on its right. Worst
> body clearance goes from 0.25 mm to 0.55 mm and the right-hand side opens from 0.25 mm to
> 2.13 mm. The cost is two `VDD2` plane-stitching vias, which the `R` landing now lands on and
> which have nowhere else to go — see §6.7. All positions in this document are rev B.

---

## Overview

The ClockxControl's I/O pads are plated through-holes. The module lies flat on the host board
over matching pads and is fixed by dropping solder into the hole from above, which wets down onto
the host pad and bonds the two boards. MouseBiteLabs already ships that pattern on
**DMGC-CPU-01 rev 2.5** (*"Added space for adding ClockxControl by insideGadgets"*), and the land
pattern in this ECO is measured out of those gerbers — see §4 of the
[study](README.md) for the extraction.

This ECO places that pattern on the AGBM and wires its three button pads to `/CPU/TP2` (Select),
`/CPU/TP9` (L) and `/CPU/TP8` (R). §§6.1–6.4 cover that core edit, where V+ and CLK stay as wires
to pads that already exist (`P1` pad `S1` is `VDD3`, `TP80` is `CK1`). **§6.5 then adds dedicated
pads for CLK / V+ / V−** immediately outside the module body, their routing, and a jumper that
keeps crystal builds unaffected by the long CLK run. **§6.7 is rev B** — the module shifted west
for clearance, and the one deletion from the host design that made it possible.

## 6.1 What changed

Every edit sits in the band between the RAM and the cartridge connector.

### Moved

| Ref | From | To | Why |
|---|---|---|---|
| `C7` (0603, `VDD35`/`GND`) | 91.900, −41.100 rot 180 | **93.100, −37.400 rot 180** | It was the only part inside the one viable module window. The new spot is in the clear band between the module and the cartridge connector, and it puts `C7` pad 1 **2.4 mm from `P1` pad `C1`** (the cart's `VDD35` pin) instead of the 6.3 mm it started at. |

**The fiducials are no longer *moved*, they are *added*.** On the ECO-5 AGBM-01 base a fiducial
ECO had already placed six, and ECO-6 relocated the `FID2`/`FID5` pair out of the module outline.
[ECO-13](ECO-13_rebase_onto_agbm02.md) rebased onto MouseBiteLabs' AGBM-02, which **carries no
fiducials at all** — he hand-builds, and a hand builder needs no optical registration. So all six
are created by this fork, placed clear of the module to begin with, and the row that used to sit
here describing a move from (89.000, −48.000) has been deleted because that position never existed
on this base.

`C7` had **no tracks attached** on the original board — both pads were fed by pours — so nothing
was orphaned by the move. At the new position its `VDD35` pad lands inside the F.Cu `VDD35` pour
and gets a 0.4 mm stub onto the `VDD35` stitching via already at (93.500, −37.200). Its `GND` pad
does *not* land in a `GND` pour there — `VDD35` (priority 27) wins that patch of F.Cu — so it gets
a 1.6 mm stub and a via at (93.300, −38.700) into the `In1.Cu` and `B.Cu` ground planes.

### Removed

| Item | Position | Net | Why |
|---|---|---|---|
| stitching via | 84.400, −45.900 | `VDD2` | the `R` landing sits on top of it (§6.7) |
| stitching via | 85.400, −45.900 | `VDD2` | same |

### Added

| Item | Position | Net | Notes |
|---|---|---|---|
| `MOD1` footprint | 91.950, −44.950 rot 180 | — | outline 82.625…101.275 × −50.950…−38.950 (18.65 × 12.00) |
| `MOD1` pad `1` | 87.425, −45.950 | `/CPU/TP2` | Select |
| `MOD1` pad `2` | 84.925, −48.450 | `/CPU/TP9` | L |
| `MOD1` pad `3` | 84.925, −45.950 | `/CPU/TP8` | R |
| 0.4 mm stub | 93.875, −37.400 → 93.500, −37.200 | `VDD35` | ties `C7` pad 1 to the existing `VDD35` stitch via |
| 1.6 mm stub + via | via at 93.300, −38.700 | `GND` | ties `C7` pad 2 into the ground planes |
| 169 track segments, 4 vias | — | `/CPU/TP2`, `/CPU/TP8`, `/CPU/TP9` | see §6.3 |

Pads are ø1.270 mm copper with 0.0635 mm mask expansion (ø1.397 mm opening) — the DMG Color's
numbers exactly. No drills: the holes belong to the module, not the host.

**Not** added *in this core edit*: V+ and CLK landings. `P1` pad `S1` (96.900, −35.200) is already
`VDD3` and sits 3.8 mm below the module's south edge; `TP80` (48.000, −58.000) is already
`CK1`, so both work as wires exactly as on a stock GBA. §6.5 adds solder-through landings for them
too, with the CLK run gated by a jumper so a crystal build sees no stub.

## 6.2 Why the module sits there

The module lies flat, so it needs a **component-free** 18.65 × 12 mm area (floating over tented
vias and traces is fine — the DMG Color footprint sits over a via field). Two constraints:

- **The back is out.** `B.Cu` rule area `x 33.1…105.1, y −54.2…−32.2`, `pads: not_allowed,
  footprints: not_allowed` — the game pak sits there. (Tracks and vias *are* permitted through
  it, which §6.3 uses.)
- **On the front, exactly one window exists**, and exactly one part blocked it. Ranking every
  legal placement by collisions gave `82.3…100.9, −50.8…−38.8` blocked only by `C7`; the runners-up
  were "on top of `U1`" and "on top of `U2`".

Within that window the position is a straight trade between two clearances that pull in opposite
directions:

- **body clearance** — how much room the 18.65 × 12 mm module has to its neighbours. This gets
  worse to the east, where `R3`, `TP114`, `TP115` and `U10` crowd the module, and better to the
  west, where the only thing near is `TP18`.
- **pad clearance** — how close the three landings sit to foreign copper. This gets worse to the
  west, because the escape fan out of `U2` and the `VDD2`/`GND`/`VDD5` stitching rows tighten up
  there.

Rev A took the pad-clearance end of that trade: centre (93.825, −45.250) rot 180, 0.458 mm minimum
pad-to-copper but only 0.25 mm of body clearance on two sides at once. **Rev B takes the middle**:
centre **(91.950, −44.950) rot 180**, 0.550 mm worst body clearance and 0.240 mm minimum
pad-to-copper — both comfortably over the 0.2 mm netclass requirement, and the east side opens
from 0.25 mm to 2.13 mm. The 0.240 mm is against *this ECO's own* escape tracks, under solder
mask, not against anything the module's solder can reach. §6.7 covers why the module cannot go
further west than this.

180° points the button end west, toward the nets it needs.

## 6.3 Routing

`TP2`, `TP8` and `TP9` originate around x 51…57 near the CPU, so each pad needs a 26–36 mm run
through a congested field. Routed with a two-layer maze router (0.05 mm grid, F.Cu + B.Cu,
0.2 mm clearance, 0.25 mm track, 0.7/0.3 mm vias), trying all six net orderings and keeping the
cheapest:

| Net | Length | Vias | Layers | Ends on |
|---|---|---|---|---|
| `/CPU/TP8` (R) | 28.6 mm | 0 | F.Cu only | existing F.Cu endpoint 61.872, −52.500 |
| `/CPU/TP2` (SEL) | 46.9 mm | 2 | F.Cu → B.Cu → F.Cu | existing F.Cu endpoint 53.279, −48.664 |
| `/CPU/TP9` (L) | 59.4 mm | 2 | F.Cu → B.Cu → F.Cu | existing F.Cu endpoint 54.248, −52.193 |

Total 134.9 mm of new track and 4 vias. Each route starts exactly on its pad centre and ends
exactly on an existing endpoint of its own net, so connectivity is unambiguous. The B.Cu portions
run through the cartridge keepout, which permits tracks.

These are slow button lines — already RC-filtered by the AGBM's own 15 Ω / 0.01 µF networks — so
length is electrically irrelevant here.

**They are maze-router output.** 169 short 45°/90° segments where a human would draw a dozen.
That is cosmetic; re-drawing them with KiCad's interactive router will look better and cost
nothing.

## 6.4 Verification

A full pairwise clearance check over `x 45…112, y −63…−36` — every track, via and pad against
every other of a different net, plus hole-to-hole and board-edge rules — was run on the original
board and on the patched board, and the two result sets differenced:

```
new violations introduced by this ECO : 0     <-- TRUE ON AGBM-01, FALSE ON AGBM-02
```

> **Corrected by [ECO-14](ECO-14_clock_domain_and_audit_fixes.md).** That sweep was run on the
> AGBM-01 base. On MouseBiteLabs' AGBM-02 there is **one** new clearance violation, and it is this
> ECO's own copper: the `CXC_CLK` via at **(47.450, −59.600)** sits **0.1632 mm** from `C13` pad 1
> (`VDD5`, `B.Cu`, unmoved by any ECO), against the project's single `Default` netclass clearance
> of **0.200 mm** — measured centre-to-centre 1.0680 mm, roundrect corner radius 0.225, via radius
> 0.350. It fails by 0.037 mm. It clears the board's `min_clearance` of 0.150 and is well inside
> PCBWay's 0.127 mm capability, so it is a rule violation rather than a manufacturability one — but
> **FIXED in [ECO-14 §14.2](ECO-14_clock_domain_and_audit_fixes.md):** the via moved to
> (47.500, −59.500), worst foreign clearance now **0.2321 mm**. Check [13] gates it.


**Superseded by [ECO-13](ECO-13_rebase_onto_agbm02.md).** The three removed violations were
`FID5` overlapping three `B.Cu` traces on the *AGBM-01* `_GBE-plus` board — a defect that cannot
exist on AGBM-02, because AGBM-02 has no fiducials to inherit. The count above was measured on the
old base and is kept only as the record of what that analysis found.

**The fiducials were then moved again — see [ECO-14 §14.3](ECO-14_clock_domain_and_audit_fixes.md).**
The spots this ECO inherited were never checked against AGBM-02's *copper*: `FID3`/`FID6` sat
0.768 mm from a `GND` via, inside their own 1.0 mm mask window, and `FID1`/`FID4` cleared by 64 µm.
All three pairs moved — to (28.1, −9.6), (31.0, −69.5) and (110.85, −57.65), clearing 1.800 mm to
2.478 mm — and each pad gained a `(clearance 0.55)` override so the `GND` pour recedes past the
window on a re-pour. Consistency check [13] now asserts both.

The checker models rectangular pads as circumscribed circles, so its absolute violation count on
either board is dominated by false positives at fine-pitch parts (adjacent TSOP pads read as
overlapping). That over-estimation is conservative in the right direction — it can only make the
router avoid more, never less — and the *difference* between the two boards is exact.

Zone pours were not re-filled: new copper inside another net's pour is resolved when KiCad
re-pours, which is a required step below.

## 6.5 The other three: CLK, V+ and V−

**Only the six button pads on the module are plated through-holes.** `CLK`, `V+` and `V-` are
plain top-side pads with no hole — confirmed against a stock unit. So those three cannot be
solder-through landings at any position: there is nothing to drop solder into. They need wires,
and that is a property of the module, not of this board.

That also explains MouseBiteLabs' DMG Color layout, which lands exactly three pads and puts
`CLK`/`V+`/`V-` on ordinary wire pads outside the outline. He was not being conservative about
geometry — he was working with what the module has.

So the goal for these three is not *no wires*, it is **the shortest possible wires**, landing on
labelled pads immediately outside the module body.

### Where they are

The module's `CLK`/`V+`/`V-` pads sit at the far end from the buttons, which — with `MOD1` at rot
180 — is the **east** end. Their positions on the module are photo-derived (u from the CLK-end
edge, v from the same long edge the button rows reference):

| Module pad | u | v | lands on the board at | ±  |
|---|---|---|---|---|
| `CLK` | ≈3.9 | ≈9.2 | 97.375, −41.750 | ±0.5 mm |
| `V+` | ≈2.3 | ≈7.1 | 98.975, −43.850 | ±0.5 mm |
| `V-` | ≈2.3 | ≈8.8 | 98.975, −42.150 | ±0.5 mm |

The wire pads go in the clear pocket immediately **south** of the module body, in the gap between
it and the cartridge connector. (The east strip is a candidate too, and the shift in rev B opened
2.1 mm of it — but three pads squeezed into a 2.1 mm slot next to `R3` are worse to solder three
separate wires onto than three pads in open ground, for about 1 mm of total wire.)

| Ref | Net | Position | Wire from the module pad |
|---|---|---|---|
| `TP83` | `CXC_CLK` (new net 241) | 97.900, −37.950 | **3.8 mm** |
| `TP84` | `VDD3` | 99.450, −37.950 | **5.9 mm** |
| `TP85` | `GND` | 101.000, −37.950 | **4.7 mm** |

ø1.2 mm pads, silkscreened `CLK` / `V+` / `V-`, left-to-right in the same order as the module's
pads so the three wires do not cross. Compare with a stock GBA install, where the same three
connections are 40–60 mm of flying wire.

A useful consequence: the ±0.5 mm uncertainty in the module pad positions now only changes **wire
length**, not whether anything mates. Nothing has to be re-measured before fabbing on account of
these three — measure if you want the wires trimmed exactly, not because the board depends on it.

`TP82`, the earlier spare GND wire pad, is **removed**: it sat under the module body, where it was
no use for a wire either.

### `JP4` — CK1 isolation jumper

Getting `CK1` to the module means 73.5 mm of copper, mostly on `B.Cu` through the cartridge
keepout. On a board built the normal way, with the crystal fitted and no module, that would be a
dead stub on the oscillator's high-impedance XIN node — roughly 5 pF of added load (about 40 ppm
of frequency error) plus a 73 mm antenna into the one node that must not be disturbed.

So the run is gated. `JP4` is a 2-pad open solder jumper at **(45.000, −64.200)**, 6.9 mm from
`TP80`, pads ø1.05 mm at 1.3 mm pitch:

- pad 1 → `/CPU/CK1` (5.0 mm of new track back to the existing CK1 copper)
- pad 2 → `CXC_CLK`, the net that carries the run to `TP83`

**Open by default**, so a crystal build is electrically identical to the board without this ECO;
all that remains on CK1 is the 5 mm to `JP4` pad 1. Bridge it only when populating the module.
Same default-open pattern ECO-5 used for `JP2`.

### Also in this pass

- **New net 241 `CXC_CLK`.**
- **Routing added**: `CXC_CLK` 73.5 mm / 2 vias, `VDD3` 7.0 mm / 2 vias from `TP84` to `P1` pad
  `S1`, `GND` 4.6 mm / 1 via from `TP85` to the `GND` stitch via already at (100.200, −35.300),
  and the two `C7` ties from §6.1. Board total is **225.5 mm of new track, 9 new vias, and two
  vias removed**:

| Net | Length | Vias |
|---|---|---|
| `CXC_CLK` (CLK run + `JP4`) | 73.5 mm | 2 |
| `/CPU/TP9` (L) | 59.4 mm | 2 |
| `/CPU/TP2` (SEL) | 46.9 mm | 2 |
| `/CPU/TP8` (R) | 28.6 mm | 0 |
| `VDD3` (`TP84` → `P1.S1`) | 7.0 mm | 2 |
| `/CPU/CK1` (`JP4` pad 1) | 5.0 mm | 0 |
| `GND` (`TP85` + `C7` pad 2) | 4.6 mm | 1 |
| `VDD35` (`C7` pad 1) | 0.4 mm | 0 |

### Re-verification

Same differential method as §6.4, over a widened region (x 38…114, y −70…−32): **0 new violations,
3 removed**.

While extending the check I found and fixed a defect in the checker itself: its pad parser used a
rigid regex that silently dropped 83 pads across 29 footprints — every through-hole pad, including
all 36 of the cartridge connector `P1`. Rebuilt with brace-matched parsing (940 pads now, matching
the board), the **§6.4 result still holds**.

## 6.6 Fab-view renders

There is no `kicad-cli` in the environment these edits were made in, so the views in `render/`
are produced by a renderer built against the board file directly: board outline, copper, an
**approximate zone re-pour** (every zone clipped to the board, minus higher-priority zones, minus
a 0.2 mm halo around every other-net track, pad, via and hole), soldermask openings, silkscreen
and drills. It is a fab preview, not a gerber export — treat it as a visual check, and take the
real gerbers from KiCad.

| File | What |
|---|---|
| `render/fab_front.png` | whole front side |
| `render/fab_back.png` | whole back side, mirrored so silk reads |
| `render/fab_landings.png` | the landings, clean |
| `render/fab_landings_fit.png` | the same, annotated — landings, wire pads and wire lengths |
| `render/agbm01_cxc_placement.png` | placement diagram: the module window, its neighbours, `C7` before and after, the deleted stitching vias |
| `render/agbm01_cxc_board_after6.png` | copper diff — every new track, via and pad against the original board |
| `render/fab_fit.png` | **fit check**: the module body drawn in place, its plated holes over the `MOD1` pads, its hole-less pads ringed at ±0.5 mm with their wires, and the gap to every neighbour |
| `render/fab_landings_1to1_600dpi.png` | **1:1 scale, 600 dpi.** Print at 100% with no scaling and lay a real module on the paper. A 10 mm ruler is drawn on the sheet to confirm the print came out to scale. |

Body clearances, from `fab_fit.png` — courtyard gaps, so the real body-to-body figures are a
little larger:

| Neighbour | Gap to the module body |
|---|---|
| `U2` (RAM), above | 0.55 mm |
| `C7`, below | 0.82 mm |
| `TP18`, left | 0.93 mm |
| `P1` (cartridge connector), below | 2.05 mm |
| `R3`, right | 2.13 mm |
| `TP114` / `TP115`, right | 2.23 mm |
| `U10`, right | 2.34 mm |

Rev A, for comparison, was `R3` 0.25 / `U2` 0.25 / `TP114`+`TP115` 0.35 / `U10` 0.47 /
`P1` 2.35 / `TP18` 2.80. Every neighbour that was inside half a millimetre is now outside two,
except `U2` — which is a package edge, not a hand-soldered joint.

Two things the renders caught in rev A that the numbers had not:

- **`TP84`'s `V+` silkscreen label was landing on `TP85`'s pad.** Silk over an exposed pad gets
  clipped by the fab or, worse, printed onto the land. All three landing labels moved beside their
  pads (±1.7 mm in x); `TP82`'s label moved too and changed from `V-` to `GND`, because two
  different pads were both silkscreened `V-`.
- **The ±0.5 mm rings on the module's three CLK/V+/V− pads overlap each other.** `V+` and `V-`
  are only 1.7 mm apart, so the photo-derived uncertainty is comparable to the spacing. That was
  fatal while these were still planned as landings; now that they are wire targets it only means
  the wires may come out a few tenths longer or shorter than the table says.

## 6.7 rev B — shifting the module west, and what it cost

Rev A's placement was optimal on one metric (pad-to-copper clearance) and poor on the one you
notice with a soldering iron in your hand: it had `R3` 0.25 mm off its right edge, `TP114`/`TP115`
0.35 mm, `U10` 0.47 mm and `U2` 0.25 mm off its top, all at once. Moving west trades a metric
nobody assembles against for one everybody does.

### How far west it can go

Two hard stops, 3.4 mm apart, and they overlap:

- **`TP18` stops the body.** It is a plated ø1.0 mm test point on `VDD2` at (81.200, −46.200),
  outside any footprint the module can sit on. The module's left edge has to clear it, so the
  centre cannot go west of x ≈ 91.2.
- **Two `VDD2` stitching vias stop the `R` landing.** They sit at (84.400, −45.900) and
  (85.400, −45.900). The `R` pad tracks the centre at (cx − 7.025, −45.950), so for a ø1.27 mm pad
  to keep 0.2 mm off a ø0.7 mm via the centre has to be east of 93.61 or west of 90.24.

93.61 is 0.2 mm from where rev A already was, and 90.24 is a millimetre past where `TP18` stops
the body. **With those vias in place, the module cannot move west at all.**

### Why the vias could not be relocated

They were checked first, before anything was deleted:

- Neither has a single track attached — pure plane stitching between the F.Cu `VDD2` island and
  the `In2.Cu` `VDD2` plane. (The third via of the row, (83.400, −45.900), does have a `B.Cu` stub,
  and it stays.)
- The whole F.Cu `VDD2` island was then swept at 0.05 mm for anywhere else a ø0.7/0.3 mm via could
  legally sit — inside both the F.Cu and `In2.Cu` `VDD2` pours, ≥0.2 mm off every foreign net on
  every layer, ≥0.5 mm hole-to-hole. **Best clearance available anywhere in the island: 0.166 mm.**
  There is no legal home. The island is boxed in by a `B.Cu` `SW` trace along y = −45.22 and the
  RAM's `B.Cu` fan-out along y = −47.14; the row at y = −45.9 is the only gap, and the landing now
  occupies it.

### Why deleting them is acceptable

The lobe of F.Cu `VDD2` pour those two vias stitched **contains no `VDD2` pads**. Every `VDD2` pad
in that island — `U1` pin 44, `C15` pad 1, `C46` pad 1 — is west of x = 79, and `U2` pins 12 and 16
hang off the island's southern leg, which has its own stitch via at (83.227, −56.074). The lobe
east of `TP18` is copper with nothing on it.

After the deletion that lobe still has two full-stack connections to the plane: via
(83.400, −45.900), and `TP18` itself, which is a `TestPoint_Pad_D1.0mm_VIA` — a plated ø0.4 mm
through-hole on `VDD2`, a bigger barrel than either via that was removed. No component current
path is shortened, lengthened or narrowed by the change.

That is the honest full cost of the shift. If you would rather not touch the host's plane
stitching at all, rev A's board is the commit before this one and is functionally identical
otherwise — you keep 0.458 mm of pad clearance and live with 0.25 mm around the module body.

### What the shift bought

| | rev A | rev B |
|---|---|---|
| worst body clearance | 0.25 mm (`R3` and `U2`) | **0.55 mm** (`U2`) |
| neighbours within 0.5 mm | 4 | 0 |
| east side | 0.25 mm | **2.13 mm** |
| min pad-to-copper | 0.458 mm | 0.240 mm |
| `C7` pad 1 → nearest cart `VDD35` pin | 9.0 mm | **2.4 mm** |
| new track / vias | 231.9 mm / 10 | 225.5 mm / 9, −2 |
| new DRC violations | 0 | 0 |

The `C7` line is a side effect worth calling out. On the stock board `C7` pad 1 is 6.3 mm from
`P1` pad `C1`; rev A had to park it west of the module at 9.0 mm, nearly 3 mm worse than
MouseBiteLabs had it. With the module out of the way, `C7` fits in the band south of it instead
and ends up at 2.4 mm — **closer to the pin it bypasses than it was on the stock board**.

### Re-verified

Same differential method as §6.4, same region (x 38…114, y −70…−32), against the unmodified
`_GBE-plus` board:

```
new violations introduced : 0
pre-existing removed      : 3   (the FID5 overlaps from §6.4)
```

## 6.8 Before you fab

1. **Open in KiCad 9, run DRC, re-pour both inner planes and the outer pours.** This ECO is a
   scripted edit verified by a scripted checker. It has not been through KiCad's DRC engine.
2. **`MOD1`, `JP4` and `TP83`/`TP84`/`TP85` exist on the board only.** The fork's archive carries
   no schematic, so these have no symbols. Running *Update PCB from Schematic* will try to delete them. Add
   matching symbols (or a board-only exclusion) before doing that.
3. **Confirm the module's pad identities.** Which of the three lattice sites is Device pad 1, 2
   and 3 is inferred from MouseBiteLabs' `P10`/`P11` assignment read against insideGadgets' GBC
   wiring list. It is one continuity beep per pad on a physical module. If it comes out different,
   swap which net feeds which pad — the geometry does not change.
3b. **`TP83`/`TP84`/`TP85` are wire pads, not landings** (§6.5). The module's CLK/V+/V− pads have
   no holes. Their positions on the module are photo-derived to about ±0.5 mm, but that now only
   affects how long the three wires are, so it does not gate a fab run.
4. **Check the shell and screen fit over the module.** The area is outside every mechanical
   keepout MouseBiteLabs defined, and a module lying directly on the board (1.6 mm) sits *lower*
   than the field-proven stock install (1.6 mm of module on top of ~1.2 mm of RAM). Good evidence,
   not a measurement — same class of open item as ECO-5's front-shell fit.
5. **`X1`, `C3` and `C4` are marked DNP on the board** as of ECO-7 (`(attr smd dnp)`), so an
   assembly house leaves them off. For a crystal build, clear the DNP flag on all three. Note
   that `C4` is not dangling with `X1` removed: it stays tied to `CK2` through `R41`, which is
   why it must come off rather than merely being harmless. The footprints stay on the board deliberately: a board with the crystal fitted still
   works normally, and you keep a bring-up path that does not depend on a $23 add-on.
6. **`C7`'s bypass duty improved.** It moved from 6.3 mm to **2.4 mm** from `P1` pad `C1`, the
   cart's `VDD35` pin — better than where MouseBiteLabs had it. `C6` and `C51` (the other two on
   that rail) are further away still, at x 76.2, and unchanged.
6b. **Two `VDD2` stitching vias were deleted** (§6.7). Nothing on the board connects to them by a
   track, and the F.Cu `VDD2` lobe they stitched contains no `VDD2` pads at all, but it is a
   deletion from the host design and you should know it happened.
7. **Tidy the routes** if you want them to look hand-drawn. Nothing depends on it.

## 6.9 Build sheet (when populating the ClockxControl)

1. Leave `X1`, `C3`, `C4` unpopulated.
2. **Bridge `JP4`** — the jumper by the crystal at (45.0, −64.2), Value `CXC CLK`. Without it the
   module gets no clock. **It is `JP4`, not `JP3`:** on AGBM-02 `JP2` and `JP3` are
   MouseBiteLabs' own RAM straps (`MA17`→GND and `/BYTE`→`VDD2`) and have nothing to do with the
   clock. Bridging `JP3` will not start the module, and on a salvaged OEM RAM it drives a pin the
   original chip leaves NC. Note also that `CXC CLK` is the footprint's **Value** field, which
   renders on `F.Fab`, not on the silkscreen — look for the jumper by position.
3. Seat the module on the `MOD1` outline, component side up, and solder through its three plated
   button holes onto `MOD1` pads 1/2/3 — Select, L, R.
4. Run three short wires from the module's `CLK`, `V+` and `V-` pads (which have no holes) down to
   `TP83`, `TP84` and `TP85` in the row just below the module: about 3.8, 5.9 and 4.7 mm.
5. Speed control is Select + L / Select + R; hold Select for 2 s to return to 1x. Note the
   AGBM's own hotkeys are Start + L + R + one of {Select, A, B, D-pad}, so holding
   Select + L + R and then pressing Start will drive both.
