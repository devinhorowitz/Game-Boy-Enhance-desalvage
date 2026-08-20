"""geom.py -- copper-clearance arithmetic, shared by the checks that need real geometry.

WHY THIS EXISTS. kisexp.py answers "what is on this board" -- refs, nets, islands. It does
not answer "how far apart is this copper", and until ECO-14 nothing in this repository did.
That is how a 0.1632 mm clearance violation and six unreadable fiducials shipped past twelve
green checks. This module is the missing half: pads as rounded rectangles, tracks as
inflated segments, vias as circles, plus the board outline -- all in board coordinates.

IT DOES NOT MODEL ZONE FILLS. kisexp has no zone reader and neither does this, so every
number here is clearance to HARD copper: a track, a via or a pad. Poured copper is handled
the way a layout tool handles it -- give the object a local clearance and let the fill
recede. Where that matters (the fiducials) the generator sets that clearance explicitly.

ROTATION SIGN. Pads are placed with radians(-rot), matching kisexp.pad_positions(). KiCad
stores rotation counter-clockwise in a y-DOWN system; the other sign silently swaps pad 1
and pad 2 on every 90-degree part. See ECO-14 section 14.4.
"""
import os
import sys, re, math, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp
from kisexp import _RE_PADAT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def base():
    z = zipfile.ZipFile(f"{ROOT}/AGBM-02 (AA Batteries)/AGBM-02 Design Files.zip")
    return z.read("AGBM-02 Design Files/AGBM-02_AA_1-1.kicad_pcb").decode().replace("\r\n","\n")

_SEG = re.compile(r'\(segment\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)'
                  r'\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)\s*\(net (\d+)\)')

def collect(board):
    """-> (segs, vias, pads) in board coords. pads = (ref.pad, x,y, hw,hh, cr, layers, net)."""
    tbl = kisexp.net_table(board)
    segs = [(float(a),float(b),float(c),float(d),float(w),l,tbl.get(int(n),str(n)))
            for a,b,c,d,w,l,n in _SEG.findall(board)]
    vias = [(x,y,tbl.get(n,str(n))) for x,y,n in kisexp.vias(board)]
    pads = []
    for fp in kisexp.footprints(board):
        if not fp.at: continue
        fx,fy,rot = fp.at
        a = math.radians(-rot)
        for m in _RE_PADAT.finditer(fp.body):
            blk = fp.body[m.start():m.start()+1500]
            sz  = re.search(r'\(size ([\d.]+) ([\d.]+)\)', blk)
            lay = re.search(r'\(layers ([^)]*)\)', blk)
            net = re.search(r'\(net (\d+) "([^"]*)"\)', blk)
            rr  = re.search(r'\(roundrect_rratio ([\d.]+)\)', blk)
            shp = re.match(r'"[^"]*" \w+ (\w+)', blk)
            if not sz: continue
            lx,ly = float(m.group(2)), float(m.group(3))
            x = fx + lx*math.cos(a) - ly*math.sin(a)
            y = fy + lx*math.sin(a) + ly*math.cos(a)
            w,h = float(sz.group(1)), float(sz.group(2))
            shape = shp.group(1) if shp else "rect"
            cr = min(w,h)*float(rr.group(1)) if rr else (min(w,h)/2 if shape=="circle" else 0.0)
            layers = lay.group(1) if lay else ""
            pads.append((f"{fp.ref}.{m.group(1)}", x, y, w/2, h/2, cr,
                         layers, net.group(2) if net else None))
    return segs, vias, pads

def _p2s(px,py,ax,ay,bx,by):
    vx,vy = bx-ax, by-ay; L2 = vx*vx+vy*vy
    t = 0 if L2==0 else max(0,min(1,((px-ax)*vx+(py-ay)*vy)/L2))
    return math.hypot(px-(ax+vx*t), py-(ay+vy*t))

def _pad_gap(px,py,pr, pad):
    _ref,x,y,hw,hh,cr,_lay,_net = pad
    dx,dy = abs(px-x), abs(py-y)
    ex,ey = max(dx-(hw-cr),0), max(dy-(hh-cr),0)
    return math.hypot(ex,ey) - cr - pr

def worst(px, py, pr, layers, segs, vias, pads, net=None, ignore=()):
    """Smallest copper-to-copper gap from a round object of radius pr on `layers`."""
    out = []
    for ax,ay,bx,by,w,lay,n in segs:
        if lay not in layers or n == net: continue
        out.append((_p2s(px,py,ax,ay,bx,by) - w/2 - pr, f"seg {n} {lay}"))
    for x,y,n in vias:
        if n == net: continue
        out.append((math.hypot(px-x,py-y) - 0.35 - pr, f"via {n}"))
    for pad in pads:
        ref,_x,_y,_hw,_hh,_cr,lay,n = pad
        if ref in ignore or n == net: continue
        if not any(L.strip('"*') in lay or '*' in lay for L in layers): pass
        if not (any(l in lay for l in layers) or "*.Cu" in lay): continue
        out.append((_pad_gap(px,py,pr,pad), f"pad {ref} ({n}) {lay}"))
    out.sort()
    return out

