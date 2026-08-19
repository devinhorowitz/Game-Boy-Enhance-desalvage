# ECO-7 — the U2 supply defect, and the DNP the ClockxControl build needs

Two things, both found by the component review in [`power-review/`](../power-review/README.md) and
then checked against the board geometry rather than taken on trust.

One is implemented here. The other is **not**, deliberately, because the fix the review proposed
would have destroyed the board and the correct fix needs KiCad's interactive router.

---

## 7.1 What is implemented

`X1`, `C3` and `C4` now carry `(attr smd dnp)` in
`AGBM-01_AA_1-2_GBE-plus-CXC.kicad_pcb`. Before this, the crystal and both load caps shipped as
ordinary fitted parts, so an assembly house would have soldered a crystal onto the node the
ClockxControl is trying to drive. The diff against the ECO-6 rev B board is exactly three lines and
touches no copper.

While confirming that, ECO-6's own write-up turned out to be **wrong about `C4`**. It said C4 is
"dangling once the crystal is gone." The netlist says otherwise:

```
CK1 ─┬─ R1 1.5M ─ CK2 ─ R41 2.2k ─ Net-(C4-Pad1) ─┬─ X1.2
     ├─ C3 27p ─ GND                               └─ C4 33p ─ GND
     ├─ X1.1
     └─ TP80
```

`X1` pad 2, `C4` pad 1 and `R41` pad 2 all sit on `Net-(C4-Pad1)`. Remove `X1` and C4 is still tied
to `CK2` through `R41`, so it is 33 pF hanging on the CPU's XOUT node through 2.2 kΩ, not a floating
part. The recommendation to depopulate it was right; the stated reason was not, and the real reason
is stronger. Corrected in both documents.

---

## 7.2 What is NOT implemented, and why

### The defect

`U2` pin 37 is the SRAM's supply pin, and on the ECO-5 board it has no path to `VDD2`.

ECO-5 extended the `U2` footprint with a third pad column at abs x = 100.31 so the longer
CY62157EV30LL body could land, and removed the copper that used to occupy that lane: two `VDD2`
vias at (100.800, −56.600) and (100.800, −55.200), three F.Cu `VDD2` tracks, and (undocumented) the
`Net-(Q5B-G)` via at (100.800, −62.150). ECO-5's own TODO is candid about this, and says the power
ties are "best finished with KiCad's interactive router." They were never finished.

**The severity is worse than the review stated.** The review said the chip is "powered only through
pins 12/16." Reading the pin functions off the board:

| Pin | Function on the footprint | Net |
|---|---|---|
| 12 | `CE2` | VDD2 |
| 16 | `NC/VCC` | VDD2 |
| **37** | **`VCC`** | VDD2 |

Pin 12 is `CE2`, a **control input**, not a supply. And per ECO-5's own pin-by-pin audit, pin 16 on
the CY62157 is **A18**, strapped high; it is `VCC` only on the OEM GBA part. So:

- with a **salvaged OEM RAM**, pin 16 may carry supply and the board may run;
- with the **CY62157EV30LL**, which is the entire point of ECO-5, **pin 37 is the only VCC pin and
  the chip has no supply at all.**

### Why the review's fix must not be applied

The review recommended restoring the two `VDD2` vias at their stock coordinates, at 0.95 confidence.
**Those coordinates are now inside ECO-5's third pad column**, which spans x 99.46 to 101.16. Each
proposed via would land on two pads of other nets:

| Proposed via | Overlaps |
|---|---|
| (100.800, −56.600) | `U2.34` `/CPU/MD_{10}`, `U2.35` `/CPU/MD_{3}` |
| (100.800, −55.200) | `U2.31` `/CPU/MD_{1}`, `U2.32` `/CPU/MD_{9}` |
| (100.800, −62.150) | `U2.45` `/CPU/MD_{15}`, `U2.46` `GND` |

Restoring them shorts `VDD2` to two data lines and `Net-(Q5B-G)` to a third and to ground. The
review verified that the sites lie inside the `VDD2` zone and the `In2` plane, which is true, but it
never checked them against the pad column ECO-5 added. That is exactly the failure mode a
high-confidence finding invites.

### Why there is no simple substitute site

Every alternative was searched, at 0.05 mm resolution, against exact pad rectangles rather than
circumscribed circles:

