# PCBWay assembly preparation — working notes

Goal: take this fork from a bare board to something PCBWay can deliver largely assembled, with only
the CPU, the cartridge connector, and the other consigned or oversized parts left to hand-solder.

**Status: the split is now derived from the board, not from this document. Not ready to
order — see §4.**

[`generated/`](generated/) holds the five buy documents, written by
[`scripts/bom_split.py`](../scripts/bom_split.py) from the board's own flags:

| | |
|---|---|
| `agbm-01-cxc-pcbway-assembly.csv` | **61 lines, 172 parts** — what PCBWay buys and places |
| `agbm-01-cxc-cpl.csv` | **172 placements** — the position file for those, and only those |
| `agbm-01-cxc-handbuy.csv` / `.md` | **8 lines** — what you buy and solder, each with its reason |
| `agbm-01-cxc-not-populated.csv` | **58 lines, 67 footprints** — DNP, fiducials, jumpers, test pads |

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
generated, not maintained** — `generated/agbm-01-cxc-handbuy.md` is the live version, and
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

### Three BOM defects that must be fixed before an order

- **Three Values are part numbers for the wrong thing.** All three are the same defect: the
  board's `Value` field names something a distributor will not ship, while the schematic's
  own Digi-Key link buys the right part. Consistency check [6] holds each pair and reports
  it until the board is corrected.
  - **`SW1`** says `CSS-1310B`; the orderable Nidec code is **`CSS-1310TB`**.
  - **`P3`** says `SJ-3524-SMT`; the Digi-Key API returns **no exact match** for it. The
    orderable CUI code is **`SJ-3524-SMT-TR`** (98,898 in stock, $0.89).
  - **`Q1`/`Q3`** say `2N3904`/`2N3906` — **TO-92 part numbers on SOT-23 pads.** There is no
    2N3904 in SOT-23; the SOT-23 parts are **`MMBT3904LT1G`**/**`MMBT3906LT1G`**, which is
    what the schematic links actually buy. The power review predicted this one and nobody
    had flagged it.
- **`D1`/`D2` are described as Schottky diodes and are not.** `1SS355VMTE-17` is a Rohm *standard*
  switching diode, 80 V, 100 mA. The review separately found `D1` is under-rated for the
  reverse-battery clamp duty the schematic assigns it.
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

## 5. Blocked on the board itself

Independent of sourcing, the board is not fabricable as committed. See
[`ECO-7`](../clockxcontrol-integration/ECO-7_u2_supply_and_dnp.md): `U2` pin 37 is the SRAM's only
`VCC` pin on the CY62157 and it has no path to `VDD2`, and `Net-(Q5B-G)` is severed at one deleted
via. Both need KiCad
rework and a re-pour. **No assembly order should be placed until that is closed.**

### And a third, found by the wiki audit: `U2`'s land goes the wrong way

MouseBiteLabs has **shipped** the CY62157EV30LL — on AGBM-02 and AGBM-12, documented on the wiki's
*Feature Configurations* and *Required Parts* pages. The AGBM-02 design-files archive committed in this repository
contains his land, and it is not ours. Both are 96-pad supersets of the stock salvage footprint at
the same origin `(88.0, −57.8)`, both keep the same pin ordering — but **he extended the pad field
toward −x and ECO-5 extended it toward +x**, putting our package body **1.55 mm further +x** than
the one he physically fitted in a shell:

| | added column | pad-row span | body centre |
|---|---|---|---|
| **AGBM-02** `AGB-SRAM_2` | x = **−8.45** | 19.42 mm | x = **+1.26** |
| **ours** (ECO-5) | x = **+12.31** | 19.00 mm | x = **+2.81** |

The obstruction Nick named was the front shell's plastic screen rim, and ECO-5's own README says
front-shell fit is **unverified**. His is the land with a physical fit behind it.

**But it cannot be adopted as a footprint swap onto this layout, and that was tested.** On
AGBM-01 the channel west of `U2`'s left pad column carries the entire RAM address-bus fanout — 37
F.Cu segments on `MA_1`…`MA_15`, `~WE_RAM`, `~LB`, `~UB`, GND. Placing his pad field there
**shorts 15 of the 24 new pads across 12 nets**. Nick could put the column there on AGBM-02
because he re-routed the fanout; ECO-5 went east because east was comparatively empty.

**The remedy is to rebase this fork onto AGBM-02**, which already carries the land, the straps and
the shell fit — and whose layout is byte-identical to AGBM-01 at 217 of 230 shared footprints.
That would also close both blockers above, since both are ECO-5's damage. Full comparison and the
cost of the rebase in [`wiki-audit/README.md`](../wiki-audit/README.md) §D and §D2. **Until that
decision is made, this board's `U2` land remains ECO-5's and its shell fit remains unverified.**

**Two manual steps no assembly line performs**, for whichever land ends up on the board — record
them in the build notes rather than expecting PCBWay to do them. Both apply *only* if you populate
a CY62157EV30LL, and both must be left open for a salvaged OEM chip:

* bridge **`JP2`** — ties `U2` pin 47 (`/BYTE`) to `VDD2` for ×16 word mode;
* solder-bridge **`U2` pins 16 to 17** — ties `MA17` to `VDD2`. Zero copper by design; verified
  adjacent on 0.5 mm pitch at `(−6.69, 1.75)` and `(−6.69, 2.25)`.

**Do not follow the wiki's `JP2`/`JP3` instruction literally on this board.** Nick's *Feature
Configurations* says to bridge `JP2` **and** `JP3` for a new RAM chip, because on AGBM-02 those are
the `MA17`→GND and `/BYTE`→`VDD2` straps. On this fork **`JP3` is ECO-6's ClockxControl clock
jumper** (`/CPU/CK1` ↔ `CXC_CLK`) and has nothing to do with the RAM. Bridging it is harmless — on
a module build it is the configuration you want — but it is not the RAM strap, and `MA17` is the
pin-16-to-17 bridge instead.

## 6. Still to do

1. ~~Resolve the remaining MPNs.~~ **Done — zero unresolved.** Re-run
   `python3 scripts/check_stock.py` before ordering to refresh stock and price; it needs
   `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` and `MOUSER_PART_API_KEY` in the
   environment.
2. Decide the two substitutions that are engineering calls, not sourcing ones: the 22 µF
   0805 line (DC-bias, above) and whether to apply the 10 µF `GRT` swap. The other three
   are mechanical.
3. Fix the remaining two BOM defects (`SW1`'s ordering code, the `D1`/`D2` Schottky
   mis-description) and the two footprint mismatches; add tantalum polarity marking. The
   `F1`/`PTC1` defect is closed by ECO-8.
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
