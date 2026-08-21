# PCBWay assembly preparation

Goal: take this fork from a bare board to something PCBWay can deliver largely assembled, with only
the CPU, the cartridge connector, and the other consigned or oversized parts left to hand-solder.

**Status: the split is derived from the board, not from this document. Not ready to order — see §3.**

[`generated/`](generated/) holds the five buy documents, written by
[`scripts/bom_split.py`](../scripts/bom_split.py) from the board's own flags:

| | |
|---|---|
| `agbm-02-cxc-pcbway-assembly.csv` | what PCBWay buys and places |
| `agbm-02-cxc-cpl.csv` | the position file for those parts, and only those |
| `agbm-02-cxc-handbuy.csv` / `.md` | what you buy and solder, each with its reason |
| `agbm-02-cxc-not-populated.csv` | DNP, fiducials, jumpers, test pads |

**Do not edit them.** A part moves between the two buy lists by changing the *design* — the board's
own `exclude_from_bom` and `dnp` flags decide — and consistency check [12] fails if the committed
files are not what a fresh run produces. The counts live in those files rather than in this prose,
so they cannot go stale here.

---

## 1. The assembly split

The board is double-sided either way, but the split is favourable:

- **The back carries all the fine-pitch work** — `U5` (QFN-16), `U6` (MSOP-10), `U7` (TSSOP-14),
  six SOT-23/TSOT-23 parts, both inductors, both common-mode chokes. That is the part a human least
  wants to do, and it is exactly what a pick-and-place is for.
- **The front carries the consigned parts** — the salvaged `U1` CPU and `U2` SRAM, the cartridge
  slot, the link port, the battery contacts, the speaker, and the ClockxControl window.

Only **8 parts have any through-hole pad**: `BT1`, `P1` (36 pins), `P3`, `P4`, `SP1`, `SW2`, `SW3`,
`VR2`.

**MouseBiteLabs already marks 49 footprints DNP** in stock AGBM, and the set is telling: `BT1`,
`SW2`–`SW6`, every test point, the logos, `JP1`, `NT1`, `Z57`/`Z58`, `C70`/`C71`, `R70`/`R71`. The
mechanical and consigned parts are already flagged "do not place." This fork adds `X1`, `C3` and
`C4` for ClockxControl builds.

### Why each part is on the hand list

`generated/agbm-02-cxc-handbuy.md` is the live version. The reasoning behind it:

| Refs | Part | Why |
|---|---|---|
| `U1` | schematic `Source` reads literally **"Salvage"** | donor CPU — the only chip a build takes off a donor console |
| `P1` | cartridge slot | aftermarket, 36 through-hole pins |
| `P4` | link port | aftermarket |
| `SP1` | speaker | aftermarket |
| `BT1` | battery contacts | retro-parts shop |
| `SW2`, `SW3` | L/R triggers, TE 1825027-5 | a real TE part, likely orderable |
| `MOD1` | ClockxControl | insideGadgets module, `exclude_from_bom` |
| `P3`, `VR2` | headphone jack, trim pot | through-hole pads, which no reflow line does |

`MOD1` was `exclude_from_bom` but **still in the position file** — a part the assembler had never
been sold, queued for a nozzle. The splitter found that; a hand-maintained table could not have.

**`U2` is not on this list, and that is the point of the fork.** On MouseBiteLabs' older AGBM-01
the SRAM was a second salvaged chip. AGBM-02 carries his own dual land, so `U2` is an ordinary
orderable part — Infineon `CY62157EV30LL-45ZXIT` — that the machine buys and places. **A build
needs exactly one chip off a donor console: the CPU.** His own Required Parts page says so: *"For
the AGBM-02 and AGBM-12, you only need the CPU."*

