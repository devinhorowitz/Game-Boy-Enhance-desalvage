# ECO-22 — the DRC was never reading this board's rules

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

**Board:** one via deleted, `VDD3`'s last 1.3 mm moved from `F.Cu` to `B.Cu`.
**Changed:** `scripts/check_drc.py`, `scripts/pack_board.py`, `scripts/kisexp.py`,
`scripts/geom.py`, `scripts/build_board.py`, `scripts/check_consistency.py`
**Raised by:** the user, with a KiCad 10 save of the board and a 710-violation DRC report.

| | before | after |
|---|---|---|
| MouseBiteLabs' AGBM-02, re-poured | 695 violations | **203** |
| this fork, re-poured | 713 | **204** |
| **new, at positions his board does not have** | **55** | **1** — ECO-19's `C7A`, by design |
| real defects the old numbers were hiding | — | **1**, fixed below |

Nothing was cleaned up to get from 55 to 1. The old numbers were measured against the
wrong rulebook.

---

## 22.1 KiCad keeps the design rules in the *project*, not the board

`check_drc.py` wrote the board into an empty temporary directory and ran `kicad-cli pcb
drc` on it. There was no `.kicad_pro` beside it, so **KiCad fell back to its own built-in
defaults** — and has done since ECO-19 first stood the check up.

MouseBiteLabs has shipped a `.kicad_pro` inside `AGBM-02 Design Files.zip` the whole time.
It differs from KiCad's defaults in both directions:

| rule | his `.kicad_pro` | KiCad default | effect of getting it wrong |
|---|---|---|---|
| `min_hole_to_hole` | **0.5** | 0.25 | **hid a real drill collision** — §22.2 |
| `min_clearance` | 0.15 | 0.0 | |
| `min_track_width` | 0.1525 | 0.2 | |
| `min_via_diameter` | 0.4 | 0.5 | |
| `min_via_annular_width` | 0.15 | 0.1 | |
| `silk_overlap` | **ignore** | warning | 199 phantom violations |
| `lib_footprint_issues` | **ignore** | warning | 199 phantom violations |
| `text_height` | **ignore** | warning | 40 phantom violations |
| `silk_over_copper` | **ignore** | warning | 39 phantom violations |
| `silk_edge_clearance` | **ignore** | warning | 6 phantom violations |
| `lib_footprint_mismatch` | **ignore** | warning | 6 phantom violations |

He also ships **113 pre-triaged `drc_exclusions`**, which the defaults discard.

**489 of the 710 violations in the uploaded report are checks MouseBiteLabs deliberately
turned off.** They are silkscreen overlaps and library-comparison nits on a hand-built
design, and he decided years ago that they are not defects. Chasing them would have been
work spent making someone else's board conform to a rule set its author rejected.

`check_drc.drc()` now extracts his project out of the base zip and writes it beside the
board under the same stem, which is the only arrangement KiCad honours. Both the base and
this fork are measured against it, so the diff is finally comparing like with like.

> The uploaded `.kicad_pro` is **not** MouseBiteLabs' — it is what KiCad 10 writes for a
> project it has never seen: `min_clearance` 0.0, `min_hole_to_hole` 0.25,
> `min_resolved_spokes` **2** against his **1** (the source of all 16 `starved_thermal`),
> and every one of those six `ignore` rules promoted to `warning`. It is not committed. The
> repository reads his file out of the zip instead, so the gate and the shipped package can
> never drift from each other or from him.

## 22.2 What the right rulebook found: a drill collision, 32 µm over

With `min_hole_to_hole` at its real 0.5 mm, one violation appears that KiCad's 0.25 mm
default could never have shown:

```
[hole_to_hole] error: min 0.4995 mm; actual 0.4680 mm
    Via [VDD3] on F.Cu - B.Cu     @(97.100, -34.100)
    PTH pad S1 [VDD3] of P1       @(96.900, -35.200)
```