def edge_segments(board):
    import re
    segs=[]
    for m in re.finditer(r'\(gr_(line|arc|rect|poly)\b([\s\S]{0,800}?)\n\t\)', board):
        body=m.group(2)
        if '"Edge.Cuts"' not in body: continue
        pts=[(float(a),float(b)) for a,b in
             re.findall(r'\((?:start|mid|end|xy) ([-\d.]+) ([-\d.]+)\)', body)]
        for i in range(len(pts)-1):
            segs.append((pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1]))
    return segs

def edge_dist(px,py,esegs):
    import math
    best=1e9
    for ax,ay,bx,by in esegs:
        best=min(best,_p2s(px,py,ax,ay,bx,by))
    return best

# ---------------------------------------------------------------------- zone fills
# ECO-14. kisexp has no zone reader and this module said so; that limit is exactly what
# let "the fill is stale" stay a sentence in a document instead of a number in a gate.
# These read the STORED fill -- the polygons KiCad last computed -- not a re-computation.
# Nothing here fills a zone; it only measures the fill that is in the file.

_FILL = re.compile(r'\(filled_polygon\s*\(layer "([^"]+)"\)([\s\S]{0,400000}?)\n\t\t\)')
_XY = re.compile(r'\(xy ([-\d.]+) ([-\d.]+)\)')


def fills(board):
    """[(layer, net_name, [(x, y), ...])] for every stored fill polygon.

    The net comes from the enclosing (zone ...), so the scan walks backwards from each
    filled_polygon to the zone header that owns it.
    """
    out = []
    for m in _FILL.finditer(board):
        head = board.rfind('(zone', 0, m.start())
        net = "?"
        if head >= 0:
            nm = re.search(r'\(net_name "([^"]*)"\)', board[head:head + 400])
            if nm:
                net = nm.group(1)
        pts = [(float(a), float(b)) for a, b in _XY.findall(m.group(2))]
        if pts:
            out.append((m.group(1), net, pts))
    return out


def fill_signature(board):
    """A stable digest of every stored fill polygon.

    Identical digests on two boards mean the fill was never recomputed between them --
    which is the whole point: it turns "we did not re-pour" into something checkable.
    """
    import hashlib
    blocks = [m.group(0) for m in _FILL.finditer(board)]
    return hashlib.sha256("".join(blocks).encode()).hexdigest()[:16], len(blocks)


def inside(px, py, poly):
    """Ray-cast point-in-polygon. Boundary counts as inside."""
    n = len(poly)
    hit = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py):
            xc = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < xc:
                hit = not hit
        j = i
    return hit


def in_foreign_fill(px, py, layer, net, zf):
    """Names of foreign-net fills on `layer` that swallow the point."""
    return [zn for zl, zn, poly in zf
            if zl == layer and zn != net and inside(px, py, poly)]


# ------------------------------------------------------- what THIS FORK put on the board
# One implementation, shared by check [14] and by scripts/render_board.py. They used to
# have two, and the two disagreed -- 15 objects against 19 -- which is how the bug below
# was found. A gate and the picture of the same board must not be able to differ.

CU_LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def added(board, base):
    """(segs, vias, pads) present in `board` and absent from `base`, keyed on geometry.

    KEYED ON GEOMETRY, NOT ON REFDES. That distinction is the whole point: a part
    MouseBiteLabs already had, which this fork MOVED, is new copper at its new
    coordinates. ECO-6 moves `C7`, and a refdes-keyed rule cannot see where it landed.
    """
    bs, bv, bp = collect(base)
    ms, mv, mp = collect(board)
    k4 = lambda t: tuple(round(v, 4) if isinstance(v, float) else v for v in t)
    xy = lambda p: (round(p[1], 4), round(p[2], 4), round(p[3], 4), round(p[4], 4))
    sb = {k4(s) for s in bs}
    vb = {(round(x, 4), round(y, 4)) for x, y, _n in bv}
    pb = {xy(p) for p in bp}
    return ([s for s in ms if k4(s) not in sb],
            [v for v in mv if (round(v[0], 4), round(v[1], 4)) not in vb],
            [p for p in mp if xy(p) not in pb])


def swallowed(board, base):
    """Sorted [(label, net, "pour+pour")] for every added object inside a foreign pour.

    Measured AT THE PAD, on the layers that pad actually occupies, against THAT PAD'S OWN
    net. The first version of this measured at the footprint ORIGIN, on `fp.layer`, against
    the net of pad 1 -- three approximations at once. On `MOD1` that reported one hit on
    `VDD35` where the pads really straddle `VDD35` and `VDD2`, and it could not see `C7` at
    all.
    """
    zf = fills(board)
    _segs, A_via, A_pad = added(board, base)
    out = []
    for x, y, net in A_via:
        hit = set()
        for lay in CU_LAYERS:
            hit |= set(in_foreign_fill(x, y, lay, net, zf))
        if hit:
            out.append((f"via ({x},{y})", net, "+".join(sorted(hit))))
    for ref, x, y, _hw, _hh, _cr, plays, net in A_pad:
        hit = set()
        for lay in CU_LAYERS:
            if lay in plays or "*.Cu" in plays:
                hit |= set(in_foreign_fill(x, y, lay, net or "<netless>", zf))
        if hit:
            out.append((ref, net or "<netless>", "+".join(sorted(hit))))
    return sorted(out)


