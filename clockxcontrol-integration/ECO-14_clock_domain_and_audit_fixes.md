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

## 14.2 One real DRC violation — **fixed**

| | was | now |
|---|---|---|
| `CXC_CLK` via | (47.450, −59.600) | **(47.500, −59.500)** |
| clearance to `C13` pad 1 (`VDD5`, `B.Cu`) | **0.1632 mm** | 0.2750 mm |
| **worst foreign clearance, all layers** | **0.1632 mm** | **0.2321 mm** |
| limited by | `C13` pad 1 | a `/CPU/CK1` `F.Cu` track |
| rule | the project's single `Default` netclass, **0.200 mm** | **passes** |

`C13` is unmoved by every ECO — `(at 46.1 -60.5 180)` on base and output alike — so the
violation was entirely this fork's via, and moving the via is the whole fix. The two
segments that meet it moved with it and were re-measured: the `F.Cu` leg from
(47.450, −60.850) clears by **0.3605 mm**, the `B.Cu` leg to (47.800, −59.250) by
**0.2707 mm**.

**That 0.11 mm nudge is the best available, and it is worth saying why the margin is only
0.032 mm.** A 0.05 mm grid search over a 3 × 4 mm corridor, then a second search around
`JP4`, put every alternative site *worse*:

```
+0.2321  (47.50, -59.50)   <- chosen
+0.2176  (47.50, -59.55)
+0.1750  (46.89, -61.50)
+0.0341  (45.93, -62.55)
-0.1205  (46.53, -64.45)
```

The corner is genuinely dense — `C13`'s pad below on `B.Cu`, `/CPU/CK1` and `/CPU/TP9` on
`F.Cu`, `/CPU/TP2` on `In2.Cu` — and **both limiting tracks are MouseBiteLabs', not ours**
(ECO-6's own `CK1` run is at x 42.5–44.4 and its `TP9` run at x 84–88, neither anywhere
near). So there was nothing of ours left to move.

The via keeps the board's **0.7 mm / 0.3 mm** geometry, which is what all 547 of
MouseBiteLabs' vias use. Shrinking it to 0.6 mm would have bought another 0.05 mm but put
the annular ring at 0.15 mm — exactly the project's `min_via_annular_width` — to buy margin
the move already provides.

---

## 14.3 The fiducials — **moved, and the pour held back**

> ### ⚠ The positions in this section are superseded by [ECO-20](ECO-20_drc_defects_closed.md)
>
> This section checked **copper** where ECO-13 had checked **components** — and it was still
> only one constraint out of five. It could not see the board's `gr_circle` shell holes, its
> 64 keepout zones, or soldermask apertures, so *"each spot is ≥ 3.0 mm from the board
> outline"* below is **wrong**: `FID2`/`FID5` were placed **inside** a 1.2 mm hole and
> `FID3`/`FID6` on the rim of another. KiCad's own DRC, first run in ECO-19, found four
> violations here. ECO-20 rebuilt the search, moved all six, and turned the margins into a
> ledger check [13] recomputes. **The `(clearance 0.55)` half of this section still stands
> and is still load-bearing.**

A fiducial is a mark a vision system finds by **contrast against bare substrate**. The pad
is 1 mm with a 0.5 mm `solder_mask_margin`, so the window is 2 mm across and needs a clear
radius of **1.00 mm** from centre. Measured to the nearest hard copper — track, via or pad:

| pair | was | clear | now | clear (F / B) | moved |
|---|---|---|---|---|---|
| `FID1`/`FID4` | (26.000, −8.000) | 1.064 mm | **(28.100, −9.600)** | **2.390 / 2.390** | 2.64 mm |
| `FID3`/`FID6` | (33.000, −69.000) | **0.768 mm** ✗ | **(31.000, −69.500)** | **2.399 / 2.478** | 2.06 mm |
| `FID2`/`FID5` | (106.250, −57.250) | 1.337 mm | **(110.850, −57.650)** | **1.800 / 1.918** | 4.62 mm |

`FID3`/`FID6` was the bad one: a `GND` via 0.768 mm away, its copper well inside the window.
`FID1`/`FID4` cleared by only 64 µm.

Every new spot is **≥ 3.0 mm from the board outline**, has **no footprint within 3 mm**, and
sits in populated copper rather than off the edge — the search rejected candidates that
merely *looked* clear because they were outside the board. The triangle stays deliberately
**scalene — 60.0, 80.7 and 95.7 mm between pairs** — so a machine cannot register the panel
180° out.

