# ECO-13 — rebase onto AGBM-02, and cull ECO-5

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

**The base board is now MouseBiteLabs' AGBM-02, unmodified.** It was the ECO-5 AGBM-01
desalvage. ECO-5 was our footprint work; he never saw it and never used it. AGBM-02 is his,
and it already does everything ECO-5 was trying to do — with a front-shell fit he
physically verified.

| | Was | Now |
|---|---|---|
| base | `agbm-01-ram-desalvage.zip` (ours) | **`AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip`** (his) |
| output | `AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb` | **`AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb`** |
| package | `agbm-01-clockxcontrol.zip` | **`agbm-02-clockxcontrol.zip`** |
| `U2` land | `Bucketmouse:AGB-SRAM` + 24 pads we added | **`Bucketmouse:AGB-SRAM_2`** — his |
| main converter | LTC3527 | **twin TPS63802** |
| donor chips needed | CPU **and** RAM | **CPU only** |

---

## 13.1 Why: adopting his land means adopting his board

The [wiki audit](../wiki-audit/README.md) §D found that ECO-5 extended `U2`'s land toward
`+x` while the land MouseBiteLabs shipped on AGBM-02 extends toward `−x`, putting our
package body 1.55 mm further into the side he named as the front-shell obstruction. The
obvious fix — drop his `AGB-SRAM_2` geometry onto our board — **was tried, and it does not
work.**

On AGBM-01 the channel immediately west of `U2`'s left pad column is where the entire RAM
address bus escapes: 37 F.Cu segments carrying `MA_1`…`MA_15`, `~WE_RAM`, `~LB`, `~UB` and
GND, fanning out from x = 81.31 toward the CPU. Tested segment-against-pad-rectangle, his
pad field at x = −8.45 **shorts 15 of the 24 new pads across 12 nets** — including `VDD2`
to `GND` at pin 12.

That is exactly what he meant by *"it would be quite an undertaking to re-layout that
portion of the board."* He could put the column there on AGBM-02 **because he re-routed the
fanout.** His land and his routing are one design, and you take both or neither.

### And "both" is much cheaper than it sounds

| | |
|---|---|
| shared reference designators | **230** |
| **at byte-identical positions** | **217** |
| moved | 13 — `U5`, `L1`, `L2`, `EM3` and ten converter passives, all to x ≈ 12–31 |
| only on AGBM-01 | `C40 C41 R21 R22 R23 R55` — the LTC3527 feedback network |
| only on AGBM-02 | `U13`, `JP2`, `JP3`, eight converter passives, `REF**` |

AGBM-02 is AGBM-01 with **two regions redone**: the converter, and the RAM corner. Every
part this fork touches outside those two regions is in the same place, including every net
number every ECO-6 route depends on.

---

## 13.2 What the rebase deletes

**ECO-5, entirely.** `agbm-01-ram-desalvage.zip`, the custom 96-pad `AGB-SRAM` land, the
`JP2` `/BYTE` jumper, the pin-16-to-17 `MA17` solder bridge, the F.Fab body outline, the
five deleted GND stitching vias and eleven deleted plane segments. All of it. The
CY62157EV30LL support it was built to provide now comes from MouseBiteLabs, with `JP2` and
`JP3` as **he** defines them and documents them on his *Feature Configurations* page:

> **ONLY IF YOU ARE USING A NEW RAM CHIP**, you will need to add a solder bridge to JP2 and
> JP3. **IF YOU ARE USING A DONOR'S RAM, DO NOT SOLDER JP2 and JP3.**

**Both ECO-7 blockers**, because both were ECO-5's damage:

* *`U2` pin 37 has no path to `VDD2`* — ECO-5 removed two `VDD2` vias and three tracks to
  clear room for its third pad column. On AGBM-02 pin 37 lands on the `x = 10.97` column,
  which is a stock column the OEM RAM also uses, already carrying `VDD2`.
* *`Net-(Q5B-G)` severed into two islands* — ECO-5 deleted the via at `(100.8, −62.15)`.
  AGBM-02 has the net **whole, one island**, verified by union-find over its segments,
  vias and pads.

Consistency check [10] existed to go **red when these were fixed**, so that four documents
claiming they were open could not quietly become wrong. It fired. It is now rewritten to
assert they are *closed*, and it goes red if either ever reappears.

**ECO-12 §12.1 and §12.2, and all of ECO-10's `Value` swaps.** See §13.4.

---

## 13.3 What the rebase gains

**MouseBiteLabs' verified mechanical fit.** The reason for the whole exercise.

**A build that needs one donor chip.** *Required Parts*: *"For the AGBM-02 and AGBM-12, you
**only** need the CPU."* `U2` therefore leaves `SALVAGE_ONLY` in the generator and becomes
an orderable part the machine buys and places. That is the "desalvage" this repository is
named for, delivered by upstream rather than by us.

**29 mW.** His measured idle figures, from *Power Draw and Battery Curves*:

