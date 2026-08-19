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

### Five lines are at zero, and every one now carries a verified alternate

Live figures, both distributors, 2026-08-19. Each `alternate` in
[`resolved-mpns.json`](resolved-mpns.json) records the substitute *and* what accepting it costs.

| Refs | Part | Digi-Key | Mouser | What to do |
|---|---|---|---|---|
| `C2 C12 C23 C37 C59 C60 C68` | Murata GRM188R61E106KA73J, 10 µF 25 V X5R 0603 | **0**, 17 wk | **0** | **`GRT188R61E106ME13D`** — same maker, same 25 V X5R 0603, GRT is Murata's soft-termination GRM. 192,278 in stock. Like-for-like. |
| `C1 C21 C42` | Murata GRM21BR61E226ME44L, 22 µF 25 V X5R 0805 | **0**, 17 wk | **0** | **No like-for-like exists** — see below. |
| `U11 U12 U18` | TI TPS22917DBVR | **0**, 16 wk | **0** | **`TPS22917DBVT`** — same die, different reel. 10,909 in stock. |
| `U14` | Microchip MIC1553YM5-TR | **0**, **24 wk** | **0** | Nothing substitutes it. Not on the critical path — see below. |
| `R26` | YAGEO RC0603FR-0733KL, 33 k | **0**, 17 wk | **95,136** | Buy it from Mouser. No decision needed. |

**`C1`/`C21`/`C42` is the one that needs a human.** Every 22 µF 25 V X5R 0805 from a tier-1
manufacturer is at zero — the part sits at the edge of what the case size supports, which is
why the whole class is scarce. The closest in-stock parts are `GRM21BR61C226ME44L` (same Murata
series at **16 V**, 95,529) and `GRM21BC81C226ME44K` (16 V X6S, 202,906). These three caps sit on
`/VFILT` (≤3.2 V), `VOUT5` (5.014 V) and `VOUT3` (3.228 V), so 16 V is 3.2× headroom on
*breakdown* — **the question is DC-bias capacitance, not breakdown.** A 16 V 0805 22 µF retains
materially less at 5 V bias than a 25 V one, so `C21`'s effective capacitance on `VOUT5` falls,
and the component review already flagged `C21`'s derating as mattering. Check the LTC3527's
output-ripple requirement against the substitute's bias curve before committing. Going to 1206
for a 25 V part is the other option and needs a footprint change.

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
4. Close the ECO-7 board defects and re-pour.
5. Generate the fab package: gerbers and drill. The BOM, the CPL and the DNP list now come
   out of `scripts/bom_split.py` — **but the CPL's rotation convention is unverified.** It
   emits the board's own `(at x y rot)` verbatim; PCBWay's expected zero-degree reference
   per package family has not been checked against a single part, and a wrong convention
   puts every polarised part in backwards. Verify before ordering, then record what was
   verified against.
6. Decide the four open questions: which variant is the target, consign the CPU/SRAM or fit them
   yourself, both sides or back only, and whether a ClockxControl build is the default.
