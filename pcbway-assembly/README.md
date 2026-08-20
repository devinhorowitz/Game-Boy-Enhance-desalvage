# PCBWay assembly preparation — working notes

Goal: take this fork from a bare board to something PCBWay can deliver largely assembled, with only
the CPU, the cartridge connector, and the other consigned or oversized parts left to hand-solder.

**Status: the split is now derived from the board, not from this document. Not ready to
order — see §4.**

[`generated/`](generated/) holds the five buy documents, written by
[`scripts/bom_split.py`](../scripts/bom_split.py) from the board's own flags:

| | |
|---|---|
| `agbm-02-cxc-pcbway-assembly.csv` | **61 lines, 172 parts** — what PCBWay buys and places |
| `agbm-02-cxc-cpl.csv` | **172 placements** — the position file for those, and only those |
| `agbm-02-cxc-handbuy.csv` / `.md` | **8 lines** — what you buy and solder, each with its reason |
| `agbm-02-cxc-not-populated.csv` | **58 lines, 67 footprints** — DNP, fiducials, jumpers, test pads |

**Do not edit them.** A part moves between the two buy lists by changing the *design* —
see [ECO-9](../clockxcontrol-integration/ECO-9_assembly_split.md) — and consistency check
[12] fails if the committed files are not what a fresh run produces.

---

## 1. The assembly split falls out well

197 real parts, **84 on F.Cu and 113 on B.Cu**, so this is a double-sided job either way. But the
split is favourable:

- **The back carries all the fine-pitch work** — `U5` (QFN-16), `U6` (MSOP-10), `U7` (TSSOP-14),
  six SOT-23/TSOT-23 parts, both inductors, both common-mode chokes. That is the part a human
  least wants to do, and it is exactly what a pick-and-place is for.
- **The front carries the consigned parts** — the salvaged `U1` CPU and `U2` SRAM, the cartridge
  slot, the link port, the battery contacts, the speaker, and the ClockxControl window.

Only **8 parts have any through-hole pad**: `BT1`, `P1` (36 pins), `P3`, `P4`, `SP1`, `SW2`, `SW3`,
`VR2`.

**MouseBiteLabs already marks 49 footprints DNP** in stock AGBM-01, and the set is telling: `BT1`,
`SW2`–`SW6`, every test point, the logos, `JP1`, `NT1`, `Z57`/`Z58`, `C70`/`C71`, `R70`/`R71`. The
mechanical and consigned parts are already flagged "do not place." ECO-7 adds `X1`, `C3` and `C4`
for ClockxControl builds, bringing it to 52.

## 2. Consigned / hand-solder set

**As of [ECO-9](../clockxcontrol-integration/ECO-9_assembly_split.md) this table is
generated, not maintained** — `generated/agbm-02-cxc-handbuy.md` is the live version, and
the board's own `exclude_from_bom` flag is what puts a part on it. The prose below is kept
because it records *why* each one was picked, and because it was the source the ECO-9 rule
was checked against.

Six schematic `Source` fields are not Digi-Key links, and they map almost exactly onto the parts a
human has to fit:

| Refs | Part | Why |
|---|---|---|
| `U1`, `U2` | Source field reads literally **"Salvage"** | donor CPU and SRAM |
| `P1` | cartridge slot | aftermarket, 36 through-hole pins |
| `P4` | link port | aftermarket |
| `SP1` | speaker | aftermarket |
| `BT1` | battery contacts | retro-parts shop |
| `SW2`, `SW3` | L/R triggers, TE 1825027-5 | a real TE part, likely orderable |
| `MOD1` | ClockxControl | insideGadgets module, `exclude_from_bom` in ECO-6 |

`P2`, `P3`, `VR1`, `VR2`, `SW1` and `SW4`–`SW6` all have Digi-Key links, so they are orderable even
though several are mechanical.

**The derived set differs from this table in two places, and both are corrections.** `P3`
and `VR2` are on the hand-buy list — they have through-hole pads, which no reflow line
does, whatever their sourcing looks like. And `MOD1` was already `exclude_from_bom` but
**still in the position file**: a part the assembler had never been sold, queued for a
nozzle. The splitter found that one; a human table could not have.

## 3. BOM resolution

The repository has **no MPN BOM**. The schematic carries a `Source` property on 194 of 235 symbols,
but they are **Digi-Key short-links**, not part numbers: 68 unique links, 62 of them Digi-Key. The
41 symbols with no source are test points plus `JP1`/`NT1`, so there is nothing to buy.

`curl` gets **HTTP 403** from Digi-Key (their bot protection, not the egress proxy, which reports no
relay failures). WebFetch resolves them.

