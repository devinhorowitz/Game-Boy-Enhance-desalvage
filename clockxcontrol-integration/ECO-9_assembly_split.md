# ECO-9 — make the board say what a machine can actually place

Eight footprints gain `exclude_from_bom` and `exclude_from_pos_files`. **No copper, no
land pattern, no placement, no part values** — a 16-line diff against the ECO-8 board.

---

## 9.1 The defect

Before this, a BOM and a position file generated from the board would have asked a
pick-and-place to **buy and place 179 parts**. Two of them do not exist as purchasable
items, and five have through-hole pads.

| Ref | | Why a machine cannot do it |
|---|---|---|
| `U1` | AGB-CPU, 128-pin QFP | **Salvaged from a donor board.** The schematic's own `Source` field reads `Salvage`. Not orderable at any price. |
| ~~`U2`~~ | *(removed by [ECO-13](ECO-13_rebase_onto_agbm02.md))* | AGBM-02 carries MouseBiteLabs' own dual RAM land, so `U2` is an **orderable part** — `CY62157EV30LL-45ZXIT`, bought and placed by the machine. A build needs one donor chip, not two. Bridge `JP2` and `JP3` by hand afterwards; leave both open if you fit a salvaged AGB-SRAM instead, which the land still accepts. |
| `P1` | AGB cartridge slot | 36 through-hole pins |
| `P3` | CUI SJ-3524-SMT jack | 4 SMD + 4 through-hole signal pins + 2 unplated posts |
| `P4` | AGB link port | 8 through-hole pins |
| `SP1` | speaker | 2 through-hole pads, wired mechanical part |
| `VR2` | Alps RK10J12R0A0B pot | 7 SMD pads + 2 through-hole anchors |
| `MOD1` | ClockxControl | a mezzanine whose plated holes are filled with solder **from above** onto the pads below |

`MOD1` is the one the tooling found rather than the human: it already carried
`exclude_from_bom` from ECO-6, so it was off the BOM — and still **in the position file**,
which is the worse half. A part the assembler was never sold, queued for a nozzle.

That is the same defect class SOLAR-GLOW's check [15] was written after: a CPL naming ten
parts nobody had bought. It is now check [12] here.

## 9.2 The rule is mechanical

The set is **derived, not listed**. A part is hand-soldered if either:

- **it has any through-hole pad** — read off the board, no maintenance; or
- **it is in `SALVAGE_ONLY`** — one entry since ECO-13 (`U1`, the CPU), and it cannot be
  derived, because a salvaged QFP is byte-identical in the file to a new one.

`np_thru_hole` does not count: an unplated mounting hole is a hole, not a joint.

The generator then **checks its own rule**: after applying the flags it sweeps every
footprint and fails the build if any part with a through-hole pad is still in the position
file and not DNP. A future ECO that adds a through-hole part cannot silently ship a CPL a
machine cannot execute.

## 9.3 Why this matters more than it looks

This is the change that makes [`scripts/bom_split.py`](../scripts/bom_split.py) mean
something. Its rule — borrowed from SOLAR-GLOW — is that **a part moves between "the
machine buys and places it" and "you hand-solder it" by changing the design, never by
editing a list**:

```
on board, not BOM-excluded, not DNP   ->  ASSEMBLY   (PCBWay buys and places it)
on board, BOM-excluded, not DNP       ->  HAND-BUY   (you buy it and solder it)
DNP, or a no-part footprint           ->  neither    (fiducials, jumpers, test pads)
```

That rule was **false on this board** until ECO-9, because MouseBiteLabs never encoded an
assembly split in the layout — reasonably, since upstream ships a design, not an assembly
order. The consign table in [`pcbway-assembly/README.md`](../pcbway-assembly/README.md)
was correct prose with nothing holding the board to it. Now the board is the record and
the prose is generated from it.

## 9.4 What comes out

`scripts/bom_split.py` writes five files into `pcbway-assembly/generated/`:

| | |
|---|---|
| `agbm-02-cxc-pcbway-assembly.csv` | **61 lines, 172 parts** — what PCBWay buys and places |
| `agbm-02-cxc-cpl.csv` | **172 placements** — the position file for those, and only those |
| `agbm-02-cxc-handbuy.csv` / `.md` | **8 lines** — the table above, with each part's reason |
| `agbm-02-cxc-not-populated.csv` | **58 lines, 67 footprints** — DNP, fiducials, jumpers, test pads |

**The assembly BOM is not orderable yet, and the tooling says so in a number rather than a
hedge: 33 of 61 lines — 105 of 172 parts — have no resolved MPN.** That is the same
sourcing gap `pcbway-assembly/README.md` §3 describes as "~35 unresolved links"; it is now
measured on every run instead of estimated once. It is a warning, not an error, because an
incomplete BOM is a known state of this work rather than a regression.

## 9.5 The decision this encodes, and how to reverse it

ECO-9 assumes **you fit the CPU and the SRAM yourself**, which is what the fork's brief
says. If you consign them to PCBWay instead — one of the four open build decisions in the
PCBWay notes — take `U1` out of `SALVAGE_ONLY` in
[`scripts/build_board.py`](../scripts/build_board.py). They go back into the position file
(the machine places them) while staying off the assembly BOM (you still supply the parts).
One edit, and every generated document follows.

The other five are not a decision. They have through-hole pins.

## 9.6 Verification

- `python3 scripts/build_board.py --check` — the board still rebuilds byte-for-byte, and
  the generator's own straggler sweep passes.
- `python3 scripts/bom_split.py --check` — the split is structurally consistent.
- `python3 scripts/check_consistency.py` check [12] — nothing in the position file lacks a
  BOM line, nothing is on both buy documents, and the committed buy documents are what a
  fresh run produces.
- `python3 scripts/test_checks.py` — strips `exclude_from_pos_files` off a hand-buy part
  and asserts the check catches it. A check that has never gone red is not known to work.

ECO-9 changes no copper, so **the [ECO-7](ECO-7_u2_supply_and_dnp.md) blockers still
block.** Both of those defects were ECO-5's and closed with it in
[ECO-13](ECO-13_rebase_onto_agbm02.md); what remains before fabrication is DRC, a
re-pour, and verifying the ClockxControl landing against a physical module.