| Board | Main converter | Idle |
|---|---|---|
| Stock GBA | — | 134 mW |
| **AGBM-02** | **twin TPS63802** | **141 mW** |
| AGBM-01 | LTC3527 | 170 mW |

17 % of idle, measured on two boards with verified-identical downstream — not modelled.
Note the honest caveat the power review already carries: this is a **light-load** gap, and
at 240–380 mW of rail delivery the two converters sit within about a point of each other.

**`R3`/`R4`/`R64` correct by inheritance.** AGBM-02 already carries 5.1 k / 33 k / 200 k.

**A refdes collision resolved.** Our ClockxControl clock jumper was `JP3`, which is
MouseBiteLabs' `/BYTE` strap on AGBM-02. It is now **`JP4`**, so his *Feature
Configurations* instructions read correctly against this board — the documentation trap the
wiki audit flagged is gone rather than merely documented.

---

## 13.4 What each ECO does on the new base

| ECO | On AGBM-02 |
|---|---|
| **ECO-5** | **deleted** — superseded by MouseBiteLabs' own land |
| **ECO-6** | carries. `C7` at the identical `(91.9, −41.1)`; the module window holds only `C7` on F.Cu; the wire-pad row is clear; both `VDD2` vias to drop are present on the right net. Jumper renamed `JP3` → `JP4`. |
| **ECO-7** | DNP of `X1`/`C3`/`C4` carries — all three present with `(attr smd)`. **Both blockers deleted.** |
| **ECO-8** | 10 of 13 rows carry. Three do not — see below. |
| **ECO-9** | carries, and improves: `U2` moves from the salvage list to the assembly BOM. |
| **ECO-10** | **no `Value` swaps survive**; its part-number work is untouched. |
| **ECO-11** | carries unchanged — `Q9`/`Q10` are `NDC7002N` on AGBM-02 too. |
| **ECO-12** | **no `Value` swaps survive**; its part-number work is untouched. |

### ECO-8: three rows are already done upstream

* **`F1` `Value`** — AGBM-02 already reads `F0805B2R00FSTR`. ECO-8's BOM fix was right and
  MouseBiteLabs made the same fix. Nothing left to change.
* **`PTC1` `Value`** — AGBM-02 already reads `0805L075SLYR`, not the stale `0467001.NR`.
  **The annotation is fixed upstream; the engineering finding is not affected.** That part
  derates to 0.55 A hold at 40 °C and 0.40 A at 60 °C, below the realistic worst-case input
  current, so the swap to `0805L110SLYR` stays — from a different starting value.
* **`R23` `Value`** — the reference does not exist. ECO-12 §12.2 had already reverted this
  change; the rebase deletes it outright.

Both `Description` rows survive: AGBM-02 still carries the legacy `0805L050WR` string on
`PTC1` and `F1` alike, exactly as AGBM-01 and AGBM-11 do.

### ECO-10 and ECO-12: the LTC3527 work goes with the LTC3527

ECO-10's headline was rescaling both LTC3527 feedback dividers 10× down, because the
converter's own 50 nA max feedback input current was moving `VOUT3` by ±85 mV — more than
the resistors' tolerance, and more than the 108 mV ECO-8 had trimmed off that rail. **It was
the right finding about the wrong converter.** `R21`, `R22`, `R23`, `R55`, `C40` and `C41`
do not exist on AGBM-02.

ECO-12 §12.1 corrected `R3`/`R4`/`R64` from a stale AGBM-01 PCB annotation. AGBM-02 already
carries the correct values — that is what made the wiki audit's case in the first place — so
the corrections are now **inherited, not applied**. §12.2 goes with `R23`.

**Everything either ECO bought that was not a `Value` change survives**, because it lives in
`scripts/mpn_overrides.json` against references AGBM-02 carries at identical positions: the
audio filter's 0.1 % ±25 ppm thin film, the 25 V AEC-Q200 decoupling, `R3`/`R4` on Susumu
RG1608, and `R63` moved onto the same film as its partner `R58`.

So on this base **only ECO-8 and ECO-11 change a `Value` at all.** That is a much smaller
diff against MouseBiteLabs' design than the fork carried a day ago, and it is the right
direction of travel.

---

## 13.5 Two things the rebase made stronger

**Nets are resolved by name, not by number.** ECO-6 used to hard-code them — `VDD2` was 8,
`GND` 2, `/CPU/TP2` 71. That is fine until the base board changes underneath, at which point
every literal silently points at a *different* net and the generator routes the clock line
into a power plane. On this rebase all eight kept their numbers, **which is exactly the kind
of luck that hides a bug rather than preventing it.** They are now looked up by name and the
build fails loudly if one is missing. `routes.json` still keys three runs by their old
number; the generator asserts each still means the net it meant.