**`P1` and `P4` are on no buy list at all.** The cartridge slot and the link port are DNP on his
board — that is how he marks the aftermarket parts a builder sources — so they are excluded from
the assembly BOM *and* from the hand-buy list, and appear only in
[`generated/agbm-02-cxc-not-populated.csv`](generated/agbm-02-cxc-not-populated.csv). **Read that
file before ordering.** It is not all jumpers and test pads.

## 2. BOM resolution

The repository has **no MPN BOM**. The schematic carries a `Source` property on most symbols, but
they are **Digi-Key short-links, not part numbers**. The symbols with no source are test points plus
`JP1`/`NT1`, so there is nothing to buy.

`curl` gets **HTTP 403** from Digi-Key (their bot protection, not the egress proxy). WebFetch
resolves them.

**Zero unresolved.** Six reference designators have no distributor part by decision — `U1`/`U2` are
salvage and `P1`/`P4`/`SP1`/`MOD1` are aftermarket.

[`resolved-mpns.json`](resolved-mpns.json) is **generated** by
[`scripts/check_stock.py`](../scripts/check_stock.py) from three inputs:

| | |
|---|---|
| [`scripts/mpn_overrides.json`](../scripts/mpn_overrides.json) | hand-maintained decisions, each with a reason. An override beats a schematic link — which is how this fork's swaps survive an upstream schematic that still points at the parts they replaced. |
| [`scripts/link_mpn.json`](../scripts/link_mpn.json) | the upstream schematic's own per-symbol Digi-Key short-links, resolved to MPNs once and frozen. For a generic value like `1u` or `100k` this is the **only** record of which part MouseBiteLabs picked. |
| the Digi-Key and Mouser APIs | everything volatile: lifecycle status, stock, unit price, the distributor's own part number. |

**Frozen data and live data rot differently**, which is why they are separate. A short-link's MPN
does not change; stock changes hourly. A distributor that could not be reached leaves its block
marked `UNKNOWN`, never zero — that distinction is load-bearing, and it caught a real case where a
rate-limited Mouser query would otherwise have reported a resistor as unstocked while Mouser had
95,136 of them.

**One board's machine-placed parts cost about $54 at Digi-Key qty-1 pricing.**

### Eleven lines are this fork's choice, and reverting one has a price

These are the lines `mpn_overrides.json` sets against MouseBiteLabs' own schematic. **If a
distributor is dry and you are tempted to fall back to his part, this is what that costs.**
Savings are at the battery, at three operating points; the ClockxControl draws ~12 mA whether
or not you overclock, so fitting it costs about 45 mW before it speeds anything up, and these
are the other side of that ledger.

| Ref | His part → this fork's | idle | in use, stock | 1.75× | what you give up by reverting |
|---|---|---|---|---|---|
| `U7` | TLV9364 → **TLV9064IPWR** | 12.0 mW | 12.0 | 12.0 | **not just efficiency — his part is specified 4.5 V to 40 V and sits on the 2.5 V `VAUD` rail, below its own minimum** |
| `DL1` + `R25` | AlInGaP + 3.3 k → **InGaN + 22 k** | 4.6 | 4.6 | 4.6 | 4.66 → 0.62 mW at `VOUT5` for the same visible brightness |
| `PTC1` | 0805L075SLYR → **0805L110SLYR** | 0.1 | 2.2 | 3.2 | **hold-current margin.** His part derates to 0.55 A at 40 °C, under the realistic worst case |
| `R15` + `R16` | 10 k → **100 k** | 0.74 | 0.74 | 0.73 | brownout-latch bias, and `R16` also sets the clamp current for `Q10A` |
| `R65` | 100 k → **470 k** | 0.25 | 0.25 | 0.25 | quiescent bias only |
| `R11` + `R24` | 1 k → 10 k, 100 k → **1 M** | 0.05 | 0.05 | 0.05 | quiescent bias only |
| **Total** | | **21.8 mW** | **25.9 mW** | **29.0 mW** |  |

