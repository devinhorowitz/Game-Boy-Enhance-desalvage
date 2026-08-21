# `scripts/` — the board is a function, and the documents are gated

Everything here exists to make two claims true and keep them true:

1. **The board is not a blob.** `clockxcontrol-integration/board/agbm-02-clockxcontrol.zip` is
   rebuilt from committed inputs by `build_board.py`, byte-for-byte.
2. **The documents cannot quietly stop describing it.** `check_consistency.py` holds every claim
   about part values, the DNP set, placement, clearance and the buy documents against the board
   itself.

```sh
python3 scripts/build_board.py  --check    # the shipped board is what the generator makes
python3 scripts/pack_board.py   --check    # the shipped package is what the tree holds
python3 scripts/bom_split.py    --check    # the buy documents agree with the board
python3 scripts/check_stock.py  --offline  # every MPN buys the value the board asks for
python3 scripts/check_consistency.py       # everything else
python3 scripts/test_checks.py             # ...and the checks can still fail
python3 scripts/check_drc.py               # KiCad's own DRC, against HIS project rules
python3 scripts/fab_package.py             # the zip you upload to PCBWay
```

`check_stock.py` without `--offline` also queries the distributors, and needs
`DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` and `MOUSER_PART_API_KEY` in the environment.
CI runs only the offline half, because CI has no credentials and should not have any.

The suite runs in CI on every push that touches anything it reads
([`.github/workflows/consistency.yml`](../.github/workflows/consistency.yml)).

---

## The files

| | |
|---|---|
| `kisexp.py` | the one s-expression reader. Footprints, properties, pads, nets, vias, segments, and a small union-find that tells "unrouted" from "routed in two pieces". A reader that can see its token but parse none of it **raises** rather than returning empty. |
| `geom.py` | copper and mechanical arithmetic: board outline, edge chords, keepouts, courtyards, mask apertures, zone blocks, and the site model the fiducial search and check [13] share. |
| `build_board.py` | MouseBiteLabs' AGBM-02 → the ClockxControl board. Every edit asserts its own precondition, so an upstream change that moves the thing being patched stops the build instead of silently patching the wrong object. |
| `routes.json` | the frozen routing. Frozen because the router is not deterministic and the clearance analysis was done against *these* paths. |
| `place_fiducials.py` | the fiducial site search — edge, keepout, copper, mask and courtyard, on the layer the mark actually lives on. |
| `pack_board.py` | tree → the deliverable zip, with fixed timestamps so two runs over an unchanged tree produce identical bytes. Ships both board formats, MouseBiteLabs' project file under each board stem, the footprint and the documents. |
| `kicad10.py` | the KiCad 10 copy of the board, and the gate that proves it is the same design. KiCad 9 stays the source of truth so check [1]'s byte-identical rebuild survives. |
| `bom_split.py` | board → the buy documents. **A part moves between them by changing the design, never by editing a list** — the board's own `exclude_from_bom` / `dnp` decide. |
| `check_stock.py` | resolves every buyable ref to an MPN and prices it live against the **Digi-Key and Mouser APIs**. Writes `pcbway-assembly/resolved-mpns.json`. |
| `mpn_overrides.json` | hand-maintained: which part a refdes buys, and why. An override beats a schematic link — which is how this fork's swaps survive an upstream schematic that still points at the parts they replaced. |
| `link_mpn.json` | the upstream schematic's own per-symbol Digi-Key short-links, resolved once and frozen. For a generic `1u` or `100k` this is the only record of which part MouseBiteLabs picked. |
| `render_board.py` | the copper views, drawn from the board with Pillow. Stamps each manifest with the SHA of the board and base it drew from. |
| `render_assembled.py` | the raytraced views, drawn by KiCad from a throwaway re-poured copy. Names every body it could not resolve on every run. |
| `check_drc.py` | KiCad's DRC on both boards, **under MouseBiteLabs' own `.kicad_pro` rules**, and a diff: only violations at positions his board does not have are this fork's. |
| `fab_package.py` | board → the PCBWay upload: gerbers, drill, CPL and BOM. Re-pours a throwaway copy first, because the committed fill would plot a shorted board, and **refuses to plot at all** if the re-poured copy does not pass DRC. |
| `check_consistency.py` | the numbered checks. |
| `test_checks.py` | mutates the board in memory and asserts each check **fails**. A check that has never gone red is not known to work, and a check that *declined to run* is not the same as one that passed. |

## The checks

Numbering is stable, so a document can cite "check [12]" and stay right. Gaps are retired checks,
not missing ones.

