# AGBM-01 component review — efficiency, stability and quality, with the ClockxControl in scope

A component-level review of MouseBiteLabs **Game Boy Enhance AGBM-01 rev 1.2** as forked here,
asking one question: **which parts are worth upgrading, and can that win back the energy the
ClockxControl overclock costs?**

Everything here was derived from the KiCad design files in this repository or from a datasheet or
distributor page that was actually fetched. Where a number is estimated rather than measured, it
says so. Nothing has been measured on hardware.

Supporting documents: the full [power budget](power-budget.md), the
[completeness critique](completeness-critic.md), and all 101 findings with their sources and
verification history in [`findings.json`](findings.json).

---

## The honest answer

**No. The energy the ClockxControl costs cannot be won back.**

Fitting the module and running it at 1.75× costs about **159 mW at the battery**. At the maximum
effort anyone proposed you recover about **69 mW, or 43 %** — and getting past 20 % needs a
schematic change plus a PCB revision on the core rail of a board built around irreplaceable
salvaged silicon.

Stated as runtime, at the 792 mW representative operating point on a 6.26 Wh pack:

| Configuration | Power | Runtime | vs stock |
|---|---|---|---|
| Stock, 1×, no module | 792 mW | 7 h 54 m | — |
| **ClockxControl fitted, 1.75×, no fixes** | **951 mW** | **6 h 35 m** | **−1 h 19 m** |
| + every drop-in fix | 919 mW | 6 h 49 m | −1 h 05 m |
| ↳ *as actually implemented in ECO-8* | *922 mW* | *6 h 47 m* | *−1 h 07 m* |
| + core-rail redesign | 885 mW | 7 h 04 m | −50 m |
| + full front-end respin | 882 mW | 7 h 06 m | −48 m |

The overclock costs you 79 minutes. Drop-in parts buy back 14 of them. Everything short of a
complete respin buys back 31.

**The de-duplicated drop-in ledger is about 20 mW off a 170 mW idle — 12 %** — plus 2 to 11 mW in
use from the PPTC. That is the real answer to the question, and it required de-duplicating five
findings that all proposed the same PPTC swap and three that all proposed the same LDO replacement.

---

## Two constraints that may make the question moot

The completeness pass found these after the eight domain reviews had finished, and they matter more
than any component swap.

**Flash carts do not work overclocked.** insideGadgets' own page: *"GBA flash carts don't seem to
work when trying to go faster than 1x as they crash."* Every 1.75× figure in the domain reviews was
computed on MouseBiteLabs' 1175 mW configuration, which is *max brightness plus an Everdrive plus
max volume*. **That configuration is not reachable.** Correcting to a genuine cartridge takes about
112 mW off the worst case and softens two stability findings from "over the limit" to "at the
limit."

**The screen is the binding constraint, not the power tree.** The LCD dot clock is exactly the
crystal frequency (4 CPU cycles per dot, 308 × 228 = 280,896 cycles per frame at 16.78 MHz), so it
scales 1:1 with the module and the kit sees **7.34 MHz at 1.75×**. insideGadgets again: *"Works with
the FunnyPlaying laminated IPS GBA screen at speed 1.25x and below. At 1.5x, the screen fades to
black… Not recommended with the GBA OneChip IPS screen."* The Hispeedido kit MouseBiteLabs
benchmarked with is not on the compatibility list at all. The only series element on the entire
display bus is `R36`, 270 Ω on the dot clock; every other line has none.

**So before optimising anything: sweep the ratio with your actual screen kit and log the highest
stable one.** If it is 1.25×, the whole power model needs re-running there and most of this document
describes a configuration you cannot use.

---

## Blockers — the board is not fabricable as committed

Detailed in [ECO-7](../clockxcontrol-integration/ECO-7_u2_supply_and_dnp.md). In short:

- **`U2` pin 37 is the SRAM's only `VCC` pin on the CY62157, and it has no path to `VDD2`.** ECO-5
  removed two `VDD2` vias and three tracks to make room for its third pad column and never finished
  the replacement ties. There is no `VDD2` via anywhere with x > 93, and the F.Cu zone that appears
  to cover the pin is an orphan island in a fill that has never been re-poured.
