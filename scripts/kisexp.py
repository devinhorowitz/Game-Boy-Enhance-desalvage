#!/usr/bin/env python3
"""kisexp.py -- the one reader every script in this repo uses for a .kicad_pcb.

Borrowed shape, not borrowed code: SOLAR-GLOW's suite leans on `kicad-cli` and
`pcbnew` and therefore has to pin a KiCad container by digest in three workflows
and keep the three in step. This repo cannot do that -- it has no schematic in the
tree to export a netlist from, and the board it ships lives inside a zip -- so the
reader is stdlib text parsing instead. That is a real trade: no geometry engine, no
zone filling, no DRC. What it buys is that the whole gate runs in seconds on a bare
runner with nothing pinned, so there is one fewer thing that can rot.

The board is a KiCad 9 s-expression file (`version 20241229`). Everything below
reads it as text in ONE pass and hands back plain dicts. Nothing here writes.

    from kisexp import load, footprints, nets_by_name

    b = load(PCB)
    for fp in footprints(b):
        fp.ref, fp.value, fp.props, fp.layer, fp.at, fp.dnp, fp.pads
"""
from __future__ import annotations

import math
import re
import zipfile

_FP_OPEN = "\n\t(footprint "
_FP_CLOSE = "\n\t)\n"

_RE_PROP = re.compile(r'\(property "([^"]+)" "([^"]*)"')
_RE_LAYER = re.compile(r'^\t\t\(layer "([^"]+)"\)', re.M)
_RE_AT = re.compile(r'^\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', re.M)
_RE_ATTR = re.compile(r'^\t\t\(attr ([^)]*)\)', re.M)
_RE_FPNAME = re.compile(r'^\t\(footprint "([^"]+)"', re.M)
_RE_PAD = re.compile(
    r'\(pad "([^"]*)"[^\n]*\n(?:[^\n]*\n)*?[^\n]*?\(net (\d+) "([^"]*)"\)')
_RE_PIN = re.compile(r'\(pinfunction "([^"]*)"\)')


class Footprint:
    __slots__ = ("ref", "value", "props", "layer", "at", "attr", "name", "body", "span")

    def __init__(self, body, span):
        self.body = body
        self.span = span
        self.props = dict(_RE_PROP.findall(body))
        self.ref = self.props.get("Reference", "?")
        self.value = self.props.get("Value", "")
        m = _RE_FPNAME.search(body)
        self.name = m.group(1) if m else ""
        m = _RE_LAYER.search(body)
        self.layer = m.group(1) if m else ""
        m = _RE_AT.search(body)
        self.at = (float(m.group(1)), float(m.group(2)),
                   float(m.group(3)) if m.group(3) else 0.0) if m else None
        m = _RE_ATTR.search(body)
        self.attr = set(m.group(1).split()) if m else set()

    # --- the three flags every buy/place decision in this repo turns on -------
    @property
    def dnp(self):
        return "dnp" in self.attr

    @property
    def bom_excluded(self):
        return "exclude_from_bom" in self.attr

    @property
    def placed(self):
        """True if a pick-and-place would put this part down."""
        return not self.dnp and "exclude_from_pos_files" not in self.attr

    @property
    def pads(self):
        """[(pad_number, net_number, net_name, pinfunction)] -- one pass, no nesting."""
        out = []
        for m in _RE_PAD.finditer(self.body):
            seg = self.body[m.start():m.end()]
            fn = _RE_PIN.search(seg)
            out.append((m.group(1), int(m.group(2)), m.group(3),
                        fn.group(1) if fn else ""))
        return out

    def __repr__(self):
        return f"<Footprint {self.ref} {self.value!r} {self.layer}>"


def load(path):
    """Read a .kicad_pcb from disk, or from `zip.zip::member/path.kicad_pcb`.

    LINE ENDINGS ARE NORMALISED, and that is load-bearing rather than tidy. Every
    matcher below anchors on "\n\t" -- the upstream MouseBiteLabs board ships CRLF
    throughout while this fork's board is LF, so without this an upstream file parses
    to ZERO footprints and every check reading it passes vacuously. That happened
    once, and it produced a confident wrong conclusion about which board had routed
    a net. A silent empty parse read as "nothing wrong" is the failure mode this
    whole suite exists to prevent, so `footprints()` also refuses to return nothing.
    """
    if "::" in path:
        zp, member = path.split("::", 1)
        with zipfile.ZipFile(zp) as z:
            raw = z.read(member).decode("utf-8")
    else:
        with open(path, encoding="utf-8", newline="") as f:
            raw = f.read()
    return raw.replace("\r\n", "\n")


