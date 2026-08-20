I've completed the sweep. Report follows.

---

# COMPLETENESS CRITIC — what the eight domain reviews missed

Method: extracted all 235 refdes from `/tmp/claude-0/-home-user-Game-Boy-Enhance-desalvage/d4943806-0aca-58a2-867c-47f254d93b45/scratchpad/review/01_bom.md`, diffed against the `refs` fields and full body text of all 100 findings in `/tmp/claude-0/-home-user-Game-Boy-Enhance-desalvage/d4943806-0aca-58a2-867c-47f254d93b45/scratchpad/review/findings_raw.json`. 68 refdes appear in no finding's `refs`; 26 appear nowhere in any finding text. Most are test points and are correctly ignored. Below are the ones that matter, plus the operating conditions, missing upgrade classes, and internal contradictions.

---

## 1. THE BIGGEST MISS: the vendor's own page rules out the review's worst case

Every 1.75x number in every domain is computed on the **1175 mW** configuration, which `00_context.md` defines as "max brightness, **Everdrive**, max volume, speaker." The ClockxControl product page — already captured locally at `/tmp/claude-0/.../scratchpad/cxc.txt`, line 80, and re-read by me verbatim — says:

> "**GBA flash carts don't seem to work when trying to go faster than 1x as they crash**, going slower should work and the GBA only seems to allow 1.75x max."

Nobody read past the 12 mA / 40–60 mA sentence on line 81. Consequence: **Everdrive + 1.75x is not a reachable operating point.** The correct worst case is 1.75x with a genuine cartridge. Using MouseBiteLabs' own schematic annotations, which I verified by grep in `agbm01/AGBM-01_AA_1-2.kicad_sch` — `3.3V@~50mA (Everdrive)` vs `3.3V@~20mA` vs `3.3V@~10mA (no cart)` — the delta is 30 mA on VDD3:

- 30 mA × 3.336 V = 100 mW at VOUT3 → /0.89 ≈ **112 mW less at the battery**
- Worst case becomes 1175 − 112 + ~250 (overclock) ≈ **1313 mW**, not 1410–1440 mW → **547 mA at 2.4 V**, not 588–600 mA
- VOUT3 at 1.75x becomes ~182 mA, not 212 mA

This directly softens two *stability* findings: `ptc1-hold-current-below-load` / `ptc1-hold-current-vs-overclock` (547 mA sits at, not 6–9 % over, the 0.55–0.62 A rerated hold current) and `converter2-current-limit-vs-overclock` (182 mA against a ~200–220 mA guaranteed ceiling is a small margin, not a deficit). Neither is refuted; both are quantitatively wrong at the operating point they claim.

## 2. The display interface is an unexamined domain — and it is the real overclock limit

Nobody looked at P2 (the 40-pin LCD FFC) as anything but a power load. Verified from the board netlist:

- **DCK (FFC pin 3) is the LCD dot clock and it scales 1:1 with the ClockxControl.** GBATEK gives 4 CPU cycles per dot, 308 dots × 228 lines = 280,896 cycles/frame at 16.78 MHz → dot clock = 16.777216/4 = **4.194304 MHz**, exactly the crystal frequency. At 1.75x the kit's DCLK pin sees **7.34 MHz**.
- The only series element on the entire display bus is **R36 (270 Ω)** between U1 pin 84 and P2 pin 3. LP, PS, SPL, CLS, SPS, MOD and 15 data lines have none, all scaling with the clock, all crossing an unshielded flex.
- `cxc.txt` lines 74–79, verbatim: *"There is a chance it may not be compatible with your display when going faster… Works with the FunnyPlaying laminated IPS GBA screen at speed 1.25x and below. At 1.5x, the screen fades to black… Not recommended with the GBA OneChip IPS screen… it's glitchy."*

