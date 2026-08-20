# ECO-17 — solder paste follows the placement list, and U2 gets the RAM we buy

**Board:** `AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb` — **254 paste apertures removed, one 3D
model corrected.** No copper, no nets, no placements.
**Changed:** `scripts/build_board.py`, `scripts/bom_split.py`, `scripts/check_consistency.py`,
`scripts/render_assembled.py`, `scripts/test_checks.py`
**Raised by:** the user, reading ECO-16's assembled renders.

---

## 17.1 A stencil cannot read `dnp`

ECO-9 encoded **who places what** in the board's attributes, and `scripts/bom_split.py` builds
the BOM and the position file from it. The paste layer never got the memo.

A stencil is cut from `F.Paste`/`B.Paste`. It knows nothing about `dnp` or
`exclude_from_pos_files`: paste goes down on every aperture and reflows whether a part lands on
it or not. On this board that was **254 apertures across thirteen parts nobody places**.

| Part | Apertures | Why it is not placed | What paste does |
|---|---|---|---|
| `U1` | 128 | the salvaged AGB-CPU, hand-fitted after reflow | 128 bumps on a 0.5 mm-pitch land, to be wicked off before the CPU can seat |
| `SW6` | 25 | D-pad — `dnp`, the build uses the rubber membrane | **a bump on each membrane contact** |
| `SW4` | 16 | A/B — same | **same** |
| `SW5` | 14 | Start/Select — same | **same** |
| `U2` | 48 | *placed*, but on **one** of two nested lands — §17.2 | solder under the body of the fitted chip |
| `VR2` | 7 | hand-soldered volume pot | bumps on its SMD pads |
| `P3` | 4 | hand-soldered headphone jack | same |
| `C3`, `C4`, `X1` | 6 | the crystal network ECO-7 marks DNP | same |
| `JP1` | 2 | a solder jumper meant to be **open** | **bridges it closed on reflow** |
| `R70`, `R71` | 4 | DNP | bumps |

**The buttons are the one that ruins a board.** `AGB-AB-Tact`, `AGB-Start-Select-Tact` and
`AGB-DPAD-Tact` are **dual-purpose footprints**: each carries the Alps tact-switch land *and the
membrane contact pads*, in one footprint. A default build uses the rubber membrane, so all three
are `dnp` — and a reflowed bump on a membrane contact destroys the flat gold surface the
conductive rubber has to sit on. Nothing recovers that except reworking every pad by hand.

**One of those pads was paste and nothing else.** `SW6` carries an unnamed `smd circle` on
`"F.Paste"` alone — a bare stencil dot with no copper under it. Stripping the paste layer from
that leaves `(layers )`, a pad on no layer at all, which is meaningless and which KiCad is under
no obligation to keep. Where the aperture *is* the pad, the pad is deleted with it. The board
diff is 253 layer lines, one whole pad, and one model.

**The rule is mechanical**, like ECO-9's: a pad keeps its aperture only if the machine will put a
part on it, and "not placed" is read off the board's own `dnp` / `exclude_from_pos_files`, never
from a list in the generator. The generator asserts it afterwards and refuses to write a board
that still has one.

## 17.2 U2 carries two nested land patterns and only one may be pasted

MouseBiteLabs' `AGB-SRAM_2` is a **dual land**. All 96 pads resolve to 48 pins, each with two
pads on the same net — an inner and an outer — so one footprint accepts either RAM:

| Pattern | Columns (local x) | Lead-tip span | Package | Which RAM |
|---|---|---|---|---|
| inner | −6.690 / +7.100 | 15.34 mm | TSOP-I-48 12.4 × 12 mm | salvaged OEM AGB-SRAM |
| **outer** | **−8.450 / +10.967** | **20.950 mm** | **TSOP-I-48 18.4 × 12 mm** | **CY62157EV30LL** |

The outer pattern's lead-tip span is **identical to three decimals** to KiCad's own
`TSOP-I-48_18.4x12mm_P0.5mm`, and Digi-Key lists the `CY62157EV30LL-45ZXIT` as *"48-TSOP I"*.
This fork's BOM buys that part, so the outer land is the one being used.

