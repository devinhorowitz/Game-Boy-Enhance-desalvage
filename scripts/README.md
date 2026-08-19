# `scripts/` — the board is a function, and the documents are gated

Everything here exists to make two claims true and keep them true:

1. **The board is not a blob.** `clockxcontrol-integration/board/agbm-01-clockxcontrol.zip`
   is rebuilt from committed inputs by `build_board.py`, byte-for-byte. Before this, the
   generator lived in a scratch directory and was never committed — ECO-8 §8.6 said so —
   which meant nobody, including its author, could re-derive the deliverable.
2. **The documents cannot quietly stop describing it.** `check_consistency.py` holds every
   ECO's part values, DNP set, placement and blocker claims against the board itself.

```sh
python3 scripts/build_board.py --check     # the shipped board is what the generator makes
python3 scripts/pack_board.py  --check     # the shipped package is what the tree holds
python3 scripts/bom_split.py   --check     # the two buy documents agree with the board
python3 scripts/check_stock.py --offline   # every MPN buys the value the board asks for
python3 scripts/check_consistency.py       # everything else
python3 scripts/test_checks.py             # ...and the checks can still fail
```

`check_stock.py` without `--offline` also queries the distributors, and needs
`DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` and `MOUSER_PART_API_KEY` in the environment.
CI runs only the offline half, because CI has no credentials and should not have any.

All three run in CI on every push that touches anything they read
([`.github/workflows/consistency.yml`](../.github/workflows/consistency.yml)).

---

## Where this came from

