# AGBM-01 component review — efficiency, stability and quality, with the ClockxControl in scope

A component-level review of MouseBiteLabs **Game Boy Enhance AGBM-01 rev 1.2** as forked here,
asking one question: **which parts are worth upgrading, and can that win back the energy the
ClockxControl overclock costs?**

Everything below was derived from the KiCad design files in this repository or from a datasheet or
distributor page that was actually fetched. Nothing is asserted from memory. Where a number is an
estimate rather than a measurement, it says so.

---

## Short answer

**Yes, but only at the PCB-revision tier.** Running the ClockxControl at 1.75x costs roughly
**146 mW at the battery** (the module's own ~45 mW plus ~100 mW of extra console draw). Against that:

| Tier | What it takes | Recovered at 1x | Recovered at 1.75x |
|---|---|---|---|
| **Drop-in parts only** | five part swaps on existing land patterns | ~32 mW | ~40 mW |
| **+ one PCB revision** | transplant AGBM-02's converter | +29 mW (idle) | +26 mW |
| **+ schematic change** | switch the CPU core rail off its LDO | +22 mW (idle) | +60 mW |
| **Total** | | ~83 mW | ~126 mW |

So at full effort you win back about **86% of what the overclock costs** — and the drop-in tier
alone, which is five parts and no board change, covers about a quarter of it.

**But read the blockers first. The board in this fork does not currently boot.**

---

## 1. Blockers — three defects in the fork's own board

These are not upgrades. They are faults in the committed board, found by reading the `.kicad_pcb`
files and diffing the fork against stock AGBM-01. **No board should be fabricated or sent to an
assembly service until these are resolved.**

### 1.1 The RAM's VCC pin 37 has no supply

ECO-5 (the RAM desalvage) removed two VDD2 vias at (100.8, −56.6) and (100.8, −55.2) and three
F.Cu VDD2 tracks, and added a third pin-37 pad at (100.31, −58.05). What is left:

- U2 pin 37 has three F.Cu pads at (95.100, −58.050), (98.968, −58.050) and (100.310, −58.050),
  joined only to each other by one F.Cu track.
- **There is no VDD2 via anywhere on the board with x > 93**, so nothing ties that group to the
  In2.Cu VDD2 plane.
- The F.Cu VDD2 zone that appears to cover them is a **6.89 mm² orphan island** — and the zone fill
  data is byte-identical to stock, i.e. the fork was never re-poured. On a re-pour KiCad will most
  likely delete that island outright.

Pins 12 and 16 *are* connected (they sit in the 59.68 mm² F.Cu VDD2 zone that is tied to the plane
at (83.227, −56.074) and (83.4, −45.9)), so a built board may partly work and behave erratically —
the worst possible failure mode on a salvaged RAM, because it looks exactly like a bad solder joint.

**Fix:** restore two 0.3 mm vias at the stock coordinates (100.8, −56.6) and (100.8, −55.2) — both
verified to lie inside the F.Cu island *and* the In2 VDD2 plane — route C8's VDD2 pad back to that
island, and re-pour.

This one is at least **documented**: the fork's own README says the VDD2 feed to U2 pin 37 and the
ground-via re-stitching are "deliberately left for the interactive router" and warns "Do not send
this to a board house without finishing the items."

### 1.2 `Net-(Q5B-G)` is open — and this one is undocumented

ECO-5 also deleted the via at (100.8, −62.15). That via was the only join between the In1.Cu run
coming from U17 pin 1 and the B.Cu run reaching Q5 pin 3 and R66 pin 2. Both files still contain
all ten segments of the net; only the via is missing.

Consequence: U17's `/RESET` output can no longer pull Q5B's gate down, R66 (100 k to VOUT5) holds
it permanently high, and **the low-battery LED indication is dead**.

The fork's README lists "five GND stitching vias" as removed. Of the five vias actually removed,
**only two are GND** — two are VDD2 (§1.1) and one is this signal net. The documentation
under-reports what was cut.

**Fix:** restore a 0.7/0.3 mm via at (100.8, −62.15). Better, re-route the net off In1.Cu entirely —
it is currently 10.54 mm of signal routing *inside the ground plane*, which is both a return-path
slot and a trap for the next person editing near U2.

### 1.3 ECO-6 does not mark X1/C3/C4 as DNP

Mine, and a real miss. The ClockxControl requires the crystal removed, but `X1`, `C3` and `C4` ship
as fitted parts in the ECO-6 board, so a builder ordering assembly gets a crystal soldered onto a
node the module is trying to drive.

There is a second, subtler error in the ECO-6 write-up itself: it says C4 is left dangling with the
crystal gone. **It is not.** C4 remains connected to CK2 through R41, so it stays loaded on the
oscillator node whether or not X1 is fitted. Worth ~2 mW at 1.75x, and the documentation is simply
wrong about the topology.

---

## 2. Where the energy actually goes

### The rails, computed rather than assumed

The LTC3527's feedback reference is 1.20 V (datasheet 35271fc). With the dividers on this board:

```
VOUT5 = 1.20 x (1 + 1.78M/560k)  = 5.014 V
VOUT3 = 1.20 x (1 + 1.78M/1.00M) = 3.336 V
VDD2  = VAUD = 2.500 V   (NCV8164ASN250T1G, fixed)
```

Which makes both LDOs **74.87% efficient** — an arithmetic match to MouseBiteLabs' own remark that
the audio supply is "roughly 75% efficient". That match is what confirms the whole model is right:
the audio rail's inefficiency *is* U4's dropout, not anything exotic.

### The three structural losses

**The CPU core rail is linear.** U8 drops 3.336 V to 2.5 V to feed the AGB CPU's four core pins and
the SRAM, throwing away 25.1% of every milliwatt the core draws — 25 mW at idle, ~40 mW at 1.75x.
This is the single largest recoverable loss, and it is the one that *scales with the overclock*,
because the overclock's extra current is core current.

**AGBM-01 has the wrong converter.** It idles at 170 mW against AGBM-02's 141 mW and a stock GBA's
134 mW. The only power-path difference is the converter — both LDOs, all three load switches and all
three supervisors are identical between the two boards. The investigation **killed my own initial
hypothesis** that a boost near VIN≈VOUT was to blame: 2×AA never reaches 3.336 V, so the LTC3527
always boosts. The real cause is that the LTC3527 makes **one Burst Mode decision for both
channels**, so the ~0.7 mA 5 V rail is dragged into fixed-frequency 1.2 MHz PWM whenever the 3.3 V
rail is loaded. About 11 of the 29 mW is attributable from published curves; the rest could not be
separated and is honestly reported as unexplained.

**The heavy rail is on the weak channel.** VOUT3 carries VDD2, VAUD and VDD3 — all logic, all cart,
all audio — and it sits on LTC3527 **converter 2**, the 400 mA channel (0.50/0.60 Ω switches). The
800 mA channel drives only the screen rail. At 1.75x, VOUT3 demands ~212 mA against a guaranteed
capability of ~220 mA at VIN 2.4 V falling to ~178 mA at the 2.0 V supervisor cutoff. **The
overclock consumes most of the remaining margin on nearly-flat cells.**

### What the overclock costs

insideGadgets publish ~12 mA for the module plus 40–60 mA more when overclocked. The review flags
that **the 40–60 mA is a system-level figure with no rail attribution, no speed and no measurement
point stated** — treat it as an anchor, not a specification. Tracing it through the power tree gives
roughly 146 mW at the battery at 1.75x.

Two things it does *not* do: **U8 is not the bottleneck** (≈3.5x current margin and ≈4x thermal
margin at 1.75x — 68.6 mW dissipation, 11 °C junction rise), and **the SRAM is comfortable**
(CY62157EV30LL-45 has 2.3x timing margin at 29 MHz). Nothing on this board is thermally stressed
overclocked or not; the largest junction rise found anywhere was ~16 °C.

---

## 3. Recommendations

### Tier 1 — drop-in, no board change (~32 mW at 1x, ~40 mW at 1.75x)

| Change | Refs | Saving | Confidence |
|---|---|---|---|
| **PPTC 0805L075SLYR → 0805L150SLYR.** Same series, same 0805 land, same recommended pad layout. R₁max drops 160 → 65 mΩ. | `PTC1` | 12 mW (range 6–23) | 0.85 |
| **Op-amp TLV9364 → TLV9064IPWR.** Pin-identical TSSOP-14, and *cheaper*. See §4.1 — this is a correctness fix first. | `U7` | ~10 mW | 0.92 |
| **Power LED → InGaN green at 0.12 mA.** The fitted AlInGaP part burns 4.66 mW continuously; an InGaN in the same 0603 pads is brighter at a fraction of the current. | `DL1` | 4.8 mW | 0.88 |
| **VOUT3 setpoint: R23 1.78 M → 1.69 M.** Drops VOUT3 to 3.228 V, cutting both LDOs' dropout. Floor analysis done: the binding constraint is the cart rail, not the LDOs. | `R23` | 4.1 / 10.3 mW | 0.75 |
| **Three bias-resistor changes.** Brownout latch R15/R16 10 k → 100 k; MIC1553 CS pull-down R65 100 k → 1 M; supervisor dividers scaled 10x. | `R15 R16 R65` + | 1.2 mW | 0.80+ |

Note `PTC1` also fixes a **stability** problem, not just an efficiency one — see §4.2.

### Tier 2 — one PCB revision (+29 mW idle, +26 mW in use)

**Transplant AGBM-02's converter.** Two TPS63802 in place of the one LTC3527, with 0.47 µH
inductors, exactly as AGBM-02 does it (U5 → VOUT5 with 820 k/91 k, U13 → VOUT3 with 510 k/91 k at a
500 mV reference). Note the existing 560 k and 1 M low-side resistors **violate** the TPS63802's
≤100 kΩ requirement and must change. Delete C40/C41; AGBM-02 has no feed-forward caps.

Beyond the measured 29 mW: converter 2's 400 mA ceiling disappears (4 A limit), the part is
buck-boost so it stays in regulation above VOUT3 on fresh alkalines, each device makes its own PFM
decision so the 5 V rail is never dragged out of power-save, and **sourcing improves markedly** —
TPS63802DLAR is widely stocked at ~$0.62–1.74 against the LTC3527's $1.81–4.52 and backorder. That
last point matters directly for the PCBWay plan.

### Tier 3 — schematic change (+22 mW idle, +60 mW at 1.75x in-game)

**Move the CPU core rail off its LDO.** A TPS62840DLC buck from VOUT3 at 2.5 V (RSET = 11.5 kΩ).
The verifier corrected the efficiency basis upward — TI's Figure 18 is the VOUT = 2.5 V curve, ~91–93%
between the VIN 3.0 and 3.6 V traces — so the saving is *larger* than first claimed.

Honest costs, all raised by the adversarial pass:
- U8's `PGOOD` output is **load-bearing** for the whole power-up sequence (it gates U4, U18 and U5's
  SHDN1), so this needs a replacement supervisor, not just a swap.
