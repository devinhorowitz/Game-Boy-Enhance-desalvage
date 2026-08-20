# ECO-14 — the clock domain question, and what a 44-agent audit of ECO-6/ECO-7 found

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

After [ECO-13](ECO-13_rebase_onto_agbm02.md) moved this fork onto MouseBiteLabs' AGBM-02, the
ClockxControl integration was audited against the new base by six independent lenses — pad
collisions, segment shorts, end-to-end connectivity, module keep-out, the crystal/DNP clock path,
and rebase delta — with every finding handed to an adversarial verifier told to refute it, then a
completeness critic asked what nobody had checked.

**The provenance question it was launched to answer came back clean.** AGBM-02 is
MouseBiteLabs' newest board and this fork sits on it, unmodified:

| | |
|---|---|
| upstream HEAD | `48e2dc3`, contained in this branch |
| the three design archives | **byte-identical** to upstream |
| `AGBM-02_AA_1-1.kicad_pcb` saved | **2026-08-16** |
| `AGBM-01_AA_1-2.kicad_pcb` saved | 2026-06-04 |
| `AGBM_LiPo_1-3.kicad_pcb` saved | 2026-06-28 |
| AGBM-12 | no design files exist — his wiki says it is not complete |

His on-board **dot-code revision stamp** confirms it independently. The 12 × 3 silkscreen lattice
at `x 122.7…129.3, y −20.0…−18.8` beside the text `'26` encodes the revision by leaving **one
position empty**; the scheme validates itself on two of three boards:

| Board | empty position | reads | file saved |
|---|---|---|---|
| AGBM-01 | col 6, row 1 | first third of June '26 | 2026-06-04 ✓ |
| AGBM-11 | col 6, row 3 | last third of June '26 | 2026-06-28 ✓ |
| **AGBM-02** | **col 7, row 1** | **first third of July '26** | 2026-08-16 — six weeks later |

AGBM-02 also carries a dot **0.025 mm off the lattice** at June's position: he re-filled June by
hand and punched out July. His silkscreen stamp is one revision behind his file, so **a board
fabbed from this repository will read "July '26"**. Cosmetic, recorded so nobody re-derives it.

**What the audit found is a different matter.** The integration lands on AGBM-02 without a short,
without a broken net, and inside the module window — but one open question outranks everything
else in this package, and it is not a geometry question.

---

## 14.1 The clock is 3.3 V, the pin it drives sits in a 2.5 V domain — and that is insideGadgets' own design

**RESOLVED against the vendor's documentation, 2026-08-20.** The short version: **this fork does
exactly what insideGadgets specifies, on the same net they specify.** What follows is kept because
the circuit fact is real and worth knowing, and because the resolution changes what to do about it
from "re-tap the supply" to "do not."

### The circuit fact

The module is powered from `VDD3` = 3.3 V — `TP84`, the `V+` wire pad ECO-6 adds, is
`(net 10 "VDD3")`. The CPU's oscillator is not in that domain:

```
U1 at (63.09, -53.12, 0.0), west edge, x = 51.840
  pin 111  GND
  pin 112  GND
  pin 113  /CPU/CK1   y = -54.620   <- XIN, the pin the module drives
  pin 114  /CPU/CK2   y = -54.120   <- XOUT
  pin 115  VDD2       y = -53.620
  pin 116  GND
  pin 117  VDD2       y = -52.620
```

| | |
|---|---|
| XIN → nearest `VDD2` CPU pin | **1.000 mm** (pin 115) |
| XIN → nearest `VDD3` CPU pin | **5.000 mm** (pin 103) |
| `U8`, the regulator making `VDD2` | `NCV8164ASN250T1G` — the **`250`** suffix is the 2.5 V fixed option |

Point-in-polygon against the board's stored `filled_polygon` blocks puts `VDD2` directly under pins
113, 114 and 115 on `In2.Cu`, with pin 115 also inside an `F.Cu` `VDD2` pour, and **no `VDD3`
copper under the oscillator on any layer.** MouseBiteLabs built a deliberate `VDD2` island there.

### Why that is not a defect in this fork

