# ECO-19 — the stock `C7` land comes back, unpopulated

**Board:** `C7A` added at (91.9, −41.1), DNP. No net changes, no routing, no copper moved.
**New:** `scripts/check_drc.py` — KiCad's own DRC on a re-poured copy, diffed against the base.
**Changed:** `scripts/build_board.py`, `scripts/geom.py`, `scripts/check_consistency.py`
**Raised by:** the user.

---

## 19.1 The argument

ECO-6 moved `C7` out of the module window because it was the one part standing in it. That
bought the ClockxControl a home and quietly cost something: **third-party mods that solder to
`C7` where it has always been lose their landmark.** A board that gains an overclocker by
giving up compatibility with everything else is a **side-grade**, not an upgrade.

`C7` sits at **(91.9, −41.1) on AGBM-01 and on AGBM-02** — byte-identical across two revisions
of MouseBiteLabs' own design, verified in `wiki-audit/README.md`. A position that stable across
a redesign is exactly what an outside mod keys off.

So the land goes back, unpopulated, as **`C7A`**.

## 19.2 Why it is nearly free

Three facts, each checked rather than assumed:

1. **No routing is needed.** ECO-6 §6.1 recorded that *"`C7` had no tracks attached on the
   original board — both pads were fed by pours."* The `VDD35` and `GND` pours still cover both
   old pad centres; KiCad's own DRC confirms `C7A` is **not** among the unconnected items on a
   re-poured board.
2. **Nothing to clear.** The nearest copper this fork adds is **2.778 mm** away.
3. **No paste.** DNP means ECO-17's rule strips both apertures, so no stencil aperture lands
   under a module.

The land is Nick's own `C7` block, taken from the board *before* ECO-6 moves it — same pads,
same courtyard, same silk — re-stamped with fresh deterministic UUIDs, its schematic `path`
removed (board-only, like `MOD1`/`JP4`/`TP83`), and flagged
`dnp exclude_from_bom exclude_from_pos_files`.

## 19.3 The two are mutually exclusive, and that is the design

`C7A`'s land is **2.15 mm inside `MOD1`'s body**, so a *populated* 0603 there fouls a module
lying on the board. Bare, it is copper and mask — the module already sits over **25 of
MouseBiteLabs' own vias**.

> **Populate `C7` for a ClockxControl build. Populate `C7A` for a stock build that needs the
> landmark. Never both.**

Check **[9]** used to fail on any footprint in the module window. It now distinguishes a
**body** from a **land**: a footprint in the window still fails unless it is `dnp` *and* named
in `WINDOW_DNP_LANDS`, so nobody can park a real part there by flagging it.

## 19.4 Three bugs this turned up in our own tooling

**Paste stripping ran too early.** ECO-17's rule walked the board *before* the new footprints
were spliced in, so anything added afterwards escaped it — and its self-check passed, because
at that point the offender did not exist. `MOD1`, `JP4`, `TP83`–`85` and the fiducials carry no
paste by construction, so nothing showed until `C7A` came through with both apertures intact.
**A rule about the finished board has to run on the finished board.** Moved; 254 → 256 stripped.

**A part inside the module body reported clearance.** `geom.neighbour_gaps()` measures distance
to the body's four edge *segments*, so a footprint wholly within the rectangle reports a
comfortable positive gap — it measures how far it is from the wall, not that it is in the room.
`C7A` read **1.420 mm** as though it were clear. Containment is now reported as a **negative**
distance, which sorts to the front and cannot be mistaken for headroom, and check [13] fails on
any *populated* part inside the body while tolerating a ledgered DNP land.

**`--only` reported the manifest's size.** Fixed in passing: a partial render run announced
"wrote 4" having written one.

## 19.5 And one much larger thing: KiCad's DRC now runs here

ECO-14 §14.6 listed *"open in KiCad, re-pour, run DRC"* as a human to-do. With KiCad 9
installed for ECO-16's renders, it is a script: `scripts/check_drc.py` re-pours a throwaway
copy and runs `kicad-cli pcb drc` on it.

**It diffs against the base rather than counting.** MouseBiteLabs' own AGBM-02, re-poured
through the identical process, has **695 violations and 0 unconnected items** — mostly silk
overlaps and library nits on a design that is hand-built and has never needed to be DRC-clean.
A gate demanding zero would fail on *his* board before it looked at ours, and would be switched
off within a week. Every violation is fingerprinted by type and position, the base's multiset is
subtracted, and what remains is ours: **69 violations and 1 unconnected item.**

Most are cosmetic silk. **Two are not, and neither was findable before:**

### `U1` pad 39 has no ground connection

DRC reports one unconnected item on this fork and none on Nick's: **`Pad 39 [GND] of U1`**.
ECO-6's `/CPU/TP8` route runs past it and pinches the `F.Cu` `GND` pour off the land. Check [13]
measures copper-to-copper distance and can never see this: nothing is too close to anything, and
a pad simply stops being connected.

> **Corrected by [ECO-20 §20.1](ECO-20_drc_defects_closed.md).** This paragraph originally
> said the route passes *0.988 mm* from the pad and pinches off its *thermal spokes*. The real
> figure is **0.3594 mm** of copper-to-copper at (73.372, −46.628), against the **0.400 mm** a
> pour sliver needs there — 0.2 mm of zone clearance to `TP8` plus the zone's own 0.2 mm
> `min_thickness`. Forty-one microns. There are no thermal spokes involved: the pad is on the
> zone's own net and the fill simply cannot reach it.

**It predates `C7A`** — confirmed by running the same DRC on the previous commit's board.

### The fiducials are placed on things

All six were placed in ECO-14 §14.3 by a search that modelled **hard copper only**. This board
has **64 mechanical keepout zones**, a 0.5 mm board-edge rule and soldermask-bridge rules, and
the search knew about none of them:

| Fiducial | What DRC says |
|---|---|
| `FID1` | **0.000 mm to `BT1`'s through-hole `GND` pad** — the battery terminal; 5 mask bridges with it; inside a keepout |
| `FID2`, `FID5` | 0.000 mm to the board outline; `FID2` inside a keepout |
| `FID3`, `FID6` | 0.000 mm to the board outline |

Both defects are **ledgered by fingerprint** in `check_drc.py` with their reasons, so they
cannot be forgotten and cannot be quietly acquired again — and when either is fixed, the ledger
line has to go in the same commit or the check fails the other way.

> **Both are closed in [ECO-20](ECO-20_drc_defects_closed.md), and those ledger lines are
> gone.** The counts in §19.6 below are what this commit produced; ECO-20's are 55 new
> violations and **0** unconnected. One correction to the table above: of the seven
> `solder_mask_bridge` violations, six were `FID1`/`BT1` and the seventh was `FID5` sitting in
> the cartridge-contact mask opening on the back — a count that matched for the wrong reason.

## 19.6 Verification

* `python3 scripts/build_board.py --check` — byte-identical rebuild
* `python3 scripts/check_consistency.py` — 0 errors; [9] and [13] carry `C7A` by ledger
* `python3 scripts/test_checks.py` — 21 cases, 0 blind
* `python3 scripts/check_drc.py` — 69 new violations and 1 unconnected item, every one ledgered
* `C7A` is **not** among the unconnected items: the pours reach it, exactly as they reached
  `C7` before ECO-6 moved it
