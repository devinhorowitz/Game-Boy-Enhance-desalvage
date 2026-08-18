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

This ECO places that pattern on the AGBM, wires its three button pads to `/CPU/TP2` (Select),
`/CPU/TP9` (L) and `/CPU/TP8` (R), and provides the V− pad. V+ and CLK need no new copper: the
cart connector's `S1` pad is already `VDD3` (the pad insideGadgets' stock instructions use) and
`TP80` is already `CK1`.

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

**Not** added: V+ and CLK pads. `P1` pad `S1` (96.900, −35.200) is already `VDD3` and sits 3.6 mm
below the module's bottom-right corner; `TP80` (48.000, −58.000) is already `CK1`. Running copper
from `CK1` to a pad near the module would hang a ~40 mm stub on the oscillator node and degrade
every board built the normal way with the crystal fitted — so CLK stays a wire, as it is on a
stock GBA.

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

## 6.5 Before you fab

1. **Open in KiCad 9, run DRC, re-pour both inner planes and the outer pours.** This ECO is a
   scripted edit verified by a scripted checker. It has not been through KiCad's DRC engine.
2. **`MOD1` and `TP82` exist on the board only.** The fork's archive carries no schematic, so
   these have no symbols. Running *Update PCB from Schematic* will try to delete them. Add
   matching symbols (or a board-only exclusion) before doing that.
3. **Confirm the module's pad identities.** Which of the three lattice sites is Device pad 1, 2
   and 3 is inferred from MouseBiteLabs' `P10`/`P11` assignment read against insideGadgets' GBC
   wiring list. It is one continuity beep per pad on a physical module. If it comes out different,
   swap which net feeds which pad — the geometry does not change.
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

## 6.6 Build sheet (when populating the ClockxControl)

1. Leave `X1`, `C3`, `C4` unpopulated.
2. Seat the module on the `MOD1` outline, component side up, and solder through its three pad
   holes onto `MOD1` pads 1/2/3.
3. Wire `V+` to `P1` pad `S1` (silkscreened `S1`, cart connector row) — that is `VDD3`, 3.3 V.
4. Wire `V-` to `TP82` (silkscreened `V-`), immediately right of the module.
5. Wire `CLK` to `TP80` (silkscreened `CK1`), by the crystal site.
6. Speed control is Select + L / Select + R; hold Select for 2 s to return to 1x. Note the
   AGBM's own hotkeys are Start + L + R + one of {Select, A, B, D-pad}, so holding
   Select + L + R and then pressing Start will drive both.