- It needs a 1.5 × 2 mm SON-8 land plus an inductor, on a board whose one component-free window is
  now occupied by the ClockxControl.
- A 1.8 MHz buck beating against the LTC3527's 1.2 MHz gives a 600 kHz difference tone in a console
  whose designer went to the trouble of a dedicated LDO for the audio rail.
- The LDO's 9 µVrms output noise is replaced by PFM ripple on a salvaged CPU's core rail.

**Not recommended: class-D for the speaker.** Worth ~48 mW at max volume, but it costs a schematic
redesign and puts a 250 kHz switcher next to the ClockxControl on a board whose selling point is
audio quality.

**Also keep U4 (VAUD) linear.** Its PSRR is worth far more than the ~4 mW it costs.

---

## 4. Correctness and stability findings

### 4.1 U7 is running outside its datasheet

`U7` is a **TLV9364, minimum supply 4.5 V**, running on the 2.5 V VAUD rail with its inputs at
1.25 V — above the part's `(V+) − 2 V` common-mode ceiling. It works, but nothing about its
behaviour is guaranteed, and it is drawing far more current than a correctly chosen part would.

The **TLV9064IPWR** is 1.8–5.5 V, true rail-to-rail input, 538 µA/amp, pin-for-pin identical in the
same TSSOP-14, in stock, and cheaper than the part fitted. The saving was revised down from 30.6 mW
to **~8.4–11.6 mW** by digitising TI's own IQ-vs-supply curve, because the 2.6 mA/amp figure is only
guaranteed at ≥4.5 V and the real current at 2.5 V is unmeasured.

