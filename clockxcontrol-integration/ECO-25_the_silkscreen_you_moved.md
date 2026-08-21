# ECO-25 — the silkscreen you moved, and the gate that could not see it

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

**Board:** five silkscreen changes — two refdes moved, three text items hidden. No copper.
**Changed:** `scripts/build_board.py`, `scripts/kicad10.py` (check **[19]**),
`scripts/test_checks.py`, `ECO-22`
**Raised by:** the user — *"I moved silkscreen on my upload that I don't see reflected in
the renders."*

---

## 25.1 They were right, and the reason is a flat error in ECO-22

ECO-22 compared the uploaded board against the committed one and reported it **functionally
identical**, listing every difference as a KiCad 10 artifact. That comparison covered
footprints, pads, vias and track coverage. **It never looked at silkscreen.**

The sentence *"No footprint, value, net or route was altered"* is true clause by clause. As
a summary it was wrong, because it implied a completeness the comparison did not have. The
consequence was not cosmetic: the five edits below were **never merged**, and every render
produced afterwards — including the regeneration in the previous commit — was drawn from a
board that did not contain them.

| | committed | uploaded |
|---|---|---|
| `C7` Reference | (0.0, −1.8) | **(−1.7944, 1.5128)** |
| `C7A` Reference | (0.0, −1.8) | **(3.1524, −0.6124)** |
| `C7A` Value | shown | **hidden** |
| `MOD1` Reference | shown | **hidden** |
| `MOD1` Value | shown | **hidden** |

## 25.2 Every one of them is a real fix

**`C7` and `C7A` are the same land in two places.** [ECO-19](ECO-19_stock_c7_land_restored.md)
restored the stock land as `C7A` at (91.9, −41.1) — the exact spot `C7` occupied before
ECO-6 moved it — and both footprints inherit MouseBiteLabs' refdes offset of (0, −1.8). Two
labels, one board coordinate, printed on top of each other. On a pair whose entire purpose
is *populate exactly one of these*, the silkscreen was unable to tell a builder which land
they were looking at. They now move apart, one down-left and one right.

**`MOD1`'s Reference and Value sat across the module body** — the one part of this board
where what a builder needs to see is the landing pattern, not a label. Hidden.

**`C7A`'s Value is hidden** because a DNP alternate does not need its capacitance on the
silkscreen. What matters there is *which land this is*.

All five are adopted into `build_board.py` verbatim, as coordinates rather than as an
opinion, so the generator reproduces the user's KiCad session exactly.

## 25.3 The gate had the same blind spot, and it was the gate written to catch this

[ECO-23](ECO-23_kicad10_companion.md) shipped check **[19]** two commits ago, describing it
as proving the KiCad 10 companion is *"the same board"*. It proved the same **copper**.
Demonstrated rather than assumed — move one refdes and change nothing else:

```
kicad10.compare() reports 0 difference(s) -> BLIND: a silkscreen move is invisible
```

`kicad10.graphics()` now extracts, format-neutrally on both KiCad 9 and KiCad 10:

* every `Reference` and `Value` placement — text, position, rotation, layer, **and whether
  it is hidden**
* every footprint graphic on silkscreen, fab, courtyard, mask, paste and the user layers,
  in local coordinates
* every top-level graphic on those layers

That is **508 text placements and 3,607 non-copper graphics**, all of which now have to
match. The same two mutations that were invisible are now caught by name:

```
a refdes MOVED     -> C7 Reference text placement differs:   (-1.7944, 1.5128, F.SilkS, False) -> (0.0, -1.8, ...)
a refdes UNHIDDEN  -> MOD1 Reference text placement differs: (0.0, -7.4, F.SilkS, True) -> (..., False)
```

`test_checks.py` gains a case that moves **only** silkscreen — the copper case that already
existed could never have caught this — bringing it to 27.

## 25.4 Why the renders looked unchanged, which is its own answer

Two different reasons, and both are correct behaviour:

* **the 9 2D views draw copper only**, so a silkscreen edit cannot appear in them. After
  this change `agbm02_front.png` is still byte-identical, as it should be.
* **the 4 raytraced views do show silkscreen** — and they were regenerated from a board
  that never received the edits.

The previous commit measured raytracer nondeterminism at a **max channel delta of 30–38**.
Re-rendering after this change gives **max delta 199** in the same view: an order of
magnitude clear of the noise floor, which is what a real silkscreen change should look like
against that background.

## 25.5 Verification

* `python3 scripts/build_board.py --check` — byte-identical rebuild
* a format-neutral silkscreen diff against the upload — **0 differences** across 508 text
  placements, 210 footprints carrying silk, and 360 top-level silk items

> ### ⚠ That "0 differences" was produced by a blind reader — see [ECO-26](ECO-26_the_third_blind_reader.md)
>
> The position pattern behind it was `(at x y)` anchored on the closing paren, which matches
> nothing against `(at 0 0 180)`. **Every `fp_text` on the board extracted an empty position**,
> so two texts in different places compared equal. One more edit was outstanding and invisible:
> `MOD1`'s `CLOCKXCONTROL` label, which the user had moved out from under MouseBiteLabs'
> silkscreen. ECO-26 fixes the reader, adopts the move, and makes a text item that yields no
> position an error rather than a match.
* `python3 scripts/kicad10.py --check` — copper, text placement and non-copper graphics all
  match
* `python3 scripts/check_consistency.py` — 0 errors
* `python3 scripts/test_checks.py` — **27 cases, 0 blind**