`Q9`/`Q10` (NDC7002N → **FDC6301N**) are on the list too and save nothing — they are a
correctness fix. The NDC7002N's worst-case gate threshold is *above* the drive those two
actually get, so a worst-case part leaves the brownout latch unarmed and the low-battery LED
dark, invisibly, because the console works normally until the protection was meant to act.
**Do not substitute those two back.** `Q2`, `Q5` and `Q7` keep the NDC7002N deliberately.

Separately, and not a running saving: the post-brownout latched-off drain falls **6.90 mW →
0.98 mW**, a 7.1× cut in what a flat pack loses while the console sits switched on but latched
off.

Two of the twelve refs are Description-only corrections and change nothing you order: `F1` and
`PTC1` both shipped a legacy `0805L050WR` string that names neither part.

**Provenance.** Every figure is *modelled*, referred to the battery, and anchored on
MouseBiteLabs' own published measurements — 170 mW idle, 792 mW representative use, 951 mW
with the module at 1.75×, 2.4 V pack. **Nothing was measured on a built board of this fork**,
because none exists. Full derivation in
[`../clockxcontrol-integration/DESIGN-DECISIONS.md`](../clockxcontrol-integration/DESIGN-DECISIONS.md) §7.

---

## 3. What is not ready to order

Live figures, both distributors, **re-queried 2026-08-20**. Every part named below is the one
`resolved-mpns.json` actually buys, and its `alternate` there records the substitute *and* what
accepting it costs. Stock moves hourly — re-run `scripts/check_stock.py` before ordering.

| Refs | Part the BOM buys | Digi-Key | Mouser | What to do |
|---|---|---|---|---|
| `C2 C12 C23 C37 C57 C59 C60 C68` | Murata `GRT188R61E106ME13D`, 10 µF 25 V | **166,367** | 0 | ✅ In stock, single-sourced. |
| `C1 C21 C42 C58` | YAGEO `CC0805MKX5R8BB226`, 22 µF **25 V** 0805 | **≈130,000** | 0 | ✅ In stock, single-sourced. |
| `U11 U12 U18` | TI `TPS22917DBVR` | **0**, 16 wk | **0** | **`TPS22917DBVT`** — same die, smaller reel. **10,879** at Digi-Key, **1,973** at Mouser. |
| `U14` | Microchip `MIC1553YM5-TR` | **0**, **24 wk** | **0** | Nothing substitutes it, and it **is** on the critical path. |
| `R26` | YAGEO `RC0603FR-1033KL`, 33 k | **25,665** | **404,500** | ✅ Nothing to do. |

Check [6] warns while either zero-stock line stays dry. Both are **MouseBiteLabs' own parts, not
fork substitutions** — an availability problem in the base design, not a defect to fix here. They
are not the same problem: `TPS22917DBVT` is a reel change at order time, no decision. `U14` has no
equivalent at all and a 24-week lead.

### `U14` has no substitute, and that was checked rather than assumed

The MIC1553 drives the low-battery LED blink. `MIC1553YM5` without the `-TR` reel suffix **is not an
orderable part** at either distributor, so there is no packaging escape. The family siblings are in
stock — `MIC1555YM5-TR` (Digi-Key 17,066 / Mouser 21,650, $0.47) and `MIC1557YM5-TR` (87,464 /
23,471, $0.47, 4-week lead) — but both are **5 MHz programmable timers** against this part's fixed
500 kHz. They are named here as facts, not proposed as a swap: putting one in is a datasheet
decision about the blink circuit, not a reel change.

### The 10 µF line

Verified parameter by parameter against Murata's `GRM188R61E106KA73J` on the Digi-Key API —
**capacitance 10 µF, rated voltage 25 V, dielectric X5R, package 0603 (1608), max thickness 1.00 mm
and operating range −55 to +85 °C are all identical.** Two differences, both neutral or better:
tolerance loosens ±10 % → ±20 %, immaterial on bulk decoupling and dwarfed by DC-bias derating; and
the `GRT` is Murata's soft-termination series and is **AEC-Q200 automotive-qualified**, which the
`GRM` is not.