**This is an upstream bug, not a fork bug.** It is worth reporting to MouseBiteLabs regardless of
what is done here.

### 4.2 PTC1 trips before the overclock does

`PTC1`'s hold current derates to 0.62 A at 40 °C and **0.47 A at 60 °C**. Peak in-use input current
is already ~0.49 A, and the ClockxControl pushes it to roughly 0.54–0.58 A. Inside a closed shell
with the backlight at maximum, the board is at or past its PPTC hold current *before* the overclock
and over it after. The Tier-1 swap fixes this as well as saving power.

### 4.3 The BOM contradicts itself on both protection parts

`F1` and `PTC1` carry **three different part numbers between them**: the schematic says
`F0805B2R00FSTR` and `0805L075SLYR`, both PCB footprints carry the stale Value `0467001.NR` — a
0603 1 A fuse in an 0805 land — and both KiCad Description fields say `0805L050WR`. Whichever is
authoritative, the layout's value would delete the resettable protection entirely. `R3`, `R4` and
`R64` also differ between schematic and PCB, and `U8`/`U4` are drawn with a symbol named `MCP1824`
while their Value is `NCV8164ASN250T1G`. **This must be resolved before any BOM goes to an
assembler.**

### 4.4 Other stability items worth knowing

- **`D1` is not a reverse-battery clamp that works.** It is not a Schottky, it is 7–13x under-rated
  for the job, and it sits on the wrong side of F1 so its fault current bypasses the fuse.
