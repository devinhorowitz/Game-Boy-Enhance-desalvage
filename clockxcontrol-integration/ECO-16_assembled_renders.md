# ECO-16 — the board as PCBWay assembles it

**Board:** `AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb` — **unchanged.** No copper, no attributes.
**New:** `scripts/render_assembled.py`, four raytraced views, `render/assembled-manifest.json`
**Changed:** `scripts/check_consistency.py` (checks [13] and [15])
**Borrowed from:** `devinhorowitz/solar-business-card` — its `scripts/render.py`, which is
in THAT repository, not this one

---

## 16.1 What was borrowed, and what was left behind

Solar-Glow's own `render.py` (in that repository) raytraces its presentation imagery through
`kicad-cli`. Its *targets* were no use here — it renders **bare** boards and deliberately
strips every component body. What was worth taking is the three disciplines wrapped around
the four-line `kicad-cli` call, each of which exists because that project got burned:

1. **Every target renders from a throwaway copy**, never the committed board. The transforms
   that make a picture honest would corrupt the file if applied in place.

2. **Zones are refilled on the copy before rendering.** `kicad-cli pcb render` has no
   `--refill-zones`; it draws the fill as *stored*. Solar-Glow published imagery of a
   previous board for a week because of this, and proved it afterwards by diffing a render
   before and after a refill (3.5% of the pixels in the affected window changed while a
   control region stayed bit-identical).

3. **Model resolution is reported out loud.** A missing 3D model is invisible as an error
   and obvious as a lie: KiCad draws nothing for a path it cannot resolve and says nothing,
   so the picture just comes back with fewer parts on it.

Discipline 2 matters more here than it did there. Check **[14]** exists precisely because
this repository's stored fill is MouseBiteLabs' from before the fork added any copper, and
**19 added objects sit inside foreign-net pours**. A render off the stored fill would show a
board that cannot be built. Refilling the *copy* is what makes the picture true while the
committed board stays stale on purpose — so [14] stays green and the three "re-pour before
fab" paragraphs it guards stay honest. The refill fills 99 zones to 16,993.8 mm² of copper.

## 16.2 Discipline 3 earned its keep immediately

**149 of 189 model references are `.wrl`. Ubuntu's `kicad-packages3d` ships 7,237 files and
not one `.wrl`.** So 79% of the bodies would have silently failed to draw, and the render
would have come back looking like a mostly-bare board with no error anywhere. The throwaway
copy rewrites `.wrl` → `.step` wherever the `.step` exists — KiCad's own pairing convention —
and the report counts the rewrites. **182 of 189 resolve** afterwards.

**The board's model paths are split across three env vars**, not one: `${KICAD6_3DMODEL_DIR}`
(2), `${KICAD8_3DMODEL_DIR}` (148) and `${KICAD9_3DMODEL_DIR}` (39). MouseBiteLabs' design has
been carried across three KiCad generations and the paths record it. A KiCad 9 install defines
only the last, so 150 of 189 would resolve to nothing. All four are passed with `--define-var`.

Five models are absent from the stock library because they are MouseBiteLabs' own vendor
downloads, which his design-files zip does not ship: `CSS-1310TB` (`SW1`),
`Same_Sky_SJ3-35083B-TR` (`P3`), `acm2520-3p-t002` (`EM1`/`EM2`),
`TPS63802DLAR--3DModel-STEP-269445` (`U5`/`U13`) and `Unnamed-SOLID` (`VR2`). They are named
in every run rather than quietly missing.

## 16.3 "As assembled by PCBWay" is not "the board with its parts on"

PCBWay places **180 of 251 footprints — 70 front, 110 back.** Five are hand-solder, 66 are
DNP, fiducials, jumpers and test pads. The set comes from `bom_split.classify()`, imported
rather than re-implemented, so the render and the buy documents cannot give different
accounts of the same build. On `agbm02_pcbway_bottom.png` you can read the consequence
directly: `P3`, `VR2` and `SP1` are bare land patterns.

| View | What it is |
|---|---|
| `render/agbm02_pcbway_top.png` | front, exactly the parts PCBWay's line places |
| `render/agbm02_pcbway_bottom.png` | back, the same — 110 of the 180 placements are here |
| `render/agbm02_finished_top.png` | front, after you have hand-soldered the rest |
| `render/agbm02_finished_bottom.png` | back, the same |

The two pairs differ by 3.6% and 2.8% of their pixels — mostly `U1`, the salvaged AGB-CPU.