Holding the *voltage* and giving up the *tolerance* is the right way round: rated voltage drives
DC-bias derating far harder than the tolerance band does. The placements sit on `VOUT3` (3.228 V),
`VCC` (≤3.2 V), `VAUD` and `VDD2` (2.5 V), `U17`'s supply and `/D1A`.

**This is a BOM-only change** — the board `Value` stays `10u` and no board file moved. **But the
schematic's own `Source` link still points at the `GRM`**, so update it there too before anyone
regenerates a BOM from the schematic.

### The 22 µF line: 25 V costs both qualifications

A sweep of every 22 µF / 25 V / 0805 part at both distributors found **six with stock and eleven at
zero**. Both soft-termination `GRT` parts — `GRT21BR61E226ME13K` and `-13L` — are among the eleven.
**No 25 V part in the market preserves everything the 16 V incumbent has.** Every stocked one gives
up *both* AEC-Q200 qualification and Murata's `GRT` soft termination, which exists to stop flex
cracking on a board that gets handled.

So the trade is narrow and deliberate: **keep the dielectric, change only the voltage.**

| | Murata `GRT21BR61C226ME13K` (his) | YAGEO `CC0805MKX5R8BB226` (this fork) |
|---|---|---|
| Capacitance / tolerance | 22 µF ±20 % | 22 µF ±20 % |
| **Rated voltage** | 16 V | **25 V** |
| Dielectric | X5R | X5R |
| Operating range | −55…+85 °C | −55…+85 °C |
| Package / max thickness | 0805, 1.45 mm | 0805, 1.45 mm |
| Body | 2.00 × 1.25 mm | 2.00 × 1.25 mm |
| Qualification | **AEC-Q200** | — |
| Termination | **soft (`GRT`)** | standard |
| Unit price | $0.42 | $0.60 |
| Lead time | 19 wk | 24 wk |
| Digi-Key / Mouser | 8,218 / 0 | **≈130,000** / 0 |

Verified parameter by parameter on the Digi-Key API. Every mechanical and electrical figure is
identical except the rated voltage — which is the point — and the two qualifications no 25 V part
offers.

**Why not the Murata 25 V part with stock.** `GRM21BC81E226ME44K` keeps the manufacturer, costs
less ($0.38) and runs to +105 °C. But it is **X6S, a different dielectric formulation**, and its
DC-bias curve could not be verified — Murata publishes that only through SimSurfing, which returns
HTTP 500/503 from here, and the product PDFs do not carry the curve. **DC bias is the entire reason
for going to 25 V**, so an unverifiable bias curve is the wrong thing to accept in exchange for it.
It also holds only 2,589.

**The part to come back to** is `GRT21BR61E226ME13L`: the incumbent's own family at 25 V, so it
would make this swap cost nothing at all. Re-check it before every order — if it has restocked, take
it. **If every 25 V line dries up,** fall back to the 16 V `GRT21BR61C226ME13K`; it is
MouseBiteLabs' own choice and it is buildable.

**Also checked:** `C0805X5R226M250NPH` (EYang, 400,000, $0.17, no lead time) is the cheapest and
deepest by far, but it is a budget maker on a board that is otherwise Murata / KEMET / YAGEO.
`GMC21X5R226M25NT` (Cal-Chip, 46,919), `CL21A226MAYNNWE` (Samsung, 2,000, 39-week lead) and
`KGM21AR51E226MU` (Kyocera AVX, 233 + 7, $1.06, 28-week lead) are genuine second sources.
**Rejected:** `ZRA21CR61E226ME01L` reads as 25 V X5R with stock, but Digi-Key gives its package as
*Nonstandard SMD* at **1.65 mm**, not 0805 / 1.45 mm. Not a drop-in.

### The `Value` field is a symbol name, not an ordering code