| | asserts | fails when |
|---|---|---|
| [1] | the shipped board rebuilds byte-for-byte from the committed base | the board was hand-edited, or the generator changed without repacking |
| [2] | every document in the shipped zip matches its copy in the tree | the package went stale |
| [2b] | the shipped `.kicad_mod` is what the board's own `MOD1` block derives to | the library part and the placed part drift apart |
| [4] | the DNP set is MouseBiteLabs' own plus exactly what a ClockxControl build adds | a stray flag on either side |
| [5] | every ref in `resolved-mpns.json` is on the board with that `Value` | the buy list and the board disagree |
| [6] | every MPN is consistent with the `Value` beside it | a distributor would ship the wrong part |
| [7] | every path any `.md` cites exists, is marked historical in its own sentence, or is ledgered | a citation rots |
| [8] | every image any `.md` displays exists | a render is deleted or renamed |
| [9] | the module window is component-free and its parts have not moved | a part lands where the module has to go |
| [10] | the `U2` pin-37 supply and `Net-(Q5B-G)` are whole, on this fork *and* on his board | either regresses |
| [11] | the board parses, parens balance, no duplicate refdes, no orphan nets | the file is corrupt |
| [12] | nothing reaches the pick-and-place without a BOM line to buy it, nothing is on both buy documents, and the generated buy documents are what a fresh run produces | a CPL names a part nobody bought |
| [13] | this fork's copper clears his by ≥ 0.2 mm, every footprint is inside the outline, the module fits its neighbours, and all six fiducials are readable | an added object crowds the host design |
| [14] | the zone fill is still byte-identical to the base | somebody re-poured and the byte-identical rebuild stopped meaning anything |
| [15] | every render is what the committed board re-renders to — by manifest digest always, pixel-for-pixel where Pillow is installed | a stale render rides a green build |
| [16] | every one of MouseBiteLabs' own part links resolves, and every divergence from one is stated | the fork substitutes a part without saying so |
| [17] | paste is only where a machine will place a part, and `U2` has exactly one of its two nested lands pasted | a stencil deposits solder on a pad no part is coming to |
| [18] | every CPL rotation is `kicad-cli`'s own, and pin 1 is where the stock library puts it | a polarised part goes in backwards |
| [19] | the KiCad 10 companion carries the same copper, pads, nets, text and graphics as the KiCad 9 board | the two formats diverge |
| [20] | every power figure the documents state is in `POWER_LEDGER` with a reason, and every ledger line is still stated somewhere | a modelled number drifts between the documents that repeat it, or arrives unjustified |
| [21] | the PCBWay package was plotted from the committed board, and carries every layer, both drill files and the assembly documents | the fab package goes stale, or ships missing a layer |

Check [19] compares **track coverage**, not segments: KiCad 10 merges collinear tracks, and a naive
diff calls that hundreds of deleted traces.

Check [20] is the odd one out: it has no artifact to re-derive from. The power figures are
modelled from MouseBiteLabs' published measurements rather than measured on a board of this
fork, so the ledger IS the source of truth and the check only keeps the documents honest
against it — in both directions.

## Where the history went

These files used to carry tags like `ECO-14:` on their rationale comments, pointing at
numbered engineering records. Those records are gone — collapsed into
[`../clockxcontrol-integration/DESIGN-DECISIONS.md`](../clockxcontrol-integration/DESIGN-DECISIONS.md),
which keeps every decision that constrains a future change and drops everything that was only
a record of how the work went — and the tags are gone with them. A comment now says what it
means without a label to look up.

The numbering survives in git: `git log --grep=ECO-14` still finds the commit, the diff, and
the document as it stood.

## Where this came from

The architecture is borrowed from
**[SOLAR-GLOW · DRH](https://github.com/devinhorowitz/solar-business-card)**, whose
`scripts/check_consistency.py` is the most disciplined drift guard I have read on a hardware
project. Three ideas were taken more or less whole:

**Numbered checks with an accumulator.** Each check prints its own verdict and appends to
`errors`/`warnings`; the suite exits nonzero on any error and never on a warning. It reads like a
report, not a stack trace.

**The exclusion-ledger shape.** Where there is no second source of truth to compare against, the
check carries a **snapshot with a reason on every line**. A deliberate change updates the snapshot
in the same commit that makes it; an undeliberate one stops being invisible. `DNP_ADDED`, `PLACED`,
`EXPECTED_ABSENT`, `VALUE_IS_NOT_MPN`, `KNOWN_NEW` and `FIDUCIAL_SITES` are all that shape. **A
ledger entry with no reason is not a ledger entry.**

**A check that goes red when the bug is fixed.** Check [10] is that instinct pointed at this board:
several documents once rested on two facts about broken copper. When somebody routes them, those
paragraphs become lies with nothing to notice. So the facts are asserted — and now that the rebase
onto AGBM-02 closed both, the check asserts they stay closed, and names what has to be corrected if
they ever reopen.

Three lessons this fork paid for, kept here because they are the reason several readers now raise
instead of returning empty:

- **A reader that finds nothing must say so.** A net table read as zero nets nearly reported 3,557
  deleted tracks as a clean diff.
- **A pattern must match the whole grammar.** A silkscreen reader whose `(at x y)` pattern could not
  match `(at 0 0 180)` extracted an empty position for *every* `fp_text` on the board, so all text
  compared equal and three real edits went unmerged.
- **"Did not run" is not "passed."** The render check needs Pillow, which CI does not install; until
  the test suite could tell the two apart, a skipped check read as a green one.
