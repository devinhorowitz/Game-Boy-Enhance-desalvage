Everything checks out — I have the three files, the power tree, the BOM, and the pad-level net map. Now writing the section.

## POWER BUDGET

Everything below is reconciled against MouseBiteLabs' own measurements. Every line is labelled **[M]** measured, **[D]** derived by arithmetic from a measured or datasheet number, or **[E]** estimated with the basis stated. Where the eight domain reviews used different anchors, I have re-referred their arithmetic to one common set and said so; I have introduced no new findings and no new part numbers.

---

### 0. The common anchor set

| Quantity | Value | Class | Source |
|---|---|---|---|
| Pack voltage at measurement | 2.40 V | [M] | MBL wiki states the figures were taken at 2.4 V (NiMH), Fluke 117, P = V·I |
| VOUT3 | 3.336 V | [D] | LTC3527 V_FB = 1.20 V typ (1.176/1.224 limits) × (1 + R23 1.78 M / R55 1.00 M) |
| VOUT5 | 5.014 V | [D] | 1.20 × (1 + R21 1.78 M / R22 560 k) |
| VDD2 = VAUD | 2.500 V | [D] | NCV8164ASN250T1G ordering table |
| LDO efficiency (U8, U4) | 74.87 % | [D] | (2.5/3.336) × (30/30.03) — matches MBL's own "roughly 75 % efficient" remark about the audio supply, which is the arithmetic confirmation that this whole model is on the right rails |
| Boost ch2 efficiency, VIN 2.4 V | 92.4 % @ 37 mA, 92.8 % @ 72 mA, 92.3 % @ 110 mA, 91.1 % @ 150 mA | [D] | LTC3527 curve G05, digitised independently by two reviewers with agreeing results |
| Boost ch1 efficiency, VIN 2.4 V | ~43 % @ 1 mA (fixed-freq), ~88 % @ 90–130 mA | [D] | curve G07; the light-load figure carries the whole 500 µA device Iq |
| Series path F1 + PTC1 | 0.150 Ω central (0.115–0.230) | [D] | F1 ≤ 0.080 Ω max (no typ published); PTC1 0805L075SL R_min 0.040 / R_1max 0.150 |
| Board copper, battery to U5 | 4.5 mΩ | [D] | scanline integral over the In2.Cu VCC pour, 0.491 mΩ/sq |
| Usable pack energy | 6.26 Wh | [D] | 1175 mW × 5.333 h = 6.266 Wh; 410 mW × 15.25 h = 6.253 Wh — MBL's two endpoints agree to 0.2 %, which validates their power and runtime figures against each other |

