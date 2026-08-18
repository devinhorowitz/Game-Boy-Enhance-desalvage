# ClockxControl integration on the AGBM — feasibility study

Can the MouseBiteLabs **Game Boy Enhance (AGBM)** carry a footprint for insideGadgets'
**GBA ClockxControl**, and drop the stock crystal the way that mod requires?

**Status: analysis only. No board file has been modified by this study.** Everything below
was derived from the design files in this repository (KiCad 9 `.kicad_pcb` for AGBM-01 rev 1.2b,
AGBM-02 rev 1.1, AGBM-11 rev 1.3) plus insideGadgets' published install sheet.
Numbers taken from the board files are exact; anything inferred from photographs or from
reasoning rather than measurement is flagged as such.

---

## Short answer

| Question | Answer |
|---|---|
| Bring all six ClockxControl signals to one labelled place on the AGBM? | **Yes — and the board is already 4/6 of the way there.** Two new pads finish it. |
| A true solder-down *mezzanine* footprint the module drops onto? | **No — not with the module as sold.** Its I/O pads are top-side only, and there is no 18 × 12 mm flat area on the component side of the AGBM. |
| Delete the crystal because the mod requires removing it? | **Yes, but as a DNP build option, not a deletion.** Keep X1/C3/C4 on the board and unpopulated for ClockxControl builds. |

The electrical side is genuinely trivial — the AGBM's oscillator is a textbook Pierce circuit with
a test point already sitting on the node the module drives. The mechanical side is where the
"footprint" idea runs out of road, and it runs out for reasons that are properties of the
ClockxControl, not of the AGBM.

---

## 1. What the ClockxControl actually needs

From insideGadgets' own **Installation (GBA)** tab, quoted verbatim:

> 1. Use a hot air gun to de-solder the existing crystal. Be careful not to remove any of the near by components.
> 2. Place the device as shown with some double sided tape or a little bit of blu-tack to insulate it from the GBA board and use the wiring below.
>
> Device V+ to GBA SI
> Device V- to GBA GND
> Device CLK to GBA CK1
> Device 1 to GBA TP2 (Select) or TP3 (Start)
> Device 2 to GBA TP9 (L trigger)
> Device 3 to GBA TP8 (R trigger)

Six wires. Module is **18 × 12 × 1.6 mm** (their published dimensions), draws ~12 mA of its own
plus 40–60 mA more when the console is actually overclocked. GBA firmware offers
0.333x / 0.5x / 0.666x / 1x / 1.25x / 1.5x / 1.75x, selected by holding **Select** and tapping
**L** or **R**; hold Select for 2 s to return to 1x.

### "GBA SI" is a typo for the pad silkscreened **S1**, and S1 is the 3.3 V rail

This matters, because "SI" reads as the link-port serial-in line, which would be a nonsense place
to draw 12 mA. It isn't that. In insideGadgets' own install photo the red V+ wire lands on the
pad silkscreened **`S1`**, in the `C2 S2 C1 S1` group at the right-hand end of the cartridge
connector's solder row. On the AGBM that pad is `P1` pad `S1`, and it is on net **`VDD3`** — the
switched 3.3 V logic rail — on **all three board variants**:

```
P1 (CART SLOT) pad S1  ->  VDD3     (AGBM-01, AGBM-02, AGBM-11: identical)
P1             pad C1  ->  VDD35
P1             pad S2  ->  VDD5
P1             pad C2  ->  /CPU/IN35
```

So: **V+ = VDD3**. On the AGBM, VDD3 comes off `U18` (TPS22917 load switch) fed from `VOUT3`,
which means the module powers down with the console — no standby drain. Same behaviour as a
stock GBA.

---

## 2. Where each signal already lives on the AGBM

All coordinates are KiCad board coordinates in mm, front side (`F.Cu`) unless noted.
The oscillator corner (`X1`, `C3`, `C4`, `R1`, `R41`, `TP80`, `TP81`) and the `L`/`R`/`SEL` tap row
are **identical across AGBM-01, AGBM-02 and AGBM-11** — same coordinates, same nets — so one ECO
covers all three. Only the power test points differ: `TP21` is `VDD3` on AGBM-01/-02 but `VUSB` on
AGBM-11, where the `VDD3` test point is `TP16` (F.Cu, 32.30, −34.20) and a lone `GND` test point
`TP25` sits at 9.80, −12.40. None of those are near the clock corner on any variant.

