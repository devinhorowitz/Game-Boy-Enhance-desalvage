# ECO-15 — reading MouseBiteLabs' own part choices

**Board:** `AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb` — **unchanged.** This ECO touches no copper.
**Files:** `scripts/link_mpn.json`, `scripts/mpn_overrides.json`, `scripts/check_stock.py`,
`scripts/check_consistency.py`, `scripts/test_checks.py`, `pcbway-assembly/resolved-mpns.json`,
`pcbway-assembly/README.md`
**Status:** three buy lines corrected, one claim withdrawn, two gates added.

---

## 15.1 The thing that was not being read

Every symbol in MouseBiteLabs' schematic carries a per-symbol `(property "Source" ...)` holding
a Digi-Key link. That link is the **only** record of which part he actually picked for a generic
value like `22u` or `100k`, because the `Value` field is a symbol name, not an orderable code.
`scripts/link_mpn.json` resolves those links.

It was built from **AGBM-01**, and it survived the ECO-13 rebase onto AGBM-02 untouched.

| | AGBM-01 map | AGBM-02 schematic |
|---|---|---|
| links present | 34 | **57** |
| never read | — | **30** |
| stale, kept from AGBM-01 | 7 | — |

The seven stale entries were harmless — 18k, 200k, 560k, 1.78M, 1M, 15p, 33k, all AGBM-01-only
values the rebase deleted, and check [5] confirms none reached the buy list. The thirty unread
ones were not harmless. They included `SW1`, `P3`, `D1`/`D2`, the whole 22 µF line, the tantalum
bulk caps, and both parts this repository had flagged as unresolved engineering calls.

This is the same defect as the pre-rebase renders in ECO-14 §14.5 and the hand-kept `.kicad_mod`
in §14.5 before that: **an artifact that describes an earlier revision, with nothing checking
that it still describes this one.** Three for three, now, on the same rebase.

## 15.2 What the links said — the claim that had to be withdrawn

`pcbway-assembly/README.md` carried a section headed *"Three BOM defects that must be fixed
before an order"*. It named `SW1`, `P3` and `Q1`/`Q3`, and said of the transistors: *"The power
review predicted this one and nobody had flagged it."*

Nobody had to. They were flagged in the schematic:

| Ref | Board `Value` | MouseBiteLabs' `Source` link | What this fork's BOM buys |
|---|---|---|---|
| `SW1` | `CSS-1310B` | **`CSS-1310TB`** | `CSS-1310TB` ✔ |
| `P3` | `SJ-3524-SMT` | **`SJ-3524-SMT-TR`** | `SJ-3524-SMT-TR` ✔ |
| `Q1` | `2N3904` | **`MMBT3904LT1G`** | `MMBT3904LT1G` ✔ |
| `Q3` | `2N3906` | **`MMBT3906LT1G`** | `MMBT3906LT1G` ✔ |

In KiCad the `Value` field is a symbol name and the orderable code lives in `Source`. That is
exactly where Nick put it. Nothing was ever going to be mis-ordered, no board edit was ever
needed, and the fork's "discoveries" were his answers, rediscovered because 30 of his 57 links
had never been opened. The section is withdrawn and check [6] no longer calls them defects — it
still names them, because a reader is better off knowing there is no 2N3904 in SOT-23.

**One of the three claims stands and is now sourced rather than asserted.** `D1`/`D2` are
described in the schematic as Schottky diodes and are not: Nick's own link goes to a part
Digi-Key itself categorises **"DIODE STANDARD 80V 100MA UMD2"**. The part he bought is correct;
the `Description` field is what is wrong.

Reading the links also confirmed, part by part, that **every ECO baseline in this fork is
right**. `DL1` was `150060VS75000` before ECO-8 changed it; `PTC1` was `0805L075SLYR`; `U7` was a
`TLV9364` (family minimum supply 4.5 V, on the 2.5 V `VAUD` rail — ECO-8's correctness fix
holds); `C24`/`C32` were the X7R part before ECO-10 moved them to C0G; `Q9`/`Q10` were `NDC7002N`
before ECO-11. Eighteen more divergences are value changes check [3] already ledgers. That is a
better result than the audit expected, and it is now checkable rather than believed.

## 15.3 Three lines this fork had made unbuyable

The links turned up the opposite problem too. Three buy lines had silently departed from
MouseBiteLabs' part with nothing recording why — and every one had landed on a part with no
stock, while his sat in five figures.

| Refs | This fork bought | Stock | His link | Stock | Resolution |
|---|---|---|---|---|---|
| `CP1`–`CP3` | `TPSB107K010R0400` ±10% | **5** | `TPSB107M010R0400` ±20% | 31,360 | **his** |
| `C1`/`C21`/`C42`/`C58` | `GRT21BR61E226ME13L` 25 V | **0** | `GRT21BR61C226ME13K` 16 V | 8,228 | **his** |
| `R26` | `RC0603FR-0733KL` | **0** | `RC0603FR-1033KL` | 25,665 | **his** |

*Stock: Digi-Key, 2026-08-20.*

**`CP1`–`CP3`.** Five in stock, for a board that needs three. Nothing on a 100 µF audio-rail bulk
tantalum needs ±10%, and no note said why the tighter part was chosen — it looks like a keyword
search that landed on the first hit rather than a decision. His ±20% part is $1.47 against
$1.10, so this costs about a dollar a board and buys the ability to actually order it.