The architecture is borrowed from **[SOLAR-GLOW · DRH](https://github.com/devinhorowitz/solar-business-card)**,
whose `scripts/check_consistency.py` is the most disciplined drift guard I have read on a
hardware project. Three ideas were taken more or less whole:

**Numbered checks with an accumulator.** Each check prints its own verdict and appends to
`errors`/`warnings`; the suite exits nonzero on any error and never on a warning. It reads
like a report, not a stack trace.

**The exclusion-ledger shape.** Where there is no second source of truth to compare
against, the check carries a **snapshot with a reason on every line**. A deliberate change
updates the snapshot in the same commit that makes it; an undeliberate one stops being
invisible. `DNP_ADDED`, `PLACED`, `EXPECTED_ABSENT`, `VALUE_IS_NOT_MPN` and
`KNOWN_DEFECT_PNS` are all that shape. A ledger entry with no reason is not a ledger entry.

**A check that goes red when the bug is fixed.** SOLAR-GLOW's check [20] re-classifies its
own historical failures every run, and fails if either stops going red. Check [10] here is
the same instinct pointed at a different problem: ECO-7 and three other documents carry a
prominent "the board is not fabricable" section resting on two facts about copper. When
somebody routes them, the board becomes fabricable and every one of those paragraphs
becomes a lie — with nothing to notice. So the facts are asserted. **Fix the board and this
check fails, naming the documents that have to be corrected in the same commit.**

### What was deliberately not borrowed

**The pinned KiCad container.** SOLAR-GLOW pins a KiCad image by digest in three workflows
and has to keep the three in step, because several of its checks are computed by KiCad
itself — netlist export, pad geometry, zone fill. Nothing here needs that: the board is a
text s-expression and `kisexp.py` reads it with the standard library. The whole gate runs
in about five seconds on a bare runner with nothing pinned, so there is one fewer surface
that can rot. **The cost is real and is stated rather than hidden:** no zone awareness, no
DRC, no clearance engine. `net_islands()` says so in its own docstring, which is why check
[10] names a specific missing via rather than just counting pieces of copper.

**The weekly freshness canary.** SOLAR-GLOW distinguishes *rot* (a pinned artifact stops
being fetchable) from *drift* (upstream moves on) and reports them differently every
Monday. There is nothing pinned here to rot. If this repo ever grows a live stock check
against distributor APIs, that workflow is the model — including its hard-won lesson that
**a probe that could not reach upstream must report UNKNOWN, never "current."**

*(This section used to say the BOM splitter was "not written here yet". It is now
`bom_split.py`, below. The paragraph is kept only for the story in it: the disclaimer
originally sat three lines under the filename, check [7] failed it — its context window is the
citing line and the one above, on purpose, so a disclaimer that drifts away from the thing it
disclaims does not count — and the fix was to move the words, not widen the window.)*

---

## The files

| | |
|---|---|
| `kisexp.py` | the one reader. Footprints, properties, pads, nets, vias, segments, and a small union-find that tells "unrouted" from "routed in two pieces". |
| `build_board.py` | ECO-5 base → the ClockxControl board. Every edit asserts its own precondition. |
| `routes.json` | the frozen ECO-6 routing. Frozen because the router is not deterministic and the ECO-6 clearance analysis was done against *these* paths. |
| `pack_board.py` | tree → the deliverable zip, with fixed timestamps so two runs over an unchanged tree produce identical bytes. |
| `bom_split.py` | board → the two buy documents. **A part moves between them by changing the design, never by editing a list** — the board's own `exclude_from_bom` / `dnp` decide, which is what [ECO-9](../clockxcontrol-integration/ECO-9_assembly_split.md) made true. |
| `check_stock.py` | resolves every buyable ref to an MPN and prices it live against the **Digi-Key and Mouser APIs**. Writes `pcbway-assembly/resolved-mpns.json`. |
| `mpn_overrides.json` | hand-maintained: which part a refdes buys, and why. An override beats a schematic link — which is how ECO-8's swaps survive an upstream schematic that still points at the parts they replaced. |
| `link_mpn.json` | the upstream schematic's own 34 per-symbol Digi-Key short-links, resolved once and frozen. For a generic `1u` or `100k` this is the only record of which part MouseBiteLabs picked. |
| `check_consistency.py` | the twelve checks. |
| `test_checks.py` | mutates the board in memory and asserts each check **fails**. A check that has never gone red is not known to work. |

## The checks

| | asserts | fails when |
|---|---|---|
| [1] | the shipped board rebuilds byte-for-byte from the committed base | the board was hand-edited, or the generator changed without repacking |
| [2] | every document in the shipped zip matches its copy in the tree | the package went stale |
| [3] | ECO-8's swap table, the generator and the board agree on all eleven values | any one of the three is edited alone |
| [4] | the DNP set is the ECO-5 base's 47 plus exactly ECO-7's three | a stray flag on either side |
| [5] | every ref in `resolved-mpns.json` is on the board with that `Value` | the buy list and the board disagree |
| [6] | every MPN is consistent with the `Value` beside it | a distributor would ship the wrong part |
| [7] | every path any `.md` cites exists, is marked historical in its own sentence, or is ledgered | a citation rots |
| [8] | every image any `.md` displays exists | a render is deleted or renamed |
| [9] | the ECO-6 module window is component-free and its parts have not moved | a part lands where the module has to go |
| [10] | both ECO-7 blockers are still open, and the stock board still proves the diagnosis | **they get fixed** — see above |
| [11] | the board parses, parens balance, no duplicate refdes, no orphan net numbers | the file is corrupt |
| [12] | nothing reaches the pick-and-place without a BOM line to buy it, nothing is on both buy documents, and the generated buy documents are what a fresh run produces | a CPL names a part nobody bought |

## What it found on its first run

Worth recording, because it is the argument for having built it.

- **A never-spliced footprint in the generator.** A `TP82` landing was constructed and then
  left out of the final concatenation, so it existed in the code and never on the board.
  Check [9] noticed a snapshot naming a footprint that was not there. Deleted.
- **An implicit newline normalisation the rebuild depended on.** The ECO-5 base carries
  exactly one stray CRLF, at EOF. The original generator's text-mode `open()` silently
  normalised it, so the shipped board is one character shorter than its input. Check [1]
  could not pass until that was made explicit — and it is now asserted, so a base board
  with different line endings fails the build instead of quietly producing a different one.
- **A silent empty parse.** `kisexp` anchors on `"\n\t"`, and the upstream MouseBiteLabs
  board is CRLF throughout — so it parsed to **zero footprints** and produced a confident,
  wrong conclusion about which board had routed a net. `load()` now normalises and
  `footprints()` refuses to return nothing from a file that plainly has some. A silent
  probe read as "no problem" is the failure this whole suite exists to prevent.
- **A wrong word in four documents.** `Net-(Q5B-G)` was described as "open" everywhere
  outside ECO-7 §7.2. It is not open: it carries ten segments of MouseBiteLabs' own
  routing and is severed at exactly one deleted via. Check [10]'s island trace found it,
  and the stock-board diff proved the cause. Corrected in all four.

## Upstream

```sh
git remote add upstream https://github.com/MouseBiteLabs/Game-Boy-Enhance
git fetch upstream && git merge upstream/main
```

Synced 2026-08-19 to `48e2dc3`. **Every design file here is byte-identical to upstream's**,
which is the property the whole ECO chain rests on — `build_board.py` regenerates the board
from `agbm-01-ram-desalvage.zip`, which is ECO-5's fork of upstream's `AGBM-01_Design Files`.
If that ever stops being true, every number in ECO-6 through ECO-10 is describing a board
nobody has.

**Do not edit the root `.gitignore`.** It is upstream's, contributed by `bytendomods`; leaving
it alone means a future sync is always a fast-forward. This fork's patterns live in scoped
files beside what they cover (`scripts/.gitignore`, `clockxcontrol-integration/board/.gitignore`).

Two of upstream's patterns are worth knowing before they bite:

| Pattern | What it would swallow |
|---|---|
| `*.net` | a KiCad netlist export. Intended — netlists regenerate — but a netlist shipped as a *deliverable* would vanish silently. |
| `*.log` | a fab or check log. Same. |

`*.csv` is present but **commented out** upstream, which is the only reason
`pcbway-assembly/generated/*.csv` survives. If a future sync uncomments it, the buy documents
stop being tracked and check [12] starts failing on files that are simply invisible. Verified
today with `git check-ignore` against every generated path.

## What it found on its second run

`bom_split.py` landed after the checks, and the first thing it did was fail:

- **`MOD1` was in the position file.** The ClockxControl footprint carried
  `exclude_from_bom` from ECO-6 — so it was off the BOM — and nothing had ever taken it out
  of the CPL. A part the assembler was never sold, queued for a nozzle, on a mezzanine
  whose plated holes are filled with solder *from above*. No human table catches that,
  because both halves look right on their own.
- **The board was asking a machine to buy the salvaged CPU.** 179 parts on the assembly
  BOM, including `U1` and `U2`, which nobody sells at any price, and five parts with
  through-hole pads. [ECO-9](../clockxcontrol-integration/ECO-9_assembly_split.md) encodes
  the split so the board itself says what a machine can do — and the rule is *mechanical*
  (any through-hole pad, plus a two-entry salvage ledger), not a list to maintain.
- **The sourcing gap got a number.** "~35 unresolved links" is now **33 of 61 assembly
  lines, 105 of 172 parts**, measured every run.

## What it found on its third run

Resolving the MPNs against the live APIs turned up a **third instance of one defect class** and
one lesson the borrowed doctrine had already written down:

- **`Q1` and `Q3` carry TO-92 part numbers on SOT-23 pads.** The board says `2N3904`/`2N3906`.
  There is no 2N3904 in SOT-23 — the SOT-23 parts are `MMBT3904LT1G`/`MMBT3906LT1G`, which is
  exactly what the schematic's own links buy. The power review's verifier predicted this in
  passing ("a part-number/package mismatch nobody flagged") and nothing had acted on it. It is
  the same shape as `SW1`'s `CSS-1310B` and `P3`'s `SJ-3524-SMT`: **the Value names something a
  distributor will not ship.** All three are now ledgered and reported until the board is fixed.
- **Three refs where the schematic and the PCB disagree about the value.** `R3` (1k vs 5.1k),
  `R4` (10k vs 33k) and `R64` (100k vs 200k) — confirmed from the distributor side, because the
  schematic's own Digi-Key links buy the schematic's values. This is the conflict that has been
  blocking the supervisor-divider change since ECO-8 §8.4, and it is now a ledgered decision
  (the MPN follows the board) that keeps being reported rather than an unexplained gap.
- **The ledger cannot assert availability either.** Swapping the 10 µF line to an in-stock part
  left the *previous* part's hand-written `OUT OF STOCK` flag attached to the entry, and it
  shipped into the assembly BOM sitting beside a live block that said 192,299 in stock. A
  hand-written stock claim is true for about a week and then quietly lies. `check_stock.py` now
  refuses to run if any hand-maintained field claims availability without naming the day it was
  checked — a dated observation carries its own expiry, an undated one does not.
- **An unreached probe must report UNKNOWN, not zero.** SOLAR-GLOW's weekly-freshness workflow
  says this in capitals and it earned its capitals here on the first live run: a rate-limited
  Mouser query returned nothing for a 33 k resistor, which the first draft wrote out as absent.
  Mouser had 95,136 of them. The client now retries with backoff and, failing that, writes an
  explicit `UNKNOWN` marker that says in its own text that it is not a stock figure of zero.