# ---------------------------------------------------------------- mechanical fit
# Every gate before this one measured COPPER. The module is a physical object that sits on
# the board, and nothing checked whether it fits -- ECO-6 carried a table of neighbour
# clearances measured off a render, and when that render turned out to be pre-rebase there
# was no way to tell whether the numbers still held. These recompute them from the board.

_FPGEO2 = re.compile(r'\(fp_(line|rect|poly)([\s\S]{0,600}?)\n\t\t\)')


def _xf(fp):
    fx, fy, rot = fp.at
    a = math.radians(-rot)
    return lambda lx, ly: (fx + lx * math.cos(a) - ly * math.sin(a),
                           fy + lx * math.sin(a) + ly * math.cos(a))


def outline(fp, tag):
    """Segments of `fp`'s `tag` graphics (e.g. "F.CrtYd", "F.Fab") in board coords."""
    T = _xf(fp)
    segs = []
    for m in _FPGEO2.finditer(fp.body):
        if tag not in m.group(2):
            continue
        pts = [T(float(x), float(y)) for x, y in
               re.findall(r'\((?:start|end|xy) ([-\d.]+) ([-\d.]+)\)', m.group(2))]
        if m.group(1) == "rect" and len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            segs += [(x0, y0, x1, y0), (x1, y0, x1, y1),
                     (x1, y1, x0, y1), (x0, y1, x0, y0)]
        elif m.group(1) == "line" and len(pts) == 2:
            segs.append((pts[0][0], pts[0][1], pts[1][0], pts[1][1]))
        elif m.group(1) == "poly" and len(pts) >= 2:
            for i in range(len(pts)):
                p, q = pts[i], pts[(i + 1) % len(pts)]
                segs.append((p[0], p[1], q[0], q[1]))
    return segs


def _seg_seg(a, c):
    return min(_p2s(a[0], a[1], *c), _p2s(a[2], a[3], *c),
               _p2s(c[0], c[1], *a), _p2s(c[2], c[3], *a))


def neighbour_gaps(board, ref="MOD1", limit=8):
    """[(neighbour, basis, mm)] from `ref`'s body to its nearest SAME-SIDE neighbours.

    SAME SIDE MATTERS. A naive sweep puts C12 at 0.055 mm, which reads like a collision and
    is not one -- C12 is on B.Cu, the far side of a 1.6 mm board. Only parts on the same
    side as `ref` can foul it.

    `basis` is the honest part: a neighbour with a courtyard is measured courtyard-to-body
    ("crtyd"); a bare test pad has none, so it is measured pad-copper-to-body ("pad"). ECO-6
    mixed the two under one "courtyard gaps" heading, which is how a reader would compare
    0.93 against 0.55 and not know they are different measurements.
    """
    fps = kisexp.by_ref(board)
    me = fps[ref]
    side = "F" if me.layer.startswith("F") else "B"
    bx = [v for s in outline(me, f"{side}.Fab") for v in (s[0], s[2])]
    by = [v for s in outline(me, f"{side}.Fab") for v in (s[1], s[3])]
    if not bx:
        return []
    x0, x1, y0, y1 = min(bx), max(bx), min(by), max(by)
    BODY = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
    _s, _v, pads = collect(board)
    out = []
    for r, fp in fps.items():
        if r == ref or fp.at is None or "*" in r:
            continue
        if not fp.layer.startswith(side):
            continue
        # A DISTANCE TO THE BODY'S EDGE IS NOT A CLEARANCE IF THE PART IS INSIDE IT.
        # BODY is four line segments, so a footprint sitting wholly within the rectangle
        # reports a comfortable positive gap -- it is measuring how far it is from the wall,
        # not that it is in the room. ECO-19's C7A is the live case: its land is 2.15 mm
        # inside MOD1's body on purpose, and this read 1.420 mm as though it were clear.
        # Containment is reported as a NEGATIVE distance, which sorts to the front and
        # cannot be mistaken for headroom.
        inside_body = (x0 <= fp.at[0] <= x1 and y0 <= fp.at[1] <= y1)
        cy = outline(fp, f"{side}.CrtYd")
        if cy:
            d = min(_seg_seg(b, c) for b in BODY for c in cy)
            out.append((r, "crtyd", -d if inside_body else d))
            continue
        pd = [p for p in pads if p[0].startswith(r + ".")]
        if pd:
            d = min(min(_p2s(p[1], p[2], *b) for b in BODY) - max(p[3], p[4]) for p in pd)
            out.append((r, "pad", -d if inside_body else d))
    return sorted(out, key=lambda t: t[2])[:limit]