So the **screen, not the power tree, is the binding constraint on usable ratio** — and the Hispeedido kit that MouseBiteLabs benchmarked with is not on insideGadgets' compatibility list at all. `clk-return-path-patchwork` tried to attribute the FunnyPlaying failure to the board's clock routing and the panel correctly struck that; nobody then supplied the actual mechanism. Every 1.75x power number in this review may describe a configuration most builders cannot run.

**R36, R38, R39, R40, R43** (`270`, `47`, `47`, `15`, `15`) appear in no finding text at all. R38/R39 sit between the CPU and cart pins ~WR and ~CS; they are the only damping on a cart bus that runs 75 % faster at 1.75x.

## 3. The ClockxControl's own user interface was never traced

I dumped MOD1's pads from `AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb`: pad 1 → `/CPU/TP2` (Select), pad 2 → `/CPU/TP9` (L), pad 3 → `/CPU/TP8` (R) — matching the vendor's "hold select and press the L & R shoulder buttons."

Those three nets each carry a **0.01 µF debounce capacitor** (C78, C64, C63) plus 15 Ω series resistors, and TP8/TP9 also feed U15. `slow-edge-inputs-u15-u16` flagged those exact caps as a Δt/Δv violation for U15/U16 and never noticed the module is now a third consumer of the same nets; the ClockxControl domain never looked at its button interface at all. Whether the module's chord detection tolerates a ~500 µs edge is unverifiable (internals unpublished) — but it is the **only** control the user has over the module, and it is a commissioning item nobody listed.

I did check the obvious collision and it is **clean**: the screen mode combos need Start (L+R+Start+A → ZA, +B → ZB); the module needs Select. They are disjoint. Worth recording as a negative result.

## 4. Components nobody touched that matter

- **VR1 + R26** (50 k trimmer, 33 k) — the *entire Display sheet's* standing divider, missed by an `ics-quiescent` finding that claimed to inventory the whole discrete population at 7.4 mW. Verified topology: R26 from VDD5 to VR1 pin 1, VR1 pin 3 to GND, wiper to FFC pin 29 (VCOM). Full track conducts regardless of wiper: 5.014 V / (33 k + 50 k) = **60.4 µA = 0.303 mW at VDD5** whenever the screen is on (not in the 170 mW idle figure). VCOM is the *original* AGB LCD's common-electrode bias; most IPS kits ignore pin 29. Depopulating VR1+R26 is a zero-cost build option worth ~0.3 mW, contingent on the kit — **unverified whether any specific kit uses pin 29.** Honest size: 0.03–0.05 % of in-use power. Rounding error, but it is a hole in a finding that claimed exhaustiveness.
- **C38 (1 µF, LM4853 BYPASS)** — mentioned nowhere. From SNAS155E, verbatim: *"The value of the pin bypass capacitor, CB, directly affects the LM4853's half-supply voltage stability and PSRR. The stability and supply rejection increase as the bypass capacitor's value increases."* CB is the **only board-side knob on the amplifier's PSRR**, it is a drop-in value change on an existing 0603, and it becomes the deciding parameter if any of the three VDD2/VAUD switcher proposals is adopted. TI states the trade explicitly (PSRR vs click-and-pop vs size), so it is not a free win. Placement checked and fine: C38 pad 1 is **2.81 mm** from U6 pin 7. 0 mW; quality.
- **C11 / C13 (VDD5 decoupling)** — checked and **adequate**, reporting the negative result. VDD5 has exactly 9 pads and only these two capacitors (~0.9 µF effective at 5 V bias, unverified derating for the 1 µF at 5 V), serving the largest load on the board. It is fine because the refill path is resistive: U11's Ron is 80–100 mΩ (25 °C, 5 V), so τ ≈ 81 ns and the steady droop is 130 mA × 90 mΩ = 11.7 mV. No action.
- **VAUD at the amplifier** — checked and adequate. C59 (10 µF) is **64.8 mm** from U6; local bulk is C54 (3.18 mm) + C36 (7.88 mm) = 2 µF. Fine, because the LDO's output impedance is milliohms inside its loop bandwidth. No action.
- **C74/C75/C76, R43** — I initially flagged these as omissions from the slow-edge finding; **they are correctly excluded**. TP4/TP5/TP7 go only to the CPU, not to U15/U16. The finding's list of five was right.