- **The SRAM has no local decoupling.** ECO-5 moved C8 7.2 mm away from pin 37 (and left its VDD2
  terminal unconnected, per §1.1). Restore a 0.1 µF within 1.5–2 mm of pin 37. The reviewer's own
  droop arithmetic was corrected downward — pins 12/16 sit in a pour, not a trace — but the
  direction is not in doubt: you do not remove a decoupling cap from beside a 16-bit SRAM and then
  clock it 75% faster.
- **`CP1`/`CP2`/`CP3` are polarized tantalums on a symmetric MLCC land with no polarity marking
  anywhere on the board**, and CP1 carries bidirectional AC with zero DC bias, reverse-biasing it
  past AVX's own 1 V limit.
- **The ClockxControl clock run is poorly referenced.** 73.5 mm GND-referenced for only 5.9 mm,
  changing reference-plane net 15 times and crossing 5 plane slots. A series-termination land at
  TP83 is cheap insurance for the salvaged CPU's XIN input.

---

## 5. What was checked and found fine

47 of the 100 findings are negative results. They are worth as much as the positive ones, because
they say where *not* to spend effort:

- **Thermal: nothing is near a limit**, overclocked or not. Largest junction rise found: ~16 °C.
- **VDD2 layout is fine** — under 1 mV of DC drop from U8 to the CPU core pins.
- **VDD2 decoupling at the CPU does not need strengthening** for 7.34 MHz; it has an order of
  magnitude in hand. (The SRAM end is a different story — §4.4.)
- **The GND/AGND split is done correctly** — single-point tie at NT1, no signal crosses it.
- **Capacitor derating is a non-issue** except C21 (−51% at 5.014 V). The parts are conservative:
  25 V X5R bulk, 16/50 V X7R decoupling, C0G feed-forward, tantalum audio.
- **No ferrite-bead resonance.** Explicitly checked and absent.
- **SW1 carries no load current** — the whole battery current bypasses it.
- **An eFuse/ideal-diode in place of F1+PTC1 is verifiably worse** at 1.8 V pack voltage.
- **The load switches, EMC parts, RA1 and the pull-ups are not levers** — together under 0.35 mW.
- **U16's HC-family choice is defensible** at 3.34 V and should be left alone.
- **`U14` is not a power switch** — it is a 555-type RC oscillator blinking the low-battery LED.
  (This corrects an assumption in the review's own brief.)

---

## 6. Method

Eight parallel domain investigations — converter, linear rails, battery path, passives, supporting
ICs, audio, ClockxControl, and thermal/EMC/layout — each required to verify every electrical number
against a fetched datasheet or distributor page and to show its arithmetic against MouseBiteLabs'
measured figures (170 mW idle, 410–1175 mW in use, taken at a 2.4 V bench supply).

The investigators emitted **102 findings**. Every one then went through an adversarial pass
instructed to **refute by default**, which re-fetched the datasheets independently rather than
trusting the citation. That pass **refuted 2 outright and revised 55 of the surviving 100** —
including correcting the U7 saving *down* by 3x, correcting the VDD2 buck saving *up*, and catching
an apples-to-oranges via count that had inflated a claim 5x. A further three-lens panel (datasheet,
systems, magnitude) on the highest-impact claims was still running when this was written; §3's
Tier-2 and Tier-3 numbers should be treated as one-pass-verified until it lands.

**Confidence is per-finding and stated.** Nothing here has been measured on hardware. The single
most valuable next step is a meter on a real board: VAUD current before and after the U7 swap, and
the installed PPTC's resistance with a milliohm meter, since both headline drop-in savings rest on
unmeasured anchors.

Machine-readable findings, with sources and verification notes: [`findings.json`](findings.json).
