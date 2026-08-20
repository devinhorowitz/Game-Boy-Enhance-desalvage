# ECO-10 — the precision and longevity pass

> ### ⚠ Superseded in part by ECO-13
>
> **[ECO-13](ECO-13_rebase_onto_agbm02.md) rebased this fork onto MouseBiteLabs' AGBM-02,
> which has no LTC3527.** `R21`, `R22`, `R23`, `R55`, `C40` and `C41` — every leg of both
> feedback dividers and both feedforward caps — **do not exist on the current board.**
> §10.2 below is therefore history: the finding was right about the wrong converter.
>
> **Everything else in this ECO is live and unchanged**, because none of it is a `Value`
> change — the audio filter's 0.1 % ±25 ppm thin film, the 25 V AEC-Q200 decoupling and the
> supervisor divider legs are part-number choices in `scripts/mpn_overrides.json`, against
> references AGBM-02 carries at identical positions.



Six `Value` changes and twenty-three MPN upgrades. **No copper.** The board edits are a
16-line diff against the ECO-9 build.

This is a deliberate *premium variant* of the AGBM-01: nothing here is a bug fix. The brief
was margin and longevity where the cost is pennies, accepting that some of it will never be
measurable in the hand. What follows is that, with one exception — §10.1 turned out to be a
real error term nobody had accounted for, and it is the reason this ECO exists at all.

Every part below was verified live on the Digi-Key API on 2026-08-19: exact MPN, exact
parameters, stock and price. `scripts/check_stock.py` re-fetches all of it.

---

## 10.1 The feedback dividers were the loudest thing on the board

**The LTC3527 specifies its own feedback input current as 1 nA typical and 50 nA maximum**
(35271fc, Electrical Characteristics, `VFB1,2 = 1.20V`). With the dividers as built, that
worst case moves the rails more than the resistors do:

| | Divider | Divider current | Worst-case shift at 50 nA |
|---|---|---|---|
| `VOUT3` | `R23` 1.69 M / `R55` 1.00 M | 1.20 µA | **±85 mV (±2.62 %)** |
| `VOUT5` | `R21` 1.78 M / `R22` 560 k | 2.14 µA | **±89 mV (±1.77 %)** |

For scale: **[ECO-8](ECO-8_component_swaps.md) trimmed `VOUT3` by 108 mV to save 6.1 mW, and
the worst-case uncertainty on that trim was 85 mV.** The trim was very nearly inside its own
error bar.

It also explains something that looked like a sourcing problem and was actually a signal:
**no 0.1 % resistor exists at 1.69 M or 1.78 M.** Nobody builds them, because nobody should
put a value that high in a feedback divider.

### What changed

| Ref | Was | Now | Part |
|---|---|---|---|
| `R21` | `1.78M` | **`178k`** | `RT0603BRD07178KL` — YAGEO RT0603, 0.1 %, ±25 ppm/°C |
| `R22` | `560k` | **`56k`** | `RT0603BRD0756KL` |
| `R23` | `1.69M` | **`169k`** | `RT0603BRD07169KL` |
| `R55` | `1M` | **`100k`** | `RT0603BRD07100KL` |
| `C40` | `15p` | **`150p`** | `GCM1885C2A151FA16D` — Murata C0G ±1 %, 100 V, AEC-Q200 |
| `C41` | `15p` | **`150p`** | same |

**The ratios are unchanged, so both rails are unchanged.** `VOUT5` = 1.20 × (1 + 178/56) =
5.014 V; `VOUT3` = 1.20 × (1 + 169/100) = 3.228 V. The generator asserts both to within
2 mV and fails the build otherwise — a future edit cannot quietly move a rail.

All four legs are **YAGEO RT0603**, so each divider tracks on one film system rather than
two that drift independently.

### What it costs, and what it buys

- **Costs 0.13 mW.** Divider current goes 1.20 → 12.0 µA and 2.14 → 21.4 µA. That is 2 % of
  what ECO-8's `VOUT3` trim saves, spent to make the trim mean something.
- **Worst-case bias error falls 10×** to ±8.4 mV and ±8.9 mV.
- **Ratio error falls from ±1.25 % to ±0.2 %**, and drift from ±100 ppm/°C to ±25 ppm/°C.