> The first sentence of that paragraph is **false**, and [ECO-20 §20.2](ECO-20_drc_defects_closed.md)
> is the correction. `geom.edge_segments()` read four of Edge.Cuts' five primitive types and
> silently dropped `gr_circle` — all 13 shell holes — so "3.0 mm from the outline" was
> measured against an outline with no holes in it. The scalene-triangle argument survives;
> the coordinates do not.

### Moving them was only half the fix

These pads are **netless and sit inside MouseBiteLabs' `GND` pours.** On a re-pour the zone
floods right up to them, leaving copper at `0.5 + zone_clearance = 0.7 mm` from centre —
**inside the 1.0 mm window.** Relocating them would have fixed nothing.

So each fiducial pad now carries **`(clearance 0.55)`**, a local override that pushes the
fill back to **1.05 mm** from centre. The window shows bare substrate, and it keeps doing so
after the re-pour that ECO-6 §6.8 requires.

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

**A thirteenth check, because twelve green ones missed both of the above.** Every check in
`scripts/check_consistency.py` was topological — what exists, what it is called, what it
connects to. **None could measure a distance**, which is exactly how a 0.1632 mm violation
and six unreadable fiducials shipped past all of them.

`scripts/geom.py` is the missing half: pads as rounded rectangles, tracks as inflated
segments, vias as circles, plus the board outline. Check **[13]** uses it to assert that
every via this fork adds clears MouseBiteLabs' copper by the project's own 0.200 mm netclass
rule, and that every fiducial has a clear 1.00 mm window *and* the local clearance that
keeps its pour back. It is honest about its limit: **it does not model zone fills**, and says
so in its own docstring rather than implying coverage it lacks.

Three cases were added to `scripts/test_checks.py`, one per way the fixed defects could
return — the via moving back, a fiducial landing on the via again, and a fiducial losing its
clearance override. All three fire; a fourth followed with check [14] below, and the suite is now
**12 cases, 0 blind**.

---

## 14.4b What building the renderer found

Two defects, both found the same way: by writing a **second independent implementation** and
watching it disagree with the first. Neither would have been found by re-reading the code.

### The picture and the gate counted different boards

`scripts/render_board.py` rings every object a stale pour swallows. It came out with **19**. Check [14],
written earlier in this same ECO, reported **15**. One of them was wrong about the board sitting
in front of both of them.

Check [14] was. It counted **footprints whose refdes was new**, tested at the **footprint
origin**, on **`fp.layer`**, against the net of **pad 1**. Four approximations stacked, and the
last one hides the worst:

* A footprint origin is not a pad. `MOD1`'s origin sits 5–7 mm east of its own landings, because
  the module body extends past the landed sites. Testing the origin answers a question about a
  point where there is no copper.
* One net for a whole footprint is wrong the moment a part has pads on different nets. `MOD1`'s
  three pads are `TP2`, `TP9` and `TP8`; testing all three against `TP2` reported one hit on
  `VDD35` where the pads really straddle **`VDD35` and `VDD2`** — two different rails.
* `fp.layer` is where a footprint is *placed*, not the layers its pads occupy.
* **And the blind spot: a refdes-keyed rule cannot see a part that MOVED.** `C7` is
  MouseBiteLabs', not this fork's, so `if ref in base_refs: continue` skipped it — but ECO-6
  *moves* `C7` from (91.9, −41.1) to (93.1, −37.4) to open the module window, and at the new spot
  **`C7.2` (`GND`) lands inside the `VDD35` pour**. A real net-to-net overlap, rail to rail,
  invisible to the gate that exists to count exactly that.

The fix is not a better rule in two places, it is **one rule in one place**: `geom.added()` keys
on **geometry, not refdes** — a moved pad is new copper at its new coordinates — and
`geom.swallowed()` measures **at each pad, on the layers that pad occupies, against that pad's
own net**. Check [14] and the renderer both call it, so they can no longer disagree. The 19
objects are now ledgered line by line with a reason each, and the check fails if the set changes
at all.

### Nothing had ever asked whether the module physically fits

Every gate in this repository measured copper. `MOD1` is an 18.65 × 12.00 mm object that sits on
the board, and whether it clears its neighbours rested entirely on a table in ECO-6 §6.6 — which,
it turned out, had been measured off `fab_fit.png`, one of the pre-rebase renders. There was no
way to tell whether the numbers still held.

They did. Every courtyard row reproduces on AGBM-02 to three decimals. That was luck, not design,
and `geom.neighbour_gaps()` now holds them in check [13] with a 0.35 mm floor. Two things the
measurement taught that the old table did not say:

* **Same side, or it is not a neighbour.** A sweep that ignores which side a part is on puts
  `C12` at **0.055 mm** and `U17` at 0.65 mm. Both are on `B.Cu` — 1.6 mm of FR4 away. The
  0.055 mm reads like an imminent collision and is nothing at all.
