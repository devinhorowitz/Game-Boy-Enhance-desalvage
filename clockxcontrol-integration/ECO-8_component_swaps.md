# ECO-8 — the drop-in component swaps from the power review

Thirteen `Value`/`Description` edits on `AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb`. **No copper, no
land pattern, no placement.** Every replacement lands on the footprint that is already on the board.

The diff against the ECO-7 build is exactly 26 lines — thirteen properties, before and after — so
the geometry is byte-identical and nothing needed re-verifying with DRC.

These come from the ranked Tier-1 ledger in [`power-review/`](../power-review/README.md), but each
one was re-checked here against the manufacturer's own datasheet rather than accepted from the
review. That mattered for `PTC1`, where the review's derating figures do not match the current
datasheet — recorded in §8.3, along with the one thing this change set makes worse.

---

## 8.1 What changed

| Ref | Was | Now | Class | Why |
|---|---|---|---|---|
| `U7` | `TLV9364` | **`TLV9064IPWR`** | correctness | 4.5 V-minimum op-amp on a 2.5 V rail |
| `R23` | `1.78M` | **`1.69M`** | efficiency | `VOUT3` 3.336 V → 3.228 V — *later superseded to `169k` by [ECO-10](ECO-10_precision_pass.md), same rail* |
| `DL1` | `150060VS75000` | **`150060GS75000`** | efficiency + quality | InGaN green, 11–18× the luminous intensity |
| `R25` | `3.3k` | **`22k`** | efficiency | pairs with `DL1` |
| `PTC1` | `0467001.NR` | **`0805L110SLYR`** | stability + BOM fix | derated hold current was below the load |
| `F1` | `0467001.NR` | **`F0805B2R00FSTR`** | BOM fix | stale value, no electrical change |
| `R15` | `10k` | **`100k`** | efficiency | brownout-latch bias |
| `R16` | `10k` | **`100k`** | efficiency | brownout-latch bias |
| `R11` | `1k` | **`10k`** | efficiency | latched-off drain |
| `R24` | `100k` | **`1M`** | efficiency | keeps `/EN` at 0.99 × SW alongside `R11` |
| `R65` | `100k` | **`470k`** | efficiency | MIC1553 `CS` pull-up |

`PTC1` and `F1` also had their `Description` field replaced. Both carried the string `0805L050WR`,
which is a third part again — a legacy string baked into the library symbol, present on both parts
in AGBM-01, AGBM-02 and AGBM-11 alike.

### The ledger, at three labelled operating points

Battery-side, on MouseBiteLabs' own measured figures (170 mW idle, 792 mW representative use,
951 mW with the module at 1.75×; 2.4 V pack).

| Change | Idle | 1× use | 1.75× |
|---|---|---|---|
| `U7` | 12.0 mW | 12.0 | 12.0 |
| `R23` | 4.1 | 6.1 | 8.2 |
| `DL1` + `R25` | 4.6 | 4.6 | 4.6 |
| `PTC1` | 0.1 | 2.2 | 3.2 |
| `R15` + `R16` | 0.74 | 0.74 | 0.73 |
| `R65` | 0.25 | 0.25 | 0.25 |
| `R11` + `R24` | 0.05 | 0.05 | 0.05 |
| **Total** | **21.8 mW** | **25.9 mW** | **29.0 mW** |
| **As a fraction** | **12.8 %** | **3.3 %** | **3.0 %** |

Plus one number that is not a running saving: the post-brownout latched-off drain falls from
**6.90 mW to 0.98 mW**, a 7.1× reduction in what a flat pack loses while the console sits switched
"on" but latched off, waiting for someone to notice and cycle `SW1`.

At 1.75× that is 951 → 922 mW, which on a 6.26 Wh pack is **6 h 47 m instead of 6 h 35 m**. The
overclock costs 79 minutes; this hands back 12 of them. That is the honest size of it, and it is
consistent with the review's own conclusion that the energy cannot be won back.