insideGadgets' GBA installation instructions, verbatim from
[the product page](https://shop.insidegadgets.com/product/gba-clockxcontrol/):

> Device V+ to GBA SI
> Device V- to GBA GND
> Device CLK to GBA CK1
> Device 1 to GBA TP2 (Select) or TP3 (Start)
> Device 2 to GBA TP9 (L trigger)
> Device 3 to GBA TP8 (R trigger)

**"GBA SI" is a typo for the pad silkscreened `S1`**, and that is now confirmed from their own
install photo rather than inferred: in
[`IMG_6317.jpg`](https://shop.insidegadgets.com/wp-content/uploads/2019/11/IMG_6317.jpg) — their
GBA install shot, not vendored here — the red `V+` wire is soldered onto the
rightmost pad of the `C2 S2 C1 S1` group at the right-hand end of the cartridge connector's solder
row. Enlarged, the silkscreen and the joint are unambiguous. ("SI" as serial-in would be a nonsense
place to draw 12 mA.)

And `S1` is the 3.3 V rail — read off both boards:

```
AGBM-02 base : P1.C2 -> /CPU/IN35   P1.S2 -> VDD5   P1.C1 -> VDD35   P1.S1 -> VDD3
our CXC board: P1.C2 -> /CPU/IN35   P1.S2 -> VDD5   P1.C1 -> VDD35   P1.S1 -> VDD3
```

`TP84` is on `VDD3`, and `VDD3` reaches `P1.S1`. **Our wire pad is the same electrical node the
vendor tells you to solder to.** The only difference is convenience: we expose it 3.8 mm from the
module instead of asking for a wire across the board.

So the 3.3 V-module-into-a-2.5 V-domain-pin arrangement is **insideGadgets' design**, shipped since
2019 and installed on stock GBAs — which have the identical CPU with the identical `VDD2`
oscillator island. It is not something this fork introduced, and **the `VDD2` re-tap floated in the
first draft of this section is now explicitly withdrawn.** `TP18` exists and is a real `VDD2` test
point, but powering the module from it would deviate from the vendor's specification on no
evidence.

### What is still genuinely unknown

**insideGadgets publishes no electrical specification for the module.** The product page gives no
supply voltage, no supply range, no `CLK` output level, no drive strength, and no mention of level
shifting. The only electrical figures on it are current: *"Consumes about 12mA of additional
current and when the GBA/GBC/DMG is overclocked, it too will use 40-60mA more."*

So the peak voltage actually presented at XIN **cannot be answered from documentation** — by us or
by anyone. It needs a scope on a running module. Two things follow:

* The [power review](../power-review/README.md)'s `clk-source-series-termination` finding is right
  that the *source* is `VDD3`-referenced — the module runs on `VDD3` by vendor spec. Its open
  question is the *destination*: XIN's local rail is `VDD2`, so an `Rs` sized to land the far end
  at 3.3 V is sizing against the source rail, not the input's. **That series-termination item stays
  open**, and it is the right place for this to be resolved with a measurement.
* If you have a scope on the first build, capture XIN. That single trace answers it.

## 14.2 One real DRC violation, introduced by ECO-6's own copper

| | |
|---|---|
| object | `CXC_CLK` via at **(47.450, −59.600)**, ø0.7 / drill 0.3, `F.Cu`–`B.Cu` |
| against | `C13` pad 1 — `VDD5`, `B.Cu`, roundrect 0.9 × 0.95, corner r 0.225, at (46.875, −60.500) |
| centre-to-centre | 1.0680 mm |
| **copper-to-copper** | **0.1632 mm** |
| rule | the project's single `Default` netclass, **clearance 0.200 mm** |

`C13` is unmoved by every ECO — `(at 46.1 -60.5 180)` on both base and output — so the violation is
entirely this fork's via. It **fails the netclass by 0.037 mm**, passes the board's own
`min_clearance` of 0.150, and is comfortably inside PCBWay's 0.127 mm capability. So it is a rule
violation, not a manufacturability one — but it will raise a DRC error at the re-pour step, and it
falsifies [ECO-6 §6.4](ECO-6_clockxcontrol_footprint.md)'s *"new violations introduced by this
ECO : 0"*, which was measured on AGBM-01. That claim is now annotated in place.

---

## 14.3 The fiducials are not clear, and ECO-13 said they were

[ECO-13 §13.6](ECO-13_rebase_onto_agbm02.md) states *"Each spot was clearance-checked against
AGBM-02."* **That check tested component clearance only, not copper.** Against copper:

* all six sit **inside `GND` pours**, so their 2 mm clear-mask windows are over foreign copper;
* `FID3`/`FID6` at (33.0, −69.0) additionally sit on top of an **upstream `GND` via** at
  (34.000, −68.500) — 1.118 mm centre-to-centre, inside the 1.0 mm mask-window radius.

Electrically this is harmless — the pads are netless, so being swallowed by the `GND` pour just
ties inert copper to ground. **It defeats the fiducial's purpose**: a fiducial is a mark a vision
system finds by contrast against bare substrate, and one sitting in a copper field with a via
through its window is not reliably machine-readable.

Not fixed here because it wants a placement decision rather than a patch: the three spots were
inherited from ECO-5's AGBM-01 layout and were never chosen for AGBM-02's copper.

---

## 14.4 Fixed in this ECO

**`scripts/kisexp.py` — `pad_positions()` rotated pads the wrong way.** It used
`radians(rot)` where KiCad's y-down coordinates need `radians(-rot)`, so **every pad on a
footprint rotated by anything other than a multiple of 180° landed in the wrong place**, silently
swapping pad 1 and pad 2 on every 90° part. `net_islands()` is built on it, and check [10] — this
repository's blocker gate — is built on `net_islands()`.

The test that settles it, on the shipped board: for each pad on a rotated footprint, ask which sign
puts it nearer a track endpoint **of its own net**.

```
-rot nearer: 200      +rot nearer: 16      tie: 3
```

and the `-rot` winners include exact **0.000 mm** hits (`R39.1`, `R39.2`, `C30.2`) that sit
1.55–1.65 mm away under `+rot`. A pad sitting exactly on its own track endpoint is ground truth.
Check [10] still passes after the fix, so its conclusion was right — it just was not reliably
derived.

**`scripts/build_board.py` — `MOD1`'s three landing pads resolved by net *number*.** `PADS`
carried the literals `71`, `13`, `12` and was the last place in the generator naming a net by
number; `WIRE_PADS` and `JP4` both go through `NET[]`. All three kept their numbers across the
rebase, which is the kind of luck that hides a bug rather than preventing it — had one moved, the
module's `L` button would have soldered onto whatever net inherited 13. Now resolved by name; the
board rebuilds byte-identically, which is the proof the numbers were the same.

**The `JP3` → `JP4` rename never reached the documents.** ECO-13 renamed our clock jumper to
`JP4` because `JP2`/`JP3` are MouseBiteLabs' RAM straps on AGBM-02 — but
[ECO-6](ECO-6_clockxcontrol_footprint.md)'s build sheet still said **"Bridge `JP3`"**, as did
`clockxcontrol-integration/README.md` in five places and `ECO-9`. A builder following it would not
start the module, and on a salvaged OEM RAM would drive `/BYTE`, a pin the original chip leaves
`NC`. **This was the most dangerous defect the audit found** and it was one the rebase created.
Corrected everywhere, with the reason stated at the build step.

**Two smaller document defects.** ECO-6 called `CXC_CLK` "new net 238"; on AGBM-02 it is **241**.
ECO-6's build step said to find the jumper by a `CXC CLK` silkscreen label — that string is the
footprint's **Value**, which renders on `F.Fab`, not silkscreen; the step now gives its position.

---

## 14.5 Open, and recorded rather than fixed

**The renders are pre-rebase.** Every PNG in `clockxcontrol-integration/render/` has an identical
git blob SHA before and after ECO-13 — they show the AGBM-01 board. They are displayed as "the
layout" and "the copper diff". Flagged in the README; regenerating them needs KiCad.

**Three of the module's six through-holes have no landing.** `MOD1` lands pads at local
(4.525, 1.0), (7.025, 3.5) and (7.025, 1.0); the other three lattice sites exist only as `F.Fab`
circles (`GHOSTS` in the generator). The landed set is an **L**, not a row or column split, which
is not what a "GBA half / GBC half" explanation would predict. No document says why. If the lattice
is three buttons × two terminals rather than six independent pads, one landing per button leaves
the module's button interface open. **Verify against a physical module** — this is the same open
item as the landing geometry being photo-derived.

**The shipped footprint does not match the board.**
`clockxcontrol-integration/footprint/ClockxControl_GBA_GBC.kicad_mod` has the centre text at size
1.2 against the board's 1.05, carries four extra silk strings, and names its reference `MOD` not
`MOD1`. Pads, mask margins and outlines are identical. Check [2] compares the zip to the tree and
never the `.kicad_mod` to the board.

**`TP83`/`TP84`/`TP85` and `JP4` lack `exclude_from_pos_files`.** The generated CPL is correct
anyway, because `bom_split.py` keys off `exclude_from_bom` — but that is the splitter's rule saving
an attribute set that is wrong. MouseBiteLabs' own equivalents (`TP27`–`TP29`) are `dnp`.

**Zone fills are stale, and that is the state the deliverable ships in.** All 14 added pads and all
9 added vias lie inside foreign-net poured copper; 8 are genuine net-to-net overlaps, two of them
rail-to-rail. This is documented in ECO-6 §6.8, ECO-7 and ECO-13 as "re-pour before fab" and it was
equally true on the AGBM-01 base — but it means **plotting gerbers from this file without opening
KiCad and running Fill All Zones produces a shorted board.** No gate in this repository is
zone-aware.

---

## 14.6 What a human should verify before fabricating, in order

1. **Scope XIN on the first build** — §14.1. The supply tap is settled (it matches the vendor's
   own `S1` = `VDD3`), but insideGadgets publishes no output-level spec, so the peak at the
   CPU's clock input is unknown to everyone. One trace answers it.
2. **Open in KiCad, re-pour, run DRC.** Expect the one violation in §14.2.
3. **The module's landing geometry and hole lattice against a physical part** — §14.5.
4. **The CPL rotation convention** against PCBWay's per-package zero reference.
5. Fiducial placement, if you want machine-readable ones — §14.3.

---

## Verification

* `python3 scripts/build_board.py --check` — byte-identical rebuild after the `PADS` change
* `python3 scripts/check_consistency.py` — 0 errors; check [10] still green under the corrected
  pad transform
* `python3 scripts/test_checks.py` — 8/8 negative tests firing
* Audit provenance: 44 agents, 1,139 tool calls, every finding adversarially verified against the
  board files before it was acted on. Two findings this document does **not** carry were refuted on
  re-derivation: a claimed missing `B.Cu` cartridge keepout (it is present on AGBM-02, verbatim)
  and a claimed 0.195 mm gap on the button runs (the nearest base endpoint is 0.000126 mm).