* **The rows were not all the same measurement.** Parts with a courtyard were measured
  courtyard-to-body; bare test pads have no courtyard and were measured pad-copper-to-body. Under
  one "courtyard gaps" heading, a reader compares `TP18`'s 0.93 against `U2`'s 0.55 as if they
  were the same quantity. The table now names the basis per row.

The tightest same-side gap is **0.400 mm**, and it is this fork's own `TP83`/`TP84`/`TP85` — sat
deliberately just clear of the body so the three wires stay short. `U2` at 0.550 mm is the next,
and it is a package edge rather than a joint anyone has to get an iron onto.

---

## 14.5 Recorded rather than fixed — and what the follow-up pass then fixed

**FIXED — the renders are no longer pre-rebase, because they are no longer hand-made.** Every PNG
in `clockxcontrol-integration/render/` had an identical git blob SHA before and after ECO-13 —
they showed the AGBM-01 board while being displayed as "the layout" and "the copper diff". The
first draft of this section said regenerating them needed KiCad. That was wrong, and the reason
it was wrong is the more useful finding: ECO-6 §6.6 said the views came from "a renderer built
against the board file directly", and **that renderer was never committed**. The pictures were
orphaned outputs of a lost tool — the same defect as the hand-kept `.kicad_mod`, in a different
medium.

`scripts/render_board.py` is the missing generator, written against the board through the same
`kisexp`/`geom` readers every gate uses. Seven views, all derived: `agbm02_front`, `agbm02_back`,
`agbm02_cxc_diff`, `agbm02_cxc_placement`, `agbm02_cxc_landings`, `agbm02_cxc_fit` and the 1:1
600 dpi print sheet. Nine pre-rebase PNGs were culled. New check **[15]** re-renders each view
from the committed board and compares the **raw pixel buffer** — pixels rather than PNG bytes, so
a Pillow build changing its deflate settings is not mistaken for a board that moved — and a second
rule fails on any PNG in `render/` the generator does not produce, since an ungenerated file is
exactly how the AGBM-01 images survived four ECOs. One image is ledgered as exempt:
`dmgc_cpu_01_2-5_cxc_footprint.png` is MouseBiteLabs' own land pattern on his DMG-Color CPU-01,
rendered from *his* gerbers, and nothing here can regenerate it.

The renderer draws the **stored** pour, not an approximate re-pour. The old one did the latter,
which is a friendlier picture and a worse one: it showed a board that does not exist in the file
and concealed the very defect check [14] exists to gate.

**STILL OPEN — three of the module's six through-holes have no landing.** Drawing the lattice
instead of describing it made its geometry exact: a **2 × 3 grid on a 2.500 mm pitch in both
axes**, at `MOD1`-local x ∈ {4.525, 7.025} and y ∈ {−1.5, 1.0, 3.5}. Landed are (4.525, 1.0) →
`SEL`, (7.025, 3.5) → `L`, (7.025, 1.0) → `R`; the other three are `F.Fab` circles of radius
0.635 mm and nothing else. The landed set spans both columns and two of three rows — an **L**, not
a row, a column or a diagonal. `render/agbm02_cxc_fit.png` now shows all six, the landed three
ringed green and the unlanded three grey, so the question is visible rather than buried in prose.

Two things fell out, neither of which closes it:

* **2.500 mm is not 0.100 inch.** A 0.1″ lattice is 2.540 mm, so an imperial module would put
  this footprint 0.04 mm out per step and 0.08 mm across the grid. Small against a plated hole,
  but it is a photo-derivation artifact and one pass with calipers settles it.
* **The tempting explanation is wrong, and it is worth recording that it is.** Three landed sites
  and three wire pads (`TP83`/`TP84`/`TP85`) invites "six sites, six signals — three landed, three
  wired". ECO-6 §6.7 item 3b kills it: the module's `CLK`/`V+`/`V−` pads *have no holes*, which is
  precisely why they are wired rather than landed. So the three unlanded lattice sites are three
  unexplained plated holes, and **a physical module is still the only way to settle it**.

**Three of the five items above were fixable without KiCad, and were fixed.** They are kept here
rather than moved out, because a defect that vanishes from the record cannot be checked for
having come back.