**Resolved: 174 of 180 buyable reference designators. The other six have no distributor part
by decision** — `U1`/`U2` are salvage and `P1`/`P4`/`SP1`/`MOD1` are aftermarket. **Zero
unresolved.**

[`resolved-mpns.json`](resolved-mpns.json) is **generated** by
[`scripts/check_stock.py`](../scripts/check_stock.py) from three inputs:

| | |
|---|---|
| [`scripts/mpn_overrides.json`](../scripts/mpn_overrides.json) | hand-maintained decisions, each with a reason. An override beats a schematic link — which is how ECO-8's swaps survive the fact that the upstream schematic still points at the parts they replaced. |
| [`scripts/link_mpn.json`](../scripts/link_mpn.json) | the upstream schematic's own 34 per-symbol Digi-Key short-links, resolved to MPNs once and frozen. For a generic value like `1u` or `100k` this is the **only** record of which part MouseBiteLabs picked. |
| the Digi-Key and Mouser APIs | everything volatile: lifecycle status, stock, unit price, the distributor's own part number. |

**Frozen data and live data rot differently**, which is why they are separate. A short-link's
MPN does not change; stock changes hourly. A distributor that could not be reached leaves its
block marked `UNKNOWN`, never zero — that distinction is load-bearing, and it caught a real
case on the first live run where a rate-limited Mouser query would otherwise have reported a
resistor as unstocked while Mouser had 95,136 of them.

**One board's 172 machine-placed parts cost about $54 at Digi-Key qty-1 pricing.**

## 4. What the resolution turned up, and why this is not ready to order

### Two lines were swapped; three remain at zero, each with a verified alternate

Live figures, both distributors, 2026-08-19. Each `alternate` in
[`resolved-mpns.json`](resolved-mpns.json) records the substitute *and* what accepting it costs.

| Refs | Part | Digi-Key | Mouser | What to do |
|---|---|---|---|---|
| `C2 C12 C23 C37 C59 C60 C68` | ~~GRM188R61E106KA73J~~ → **Murata `GRT188R61E106ME13D`** | **192,299** | 0 | ✅ **Swapped.** See below. |
| `C1 C21 C42` | ~~GRM21BR61E226ME44L~~ → **Murata `GRT21BR61E226ME13L`** | **2,022** | 0 | ✅ **Swapped.** Exact match at 25 V — see below. |
| `U11 U12 U18` | TI TPS22917DBVR | **0**, 16 wk | **0** | **`TPS22917DBVT`** — same die, different reel. 10,909 in stock. |
| `U14` | Microchip MIC1553YM5-TR | **0**, **24 wk** | **0** | Nothing substitutes it. Not on the critical path — see below. |
| `R26` | YAGEO RC0603FR-0733KL, 33 k | **0**, 17 wk | **95,136** | Buy it from Mouser. No decision needed. |

**The 10 µF swap, and why it is safe.** Verified parameter by parameter against the incumbent
on the Digi-Key API — **capacitance 10 µF, rated voltage 25 V, dielectric X5R, package 0603
(1608), max thickness 1.00 mm and operating range −55 to +85 °C are all identical.** Two
differences, both neutral or better: tolerance loosens ±10 % → ±20 %, immaterial on bulk
decoupling and dwarfed by DC-bias derating anyway; and the GRT is Murata's soft-termination
series and is **AEC-Q200 automotive-qualified**, which the GRM is not.

Holding the *voltage* and giving up the *tolerance* is the right way round: rated voltage
drives DC-bias derating far harder than the tolerance band does, and DC-bias is the property
the component review said to protect. The seven placements sit on `VOUT3` (3.228 V), `VCC`
(≤3.2 V), `VAUD` and `VDD2` (2.5 V), `U17`'s supply and `/D1A`.

**One thing to know: the fitted GRT part is single-sourced.** Digi-Key has 192,299; Mouser has
zero. If depth and a second source matter more to you than the 25 V rating,
`GRT188R61C106KE13D` is 10 µF ±10 % **16 V** X5R 0603 with **764,592 at Digi-Key and 456,339 at
Mouser** — it also restores the incumbent's ±10 %. The cost is exactly the thing this swap was
chosen to protect: 16 V in the same case means noticeably more capacitance lost to DC bias.
Breakdown is not the issue either way — the highest of these seven rails is 3.23 V.

This is a **BOM-only change**: the board `Value` stays `10u` and no board file moved, so unlike
ECO-8's Value edits it cannot be reverted by a PCB-from-schematic sync. **But the schematic's
own `Source` link for these seven still points at the GRM**, so update it there too before
anyone regenerates a BOM from the schematic.

