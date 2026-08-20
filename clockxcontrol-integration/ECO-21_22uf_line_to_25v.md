# ECO-21 — the 22 µF line goes to 25 V, and what that costs

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

**Board:** unchanged. No copper, no footprint, no `Value` — `C1`/`C21`/`C42`/`C58` still read `22u`.
**Changed:** `scripts/mpn_overrides.json`, `pcbway-assembly/resolved-mpns.json`, the generated
assembly BOM, `pcbway-assembly/README.md`, `ECO-10`, `ECO-15`
**Raised by:** the user — *"switch the 22uF line to the 25V part."*

| | was | now |
|---|---|---|
| Part | Murata `GRT21BR61C226ME13K` | YAGEO **`CC0805MKX5R8BB226`** |
| Rated voltage | 16 V | **25 V** |
| Digi-Key / Mouser | 8,218 / 0 | **≈130,000** / 0 |

---

## 21.1 Why the line moved

`C1` sits on `/VFILT`, `C21` and `C58` on `VOUT5`, `C42` on `VOUT3`. A class-II ceramic loses
capacitance to DC bias, and a 16 V part loses more of it at a given working voltage than a 25 V
part in the same body. [ECO-15](ECO-15_upstream_link_sync.md) knew that and accepted the 16 V
part anyway, for a good reason at the time: the 25 V part this fork had been buying,
`GRT21BR61E226ME13L`, had gone to **zero**, and so had the `GRM` it was itself swapped from. Two
swaps in a row had chased availability onto dead lines. Returning to MouseBiteLabs' own 16 V
part was the only thing on the table that could actually be ordered.

This ECO buys the headroom back.

## 21.2 The thing that made it a decision rather than a swap

A fresh sweep of every 22 µF / 25 V / 0805 part at both distributors, 2026-08-20, across five
query shapes with no stock floor: **22 distinct parts, six with stock and sixteen at zero.**

Both soft-termination parts — `GRT21BR61E226ME13K` and `GRT21BR61E226ME13L` — are among the
sixteen. So is the `GRM` family. That is the finding:

> **No 22 µF 25 V 0805 part in the market preserves everything the 16 V incumbent has.** Every
> one with stock gives up *both* AEC-Q200 qualification and Murata's `GRT` soft termination.

Soft termination is not decoration on this board. It is a flexible-electrode termination that
stops a board-flex crack propagating into the ceramic, and [ECO-10 §10.4](ECO-10_precision_pass.md)
argued for the `GRT` family on exactly that basis — a handheld gets dropped. Giving it up is a
real cost, and it is the cost of the voltage rating. There is no version of this change that
does not pay it.

That same §10.4 is titled *"Decoupling: 16 V → 25 V, and automotive grade"*: it made this exact
move on the 1 µF line, to TDK's `CGA3E1X7R1E105K080AC`, and got **both** the voltage and the
automotive grade because a part existed that had them. Here no such part does. Same reasoning,
worse market.

## 21.3 What was chosen, and what was rejected

**Keep the dielectric, change only the voltage.** Verified parameter by parameter against the
incumbent on the Digi-Key API:

| | `GRT21BR61C226ME13K` (was) | `CC0805MKX5R8BB226` (now) |
|---|---|---|
| Capacitance / tolerance | 22 µF ±20 % | 22 µF ±20 % |
| **Rated voltage** | 16 V | **25 V** |
| Dielectric | X5R | X5R |
| Operating range | −55…+85 °C | −55…+85 °C |
| Package / max thickness | 0805 (2012 metric), 1.45 mm | 0805 (2012 metric), 1.45 mm |
| Body | 2.00 × 1.25 mm | 2.00 × 1.25 mm |
| Qualification | **AEC-Q200** | — |
| Termination | **soft (`GRT`)** | standard |
| Unit price | $0.42 | $0.60 |
| Lead time | 19 wk | 24 wk |
| Digi-Key / Mouser | 8,218 / 0 | **≈130,000** / 0 |

