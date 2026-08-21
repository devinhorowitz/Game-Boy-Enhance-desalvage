"""geom.py -- copper-clearance arithmetic, shared by the checks that need real geometry.

WHY THIS EXISTS. kisexp.py answers "what is on this board" -- refs, nets, islands. It does
not answer "how far apart is this copper", and until this module nothing here did.
That is how a 0.1632 mm clearance violation and six unreadable fiducials shipped past twelve
green checks. This module is the missing half: pads as rounded rectangles, tracks as
inflated segments, vias as circles, plus the board outline -- all in board coordinates.

IT DOES NOT MODEL ZONE FILLS. kisexp has no zone reader and neither does this, so every
number here is clearance to HARD copper: a track, a via or a pad. Poured copper is handled
the way a layout tool handles it -- give the object a local clearance and let the fill
recede. Where that matters (the fiducials) the generator sets that clearance explicitly.

ROTATION SIGN. Pads are placed with radians(-rot), matching kisexp.pad_positions(). KiCad
stores rotation counter-clockwise in a y-DOWN system; the other sign silently swaps pad 1
and pad 2 on every 90-degree part. kisexp and this module must agree on the sign;
check [18] gates the result against kicad-cli's own position export.
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
    """-> (segs, vias, pads) in board coords.

    pads = (ref.pad, x, y, hw, hh, cr, layers, net, ANG) where ANG is the pad's EFFECTIVE
    orientation in degrees -- the footprint's rotation plus the pad's own.

    THAT LAST FIELD WAS MISSING AND IT MATTERED. A pad carries its own `(at x y rot)`, and
    345 of this board's 956 pads are turned 90 or 270 degrees inside their footprint --
    every fine-pitch QFP and SOP side row. Without it, `(size 0.3 1.25)` was read as
    0.3 wide by 1.25 tall for a pad that is physically 1.25 wide by 0.3 tall, so every
    clearance measured against one was wrong by up to half a millimetre in the worst axis.
    U1's pin 39 read as spanning 1.25 mm in y when it spans 0.3.
    """
    tbl = kisexp.net_table(board)
    segs = [(float(a),float(b),float(c),float(d),float(w),l,tbl.get(int(n),str(n)))
            for a,b,c,d,w,l,n in _SEG.findall(board)]
    # See kisexp._refuse_empty. _SEG matches the KiCad 9 `(net N)` form only, and a board
    # saved by KiCad 10 yields zero segments from it -- which reads as "no copper" to every
    # clearance check in this file.
    kisexp._refuse_empty(board, "\n\t(segment", segs, "geom.collect()")
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
            pang = float(m.group(4)) if m.group(4) else 0.0   # the pad's OWN rotation
            x = fx + lx*math.cos(a) - ly*math.sin(a)
            y = fy + lx*math.sin(a) + ly*math.cos(a)
            w,h = float(sz.group(1)), float(sz.group(2))
            shape = shp.group(1) if shp else "rect"
            cr = min(w,h)*float(rr.group(1)) if rr else (min(w,h)/2 if shape=="circle" else 0.0)
            layers = lay.group(1) if lay else ""
            pads.append((f"{fp.ref}.{m.group(1)}", x, y, w/2, h/2, cr,
                         layers, net.group(2) if net else None, (rot + pang) % 360))
    return segs, vias, pads

def _p2s(px,py,ax,ay,bx,by):
    vx,vy = bx-ax, by-ay; L2 = vx*vx+vy*vy
    t = 0 if L2==0 else max(0,min(1,((px-ax)*vx+(py-ay)*vy)/L2))
    return math.hypot(px-(ax+vx*t), py-(ay+vy*t))

def _pad_gap(px,py,pr, pad):
    """Distance from a round object to a rounded-rectangle pad, IN THE PAD'S OWN FRAME.

    The query point is rotated into the pad's frame rather than the rectangle being rotated
    out of it -- exact for any angle, and the 24 pads on this board at 1.25, 15.25, 21, 111,
    285.25 and 343 degrees are handled by the same arithmetic as the 932 at right angles.
    """
    _ref,x,y,hw,hh,cr,_lay,_net = pad[:8]
    ang = pad[8] if len(pad) > 8 else 0.0
    dx0, dy0 = px - x, py - y
    if ang:
        # board y grows DOWNWARD, so the inverse rotation takes -ang the same way
        # pad_positions and collect() do
        t = math.radians(ang)
        dx0, dy0 = dx0*math.cos(t) + dy0*math.sin(t), -dx0*math.sin(t) + dy0*math.cos(t)
    dx,dy = abs(dx0), abs(dy0)
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
        ref,_x,_y,_hw,_hh,_cr,lay,n = pad[:8]
        if ref in ignore or n == net: continue
        if not any(L.strip('"*') in lay or '*' in lay for L in layers): pass
        if not (any(l in lay for l in layers) or "*.Cu" in lay): continue
        out.append((_pad_gap(px,py,pr,pad), f"pad {ref} ({n}) {lay}"))
    out.sort()
    return out

def _arc_pts(p0, pm, p1, n=24):
    """Polygonise a KiCad three-point arc. Falls back to the two chords if degenerate."""
    (x0,y0),(xm,ym),(x1,y1) = p0, pm, p1
    d = 2*(x0*(ym-y1) + xm*(y1-y0) + x1*(y0-ym))
    if abs(d) < 1e-9:
        return [p0, pm, p1]
    ux = ((x0*x0+y0*y0)*(ym-y1) + (xm*xm+ym*ym)*(y1-y0) + (x1*x1+y1*y1)*(y0-ym))/d
    uy = ((x0*x0+y0*y0)*(x1-xm) + (xm*xm+ym*ym)*(x0-x1) + (x1*x1+y1*y1)*(xm-x0))/d
    r  = math.hypot(x0-ux, y0-uy)
    a0, am, a1 = (math.atan2(y-uy, x-ux) for x,y in (p0, pm, p1))
    # walk start -> end the way that passes through the mid point
    def norm(a): return (a + 2*math.pi) % (2*math.pi)
    sweep = norm(a1-a0)
    if not (norm(am-a0) <= sweep):
        sweep -= 2*math.pi
    return [(ux + r*math.cos(a0 + sweep*i/n), uy + r*math.sin(a0 + sweep*i/n))
            for i in range(n+1)]


def edge_segments(board):
    """Every Edge.Cuts primitive, flattened to straight chords.

    gr_circle WAS MISSING. IT COST FOUR DRC VIOLATIONS AND A WRONG SENTENCE ABOUT
    FIDUCIAL CLEARANCE.
    This board's outline is not one ring: 13 of its Edge.Cuts items are gr_circle -- the
    shell's screw and standoff holes -- and until 2026-08-20 this function read gr_line,
    gr_arc, gr_rect and gr_poly only, so the fiducial search placed two pairs with the
    written claim "each is >= 3.0 mm from the board edge" while FID2/FID5 sat INSIDE a
    1.2 mm hole and FID3/FID6 straddled the rim of another. A hole in the board IS board
    edge. Anything measuring distance to the outline has to see all five primitives, and
    gr_rect is four sides rather than the one diagonal the old code produced.
    """
    import re
    segs = []
    def chain(pts, close=False):
        if close and pts and pts[0] != pts[-1]:
            pts = pts + [pts[0]]
        for i in range(len(pts)-1):
            segs.append((pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]))
    for m in re.finditer(r'\(gr_(line|arc|rect|poly|circle)\b([\s\S]{0,4000}?)\n\t\)', board):
        kind, body = m.group(1), m.group(2)
        if '"Edge.Cuts"' not in body: continue
        pts = [(float(a),float(b)) for a,b in
               re.findall(r'\((?:start|mid|end|xy|center) ([-\d.]+) ([-\d.]+)\)', body)]
        if kind == "circle" and len(pts) >= 2:
            (cx,cy),(ex,ey) = pts[0], pts[1]
            r = math.hypot(ex-cx, ey-cy)
            chain([(cx + r*math.cos(2*math.pi*i/48), cy + r*math.sin(2*math.pi*i/48))
                   for i in range(48)], close=True)
        elif kind == "arc" and len(pts) >= 3:
            chain(_arc_pts(pts[0], pts[1], pts[2]))
        elif kind == "rect" and len(pts) >= 2:
            (x0,y0),(x1,y1) = pts[0], pts[1]
            chain([(x0,y0),(x1,y0),(x1,y1),(x0,y1)], close=True)
        elif kind == "poly":
            chain(pts, close=True)
        else:
            chain(pts)
    # AND THE FOOTPRINTS. SW1 and VR2 each carry one Edge.Cuts circle -- routed holes for
    # the switch shaft and the volume wheel -- and a top-level-only scan misses both. The
    # one at (12.727, -12.215) is 0.2145 mm from where the first attempt at FID1 put
    # a fiducial, which is how it was found: by KiCad, after this function said 2.80 mm.
    for fp in kisexp.footprints(board):
        if fp.at:
            segs += outline(fp, "Edge.Cuts")
    return segs

def edge_dist(px,py,esegs):
    import math
    best=1e9
    for ax,ay,bx,by in esegs:
        best=min(best,_p2s(px,py,ax,ay,bx,by))
    return best

# ---------------------------------------------------------------------- zone fills
# kisexp has no zone reader and this module said so; that limit is exactly what
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
    coordinates. This fork moves `C7`, and a refdes-keyed rule cannot see where it went.
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
    for pad in A_pad:
        # collect() returns NINE fields since the pad's own rotation was added to it;
        # slice rather than unpack, the way worst() does. This line read eight and crashed the
        # instant an added pad first landed in a foreign pour, which was the fiducial move
        # -- a long run of green on a path nothing had ever taken.
        ref, x, y, _hw, _hh, _cr, plays, net = pad[:8]
        hit = set()
        for lay in CU_LAYERS:
            if lay in plays or "*.Cu" in plays:
                hit |= set(in_foreign_fill(x, y, lay, net or "<netless>", zf))
        if hit:
            out.append((ref, net or "<netless>", "+".join(sorted(hit))))
    return sorted(out)


# ---------------------------------------------------------------- mechanical fit
# Every gate before this one measured COPPER. The module is a physical object that sits on
# the board, and nothing checked whether it fits -- there was a table of neighbour
# clearances measured off a render, and when that render turned out to be pre-rebase there
# was no way to tell whether the numbers still held. These recompute them from the board.

_FPGEO2 = re.compile(r'\(fp_(line|rect|poly|circle|arc)([\s\S]{0,4000}?)\n\t\t\)')


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
               re.findall(r'\((?:start|mid|end|xy|center) ([-\d.]+) ([-\d.]+)\)', m.group(2))]
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
        elif m.group(1) == "circle" and len(pts) >= 2:
            # a footprint circle is (center)(end); rotation moves both, so the radius is
            # whatever separates them after the transform
            (cx, cy), (ex, ey) = pts[0], pts[1]
            r = math.hypot(ex - cx, ey - cy)
            ring = [(cx + r * math.cos(2 * math.pi * k / 32),
                     cy + r * math.sin(2 * math.pi * k / 32)) for k in range(32)]
            for i in range(32):
                p, q = ring[i], ring[(i + 1) % 32]
                segs.append((p[0], p[1], q[0], q[1]))
        elif m.group(1) == "arc" and len(pts) >= 3:
            a = _arc_pts(pts[0], pts[1], pts[2])
            for i in range(len(a) - 1):
                segs.append((a[i][0], a[i][1], a[i + 1][0], a[i + 1][1]))
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
    ("crtyd"); a bare test pad has none, so it is measured pad-copper-to-body ("pad"). The
    land-pattern work
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
        # A DISTANCE TO THE BODY'S EDGE IS NOT A CLEARANCE IF THE PART IS INSIDE IT. BODY is
        # four line segments, so a footprint sitting wholly within the rectangle reports a
        # comfortable positive gap -- it is measuring how far it is from the wall, not that it
        # is in the room. C7A is the live case: its land is 2.15 mm inside
        # MOD1's body on purpose, and this read 1.420 mm as though it were clear. Containment is
        # reported as a NEGATIVE distance, which sorts to the front and cannot be mistaken for
        # headroom.
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


# ------------------------------------------------------------------- keepout zones
# CHECK [13] KNEW NOTHING ABOUT THESE AND SAID SO. This board carries 64 keepout zones --
# the GBA shell's ribs, screw bosses and LCD bezel -- and two earlier fiducials landed
# inside two of them. A keepout is not copper, so no amount of copper arithmetic finds it.
_KEEP_RULES = ("tracks", "vias", "pads", "copperpour", "footprints")


def zone_blocks(board):
    """Yield each zone's full s-expression, paren-balanced -- INCLUDING footprint zones.

    16 of this board's 64 keepouts live inside footprints, at indent 2, and their vertices
    are already in board coordinates. A reader that only walks the top level sees 48.
    """
    for m in re.finditer(r'\n\t+\(zone\b', board):
        i, d = m.end() - len("(zone"), 0
        for j in range(i, len(board)):
            c = board[j]
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    yield board[i:j + 1]
                    break


def _pts(block):
    """Vertices of a `(pts ...)` list, flattening `(arc (start)(mid)(end))` entries.

    FOUR OF THIS BOARD'S KEEPOUTS ARE DRAWN AS A SINGLE FULL-CIRCLE ARC -- start == end,
    mid diametrically opposite -- and carry no (xy) at all. An (xy)-only reader returns an
    empty vertex list for them and they vanish, which is precisely how the keepout ringing
    the screw hole at (110.9, -56.85) stayed invisible while FID2 sat inside it.
    """
    out, pend = [], []
    for kind, a, b in re.findall(r'\((xy|start|mid|end) ([-\d.]+) ([-\d.]+)\)', block):
        if kind == "xy":
            out.append((float(a), float(b)))
            continue
        pend.append((float(a), float(b)))
        if len(pend) < 3:
            continue
        p0, pm, p1 = pend
        pend = []
        if p0 == p1:                       # a closed circle written as one arc
            cx, cy = (p0[0] + pm[0]) / 2, (p0[1] + pm[1]) / 2
            r = math.hypot(p0[0] - cx, p0[1] - cy)
            out += [(cx + r * math.cos(2 * math.pi * k / 48),
                     cy + r * math.sin(2 * math.pi * k / 48)) for k in range(48)]
        else:
            out += _arc_pts(p0, pm, p1)
    return out


def keepouts(board):
    """[(layers, rules, polygon)] for every keepout zone.

    `layers` is a set of copper-layer names, `rules` maps each of tracks/vias/pads/
    copperpour/footprints to "allowed" or "not_allowed", and `polygon` is the zone
    outline -- NOT its fill, because a keepout has none.
    """
    out = []
    for z in zone_blocks(board):
        k = z.find("(keepout")
        if k < 0:
            continue
        rules = dict(re.findall(r"\((%s) (\w+)\)" % "|".join(_KEEP_RULES), z[k:k + 400]))
        lay = re.search(r'\(layers? ([^)]*)\)', z)
        layers = set(re.findall(r'"([^"]+)"', lay.group(1))) if lay else set()
        p = z.find("(polygon")
        pts = _pts(z[p:]) if p >= 0 else []
        if pts:
            out.append((layers, rules, pts))
    return out


def poly_dist(px, py, poly):
    """Signed distance to a closed polygon: NEGATIVE inside, positive outside."""
    d = min(_p2s(px, py, poly[i][0], poly[i][1],
                 poly[(i + 1) % len(poly)][0], poly[(i + 1) % len(poly)][1])
            for i in range(len(poly)))
    return -d if inside(px, py, poly) else d


# =====================================================================================
# CAN A FIDUCIAL LIVE HERE? -- the five questions the first search never asked
# =====================================================================================
# An earlier pass placed six fiducials by maximising distance to HARD COPPER alone, wrote
# the resulting margins into a comment, and shipped four DRC violations: two marks inside
# shell holes, two inside keepout zones, one merged with the battery terminal's mask.
# Everything below exists so the placement TOOL and the GATE cannot disagree about what a
# legal site is -- scripts/place_fiducials.py searches with it, check [13] re-measures the
# six chosen spots with it, and both get the same numbers from the same code.
_GRAPH = re.compile(r'\n\t\(gr_(poly|rect|circle|line|arc)\b([\s\S]{0,40000}?)\n\t\)')
_FPGRAPH = re.compile(r'\(fp_(poly|rect|circle|line|arc)([\s\S]{0,4000}?)\n\t\t\)')
_PT = re.compile(r'\((?:xy|start|mid|end|center) ([-\d.]+) ([-\d.]+)\)')
FID_WINDOW = 1.00        # 0.5 mm pad + 0.5 mm solder_mask_margin


def _closed(kind, pts):
    """The shape as a closed ring, or None if it is an open line/arc."""
    if kind == "poly" and len(pts) >= 3:
        return pts
    if kind == "rect" and len(pts) == 2:
        (x0, y0), (x1, y1) = pts
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if kind == "circle" and len(pts) >= 2:
        (cx, cy), (ex, ey) = pts[0], pts[1]
        r = math.hypot(ex - cx, ey - cy)
        return [(cx + r * math.cos(2 * math.pi * k / 32),
                 cy + r * math.sin(2 * math.pi * k / 32)) for k in range(32)]
    return None


def mask_apertures(board, skip=()):
    """({layer: [ring]}, {layer: [chord]}) for every soldermask GRAPHIC on the board.

    AN APERTURE IS A FILLED REGION, NOT AN OUTLINE, and the difference is not academic:
    the two 7.5 x 5 mm B.Mask polygons over the cartridge-edge contacts swallowed a
    fiducial whole, and a boundary-distance test called that 0.9 mm of clearance.
    Closed shapes come back as rings so the caller can use a SIGNED distance.
    """
    polys = {"F.Mask": [], "B.Mask": []}
    chords = {"F.Mask": [], "B.Mask": []}

    def eat(kind, pts, lay):
        ring = _closed(kind, pts)
        if ring:
            polys[lay].append(ring)
        elif len(pts) >= 2:
            chords[lay] += [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                            for i in range(len(pts) - 1)]
    for m in _GRAPH.finditer(board):
        lay = re.search(r'\(layer "([^"]+)"\)', m.group(2))
        if lay and lay.group(1) in polys:
            eat(m.group(1), [(float(a), float(b)) for a, b in _PT.findall(m.group(2))],
                lay.group(1))
    for fp in kisexp.footprints(board):
        if not fp.at or fp.ref in skip:
            continue
        T = _xf(fp)
        for m in _FPGRAPH.finditer(fp.body):
            lay = re.search(r'\(layer "([^"]+)"\)', m.group(2))
            if lay and lay.group(1) in polys:
                eat(m.group(1), [T(float(a), float(b)) for a, b in _PT.findall(m.group(2))],
                    lay.group(1))
    return polys, chords


def courtyards(board, skip=()):
    """{layer: [chord]} for every footprint's courtyard, in board coordinates."""
    out = {"F.CrtYd": [], "B.CrtYd": []}
    for fp in kisexp.footprints(board):
        if not fp.at or fp.ref in skip:
            continue
        for lay in out:
            out[lay] += outline(fp, lay)
    return out