- **`Net-(Q5B-G)` is broken at one deleted via**, so the low-battery LED indication is dead. The
  net is fully routed — ten segments of MouseBiteLabs' own copper — but ECO-5 removed the In1↔B.Cu
  transition via at (100.800, −62.150), leaving `U17`'s supervisor output on one island and `Q5B`'s
  gate plus `R66` on another. The stock board has it whole; this fork does not. Undocumented: ECO-5's README
  says five GND vias were removed; only two of the five actually were.
- The review's proposed fix for both — restore the vias at stock coordinates — **would short `VDD2`
  to two data lines**, because those coordinates are now inside ECO-5's pad column. ECO-7 documents
  why, and why no substitute site exists.

`X1`, `C3` and `C4` are now marked DNP, which ECO-7 implemented.

---

## Where the energy actually goes

Full accounting in [power-budget.md](power-budget.md), with every line labelled measured, derived or
estimated. The headline structure:

The LTC3527's feedback reference is 1.20 V, so `VOUT3` = 1.20 × (1 + 1.78 M/1.00 M) = **3.336 V**
and `VOUT5` = **5.014 V**. Both `NCV8164` LDOs drop that to 2.500 V, making them **74.87 %**
efficient — an arithmetic match to MouseBiteLabs' own "roughly 75 % efficient" remark about the
audio supply, which is what confirms the model is on the right rails.