## 5. Upgrade classes nobody proposed

- **ESD on the external ports.** Zero TVS anywhere on AGBM-01 (only D1/D2, 1SS355VM switching diodes). AGBM-11 carries an SMF5.0A-T13 (verified in `agbm11/*.kicad_sch`) but on the battery input, not on any port. Three user-accessible connectors feed an irreplaceable salvaged CPU. **My conclusion is mostly negative and I am recording it as such**: the link port is already the best-protected node on the board (RA1's 330 Ω in series plus the ACM2520 chokes), the headphone jack drives into a low-Z amp output, and the 32-line cart bus has no room and would be *harmed* by added capacitance at a 7.34 MHz bus rate. The one genuine exposure is **P4 pin 1 = VDD35 through EM3** — a *power* pin on an external cable with only a 0.2 Ω ferrite (MH1608-601Y, 600 Ω @100 MHz, 200 mΩ DCR max) between the outside world and a rail generated *inside* the salvaged CPU, with no fuse, no current limit and no clamp. Needs a PCB revision; speculative.
- **Connector / switch / cart-slot contact quality.** SW1 was analysed and correctly dismissed (carries no load current). Nobody assessed **P1's 36 contacts**, which on a salvaged 20-year-old board carry the entire cart bus, VDD35, and — now — the ClockxControl's supply via pad S1. This is the exact parallel of the `battery-contacts-and-cell-esr` finding and deserves the same treatment: unquantifiable from datasheets, zero-cost to clean, potentially larger than any component swap.
- **The crystal for non-ClockxControl builds.** Verified: X1's land is `Bucketmouse:AGB-Crystal`, two custom 1.5 × 4.5 mm pads on 8.52 mm centres. **No standard SMD crystal package fits it** — so there is no drop-in crystal upgrade, and a modern part needs a PCB revision. The salvaged crystal's ESR and the drive level set by R41 (2.2 k) / R1 (1.5 M) are uncharacterised. Nobody said any of this.
- **Cold operation.** Not considered anywhere. Verified from the Energizer E91 datasheet: **Operating Temp −18 °C to 55 °C**, Nominal IR 150–300 mΩ *fresh*, and all capacity curves at 21 °C — **no published cold IR**. So the cold case cannot be quantified from the datasheet, but the direction is unambiguous and it stacks against the review: cold raises pack ESR → more sag → the TPS3840DL20's verified 2.0 V cutoff trips earlier, and the LTC3527's channel-2 ceiling falls with VIN. Every brownout number in this review is a room-temperature number. (Cold *helps* PTC1 — hold current rises to 1.15–1.24 A at −40 °C.)
- **No consolidated ledger.** Nobody produced the non-double-counted drop-in total, which is what the reviewer actually asked for. See §7.

## 6. Contradictions inside the surviving set

**(a) The channel-swap finding's verdict inverts on a number in the designer's own schematic.** `ltc3527-channel-assignment-backwards` computes its VOUT5 penalty at **88 mA**. MouseBiteLabs annotates the 5 V rail **`5.0V @ ~130mA`** — I verified the text and its position (118.618, 151.384), nearest object R21 at 7.41 mm, i.e. the VOUT5 feedback divider. The `clockxcontrol` domain independently derived 120–160 mA. Redoing the finding's *own* model at 130 mA (D = 0.5114, ΔI = 0.2221 A, I_L,avg = 0.130/0.4886 = 0.2661 A, I_rms² = 0.074904; R_eff+DCR ch1 = 0.4689 Ω, ch2 = 0.6689 Ω):

- penalty = 0.074904 × (0.6689 − 0.4689) = **+15.0 mW**, not +7.3 mW
- self-consistent split at 1175 mW total (VOUT5 130 mA, VOUT3 135 mA): gain on VOUT3 = 6.98 mW → **net −8.0 mW**
- overclocked (VOUT3 197 mA): gain 14.6 mW → **net −0.4 mW**

The swap is **net negative at max brightness**, stock and overclocked, and only wins at low backlight. Its own risk section says "if your screen draws more than ~90 mA on VSHA this swap trades one ceiling for another" — the designer's own number is 130 mA, so the finding's stated disqualifying condition is met. It should be **rejected**, not offered at 4/13 mW. (Contingent on 130 mA being real and on the kit actually drawing backlight through VSHA — two domains assert opposite things about that. Measure TP13.)

**(b) Five findings, one part, three answers.** PTC1 is the subject of `ptc1-lorho-1a5-swap` (→150SL, 11/16.6 mW), `ptc1-hold-current-below-load` (→150SL, 0 mW), `ptc1-lorho-075-to-150` (→150SL, 4.7/8.4 mW), `ptc1-hold-current-vs-overclock` (→150SL, 0 mW) and `ptc1-trip-margin-at-175x` (→**110**SL, 2/3 mW). Two different recommended parts; three different savings for the same swap; and a **direct doctrinal conflict on F1 coordination** — the thermal panel says 150SL's Itrip 3.00 A exceeds F1's 2 A rating and inverts the protection hierarchy, while the converter finding argues coordination is fine because F1's 5-second fusing current is 4.00 A. Both comparisons are legitimate against different F1 parameters and neither is resolved. Also unresolved: the fitted part's rerated hold current is quoted as **0.55 A @40 °C** (2025 Lo Rho revision) in one place and **0.62 A @40 °C** (2011 revision / DigiKey) in another, and R1max as 0.150 vs 0.160 Ω. Which revision applies decides whether the stock part is marginal or over.

**(c) Same milliwatts booked three times.** The VDD2 LDO→switcher swap appears as three findings (`vdd2-buckboost-from-vcc` 23.6/39.4, `u8-ldo-to-buck-from-vout3` 21.1/33.8, `clockxcontrol/vdd2-ldo-to-buck` 22/49). Only one correction says "do not sum." Same for F1: `f1-fuse-series-resistance` (4/6), `f1-redundant-lower-r` (1.7/3) and `f1-ptc1-thermal-relief` (0.03) all attack the same series resistance.

**(d) Two mutually exclusive VOUT3 trims.** `vout3-trim-to-3v30` (R55 → 1.02 M, 3.294 V, 1.2/3.5 mW) and `vout3-setpoint-lower` (R23 → 1.69 M, 3.228 V, 4.1/10.3 mW). Nobody flags that these are the same change done two ways. Worse, **neither notices they are anti-additive with the U8-buck proposals**: once U8 is a ~93 % buck, its input power is set by output power, so lowering VOUT3 saves essentially nothing on that branch and the trim's benefit collapses to the VAUD and VDD3 terms.

**(e) Four different VAUD currents.** Audio says 12.75 mA (panel-revised to ~7.7), linear-rails uses ~5 mA, clockxcontrol 5 mA, thermal 15–30 mA. Three separate findings independently "close" the 170 mW idle budget using incompatible values for the same rail.

**(f) Incompatible efficiency models for the same rail.** `power-led-and-series-resistor` refers its 4.04 mW VOUT5 saving to the battery at **80 %**, while `ltc3527-shared-burst-decision` argues that same channel runs fixed-frequency at **37–43 %** at ~1 mA. Both cannot be right. If the burst finding is right, most of ch1's loss is load-independent and the LED saving must be computed as the difference of two points on the fixed-frequency curve, not by dividing by 0.80. The end number happens to land near 5 mW either way (my recomputation: 4.7–6.5 mW), so the recommendation stands — but the method is wrong and the *direction* of the error is toward a larger saving.

**(g) VOUT3's load is missing a rail.** The converter domain's 150/212 mA VOUT3 figures do not itemise **VSHD** — the LCD's digital supply, which I verified runs VDD3 → U12 → `/CPU/VSHD` → FFC pins 2/7/27. The clockxcontrol domain added it; the converter domain, whose brownout finding depends on the total, did not. That omission (+20–40 mA) roughly cancels the Everdrive correction from §1, which is precisely why **nobody has a defensible VOUT3 number.**

## 7. What I would put a meter on, in priority order

1. **Current into TP16 (VOUT3) and TP13 (VOUT5)**, at min and max brightness, 1x and 1.75x, with the real screen kit and a genuine cart. This single measurement is the input to roughly fifteen findings — the channel split, converter-2 headroom, the burst-mode analysis, the VDD2-buck savings, the PTC margin. Every one of them currently rests on an estimate, and §6(a) shows one verdict *inverts* on it. Two minutes of work.
2. **DC drop across F1 and across PTC1 separately, four-wire, at a known ~500 mA, hot.** Resolves five findings and the 0.150-vs-0.160-vs-0.350 Ω and 0.55-vs-0.62 A contradictions at once, and tells you whether the input-path claims (2–33 mW) are real.
3. **VDD2 current at TP18**, 1x and 1.75x in a game. The three duplicate LDO findings scale at 0.70 mW per mA; the anchors used across the review span 25–82 mA, a 3x range.
4. **Does the screen work at 1.75x at all?** Before any of the above matters. Ratio-sweep the module with your actual kit and log the highest stable ratio; if it is 1.25x, re-run the whole power model there.
5. **VAUD current at TP22 with volume at zero**, before and after the U7→TLV9064 swap. Decides the largest claimed audio lever (12.3 vs 30.6 mW) and reconciles the four conflicting VAUD numbers.
6. **Internal temperature at PTC1** in a closed shell, max brightness, after 30 minutes. At 20 °C ambient the PPTC finding is a non-issue; at 40 °C it is marginal; at 60 °C it is over. Everything hinges on an unmeasured number.
7. **Scope CK1 at TP80** with the module fitted at 1.75x: peak overshoot vs VDD3+0.3 V, and the actual edge rate. Four findings inherit an assumed 2 ns edge, and one proposes a series-resistor land specifically to be able to fix what this measurement would reveal.
8. **Cell-terminal-to-BT1-pad drop** at a known current, and again after cleaning the cart-slot contacts. Both are zero-cost, unquantifiable from datasheets, and potentially larger than every component swap in the review.

## 8. The ledger nobody wrote

De-duplicated, drop-in only, no PCB or schematic change, at idle: U7→TLV9064 12.3 mW + DL1/R25 ~5 mW + R15/R16 latch 0.74 mW + supervisor dividers 0.19 mW + R65 0.28 mW + R11/R24 0.05 mW + one VOUT3 trim ~1.2 mW ≈ **20 mW off a 170 mW idle (12 %)**, plus 2–11 mW in use from PTC1. Everything larger requires a board spin. That total is the answer to the question the reviewer actually asked, and it appears nowhere in the eight domain reports.

**Sources:** [GBATEK LCD timing (mgba-emu fork)](https://deepwiki.com/mgba-emu/gbatek/2.3-gba-lcd-video-controller) · [GBATEK (problemkaputt.de)](https://problemkaputt.de/gbatek-lcd-dimensions-and-timings.htm) · [Energizer E91 datasheet](https://data.energizer.com/pdfs/e91.pdf) · LM4853 SNAS155E and LTC3527 35271fc read from the local captures at `/tmp/claude-0/.../scratchpad/LM4853.txt` and `ltc3527.txt` · insideGadgets ClockxControl product page from the local capture at `/tmp/claude-0/.../scratchpad/cxc.txt` · all netlist, footprint and schematic-annotation claims re-derived by me from `/tmp/claude-0/.../scratchpad/x/agbm-01-ram-desalvage/AGBM-01_AA_1-2_GBE-plus.kicad_pcb`, `AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb`, `agbm01/AGBM-01_AA_1-2.kicad_sch` and `agbm11/`.