**Stated honestly: a typical part was never affected.** At the 1 nA typical figure the error
is ±1.7 mV. This is a worst-case margin change, not a defect repair, and MouseBiteLabs'
original choice — high impedance for low quiescent current on a battery device — was a
defensible trade. This ECO takes the other side of it.

### `C40`/`C41` are not decoupling

Verified from the netlist: both run **`VOUT` → `FB`**, i.e. across the *top* leg. They are
feedforward caps, and their zero sits at `1/(2π·R_top·C)` — about 6 kHz as built. Dropping
`R_top` 10× without touching them moves that zero to ~60 kHz and throws away the phase lead
it exists to provide. 15 pF → 150 pF holds it where the design put it.

The datasheet says only that *"a typical value of 15pF will generally suffice"*, so this
preserves MouseBiteLabs' compensation rather than following a mandate. C0G ±1 % because a
compensation element should not drift with temperature.

---

## 10.2 The audio filter, on one film system

`U7`'s two channels form a 4th-order Butterworth at 15.84 kHz. Eight resistors set `f0` and
`Q`; four capacitors set `Q`. Every one is now precision, and — the part that matters for a
ratio-critical network — **every resistor is Susumu RG1608**, so the ratios track instead of
drifting independently.

| Refs | Value | Was | Now |
|---|---|---|---|
| `R51` `R42` | 7.5 k | 1 %, ±100 ppm thick film | **`RG1608P-752-B-T5`** — 0.1 %, ±25 ppm thin film |
| `R52` `R47` | 20 k | ″ | **`RG1608P-203-B-T5`** |
| `R53` `R34` | 5.1 k | ″ | **`RG1608P-512-B-T5`** |
| `R54` `R48` | 18 k | ″ | **`RG1608P-183-B-T5`** |
| `C24` `C32` | 1000 p | **X7R** ±10 % | **`C0603C102J5GACTU`** — C0G ±5 % |
| `C28` `C35` | 3300 p | **X7R** ±10 % | **`C0603C332J5GACTU`** — C0G ±5 % |
| `C26` `C31` | 680 p | C0G ±5 % | **`GCM1885C2A681FA16D`** — C0G ±1 %, AEC-Q200 |
| `C27` `C33` | 330 p | C0G ±5 % | **`GCM1885C2A331FA16D`** — C0G ±1 %, AEC-Q200 |

**The X7R → C0G swap is the one that is audible in principle.** The power review found it
and [ECO-8 §8.4](ECO-8_component_swaps.md) deferred it because dielectric is not expressible
in a KiCad `Value` field. `C24`/`C28`/`C32`/`C35` are the **feedback** capacitors — the ones
that set `Q` — and their partners in the same sections were *already* C0G. X7R drifts ±15 %
over its range while C0G drifts ±30 ppm/°C, so a handheld warming in the hand detunes half
of each filter section, and no tolerance grade fixes that.

The review also corrected its own headline here, and the correction stands: the tolerance
argument is worth about **0.17 dB** of worst-case passband peaking, not the 0.6 dB first
claimed. **The temperature argument is the real one.**

---

## 10.3 The supervisor divider that could be finished

| Refs | Was | Now |
|---|---|---|
| `R58` | 5.1 k, 1 %, ±100 ppm | **`RG1608P-512-B-T5`** — 0.1 %, ±25 ppm |
| `R63` | 100 k, 1 %, ±100 ppm | **`RT0603BRD07100KL`** — 0.1 %, ±25 ppm |

Together these set `U17`'s low-battery trip point. A trip point should not move with
temperature.

**`R3`, `R4` and `R64` are deliberately left at 1 %.** They are the other supervisor legs,
and they still carry the unresolved schematic-versus-PCB value conflict — schematic 5.1 k /
33 k / 200 k against PCB 1 k / 10 k / 100 k, confirmed from the distributor side because the
schematic's own Digi-Key links buy the schematic's values. **Buying precision parts of a
value that may be wrong is waste.** Settle the conflict first; the upgrade is one line each
after that.

---