def footprints(board):
    """Iterate every footprint in ONE pass. A full walk is O(n), not O(n^2).

    Raises if a board that plainly contains footprints yields none -- see load().
    """
    if "(footprint " in board and _FP_OPEN not in board:
        raise ValueError(
            "this board has footprints but none in the expected layout -- it was not "
            "run through kisexp.load(), or its formatting is not KiCad 9 tab-indented. "
            "Refusing to return an empty parse.")
    i = board.find(_FP_OPEN)
    while i >= 0:
        j = board.find(_FP_CLOSE, i + 1)
        if j < 0:
            break
        yield Footprint(board[i + 1:j + len(_FP_CLOSE)], (i + 1, j + len(_FP_CLOSE)))
        i = board.find(_FP_OPEN, j)


def by_ref(board):
    return {fp.ref: fp for fp in footprints(board)}


def nets_by_name(board):
    """net name -> ['REF.pad', ...] for every pad on the board."""
    nets = {}
    for fp in footprints(board):
        for num, _n, name, _fn in fp.pads:
            nets.setdefault(name, []).append(f"{fp.ref}.{num}")
    return nets


# =====================================================================================
# THE KICAD 10 FORMAT BREAK, AND WHY EVERY READER BELOW REFUSES TO RETURN NOTHING
# =====================================================================================
# KiCad 10 (file version 20260206) stopped referencing nets BY NUMBER and started
# referencing them BY NAME: `(net 12)` on a segment or via became `(net "/CPU/TP8")`, and
# a pad's `(net 12 "/CPU/TP8")` became `(net "/CPU/TP8")`. The `(net N "name")` declaration
# table at the top of the file is gone entirely.
#
# Every regex in this repository that reads a net was written against the KiCad 9 form, so
# on a KiCad 10 board they match NOTHING -- and each one used to return an empty list and
# let the caller carry on. That is not a hypothetical: the first comparison run against a
# KiCad 10 save of this very board printed "theirs 0 segments" and the natural reading was
# that 3,557 tracks had been deleted. Nothing had been deleted; the parser had gone blind.
#
# This is the same failure `footprints()` already guards -- the CRLF parse that produced a
# confident wrong conclusion about which board had routed a net. So the rule is uniform:
# A READER THAT CAN SEE THE TOKEN BUT PARSE NONE OF IT RAISES. Silence is never zero.
def _refuse_empty(board, token, found, what):
    if found or token not in board:
        return
    v = re.search(r'\(version (\d+)\)', board)
    raise ValueError(
        f"this board contains {token!r} but {what} parsed ZERO of them"
        + (f" -- it is file version {v.group(1)}" if v else "")
        + ". KiCad 10 (version 20260206) writes nets BY NAME, `(net \"GND\")`, where "
          "KiCad 9 (20241229) writes `(net 2)`; these readers understand the KiCad 9 form "
          "only. Refusing to return an empty parse, because every clearance and "
          "connectivity check downstream would pass vacuously on it.")


def net_table(board):
    """The board's declared net list: {number: name}. Pads reference these."""
    out = {int(n): nm for n, nm in re.findall(r'\n\t\(net (\d+) "([^"]*)"\)', board)}
    _refuse_empty(board, "\n\t(net ", out, "net_table()")
    return out


def vias(board):
    """[(x, y, net_number)] for every via."""
    out = []
    for m in re.finditer(
            r'\n\t\(via\n\t\t\(at ([-\d.]+) ([-\d.]+)\)(?:.|\n)*?\(net (\d+)\)', board):
        out.append((float(m.group(1)), float(m.group(2)), int(m.group(3))))
    _refuse_empty(board, "\n\t(via", out, "vias()")
    return out


def balanced(board):
    """True if every paren outside a quoted string closes. Cheap structural gate."""
    d = i = 0
    inq = False
    n = len(board)
    while i < n:
        c = board[i]
        if inq:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                inq = False
        elif c == '"':
            inq = True
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d < 0:
                return False
        i += 1
    return d == 0 and not inq


# =====================================================================================
# Net connectivity -- the minimum needed to tell "unrouted" from "routed in two pieces"
# =====================================================================================
# NOT a general-purpose connectivity engine. It joins TRACK ENDPOINTS, vias and pad
# origins, and it does NOT understand zones, so a net whose pieces are joined only by a
# copper pour reads here as separate islands. Every net this repo asserts on is a routed
# signal, not a plane, so that limit is stated rather than worked around -- and it is
# exactly why check [10] names the missing via site instead of just counting pieces.
_RE_PADAT = re.compile(
    r'\(pad "([^"]*)" \w+ \w+\n\t\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)')
_LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def pad_positions(board, net_number):
    """[(ref.pad, x, y)] in board coordinates for every pad on the net."""
    out = []
    for fp in footprints(board):
        if fp.at is None:
            continue
        fx, fy, rot = fp.at
        # SIGN. KiCad stores footprint rotation counter-clockwise in a y-DOWN coordinate
        # system, so mapping a pad's local offset into board space needs radians(-rot),
        # not radians(rot). This was wrong until 2026-08-20 and it mattered: every pad on
        # a footprint rotated by anything other than a multiple of 180 landed in the wrong
        # place, which silently swapped pad 1 and pad 2 on every 90-degree part.
        #
        # The test that settles it, on the shipped board: for each pad on a rotated
        # footprint, ask which sign puts it nearer a track endpoint of its OWN net.
        #     -rot nearer: 200      +rot nearer: 16      tie: 3
        # and the -rot winners include exact 0.000 mm hits (R39.1, R39.2, C30.2) that sit
        # 1.55-1.65 mm away under +rot. A pad sitting exactly on its own track endpoint is
        # ground truth; 1.6 mm away is not.
        a = math.radians(-rot)
        for m in _RE_PADAT.finditer(fp.body):
            seg = fp.body[m.start():m.start() + 1500]
            nm = re.search(r'\(net (\d+) "', seg)
            if not nm or int(nm.group(1)) != net_number:
                continue
            dx, dy = float(m.group(2)), float(m.group(3))
            out.append((f"{fp.ref}.{m.group(1)}",
                        fx + dx * math.cos(a) - dy * math.sin(a),
                        fy + dx * math.sin(a) + dy * math.cos(a)))
    return out


def segments(board, net_number):
    """[(x0, y0, x1, y1, layer)] for every track segment on the net."""
    out = []
    i = board.find("\n\t(segment")
    while i >= 0:
        j = board.find("\n\t)\n", i + 1)
        body = board[i:j + 4]
        if f"(net {net_number})" in body:
            s = re.search(r"\(start ([-\d.]+) ([-\d.]+)\)", body)
            e = re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", body)
            L = re.search(r'\(layer "([^"]+)"\)', body)
            if s and e and L:
                out.append((float(s.group(1)), float(s.group(2)),
                            float(e.group(1)), float(e.group(2)), L.group(1)))
        i = board.find("\n\t(segment", j)
    return out


def net_islands(board, net_number, tol=0.02):
    """Group the net's pads into electrically-connected islands.

    Returns [[ref.pad, ...], ...]. One list means the net is whole; more than one means
    it is routed but broken. Zero segments and one island per pad means unrouted.
    """
    par = {}

    def find(a):
        par.setdefault(a, a)
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def uni(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb

    q = lambda v: round(v, 4)                                     # noqa: E731
    for x0, y0, x1, y1, lay in segments(board, net_number):
        uni((q(x0), q(y0), lay), (q(x1), q(y1), lay))
    for vx, vy, n in vias(board):
        if n != net_number:
            continue
        for lay in _LAYERS:
            uni(("via", q(vx), q(vy)), (q(vx), q(vy), lay))
    nodes = [k for k in par if len(k) == 3 and isinstance(k[2], str) and k[2] in _LAYERS]
    for ref, px, py in pad_positions(board, net_number):
        for n in nodes:
            if abs(n[0] - px) < tol and abs(n[1] - py) < tol:
                uni(("pad", ref, 0), n)
    groups = {}
    for ref, _px, _py in pad_positions(board, net_number):
        groups.setdefault(find(("pad", ref, 0)), []).append(ref)
    return [sorted(v) for v in groups.values()]


def pad_blocks(body):
    """Yield each pad's full s-expression from a footprint body, paren-balanced.

    THE BOUNDED-REGEX VERSION OF THIS IS A TRAP. `\(pad "..." ... ([\s\S]{0,300}?)\n\t\t\)`
    reads correctly for a plain SMD pad and does two different wrong things elsewhere: a
    `custom` pad whose primitives run past the bound is SKIPPED ENTIRELY AND SILENTLY, and a
    non-anchored variant happily pairs one pad's `(at ...)` with the NEXT pad's `(layers
    ...)`. Both were live here -- the second reported U2 as pasted on three of its four lead
    columns when the board has exactly two. Walk the parens.
    """
    import re as _re
    for m in _re.finditer(r'\(pad "', body):
        i, d = m.start(), 0
        for j in range(i, len(body)):
            c = body[j]
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    yield body[i:j + 1]
                    break
