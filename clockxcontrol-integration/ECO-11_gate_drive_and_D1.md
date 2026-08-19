# ECO-11 — the two correctness items, one applied and one refused

The power review flagged two defects that ECO-8 through ECO-10 deliberately left alone,
because each needed an analysis rather than a parametric search. Here is the analysis.

**One is real and is fixed here.** `Q9` and `Q10` are given gate drive *below* the
NDC7002N's worst-case threshold, so the brownout latch is not guaranteed to arm and the
low-battery LED is not guaranteed to light. Two `Value` changes, no copper.

**The other does not survive checking, and the correction matters more than the fix would
have.** The review said `D1` is "7–13× under-rated for the reverse-battery clamp duty the
schematic assigns it." **The schematic assigns it no duty.** And no diode that fits the land
would work anyway. §11.2.

---

## 11.1 `Q9` / `Q10` — the latch may never arm

### The threshold, read off onsemi's own table

**NDC7002N:** `VGS(th)` = **1.0 min / 1.9 typ / 2.5 V max** at `VDS = VGS`, `ID = 250 µA`.
There is **no `RDS(on)` specification below `VGS` = 4.5 V at all** — the part is not
characterised in the region this board uses it.

### The drive those parts actually get

| | What it must do | Its `VGS` |
|---|---|---|
| `Q10A` | pull `/~MR` down through the TPS3840's **100 kΩ internal MR pull-up**, ≈ **14 µA** | `SW − Vce(sat)` ≈ **2.0 V** at the trip |
| `Q10B` | hold `Q1-C` at saturation, ≈ 41 µA | `0.990 × SW` = **2.05 V** at the trip, 3.17 V fresh |
| `Q9B` | pass `DL2`'s ≈ 165 µA through `R10` | `/D1A` ≈ **3.0 V** |

The 100 kΩ is not an assumption — the TPS3840 datasheet lists *"Manual reset internal
pull-up resistance … 100 kΩ"*. And `/VFILT` at the trip is `VIT−` = 2.0 V, confirmed twice:
the datasheet's own variant table gives `TPS3840DL20 … 2.0`, and Digi-Key's parametric data
gives `Voltage - Threshold 2V`.

### Why that fails

A worst-case NDC7002N sits **at or below its own threshold** in all three cases, and the
threshold is *defined* as the `VGS` that produces 250 µA. Sub-threshold conduction falls a
decade every 60–100 mV, so half a volt short is five to eight decades short — nanoamps
against a 14 µA requirement.

**The latch does not arm. The low-battery LED does not light.** Neither failure is visible:
the console works normally right up until the moment the protection was supposed to act.

**And it is worse cold.** `VGS(th)` has a negative temperature coefficient, so a cold
console pushes a *typical* part toward the same place a worst-case part sits at room
temperature.

### The fix

| Ref | Was | Now |
|---|---|---|
| `Q9` | `NDC7002N` | **`FDC6301N`** |
| `Q10` | `NDC7002N` | **`FDC6301N`** |

`VGS(th)` = **0.65 / 0.85 / 1.5 V max**, same SUPERSOT-6 / TSOT-23-6 land, same pin
assignment. Every node above gains at least **0.5 V of worst-case overdrive**.

`Q9B` is the one ECO-8 narrowed itself: swapping `DL1` to the InGaN part lowered `/D1A` in
the low-battery state from ~3.6 V to ~3.0 V, cutting the margin over a 2.5 V threshold from
1.1 V to 0.5 V. [ECO-8 §8.3](ECO-8_component_swaps.md) said so at the time and named this
part as the thing that would restore it. **It does.**

### The one objection, and why it does not hold

The FDC6301N's gate rating is **asymmetric — −0.5 to +8 V** — against the NDC7002N's 20 V.
`Q10A` is the only node on the board that ever sees a negative `VGS`: at power-up `/EN`
rises through `R11` while `Q10A`'s gate is still held down by `R17`, so `VGS` swings to
about `−SW`.

The datasheet's own feature list answers it: **"Gate−Source Zener for ESD Ruggedness. >6 kV
Human Body Model."** The part carries an integrated clamp. It forward-conducts at about
−0.7 V, and the current is set by `R16` — which **ECO-8 raised from 10 k to 100 k**, making
that clamp current `(3.2 − 0.7)/100k` = **25 µA**. This is exactly what the Zener is for,
and ECO-8 made it ten times gentler without knowing it would matter.

### Headroom

FDC6301N is 25 V / 0.22 A continuous. Maximum `VDS` anywhere in `Q9`/`Q10` is 5.0 V, and
the drain currents are 14 µA, 41 µA, 124 µA and 165 µA. **Three orders of margin.**
`RDS(on)` of 5 Ω max at `VGS` = 2.7 V costs `Q9A` 0.6 mV on the LED.

### `Q2`, `Q5` and `Q7` keep the NDC7002N

Deliberately, and the reasons are different for each:

- **`Q5`** — its gates are driven to `VOUT5` = 5.0 V, so there is no margin problem to fix.
  (`Q5B`'s gate is also the severed net from [ECO-7](ECO-7_u2_supply_and_dnp.md), so nothing
  downstream of it works regardless.)
- **`Q2`/`Q7`** — they switch display signals from `U16` at 3.228 V, where the worst-case
  overdrive is already 0.73 V. Changing `RDS(on)` from 1.6 Ω to 3.1 Ω and altering `Ciss`
  in a display path whose timing I have not analysed is a risk bought for no stated benefit.

The cost is one extra BOM line. That is the right trade.

---

## 11.2 `D1` — the finding does not survive, and the truth is worse

### What the review said