**The 22 µF line** is the instructive one. Its override records a swap made on 2026-08-19 *away
from* `GRM21BR61E226ME44L` **because that part was at zero stock** — and the replacement is at
zero too. Both 25 V parts in the family are. The swap chased availability and landed on another
dead line, because it never checked the part Nick had already chosen. Returning to his 16 V part
keeps the soft-termination `GRT` family and gives up DC-bias headroom: a 16 V X5R loses more
capacitance at a given working voltage than a 25 V one. **Accepted deliberately, and worth a
scope on the first build** if bulk capacitance turns out to matter.

> **Superseded by [ECO-21](ECO-21_22uf_line_to_25v.md).** That headroom was bought back: the
> line now buys YAGEO's 25 V `CC0805MKX5R8BB226`. What this ECO could not know is that the
> choice was never "his `GRT` at 16 V or a `GRT` at 25 V" — **no 25 V `GRT` exists in stock at
> all**, so keeping the soft-termination family and going to 25 V is not an available option.
> ECO-21 gives up the `GRT` family and AEC-Q200 to take the voltage, and says so plainly.

**`R26`.** The `-07`/`-10`/`-13` field in a Yageo `RC0603FR` part number is an internal spec
code; `-07` and `-13` are the moisture-resistant grade and `-10` is not. Nothing on this board
needs 85/85 grade on `R26`, so his part is taken. A sweep of all eleven Yageo lines this fork
buys found the `-07` preference is otherwise sound — nine are stocked in six and seven figures.
`R64`'s `RC0603FR-07200KL` is thin at 5,187 against his `-13` at 82,572; ours is kept, because
5,187 covers any realistic build of this board and it is the better grade, but the thinness is
now on the record as a flag.

## 15.4 Two more zero-stock lines, and they are not this fork's doing

The stock refresh this ECO ran was the first one to complete: the shipped BOM had carried **no
Digi-Key stock figure at all**, because that half of the previous run never finished. All 70
lines now have one, and two more read zero at both distributors:

* `U11`/`U12`/`U18` — `TPS22917DBVR`, load switches
* `U14` — `MIC1553YM5-TR`

Both are **MouseBiteLabs' own parts**, matching his links exactly. This is an availability
problem in the base design, not a fork regression, and no stocked drop-in was found for either
(`TPS22918DBVR` is also dry; `MIC2025-2YM` is a different function). Recorded, not substituted —
changing his parts without cause is the thing this audit exists to prevent.

## 15.5 A parser that was handing parts to the wrong symbol

`check_stock.schematic_sources()` found the end of a symbol block with
`t.find("\n\t)\n", start)`. That heuristic runs past the end of a symbol and picks up the
**next** symbol's `Source`. It mapped 359 refdes where only 187 carry a link — handing `SW1`'s
slide-switch link to `U13`, and `Q3`'s transistor link to `U5`.

Nothing was mis-ordered: every victim was either overridden or not a buyable part (test points
and jumpers, mostly). That is luck. A part that landed next to a `Source`-carrying symbol
without an override would have been bought as its neighbour, silently. Replaced with a
balanced-paren walk; 359 → 187.

It was check [16] that found this, by reporting that `U13`'s link buys a slide switch.

## 15.6 The gates

**Check [16] — UPSTREAM LINKS.** Two rules.

*Completeness:* every `Source` link in the base schematic must be resolved in
`scripts/link_mpn.json`, or the fork is buying blind against choices it has not read. This is
the rule that was missing for the whole life of the rebase.

*Deliberateness:* where a buy line departs from a link **for the same value**, the override must
carry an `"upstream"` field **naming the part it departs from**, plus an `eco` or `flag` saying
why. Naming the part is the load-bearing half — `CP1`–`CP3` already carried a `flag` (about
polarity marking) while silently buying a part with five units in stock, so "has a reason field"
was not a strong enough test. Value changes are exempt and handed to check [3], which already
ledgers all eighteen of them.

**Check [6] gains a buyability warning.** Zero-stock and no-data lines are now reported. A
**warning, not an error**: stock is somebody else's inventory on a particular day, not an
invariant of this repository, and a gate that fails on market conditions is a gate people learn
to ignore. But "no figure at all" is reported as **UNKNOWN, not zero** — the same rule
`check_stock.py` already applies to an unreachable distributor.

**Two negative tests.** One drops a link from the map; one strips a diverging line's ledger. The
second took three attempts to make honest: the first picked "any entry with an `upstream`" and
landed on one whose value an ECO had changed, which [16] correctly skips; the second targeted
`CP1`, which stopped being a divergence the moment this ECO put it back on Nick's part. It now
selects its victim by asking [16] what it is actually counting. Suite is **18 cases, 0 blind**.

## 15.7 Verification

* `python3 scripts/build_board.py --check` — byte-identical; no copper changed
* `python3 scripts/check_consistency.py` — 0 errors across 17 checks
* `python3 scripts/test_checks.py` — 18 cases, 0 blind
* `python3 scripts/check_stock.py` — 70 lines, 69 API calls, 182 of 185 refs resolved
* All 57 upstream links resolved through a browser-grade fetch; `curl` and `urllib` both get
  HTTP 403 from `www.digikey.com` (their bot protection, not the egress proxy), which is why
  the map is data rather than something a script regenerates.
