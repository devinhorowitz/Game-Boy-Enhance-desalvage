# ECO-24 — a stale picture can no longer ride a green build

Derivative of MouseBiteLabs *Game Boy Enhance* (AGBM-02), CC BY-SA 4.0.

**Changed:** `scripts/render_board.py`, `scripts/render_assembled.py`,
`scripts/check_consistency.py` (check **[15]**), `scripts/test_checks.py`
**Raised by:** the user, asking whether the render pipeline is automatic.

---

## 24.1 It was not, and the gap was in the half nobody could see

Nothing renders automatically. `render_board.py` and `render_assembled.py` are run by hand;
`pack_board.py` sweeps whatever PNGs are in `render/` into the deliverable; check [15]
re-renders in memory and compares pixel digests against the committed files.

That last step is the guard — and **it never ran on CI.** Re-rendering needs Pillow, and
this project's workflow installs nothing on purpose:

> NO CONTAINER, NO PINNED IMAGE, NO pip INSTALL. […] the whole gate runs in about five
> seconds on a bare runner, and there is no digest that can rot underneath it.

So check [15] reported `did not run` on every build, `test_checks.py` counted it as a
declared skip, and **a board change committed without re-rendering would have passed a
fully green pipeline.** The pictures would have been of a board that no longer existed, and
the first thing to notice would have been a person looking at a fab drawing.

Installing Pillow in CI would fix it and cost more than it is worth: the pixel digests are
Pillow-version-sensitive, so a runner-image roll could turn check [15] red for a reason that
has nothing to do with this board — precisely the rot the workflow's design note refuses.

## 24.2 The fix needs no Pillow, no KiCad and no rendering

Both renderers now stamp their manifest with the SHA-256 of **what they drew from**:

```json
"source": { "board": "797a9cb544d2a070", "base": "9baf08be6d4c7dd2" }
```

Check [15] recomputes those two hashes from the shipped board and the base zip and compares.
That is pure string handling, so it runs everywhere the rest of the suite does, and it
catches the failure that actually matters — *the board moved and the pictures did not*.

The check is now explicitly two halves, and the order is the point:

| | needs | catches |
|---|---|---|
| **source digest** — always runs | nothing | the board or the base changed and the renders were not redone |
| **pixel digest** — where Pillow exists | Pillow | the renderer's *output* changed while its input did not |

The weaker check is the one that always runs; the stronger one is a local bonus. Where
Pillow is missing the warning now says so precisely — *"the pixel half of check [15] did not
run (the source-digest half above did)"* — rather than implying the whole check was skipped.

## 24.3 The meta-test case moved to the half that always runs

`test_checks.py`'s `[15]` case is pinned to the reason **`written from a DIFFERENT board`**.
Pinning it to the pixel half's message would have made the case go BLIND on exactly the
runner it most needs to work on, since that message cannot exist without Pillow. Verified
both ways:

```
with Pillow:      26 cases, 0 blind   [15] ... -> caught
without Pillow:   26 cases, 0 blind   [15] ... -> caught
```

Before this ECO the second line read `did not run`.

## 24.4 What is still manual, on purpose

Generating the images. A board change means running both renderers and committing the PNGs
in the same commit — the difference is that forgetting is now a **build failure** instead of
a silent pass. `pack_board.py`'s sweep of `render/*.png` is unchanged and remains the one
genuinely automatic link in the chain.

## 24.5 Verification

* `python3 scripts/check_consistency.py` — **0 errors**; [15] reports both manifests written
  from board `797a9cb544d2a070` and base `9baf08be6d4c7dd2`
* the same, with Pillow blocked — the source-digest half still passes, the pixel half warns
* the same again with the board mutated and Pillow blocked — **2 errors**, where the
  previous code reported a skip
* `python3 scripts/test_checks.py` — **26 cases, 0 blind**, with and without Pillow
