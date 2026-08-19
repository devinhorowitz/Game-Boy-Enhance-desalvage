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
python3 scripts/check_consistency.py       # everything else
```

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

**The BOM splitter** — SOLAR-GLOW's `bom_split.py`, which is **not written here yet**. Its rule
is the right one for the queued PCBWay work: a part moves between "the machine buys and places
it" and "you hand-solder it" **by changing the design**, never by editing a list, because the
board's own `exclude_from_bom` / `dnp` flags decide. `kisexp.Footprint` already exposes those
three flags for exactly this.

*(That paragraph originally put "Not written yet." at the end, three lines below the filename.
Check [7] failed it — its context window is the citing line and the one above, on purpose, so a
disclaimer that drifts away from the thing it disclaims does not count. The fix was to move the
words, not to widen the window. That is the discipline doing its job on its own README.)*

---

## The files

| | |
|---|---|
| `kisexp.py` | the one reader. Footprints, properties, pads, nets, vias, segments, and a small union-find that tells "unrouted" from "routed in two pieces". |
| `build_board.py` | ECO-5 base → the ClockxControl board. Every edit asserts its own precondition. |
| `routes.json` | the frozen ECO-6 routing. Frozen because the router is not deterministic and the ECO-6 clearance analysis was done against *these* paths. |
| `pack_board.py` | tree → the deliverable zip, with fixed timestamps so two runs over an unchanged tree produce identical bytes. |
| `check_consistency.py` | the eleven checks. |
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