In KiCad the `Value` field is a **symbol name**; the orderable code lives in the per-symbol `Source`
link, which is exactly where MouseBiteLabs put it. The BOM buys the link's part in every case:

| Ref | Board `Value` (a symbol name) | MouseBiteLabs' own `Source` link | What the BOM buys |
|---|---|---|---|
| `SW1` | `CSS-1310B` | `CSS-1310TB` | `CSS-1310TB` ✔ |
| `P3` | `SJ-3524-SMT` | `SJ-3524-SMT-TR` | `SJ-3524-SMT-TR` ✔ |
| `Q1` | `2N3904` | `MMBT3904LT1G` | `MMBT3904LT1G` ✔ |
| `Q3` | `2N3906` | `MMBT3906LT1G` | `MMBT3906LT1G` ✔ |

There is no 2N3904 in SOT-23, so a reader is better off knowing the Value is generic — which is why
check [6] keeps naming these. Check **[16]** fails if any link in the base schematic is unresolved.

### Remaining defects and mismatches

- **`D1`/`D2` are described as Schottky diodes and are not.** MouseBiteLabs' own link goes to a part
  Digi-Key categorises **"DIODE STANDARD 80V 100MA UMD2"**. `1SS355VMTE-17` is a Rohm *standard*
  switching diode. The part he bought is fine; the schematic's *Description* field is what is wrong.
- **`L1`/`L2` package**: the specified part is a Taiyo Yuden **LSXND3030QKT4R7MNG, 3.00 × 3.00 ×
  1.50 mm**, but the footprint is named `L_Taiyo-Yuden_NR-20xx_HandSoldering` — the NR-20xx family is
  2.0 × 2.0 mm. The land measures 4.00 × 2.00 mm overall with 1.65 × 2.00 mm pads. Check against the
  manufacturer's recommended land pattern before ordering.
- **`CP1`/`CP2`/`CP3` package**: the specified part is a KYOCERA AVX **TPSB107M010R0400**, a
  1411/3528-metric molded tantalum, 3.50 × 2.80 × 2.10 mm, on a footprint named
  `C_1210_3225Metric_Boxed_2` (3.2 × 2.5 mm). The land measures 4.10 × 2.70 mm.
- **`CP1`/`CP2`/`CP3` polarity**: they are **polarized tantalums on a symmetric land pattern with no
  polarity marking anywhere on the board**. A human reads the part's own stripe; a pick-and-place
  reads the CPL rotation, and if that rotation is wrong all three go in backwards.
  **Add polarity silkscreen before ordering assembly.**

---

## 4. What the board settles for you, and what it does not

### Two hand steps the machine will not do

Both concern `U2`, and both are MouseBiteLabs' jumpers with his numbering — see his *Feature
Configurations* wiki page. **Only if you populate the CY62157EV30LL**; leave both **open** for a
salvaged OEM AGB-SRAM, which the land still accepts:

* bridge **`JP2`** — ties `U2` pin 17 (`MA17`) to GND
* bridge **`JP3`** — ties `U2` pin 47 (`/BYTE`) to `VDD2` for ×16 word mode

**This fork's ClockxControl clock jumper is `JP4`**, not `JP3` — `JP3` is his `/BYTE` strap. His
instructions read correctly against this board.

### One build decision the board deliberately leaves to you

`Z57`/`Z58` carry the Value **`100p or 0 ohm`** — MouseBiteLabs states the choice in the field
rather than picking for you. Capacitors make the `L+R+Start+A/B` hotkeys fake a screen kit's touch
input; resistors or jumpers make them plain button inputs for an external mod. **The generated BOM
buys the capacitor.** If you want button inputs, change it before ordering. His own note is worth
reading first — of three units he built, only one could reliably fake the touch input.

### The rotation convention is settled

Every rotation in the position file is byte-identical to what `kicad-cli pcb export pos` emits, and
14 of the 21 placed footprint families are MouseBiteLabs' copies of KiCad's **stock library**,
putting pin 1 in the same corner to **0.000 mm**. Checks [17] and [18] assert both. What remains is
only to confirm your assembler accepts a KiCad position file.