*(ECO-8 later trimmed `VOUT3` to 3.228 V and **[ECO-12
§12.2](../clockxcontrol-integration/ECO-12_wiki_audit_corrections.md) reverted it**, so this
model's 3.336 V is again the rail the board actually produces. The trim was worth 6.1 mW and cost
108 mV of headroom on the bus a 1.75× overclock stresses — the wrong trade for this fork, and
against the build guide's own Test 3.)*

At idle, 148 of the measured 170 mW is accounted for and **22 mW is not**. That residual is almost
certainly LTC3527 light-load overhead — it is the same energy as the measured AGBM-01/AGBM-02 gap —
but the published curves say the converter should be doing better than the measurement shows, and
that cannot be reconciled from datasheets alone.

In use, two facts dominate:

- **The backlight is 58 % of the console.** Every lever here operates on the remaining 42 %.
- **Converter 1 is the largest single loss on the board, 60.7 mW** — more than double converter 2's,
  because it carries 91 to 130 mA through the 0.3/0.4 Ω switch pair. It is also the channel nobody
  proposed changing.

### What the overclock costs

insideGadgets publish one sentence: *"Consumes about 12mA of additional current and when the
GBA/GBC/DMG is overclocked, it too will use 40-60mA more."* **That is a system-level, battery-side
figure** — no measurement point, no speed, and the identical 40–60 mA is quoted for three different
consoles at three different ratios. Reading it as a `VOUT3` current, which several domain reviews
did, inflates the overclock's cost by about 60 %.

Every part of the cost lands on **LTC3527 converter 2, the 400 mA channel**: the module's supply via
`VDD3`, the extra core current via `VDD2` (which an LDO passes 1:1 to `VOUT3`), and the cart bus.

| | mW | share |
|---|---|---|
| **Useful work at the load pins** | **125.0** | 78.6 % |
| **Conversion and series loss** | **34.3** | 21.6 % |
| — `U8` LDO on new core current | 15.0 | 9.4 % |
| — converter 2 extra loss | 12.0 | 7.5 % |
| — `F1` + `PTC1` series | 7.3 | 4.6 % |

**Just over a fifth of the overclock's cost is loss rather than work**, and the largest single piece
is `U8` — an LDO throwing away 0.836 V on every milliamp of new core current. That is the only loss
the overclock *creates* rather than merely enlarges.

**Fitting the module costs 45 mW before it overclocks anything**, which at idle is 26 % of the
board's entire 170 mW. No lever in this review touches it.

---

## What to actually do

### Drop-in, no board change — **implemented, see [ECO-8](../clockxcontrol-integration/ECO-8_component_swaps.md)**

| Lever | 1× | 1.75× | In the board? |
|---|---|---|---|
| **`U7` TLV9364QPWRQ1 → TLV9064IPWR** | 12.0 mW | 12.0 mW | yes |
| **`VOUT3` trim, `R23` 1.78 M → 1.69 M** | 6.1 | 8.2 | yes |
| **`DL1` → InGaN green + `R25` 3.3 k → 22 k** | 4.6 | 4.6 | yes |
| **`PTC1` 0805L075SLYR → 0805L110SLYR** | 2.2 | 3.2 | yes |
| `R15`, `R16` 10 k → 100 k (brownout latch) | 0.74 | 0.73 | yes |
| `R65` 100 k → 470 k (MIC1553 `CS`) | 0.25 | 0.25 | yes |
| `R11` 1 k → 10 k **with** `R24` 100 k → 1 M | 0.05 | 0.05 | yes |
| `R3`/`R4`/`R58`/`R63` supervisor dividers | 0.19 | 0.19 | **no** — see below |
| `R12` 100 k → 470 k | 0.04 | 0.04 | **no** |
| **Total implemented** | **25.9 mW** | **29.0 mW** | |

ECO-8 is thirteen `Value`/`Description` edits and no copper: a 26-line diff against the ECO-7 board,
geometry byte-identical. At idle the implemented set is **21.8 mW off 170 mW, 12.8 %**; at 1.75× it
is 29.0 mW off 951 mW, taking runtime from 6 h 35 m to **6 h 47 m**. It also cuts the post-brownout
latched-off drain from 6.90 mW to 0.98 mW.

Two levers were left out. The **supervisor dividers** cannot be scaled while `R3` and `R4` have
different values in the schematic (5.1 k / 33 k) and in the PCB (1 k / 10 k) — scaling a disputed
baseline sets a battery-warning threshold nobody can predict. **`R12`** is 44 µW, below the
resolution of this entire model, on the one node where leakage would silently disarm the brownout
latch.

ECO-8 also **corrects the review's `PTC1` derating figures**. The findings quote 0.62 A at 40 °C and
0.47 A at 60 °C for the fitted part; the Littelfuse Low Rho datasheet (rev GD 03/06/25) says
**0.55 A and 0.40 A**, and there is no 50 °C column at all. The real derating is worse than the
review claimed, so the case for the swap is stronger, not weaker. ECO-8 also records the one thing
this change set makes worse — the `R25` = 22 k / InGaN pairing narrows the `Q9B` gate margin on the
low-battery LED — with the arithmetic showing it still works.

**`U7` is the single best change on the board and it is not a power part.** It is a **4.5 V-minimum**
op-amp being run on 2.5 V with its inputs above the common-mode ceiling — verified against TI's own
datasheet text, not just claimed. The pin-identical TLV9064IPWR fixes it, is in stock, and is
*cheaper than the part fitted*. Do it whether or not you care about runtime.

### One PCB revision on the core rail — 66 mW total at 1.75×

Replace `U8` with a **TPS63802 buck-boost fed from `VCC`**, skipping the boost entirely for the core
rail. Take this and not the buck-from-`VOUT3` alternative, for a reason worth stating: the TPS63802
carries an open-drain PG at the same thresholds as the `NCV8164`'s PGOOD, so **`/PG_2V5` transfers
with zero added parts**. `/PG_2V5` gates `U5` pin 1, so losing it kills the 5 V boost and the CPU
never leaves reset. The buck alternative needs a fourth supervisor to avoid a dead board.

**Do not sum the tiers naively.** With `U8` gone, the `VOUT3` trim collapses from 6.1 to 2.4 mW,
because a buck's input power is set by its output power. Tier 1 + core rail, de-duplicated, is
**48.6 mW at 1× and 65.6 mW at 1.75×**.

#### MouseBiteLabs already tried this and rejected it — on audio

Added by the [wiki audit](../wiki-audit/README.md). The *Schematic Explanation* page:

> LDOs are (usually) less efficient than a switch mode power supply, but in my (admittedly early)
> testing I found that **with a SMPS for the 2.5V supply I could hear more audio noise than with an
> LDO**, so the minimal lost power is worth it in my view.

`U8` **is** the 2.5 V supply. This is not an adjacent finding — it is the same swap, tried on real
hardware, and rejected against the project's stated primary goal. The review's largest single lever
therefore has a prior negative result standing against it, and any table that lists 66 mW without
that caveat is overselling.

Two things keep it from being a flat "no":

* Nick raises the caveat himself — *"since my original testing I have done a lot to improve the
  audio quality in other ways that a 2.5V SMPS might not affect the audio quality as it used to,
  but at this point in the design I am done messing with things for such minimal gain."* The
  single-point ground and the `U9` buffer both post-date that test.
* His objection is to a switcher on **this rail**, not to switchers: **AGBM-02 is the twin-TPS63802
  board**, and he shipped it.

But `VAUD` and `VDD2` come off the same 2.5 V generation stage in his reasoning, and the buffer `U9`
that removed *all* the audible noise runs on `VAUD`, referenced to the audio ground. **Do not take
this lever without a listening test**, and note the asymmetry: the power is worth about 40 mW at 1×,
and the failure mode is the one thing this project exists to get right.

### The converter transplant — DONE, by rebasing rather than by respinning

> **[ECO-13](../clockxcontrol-integration/ECO-13_rebase_onto_agbm02.md), 2026-08-19: this
> fork now sits on MouseBiteLabs' AGBM-02, which *is* the twin-TPS63802 board.** The
> transplant this section ranks and defers is no longer a modification anyone has to make —
> it arrived with the base board, along with his verified CY62157 land, and it cost nothing
> to take because AGBM-02 is AGBM-01 with 217 of 230 footprints at identical positions.
>
> Everything below still stands as the *assessment*, and it is the reason the ranking was
> right: this is a light-load gap, not a 29 mW dividend at play. The honest summary is that
> the fork took the 29 mW because it was going to AGBM-02 anyway for the RAM land, **not**
> because the power case justified a respin. It did not.
>
> Two consequences for the rest of this document:
> * **The LTC3527 analysis is now history.** `R21`, `R22`, `R23`, `R55`, `C40` and `C41` do
>   not exist on this board, so ECO-10's feedback-divider rescale and ECO-12 §12.2's
>   `VOUT3` revert are both deleted. The 50 nA-feedback-current finding was right about the
>   wrong converter.
> * **`U8` is still an LDO**, so the core-rail item below is still live — and still carries
>   MouseBiteLabs' recorded objection to a switcher on that rail.

#### The original assessment, unchanged

The AGBM-02 twin-TPS63802 swap is the **only measured number in the review** — 170 vs 141 mW on two
boards with verified-identical downstream. But it is a **light-load-only gap**. At in-use currents
the digitised curves put the two converters within about a point of each other, and a 29 mW fixed
overhead cannot survive as 29 mW at 240 to 380 mW of rail delivery. Idle is not an operating point
anyone plays at.

**Revised from an earlier draft of this document, which ranked it second at 26 mW in use. That was
wrong.** Take it only if you are respinning the front end anyway.

### Evaluated and declined

A switcher on `VAUD` (costs the LDO's 85 dB PSRR on the rail that *is* the PWM DAC's reference), a
class-D speaker amp (~25 mW, and the TPA2005D1's 2.5 V minimum sits above `VAUD`'s worst case), a
better LDO in `U8`'s footprint (0.1 mW — any 2.5 V linear from 3.336 V is 74.9 % whatever the part),
an eFuse in place of `F1`+`PTC1` (verifiably worse at 1.8 V pack), and the **LTC3527 channel swap,
which inverts to −8 mW** once you use the designer's own annotated 130 mA for the 5 V rail.

---

## Correctness and stability findings

- **`U7` runs outside its datasheet** (above). Upstream bug, worth reporting to MouseBiteLabs.
- ~~**`D1`/`D2` are not Schottky diodes** … `D1` is 7–13× under-rated for the reverse-battery
  clamp duty the schematic assigns it~~ — **this finding does not survive checking. See
  [ECO-11 §11.2](../clockxcontrol-integration/ECO-11_gate_drive_and_D1.md).** The parts are
  indeed Rohm 1SS355VMTE-17 switching diodes rather than Schottkys, and the *rating* number
  is right — but the duty is real and the conclusion is still no-change. The
  [wiki audit](../wiki-audit/README.md) found MouseBiteLabs documenting `D1`'s purpose
  outright: *"`D1` provides reverse polarity protection … **the batteries will short
  circuit** and a (large) negative voltage will be prevented from hitting the rest of the
  system."* It is a **sacrificial crowbar by design** — the shorted pack is the stated
  mechanism, not a failure. `D1`'s surge rating is **500 mA at 1 s** against 4–7 A
  available, `F1` is not in the reverse loop, and moving it there does not help because
  `F1` needs *seconds* at that current — but a diode driven past `IFSM` fails **short**,
  which clamps harder than the working diode did, so the specified function is delivered
  either way. **No part swap improves it**, and nothing was changed. What is worth saying
  plainly: `D1` protects the console, not the pack, and was never meant to — so a reversal
  is a *thermal, self-sustaining* event whose remedy is removing the cells.
- **`SW1`'s value is not an orderable part number** — `CSS-1310B` should be `CSS-1310TB`.
- ~~**`F1` and `PTC1` carry three different part numbers**~~ — fixed in
  [ECO-8](../clockxcontrol-integration/ECO-8_component_swaps.md).
- **`CP1`–`CP3` are polarized tantalums on a symmetric land with no polarity marking anywhere**, and
  `CP1` carries bidirectional AC with no DC bias, past the manufacturer's 1 V reverse limit.
- **The SRAM has no local decoupling** — ECO-5 moved `C8` 7.1 mm from pin 37 and left it
  unconnected.
- **`U14` is a 555-type oscillator**, not a power switch. This corrects the review's own brief.

---

## Read this before acting on any single finding

ECO-7 caught the review's **highest-confidence finding (0.95) recommending a change that would have
shorted `VDD2` to two data lines.** It had been verified for zone and plane membership, correctly,
and never checked against the pad column ECO-5 added.

The deep-verification panel is the same story in miniature: all eight top findings survived, but
**every one of the twenty-four lenses returned REVISED. Not one was confirmed as stated.**

And the completeness pass documents seven contradictions inside the surviving set: five findings
proposing the same PPTC swap with three different answers and two different parts, the same LDO
milliwatts booked three times, two mutually exclusive `VOUT3` trims, four different values for the
same `VAUD` current, and two incompatible efficiency models for the same rail.

**Treat every finding as a lead requiring a geometry and arithmetic check, not a conclusion.**

## What to put a meter on

In priority order, from the completeness critique:

1. **Does your screen work at 1.75× at all?** Before anything else matters.
2. **Current into `TP16` (`VOUT3`) and `TP13` (`VOUT5`)**, min and max brightness, 1× and 1.75×.
   This single measurement is the input to roughly fifteen findings, and one verdict *inverts* on it.
3. **Four-wire DC drop across `F1` and `PTC1` separately** at ~500 mA, hot. Resolves five findings.
4. **`VDD2` current at `TP18`**, 1× and 1.75×. The anchors used across the review span 25 to 82 mA.
5. **`VAUD` at `TP22` before and after the `U7` swap.** Decides the largest drop-in lever.
6. **Internal temperature at `PTC1`** in a closed shell after 30 minutes. At 20 °C the PPTC finding
   is a non-issue; at 60 °C it is over its rerated hold current.

---

## Method

Eight parallel domain investigations, each required to verify every electrical number against a
fetched source and show its arithmetic against MouseBiteLabs' measured figures. **102 findings**,
each then put through an adversarial pass instructed to refute by default and to re-fetch the
datasheets independently rather than trust the citation: **2 refuted, 55 of the surviving 100
revised.** The eight highest-impact claims then went through a three-lens panel (datasheet, systems,
magnitude), which revised all eight. A power-budget synthesis reconciled every domain's arithmetic
to one common anchor set, and a completeness pass swept all 235 reference designators for what the
domains missed.

**47 findings are negative results** — thermal is not a problem anywhere, `VDD2` layout and CPU
decoupling are fine, the ground split is done correctly, capacitor derating is a non-issue except
`C21`, and the load switches, EMC parts and pull-ups are not levers. They are recorded so nobody
re-derives them.