**The 22 µF swap, and a correction.** This section previously said *"no like-for-like exists —
every 22 µF 25 V X5R 0805 from a tier-1 manufacturer is at zero"* and recommended dropping to a
**16 V** part. **That was wrong.** It came from a keyword search that filtered on stock ≥ 5,000,
which silently excluded every real 25 V candidate — all of which sit in the hundreds to low
thousands. A threshold chosen to shorten a search result had turned into a claim about the
market. A deeper sweep — 1,297 results across 15 query shapes with no stock floor, plus an
independent Mouser keyword sweep — found three.

`GRT21BR61E226ME13L` is the same GRM→GRT move already made on the 10 µF line, and it gives up
**nothing**. Verified parameter by parameter against the incumbent:

| | GRM (was) | GRT (now) |
|---|---|---|
| Capacitance / tolerance | 22 µF ±20 % | 22 µF ±20 % |
| **Rated voltage** | **25 V** | **25 V** |
| Dielectric | X5R | X5R |
| Package / max thickness | 0805, 1.45 mm | 0805, 1.45 mm |
| Operating range | −55…+85 °C | −55…+85 °C |
| Qualification | — | **AEC-Q200** |
| Stock | **0** | **2,022** |

2,022 is 674 boards at three per board. Mouser has none, so **this line is single-sourced.**

**If you want depth:** `GRM21BC81E226ME44K` — Murata, 25 V, 0805, same 1.45 mm, **7,338 in
stock** (3.6×) and a wider −55…+105 °C range. The catch is that it is **X6S, a different
dielectric formulation**, and DC-bias is exactly what holding 25 V was meant to protect. I could
not verify its bias curve: Murata publishes that only through SimSurfing, whose API returns
HTTP 500 from here, and the product PDFs do not carry the curve. So the conservative pick is the
one that changes nothing. With SimSurfing access, compare the two at 5 V bias — the extra stock
is real.

**Checked and rejected:** `ZRA21CR61E226ME01L` (Murata, 25 V X5R, 5,330) looks ideal in a Mouser
listing, but Digi-Key's parameters give its package as *Nonstandard SMD* at **1.65 mm** thick,
not 0805/1.45 mm. Not a drop-in. `KGM21AR51E226MU` (Kyocera AVX, 612 + 5 at Mouser, $1.06,
28-week lead) is a genuine second source if both Murata parts dry up.

The 16 V part is **no longer recommended** now that 25 V is in stock.

**`U14` is the longest lead on the board at 24 weeks, and it does not block a first build.** The
MIC1553 drives the low-battery LED blink — which is already dead for an unrelated reason, the
`Net-(Q5B-G)` break in [ECO-7](../clockxcontrol-integration/ECO-7_u2_supply_and_dnp.md).