---

## 5. The upload package

[`fab/agbm-02-cxc-pcbway.zip`](fab/agbm-02-cxc-pcbway.zip) is the file you upload. It is
generated by [`scripts/fab_package.py`](../scripts/fab_package.py) and contains:

```
gerbers/    F.Cu In1.Cu In2.Cu B.Cu, both masks, both silks, both pastes, Edge.Cuts
            RS-274X, 6-digit, Protel extensions (.GTL/.G1/.G2/.GBL/...) plus the .gbrjob
drill/      Excellon, millimetres, PTH and NPTH in SEPARATE files, plus drill maps
assembly/   the position file, the assembly BOM, and the do-not-populate list
ORDER.txt   stackup, thickness, layer count, and the things a human has to tell them
```

**It is not plotted from the committed board.** The committed fill is MouseBiteLabs' own,
from before this fork added copper, and 22 of this fork's objects sit inside a foreign-net
pour it has never been recomputed around. The generator re-pours a throwaway copy first, and
that is not cosmetic: **re-pouring takes `F.Cu` from 52 filled regions to 88.** Plotting the
committed file would ship a board with shorted copper.

**It also refuses to build a board that fails DRC.** The re-poured copy goes through KiCad's
own DRC against MouseBiteLabs' project rules, diffed against his board by violation position,
*before* a single aperture is plotted. One unledgered violation aborts the build. There is no
override flag.

Check [21] holds the package to the committed board on every run — cheaply, by comparing the
digest the manifest records. `python3 scripts/fab_package.py --check` does the expensive
version: it re-plots everything and compares aperture by aperture, with the creation
timestamp and generator version normalised out so two runs of the same board compare equal.

### What you still have to set on the order form

| | |
|---|---|
| Layers | **4** |
| Finished thickness | **1.0 mm** — not the 1.6 mm default, and **not** the 1.2 mm the KiCad stackup states. See below |
| Surface finish | **ENIG.** MouseBiteLabs allows HASL *only* with tactile switches fitted; this board keeps its membrane contacts, so ENIG is required |
| Assembly | **both sides.** The fine-pitch work is on the back |

**On the thickness, because the two sources disagree.** The KiCad file carries
`(general (thickness 1.2))` and a stackup whose layers sum to 1.2 mm. MouseBiteLabs' own
README — for AGBM-01, AGBM-02 and AGBM-11 alike — says **order 1.0 mm**. The stackup is a
drawing aid he never adjusted; the shell is what decides. `ORDER.txt` reads the order options
straight out of his README and flags the conflict, because the `.gbrjob` shipped alongside the
gerbers repeats the stackup's number. Check [21] asserts the sheet still carries his.

`ORDER.txt` inside the zip repeats all of this, so it travels with the upload.

---

## 6. Before you order

1. **Open the board in KiCad and Fill All Zones, then plot gerbers.** The shipped fill is
   MouseBiteLabs' own and is deliberately not re-poured by the generator, so check [1]'s
   byte-identical rebuild stays meaningful. **Do not plot gerbers straight from the shipped file.**
2. **Verify the ClockxControl landing geometry against a physical module** — it is photo-derived,
   and it is the largest unverified thing in the package.
3. **Re-run `python3 scripts/check_stock.py`** to refresh stock and price. It needs
   `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` and `MOUSER_PART_API_KEY` in the environment.
4. **Correct the `D1`/`D2` Description field**, fix the two footprint mismatches, and add tantalum
   polarity marking.
5. **Update the schematic's `Source` links** for any line this fork overrides, so a BOM regenerated
   from the schematic does not silently revert them.

DRC status, and what this fork adds to it, is in
[`../clockxcontrol-integration/DESIGN-DECISIONS.md`](../clockxcontrol-integration/DESIGN-DECISIONS.md).