**`P1` and `P4` nearly got left out of the finished view.** They carry `dnp` *on top of*
`exclude_from_bom`, so `classify()` returns `"none"` for them — correct for the assembly
house, which leaves them off entirely, and wrong for a picture of a finished board, which
certainly has its cartridge connector fitted. The finished targets keep the hand-solder set
by name, taken from `build_board.THRU_HOLE_REASONS` and `SALVAGE_ONLY`. `X1`/`C3`/`C4` stay
off: ECO-7 marks the crystal DNP for ClockxControl builds, and a finished ClockxControl board
really does not have one — the render now says so visually.

`MOD1`, `P1`, `P4` and `SP1` are kept and still invisible, because they carry **no 3D model
at all** — `MOD1` because it is this fork's own footprint and insideGadgets publish no model
for the ClockxControl, the other three because MouseBiteLabs' footprints do not carry one.
Every run names them, so nobody has to wonder whether the render or the board is wrong.

## 16.4 What the first render found: a crystal floating in space

The first assembled view came back with a grey slug hovering nine millimetres above the top
edge of the board, casting its own shadow.

It is **MouseBiteLabs' own**, in AGBM-02 as shipped: an unannotated `Crystal_HC49-4H_Vertical`
footprint, reference `REF**`, **zero pads**, parked at `(8.89, -81.888)` — outside `Edge.Cuts`.
Almost certainly a leftover reference for the crystal option that `X1`/`C3`/`C4` implement.
No fab makes it, because it is outside the outline. It is not this fork's to delete from his
file. And it must not appear in a picture captioned "as PCBWay assembles it", so the throwaway
copy strips the bodies of anything whose origin falls outside the board outline, and says
which.

**The cosmetic problem was not the finding.** `bom_split.classify()` returns **`"assembly"`**
for it — it is not `dnp` and not `exclude_from_bom`, so nothing in the classification rules
excludes it. The only thing keeping a through-hole crystal off the position file is the `*`
in its refdes. Annotate that footprint, or relax the `*` filter, and PCBWay is told to place
a crystal nine millimetres off the board.

Check **[13]** now warns on any footprint outside the outline that `classify()` does not
exclude. It found exactly one, and this is it.

## 16.5 Why these are not pixel-gated like the 2D views

Check [15] holds `scripts/render_board.py` to a pixel-exact re-render, because that renderer
is pure Python and its output is a function of the board alone. A raytrace is a function of
the board **and** KiCad's build **and** the 3D library, so pixel equality across machines is
not a property worth asserting — a gate that fails on somebody's KiCad version is a gate
people learn to ignore.

What [15] asserts instead is the thing that actually goes wrong: the manifest records how
many bodies resolved per view, and the check fails if a named render is missing and reports
the resolution rate and the bodyless set. It warns, rather than failing, when the assembled
renders have not been made on this tree at all — KiCad 9 is not a dependency this repository
otherwise has.

A second bug surfaced here: `--only` used to **rewrite** the manifest with its single target,
dropping the other three from the record, after which [15] reported the real, present PNGs as
ungenerated orphans. A partial run must narrow what it re-renders, not what the repository
knows about. It merges now.

## 16.6 Reproducing this

KiCad 9 is not installed by default in this environment. On Ubuntu 24.04:

```sh
curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x245D5502FAD7A805" \
  | gpg --dearmor -o /etc/apt/keyrings/kicad.gpg
echo "deb [signed-by=/etc/apt/keyrings/kicad.gpg] \
  https://ppa.launchpadcontent.net/kicad/kicad-9.0-releases/ubuntu noble main" \
  > /etc/apt/sources.list.d/kicad9.list
apt-get update && apt-get install -y --no-install-recommends kicad kicad-packages3d
python3 scripts/render_assembled.py --check     # toolchain and model library
python3 scripts/render_assembled.py             # ~4 min for four views
```

Ubuntu's own `kicad` is **7.0.11**, which cannot open this board at all — the file is KiCad 9
format (`version 20241229`).

## 16.7 Verification

* `python3 scripts/render_assembled.py --check` — kicad-cli 9.0.9, 182/189 bodies resolve
* `python3 scripts/build_board.py --check` — byte-identical; the committed board is untouched
* `python3 scripts/check_consistency.py` — 0 errors; [13] warns on `REF**`, [15] green
* `python3 scripts/test_checks.py` — 18 cases, 0 blind
