# ECO-6 — ClockxControl mezzanine footprint (engineering write-up)

Cuts the insideGadgets **GBA ClockxControl** landing pattern into
`AGBM-01_AA_1-2_GBE-plus.kicad_pcb` (the ECO-5 de-salvage board), so the module solders
directly to the AGBM instead of being taped down and wired to six scattered points.

Output board: [`board/agbm-01-clockxcontrol.zip`](board/agbm-01-clockxcontrol.zip) →
`AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb`.

Derivative of MouseBiteLabs Game Boy Enhance (AGBM-01) and Game Boy DMG Color, CC BY-SA 4.0.

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
to pads that already exist (`P1` pad `S1` is `VDD3`, `TP80` is `CK1`). **§6.5 then extends it to a
fully wire-free build**: three more landings for CLK / V+ / V−, their routing, and a jumper that
keeps crystal builds unaffected by the long CLK run.

## 6.1 What changed

Nine edits, all in the band between the RAM and the cartridge connector.

### Moved

| Ref | From | To | Why |
|---|---|---|---|
| `C7` (0603, `VDD35`/`GND`) | 91.900, −41.100 rot 180 | **82.700, −40.300 rot 0** | It was the only part inside the one viable module window. Rotation zeroed so pad 1 (`VDD35`) lands on the left at 81.925, where the tie via fits. |
| `FID2` (fiducial, F.Cu) | 89.000, −48.000 | **106.250, −57.250** | Inside the module outline. |
| `FID5` (fiducial, B.Cu) | 89.000, −48.000 | **106.250, −57.250** | Moved with its pair — and it needed to move anyway, see §6.4. |

`C7` had **no tracks attached** on the original board — both pads were fed by pours — so nothing
was orphaned by the move. Its `GND` pad still lands inside the F.Cu `GND` pour at the new
position. Its `VDD35` pad does not, so it gets an explicit tie (below).

### Added

| Item | Position | Net | Notes |
|---|---|---|---|
| `MOD1` footprint | 93.825, −45.250 rot 180 | — | outline 84.500…103.150 × −51.250…−39.250 (18.65 × 12.00) |
| `MOD1` pad `1` | 89.300, −46.250 | `/CPU/TP2` | Select |
| `MOD1` pad `2` | 86.800, −48.750 | `/CPU/TP9` | L |
| `MOD1` pad `3` | 86.800, −46.250 | `/CPU/TP8` | R |
| `TP82` pad | 102.000, −41.000 | `GND` | the module's V− wire pad, silkscreened `V-` |
| via + 0.9 mm stub | via at 81.025, −40.300 | `VDD35` | ties `C7` pad 1 down to the `In2.Cu` `VDD35` pour |
| 174 track segments, 4 vias | — | `/CPU/TP2`, `/CPU/TP8`, `/CPU/TP9` | see §6.3 |

Pads are ø1.270 mm copper with 0.0635 mm mask expansion (ø1.397 mm opening) — the DMG Color's
numbers exactly. No drills: the holes belong to the module, not the host.

**Not** added *in this core edit*: V+ and CLK landings. `P1` pad `S1` (96.900, −35.200) is already
`VDD3` and sits 3.6 mm below the module's bottom-right corner; `TP80` (48.000, −58.000) is already
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

Within that window the footprint was then positioned to maximise pad clearance against the
existing copper — the escape fan from `U2` and the `VDD2`/`GND`/`VDD5` stitching rows run right
through it. Sweeping centre position and both 0°/180° orientations gives a best of
**0.458 mm minimum pad-to-copper clearance** at centre (93.825, −45.250) rot 180, against a
0.2 mm netclass requirement. 180° also points the button end west, toward the nets it needs.

## 6.3 Routing

`TP2`, `TP8` and `TP9` originate around x 51…57 near the CPU, so each pad needs a 26–36 mm run
through a congested field. Routed with a two-layer maze router (0.05 mm grid, F.Cu + B.Cu,
0.2 mm clearance, 0.25 mm track, 0.7/0.3 mm vias), trying all six net orderings and keeping the
cheapest:

| Net | Length | Vias | Layers | Ends on |
|---|---|---|---|---|
| `/CPU/TP8` (R) | 30.5 mm | 0 | F.Cu only | existing F.Cu endpoint 61.872, −52.500 |
| `/CPU/TP2` (SEL) | 48.7 mm | 2 | F.Cu → B.Cu → F.Cu | existing F.Cu endpoint 53.279, −48.664 |
| `/CPU/TP9` (L) | 64.7 mm | 2 | F.Cu → B.Cu → F.Cu | existing F.Cu endpoint 54.248, −52.193 |

Total 143.9 mm of new track and 4 vias. Each route starts exactly on its pad centre and ends
exactly on an existing endpoint of its own net, so connectivity is unambiguous. The B.Cu portions
run through the cartridge keepout, which permits tracks.

These are slow button lines — already RC-filtered by the AGBM's own 15 Ω / 0.01 µF networks — so
length is electrically irrelevant here.

**They are maze-router output.** 174 short 45°/90° segments where a human would draw a dozen.
That is cosmetic; re-drawing them with KiCad's interactive router will look better and cost
nothing.

## 6.4 Verification

A full pairwise clearance check over `x 45…112, y −63…−36` — every track, via and pad against
every other of a different net, plus hole-to-hole and board-edge rules — was run on the original
board and on the patched board, and the two result sets differenced:

```
new violations introduced by this ECO : 0
pre-existing violations removed       : 3
```

The three removed are worth flagging: on the original `_GBE-plus` board, **`FID5` (the back-side
fiducial added by the fiducial ECO) overlapped three `B.Cu` traces** — nets 87, 97 and 109 — by up
to 0.582 mm. That is an exposed-copper-over-traces short waiting to happen, and `FID5` was also
inside the `B.Cu` cartridge keepout. Moving the pair to (106.250, −57.250) clears both problems.

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
| `CLK` | ≈3.9 | ≈9.2 | 99.250, −42.050 | ±0.5 mm |
| `V+` | ≈2.3 | ≈7.1 | 100.850, −44.150 | ±0.5 mm |
| `V-` | ≈2.3 | ≈8.8 | 100.850, −42.450 | ±0.5 mm |

The east strip beyond the module (x 103.15…104.6) is blocked by `TP114`/`TP115` and the
mechanical keepout, so the wire pads go in the clear pocket immediately **south** of the module
body, in the gap between it and the cartridge connector:

| Ref | Net | Position | Wire from the module pad |
|---|---|---|---|
| `TP83` | `CXC_CLK` (new net 238) | 98.600, −38.200 | **3.9 mm** |
| `TP84` | `VDD3` | 100.900, −38.200 | **6.0 mm** |
| `TP85` | `GND` | 103.000, −38.200 | **4.8 mm** |

ø1.2 mm pads, silkscreened `CLK` / `V+` / `V-`, left-to-right in the same order as the module's
pads so the three wires do not cross. Compare with a stock GBA install, where the same three
connections are 40–60 mm of flying wire.

A useful consequence: the ±0.5 mm uncertainty in the module pad positions now only changes **wire
length**, not whether anything mates. Nothing has to be re-measured before fabbing on account of
these three — measure if you want the wires trimmed exactly, not because the board depends on it.

`TP82`, the earlier spare GND wire pad, is **removed**: it sat under the module body, where it was
no use for a wire either.

### `JP3` — CK1 isolation jumper

Getting `CK1` to the module means 73.5 mm of copper, mostly on `B.Cu` through the cartridge
keepout. On a board built the normal way, with the crystal fitted and no module, that would be a
dead stub on the oscillator's high-impedance XIN node — roughly 5 pF of added load (about 40 ppm
of frequency error) plus a 73 mm antenna into the one node that must not be disturbed.