| CXC pin | AGBM net | Already exposed at | Coordinates |
|---|---|---|---|
| `CLK` | `/CPU/CK1` | **`TP80`** (silkscreen `CK1`) | 48.00, −58.00 |
| `1` (Select) | `/CPU/TP2` | **`TP29`** (silkscreen `SEL`), also `TP2` | 57.00, −69.80 |
| `2` (L) | `/CPU/TP9` | **`TP28`** (silkscreen `L`), also `TP9` | 51.00, −69.80 |
| `3` (R) | `/CPU/TP8` | **`TP27`** (silkscreen `R`), also `TP8` | 54.00, −69.80 |
| `V+` | `VDD3` | *nothing usable nearby* — `TP21` is on **B.Cu** (42.70, −42.00); `P1.S1` is at the cart connector | — |
| `V-` | `GND` | *no GND test point at all* on AGBM-01/-02 | — |

That is the entire gap. **Four of six signals already have labelled front-side pads**, three of
them (`L`, `R`, `SEL`) grouped in one row at 3 mm pitch that MouseBiteLabs put there for the
hotkey/touch-control mods. The two that are missing are the two boring ones: 3.3 V and ground.

![AGBM-01 front, ClockxControl-relevant areas](render/agbm01_cxc_overview.png)

---

## 3. The crystal circuit, and what happens when you dump it

Straight out of the board file — `U1` is the AGB CPU, pins 113/114 are XIN/XOUT:

```
U1.113 (CK1) ──┬── R1 1.5M ──┬── U1.114 (CK2) ── R41 2.2k ──┬── X1 pad 2
               │             │                              └── C4 33p ── GND
               ├── C3 27p ── GND                             (net: Net-(C4-Pad1))
               ├── X1 pad 1  (4.194304 MHz, HC-49)
               └── TP80 (test point "CK1")            TP81 sits on CK2
```

Nothing else on the board touches `CK1` or `CK2` — no second consumer, no buffer, no divider.
The whole system clock is derived inside the CPU. So substituting an external driver is a
one-node change.

**For a ClockxControl build:**

- **`X1` — do not populate.** This is the mod's own requirement.
- **`C3` (27 p) — do not populate.** It is the XIN load cap; with the crystal gone it is just
  27 pF hung on the module's output. Harmless if left (≈0.37 mA of extra drive current at
  4.19 MHz, more when overclocked) but there is no reason to keep it.
- **`C4` (33 p) — do not populate.** Dangling once the crystal is gone.
- **`R41` (2.2 k) and `R1` (1.5 M) — may stay.** `R41` is the XOUT drive-limiting resistor and
  ends up driving nothing. `R1` is the 1.5 M bias resistor; leaving it couples the externally
  driven CK1 to the CPU's own (now unloaded) inverter output through 1.5 MΩ, which is nothing.
  insideGadgets' stock-GBA instructions only say to remove the crystal, so the caps and resistors
  staying in place is the field-proven configuration anyway.

**Keep the footprints.** Deleting X1/C3/C4 from the design would mean the board cannot boot
without a $23 add-on installed, would diverge from upstream for every builder who does not want
the mod, and would remove the fallback if the module ever fails. A DNP line in the BOM plus a
build note gets you everything and costs nothing — the same pattern ECO-5 used for `JP2`.

---

## 4. Why a real mezzanine footprint does not work

"Footprint" in the strong sense — a land pattern the module solders straight down onto — fails on
four independent counts. Any one of them is enough.

### 4.1 The module's pads face the wrong way

Every published install photo shows the module mounted **component-side up**, with wires soldered
to pads on its **top** face: three at the left edge (`CLK`, `V-`, `V+`) and a 2 × 3 grid of six
larger pads at the right end (`1`, `2`, `3`, each apparently doubled). There are no castellations
and no documented bottom-side pads. To solder it face-down onto a land pattern you would need it
to have a mating surface it does not have; face-down mounting would also put its own components
(TSSOP, QFN, and a crystal can, ~1 mm tall) against the AGBM.
*Inference from photographs — insideGadgets publishes no mechanical drawing. See §7.*