- **The `In2.Cu` `VDD2` plane does not reach.** At y = −58 (pin 37's row) it covers only x 84 to 89.
  At x = 97 the `In2` and `In1` planes are both **GND**. The nearest `In2` `VDD2` with real
  enclosure is the y ≈ −46 band, about 12 mm away.
- **The gap between the pad columns is a bus.** x 95.89 to 98.18 is filled with 24 parallel F.Cu
  links on a 0.5 mm pitch, one per pin, bridging the inner column to the outer. A 0.7 mm via pad
  cannot exist in a 0.5 mm pitch field.
- **The lane east of the third column is spoken for.** x ≥ 101.71 is needed to clear the pads, the
  `In2` `VDD2` plane ends at x ≈ 101.8, and ECO-5's own BYTE riser for `JP2` runs up x = 102.20.
- **A wide scan over x 78 to 104, y −66 to −44 returned five `VDD2` via sites total**, all in the
  y ≈ −46 band and none reachable from pin 37 without crossing the bus.

The corridor between `U2`'s left and right pad columns carries 55 F.Cu segments of MD-bus fanout, so
an F.Cu track west to the main `VDD2` pour is not available either.

**Conclusion: the pin-37 tie cannot be completed with the third pad column and the BYTE riser as
drawn.** This is a rework of that corner, not a patch. The options are to narrow or shift the third
pad column, move the BYTE riser, or bring `VDD2` in on a layer that is not currently carrying GND
there.

### `Net-(Q5B-G)` — a fix exists, and it still needs the router

**It is not "open" — it is routed, and broken in exactly one place.** That distinction was blurred
in the summaries of this document elsewhere in the repository and is now corrected there; the net
carries ten track segments and one via, and every one of them is MouseBiteLabs' own routing.

This one is tractable. The net runs from `U17` pin 1 on B.Cu, through a via at (104.380, −53.300),
along 10.54 mm **inside the In1 ground plane**, to the deleted via at (100.800, −62.150), and back
to B.Cu for `Q5` pin 3 and `R66` pin 2. With the via gone, `R66` holds `Q5B`'s gate high permanently
and the low-battery LED indication is dead.

**The stock board proves the diagnosis.** Consistency check [10] traces the net's islands on both
boards and diffs them:

| | islands | vias on the net |
|---|---|---|
| MouseBiteLabs AGBM-01 rev 1.2, as shipped | **1** — `U17.1`, `Q5.3`, `R66.2` all together | (104.382, −53.300) **and (100.800, −62.150)** |
| this fork, ECO-5 onward | **2** — `U17.1` \| `Q5.3`, `R66.2` | (104.382, −53.300) only |

Same ten segments on both. One via, deleted. This is unambiguously a fork regression against a
known-good reference, not an upstream gap — and the check keeps the comparison rather than trusting
that sentence, so if the stock board ever turns out to be broken too, it says so instead.

Scanning the In1 diagonal for a site clear of the pad column gives a usable window at
**t ≈ 0.10 along the run, (104.077, −59.240), 0.360 mm clearance and 1.55 mm hole-to-hole.** The via
itself is fine there. What is not fine is the B.Cu side: straight links from that point to `Q5.3`
and `R66.2` foul `Q5.2` and a net-227 segment, so the two B.Cu runs need real routing.

Left for KiCad rather than scripted in, for the same reason the review's fix was wrong: this corner
is dense enough that geometry has to be checked against a live DRC engine, not a static script.

---

## 7.3 Before you fab

1. **Do not fabricate the ECO-5 or ECO-6 board as committed.** `U2` pin 37 has no supply, and with a
   CY62157 that means no supply at all.
2. Rework the `U2` corner in KiCad to bring `VDD2` to pin 37, and re-pour. The zone fill in every
   board file in this repository is the stale stock fill; nothing has been re-poured since ECO-5.
3. Restore `Net-(Q5B-G)` with the via at (104.077, −59.240) and route its two B.Cu links.
   **Not at the stock site.** Restoring the deleted via where MouseBiteLabs had it is the same trap
   as the `VDD2` vias: (100.800, −62.150) now sits with **0.000 mm** gap to `U2.45` (`/CPU/MD_15`,
   pad 1.7 × 0.3 at (100.310, −62.050)) and 0.250 mm to `U2.46` (`GND`) — both inside a 0.7 mm
   annulus. Measured, not assumed.
4. Re-run the full differential check afterwards.


---

## 7.4 These blockers are now gated

`scripts/check_consistency.py` check [10] asserts **both defects are still present**, and goes RED
when either is fixed. That is deliberate. The moment somebody routes pin 37 or drops the missing
via, this document and three others become wrong, with nothing to notice — so the check fails and
names the four files that have to be corrected in the same commit.

A blocker that gets quietly fixed and leaves its scary paragraph behind is how a repository starts
lying about itself. See [`scripts/README.md`](../scripts/README.md).