> `D1`/`D2` are not Schottky diodes. Verified: Rohm 1SS355VMTE-17, *standard* switching
> diodes, 80 V, 100 mA. `D1` is 7–13× under-rated for the reverse-battery clamp duty the
> schematic assigns it, and sits on the wrong side of `F1`.

### What the schematic actually says

**Nothing.** There is no text note anywhere in `AGBM-01_AA_1-2.kicad_sch` describing `D1`'s
purpose. The word "Schottky" appears only in two places, and neither is a design statement:
the KiCad symbol chosen is `Device:D_Schottky`, and that symbol's stock `Description` field
reads "Schottky diode". The AGBM-01 README's own BOM table calls `D1` simply **"Diode."**

MouseBiteLabs *does* annotate diodes when they have a specific job — the AGBM-11 schematic
carries *"D2 protects against backfeeding into VDD5 if solder bridge on LEDs"*. `D1` has no
such note. **The duty the review says the schematic assigns was never assigned.**

### The numbers, either way

`D1` sits between `Net-(BT1-+)` and `GND`, cathode to the battery — reverse-biased in normal
use. `F1` is between `Net-(BT1-+)` and `VBATT`. So on a reversal the loop is
`pack → D1 → pack`, and **`F1` is not in it.**

- **`1SS355VMTE-17`: `IFSM` = 500 mA at t = 1 s.** That is the entire surge rating.
- Available reverse current: 3.2 V into a 300–600 mΩ pack plus contacts and trace ≈ **4–7 A**.
- Nothing opens. Ever.

**Moving `D1` to the `VBATT` side so `F1` joins the loop does not rescue it either.** The
Accu-Guard II `F0805B2R00` has a **fusing current of 4.00 A within 5 seconds** — at 4–7 A
this fuse takes *seconds*, because the available fault is only 2–3.5× its rating, exactly
the region where a thin-film fuse is slow. The event is then 36–180 A²s. The best 2 A
Schottky that fits the `SOD-323F` land carries perhaps 4 A²s. **Still 10–40× short.**

### Therefore

**No part swap makes this work, and no reasonable topology change does either.** A 2 A
Schottky would cost money, survive nothing, and leave behind the impression of protection
that a future reader would trust.

Two readings of `D1` are consistent with the board, and the numbers choose between them:

1. **As a reverse-polarity crowbar** it is absurdly under-rated *and placed where the fuse
   cannot help it* — which is not a mistake a designer makes twice.
2. **As a negative-transient / ESD clamp across the battery input** — a reverse-biased
   500 mA diode upstream of the fuse — it is **correctly chosen and correctly placed.**

Reading 2 is the one consistent with the part, the position and the absence of any note.
**`D1` is not changed.**

### What is true, and should be said plainly

**The AGBM-01 has no effective reverse-battery protection.** Not "weak" — none. If both
cells go in backwards, `D1` fails within milliseconds, and a failed diode is usually a
short, at which point the pack is hard-shorted through the failed die until someone removes
it. Alkaline cells into a dead short get hot and can vent.

The exposure is genuinely low: in a 2×AA series holder, **one** cell reversed gives
1.6 − 1.6 ≈ 0 V and harms nothing; **both** reversed requires defeating the compartment
keying twice. But low probability is not protection, and the fix is not a diode:

> **The real fix is series protection — a P-channel MOSFET ideal-diode in the `VBATT`
> path** — which is a board revision, and one with a real power cost, since its `RDS(on)`
> sits in the main current path on a board whose review fights for single milliwatts.

Recorded, not applied. It is a design decision, not a part swap.

### `D2` is fine, and here is why it looked suspect

`D2` is in **parallel with `R9` (100 k)**, feeding `C1` (22 µF) and `U3`'s supply. It is the
fast-charge bypass: `/VFILT` follows `VBATT` **up** quickly through the diode and comes
**down** slowly through `R9` (τ = 2.2 s). That makes the supervisor's supply *sag-immune* —
it sees the pack's peak, not its momentary droop under load, so a current transient does not
false-trip the brownout.

Its `Vf` does **not** set the brownout threshold, which was the reason to worry: in steady
state `R9` carries the DC and the diode carries essentially nothing, so
`/VFILT = VBATT − 700 nA × 100 k = VBATT − 0.07 V`. A Schottky would change nothing that
matters. **`D2` is not changed.**

---

## 11.3 Found on the way: the schematic's brownout note is wrong by a volt

All three AGBM schematics carry the same annotation:

> *"Bootloop protection: Shuts off power if battery drops below 3V"*

That is **correct for AGBM-11 and wrong for both AA variants**, and the part numbers prove
it:

| Variant | Supervisor fitted | Actual trip |
|---|---|---|
| AGBM-11 (1S LiPo) | `TPS3840DL30` / `DL31` | **3.0 / 3.1 V** — the note is right |
| AGBM-02 (2×AA) | `TPS3840DL20` | **2.0 V** |
| **AGBM-01 (2×AA)** | **`TPS3840DL20`** | **2.0 V** → `VBATT` ≈ **2.07 V** |

The note was written for the lithium board and copied to the alkaline ones. **The fitted
part is the right one** — a 3 V cutoff on 2×AA alkaline would strand most of the pack's
capacity — so this is a stale annotation, not a design error. It is upstream's and worth
reporting there.

---

## 11.4 Verification

- `python3 scripts/build_board.py --check` — the board rebuilds byte-for-byte.
- `python3 scripts/check_consistency.py` check [3] — the table in §11.1, the generator's
  `ECO11` list and the board's `Value` fields must agree.
- `python3 scripts/check_stock.py` — `FDC6301N` re-verified against Digi-Key and Mouser.

**ECO-11 changes no copper**, so [ECO-7](ECO-7_u2_supply_and_dnp.md)'s blockers still block.
Do not fabricate.