def board_outline(board):
    """The board's outer boundary as one ring -- the largest closed loop in Edge.Cuts."""
    adj = {}
    q = lambda v: (round(v[0], 3), round(v[1], 3))                # noqa: E731
    for ax, ay, bx, by in edge_segments(board):
        a, b = q((ax, ay)), q((bx, by))
        if a == b:
            continue
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, best, ring = set(), 0.0, []
    for start in adj:
        if start in seen:
            continue
        loop, cur, prev = [start], start, None
        seen.add(start)
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        if len(loop) > 2:
            a = abs(sum(loop[i][0] * loop[(i + 1) % len(loop)][1]
                        - loop[(i + 1) % len(loop)][0] * loop[i][1]
                        for i in range(len(loop)))) / 2
            if a > best:
                best, ring = a, loop
    return ring


class _Grid:
    """A 3 mm bucket index. The site search asks ~160,000 questions; a linear scan of
    this board's 7,000 copper objects for each is 40 minutes, and this is seconds."""
    CELL = 3.0

    def __init__(self):
        self.g = {}

    def add(self, x0, y0, x1, y1, obj):
        C = self.CELL
        for cx in range(int(math.floor(min(x0, x1) / C)), int(math.floor(max(x0, x1) / C)) + 1):
            for cy in range(int(math.floor(min(y0, y1) / C)), int(math.floor(max(y0, y1) / C)) + 1):
                self.g.setdefault((cx, cy), []).append(obj)

    def near(self, x, y):
        cx, cy = int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL))
        return [o for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                for o in self.g.get((cx + dx, cy + dy), ())]