**FIXED — the shipped footprint no longer has an independent existence.**
`clockxcontrol-integration/footprint/ClockxControl_GBA_GBC.kicad_mod` had the centre text at size
1.2 against the board's 1.05, carried four extra silk strings, and named its reference `MOD` not
`MOD1`; pads, mask margins and outlines were already identical. The fault was not the drift, it
was that a second hand-kept copy existed at all: check [2] compared the zip to the tree and never
the `.kicad_mod` to the board, so any future divergence would have been just as invisible.
`build_board.py` now grows a `library_footprint()` that **derives** the `.kicad_mod` from the
board's own `MOD1` block — strips the placement, restores `REF**`, keeps the pads, the outline and
the four texts the board actually carries (`CLOCKXCONTROL`, `SEL`, `L`, `R`) — and emits it
alongside the board on every run. 3,709 characters of hand-kept file became 3,181 of generated
one. New check **[2b]** re-derives it from the shipped board and compares; `--no-footprint`
suppresses the emission for anyone who wants the board alone.

**FIXED — `TP83`/`TP84`/`TP85` and `JP4` now carry `exclude_from_pos_files`.** The generated CPL
was correct anyway, because `bom_split.py` keys off `exclude_from_bom` — but that was the
splitter's rule saving an attribute set that was wrong, and the wrongness would have surfaced the
moment anyone opened the board in KiCad and exported a position file by hand. The attribute now
matches MouseBiteLabs' own convention for the same kind of object: their `TP18` and `TP80` are
`exclude_from_pos_files`, their `TP27`–`TP29` are `exclude_from_pos_files dnp`. Ours are
`exclude_from_bom exclude_from_pos_files` — not bought, not placed, but not `dnp` either, because
unlike Nick's they are landing pads this fork actually intends to be etched.

**STILL TRUE, NOW GATED — zone fills are stale, and that is the state the deliverable ships in.**
All 14 added pads and all 9 added vias lie inside foreign-net poured copper; 8 are genuine
net-to-net overlaps, two of them rail-to-rail. This is documented in ECO-6 §6.8, ECO-7 and ECO-13
as "re-pour before fab" and it was equally true on the AGBM-01 base — but it means **plotting
gerbers from this file without opening KiCad and running Fill All Zones produces a shorted
board.** The state has not changed; what changed is that it is no longer un-gated. New check
**[14]** hashes the `filled_polygon` set against the base's (152 polygons, `e94ca194ae163914`)
and re-counts the objects sitting in foreign pours. It is deliberately the ECO-13 shape — a check
that **goes red when the problem is fixed** — because on the day someone opens KiCad and re-pours,
three documents' "re-pour before fab" paragraphs become lies, and [14] will fail until they are
corrected in the same commit.

---

## 14.6 What a human should verify before fabricating, in order

1. **Scope XIN on the first build** — §14.1. The supply tap is settled (it matches the vendor's
   own `S1` = `VDD3`), but insideGadgets publishes no output-level spec, so the peak at the
   CPU's clock input is unknown to everyone. One trace answers it.
2. **Open in KiCad, re-pour, run DRC.** §14.2's violation is fixed; this is to catch
   anything the generated copper still hides from a hard-copper-only model.
3. **The module's landing geometry and hole lattice against a physical part** — §14.5. Two
   specific questions now, not one: *which* three of the six lattice sites the module actually
   needs landed, and whether its pitch is the 2.500 mm this footprint models or the 2.540 mm of
   an imperial 0.1″ grid. Calipers and a continuity beep answer both.
4. **The CPL rotation convention** against PCBWay's per-package zero reference.
5. **Lay a real module on `render/agbm02_cxc_1to1_600dpi.png`** — print at 100%, check the 10 mm
   ruler measures 10 mm, then confirm the body and the lattice line up before anything is ordered.

---

## Verification

* `python3 scripts/build_board.py --check` — byte-identical rebuild after the `PADS` change
* `python3 scripts/pack_board.py --check` — package matches the tree (22 members)
* `python3 scripts/bom_split.py --check` — 68 assembly lines / 5 hand-buy / 180 placements
* `python3 scripts/check_stock.py --offline` — 182 of 185 buyable refs resolved, 3 unresolved
  by decision (`MOD1`, `SP1`, `U1`)
* `python3 scripts/render_board.py --check` — all 7 views re-render pixel-for-pixel
* `python3 scripts/check_consistency.py` — **0 errors, 3 warnings** across 16 checks; check [10]
  still green under the corrected pad transform, and [2b], [13]'s mechanical-fit half, [14]'s
  hazard ledger and [15] are new here
* `python3 scripts/test_checks.py` — **16 cases, 0 blind**: every check this ECO added has a
  mutation that makes it fail
* Audit provenance: 44 agents, 1,139 tool calls, every finding adversarially verified against the
  board files before it was acted on. Two findings this document does **not** carry were refuted on
  re-derivation: a claimed missing `B.Cu` cartridge keepout (it is present on AGBM-02, verbatim)
  and a claimed 0.195 mm gap on the button runs (the nearest base endpoint is 0.000126 mm).
