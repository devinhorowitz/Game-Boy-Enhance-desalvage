# ECO-12 — the wiki audit: put back what this fork drifted away from

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-01), CC BY-SA 4.0.

Reading MouseBiteLabs' project wiki end to end settled two questions this fork had left
open, and one of them had turned into a live regression in our own generated BOM. The
full audit — every ECO in this fork checked against what Nick wrote, designed, measured
and struggled with — is in [`wiki-audit/README.md`](../wiki-audit/README.md). This is the
part of it that changed the board.

| Ref | Was | Now | Why | Note |
|---|---|---|---|---|
| `R3` | `1k` | **`5.1k`** | correctness | `U10` low-battery divider, top leg |
| `R4` | `10k` | **`33k`** | correctness | `U10` low-battery divider, bottom leg |
| `R64` | `100k` | **`200k`** | correctness | 555 blink rate |
| `R23` | `169k` | **`178k`** | margin | reverts ECO-8's `VOUT3` trim |

Part numbers moved with them:

| Ref | Was | Now | |
|---|---|---|---|
| `R3` | `RC0603FR-071KL` — 1 % thick film | **`RG1608P-512-B-T5`** | Susumu, 0.1 %, ±25 ppm, anti-sulfur, AEC-Q200 |
| `R4` | `RC0603FR-0710KL` — 1 % thick film | **`RG1608P-333-B-T5`** | same film system as `R3` |
| `R63` | `RT0603BRD07100KL` — YAGEO | **`RG1608P-104-B-T5`** | same film system as `R58` |
| `R64` | `RC0603FR-07100KL` — 1 % thick film | **`RC0603FR-07200KL`** | still 1 %, deliberately |
| `R23` | `RT0603BRD07169KL` — YAGEO 0.1 % | **`RT0603BRD07178KL`** | now shares `R21`'s line |

*(Every `Was` cell in the part-number table carries a qualifier so that check [3],
which parses `| ref | was | **now** |` rows, reads only the swap table above it.)*

Net BOM effect, measured from `pcbway-assembly/resolved-mpns.json` before and after:
**63 → 65 assembly lines** and **$58.34 → $58.36** at qty 1. `R23` merges into `R21`'s line,
but `R4`, `R63` and `R64` each land on a part nothing else on the board uses. **Two cents and
two lines** to put four thresholds where their author documented them.

---

## 12.1 `R3`, `R4`, `R64` — the conflict was a stale PCB annotation

ECO-8 §8.4 found that the AGBM-01 schematic and the AGBM-01 PCB disagree on three
resistors, deferred the question, and ECO-10 §10.3 deferred it again in as many words:

> **Buying precision parts of a value that may be wrong is waste.** Settle the conflict
> first; the upgrade is one line each after that.

`scripts/mpn_overrides.json` said how to settle it — *"measure the trip point on a built
board, **or ask MouseBiteLabs**."* The wiki is MouseBiteLabs answering, and it answers
four separate ways.

**1. The AGBM-02 PCB.** The decisive one. AGBM-02 is the same AA design one revision
later with an identical supervisor circuit, and its `.kicad_pcb` — extracted from
the AGBM-02 design-files archive committed under `AGBM-02 (AA Batteries)/` —
carries `R3 = 5.1k`, `R4 = 33k`, `R64 = 200k`. Nick corrected the annotation on the newer
board. AGBM-01's is simply stale.

```
AGBM-01 stock PCB: R3=1k    R4=10k   R64=100k   R58=5.1k  R63=100k
AGBM-02      PCB : R3=5.1k  R4=33k   R64=200k   R58=5.1k  R63=100k
```

**2. Both AA README BOMs.** `AGBM-01 (AA Batteries)/README.md` and
`AGBM-02 (AA Batteries)/README.md` each list `R3 = 5.1k`, `R4 = 33k`, `R64 = 200k`, with
Digi-Key links that buy those values. Anyone who has ever built this board bought the
schematic's values, because the README is what you order from.

**3. The measured thresholds.** *Power Draw and Battery Curves* states them outright:

> The low battery LED turns on when the voltage passes 2.3V. This represents roughly 5 to
> 7% battery left. The LED begins blinking when the voltage passes 2.1V, which represents
> less than 1% battery life remaining. The Game Boy shuts off when the battery voltage
> hits 2.0V.

The netlist says how that number is made — `SW → R3 → (U10.VDD, C10, R4) → GND` — so the
TPS3840DL20's 2.00 V threshold appears at `SW` as `2.00 × (R3 + R4) / R4`:

| Values | Trip point | Against the wiki's 2.3 V |
|---|---|---|
| **5.1 k / 33 k** | **2.309 V** | matches |
| 1 k / 10 k | 2.200 V | 109 mV low |

The cross-check that removes all doubt: `U17`'s divider is **not** in conflict — `R58` =
5.1 k and `R63` = 100 k on every file — and it gives `2.00 × 105.1/100 = 2.102 V`,
matching the wiki's 2.1 V. **Both** AA supervisors use a 5.1 k top leg. The PCB's `1k`
is the one value in the set that fits nothing.

**4. It is an acceptance test.** The AGBM-01 build guide, Test 4:

> If you have the ability to change the input voltage, try sweeping it from 2V to 3V to
> see if the color changes. It should go from green to red at **2.3V** (when voltage is
> dropping) and should start blinking once it gets below **2.1V**.

A board built to the PCB's annotation fails a test its own author wrote.

### This fork had the regression live

ECO-9 derives the PCBWay BOM and CPL from the board's `Value` fields — that is the point
of it, and it is the right rule. It also means that until this ECO, **we were ordering
the stale values.** `pcbway-assembly/resolved-mpns.json` carried them as a standing
`value_conflicts` ledger of three, and a board built from it would have:

* **warned late.** 2.200 V instead of 2.309 V. Nick puts 2.3 V at 5–7 % of pack and 2.1 V
  at under 1 %, so the entire low-battery warning — 20 minutes to an hour depending on the
  screen kit — roughly halves.
* **blinked at double rate.** `R64` with `C44` = 1 µF sets the 555's period. The astable is
  the OUT-to-RC form (`R64` between `U14` OUT and the tied TRIG/THRES node, `C44` to GND),
  so `T = 2·ln2·R·C`: 200 k → **3.6 Hz**, 100 k → **7.2 Hz**.
* **flickered.** The wiki is explicit that `C10` and `C12` exist to stop the LED
  chattering between states as a loaded pack sags:

  > it is important to make sure the voltage doesn't shift *too* quickly when the
  > batteries are low, otherwise you might get the power LED to flip between solid red and
  > flashing red whenever, say, the audio is temporarily louder than usual.

  `R3∥R4 × C10` falls from **0.44 ms** to **0.09 ms** on the stale values — the filter is
  4.9× lighter than designed, which attacks precisely the symptom it exists to prevent.

### The precision upgrade ECO-10 deferred, now that the value is known

ECO-10's condition is met, so its deferred line is taken: `R3` and `R4` go to 0.1 %
±25 ppm. They take **Susumu RG1608** — the same part family `R58` already uses — so
`U10`'s divider runs on one film system and the *ratio*, which is the entire quantity that
sets the trip point, tracks instead of drifting on two independent films. 1 % ±100 ppm to
0.1 % ±25 ppm takes the trip-point spread from roughly **±21 mV to ±2 mV**; on Nick's own
battery curves ±21 mV is a few minutes of the warning window.

RG1608 is also **anti-sulfur and AEC-Q200**, and that is not decoration here: this divider
hangs off `SW` a few millimetres from two AA cells, and sulfur creep is the classic way a
thick-film chip resistor goes open.

While in the same circuit, `R63` moves from YAGEO `RT0603BRD07100KL` to Susumu
`RG1608P-104-B-T5`. ECO-10 upgraded it to 0.1 % but left it on a different film from its
own partner `R58` — a divider split across two film systems, which is the one thing
ECO-10's own reasoning says not to do. `R55` keeps the YAGEO part: it is the `VOUT3`
bottom leg and belongs to the all-YAGEO LTC3527 pair.

**`R64` stays at 1 %, deliberately.** It is not a divider leg; it is a 555 timing resistor
setting a blink rate. Precision there buys nothing, and the rule that deferred all three
of these — do not buy precision where it buys nothing — applies just as much to the
upgrade as to the deferral. It buys exactly the part the upstream schematic's own
Digi-Key link buys.

---

## 12.2 `R23` — give `VOUT3` its 108 mV back

ECO-8 trimmed `VOUT3` from **3.336 V to 3.228 V** by taking `R23` from 1.78 M to 1.69 M,
for 4.1 mW idle / 6.1 mW at 1× / 8.2 mW at 1.75×. It was the second-largest item in that
ECO's ledger. **It is the wrong trade for this fork, and this reverts it.**

The stated goal of this fork is margin and longevity on a board that is *deliberately
overclocked*. `VDD3` is the CPU's 3.3 V I/O ring and, through the cart switch, the
cartridge supply `VDD35` — the bus a 1.75× overclock actually stresses, since ROM fetch is
what the extra clock is spent on. Trading rail headroom for power on that rail, on this
board, is backwards:

| | |
|---|---|
| bought | 8.2 mW at 1.75×, **0.86 %** of 951 mW — about **3½ minutes** of a 6 h 47 m session |
| paid | **108 mV**, **3.2 %** of the rail |
| and | Nick's build guide Test 3 reads *"VDD3 to GND: **3.3V**"* |

The RAM is unaffected either way — it runs on `VDD2` from LDO `U8`, whose output does not
move with its input — so this is specifically about the 3.3 V I/O and cart domain.

### It also repairs something ECO-8 broke silently

`C41` is the feedforward capacitor across `R23` (`VOUT3 → FB2`), and it sets a zero at
`1/(2π·R_top·C)`. MouseBiteLabs sized it against 1.78 M. ECO-8 moved `R23` to 1.69 M
without touching `C41`, shifting that zero **5.3 %** — and ECO-10, doing the right thing by
its own lights, then carefully preserved the *shifted* constant when it rescaled.

Going to 178 k restores the original exactly:

| | MouseBiteLabs | ECO-8 + ECO-10 | ECO-12 |
|---|---|---|---|
| `R_top × C` | 1.78 M × 15 p = **26.7 µs** | 169 k × 150 p = 25.35 µs | 178 k × 150 p = **26.7 µs** |
| `(R_top∥R_bot) × C` | 640.3 k × 15 p = **9.60 µs** | 62.83 k × 150 p = 9.42 µs | 64.03 k × 150 p = **9.60 µs** |

`VOUT5`'s leg was already exact (`425.7 k × 15 p = 42.57 k × 150 p = 6.39 µs`) and is not
touched.

**Everything ECO-10 bought is kept.** The rescale is what mattered there — the LTC3527's
50 nA max feedback input current was moving `VOUT3` by ±85 mV, which was *worse than the
108 mV ECO-8 was trimming*. At 178 k/100 k the bias error is ±8.9 mV and the leg is still
0.1 % ±25 ppm thin film. This changes the ratio back, not the impedance.

`R23` now carries `RT0603BRD07178KL`, which is already `R21`'s part, so this line of the
change removes a BOM line rather than adding one. (§12.1 adds three, for a net of two — see
the header.)

### What ECO-8's ledger looks like now

| Change | Idle | 1× use | 1.75× |
|---|---|---|---|
| `U7` | 12.0 mW | 12.0 | 12.0 |
| ~~`R23`~~ | ~~4.1~~ **0** | ~~6.1~~ **0** | ~~8.2~~ **0** |
| `DL1` + `R25` | 4.6 | 4.6 | 4.6 |
| `PTC1` | 0.1 | 2.2 | 3.2 |
| `R15` + `R16` | 0.74 | 0.74 | 0.73 |
| `R65` | 0.25 | 0.25 | 0.25 |
| `R11` + `R24` | 0.05 | 0.05 | 0.05 |
| **Total** | **17.7 mW** | **19.8 mW** | **20.8 mW** |
| **As a fraction** | **10.4 %** | **2.5 %** | **2.2 %** |

At 1.75× that is 951 → 930 mW: **6 h 44 m instead of 6 h 35 m**, nine minutes back rather
than twelve. The post-brownout latched-off drain figure — 6.90 mW to 0.98 mW — is
untouched, because it comes from `R11`/`R24`/`R15`/`R16`, not from `R23`.

---

## What the build now refuses to ship

`scripts/build_board.py` asserts all four thresholds at generation time, so a future edit
that moves one fails the build instead of shipping a board that quietly regulates — or
warns — somewhere else:

```python
for name, vref, top, bot, want, tol in (
        ("VOUT5 (LTC3527 FB1)", 1.20, 178e3,  56e3, 5.014, 0.002),
        ("VOUT3 (LTC3527 FB2)", 1.20, 178e3, 100e3, 3.336, 0.002),
        ("U10 low-battery trip", 2.00,  5.1e3, 33e3, 2.309, 0.002),
        ("U17 blink trip",       2.00,  5.1e3, 100e3, 2.102, 0.002)):
```

plus the 555's blink rate. The two supervisor targets are not derivations — they are
MouseBiteLabs' published figures, and the build guide sweeps for exactly them.

---

## Verification

* `python3 scripts/build_board.py --check` — board rebuilds byte-identically from sources
* `python3 scripts/check_consistency.py` — check [3] holds this table to the generator and
  the board; check [6] holds the part numbers to the values
* `python3 scripts/check_stock.py` — `value_conflicts` is now **empty**; it listed
  `R3`, `R4` and `R64` for as long as the conflict stood
* `python3 scripts/test_checks.py` — the negative tests still fire