### 4.2 There is no 18 × 12 mm flat area on the component side of the AGBM

Scripted scan of `AGBM-01_AA_1-2.kicad_pcb`: rasterise the `Edge.Cuts` outline, mask out every
front-side footprint courtyard, then search for a free axis-aligned rectangle.

| Requirement | Clearance allowance | Result on `F.Cu` |
|---|---|---|
| 18 × 12 mm | 0.3 mm | **none** |
| 18 × 12 mm | 0.0 mm (best case, parts touching) | **none** |
| 12 × 18 mm (rotated) | 0.0 mm | **none** |
| 18 × 11 mm | 0.1 mm | one window, x 108.7…127.7, y −21.1…−10.1 |

…and that single 18 × 11 window is entirely inside the board's own mechanical keepout at
x 108.7…137.9, y −28.7…7.7 (speaker / volume wheel). So it is not available either. The
component side of the AGBM has nowhere to lay this module flat.

### 4.3 The back side is a hard cartridge keepout

The obvious answer — "put it on the back, there's loads of room" — is wrong, and the board file
says so explicitly. MouseBiteLabs defined a rule area on `B.Cu`:

```
keepout zone, B.Cu, x 33.1..105.1, y -54.2..-32.2   (72 x 22 mm)
    footprints: not_allowed
    pads:       not_allowed
```

That 72 × 22 mm rectangle is the reason the back of the board looks empty behind the CPU. It is
where the game pak sits once inserted. Everything the free-space scan reported as "available" on
`B.Cu` in that band is inside it. (Other mechanical keepouts on the board follow the same logic:
the D-pad and A/B membrane areas, the speaker/volume corner, and two narrow strips along the top
edge at y −69.1…−64.9 that read as front-shell ribs.)

### 4.4 The module's pad geometry is not published

insideGadgets sell an assembled unit; the hardware design is not released. A land pattern needs
pad centres to about ±0.1 mm, and photogrammetry gets nowhere near that (§7 has my estimate, with
±0.3 mm error bars, expressly not for fab). Anyone drawing this footprint has to measure a
physical unit with calipers or get a drawing from insideGadgets.

### Where the module *does* go

On a stock GBA, insideGadgets tape it on top of the WRAM chip, immediately right of the CPU. The
AGBM keeps its RAM (`U2`) in the same general place — body spanning roughly x 80.3…100.0,
y −64.1…−51.5 on the front — so the stock mounting spot maps across essentially unchanged. That
is the reference position for a build, and it is why MouseBiteLabs lists the mod as "potentially
compatible": the button test points are in their original locations, and the RAM is in about its
original location.

---

## 5. Recommended ECO — "CXC service pads"

Two pads. That is the whole change.

Extend the existing `TP81`/`TP80` test-point column (1.9 mm pitch, `Bucketmouse:TestPoint_Pad_D1.0mm`)
upward by two more pads into a pocket that is verified clear on **all** variants:

| New ref | Net | Position | Nearest source | Notes |
|---|---|---|---|---|
| `TP82` | `GND` | 48.00, −59.90 | In1.Cu ground plane directly underneath | via to plane; `C3` pad 1 is 2.5 mm away as an alternative |
| `TP83` | `VDD3` | 48.00, −61.80 | `C50` pad 1 at 50.23, −62.40 | 2.3 mm surface trace |

Resulting front-side column, top of board downwards: `3V3` (−61.8) · `GND` (−59.9) ·
`CK1` (−58.0) · `CK2` (−56.1). Silkscreen the two new ones `3V3` and `GND` in the same style as
the existing `L` / `R` / `SEL` labels, and add a `CXC` group label.

