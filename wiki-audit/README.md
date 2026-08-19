# The wiki audit — every ECO in this fork, checked against what Nick actually built

Derivative of MouseBiteLabs *Game Boy Enhance*, CC BY-SA 4.0.

This fork has changed twelve things about the AGBM-01. Every one of them was reasoned from
the schematic, the PCB, and datasheets. **None of them had been checked against the
author's own written record.**

So: the [MouseBiteLabs project wiki](https://github.com/MouseBiteLabs/Game-Boy-Enhance/wiki)
— all 21 pages — read end to end, against every ECO in this repository. The question was
not "is our reasoning sound," it was **"did we quietly undo something Nick fought for."**

Two answers came back that changed the board, one that changed a document's reasoning, and
one that is now the largest open risk in the package.

| | Finding | Outcome |
|---|---|---|
| **A** | `R3`/`R4`/`R64`: the PCB annotation is stale, and our BOM was ordering it | **fixed** — [ECO-12 §12.1](../clockxcontrol-integration/ECO-12_wiki_audit_corrections.md) |
| **B** | ECO-8 trimmed `VOUT3` 108 mV; wrong trade for an overclocked board | **reverted** — [ECO-12 §12.2](../clockxcontrol-integration/ECO-12_wiki_audit_corrections.md) |
| **C** | ECO-11 §11.2's premise about `D1` was contradicted by the wiki | **rewritten** — conclusion survives |
| **D** | ECO-5's RAM land extends the opposite way from the one Nick shipped | **fixed** — [ECO-13](../clockxcontrol-integration/ECO-13_rebase_onto_agbm02.md) rebased onto AGBM-02 |
| **E** | Nick tried an SMPS on `VDD2` and rejected it on audio | **recorded** in the power review |
| **F** | Ten ECO decisions actively corroborated | no action |

---

## A. `R3`, `R4`, `R64` — we were ordering values Nick never used

**The single most important thing this audit found**, because it was live in our own
output, not merely a doubt in a document.

ECO-8 §8.4 found the AGBM-01 schematic and PCB disagreeing on three resistors and deferred
it. ECO-10 §10.3 deferred it again — *"buying precision parts of a value that may be wrong
is waste."* `scripts/mpn_overrides.json` recorded how to settle it: *"measure the trip
point on a built board, **or ask MouseBiteLabs**."*

The wiki is MouseBiteLabs answering. The full evidence chain is in
[ECO-12 §12.1](../clockxcontrol-integration/ECO-12_wiki_audit_corrections.md); in short:

* the **AGBM-02 PCB** — same AA design, one revision later, identical supervisor circuit —
  carries `5.1k / 33k / 200k`, so Nick fixed the annotation on the newer board;
* both AA **README BOMs** buy `5.1k / 33k / 200k`;
* the wiki states the resulting thresholds — **2.3 V** and **2.1 V** — and `5.1k/33k` gives
  **2.309 V** while the PCB's `1k/10k` gives **2.200 V**;
* the build guide's **Test 4** sweeps 2 V to 3 V expecting the change at 2.3 V.

**Why it mattered here and not upstream.** Nick's builders order from the README, so they
have always fitted the right parts; the stale PCB text harms nobody. **We** built ECO-9 to
derive the PCBWay BOM from the board's `Value` fields — the right rule, and the reason the
stale text became an order. A board built from our BOM would have warned ~100 mV late
(halving a 20-minute-to-an-hour warning window), blinked at 7.2 Hz instead of 3.6 Hz, and
run `U10`'s anti-flicker filter 4.9× lighter than designed.

Fixed, and the four thresholds are now asserted at generation time so the build fails
rather than shipping a board that warns in the wrong place.

---

## B. `VOUT3` — ECO-8's 108 mV was the wrong trade for *this* fork

ECO-8 took `R23` from 1.78 M to 1.69 M, moving `VOUT3` from **3.336 V to 3.228 V** to save
6.1 mW. The reasoning was sound *in general*. It is wrong for a board whose entire premise
is a 1.75× overclock and whose owner asked for margin.

`VDD3` is the CPU's 3.3 V I/O ring and, through the cart switch, `VDD35` — the cartridge
supply. That is the bus the overclock stresses. 8.2 mW at 1.75× is 0.86 % of the load,
about three and a half minutes of a 6 h 47 m session, bought with 3.2 % of the rail's
headroom. And the build guide's **Test 3** reads *"VDD3 to GND: 3.3V."*

Reverted in [ECO-12 §12.2](../clockxcontrol-integration/ECO-12_wiki_audit_corrections.md).
It also repaired something ECO-8 broke without noticing: `C41` was sized against 1.78 M, so
the trim shifted the feedforward zero 5.3 % and ECO-10 then faithfully preserved the
*shifted* value. 178 k × 150 p restores Nick's `26.7 µs` exactly.

Everything ECO-10 bought is kept — the 10× rescale, which was the part that mattered, and
the 0.1 % thin film.

---

## C. `D1` — our premise was wrong, our conclusion was not

[ECO-11 §11.2](../clockxcontrol-integration/ECO-11_gate_drive_and_D1.md) refused the power
review's `D1` finding, and one of its arguments was that the schematic assigns `D1` no
duty, so the reverse-battery reading was an over-read.

**The schematic doesn't. The wiki does, in its first paragraph:**

> Starting from the batteries on the left, `D1` provides reverse polarity protection in the
> event a user somehow jams the AA batteries in backwards. In this instance, the batteries
> will short circuit and a (large) negative voltage will be prevented from hitting the rest
> of the system.

So the duty *was* assigned, and our inference that `D1` was an ESD clamp was wrong.

But read what Nick wrote. **"The batteries will short circuit"** — he states the mechanism
and accepts it. `D1` is a *sacrificial crowbar*: its job is to clamp the node so nothing
downstream sees a large negative voltage, and a diode driven past `IFSM` fails **short**,
which clamps harder than the working diode did. The specified function is delivered either
way.

The numbers are unchanged (500 mA `IFSM` against 4–7 A available; `F1` is not in the loop,
verified from the netlist), and so is the decision: **`D1` is not changed.** §11.2 has been
rewritten to say this for the right reason, and the "no effective reverse-battery
protection" language — written against the wrong premise — is now stated accurately: `D1`
protects the console, as documented; it does not protect the pack, and was never meant to.

---

## D. ECO-5's RAM land goes the opposite way from the one Nick shipped

**This is now the largest open risk in the package, and it is not one this session can
close.**

The *Schematic Explanation* page says the CY62157EV30LL was blocked by mechanics:

> the replacement part is *longer* than the original footprint. I would have included pads
> for it on the AGBM boards, but it's large enough that it would also **interfere with the
> plastic rim around the screen on the front shell**, keeping it from closing properly. …
> A project for a future revision, perhaps. Maybe a project for you, dear reader!

ECO-5 is that project. But the wiki has moved on since that paragraph was written —
*Feature Configurations* and *Required Parts* both document the CY62157EV30LL as a
**shipped, supported option on AGBM-02 and AGBM-12**, with `JP2`/`JP3` solder bridges.
**Nick solved it.** And the AGBM-02 design-files archive committed in this repository contains
the answer.

Comparing the two 96-pad `U2` lands, both at the same board origin `(88.0, −57.8)`:

| | added column | pad-row span | body centre |
|---|---|---|---|
| stock `AGB-SRAM` (72 pads) | — | columns at −6.69, 7.10, 10.97 | — |
| **AGBM-02** `AGB-SRAM_2` | **x = −8.45** (pins 1–24) | 19.42 mm | x = **+1.26** |
| **ours** (ECO-5) | **x = +12.31** (pins 25–48) | 19.00 mm | x = **+2.81** |

Both are supersets of the stock salvage land, so a donor `AGB-SRAM` fits either, and the
pin ordering is the same on both — ours is not mirrored. But **Nick extended the land
toward −x and we extended it toward +x**, putting our CY62157 body **1.55 mm further +x**
than the placement he physically built and fitted in a shell. Our copper reaches
x = 101.16 against his 99.72.

Nick's stated obstruction was the front-shell screen rim, and the direction he chose to
escape it is the direction we did not.

**Corroborating that vertical clearance in this region is real**, the build guide's Step 6b
carries a warning about a part 46 mm away:

> Ensure the crystal oscillator, `X1`, sits flush on the board and is not raised up by any
> extra solder. If it's raised up too much, then you might have interference with the
> screen.

### Correction: this cannot be done as a footprint swap

An earlier version of this section recommended replacing ECO-5's land with AGBM-02's
`Bucketmouse:AGB-SRAM_2` geometry, calling it "a 24-pad relocation and re-route." **That was
wrong, and testing it is what proved it wrong.**

Nick's land and Nick's routing are one design. On AGBM-01 the channel immediately west of
`U2`'s left pad column is where **the entire RAM address bus escapes** — 37 F.Cu segments
carrying `MA_1`…`MA_15`, `~WE_RAM`, `~LB`, `~UB` and GND, fanning out from board x = 81.31
toward the CPU. Dropping his pad field at x = −8.45 onto that copper was tested
geometrically, segment against pad rectangle, and it **shorts 15 of the 24 new pads across
12 nets**:

```
pin  7 (/CPU/MA_{9})  <- MA_{10}, MA_{11}, MA_{12}
pin  9 (NC)           <- MA_{8},  MA_{9},  MA_{10}
pin 12 (VDD2)         <- MA_{8},  ~WE_RAM, GND
pin 16 (VDD2)         <- ~LB, ~UB
                                        … 15 of 24 in total
```

This is exactly what Nick meant by *"it would be quite an undertaking to re-layout that
portion of the board."* He could put the column there on AGBM-02 **because he re-routed the
fanout**; ECO-5 went east because east was comparatively empty — 14 segments and no address
bus against 58 segments and all of it.

So the direction difference stands as a **finding**, and the mechanical risk stands, but the
remedy is not a footprint swap onto this layout. See §D2.

---

## D2. The real remedy: AGBM-02 is the base this fork should have been built on

The two layouts are far closer than "different board" suggests. Measured across every
footprint:

| | |
|---|---|
| shared reference designators | **230** |
| **at byte-identical positions** | **217** |
| moved | 13 — `U5`, `L1`, `L2`, `EM3`, and ten converter passives |
| only on AGBM-01 | `C40 C41 R21 R22 R23 R55` — the LTC3527 feedback network |
| only on AGBM-02 | `U13`, `JP2`, `JP3`, eight converter passives, `REF**` |

**AGBM-02 is AGBM-01 with two regions redone**: the LTC3527 replaced by twin TPS63802s, and
the RAM corner given the CY62157 land plus the `MA17` and `/BYTE` straps. Everything else is
in the same place — including `C7` at exactly `(91.9, −41.1)`, the one part ECO-6 has to move
out of the ClockxControl window, verified present at identical coordinates on both boards.

Rebasing this fork onto AGBM-02 would therefore:

* **delete ECO-5 outright** — the CY62157 land, `JP2`/`JP3` and the shell fit all come from
  Nick, validated, instead of from us, unvalidated;
* **close both ECO-7 blockers**, because both are ECO-5's damage — `U2` pin 37's missing
  `VDD2` path and the severed `Net-(Q5B-G)` (AGBM-02 has it whole, one island, verified);
* **delete ECO-12 §12.1**, because AGBM-02 already carries `5.1k/33k/200k`;
* **delete ECO-10's LTC3527 divider work and ECO-12 §12.2**, because those six refs do not
  exist on AGBM-02;
* **carry ECO-6, ECO-7, ECO-8, ECO-9, ECO-11 and ECO-10's audio/decoupling work across**
  largely unchanged, since their parts are all at identical positions; and
* **pick up 29 mW** — Nick's measured 141 mW idle against AGBM-01's 170 mW.

**This was done.** [ECO-13](../clockxcontrol-integration/ECO-13_rebase_onto_agbm02.md) is
the record. Every prediction above held: ECO-5 deleted outright, both ECO-7 blockers closed,
ECO-12 §12.1 and §12.2 and all of ECO-10's `Value` swaps deleted, ECO-6/7/8/9/11 carried
across, and `U2` moved from the salvage list to the assembly BOM at
`CY62157EV30LL-45ZXIT` — **a build now needs one donor chip, not two.**

Two things the rebase turned up that this audit had not predicted:

* **Our ClockxControl clock jumper was `JP3`, which is his `/BYTE` strap on AGBM-02.** The
  documentation trap flagged in §D's smaller findings was worse than described — it was a
  refdes collision, not just a naming confusion. Ours is now `JP4` and his instructions read
  correctly against this board.
* **`C70`/`C71` are a gap in his own BOM.** 27 pF coupling caps on the hotkey touch nets,
  fitted (not DNP) on both AGBM-01 and AGBM-02, listed in neither README. Sourced here, with
  the reasoning recorded — the two parts that would have matched this board's other
  dielectric families are NRND and obsolete respectively.

### Two smaller things from the same comparison

**`JP2`/`JP3` mean different things on our board than on Nick's.** On AGBM-02, `JP2` ties
`U2` pin 17 (`MA17`) to **GND** and `JP3` ties pin 47 (`/BYTE`) to **VDD2**; *Feature
Configurations* tells builders to bridge both for a new RAM chip. On ours, `JP2` is the
`/BYTE`→`VDD2` strap and **`JP3` is the ClockxControl clock jumper** (`/CPU/CK1` ↔
`CXC_CLK`) that ECO-6 added. A builder cross-reading Nick's page against our board gets
`JP2` right by coincidence and `JP3` wrong. Bridging our `JP3` is harmless — on a CXC build
it is the configuration you want anyway — but the collision is a documentation trap and is
now recorded.

**`MA17` is handled, differently but correctly.** Nick straps it to GND through `JP2`; ECO-5
straps it to `VDD2` with a zero-copper solder bridge between pins 16 and 17. Verified on our
board: `U2.16 = VDD2` at `(−6.69, 1.75)`, `U2.17` unconnected at `(−6.69, 2.25)` — adjacent
pads on 0.5 mm pitch. The wiki permits both (*"needs to be grounded or tied to VDD2"*). No
regression. Both are hand operations a pick-and-place will not perform, which is a note for
the assembly documentation, not a defect.

---

## E. Nick tried an SMPS on `VDD2` and rejected it — on audio

The power review's Tier-2 list proposes replacing LDOs with switching regulators. The wiki
says he went there first and came back:

> in my (admittedly early) testing I found that with a SMPS for the 2.5V supply I could
> hear more audio noise than with an LDO, so the minimal lost power is worth it in my view.

Audio quality is the stated design goal of this project, and the whole grounding scheme,
the 2.5 V buffer and the separate audio LDO exist to serve it. He also gives the honest
caveat himself — he has not retested since fixing the audio other ways.

He does **not** reject switching regulators generally: **AGBM-02 is the TPS63802 board**,
and he measured it. That is the number the review should have been using:

| Board | Main converter | Idle |
|---|---|---|
| Stock GBA | — | 134 mW |
| **AGBM-02** | **TPS63802** | **141 mW** |
| AGBM-11 | LTC3527 | 160 mW |
| **AGBM-01** | **LTC3527** | **170 mW** |

**29 mW, 17 % of idle, measured on real hardware.** Recorded in
[`power-review/README.md`](../power-review/README.md), with the `VDD2` rejection alongside
it so nobody re-proposes the part he already ruled out.

---

## F. What the wiki confirmed — ten decisions that hold

Recorded because "we checked and it was fine" is a result.

1. **`PTC1` (ECO-8).** The wiki gives its purpose — *"providing an easy way of
   troubleshooting during assembly without having to replace blown fuses"* — and notes its
   series resistance is why the LED and bootloop sensing sit **before** it. Verified on our
   board: `VBATT = {F1.2, PTC1.1, R9.1, SW1.1, D2.2}`, so `R9`→`U3` and the `SW` taps are
   all upstream of `PTC1`. ECO-8's lower-Rho part reduces a drop Nick calls out as
   unwanted. Aligned with intent, and the sense taps are untouched.

2. **`F1` (ECO-8).** *"a 2A fuse"* — our BOM-fix value is 2.00 A. The stale `0467001.NR`
   annotation (a 1 A part) was the error, exactly as ECO-8 said.

3. **The 2.0 V brownout threshold (ECO-11 §11.3).** *"pulls the EN net to GND whenever the
   voltage on the VDD pin drops below 2V … technically, the EN net is pulled to GND when
   the batteries drop below 2.03V."* Confirms the schematic's *"below 3V"* note is the
   stale one and the AA boards trip at 2 V. §11.3 stands, and Nick's 30 mV `R9` drop
   figure independently confirms our `/VFILT` arithmetic.

4. **The latch fix (ECO-11 §11.1) has an acceptance test Nick already wrote.** Test 1:
   > Momentarily short circuit EN to GND *without* turning the switch off. … **If EN
   > doesn't drop to 0V and stay there after you remove the short**, make sure you're
   > actually shorting it…

   That is precisely the behaviour ECO-11 argues a worst-case NDC7002N cannot guarantee.
   Nick attributes the failure to 2N3904/2N3906 pinout variants — a real cause — but the
   test's existence shows this step fails in the field, and ECO-11 adds a second mechanism
   that produces the identical symptom. Not a regression: a marginal test made less
   marginal.

5. **Power sequencing (ECO-10).** The thing Nick says shelved the project for a while:
   > the core (VDD2, the 2.5V supply) must be powered on first, *then* VDD3 … If you do it
   > in reverse, the CPU gets very hot and draws a bunch of power.

   ECO-10 rescaled both feedback dividers 10×. The sequence is set by `PGOOD` release, not
   by divider impedance, and the rails are unchanged. ECO-12 §12.2 additionally restores
   `VOUT3`'s feedforward time constant to Nick's exact value. **No effect on the sequence.**

6. **`C10`/`C12` (ECO-12, ECO-10).** The wiki explains the asymmetry — the blinking
   circuit's filter is heavier because a nearly-flat pack sags harder under load. Our board
   has `C10 = 0.1 µF`, `C12 = 10 µF`. Unchanged, and the reason is now on record.

7. **`DL1`/`R25` (ECO-8).** *Feature Configurations* explicitly invites this:
   > you can select any color you want for the LEDs, given that they have a 0603 footprint
   > … **To increase the brightness**, decrease the resistance … High Power LED Resistor:
   > `R25`.

   ECO-8 swapped to an InGaN green and raised `R25` 3.3 k → 22 k — the sanctioned knob,
   turned the sanctioned way.

8. **ECO-7's DNP of `X1`/`C3`/`C4`.** The build guide warns `X1` can foul the screen if it
   sits proud, and suggests the donor crystal for clearance. A ClockxControl build removes
   the part and the risk. **Improvement, not regression.**

9. **`U7` (ECO-8).** The Sallen-Key filter is Nick's own design at ~16 kHz, built from a
   published calculator; ECO-10's 0.1 % pass targets `f0` and `Q`. Nothing in the wiki
   suggests he wanted the tolerance he got — the opposite: audio quality is the stated
   goal.

10. **`CP1` stays.** Nick flags it as an unexplained empirical fix:
    > I found without it, there is a DC voltage across the speaker coil. I'm actually not
    > sure why that is.

    Exactly the kind of hard-won part a cleanup pass deletes. No ECO touches it, and none
    should without a scope on a real board.

---

## Provenance

Wiki cloned from `https://github.com/MouseBiteLabs/Game-Boy-Enhance.wiki.git`, 21 pages,
read 2026-08-19. Board comparisons run against the AGBM-01 and AGBM-02 design-files archives committed under
`AGBM-01 (AA Batteries)/` and `AGBM-02 (AA Batteries)/`, parsed with `scripts/kisexp.py`.

Every quotation is verbatim. Every number that touches the board is asserted somewhere in
`scripts/` — the four supervisor and rail thresholds in `build_board.py`, the swap tables
in `check_consistency.py` check [3], the part numbers in check [6].