def _chord_grid(chords):
    g = _Grid()
    for c in chords:
        g.add(c[0], c[1], c[2], c[3], ("chord", c))
    return g


def _ring_grid(rings):
    g = _Grid()
    for r in rings:
        xs = [p[0] for p in r]
        ys = [p[1] for p in r]
        g.add(min(xs), min(ys), max(xs), max(ys), ("ring", r))
    return g


def site_model(board, skip=()):
    """Everything site_margins() needs, indexed once. `skip` drops refs by name."""
    segs, vias, pads = collect(board)
    pads = [p for p in pads if p[0].rsplit(".", 1)[0] not in skip]
    cu = {"F.Cu": _Grid(), "B.Cu": _Grid()}
    for ax, ay, bx, by, w, lay, _n in segs:
        if lay in cu:
            cu[lay].add(ax, ay, bx, by, ("seg", (ax, ay, bx, by, w)))
    for vx, vy, _n in vias:
        for lay in cu:
            cu[lay].add(vx, vy, vx, vy, ("via", (vx, vy)))
    for p in pads:
        ex = max(p[3], p[4])
        for lay in cu:
            if lay in p[6] or "*.Cu" in p[6]:
                cu[lay].add(p[1] - ex, p[2] - ex, p[1] + ex, p[2] + ex, ("pad", p))
    mp, mc = mask_apertures(board, skip)
    ct = courtyards(board, skip)
    ko = {"F.Cu": [], "B.Cu": []}
    for lay, rules, poly in keepouts(board):
        if any(rules.get(k, "allowed") == "not_allowed" for k in ("pads", "footprints")):
            for L in ko:
                if L in lay:
                    ko[L].append(poly)
    return {"cu": cu,
            "edge": _chord_grid(edge_segments(board)),
            "mask": {L: (_ring_grid(mp[L]), _chord_grid(mc[L])) for L in mp},
            "crtyd": {L: _chord_grid(ct[L]) for L in ct},
            "keepout": {L: _ring_grid(ko[L]) for L in ko},
            "outer": board_outline(board)}