**The threshold assertions read the board instead of a literal.** On the AGBM-01 base those
values were ours to set, so asserting our own numbers proved something. On AGBM-02 they are
MouseBiteLabs' and inherited, so the only assertion worth making is that the board in front
of us still produces the thresholds he published — 2.309 V and 2.102 V, from `R3`/`R4` and
`R58`/`R63` as the board carries them, plus the 3.6 Hz blink from `R64`. **This fails if
upstream drifts**, which a literal never would.

---

## 13.6 Fiducials are ours, and always were

Neither AGBM-01 nor AGBM-02 carries a single fiducial — MouseBiteLabs hand-builds, and a
hand builder needs no optical registration. ECO-5 added six; ECO-6 then moved a pair out
from under the module. On this base they are simply **placed clear of it to begin with**:
three per side at `(26, −8)`, `(33, −69)` and `(106.25, −57.25)`, a deliberately asymmetric
triangle so a machine cannot register the panel 180° out. Each spot was clearance-checked
against AGBM-02.

---

## 13.7 What is still open

* **The ClockxControl landing geometry is still photo-derived** and must be checked against a
  physical module. Unchanged by the rebase.
* **The CPL rotation convention is still unverified** against PCBWay's per-package zero
  reference.
* **The ECO-6 routing is generated, not laid out in KiCad.** Open the board and run DRC
  before fabricating — the rebase did not change that, and a re-pour is still wanted.
* **AGBM-02 is newer and less proven than AGBM-01.** MouseBiteLabs' own note:
  *"The AGBM-02 was not as thoroughly analyzed, but a random sampling of configurations
  yields pretty similar power consumption measurements."* His battery-life tables were all
  measured on an AGBM-01.
* **`REF**` on AGBM-02** is an unannotated `Crystal_HC49-4H_Vertical` footprint at
  `(8.89, −81.888)`, well outside the board outline. It is upstream's, it is excluded from
  the BOM and position files by the assembly split, and it is noted here so nobody has to
  rediscover it.

---

## 13.8 Two things found while doing it

**`C70`/`C71` are a gap in MouseBiteLabs' own BOM.** 27 pF coupling caps on the hotkey
touch-input nets — `Net-(C70-Pad1)` is `C70.1`, `R70.2`, `TP10.1`, `Z57.2`, read off the
netlist — fitted (not DNP) on AGBM-01 and AGBM-02 alike, and listed in neither README. So
there is no upstream link to resolve and this fork had to choose. It took Samsung
`CL10C270JB8NNNC`: the TDK CGA part that would have matched ECO-10's decoupling family has
8 in stock, and both Murata candidates are flagged Not Recommended for New Designs while
TDK's C-series equivalent is Obsolete. All four dead ends are recorded in the override.

**`Z57`/`Z58` state a build decision in the `Value` field.** They read `100p or 0 ohm`,
because the pair is configurable: capacitors make the `L+R+Start+A/B` hotkeys fake a screen
kit's touch input, resistors or jumpers make them plain button inputs. **The generated BOM
buys the capacitor**; change it before ordering if you want button inputs. This also exposed
a real defect in `scripts/check_stock.py`, which grouped buy lines **by MPN alone**: `Z57`
and `Z58` resolve to the same 100 pF part as `C18`/`C19`/`C20` but carry a different board
`Value`, so one line was claiming a single Value for references the board disagreed about.
Grouping is now by MPN **and** board Value.

---

## 13.9 A note on the distributor data in this commit

`pcbway-assembly/resolved-mpns.json` was regenerated with **`scripts/check_stock.py
--reshape`**, a mode added here. Mouser's daily call quota was exhausted and Digi-Key was
returning HTTP 429, so no distributor could be queried — and writing a file full of blanks
would have been honest but useless, replacing real dated figures with nothing.

`--reshape` rebuilds the file's **structure** from the board and the overrides — which
references exist, what they group into, what each buys — and **carries the previously
fetched figures forward by MPN**, stamping every line with `data_as_of`. It queries nothing
and says so loudly. The rule this repository runs on is that a probe which did not run
reports UNKNOWN and never zero; a figure that *did* run, labelled with when it ran, does not
break it. What is forbidden is an undated number presented as current, and `data_as_of` is
exactly what stops that.

**Re-run `scripts/check_stock.py` without `--reshape` before placing an order.** Every stock
and price figure in that file is from 2026-08-19, and the two new lines this rebase
introduced — the TPS63802s and the CY62157 — were priced live before the quota ran out.

`scripts/check_stock.py` also gained real throttle handling while this was diagnosed:
Digi-Key had **no retry at all**, so a single HTTP 429 turned into a silently blank column.
It now backs off exponentially, remembers the back-off across parts, retries four times, and
reports the 429 count in its summary.

---

## Verification

* `python3 scripts/build_board.py --check` — board rebuilds byte-identically from the
  AGBM-02 base
* `python3 scripts/check_consistency.py` — check [10] now asserts both former blockers are
  **closed**, and goes red if either returns
* `python3 scripts/test_checks.py` — the negative tests still fire