*(An earlier draft of the review headlined "about 32 mW at 1.75×" against a table that summed to
29.2. The 29.0 above is the same arithmetic with the supervisor dividers and `R12` left out — see
§8.4 — and the review's table now carries these figures.)*

---

## 8.2 The one that is not about power

**`U7` is the single best change on this board and it is a correctness fix.**

`U7` is the quad op-amp that forms both channels of the 4th-order Butterworth reconstruction filter
and then buffers them into the volume pot. From the PCB net map, `U7` pin 4 (`V+`) is on `VAUD` and
pin 11 (`V−`) is on `AGND`, so it runs on **2.5 V**.

From TI's TLV9361-Q1/9362-Q1/9364-Q1 datasheet (SBOSAD6B), which I extracted rather than quoted:

- Features, verbatim: *"Wide supply: ±2.25V to ±20V, 4.5V to 40V"*
- §7.4 Device Functional Modes, verbatim: *"The TLV936x-Q1 has a single functional mode and is
  operational when the power-supply voltage is greater than 4.5V (±2.25V)."*
- Features: *"Low quiescent current: 2.6mA per amplifier"*
- Input common-mode range: `(V−)` to `(V+) − 2 V`; **rail-to-rail output only, not rail-to-rail
  input**

So the part is being run **2.0 V below its minimum supply**, and its common-mode ceiling on this
board is `2.5 − 2 = 0.5 V` while all four non-inverting inputs sit at the `VAUD/2 = 1.25 V` bias set
by `R45`/`R46` and `R49`/`R50`. Both the supply and the common-mode specification are violated. The
part is not guaranteed to do anything at all here.

The **TLV9064** (SBOS839N) is specified from **1.8 V to 5.5 V**, has true rail-to-rail inputs
(`VCM = (V−) − 0.1 V` to `(V+) + 0.1 V`), and draws **538 µA per amplifier typ / 750 µA max**.

Pinouts, both taken from TI's own Pin Functions tables for the 14-pin SOIC/TSSOP package:

| Pin | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TLV9364-Q1 | OUT1 | IN1− | IN1+ | V+ | IN2+ | IN2− | OUT2 | OUT3 | IN3− | IN3+ | V− | IN4+ | IN4− | OUT4 |
| TLV9064 | OUT1 | IN1− | IN1+ | V+ | IN2+ | IN2− | OUT2 | OUT3 | IN3− | IN3+ | V− | IN4+ | IN4− | OUT4 |

Pin-for-pin identical, and the TLV9064 `PW` package is TSSOP-14, 5.00 × 4.40 mm — which is the
footprint already on the board (`Bucketmouse:TSSOP-14_4.4x5mm_P0.65mm`). `TLV9064IPWR` appears in the
datasheet's own orderable table.

Filter performance is unaffected: the required slew for 1.25 Vpk at 16 kHz is 0.126 V/µs against
6.5 V/µs available, and the Sallen-Key feedback caps are isolated from each output by
`R53`/`R34` = 5.1 k, which acts as a built-in `R_ISO`.

**This is an upstream bug, not a fork bug** — AGBM-02 carries the same part. It is worth reporting
to MouseBiteLabs whether or not you care about the 12 mW.

---

## 8.3 One correction to the review, and one thing this makes worse

### `PTC1` is a Lo Rho part, and the review's derating numbers were optimistic

The review's first PTC finding cited the **standard** `0805L` datasheet. The fitted part is
`0805L075SLYR` — the `SL` suffix is Littelfuse's **Low Rho** series, a different device with
different resistance and different derating. The review's verification pass caught the series error
but quoted derating figures that do not appear in the current datasheet either.

From the Littelfuse **Low Rho Series** PolySwitch datasheet, rev GD 03/06/25, which I downloaded and
extracted:

| Part | I_hold | I_trip | V_max | I_max | R_min | R_1max |
|---|---|---|---|---|---|---|
| `0805L075SL` (fitted) | 0.75 A | 1.50 A | 6 V | 50 A | 0.040 Ω | 0.150 Ω |
| **`0805L110SL`** (now) | 1.10 A | 1.80 A | 6 V | 50 A | **0.030 Ω** | **0.120 Ω** |
| `0805L150SL` | 1.50 A | 3.00 A | 6 V | 50 A | 0.015 Ω | 0.065 Ω |

*(Digi-Key's parametric data lists the `0805L110SLYR` at 30 / **130** mΩ and the `0805L075SLYR` at
40 / 160 mΩ — a 10 mΩ offset from this datasheet revision on both parts, so the **difference** is
0.030 Ω either way and none of the arithmetic below moves.)*

Hold current versus ambient, same datasheet (note there is **no 50 °C column**):

| Part | −40 °C | −20 °C | 0 °C | 20 °C | 40 °C | 60 °C | 70 °C | 85 °C |
|---|---|---|---|---|---|---|---|---|
| `0805L075SL` | 1.15 | 1.00 | 0.85 | **0.75** | **0.55** | **0.40** | 0.30 | 0.20 |
| `0805L110SL` | 1.70 | 1.50 | 1.30 | **1.10** | **0.85** | **0.60** | 0.50 | 0.30 |
| `0805L150SL` | 2.25 | 2.00 | 1.75 | **1.50** | **1.15** | **0.85** | 0.65 | 0.45 |

The review quoted 0.62 A at 40 °C and 0.47 A at 60 °C for the fitted part. The datasheet says
**0.55 A and 0.40 A**. The real derating is *worse* than the review claimed, which makes the case for
the swap stronger, not weaker.

`PTC1` carries 100 % of the converter input current — `VCC` has exactly eight pads (`C37`, `L1.1`,
`L2.1`, `PTC1.2`, `TP32`, `U5` VIN/VIN1/VIN2) and `SW1` gates only `/EN`, never the load. Correcting
the review's worst case for the fact that flash carts do not work overclocked, the realistic
worst-case battery current is about **585 mA** (≈1063 mW at a 1.9 V end-of-life pack, plus the
module's ~25 mA referred to the battery):

- fitted `0805L075SL`: 585 mA is **6 % over** its 40 °C hold current and **46 % over** at 60 °C
- `0805L110SL`: 585 mA is **69 % of** its 40 °C hold current, and just under it at 60 °C

Protection given up: `I_trip` rises from 1.50 A to 1.80 A. That is why `0805L110SLYR` and not
`0805L150SLYR`, which the review's highest-confidence PTC finding proposed and which saves roughly
three times as much. **`F1` is a one-shot fuse.** With the 1.5 A part, a sustained 2–3 A fault trips
the resettable device and the console comes back when the fault clears; with the 3 A part, that same
fault falls through to `F1` instead and permanently opens a soldered-down fuse on a board with no
fuse holder. The 1.10 A part keeps a resettable band of 1.8–4 A. **If you run 1.75× at maximum
brightness and see nuisance trips, `0805L150SLYR` is the drop-in — decide it knowing the above.**

### `R25` = 22 k narrows one margin, on the low-battery LED

`/D1A` carries `DL1` pad 1 (K), `C68` (10 µF to GND), `Q9` pin 6 (`Q9A` drain) and `Q9` pin 3
(**`Q9B`'s gate**). `R25` feeds `DL1`'s anode from `VOUT5`, and `Q9B` switches the red low-battery
LED `DL2`.

In the battery-good state `Q9A` holds `/D1A` near 0 and the green LED is lit. When the supervisor
trips, `Q9A` releases and `/D1A` charges through `R25` and `DL1` — but once `C68` is charged the only
DC load is leakage, so the LED's forward drop at leakage current sets the steady-state level. The
review's verification puts that at about **3.6 V with the AlInGaP part and about 3.0 V with the
InGaN part**, against the NDC7002N's worst-case `VGS(th)` of 2.5 V. Margin falls from ~1.1 V to
~0.5 V.

I am doing the swap anyway, and here is the arithmetic that says it is fine: `DL2` is fed from `R10`
= 20 k, so `Q9B` only has to pass about **165 µA**, and the NDC7002N's threshold is *defined* at
250 µA. A worst-case part with 0.5 V of overdrive passes far more than 165 µA. The red LED lights.

Two smaller consequences, both cosmetic: the green-to-red changeover is delayed by roughly 0.4–0.5 s
while `C68` charges through 22 k, and 525 nm InGaN is a visibly colder green than the 570 nm
yellow-green of a stock AGB.

**This is the only change in ECO-8 that makes anything worse.** If it bothers you, the alternative is
to keep `150060VS75000` and take `R25` = 10 k alone: 3.9 mW instead of 4.6 mW, margin untouched, but
the power LED gets three times dimmer than stock rather than brighter.

Both Würth datasheets were downloaded and checked directly for this, not taken from the review:

| | `150060VS75000` (was) | `150060GS75000` (now) |
|---|---|---|
| Chip technology | AlInGaP | InGaN |
| λ dominant @ 20 mA | 570 nm | 525 nm |
| Luminous intensity @ 20 mA | 12–40 mcd | **220–430 mcd** |
| Body | 1.6 × 0.8 mm, 0603 | 1.6 × 0.8 mm, 0603 |
| Recommended land pattern | 0.8 / 0.8 / 2.4 mm | **0.8 / 0.8 / 2.4 mm** |
| Polarity | pin 1 = −, pin 2 = + | pin 1 = −, pin 2 = + |
| Status | Valid | Valid |

Identical land, identical polarity, identical family (WL-SMCW), same revision 002.009. At the
0.124 mA that 22 k gives it, the InGaN part is **brighter than the incumbent is today at 0.93 mA**,
on 1/7.5 of the power.

---

## 8.4 Considered and declined

These were all in the review and are all deliberately **not** in the board.

**`R3`/`R4`/`R58`/`R63` supervisor dividers → 10× (0.185 mW).** `R3` and `R4` have *different values
in the schematic and in the PCB* — schematic 5.1 k / 33 k, PCB 1 k / 10 k, along with `R64`
(200 k vs 100 k). Scaling a divider whose baseline is in dispute sets a battery-warning threshold
nobody can predict from the files. **Settle the schematic first.** There is also an unquantified
second-order effect: `C12` is a 10 µF MLCC across `R63` = 100 k, and MLCC insulation resistance at
that impedance is enough to shift a brownout trip point. 0.185 mW does not buy that analysis.

**`R12` 100 k → 470 k (0.044 mW).** The review blesses 470 k as the safe upper bound. 44 µW is
0.026 % of idle — below the resolution of the entire power model — and `Q1-C` is the one node where
a leakage-driven failure would silently disarm the brownout latch on a hot board. Not worth it.

**`F1` 2 A → 2.5 A (1.5 mW at 292 mA).** `F1` is the board's only permanent disconnect and the
review's own advice is to take the milliwatts out of `PTC1` instead, which ECO-8 does. Also worth
recording while the fuse is in view: **`F1` does not protect against a reversed battery.** `D1` sits
*across* the pack upstream of `F1`, so on reverse insertion the loop is battery → `D1` → battery and
never passes through the fuse.

**`L2` 4.7 µH → 3.3 µH (1.1 / 2.8 mW).** Mechanically this *is* a value edit, so it could have gone
in — it is declined on confidence. It is the lowest-confidence item in the whole drop-in set (0.65),
it changes the converter's ripple and Burst threshold rather than just a bias current, and it does so
on the rail that feeds a salvaged CPU. It also compounds the `L1`/`L2` footprint mismatch already
open in the PCBWay notes. Measure the rail before changing the inductor.

**`Q10` NDC7002N → FDC6301N.** This one is *not* declined on merit — it is the best remaining swap
and it is a genuine drop-in on the existing SuperSOT-6 land. It is out of scope here because it is a
functional change to the brownout latch, not a value tweak, and it deserves its own ECO. The case:
`/~MR` has no external pull-up, so the TPS3840's internal 100 kΩ means `Q10A` must sink about 14 µA
at `VGS ≈ 1.8 V` to latch — and the NDC7002N's `VGS(th)` is specified 1.0 V min / 1.9 V typ /
**2.5 V max**, with no on-resistance specified below `VGS` = 4.5 V. A worst-case part never latches
the brownout at all, and a typical part sits essentially at threshold. The FDC6301N is
0.65 / 0.85 / **1.5 V** in the identical CASE 419BL package with the same pin assignment. It would
also restore the `Q9B` margin that §8.3 narrows. **Recommended as ECO-9.**

**`C24`/`C28`/`C32`/`C35` X7R → C0G.** Real and worth doing, but dielectric is not expressible in a
KiCad `Value` field — these all read `1000p`/`3300p`. It is recorded in
[`pcbway-assembly/`](../pcbway-assembly/README.md) as an MPN-level substitution instead. The argument
is not the tolerance (the review's 0.6 dB is about 3× too big once you compare like with like — the
real figure is 0.17 dB); it is that X7R drifts ±15 % over temperature while its C0G partners in the
same Butterworth section drift ±30 ppm/°C, so a handheld warming in the hand detunes half of each
filter section and no tolerance grade fixes that.

---

## 8.5 The schematic is still the source of truth

**These edits will be silently reverted by the next "Update PCB from Schematic" with value updating
enabled.** This repository ships a `.kicad_pcb`, not a schematic, so the PCB `Value` fields are what
a PCB-derived BOM and a PCBWay assembly package will read — which is why they are set here. Before
anyone re-syncs, set the same values in `AGBM-01_AA_1-2.kicad_sch`:

```
U7   TLV9364      -> TLV9064IPWR
R23  1.78M        -> 1.69M
DL1  150060VS75000-> 150060GS75000
R25  3.3k         -> 22k
PTC1 0805L075SLYR -> 0805L110SLYR      (schematic value was right; PCB Value was 0467001.NR)
F1   F0805B2R00FSTR   no change         (schematic value was right; PCB Value was 0467001.NR)
R15  10k          -> 100k
R16  10k          -> 100k
R11  1k           -> 10k
R24  100k         -> 1M
R65  100k         -> 470k
```

And settle `R3` / `R4` / `R64`, which disagree between the two files today.

---

## 8.6 How this was checked

- The board is generated from the ECO-5 fork by a patch script rather than hand-edited (the script
  is not in the repository — the generated `.kicad_pcb` is the deliverable). Its ECO-8 block asserts
  that each `(property "<field>" "<old>"` string occurs **exactly once** inside the target footprint
  before replacing it, so a silent mis-hit fails the build rather than producing a wrong board.
- `diff` against the ECO-7 build: **26 lines, 13 properties**, nothing else. Geometry byte-identical,
  so the ECO-6 clearance analysis carries over unchanged — and so does its caveat that the board has
  still never been through KiCad's own DRC.
- The file re-parses as balanced s-expressions with 9 top-level children.
- Read back from the generated board: all 13 changed, all `DNP` flags from ECO-7 intact, `R21`
  (the `VOUT5` divider) and `R55` (the `VOUT3` divider's lower leg) untouched.

## 8.7 The blockers are still blockers

ECO-8 changes no copper, so nothing in [ECO-7](ECO-7_u2_supply_and_dnp.md) is resolved by it.
`U2` pin 37 still has no path to `VDD2` and `Net-(Q5B-G)` is still severed at the via ECO-5
deleted at (100.800, −62.150). **The board is not
fabricable until both are routed in KiCad.** `R65`'s new value sits downstream of the second of
those — with `Q5B`'s gate cut off from the supervisor, the MIC1553's `CS` is indeterminate whatever
`R65` is; 470 k does the right thing once the via is back.
