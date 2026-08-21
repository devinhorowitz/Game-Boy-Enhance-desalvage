# ECO-26 — the third blind reader, and the label it hid

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

**Board:** `MOD1`'s `CLOCKXCONTROL` silkscreen label moves off MouseBiteLabs' silkscreen.
**Changed:** `scripts/kicad10.py`, `scripts/build_board.py`, `scripts/test_checks.py`, `ECO-25`
**Raised by:** the user — *"Still not right, I moved the clockxcontrol silkscreen so it
didn't overlap with the AGB silkscreen."*

---

## 26.1 One character of regex

ECO-25 widened check [19] to cover silkscreen and reported the fork's silk **identical** to
the user's upload. It was not. `MOD1`'s `CLOCKXCONTROL` label had been moved from **(0, 0)**
— dead centre of the module body, printing over MouseBiteLabs' own silkscreen — out to
**(−2.538, 2.7004)**. The comparison could not see it, and the reason is the position
pattern:

```python
r'\((?:xy|start|mid|end|center|at) ([-\d.]+) ([-\d.]+)\)'
```

That is anchored on the closing paren after the second number. A text item is placed with a
**rotation**:

```
(fp_text user "CLOCKXCONTROL"
    (at 0 0 180)
```

Three numbers. The pattern matches **nothing**, `re.findall` returns `[]`, and the item's
position becomes the empty tuple. Every `fp_text` on this board is placed with a rotation, so
*every text on the board* extracted as `()` — and two labels in different places compared
equal. Demonstrated rather than argued:

```
SHIPPED  ours=[]                theirs=[]                  -> compare equal? True
FIXED    ours=[('0', '0')]      theirs=[('-2.538','2.7004')] -> compare equal? False
```

## 26.2 The third time, in one session

| | the reader | what it returned | what it looked like |
|---|---|---|---|
| ECO-13 era | `kisexp.load` on CRLF | 0 footprints | "this board has no parts" |
| [ECO-22](ECO-22_the_project_file.md) | `geom.collect` on KiCad 10 | 0 segments | "3,557 tracks deleted" |
| **here** | `graphics` on rotated text | empty positions | **"the silkscreen is identical"** |

The first two produced a `_refuse_empty()` guard in `kisexp`, written specifically so that a
reader which can see the token but parse none of it **raises** instead of returning nothing.
Then ECO-25 added a new extractor without applying that discipline to it, and the same class
of bug landed in the very gate built to catch this failure.

So `_pts()` now enforces it locally: **a `text` item that yields no position raises**, naming
the item. There is no reading of this board where a label has no place on it.

```
guard fires: MOD1 fp_text: a text item parsed to NO position. A blind reader here reports
every text on the board as unchanged, so this refuses to compare rather than return a
false match.
```

Rotation is captured now too, rather than discarded — a label turned 180° is a different
label, and the old tuple could not have expressed that either.

## 26.3 What the fixed reader finds

With the pattern corrected, a full graphics diff against the upload returns exactly **one**
outstanding difference, and it is the one the user described:

```
MOD1  OURS  : ('text', 'F.SilkS', 'CLOCKXCONTROL', ((0.0,    0.0,    180.0),))
MOD1  THEIRS: ('text', 'F.SilkS', 'CLOCKXCONTROL', ((-2.538, 2.7004, 180.0),))
```

Adopted. After it, the diff across ref/value placements, footprint silk graphics and
top-level silk items is **0, 0, 0** — this time measured by a reader that can see text.

`test_checks.py` gains a case that moves that label back on top of the AGB silkscreen, held
to the reason `non-copper graphics differ`. It is deliberately separate from ECO-25's case: a
`(property ...)` and an `fp_text` are different code paths, and only the second was blind.
**28 cases, 0 blind.**

## 26.4 Verification

* `python3 scripts/build_board.py --check` — byte-identical rebuild
* full graphics diff vs the upload — **0 differences**, fixed reader
* the blind-reader guard fires when a text position cannot be parsed
* `python3 scripts/kicad10.py --check` — 508 text placements + 3,607 non-copper graphics match
* `python3 scripts/check_consistency.py` — 0 errors
* `python3 scripts/test_checks.py` — **28 cases, 0 blind**
