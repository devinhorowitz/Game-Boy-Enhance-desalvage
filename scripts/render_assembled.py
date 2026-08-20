#!/usr/bin/env python3
"""render_assembled.py -- raytrace the board as PCBWay actually ships it.

    python3 scripts/render_assembled.py            # every target -> render/
    python3 scripts/render_assembled.py --only pcbway-top
    python3 scripts/render_assembled.py --list     # show targets, render nothing
    python3 scripts/render_assembled.py --check    # inputs sound? render nothing

BORROWED FROM SOLAR-GLOW

The shape is `scripts/render.py` in devinhorowitz/solar-business-card, adapted. What was
worth taking is not the kicad-cli invocation -- that is four lines -- but the three
disciplines around it, each of which exists because that project got burned:

  1. EVERY TARGET RENDERS FROM A THROWAWAY COPY, never the committed board. Transforms
     that make the picture honest would corrupt the file if applied in place.

  2. ZONES ARE REFILLED ON THE COPY BEFORE RENDERING. `kicad-cli pcb render` has no
     --refill-zones; it draws the fill as STORED. Solar-Glow shipped imagery of a
     previous board for a week because of this and proved it afterwards by diffing a
     render before and after a refill. THIS REPOSITORY IS THE SAME CASE, WORSE: check
     [14] exists precisely because our stored fill is MouseBiteLabs' from before this
     fork added any copper, and 19 added objects sit inside foreign-net pours. A render
     off the stored fill would show a board that cannot be built. Refilling the COPY is
     what makes the picture true while the committed board stays stale on purpose -- so
     check [14] stays green and its three "re-pour before fab" paragraphs stay honest.

  3. MODEL RESOLUTION IS REPORTED OUT LOUD. A missing 3D model is invisible as an error
     and obvious as a lie: KiCad draws nothing for a path it cannot resolve and says
     nothing, so the image just comes back with fewer parts. Solar-Glow hit this twice.
     We hit it immediately -- see below.

WHAT THIS FORK HAD TO ADD

  * THE .wrl PROBLEM. This board names 149 `.wrl` models and 38 `.step`. Ubuntu's
    `kicad-packages3d` ships 7,237 files and NOT ONE `.wrl`. So 79% of the bodies would
    have silently failed to draw. The copy rewrites `.wrl` -> `.step` wherever the .step
    exists, which is KiCad's own pairing convention, and the report counts the rewrites.

  * THREE MODEL ENV VARS, NOT ONE. The board's paths are split across
    ${KICAD6_3DMODEL_DIR} (2), ${KICAD8_3DMODEL_DIR} (148) and ${KICAD9_3DMODEL_DIR}
    (39) -- MouseBiteLabs' board has been carried across three KiCad generations. A
    KiCad 9 install defines only the last of those, so 150 of 189 references resolve to
    nothing. All three are passed with --define-var.

  * WHO PLACES WHAT. "As assembled by PCBWay" is not "the board with all its parts on".
    PCBWay places 180 of the 251 footprints; 5 are hand-solder and 66 are DNP, fiducials,
    jumpers and test pads. The set comes from `bom_split.classify()` -- imported, not
    re-implemented, so the render and the buy documents cannot give different accounts of
    the same build.

WHY THESE ARE NOT PIXEL-GATED LIKE THE 2D VIEWS

check [15] holds `scripts/render_board.py` to a pixel-exact re-render, because that
renderer is pure Python and its output is a function of the board alone. A raytrace is a
function of the board AND KiCad's build AND the 3D library, so pixel equality across
machines is not a property worth asserting -- a gate that fails on somebody's KiCad
version is a gate people learn to ignore. What IS asserted, and recorded in the manifest,
is the thing that actually goes wrong: how many bodies resolved, and which did not.

AND IT IS WORSE THAN CROSS-MACHINE VARIANCE: THIS RAYTRACER IS NOT DETERMINISTIC AT ALL.
Measured 2026-08-20, same machine, same KiCad 10.0.5, same board, two consecutive runs with
nothing whatsoever changed in between:

    agbm02_pcbway_top       40,309 of 2,342,592 px differ (1.72%), max channel delta 30
    agbm02_pcbway_bottom    44,630 of 2,342,592 px differ (1.91%), max channel delta 31
    agbm02_finished_top     43,685 of 2,342,592 px differ (1.87%), max channel delta 38
    agbm02_finished_bottom  45,127 of 2,342,592 px differ (1.93%), max channel delta 32

Subtle shading and anti-aliasing noise -- nothing structural moves -- but it means a pixel
gate on these would fail at random on the SAME machine, and it means re-running this script
always produces a git diff whether or not the board changed. Do not "fix" check [15] by
extending its pixel comparison to cover these four; that check would be red half the time.
The `source` digest ECO-24 added to the manifest is the honest gate for them: it asserts
what these pictures were drawn FROM, which is deterministic, rather than what they look
like, which is not.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kisexp                                                    # noqa: E402
import bom_split                                                 # noqa: E402
import build_board                                               # noqa: E402

# The hand-solder set, taken from the generator rather than typed here. P1 and P4 carry
# `dnp` ON TOP OF `exclude_from_bom`, so bom_split.classify() calls them "none" -- correct
# for the assembly house, which leaves them off entirely, and wrong for a picture of a
# FINISHED board, which certainly has its cartridge connector fitted. Naming them by class
# alone would have quietly left the two biggest through-hole parts off the finished view.
# X1/C3/C4 stay off: ECO-7 marks the crystal DNP for ClockxControl builds, and a finished
# ClockxControl board really does not have one.
HAND_FITTED = set(build_board.THRU_HOLE_REASONS) | set(build_board.SALVAGE_ONLY)

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "clockxcontrol-integration" / "board" / "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb"
OUTDIR = ROOT / "clockxcontrol-integration" / "render"
MANIFEST = OUTDIR / "assembled-manifest.json"

WIDTH, HEIGHT = 2000, 1200
MODEL_VARS = ("KICAD6_3DMODEL_DIR", "KICAD7_3DMODEL_DIR",
              "KICAD8_3DMODEL_DIR", "KICAD9_3DMODEL_DIR")

# target -> (filename, which classes keep their bodies, side, one-line description)
TARGETS = {
    "pcbway-top": ("agbm02_pcbway_top.png", {"assembly"}, "top",
                   "front, exactly the parts PCBWay's line places"),
    "pcbway-bottom": ("agbm02_pcbway_bottom.png", {"assembly"}, "bottom",
                      "back, exactly the parts PCBWay's line places"),
    "finished-top": ("agbm02_finished_top.png", {"assembly", "hand", "+hand-fitted"},
                     "top", "front, after you have hand-soldered the rest too"),
    "finished-bottom": ("agbm02_finished_bottom.png", {"assembly", "hand", "+hand-fitted"},
                        "bottom", "back, after you have hand-soldered the rest too"),
}


def stock_model_dir() -> str:
    """Where the KICAD*_3DMODEL_DIR vars should point on THIS machine."""
    env = os.environ.get("KICAD9_3DMODEL_DIR")
    if env and os.path.isdir(env):
        return env
    for d in ("/usr/share/kicad/3dmodels", "/usr/local/share/kicad/3dmodels",
              "/usr/share/kicad/modules/packages3d"):
        if os.path.isdir(d):
            return d
    return ""


def footprint_blocks(src: str):
    """(ref, start, end) for every footprint, paren-balanced and string-aware.

    Paren-balanced rather than a lazy regex: a footprint contains nested pads, models and
    properties, and a lazy match runs past its own end into the next part -- the same bug
    ECO-15 found in check_stock's schematic parser, which handed SW1's link to U13.
    """
    for m in re.finditer(r'\n\t\(footprint "', src):
        i = m.start() + 1
        d, j, instr = 0, m.start() + 1, False
        while j < len(src):
            c = src[j]
            if instr:
                if c == "\\":
                    j += 2
                    continue
                if c == '"':
                    instr = False
            elif c == '"':
                instr = True
            elif c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        ref = re.search(r'\(property "Reference"\s+"([^"]+)"', src[i:j + 1])
        yield (ref.group(1) if ref else "?"), i, j + 1


def model_paths(src: str):
    return re.findall(r'\(model "([^"]+)"', src)


def resolve(ref: str, stock: str) -> str:
    return re.sub(r'\$\{KICAD\d+_3DMODEL_DIR\}', stock, ref)


def rewrite_wrl_to_step(src: str, stock: str) -> tuple[str, int, list[str]]:
    """Point every .wrl at its .step twin where the .wrl is absent and the .step is not.

    KiCad pairs a .wrl and a .step of the same stem as one model; the .wrl is the render
    body. Ubuntu's kicad-packages3d ships STEP only -- 7,237 files, zero .wrl -- so on this
    machine the board's 149 .wrl references resolve to nothing at all. Rewriting is done on
    the THROWAWAY COPY and counted, never guessed at silently.
    """
    swapped, still_missing = 0, []
    def sub(m):
        nonlocal swapped
        p = m.group(1)
        real = resolve(p, stock)
        if os.path.isfile(real):
            return m.group(0)
        alt = os.path.splitext(real)[0] + ".step"
        if os.path.isfile(alt):
            swapped += 1
            return '(model "%s"' % (os.path.splitext(p)[0] + ".step")
        still_missing.append(os.path.relpath(real, stock) if stock else real)
        return m.group(0)
    out = re.sub(r'\(model "([^"]+)"', sub, src)
    return out, swapped, sorted(set(still_missing))


def board_bbox(src: str):
    """(x0, y0, x1, y1) of Edge.Cuts."""
    import geom
    segs = geom.edge_segments(src)
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def strip_unplaced(src: str, keep: set[str]) -> tuple[str, dict]:
    """Delete the (model ...) blocks of every footprint NOT in `keep`.

    The classification is `bom_split.classify()` -- the same function the buy documents and
    the position file are built from. A part PCBWay does not place must not appear in a
    picture captioned "as PCBWay assembles it", and a DNP part keeps its model reference in
    the file, resolves perfectly, and would be drawn.
    """
    board = kisexp.by_ref(src)
    bb = board_bbox(src)
    dropped, kept, offboard, bodyless = {}, {}, [], []
    out, last = [], 0
    for ref, a, b in footprint_blocks(src):
        fp = board.get(ref)
        cls = bom_split.classify(fp)[0] if fp else "none"
        blk = src[a:b]
        n = blk.count("(model ")
        # OFF-BOARD FOOTPRINTS ARE NOT PART OF THE BOARD, whatever they classify as.
        # MouseBiteLabs' AGBM-02 parks an unannotated HC49 crystal -- ref "REF**", zero
        # pads, a leftover reference for the crystal option ECO-7 marks DNP -- at
        # (8.89, -81.888), nine millimetres above the top edge. It carries a 3D model, so
        # the first assembled render came back with a crystal floating in space beside the
        # board. It is outside Edge.Cuts, so no fab makes it; it is not ours to delete from
        # his file; and it must not appear in a picture captioned "as PCBWay assembles it".
        if bb and fp is not None and fp.at is not None and not (
                bb[0] - 0.5 <= fp.at[0] <= bb[2] + 0.5
                and bb[1] - 0.5 <= fp.at[1] <= bb[3] + 0.5):
            if n:
                offboard.append(ref)
                out.append(src[last:a])
                out.append(re.sub(r'\n\t\t\(model "(?:[^"]*)"[\s\S]*?\n\t\t\)', "", blk))
                last = b
            continue
        if cls in keep or ("+hand-fitted" in keep and ref in HAND_FITTED):
            k = cls if cls in keep else "hand-fitted (dnp)"
            kept[k] = kept.get(k, 0) + 1
            if n == 0:
                bodyless.append(ref)          # kept, and still nothing to draw
            continue
        if n:
            dropped[cls] = dropped.get(cls, 0) + n
            out.append(src[last:a])
            out.append(re.sub(r'\n\t\t\(model "(?:[^"]*)"[\s\S]*?\n\t\t\)', "", blk))
            last = b
    out.append(src[last:])
    return "".join(out), {"kept": kept, "dropped_models": dropped,
                          "offboard": sorted(offboard), "bodyless": sorted(bodyless)}


def refill_zones(pcb: Path) -> str:
    """Fill the zones on the temp COPY. See the module docstring, discipline 2."""
    import pcbnew
    b = pcbnew.LoadBoard(str(pcb))
    zones = list(b.Zones())
    pcbnew.ZONE_FILLER(b).Fill(zones)
    b.Save(str(pcb))
    area = sum(z.GetFilledArea() for z in zones) / 1e12
    return f"refilled {len(zones)} zones -> {area:,.1f} mm2 of copper"


def prepare(workdir: Path, keep: set[str], stock: str) -> tuple[Path, dict]:
    src = BOARD.read_text(encoding="utf-8")
    info = {}
    src, swapped, missing = rewrite_wrl_to_step(src, stock)
    info["wrl_to_step"] = swapped
    info["unresolvable"] = missing
    src, split = strip_unplaced(src, keep)
    info.update(split)
    dest = workdir / BOARD.name
    dest.write_text(src, encoding="utf-8", newline="")
    for ext in ("kicad_pro", "kicad_dru"):
        s = BOARD.with_suffix("." + ext)
        if s.exists():
            shutil.copy(s, dest.with_suffix("." + ext))
    info["zones"] = refill_zones(dest)
    return dest, info


def report(src_after: str, info: dict, stock: str) -> dict:
    """Say out loud how many bodies this machine can draw. Discipline 3."""
    refs = model_paths(src_after)
    good = [r for r in refs if os.path.isfile(resolve(r, stock))]
    bad = sorted({os.path.basename(r) for r in refs
                  if not os.path.isfile(resolve(r, stock))})
    swapped = info.get("wrl_to_step", 0)
    extra = f" ({swapped} rewritten .wrl -> .step)" if swapped else ""
    print(f"    bodies: {len(good)}/{len(refs)} resolve{extra}")
    if bad:
        print(f"    NOT DRAWN, no model file on this machine: {', '.join(bad)}")
    if info.get("bodyless"):
        # Kept on purpose and still invisible. A reader looking for the cartridge connector
        # in a "finished board" picture deserves to be told it has no 3D model rather than
        # left to wonder whether the render or the board is wrong.
        print(f"    KEPT but carry no 3D model at all: {', '.join(info['bodyless'])}")
    if info.get("offboard"):
        print(f"    bodies removed as OUTSIDE the board outline: "
              + ", ".join(info["offboard"]))
    if info.get("dropped_models"):
        print(f"    bodies removed as not-placed: "
              + ", ".join(f"{k} {v}" for k, v in sorted(info["dropped_models"].items())))
    print(f"    {info['zones']}")
    return {"resolved": len(good), "referenced": len(refs), "missing": bad,
            "bodyless": info.get("bodyless", []), "kept": info.get("kept", {}),
            "offboard": info.get("offboard", [])}


def render(pcb: Path, out: Path, side: str, stock: str) -> bool:
    cmd = ["kicad-cli", "pcb", "render", "--output", str(out),
           "--quality", "high", "--background", "opaque",
           "--width", str(WIDTH), "--height", str(HEIGHT), "--side", side,
           "--zoom", "1.0"]
    for v in MODEL_VARS:
        cmd += ["--define-var", f"{v}={stock}"]
    cmd.append(str(pcb))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["(no output)"]
        print(f"    !! failed: {tail[0]}")
        return False
    try:
        shown = out.relative_to(ROOT)
    except ValueError:
        shown = out
    print(f"    wrote {shown} ({out.stat().st_size:,} bytes)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=sorted(TARGETS))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="verify the toolchain and the model library, render nothing")
    a = ap.parse_args()

    if a.list:
        for k, (fn, keep, side, desc) in TARGETS.items():
            print(f"{k:16s} {fn:28s} {desc}")
        return 0

    stock = stock_model_dir()
    problems = []
    if not shutil.which("kicad-cli"):
        problems.append("kicad-cli not found -- needs KiCad 9 "
                        "(ppa:kicad/kicad-9.0-releases on Ubuntu)")
    try:
        import pcbnew                                             # noqa: F401
    except ImportError:
        problems.append("the pcbnew Python module is not importable -- refill_zones needs "
                        "it, and a render off the STORED fill would show a shorted board")
    if not stock:
        problems.append("no KiCad 3D model library found -- every body would be missing "
                        "and nothing would say so")
    if a.check:
        for p in problems:
            print("ERROR: " + p, file=sys.stderr)
        if problems:
            return 1
        src, sw, miss = rewrite_wrl_to_step(BOARD.read_text(encoding="utf-8"), stock)
        refs = model_paths(src)
        good = sum(1 for r in refs if os.path.isfile(resolve(r, stock)))
        print(f"ok: kicad-cli {subprocess.run(['kicad-cli','version'],capture_output=True,text=True).stdout.strip()}, "
              f"models at {stock}")
        print(f"ok: {good}/{len(refs)} bodies resolve ({sw} via .wrl -> .step)")
        if miss:
            print(f"note: {len(miss)} model(s) absent from the stock library: "
                  + ", ".join(os.path.basename(m) for m in miss))
        return 0
    if problems:
        for p in problems:
            print("render_assembled: " + p, file=sys.stderr)
        return 1

    OUTDIR.mkdir(parents=True, exist_ok=True)
    # MERGE into the existing manifest, never replace it. A `--only` run used to rewrite
    # the file with its single target, which dropped the other three from the record --
    # and check [15] then reported the real, present PNGs as ungenerated orphans. A
    # partial run must narrow what it re-renders, not what the repository knows about.
    man = {"kicad": subprocess.run(["kicad-cli", "version"], capture_output=True,
                                   text=True).stdout.strip(),
           "models": stock, "targets": {}}
    if MANIFEST.exists():
        try:
            man["targets"] = json.loads(MANIFEST.read_text(encoding="utf-8")).get(
                "targets", {})
        except ValueError:
            pass
    todo = [a.only] if a.only else list(TARGETS)
    failed = 0
    for name in todo:
        fn, keep, side, desc = TARGETS[name]
        print(f"  {name}: {desc}")
        with tempfile.TemporaryDirectory() as td:
            pcb, info = prepare(Path(td), keep, stock)
            stats = report(pcb.read_text(encoding="utf-8"), info, stock)
            out = OUTDIR / fn
            if not render(pcb, out, side, stock):
                failed += 1
                continue
        man["targets"][fn] = {"desc": desc, "side": side,
                              "keeps": sorted(keep), **stats,
                              "bytes": out.stat().st_size}
    live = {fn for fn, _k, _s, _d in TARGETS.values()}
    man["targets"] = {k: v for k, v in man["targets"].items() if k in live}
    # ECO-24: the board these bodies were placed on, so a stale assembled render is
    # catchable without KiCad. Same rationale as render_board.source_digest().
    import render_board as _rb
    import geom as _geom
    man["source"] = _rb.source_digest(kisexp.load(str(BOARD)), _geom.base())
    MANIFEST.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n", newline="")
    # len(man["targets"]) is the MANIFEST's size, which after the merge is every target
    # this repository knows about -- so a --only run used to announce "wrote 4 render(s)"
    # having written one.
    print(f"wrote {len(todo) - failed} of {len(todo)} render(s) this run "
          f"({len(man['targets'])} in the manifest) + {MANIFEST.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