ECO-6 brought `VDD3` across on `B.Cu`, punched a via at (97.100, −34.100), and ran the last
1.3 mm to `P1` pad `S1` on `F.Cu`. The via's **drill** lands 0.4680 mm from `S1`'s 1.0 mm
hole. Hole-to-hole is a **mechanical** rule — it is about how close two drill hits can be
without breaking out — so both being `VDD3` buys nothing.

### The fix removes the hole rather than moving it

`P1` pad `S1` is `thru_hole` on `"*.Cu"`. **It is already on every layer**, so a `B.Cu`
track can land on it directly and the layer change was never needed. Measured along the new
corridor (97.400, −34.400) → (96.900, −35.200):

| | clearance to the nearest foreign copper |
|---|---|
| `B.Cu` — the new path | **0.8260 mm** |
| `F.Cu` — the path ECO-6 took | 0.1679 mm |

ECO-6 went to `F.Cu` and bought 0.30 mm of *track* clearance at the cost of a *drill*
collision, on the layer that had five times less room. The via is deleted, `VDD3`'s tail
stays on `B.Cu`, and the fork drops from nine added vias to eight.

Relocating the via instead needs ≈0.8 mm of travel before any spot satisfies both the
0.5 mm hole rule and the 0.2 mm clearance rule, and the best of those clears by **8 µm**.
Deleting a hole beats relocating one.

## 22.3 A KiCad 10 board reads as an empty board, and that nearly cost a wrong answer

The uploaded board is **file version 20260206, written by KiCad 10.0.5**. Ours is
20241229 / KiCad 9. The format changed underneath us:

* `(net 12)` on a segment or via became `(net "/CPU/TP8")`
* a pad's `(net 12 "/CPU/TP8")` became `(net "/CPU/TP8")`
* the `(net N "name")` declaration table at the top of the file is **gone**
* vias gained `(capping …)`, `(covering …)`, `(plugging …)`

Every net-reading regex in this repository was written against the KiCad 9 form. On a
KiCad 10 board they match nothing — and each one used to return an empty list and let the
caller carry on. The first comparison run printed **“theirs 0 segments”**, and the natural
reading of that is that 3,557 tracks had been deleted. Nothing had been deleted. The parser
had gone blind, exactly as it once did on CRLF.

`kisexp` now has `_refuse_empty()`, and `net_table()`, `vias()` and `geom.collect()` all
call it: **a reader that can see the token but parse none of it raises**, naming the file
version and the format change. Silence is never zero.

## 22.4 What the upload actually changed

Compared format-neutrally, the uploaded board is **functionally identical to the committed
one**. Every difference is a KiCad 10 artifact:

| | |
|---|---|
| 3,557 → 3,243 segments | KiCad 10 **merged collinear tracks** — 375 of ours became 61 of theirs, same copper |
| `MOD1` pads “changed” | `(at 7.025 1.0 180)` → `(at 7.025 1 180)`; a trailing zero |
| 152 → 204 fill polygons | the zones were **re-poured**, which is what ECO-14 §14.6 has been asking for |
| one `GND` via at (88.000, −44.300) → (87.987, −44.356) | 66 µm |

No footprint, value, net or route was altered.

## 22.5 The package now ships the rules

Opening this board without a project file is what produced the 710. So
`scripts/pack_board.py` now puts **his `.kicad_pro` in the deliverable zip**, under the
board's own stem, taken from the base zip unmodified — the same bytes `check_drc.py` gates
against, so the two cannot disagree.

## 22.6 Verification

* `python3 scripts/build_board.py --check` — byte-identical rebuild
* `python3 scripts/check_consistency.py` — **0 errors**, 2 pre-existing warnings
* `python3 scripts/test_checks.py` — **25 cases, 0 blind**
* `python3 scripts/check_drc.py` — base **203**, this fork **204**, **1 new** and it is
  `C7A`'s deliberate courtyard overlap; **0 unconnected** on both