FAR = 9.0                 # "nothing of that kind anywhere near" -- reported, not clipped


def site_margins(M, x, y, layer):
    """{edge, keepout, copper, mask, crtyd, on_board} for a fiducial at (x, y) on `layer`.

    Every number is measured FROM THE CENTRE, so compare against the 1.0 mm mask window
    rather than the 0.5 mm copper dot. `keepout` and `mask` are SIGNED -- negative means
    the point is inside the zone or inside the aperture.
    """
    side = "F" if layer.startswith("F") else "B"
    cu_l, mk_l, ct_l = f"{side}.Cu", f"{side}.Mask", f"{side}.CrtYd"
    # FAR is a CEILING, not a sentinel with a different meaning: 9 mm and 40 mm are the
    # same answer -- "nothing of that kind is anywhere near" -- and clamping keeps the
    # ledger stable when a part 12 mm away moves to 15.
    clamp = lambda v: round(min(FAR, v), 4)                       # noqa: E731
    rings, chords = M["mask"][mk_l]
    cu = FAR
    for kind, o in M["cu"][cu_l].near(x, y):
        cu = min(cu, _p2s(x, y, o[0], o[1], o[2], o[3]) - o[4] / 2 if kind == "seg" else
                     math.hypot(x - o[0], y - o[1]) - 0.35 if kind == "via" else
                     _pad_gap(x, y, 0.0, o))
    return {
        "on_board": inside(x, y, M["outer"]),
        "edge":    clamp(min((_p2s(x, y, *c) for _k, c in M["edge"].near(x, y)), default=FAR)),
        "keepout": clamp(min((poly_dist(x, y, r)
                              for _k, r in M["keepout"][cu_l].near(x, y)), default=FAR)),
        "copper":  clamp(cu),
        "mask":    clamp(min([poly_dist(x, y, r) for _k, r in rings.near(x, y)]
                             + [_p2s(x, y, *c) for _k, c in chords.near(x, y)], default=FAR)),
        "crtyd":   clamp(min((_p2s(x, y, *c)
                              for _k, c in M["crtyd"][ct_l].near(x, y)), default=FAR)),
    }