Every mechanical and electrical figure is identical except the rated voltage. The board's land is
`C_0805_2012Metric_Boxed_2` and both parts are 0805 at 1.45 mm max thickness, so **nothing on the
board changes** — this is a BOM-only ECO.

**`GRM21BC81E226ME44K` was rejected, and this is the interesting one.** It keeps Murata, costs
less at $0.38, and runs to +105 °C. But it is **X6S — a different dielectric formulation** — and
its DC-bias curve could not be verified: Murata publishes that only through SimSurfing, whose API
returns HTTP 500/503 from here, and the product PDFs do not carry the curve.

> **DC bias is the entire reason for going to 25 V.** Accepting an unverifiable bias curve in
> exchange for it would be trading the goal away to reach the goal. An unreached probe reports
> UNKNOWN, not "probably fine."

It also holds only 2,589 — about 647 boards at four per board.

**Also weighed:** `C0805X5R226M250NPH` (EYang, X5R, 400,000, $0.17, no lead time) is by a wide
margin the cheapest and deepest, and it is a real X5R at 25 V in the right body. It was passed
over on manufacturer tier alone — this BOM is otherwise Murata, KEMET, TDK and YAGEO — which is a
judgement, not a measurement, and it is recorded here as one. `GMC21X5R226M25NT` (Cal-Chip,
46,919), `CL21A226MAYNNWE` (Samsung, 2,000, 39-week lead) and `KGM21AR51E226MU` (Kyocera AVX,
233 + 7, $1.06, 28-week lead) are genuine second sources.

**Rejected on geometry:** `ZRA21CR61E226ME01L` reads as a 25 V X5R with stock in a Mouser
listing, but Digi-Key's parameters give its package as *Nonstandard SMD* at **1.65 mm** thick,
not 0805 / 1.45 mm. It is not a drop-in, and a listing that looks right is not a parameter table.

## 21.4 Single-sourced, and the part to come back to

**Mouser has zero.** This line is single-sourced at Digi-Key at ≈130,000 — deep, but one
supplier. `resolved-mpns.json` carries the live block; re-run `scripts/check_stock.py` before
ordering rather than trusting any number in this document.

`GRT21BR61E226ME13L` is **the part to come back to**: the incumbent's own family at 25 V, same
soft termination, same AEC-Q200, same X5R, same 1.45 mm. It would make this whole ECO cost
nothing. It is at 0 / 0 with a 21-week lead (verified 2026-08-20). **Re-check it before every
order; if it has restocked, take it.**

If every 25 V line dries up, fall back to the 16 V `GRT21BR61C226ME13K` — MouseBiteLabs' own
choice, buildable at 8,218, and it costs only the headroom this ECO went after.

## 21.5 What is *not* verified here

Stated plainly, because the override is a decision record and a decision record that hides its
gaps is worse than none:

* **No bias curve was compared for any candidate.** The argument is the standard one — more
  voltage headroom in the same body and dielectric means less capacitance lost at a given
  working voltage — not a measured comparison. SimSurfing is the source for that data and it is
  unreachable from here.
* **No rail was scoped.** [ECO-15](ECO-15_upstream_link_sync.md) called for scoping the rails on
  the first build if bulk capacitance turns out to matter, and that call still stands. This
  change improves the margin; it does not measure it.
* **The manufacturer-tier judgement is a judgement.** EYang's part is cheaper, deeper and meets
  every published parameter.

## 21.6 Verification

* `python3 scripts/check_stock.py` — 185 buyable refs, 182 resolved, 0 unresolved
* `python3 scripts/bom_split.py` — the assembly BOM carries the new part on one 4-ref line
* `python3 scripts/check_consistency.py` — 0 errors
* `python3 scripts/build_board.py --check` — byte-identical rebuild; **the board did not move**