So the run is gated. `JP3` is a 2-pad open solder jumper at **(45.000, −64.200)**, 6.9 mm from
`TP80`, pads ø1.05 mm at 1.3 mm pitch:

- pad 1 → `/CPU/CK1` (5.0 mm of new track back to the existing CK1 copper)
- pad 2 → `CXC_CLK`, the net that carries the run to `TP83`

**Open by default**, so a crystal build is electrically identical to the board without this ECO;
all that remains on CK1 is the 5 mm to `JP3` pad 1. Bridge it only when populating the module.
Same default-open pattern ECO-5 used for `JP2`.

### Also in this pass

- **Two GND stitching vias relocated**: (100.200, −41.500) → (100.400, −41.500) and
  (101.000, −44.500) → (101.400, −45.300). Both had zero attached tracks — pure plane stitching,
  confirmed before moving.
- **New net 238 `CXC_CLK`.**
- **Routing added**: `CXC_CLK` 73.5 mm / 2 vias, `VDD3` 7.7 mm / 2 vias from `TP84` to `P1` pad
  `S1`, `GND` a 0.9 mm stub and a via into the ground plane. Board total is now **231.9 mm of new
  track and 10 new vias**.

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
| `render/fab_landings_fit.png` | the same, annotated — measured vs photo-derived, with ±0.5 mm rings |
| `render/fab_landings_1to1_600dpi.png` | **1:1 scale, 600 dpi.** Print at 100% with no scaling and lay a real module on the paper. A 10 mm ruler is drawn on the sheet to confirm the print came out to scale. |

Two things the render caught that the numbers had not:

- **`TP84`'s `V+` silkscreen label was landing on `TP85`'s pad.** Silk over an exposed pad gets
  clipped by the fab or, worse, printed onto the land. All three landing labels moved beside their
  pads (±1.7 mm in x); `TP82`'s label moved too and changed from `V-` to `GND`, because two
  different pads were both silkscreened `V-`.
- **The ±0.5 mm rings on the three photo-derived landings overlap each other.** At 1.7 mm spacing
  that is what the uncertainty means in practice: if the estimate is off in the wrong direction,
  two of these pads foul. It is the clearest argument for measuring a module before fabbing.

## 6.7 Before you fab

1. **Open in KiCad 9, run DRC, re-pour both inner planes and the outer pours.** This ECO is a
   scripted edit verified by a scripted checker. It has not been through KiCad's DRC engine.
2. **`MOD1` and `TP82` exist on the board only.** The fork's archive carries no schematic, so
   these have no symbols. Running *Update PCB from Schematic* will try to delete them. Add
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
5. **Depopulate `X1`, `C3`, `C4`** when building with a ClockxControl, and leave them populated
   otherwise. The footprints stay on the board deliberately: a board with the crystal fitted still
   works normally, and you keep a bring-up path that does not depend on a $23 add-on.
6. **Re-check `C7`'s bypass duty if you care.** It moved from 6.5 mm to 8.5 mm from the cart's
   `VDD35` pins. `C6` and `C51` (the other two on that rail) are further away still, at x 76.2.
7. **Tidy the routes** if you want them to look hand-drawn. Nothing depends on it.

## 6.8 Build sheet (when populating the ClockxControl)

1. Leave `X1`, `C3`, `C4` unpopulated.
2. **Bridge `JP3`** (by the crystal, silkscreened `CXC CLK`). Without it the module gets no clock.
3. Seat the module on the `MOD1` outline, component side up, and solder through its three plated
   button holes onto `MOD1` pads 1/2/3 — Select, L, R.
4. Run three short wires from the module's `CLK`, `V+` and `V-` pads (which have no holes) down to
   `TP83`, `TP84` and `TP85` in the row just below the module: about 4, 6 and 5 mm.
5. Speed control is Select + L / Select + R; hold Select for 2 s to return to 1x. Note the
   AGBM's own hotkeys are Start + L + R + one of {Select, A, B, D-pad}, so holding
   Select + L + R and then pressing Start will drive both.
