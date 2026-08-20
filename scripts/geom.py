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