**Pasting both is not belt-and-braces, it is a short.** The inner pads of *adjacent pins* sit
0.5 mm apart with a 0.2 mm gap and carry **different nets** — `MA15`, `MA14`, and so on. Paste on
the unused pattern reflows **under the body** of the chip that is fitted, where a bridge between
two address lines can be neither inspected nor reworked.

So exactly one pattern is pasted, selected by `RAM_FITTED` in the generator. Flip it and
MouseBiteLabs' `JP2`/`JP3` straps together — his wiki: both bridged for the CY62157EV30LL, both
left open for a salvaged OEM part.

## 17.3 The body has to match the land

`U2`'s 3D model named `TSOP-I-48_12.4x12mm_P0.5mm` — the **salvaged** package. Correct for
MouseBiteLabs' default build, wrong for ours, and it is why ECO-16's renders showed a chip two
thirds the size of the one that will actually be on the board. The user caught it from the
picture.

The footprint origin is not the package centre for either pattern, so the model needs an offset
as well as a name: the midpoint of the two columns it belongs to, **+1.25875 mm** for the outer
land. Both come from the same `RAM_FITTED` switch, so the land that is pasted, the body that is
drawn, and the part the BOM buys cannot disagree.

Against the ECO-16 render, **3.66% of the pixels changed**: `U2` grew, and the membrane contacts,
`X1`'s pads and `U1`'s 128-pad land all went from grey to bare gold. That colour change *is* the
paste.

## 17.4 The position file now says where its origin is

The CPL emitted the board file's own `(at x y rot)` verbatim. Those y values are **negative** —
KiCad's origin sits above the board and y grows downward — and a position file full of negative
y with no stated datum is ambiguous to an assembly house: every part reads as off-board.

It now carries both, with the datum named in the header:

* `x_mm`, `y_mm` — millimetres from the board's **lower-left corner, y up**, which is what an
  assembly house expects
* `kicad_x`, `kicad_y` — the board file's own numbers, kept so nothing is lost

Check **[17b]** asserts every placement lands inside the 131.32 × 72.42 mm outline. Getting the
datum backwards mirrors every part about the board's mid-line — an error that looks entirely
plausible on a spreadsheet, and that this arithmetic catches.

**The rotation convention is still unverified and this ECO does not change that.** `rot` is
KiCad's own angle; PCBWay's zero reference per package family has not been checked against a
single part. What *can* be said now is that the CPL's rotation and the assembled render's
orientation are **the same number from the same field**, so the render is a faithful picture of
what the position file asks for — which makes it the thing to check the convention against, one
part at a time, before ordering.

## 17.5 What the gates hold

**Check [17]** — paste exists only on pads a machine will put a part on, and `U2` is pasted on
exactly the pattern its RAM uses, with a 3D body to match. Three assertions, and the last one
would have caught §17.3 on its own.

**Check [17b]** — every CPL placement lands inside the board outline.

**Two negative cases**, one per way this rots: an aperture restored on a membrane contact, and
`U2`'s unused land pasted again. Suite is **20 cases, 0 blind**.

A third bug surfaced while wiring it: check [12] carried **its own copy** of the CPL's column
list to regenerate the file for comparison, so adding a column made the check report the
freshly-written file as stale against its own stale idea of the format. `bom_split.CPL_COLUMNS`
is now the only copy. That is the third time in this audit that two implementations of one fact
have disagreed — after `geom.swallowed` (ECO-14) and `schematic_sources` (ECO-15).

## 17.6 Still open

* **The rotation convention**, per §17.4. Unchanged by this ECO, and now checkable against the
  renders.
* **`CP1`–`CP3` have no polarity marking** on a symmetric land. ECO-15 put them back on
  MouseBiteLabs' ±20% part; the marking is still absent and still wants adding before an
  assembly order.
* **A tact-switch build** must restore paste on `SW4`/`SW5`/`SW6`'s roundrect pads — but never on
  their membrane contacts. Clear the `dnp` and the generator does the rest.

## 17.7 Verification

* `python3 scripts/build_board.py --check` — byte-identical rebuild, 254 apertures stripped
  (253 layer lines rewritten and one paste-only pad deleted whole)
* `python3 scripts/check_consistency.py` — 0 errors across 19 checks
* `python3 scripts/test_checks.py` — 20 cases, 0 blind
* `python3 scripts/render_assembled.py` — 175/180 bodies, `U2` now the 18.4 mm package
