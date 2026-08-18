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

## 6.5 All six landings — the wireless build

The three button pads above are geometry taken from a shipping board. `CLK`, `V+` and `V-` are
not: MouseBiteLabs left them as wire pads, and insideGadgets publish nothing. To make the
integration wire-free anyway, this ECO adds three more landings **at a photo-derived estimate**,
with their nets assigned and routed, as individually-draggable single-pad footprints so the final
positions can be corrected by hand.

### The estimate and how it was made

The install photo was calibrated against the lattice that *is* known. The three silkscreen capsule
outlines around the button pads pin the v axis exactly — rows 2.5 / 5.0 / 7.5 mm land at image
y 1249 / 1174.5 / 1100 px, giving **29.9 px/mm** and putting the reference long edge (v = 0) at
image y 1324.5, under the kapton where it cannot be read directly. The pad columns fix the u axis
the same way. Reading the three left-end pads through that transform gives, in module coordinates
(u from the CLK-end short edge, v from the same long edge the button rows reference):

| Module pad | u | v | **Uncertainty** |
|---|---|---|---|
| `CLK` | ≈3.9 | ≈9.2 | **±0.5 mm** |
| `V+` | ≈2.3 | ≈7.1 | **±0.5 mm** |
| `V-` | ≈2.3 | ≈8.8 | **±0.5 mm** |

The u ≈ 2.3 for `V+`/`V-` is suggestive — it is the same 2.3 mm inset the button columns use from
the other end — but that is a pattern, not a measurement. Treat all three as provisional.

### As placed

| Ref | Net | Position | Pad |
|---|---|---|---|
| `TP83` | `CXC_CLK` (new net 238) | 99.250, −42.050 | ø1.4 mm, silk `CLK` |
| `TP84` | `VDD3` | 100.850, −44.150 | ø1.4 mm, silk `V+` |
| `TP85` | `GND` | 100.850, −42.450 | ø1.4 mm, silk `V-` |

ø1.4 mm rather than the ø1.27 mm of the measured three: slightly oversized to absorb some of the
error, and as large as the ~1.7 mm spacing between them allows. They are separate footprints, not
pads inside `MOD1`, precisely so each can be dragged on its own in the PCB editor with its track
rubber-banding along.

**To correct them after measuring a module**, the mapping is direct — `MOD1` sits at
(93.825, −45.250) rot 180, so the module's CLK-end edge is at x = 103.150 and its reference long
edge at y = −51.250:

```
x = 103.150 − u        y = −51.250 + v
```

Measure each pad's centre from those two edges, plug in, done.

`TP82` (the original V− wire pad at 102.000, −41.000) is left in place as a fallback: if the `V-`
landing does not line up on a real module, a short wire to `TP82` still gets you there.

### `JP3` — CK1 isolation jumper

Making the build wire-free means `CK1` has to reach the module on copper: **75.8 mm** of it, mostly
on `B.Cu` through the cartridge keepout. On a board built the normal way, with the crystal fitted
and no module, that track would be a dead stub hanging off the oscillator's high-impedance XIN
node — roughly 5 pF of added load (about 40 ppm of frequency error) plus a 75 mm antenna for
crosstalk into the one node on the board that must not be disturbed.

So the run is gated. `JP3` is a 2-pad open solder jumper at **(45.000, −64.200)**, 6.9 mm from
`TP80`, pads ø1.05 mm at 1.3 mm pitch:

- pad 1 → `/CPU/CK1` (5.0 mm of new track back to the existing CK1 copper)
- pad 2 → `CXC_CLK`, the new net that carries the run to `TP83`

**Open by default.** A crystal build is then electrically identical to the board without this ECO —
the stub is disconnected, and all that remains on CK1 is the 5 mm to `JP3` pad 1. Bridge it only
when populating the ClockxControl. This is the same default-open pattern ECO-5 used for `JP2`.

### Also in this pass

- **Two GND stitching vias relocated** to clear the new landings: (100.200, −41.500) →
  (100.400, −41.500) and (101.000, −44.500) → (101.400, −45.300). Both had zero attached tracks —
  pure plane stitching, confirmed before moving.
- **New net 238 `CXC_CLK`.**
- **Routing added**: `CXC_CLK` 75.8 mm / 2 vias, `VDD3` 12.4 mm / 2 vias to `P1` pad `S1`,
  `GND` 2.8 mm / 1 via, `CK1` 5.0 mm. Board total is now **240.9 mm of new track and 10 new
  vias**.

### Re-verification

Same differential method as §6.4, over a widened region (x 38…114, y −70…−32): **0 new violations,
3 removed**.

While extending the check I found and fixed a defect in the checker itself: its pad parser used a
rigid regex that silently dropped 83 pads across 29 footprints — every through-hole pad, including
all 36 of the cartridge connector `P1`. Rebuilt with brace-matched parsing (940 pads now, matching
the board), the **§6.4 result still holds**: the original three-landing ECO was and remains clean.

---

## 6.6 Before you fab

1. **Open in KiCad 9, run DRC, re-pour both inner planes and the outer pours.** This ECO is a
   scripted edit verified by a scripted checker. It has not been through KiCad's DRC engine.
2. **`MOD1` and `TP82` exist on the board only.** The fork's archive carries no schematic, so
   these have no symbols. Running *Update PCB from Schematic* will try to delete them. Add
   matching symbols (or a board-only exclusion) before doing that.
3. **Confirm the module's pad identities.** Which of the three lattice sites is Device pad 1, 2
   and 3 is inferred from MouseBiteLabs' `P10`/`P11` assignment read against insideGadgets' GBC
   wiring list. It is one continuity beep per pad on a physical module. If it comes out different,
   swap which net feeds which pad — the geometry does not change.
3b. **Measure and correct `TP83`/`TP84`/`TP85`** (§6.5). Their positions are photo-derived to about
   ±0.5 mm and are the one genuinely provisional thing in this ECO. Do not fab without checking
   them against a physical module.
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

## 6.7 Build sheet (when populating the ClockxControl)

1. Leave `X1`, `C3`, `C4` unpopulated.
2. **Bridge `JP3`** (by the crystal, silkscreened `CXC CLK`). Without it the module gets no clock.
3. Seat the module on the `MOD1` outline, component side up, and solder through all six pad holes:
   `MOD1` pads 1/2/3 for Select/L/R, and `TP83`/`TP84`/`TP85` for CLK/V+/V−.
4. If `TP83`/`TP84`/`TP85` do not line up on your module, fall back to wires — `TP82` for V−,
   `P1` pad `S1` for V+, `TP80` for CLK — and fix the pad positions for the next spin.
5. Speed control is Select + L / Select + R; hold Select for 2 s to return to 1x. Note the
   AGBM's own hotkeys are Start + L + R + one of {Select, A, B, D-pad}, so holding
   Select + L + R and then pressing Start will drive both.
