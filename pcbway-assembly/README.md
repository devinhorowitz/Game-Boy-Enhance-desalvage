# PCBWay assembly preparation — working notes

Goal: take this fork from a bare board to something PCBWay can deliver largely assembled, with only
the CPU, the cartridge connector, and the other consigned or oversized parts left to hand-solder.

**Status: scoping and BOM resolution. Not ready to order — see §4.**

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

## 3. BOM resolution

The repository has **no MPN BOM**. The schematic carries a `Source` property on 194 of 235 symbols,
but they are **Digi-Key short-links**, not part numbers: 68 unique links, 62 of them Digi-Key. The
41 symbols with no source are test points plus `JP1`/`NT1`, so there is nothing to buy.

`curl` gets **HTTP 403** from Digi-Key (their bot protection, not the egress proxy, which reports no
relay failures). WebFetch resolves them.

**29 lines resolved so far, covering 65 reference designators** —
[`resolved-mpns.json`](resolved-mpns.json). Priority went to the actives, the disputed parts, and
anything the component review flagged. The ~35 unresolved links are almost all generic 0603
resistor and capacitor values, which are trivially substitutable and carry no sourcing risk; they
still need resolving before an order, but they are not where the problems are.

Every part [ECO-8](../clockxcontrol-integration/ECO-8_component_swaps.md) introduces is in that file
with its datasheet numbers, its Digi-Key stock as of 2026-08-18, and a note saying what it replaced
and why. All of them are 0603/0805/TSSOP-14 drop-ins on lands that are already on the board.

## 4. What the resolution turned up, and why this is not ready to order

### Five lines have real availability problems

| Refs | Part | Problem |
|---|---|---|
| `C2 C12 C23 C37 C59 C60 C68` | Murata GRM188R61E106KA73J 10 µF 0603 | **out of stock**, 10,000 due 28 Dec 2026 |
| `C1 C21 C42` | Murata GRM21BR61E226ME44L 22 µF 0805 | **out of stock**, 17-week lead |
| `U11 U12 U18` | TI TPS22917DBVR | **out of stock**, due 6 Oct 2026 (`DBVT` is the same part on another reel, 10,916 in stock) |
| `U14` | Microchip MIC1553YM5-TR | **0 in stock**, 3,000 due 14 Sep 2026 |
| `U5` | ADI LTC3527EUD#PBF | **$8.78 qty 1**, only 119 in stock |

The two capacitor lines are the serious ones: ten placements between them, both bulk decoupling.
Equivalents in the same case size and dielectric are easy, but they have to be chosen deliberately
rather than left to a substitution desk, because the component review found `C21`'s DC-bias
derating already matters on the 5 V rail.

The `U5` line is worth noting against the review's Tier-2 recommendation: at $8.78 and 119 in stock,
the LTC3527 is both the most expensive active on the board and the thinnest supply. The TPS63802
transplant is cheaper *and* better sourced, which strengthens a case that was already made on
efficiency.

### Three BOM defects that must be fixed before an order

- **`SW1`'s value is not an orderable part number.** The schematic says `CSS-1310B`; the real Nidec
  ordering code is **`CSS-1310TB`** (SP3T, SMD right-angle, 17,509 in stock).
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

1. Resolve the remaining ~41 Digi-Key short-links to MPNs.
2. Choose in-stock equivalents for the five problem lines, deliberately, with the review's derating
   findings in hand.
3. Fix the remaining two BOM defects (`SW1`'s ordering code, the `D1`/`D2` Schottky
   mis-description) and the two footprint mismatches; add tantalum polarity marking. The
   `F1`/`PTC1` defect is closed by ECO-8.
4. Close the ECO-7 board defects and re-pour.
5. Generate the fab and assembly package: gerbers, drill, **CPL/centroid for both sides with the
   rotation convention PCBWay expects**, the BOM in PCBWay's format, and a fab/assembly note sheet
   naming the DNP set and the consigned set.
6. Decide the four open questions: which variant is the target, consign the CPU/SRAM or fit them
   yourself, both sides or back only, and whether a ClockxControl build is the default.