**The structural fact that governs everything below:** VDD2 (CPU core + SRAM), VAUD (audio), VDD3 (CPU I/O, logic, cart, and the ClockxControl's V+ at P1 pad S1) are all fed from VOUT3, which is LTC3527 **converter 2** — the 400 mA channel. VOUT5 (backlight via VSHA, cart 5 V) is on converter 1, the 800 mA channel. Every milliamp the overclock adds passes through converter 2.

---

### 1. Where the 170 mW of idle goes, and where a representative in-use figure goes

#### 1a. Fixing the load model, and the one number I had to fit

There is no published per-rail current measurement for this board. The only per-rail data that exists is MouseBiteLabs' own annotation block on the AGBM-01 root schematic, headed **"Rough estimates (rounded up)"**: `2.5V @ ~30mA`, `3.3V@~10mA (no cart)`, `3.3V@~20mA`, `3.3V@~50mA (Everdrive)`, `5.0V @ ~130mA`. Those are the load model's backbone, and their author labelled them rounded up.

The audio rail I did not have to estimate — it is built from digitised datasheet curves at the actual 2.5 V operating point: U7 TLV9364 at 1.354 mA/amplifier × 4 = 5.42 mA, U6 LM4853 at 1.8 mA, U9 plus the four 100 k bias dividers and the VR2 pot track at ~0.4 mA. **I_VAUD(quiescent) = 7.6 mA [D].**

Taking MBL's `~30 mA` for VDD2 at idle over-predicts AGBM-01's measured 170 mW by 14.5 mW (8.5 %). Taking 19.5 mA instead closes **AGBM-02** to within 1.3 mW of its measured 141 mW, using the same downstream (verified identical from both boards' netlists: same two NCV8164, same three TPS22917, same three TPS3840). I have adopted the AGBM-02-anchored figure, because it is validated against an independent measurement rather than fitted to the board under review:

**I_VDD2(idle) = 19.5 mA [E]** — the single fitted parameter in this section. It is 35 % below MBL's rounded-up annotation, which is what "rounded up" means.

#### 1b. Idle accounting — AGBM-01, 170 mW measured

| Line | mW at battery | % | Class |
|---|---|---|---|
| **Measured total, idle (no game, no screen)** | **170.0** | 100 % | **[M]** |
| *Useful work* | | | |
| CPU core + SRAM (VDD2, 19.5 mA × 2.5 V) | 48.8 | 28.7 % | [E] |
| CPU I/O + logic (VDD3, 10 mA × 3.336 V, no cart) | 33.4 | 19.6 % | [E] MBL annotation |
| Audio chain (VAUD, 7.6 mA × 2.5 V) | 19.0 | 11.2 % | [D] digitised IQ |
| Green power LED DL1 through R25 (0.93 mA × 5.014 V) | 4.7 | 2.8 % | [D] digitised LED I–V |
| Supporting-IC quiescent: 3 × TPS3840 (300 nA ea.), 3 × TPS22917 (0.5 µA ea.), MIC1553 in shutdown (<1 µA), brownout latch bias (387 µA off VBATT), supervisor dividers, pull-up network | 1.6 | 0.9 % | [D] |
| **Useful subtotal** | **107.5** | **63.2 %** | |
| *Losses* | | | |
| U8 LDO (VDD2), 0.836 V × 19.53 mA | 16.4 | 9.6 % | [D] |
| LTC3527 converter 2, 124.1 mW delivered at 92.4 % | 10.2 | 6.0 % | [D] curve |
| U4 LDO (VAUD), 0.836 V × 7.63 mA | 6.5 | 3.8 % | [D] |
| LTC3527 converter 1, 5.0 mW delivered at ~43 % (carries the 500 µA device Iq) | 6.6 | 3.9 % | [D] curve |
| Series protection F1 + PTC1 (70.8 mA² × 0.150 Ω) | 0.8 | 0.5 % | [D] |
| U18 load switch (10 mA² × 0.09 Ω) | 0.01 | — | [D] |
| Board copper (70.8 mA² × 4.5 mΩ) | 0.02 | — | [D] |
| **Loss subtotal** | **40.5** | **23.8 %** | |
| **Named lines total** | **148.0** | **87.1 %** | |
| **UNACCOUNTED** | **22.0** | **12.9 %** | |

**What the 22 mW is.** It is not a modelling slop term — it is the AGBM-01/AGBM-02 gap wearing a different hat. The same load model that closes AGBM-02 to 1.3 mW leaves 22 mW of AGBM-01 unallocated; the measured gap is 29 mW. Nothing downstream differs between the boards, so the residual has to be LTC3527 light-load overhead: 1.2 MHz gate-drive and core loss in two 3×3×1.5 mm wire-wound drums versus 2.1 MHz PFM in 2×1.6 mm metal-composite parts, plus 500 µA of active device quiescent versus 2 × 11 µA. The converter review identified ~3 mW of it as the marginal cost of the shared Burst-Mode decision forcing the 0.93 mA 5 V rail into fixed-frequency PWM, ~2.3 mW as excess conduction loss, and ~2.7 mW as the Iq delta. **The remaining ~14 mW is not separable from published data. It is the largest single unallocated line in this budget and it needs a current probe on TP13 and TP16 to close.**

Note also that the two curve-based converter lines (10.2 + 6.6 = 16.8 mW) are the numbers the *published curves* predict. The measurement says the LTC3527 is doing worse than that by roughly the residual. Do not read those two lines as verified.

#### 1c. In-use accounting — 792 mW, Funnyplaying ITA, max brightness, OEM cart, speaker

**Which figure and why.** I use **792 mW** — FP ITA at max brightness — as the representative operating point. It is a real measured configuration; its 410 mW companion bounds the backlight swing on the same panel; and it avoids the 1175 mW corner, which is the extreme (Hispeedido IPS at max brightness *plus* an Everdrive *plus* max volume into the speaker) and is not what a builder plays at. The 1175 mW corner is carried alongside as the stress case for the PTC and current-limit work.

Input current 792 mW / 2.4 V = **330 mA [D]**.

| Line | mW at battery | % | Class |
|---|---|---|---|
| **Measured total** | **792.0** | 100 % | **[M]** |
| *Useful work* | | | |
| Backlight + cart 5 V (VOUT5, 91 mA × 5.014 V) | 456 | 57.6 % | [D] back-solved — see below |
| CPU core + SRAM (VDD2, 30 mA × 2.5 V) | 75.0 | 9.5 % | [E] MBL annotation |
| CPU I/O + logic + OEM cart (VDD3, 20 mA × 3.336 V) | 66.7 | 8.4 % | [E] MBL annotation |
| Audio (VAUD, 22 mA × 2.5 V, speaker at volume) | 55.0 | 6.9 % | [E] inside MBL's 50–100 mW range |
| **Useful subtotal** | **652.7** | **82.4 %** | |
| *Losses* | | | |
| LTC3527 converter 1 (456 mW delivered at ~88 %) | 60.7 | 7.7 % | [D] |
| U8 LDO (0.836 V × 30.03 mA) | 25.2 | 3.2 % | [D] |
| LTC3527 converter 2 (240.3 mW delivered at 92.8 %) | 18.7 | 2.4 % | [D] curve |
| U4 LDO (0.836 V × 22.03 mA) | 18.4 | 2.3 % | [D] |
| Series protection F1 + PTC1 (330 mA² × 0.150 Ω) | 16.3 | 2.1 % | [D] |
| Load switches U11 + U18 conduction | 0.1 | — | [D] |
| **Loss subtotal** | **139.4** | **17.6 %** | |

**Honesty about closure.** The VOUT5 line is back-solved: it is whatever is left after every other line, so the in-use budget closes by construction and the unallocated energy is hidden inside it. That is not as bad as it sounds, because the same procedure applied at the **1175 mW** corner (VDD2 30 mA, VDD3 50 mA with an Everdrive, VAUD 30 mA at max volume → VOUT3 = 110 mA) back-solves VOUT5 to **130.1 mA** — against MouseBiteLabs' own independent annotation of **`5.0V @ ~130mA`**. Two independent routes to the same number is the strongest validation available for this model. It bounds the in-use model error at roughly the annotation's own precision, about **±5 % of total**, but it does not let me attribute that ±5 % to a named line. Only a probe on TP13 (VOUT5) and TP16 (VOUT3) closes it.

Two things worth pulling out of the in-use table:

- **The backlight is 58 % of the console.** Every efficiency lever in this review operates on the remaining 42 %.
- **Converter 1 is the largest single loss on the board in use — 60.7 mW**, more than double converter 2's, because it carries 91–130 mA at a 0.52 duty cycle through the 0.3/0.4 Ω switch pair. It is also the channel nobody proposed changing.

---

### 2. The same accounting with the ClockxControl fitted

#### 2a. Where the module's current actually lands — and the flag

From the netlist, unambiguously: the module's V+ is on P1 pad **S1 = VDD3**, fed from VOUT3 through U18 (TPS22917, ~90 mΩ, 1 mV of drop — irrelevant). The overclock's extra CPU current is on **VDD2**, which is U8's output; an LDO passes its load current 1:1, so that current appears on **VOUT3** too. CPU I/O switching is on **VDD3**. The cart reaches VDD35, which has **no source anywhere on the board** (verified — all ten pads are loads or connectors), so it is generated inside the salvaged CPU from its VDD3/VDD2 pins and bills to VOUT3 as well.

**Every part of the ClockxControl's cost — module supply, core dynamic power, I/O switching, cart — lands on LTC3527 converter 2, the 400 mA channel.**

**FLAG, as the brief requires.** insideGadgets publish exactly one sentence: *"Consumes about 12mA of additional current and when the GBA/GBC/DMG is overclocked, it too will use 40-60mA more."* Grammatically "it" is the console. There is no measurement point, no speed, no cartridge or screen condition, and the identical 40–60 mA is quoted for the DMG (3x), the GBC (2x) and the GBA (1.75x) — three different CPUs on three different rails. **It is a system-level, battery-side figure and must not be silently treated as a VOUT3 current.** Doing so inflates the overclock's cost by about 60 %: 50 mA read as battery current is 120 mW at the battery; read as a VOUT3 current it becomes 50 × 3.336 / 0.92 ≈ 181 mW plus series, ~190 mW. Several of the domain reviews took the second reading.

#### 2b. My own model, and the cross-check that settles it

CMOS dynamic power scales with clock; leakage does not. Taking VDD2 as 75 % dynamic and VDD3 I/O as 60 % dynamic **[E, stated basis, no public AGB CPU datasheet exists]**:

| Rail | 1x (mA) | 1.75x (mA) | Δ (mA) |
|---|---|---|---|
| VDD2 (core + SRAM), in use | 30.0 | 48.0 | +18.0 |
| VDD3 (CPU I/O, logic) | 20.0 | 29.0 | +9.0 |
| VDD35 → cart bus | (in VDD3) | — | +3.0 [E] |
| Module's own supply, on VDD3 | +12.0 | +12.0 | (fixed) |
| **ΔI on VOUT3, total** | **+12.0** | **+42.0** | |

Referred to the battery, the overclock component alone (30 mA of ΔI on VOUT3) is 30 × 3.336 / 0.925 = 108 mW at VCC, ≈ **115 mW at the battery**. insideGadgets' 40–60 mA read battery-side is 96–144 mW at 2.4 V. **The two agree.** The per-rail reading (190 mW) does not fit inside either. I use the battery-side reading.

#### 2c. The overclocked in-use budget

| | 1x, no module | 1x, module fitted | 1.75x |
|---|---|---|---|
| VOUT3 current [D/E] | 72 mA | 84 mA | 114 mA |
| VOUT3 delivered | 240.3 mW | 280.3 mW | 380.3 mW |
| Converter 2 input (92.8 / 92.6 / 92.5 %) | 259 mW | 302.7 mW | 411 mW |
| Converter 1 input (unchanged) | 516.7 mW | 516.7 mW | 516.7 mW |
| Input current | 330 mA | 348 mA | 397 mA |
| Series F1 + PTC1 loss | 16.3 mW | 18.2 mW | 23.6 mW |
| **Total at the battery** | **792 mW [M]** | **837 mW [D]** | **951 mW [D]** |

**Fitting the module costs 45 mW before it overclocks anything.** At idle the same 12 mA costs 44 mW — **26 % of the entire 170 mW idle figure** — and idle goes 170 → 214 mW at 1x and → **266 mW at 1.75x** (+56 %).

#### 2d. What the overclock costs, and how much of it is waste

The 1x-with-module → 1.75x increment is **+114 mW**; the whole module-plus-overclock increment against a stock board is **+159 mW**. Decomposing the 159 mW:

| Component of the increment | mW | % of increment | Class |
|---|---|---|---|
| **Useful work at the load pins** | **125.0** | **78.6 %** | |
|  — module's own supply (12 mA × 3.336 V on VDD3) | 40.0 | 25.2 % | [D] |
|  — extra CPU core + SRAM (18 mA × 2.5 V on VDD2) | 45.0 | 28.3 % | [E] |
|  — extra CPU I/O switching (9 mA × 3.336 V on VDD3) | 30.0 | 18.9 % | [E] |
|  — extra cart bus activity (3 mA × 3.336 V) | 10.0 | 6.3 % | [E] |
| **Conversion and series loss** | **34.3** | **21.6 %** | |
|  — U8 LDO burns 0.836 V × 18 mA of new core current | 15.0 | 9.4 % | [D] |
|  — LTC3527 converter 2, extra loss on +140 mW delivered | 12.0 | 7.5 % | [D] |
|  — F1 + PTC1, series loss rises 16.3 → 23.6 mW | 7.3 | 4.6 % | [D] |
|  — board copper | 0.2 | 0.1 % | [D] |

**Just over a fifth of what the overclock costs at the battery is loss rather than work**, and the biggest single piece of that is U8 — an LDO throwing away 0.836 V on every milliamp of new core current the ClockxControl creates. That is the one loss the overclock *creates* rather than merely enlarges, and it is the reason the core-rail redesign dominates the recovery table.

The overclock also consumes converter 2's margin. At end of discharge the guaranteed capability of the 400 mA channel at 3.336 V is ~178 mA (VIN 2.0 V, the TPS3840DL20 cutoff); the overclocked demand is 114 mA at the ITA anchor and reaches ~152 mA at the 1175 mW corner. That is a margin problem, not an energy one, and it is covered in the converter and stability findings.

---

### 3. Ranked recovery table

Every efficiency finding that survived verification, re-referred to the anchors above. Savings are **at the battery**. "1x" and "1.75x" are the in-use 792 / 951 mW operating points.

#### Tier 1 — drop-in parts only (no schematic change, no PCB revision, applies to an already-fabricated board)

| # | Lever | 1x | 1.75x | Class | Running total (1.75x) |
|---|---|---|---|---|---|
| 1 | **U7 TLV9364QPWRQ1 → TLV9064IPWR.** ΔIQ = 4 × (1.354 − 0.528) = 3.30 mA at VAUD, passed 1:1 by U4 to VOUT3 = 11.0 mW, /0.925 | **12.0** | **12.0** | drop-in, identical TSSOP-14 land | 12.0 |
| 2 | **VOUT3 trim, R23 1.78 M → 1.69 M** (3.336 → 3.228 V). Saving = 0.108 V × (I_U8 + I_U4) | **6.1** | **8.2** | drop-in, one 0603 | 20.2 |
| 3 | **DL1 → 150060GS75000 + R25 3.3 k → 22 k.** 4.66 → 0.62 mW at VOUT5, referred through ch1 at 88 % | **4.6** | **4.6** | drop-in, same 0603 lands | 24.8 |
| 4 | **PTC1 0805L075SLYR → 0805L110SLYR.** ΔR mid 0.020 Ω × I_in² | **2.2** | **3.2** | drop-in, same 0805 land | 28.0 |
| 5 | **F1 → F0805B2R50FSTR** (0.080 → 0.060 Ω max). Upper bound — only maxima are published | **≤2.2** | **≤3.2** | build option | 31.2 |
| 6 | **Six resistor values in the quiescent network**: R15/R16 10 k → 100 k (brownout latch, 0.74 mW), R65 100 k → 1 M (0.25 mW), R3/R4 and R58/R63 supervisor dividers ×10 (0.19 mW), R11/R24 (0.05 mW) | **1.2** | **1.2** | drop-in, six 0603s | **32.4** |

**Tier 1 total: 28.3 mW at 1x, 32.4 mW at 1.75x.**

#### Tier 2 — one PCB revision, no new nets

| # | Lever | 1x | 1.75x | Class | Note |
|---|---|---|---|---|---|
| 7 | **L2 4.7 µH → WE-MAPI 74438356047** (120 → 63 mΩ DCR), on my reconciled ch2 inductor currents (108 / 171 mA) | 0.7 | 1.7 | needs PCB revision | Rounding error, and the 4.1 × 4.1 mm body collides with C42 — **not worth a revision** |
| — | L2 4.7 → 3.3 µH (same land, true drop-in) | 1.1 | — | drop-in | **Barred on this fork.** It reduces converter 2's output-current capability, taking peak inductor current from 17 % to 24 % above the 400 mA guaranteed limit at end of discharge — the exact margin the overclock is already eating |
| — | Channel swap: VOUT3 → converter 1, VOUT5 → converter 2 | **−5.5** | **−2.6** | schematic + PCB | **Negative at these anchors.** Re-referred to the reconciled rail split, VOUT5 carries 91–130 mA in use and VOUT3 only 72–114 mA, so moving the *heavier* rail onto the weak channel loses more than the swap gains. It wins only at minimum brightness. Its value is the stability/current-limit argument, not efficiency |

#### Tier 3 — redesign the core rail (schematic change + PCB revision)

| # | Lever | 1x | 1.75x | Class |
|---|---|---|---|---|
| 8a | **U8 NCV8164 → TPS63802 buck-boost fed from VCC.** Chain goes 0.925 × 0.749 = 69.3 % → 89 %. At 30 / 48 mA of core current | **24** | **39** | schematic + PCB revision |
| 8b | *Alternative:* U8 → TPS62840 buck from VOUT3 + a TPS3840DL23 to regenerate /PG_2V5. Chain 0.925 × 0.93 = 86 % | 21 | 34 | schematic + PCB revision |

Take **8a**, not 8b: the TPS63802 carries an open-drain PG on pad 5 at 95 %/90 % thresholds — numerically identical to the NCV8164 PGOOD it replaces — so `/PG_2V5` transfers with **zero added parts**, and MouseBiteLabs already ships that exact land pattern on AGBM-02. This matters more than the 3 mW: `/PG_2V5` has six pads including **U5 pin 1 (~SHDN1)**, so losing it kills the 5 V boost channel and the CPU never leaves reset. Option 8b needs a fourth supervisor to avoid a dead board.

**Overlap warning:** with U8 gone, lever 2 (the VOUT3 trim) only saves on U4's 22 mA, dropping from 6.1 → 2.4 mW at 1x and 8.2 → 2.4 mW at 1.75x. **Do not sum tiers 1 and 3 naively.**

| Combined | 1x | 1.75x |
|---|---|---|
| Tier 1 alone | 28.3 | 32.4 |
| Tier 1 + Tier 3 (overlap removed) | **48.6** | **65.6** |

#### Tier 4 — replace the converter (full front-end respin)

| # | Lever | Idle | In use 1x | In use 1.75x | Class |
|---|---|---|---|---|---|
| 9 | **LTC3527 → 2 × TPS63802** (the AGBM-02 transplant) | **29 [M]** | ~0 | ~3 | full front-end PCB revision |

This is the only **measured** number in the whole table — 170 vs 141 mW, MouseBiteLabs' own bench figures on two boards with verified-identical downstream. But it is a **light-load-only** gap. At in-use currents the digitised curves put the two converters within about a point of each other; a 29 mW fixed overhead cannot survive as 29 mW at 240–380 mW of rail delivery. The physical story is consistent: at idle the two TPS63802s each sit in PFM at 11 µA, while the LTC3527 is locked in 1.2 MHz fixed-frequency PWM on *both* channels — its Burst-Mode decision is chip-level and requires both outputs below threshold, and converter 2 at 37 mA never is. Under load AGBM-02's converters also leave PFM and the gap closes.

**So: 29 mW at idle, nearly nothing in use.** Idle is not an operating point anyone plays at. This lever should be taken only because you are respinning the front end anyway, and it is the *last* thing on the list by in-use return, not the first — despite being the only measured one.

#### Levers evaluated and correctly declined (0 mW, listed so nobody re-derives them)

- **A switcher on VAUD** — 4.8 mW at the cost of the LDO's 85 dB PSRR and 9 µV_RMS on the rail that *is* the PWM DAC's reference. Declined.
- **A class-D speaker amp** — ~25 mW at MBL's own max-volume anchor, 0 muted, −1.5 mW on headphones; and the TPA2005D1's 2.5 V minimum VDD sits *above* VAUD's 2.45 V worst case. Declined.
- **A better LDO in U8's footprint** — 0.1 mW. Any 2.5 V linear from 3.336 V is 74.9 % efficient whatever the part number.
- **An ideal-diode/eFuse in place of F1+PTC1** — the LM66100 is 141–210 mΩ at VIN 1.8 V, *worse* than what is fitted. Costs 4–22 mW.
- **Depopulating C3/C4** — 2.6 / 3.9 mW, but ECO-7 already marks X1/C3/C4 DNP, so the incremental saving over the planned build is **zero**. It is what you lose by leaving them in on a hand retrofit.
- **F1/PTC1 thermal relief, EM chokes and beads, board copper widening, extra VDD2 vias** — 0.03 mW, 0 mW, 0.5 mW, 0 mW. Rounding error or non-existent.

---

### 4. The honest headline

**No. The energy the ClockxControl costs cannot be won back. At the maximum effort anyone in this review proposed you recover about 43 % of it, and the change class required to get past 20 % is a schematic change plus a PCB revision on the core rail of a board built around irreplaceable salvaged silicon.**

At the 792 mW representative operating point, with a 6.26 Wh pack:

| Configuration | Power | Runtime | vs stock |
|---|---|---|---|
| Stock, 1x, no module | 792 mW | 7 h 54 m | — |
| **ClockxControl fitted, 1.75x, no fixes** | **951 mW** | **6 h 35 m** | **−1 h 19 m** |
| + all Tier 1 drop-in fixes (32 mW) | 919 mW | 6 h 49 m | −1 h 05 m |
| + Tier 3 core-rail redesign (66 mW total) | 885 mW | 7 h 04 m | −50 m |
| + Tier 4 converter transplant (~69 mW total) | 882 mW | 7 h 06 m | −48 m |

Stated as recovery of the 159 mW the module and overclock cost:

- **Drop-in parts only — 32 mW, 20 %.** Six part swaps and two resistor values, all on existing land patterns, applicable to a board already in a shell. This recovers 14 minutes of the 79 minutes of runtime the overclock takes.
- **One PCB revision of the core rail — 66 mW, 41 %.** Recovers 29 of the 79 minutes.
- **Everything, including a full front-end respin — ~69 mW, 43 %.** Recovers 31 of the 79 minutes. The last 3 mW costs an entire converter redesign.

Three things a builder should take from that:

1. **The single most efficient change on the board is not a power part at all.** U7 is a 4.5 V-minimum op-amp being run on 2.5 V with its inputs 0.75 V above the common-mode ceiling. Replacing it with the pin-identical TLV9064IPWR is a correctness fix that also happens to be the largest drop-in saving here — **12 mW, 37 % of everything Tier 1 recovers**, from a part that is cheaper than the one fitted. Do it whether or not you care about runtime.
2. **21.6 % of the overclock's cost is loss, and 9.4 percentage points of that is one LDO.** U8 burns 15 mW of new heat purely because the CPU core rail is made linearly from a boosted rail. That is the only loss the overclock *creates*, and it is the whole case for Tier 3.
3. **The fixed cost of the module is worse than the marginal cost of the overclock, proportionally.** 12 mA on VDD3 is 44–45 mW at the battery whether you overclock or not — 26 % of the board's entire idle figure, for a part that is doing nothing at 1x. There is no lever anywhere in this review that touches it: it is 12 mA into a 3.336 V rail through a 90 mΩ switch, and the only inefficiency in that path is the boost itself.

And the caveat that bounds all of it: **~13 % of the idle budget (22 mW) is unaccounted**, and in use I can bound the model error to about ±5 % but cannot attribute it to a line. The 22 mW is almost certainly LTC3527 light-load overhead — it is the same energy as the measured AGBM-01/AGBM-02 gap — but the published curves say the converter should be doing better than the measurement shows, and I cannot reconcile that from datasheets alone. **Two five-minute measurements would close it: a current probe on TP16 (VOUT3) and TP13 (VOUT5), at idle and with a game running, at 1x and 1.75x.** Every estimated line in this section collapses to a measured one if someone takes them.