## 10.4 Decoupling: 16 V → 25 V, and automotive grade

| Refs | Was | Now |
|---|---|---|
| the twenty 1 µF placements | `C0603C105K4RACTU` — KEMET X7R, **16 V** | **`CGA3E1X7R1E105K080AC`** — TDK X7R, **25 V**, AEC-Q200 |

TDK's CGA series is the automotive-qualified grade of the C-series, same 0603 × 0.90 mm
body. A higher rated voltage in the same case means **less capacitance lost to DC bias** on
every rail these sit on, and the automotive grade is screened harder. 1,435,431 in stock at
$0.17.

**Not changed, and worth saying why:** the sixteen 0.1 µF placements are already
`C0603C104K5RACTU` — X7R at **50 V**. That is already the right part, and churning it would
buy nothing. A pass that changes everything it touches is not a pass, it is a habit.

The 10 µF and 22 µF bulk lines were already moved to Murata's **GRT** soft-termination
series (AEC-Q200) when they went out of stock — see
[`pcbway-assembly/`](../pcbway-assembly/README.md). (The 22 µF line no longer carries it: [ECO-21](ECO-21_22uf_line_to_25v.md) traded soft termination for a 25 V rating, because no 25 V `GRT` is in stock. The 10 µF line still does.) Soft termination is a genuine longevity
feature in a handheld that gets dropped: it is what stops a board-flex crack from reaching
the electrodes.

---

## 10.5 What this costs

**Sixty cents.** Measured, not estimated: the machine-placed BOM was **$54.12** before this
ECO and is **$54.72** after, at Digi-Key qty-1 pricing across all 172 parts. `bom_split.py`
and `check_stock.py` compute both figures from live data.

Precision thin film is **$0.10–0.11 a part — the same price as the 1 % thick film it
replaces.** Susumu RG1608 at 0.1 % / ±25 ppm costs $0.10; the YAGEO RC0603 at 1 % / ±100 ppm
costs $0.10. Nearly the whole tolerance upgrade on this board is free, and the sixty cents is
almost entirely the C0G capacitors and the automotive-grade 1 µF line.

*(An earlier draft of this section estimated "$4 per board" before the measurement existed.
It was wrong by about 7×, in the direction that would have made the decision look harder than
it is.)*

## 10.6 Not in this ECO

The two **correctness** items the power review found are real fixes rather than upgrades,
and each needs its own analysis rather than a line in a tolerance pass:

- **`D1`/`D2` are described as Schottky diodes and are not.** They are Rohm 1SS355VMTE-17
  standard switching diodes, 80 V / **100 mA**, in SOD-323F. `D1` sits across the pack as
  the reverse-battery clamp, where it must carry the pack's short-circuit current — 3–8 A
  into a 300–600 mΩ pack — until `F1` opens. A 100 mA part will not. The candidate is a 2 A
  40 V Schottky in the same SOD-323F land (`GSGP0240SD`, 2,808 in stock), **but choosing it
  properly needs the surge (`IFSM`, `I²t`) coordinated against `F1`'s 0.030 A²s pre-arc**,
  which is a datasheet analysis, not a parametric search.
- **`Q10` NDC7002N → FDC6301N** for the brownout-latch gate-drive margin, already argued in
  [ECO-9 §9.x](ECO-9_assembly_split.md) and the review. `FDC6301N` is 37,403 in stock at
  $0.64, drop-in on the same TSOT-23-6 land.

Both are tracked; neither is applied here.

## 10.7 Verification

- `python3 scripts/build_board.py --check` — the board rebuilds byte-for-byte, and the
  generator asserts both rescaled dividers still give 5.014 V and 3.228 V.
- `python3 scripts/check_consistency.py` check [3] — the table in §10.1 above, the
  generator's `ECO10` list and the board's `Value` fields must all agree.
- `python3 scripts/check_stock.py` — every MPN re-verified against Digi-Key and Mouser.

**ECO-10 changes no copper, so [ECO-7](ECO-7_u2_supply_and_dnp.md)'s blockers still block.**
`U2` pin 37 has no supply and `Net-(Q5B-G)` is still severed. Do not fabricate.