`U5` (ADI LTC3527EUD#PBF) is no longer on this list — it is in stock — but it remains the most
expensive active on the board, which strengthens the review's Tier-2 case for the TPS63802
transplant on cost as well as efficiency.

### ~~Three BOM defects that must be fixed before an order~~ — withdrawn, they were not defects

**This section used to say `SW1`, `P3` and `Q1`/`Q3` were BOM defects that had to be fixed
before an order. That was wrong, and [ECO-15](../clockxcontrol-integration/ECO-15_upstream_link_sync.md)
withdraws it.** In KiCad the `Value` field is a **symbol name**; the orderable code lives in
the per-symbol `Source` link, which is exactly where MouseBiteLabs put it. Nothing was ever
going to be mis-ordered — the BOM buys the link's part in every case:

| Ref | Board `Value` (a symbol name) | MouseBiteLabs' own `Source` link | What the BOM buys |
|---|---|---|---|
| `SW1` | `CSS-1310B` | `CSS-1310TB` | `CSS-1310TB` ✔ |
| `P3` | `SJ-3524-SMT` | `SJ-3524-SMT-TR` | `SJ-3524-SMT-TR` ✔ |
| `Q1` | `2N3904` | `MMBT3904LT1G` | `MMBT3904LT1G` ✔ |
| `Q3` | `2N3906` | `MMBT3906LT1G` | `MMBT3906LT1G` ✔ |

There is no 2N3904 in SOT-23, so a reader is still better off knowing the Value is generic —
which is why check [6] keeps naming these three. It no longer calls them defects.

The reason this fork believed it had found something is worth recording: `scripts/link_mpn.json`
was built from **AGBM-01** and survived the ECO-13 rebase untouched, so 30 of AGBM-02's 57
`Source` links had never been read — including the ones for `SW1`, `P3` and `D1`/`D2`. The fork
was rediscovering answers it had simply not looked up. Check **[16]** now fails if any link in
the base schematic is unresolved.

- **`D1`/`D2` are described as Schottky diodes and are not.** This one stands, and is now
  sourced rather than asserted: MouseBiteLabs' own link for `D1`/`D2` goes to a part Digi-Key
  itself categorises **"DIODE STANDARD 80V 100MA UMD2"**. `1SS355VMTE-17` is a Rohm *standard*
  switching diode. The part he bought is fine; the schematic's *Description* field is what is
  wrong. The review separately found `D1` is under-rated for the reverse-battery clamp duty the
  schematic assigns it.

### Three lines this fork had made unbuyable — fixed by ECO-15

Reading MouseBiteLabs' links turned up the opposite problem from the one above: three buy lines
where **this fork had substituted a part he never chose, and landed on one with no stock.**

| Refs | This fork bought | Stock | MouseBiteLabs' link | Stock | Now |
|---|---|---|---|---|---|
| `CP1`–`CP3` | `TPSB107K010R0400` (±10%) | **5** | `TPSB107M010R0400` (±20%) | 31,360 | his |
| `C1`/`C21`/`C42`/`C58` | `GRT21BR61E226ME13L` (25 V) | **0** | `GRT21BR61C226ME13K` (16 V) | 8,228 | his |
| `R26` | `RC0603FR-0733KL` | **0** | `RC0603FR-1033KL` | 25,665 | his |

Nothing recorded why any of the three differed. The 22 µF line is the instructive one: it had
already been swapped once *because the incumbent was at zero stock*, and the replacement was at
zero too — both 25 V parts in that family are. Taking his 16 V part costs some DC-bias headroom,
which ECO-15 records as a deliberate trade and a thing to scope on the first build.
- ~~**`F1` and `PTC1` disagree across three places.**~~ **Fixed by
  [ECO-8](../clockxcontrol-integration/ECO-8_component_swaps.md).** The schematic said
  `F0805B2R00FSTR` (KYOCERA AVX 2 A fuse, 0.08 Ω) and `0805L075SLYR` (Littelfuse PPTC); both PCB
  footprints carried the stale Value `0467001.NR` — a Littelfuse 467-series *0603 1 A* fuse — and
  both Description fields said `0805L050WR`, a third part again. A BOM generated from the layout
  would have ordered two wrong parts and deleted the resettable protection entirely. The PCB now
  reads `F0805B2R00FSTR` and `0805L110SLYR`, with accurate Descriptions.

### Two possible footprint / package mismatches

Both need checking against the manufacturer's recommended land pattern before any order:

- **`L1`/`L2`**: the specified part is a Taiyo Yuden **LSXND3030QKT4R7MNG, 3.00 × 3.00 × 1.50 mm**,
  but the footprint is named `L_Taiyo-Yuden_NR-20xx_HandSoldering` — the NR-20xx family is
  2.0 × 2.0 mm. The land measures 4.00 × 2.00 mm overall with 1.65 × 2.00 mm pads.
- **`CP1`/`CP2`/`CP3`**: the specified part is a KYOCERA AVX **TPSB107K010R0400**, a
  **1411/3528-metric molded tantalum, 3.50 × 2.80 × 2.10 mm**, on a footprint named
  `C_1210_3225Metric_Boxed_2` (3.2 × 2.5 mm). The land measures 4.10 × 2.70 mm.

### One thing that will go wrong on a machine line if nobody catches it

`CP1`, `CP2` and `CP3` are **polarized tantalums on a symmetric land pattern with no polarity
marking anywhere on the board**. A human soldering them reads the part's own stripe. A pick-and-place
reads the CPL rotation, and if that rotation is wrong all three go in backwards. The review
separately found `CP1` carries bidirectional AC with no DC bias, which reverse-biases it past the
manufacturer's own 1 V limit regardless of orientation.

**Add polarity silkscreen before ordering assembly.**

## 5. The board-level blockers are closed

**[ECO-13](../clockxcontrol-integration/ECO-13_rebase_onto_agbm02.md) rebased this fork
onto MouseBiteLabs' AGBM-02.** Both defects that made the previous board un-fabricable were
ECO-5's own damage, and both closed with it:

| Was | Now |
|---|---|
| `U2` pin 37 — the SRAM's only `VCC` on a CY62157 — had no path to `VDD2` | **closed.** Pin 37 lands on a stock column that already carries `VDD2`; both vias ECO-5 deleted are present. |
| `Net-(Q5B-G)` severed at one deleted via, leaving the low-battery LED dead | **closed.** Whole on AGBM-02, one island, and whole on the base too. |
| `U2`'s land extended 1.55 mm further into the front-shell rim than the placement Nick fitted | **closed.** The board carries **his** `Bucketmouse:AGB-SRAM_2`, with the shell fit he verified. |

Consistency check [10] now asserts all of that and goes red if any of it regresses.

### What is still open before an order

1. **Run DRC in KiCad, and re-pour.** The ECO-6 copper is generated from
   `scripts/routes.json`, not laid out interactively, and has never been through DRC. The
   zone fill is still MouseBiteLabs' stock fill.
2. **Verify the ClockxControl landing geometry against a physical module** — it is
   photo-derived, and it is now the largest unverified thing in the package.
3. **Verify the CPL rotation convention** against PCBWay's per-package zero reference. A
   wrong convention puts every polarised part in backwards.

### Two hand steps the machine will not do

Both concern `U2`, and both are MouseBiteLabs' jumpers with his numbering — see his
*Feature Configurations* wiki page. **Only if you populate the CY62157EV30LL**; leave both
**open** for a salvaged OEM AGB-SRAM, which the land still accepts:

* bridge **`JP2`** — ties `U2` pin 17 (`MA17`) to GND
* bridge **`JP3`** — ties `U2` pin 47 (`/BYTE`) to `VDD2` for ×16 word mode

**Our ClockxControl clock jumper is `JP4`**, not `JP3`. It was `JP3` on the AGBM-01 base,
where nothing else claimed the name; on AGBM-02 that collided with his `/BYTE` strap, so
ECO-13 renamed ours. His instructions now read correctly against this board.

### One build decision the board deliberately leaves to you

`Z57`/`Z58` carry the Value **`100p or 0 ohm`** — MouseBiteLabs states the choice in the
field rather than picking for you. Capacitors make the `L+R+Start+A/B` hotkeys fake a screen
kit's touch input; resistors or jumpers make them plain button inputs for an external mod.
**The generated BOM buys the capacitor.** If you want button inputs, change it before
ordering. His own note is worth reading first — of three units he built, only one could
reliably fake the touch input.

## 6. Still to do

1. ~~Resolve the remaining MPNs.~~ **Done — zero unresolved.** Re-run
   `python3 scripts/check_stock.py` before ordering to refresh stock and price; it needs
   `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` and `MOUSER_PART_API_KEY` in the
   environment.
2. Decide the two substitutions that are engineering calls, not sourcing ones: the 22 µF
   0805 line (DC-bias, above) and whether to apply the 10 µF `GRT` swap. The other three
   are mechanical. **Both of those are now settled by ECO-15, and not the way this list
   assumed:** the 10 µF `GRT` "swap" is not a swap at all — MouseBiteLabs' own link already
   buys `GRT188R61E106ME13D`, so there is nothing to apply. And the 22 µF line went the
   other way: no 25 V part in that family is in stock anywhere, so it returns to his 16 V
   `GRT21BR61C226ME13K`.
3. Correct the `D1`/`D2` *Description* field, which calls a standard switching diode a
   Schottky, and fix the two footprint mismatches; add tantalum polarity marking. `SW1`'s
   "ordering code defect" was withdrawn by ECO-15 — it was never one. The `F1`/`PTC1`
   defect is closed by ECO-8.
3b. **`U11`/`U12`/`U18` (`TPS22917DBVR`) and `U14` (`MIC1553YM5-TR`) read ZERO stock at both
   distributors** as of 2026-08-20, and both are MouseBiteLabs' own parts, not fork
   substitutions — so this is an availability problem in the base design, not a defect to
   fix here. No stocked drop-in was found for either. Re-check before ordering; check [6]
   warns while they stay dry.
4. Settle the base-board question in §5 first — rebasing onto AGBM-02 deletes ECO-5 and both
   ECO-7 defects outright, so closing them by hand on AGBM-01 may be work spent on a board
   that is about to be replaced. If AGBM-01 is kept, close both defects and re-pour.
5. Generate the fab package: gerbers and drill. The BOM, the CPL and the DNP list now come
   out of `scripts/bom_split.py` — **but the CPL's rotation convention is unverified.** It
   emits the board's own `(at x y rot)` verbatim; PCBWay's expected zero-degree reference
   per package family has not been checked against a single part, and a wrong convention
   puts every polarised part in backwards. Verify before ordering, then record what was
   verified against.
6. Decide the four open questions: which variant is the target, consign the CPU/SRAM or fit them
   yourself, both sides or back only, and whether a ClockxControl build is the default.