**Clearance check** (footprint courtyards, all four board files — AGBM-01, AGBM-02, AGBM-11 and
this fork's `AGBM-01_AA_1-2_GBE-plus.kicad_pcb`): the pocket x 47.0…49.4, y −63.1…−59.1 is empty
on every one of them. Nearest neighbours are `TP80` (0.9 mm pad-to-pad), `C50` (1.0 mm to the
right), `C3` (0.9 mm to the left) and `U1`'s courtyard (2.7 mm). Both new pad sites are covered by
the `In1.Cu` ground plane, so the GND pad is a via drop. Neither site is inside any mechanical
keepout.

**Why here and not next to the RAM.** The tempting alternative is to put all six pads together in
the genuinely free strip below `U2` (x 82…103, y −51.3…−42, about 21 × 9 mm and clear of
keepouts), right where the module gets taped down. Don't — not without a jumper. That would mean
running `CK1` about 40 mm across the board to reach it, and `CK1` is an oscillator node. On a
board built the normal way, with the crystal fitted, that stub adds parasitic capacitance to the
Pierce loop and degrades a circuit that currently works. If you want the pads there anyway, put a
solder jumper in series so the stub is disconnected for crystal builds — but two pads by the
crystal and a slightly longer wire is the cheaper answer, and long wires are what this mod uses on
a stock GBA regardless.

**BOM change:** mark `X1`, `C3`, `C4` as *"do not populate when installing an insideGadgets
ClockxControl"*, with a build note pointing at the four-pad column and the `L`/`R`/`SEL` row.

After this ECO a ClockxControl install on an AGBM is: six wires, two landing groups, both
labelled, nothing to trace out with a multimeter.

---

## 6. Compatibility notes and risks

**Hotkey combos partially overlap.** The AGBM's own hotkey logic is discrete, not firmware:
`U15` (SN74LVC1G332, 3-input OR) takes Start (`TP3`), R (`TP8`) and L (`TP9`) and produces
`/CPU/LRST`; `U16` (SN74HC02 quad NOR) then gates `LRST` against Select (`TP2`), A (`TP0`),
B (`TP1`) and a D-pad line (`TP6`) to drive the reset and touch-control FETs. So AGBM hotkeys are
**Start + L + R + one of {Select, A, B, D-pad}**, while ClockxControl is **Select + L/R**. They do
not collide in normal use, but holding Select + L + R and then pressing Start will drive both.
Worth a line in a build sheet.

**The module taps the same button nets the AGBM's own logic uses.** `TP2`/`TP8`/`TP9` already
carry 15 Ω series resistors and 0.01 µF caps (`R43`/`R44`, `C63`/`C64`/`C78`) plus the OR-gate
inputs. Adding a high-impedance monitor is fine; do not expect to *drive* those nets.

**Power.** +12 mA continuous on `VDD3`, +40–60 mA when actually overclocked. At 3.3 V that is
roughly 40 mW idle and up to ~200 mW overclocked. The AGBM's headline efficiency claim is ~150 mW
less draw than a Funnyplaying GBA — so running overclocked spends that advantage and then some.
Battery-life figures in the AGBM READMEs do not apply to an overclocked build.

**Screens and carts** (insideGadgets' own caveats): works with the FP IPS kit; the FunnyPlaying
laminated IPS is reported good to 1.25x and fades to black at 1.5x; the OneChip IPS is reported
glitchy. GBA flash carts crash above 1x; genuine carts are generally fine; 1.75x is the ceiling.

**Underclocking and the AGBM's audio chain — untested, flagged.** The GBA's PWM audio carrier
scales with the system clock, and MouseBiteLabs put real work into the AGBM's analogue
reconstruction path (`U7` TLV9364 and friends), tuned around stock timing. At 0.5x and especially
0.333x the carrier drops toward the audio band. Expect artefacts, possibly different from what a
stock GBA does. This is reasoning from the topology, not a measurement.

**No crystal means no clock.** With `X1` unpopulated the console will not boot without the module
fitted and working. Obvious, but it makes the module a single point of failure and makes
bring-up testing harder — you lose the ability to check the CPU comes alive before the mod goes
on. Building the board with the crystal, testing per the wiki, then removing `X1`/`C3`/`C4` is the
safer order.

**Overclocking and the RAM — the desalvage part is the *better* one here.** At 1.75x the system
clock is ~29.4 MHz, so a 3-cycle 16-bit EWRAM access shortens from ~179 ns to ~102 ns. The
CY62157EV30LL-45Z from ECO-5 still has better than 2x margin at that speed. A salvaged original
GBA WRAM has less headroom. If this fork ends up carrying both mods, that is a point in the
de-salvaged board's favour, not against it.

---

## 7. Appendix — photo-derived module pad estimate (NOT for fab)

Scaled off insideGadgets' install photo `IMG_6317.jpg`, using the published 18 × 12 mm outline as
the reference (≈27.9 px/mm). Origin = module's top-left corner, x right, y down.
**Error bars are roughly ±0.3 mm** — perspective, solder blobs and eyeballed pad centres.
Good enough to reason about the layout; useless for drawing a land pattern.

| Pad | Est. position (mm) | Notes |
|---|---|---|
| `CLK` | 3.0, 1.1 | left edge, small round pad |
| `V-` | 1.1, 2.7 | left edge |
| `V+` | 1.0, 4.6 | left edge |
| `1` (top pair) | 13.3, 3.7 and 15.9, 3.7 | large round pads, ~1.3 mm |
| `2` (mid pair) | 13.4, 6.5 and 15.8, 6.4 | column pitch ≈2.5 mm |
| `3` (bottom pair) | 13.3, 8.8 and 15.7, 9.0 | row pitch ≈2.6 mm |

Shape of the thing: three signals at the far left edge, six big pads clustered in the right ~5 mm,
13 mm apart. Even with exact numbers, that split means a land pattern would have to span the whole
module length — which brings you straight back to §4.2 and the missing 18 × 12 mm of flat board.

---

## 8. Open items

1. **Measure a physical ClockxControl** — pad centres, pad diameters, whether the pads are plated
   through, and what is on the underside. Everything in §4.1 and §7 is inference until then. Or
   ask insideGadgets for a drawing; if they will make a castellated-edge variant, a genuine
   mezzanine footprint becomes a real option.
2. **Shell / screen clearance for the module** on an AGBM specifically. The stock spot on top of
   `U2` is ~1.2 mm of RAM plus 1.6 mm of module plus wires. The AGBM build guide already warns
   that `X1` must sit flush "or you might have interference with the screen", so vertical margin
   over there is not generous. Same class of open item as ECO-5's front-shell fit: it needs a
   shell, a screen kit and calipers.
3. **If the ECO in §5 gets cut into the board**, it is two pads, one 2.3 mm trace, one via and two
   silkscreen strings — but it still needs KiCad DRC, a re-pour, and the pads adding to the
   schematic so the netlist stays consistent.

---

## Sources

- insideGadgets, [GBA/GBC/DMG ClockxControl](https://shop.insidegadgets.com/product/gba-clockxcontrol/) — install wiring, dimensions, firmware speeds, current draw, screen/cart compatibility, and the install photos referenced in §1 and §7.
- MouseBiteLabs, [Game Boy Enhance wiki — Mod Compatibility](https://github.com/MouseBiteLabs/Game-Boy-Enhance/wiki/Mod-Compatibility) — lists ClockxControl as potentially compatible and notes the button test points kept their original locations.
- MouseBiteLabs, [AGBM-01 (AA) Build/Test Order](https://github.com/MouseBiteLabs/Game-Boy-Enhance/wiki/AGBM-01-%28AA%29-Build-Test-Order) — the X1 flush-mounting / screen interference warning.
- This repository: `AGBM-01 (AA Batteries)/AGBM-01_Design Files.zip`, `AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip`, `AGBM-11 (Lithium-ion)/AGBM-11 Design Files.zip`, and `agbm-01-ram-desalvage.zip` (ECO-5).

## License & attribution

Derivative analysis of the **MouseBiteLabs Game Boy Enhance (AGBM)**, licensed
**CC BY-SA 4.0** — https://github.com/MouseBiteLabs/Game-Boy-Enhance. This document and the
rendering in `render/` are released under the same licence. The ClockxControl is a product of
insideGadgets; no part of their design is reproduced here.
