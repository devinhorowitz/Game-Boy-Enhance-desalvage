#!/usr/bin/env python3
"""render_board.py -- draw the AGBM-02 ClockxControl board straight from the .kicad_pcb.

    python3 scripts/render_board.py            # write every view into render/
    python3 scripts/render_board.py --check    # re-render and compare, write nothing
    python3 scripts/render_board.py --list     # name the views and their crops

WHY THIS FILE EXISTS

ECO-6 §6.6 says the views in `render/` were "produced by a renderer built against the
board file directly". That renderer was never committed. What shipped was a set of PNGs
with no generator -- so when ECO-13 rebased the fork from AGBM-01 onto AGBM-02, every
render silently went on describing a board this repository no longer contains. Their git
blob SHAs were identical before and after the rebase, which is how ECO-14 §14.5 caught it.

The defect was never really "the pictures are stale". It was that a picture had no
provenance. This file is the provenance: the views are a FUNCTION of the board file, so
they cannot describe a board other than the one committed beside them, and `--check`
proves it on every run.

WHAT IS DRAWN, AND WHAT IS NOT

Drawn: the board outline (Edge.Cuts), the STORED zone fills, copper tracks and arcs, pads
(roundrect, rect, circle, oval), vias, and drill holes knocked back out of the copper.

Not drawn: soldermask, silkscreen, paste, and the true outline of the 32 `custom` pads --
those are approximated by their bounding shape. There is no `kicad-cli` and no KiCad in
this environment; this is a visual check, not a gerber export. Take real gerbers from KiCad.

THE ZONE FILLS ARE THE STORED ONES, ON PURPOSE

The earlier renderer drew an APPROXIMATE RE-POUR -- it computed what the pour ought to look
like. That is a friendlier picture and a worse one: it showed a board that does not exist in
the file, and it hid the very defect ECO-14 check [14] exists to gate. These views draw the
fill KiCad actually last computed, which is MouseBiteLabs' fill from before this fork added
any copper. Where an added via or pad lands inside a foreign-net pour, the view rings it in
`ALERT` and the caption counts them. That is not a rendering artifact -- it is the board,
and it is why nobody may plot gerbers from this file without opening KiCad and re-pouring.

DETERMINISM

Same board in, same pixels out: no timestamps, no randomness, a fixed supersample factor
and a fixed resampling filter. `--check` compares the RAW PIXEL BUFFER, not the PNG bytes,
so a different Pillow build changing its deflate settings is not mistaken for a board that
moved. The Pillow version is recorded in the manifest and reported when a digest differs.
"""

import argparse, hashlib, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp, geom

from PIL import Image, ImageDraw, ImageFont

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD  = os.path.join(ROOT, "clockxcontrol-integration", "board",
                      "AGBM-02_AA_1-1_GBE-plus-CXC.kicad_pcb")
OUTDIR = os.path.join(ROOT, "clockxcontrol-integration", "render")
MANIFEST = os.path.join(OUTDIR, "render-manifest.json")

SS = 3                      # supersample factor; 3 is the quality/△memory knee
BG      = (18, 18, 22)
EDGE    = (236, 236, 214)
ALERT   = (255, 64, 96)
ADDED   = (255, 214, 64)
LABEL   = (198, 198, 206)
DRILL   = (10, 10, 12)

# copper on top, its pour underneath -- the pour is the same hue at a third the value
CU = {"F.Cu":   ((214, 122,  66), ( 62,  40,  26)),
      "In1.Cu": ((122, 182,  72), ( 36,  50,  26)),
      "In2.Cu": ((192,  95, 192), ( 52,  30,  52)),
      "B.Cu":   (( 76, 138, 208), ( 26,  40,  58))}
ORDER = ["B.Cu", "In2.Cu", "In1.Cu", "F.Cu"]   # painted back-to-front


# ------------------------------------------------------------------ board readers
_ARC = re.compile(r'\(arc\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(mid ([-\d.]+) ([-\d.]+)\)'
                  r'\s*\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)')


def arcs(board):
    """Copper arcs, flattened to short chords. KiCad stores start/mid/end, not a centre."""
    out = []
    for a in _ARC.finditer(board):
        x0, y0, xm, ym, x1, y1 = (float(a.group(i)) for i in range(1, 7))
        w, lay = float(a.group(7)), a.group(8)
        d = 2 * (x0 * (ym - y1) + xm * (y1 - y0) + x1 * (y0 - ym))
        if abs(d) < 1e-9:                       # degenerate: it is a line
            out.append((x0, y0, x1, y1, w, lay)); continue
        ux = ((x0**2 + y0**2) * (ym - y1) + (xm**2 + ym**2) * (y1 - y0)
              + (x1**2 + y1**2) * (y0 - ym)) / d
        uy = ((x0**2 + y0**2) * (x1 - xm) + (xm**2 + ym**2) * (x0 - x1)
              + (x1**2 + y1**2) * (xm - x0)) / d
        r  = math.hypot(x0 - ux, y0 - uy)
        a0, am, a1 = (math.atan2(p[1] - uy, p[0] - ux) for p in
                      ((x0, y0), (xm, ym), (x1, y1)))
        sweep = (a1 - a0) % (2 * math.pi)
        if not ((am - a0) % (2 * math.pi)) <= sweep:
            sweep -= 2 * math.pi
        n = max(4, int(abs(sweep) * r / 0.05))
        pts = [(ux + r * math.cos(a0 + sweep * i / n),
                uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]
        for i in range(n):
            out.append((pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1], w, lay))
    return out


_PADBLK = re.compile(r'\(pad "([^"]*)" (\w+) (\w+)')


def drills(board):
    """[(x, y, rx, ry)] in board coords for every drilled hole, pads and vias alike."""
    out = []
    for fp in kisexp.footprints(board):
        if not fp.at:
            continue
        fx, fy, rot = fp.at
        a = math.radians(-rot)
        for m in _PADBLK.finditer(fp.body):
            blk = fp.body[m.start():m.start() + 1500]
            at  = re.search(r'\(at ([-\d.]+) ([-\d.]+)', blk)
            dr  = re.search(r'\(drill (oval ([\d.]+) ([\d.]+)|([\d.]+))', blk)
            if not at or not dr:
                continue
            lx, ly = float(at.group(1)), float(at.group(2))
            x = fx + lx * math.cos(a) - ly * math.sin(a)
            y = fy + lx * math.sin(a) + ly * math.cos(a)
            if dr.group(4):
                r = float(dr.group(4)) / 2
                out.append((x, y, r, r))
            else:
                out.append((x, y, float(dr.group(2)) / 2, float(dr.group(3)) / 2))
    for m in re.finditer(r'\(via\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size [\d.]+\)'
                         r'\s*\(drill ([\d.]+)\)', board):
        r = float(m.group(3)) / 2
        out.append((float(m.group(1)), float(m.group(2)), r, r))
    return out


# ------------------------------------------------------------------ the canvas
class Canvas:
    """A crop window in board mm, and the supersampled bitmap it paints into."""

    def __init__(self, x0, y0, x1, y1, px_per_mm, pad_mm=0.0):
        self.x0, self.y0 = x0 - pad_mm, y0 - pad_mm
        self.x1, self.y1 = x1 + pad_mm, y1 + pad_mm
        self.s = px_per_mm * SS
        self.w = max(1, int(round((self.x1 - self.x0) * self.s)))
        self.h = max(1, int(round((self.y1 - self.y0) * self.s)))
        self.im = Image.new("RGB", (self.w, self.h), BG)
        self.d  = ImageDraw.Draw(self.im)
        self.px_per_mm = px_per_mm

    def P(self, x, y):
        return ((x - self.x0) * self.s, (y - self.y0) * self.s)

    def holds(self, x, y):
        """1 if the point is inside this crop. A caption must count what is IN FRAME."""
        return int(self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1)

    def line(self, x0, y0, x1, y1, w_mm, colour):
        w = max(1, int(round(w_mm * self.s)))
        self.d.line([self.P(x0, y0), self.P(x1, y1)], fill=colour, width=w)
        r = w / 2                                     # round caps, as copper has
        for x, y in ((x0, y0), (x1, y1)):
            cx, cy = self.P(x, y)
            self.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour)

    def disc(self, x, y, r_mm, colour, outline=None, ow_mm=0.0):
        cx, cy = self.P(x, y)
        r = r_mm * self.s
        self.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour,
                       outline=outline,
                       width=max(1, int(round(ow_mm * self.s))) if outline else 0)

    def ellipse(self, x, y, rx_mm, ry_mm, colour):
        cx, cy = self.P(x, y)
        rx, ry = rx_mm * self.s, ry_mm * self.s
        self.d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=colour)

    def roundrect(self, x, y, hw, hh, cr, colour, ang=0.0):
        """A pad, TURNED THE WAY THE BOARD TURNS IT.

        345 of this board's 956 pads carry their own 90 or 270 degree rotation -- every
        fine-pitch QFP and SOP side row -- and this used to draw all of them from the
        stored (size w h) as though it were width-by-height in BOARD axes. U1's pin 39 was
        drawn 0.3 mm wide and 1.25 tall where it is physically 1.25 by 0.3: a picture whose
        whole job is to show what size and orientation each land really is, drawing a
        quarter of them across the wrong axis. ECO-18 gave geom.collect() the angle; this
        is the other half.
        """
        a = ang % 360
        if abs(a % 90) < 1e-6:
            if abs(a % 180) > 1e-6:
                hw, hh = hh, hw
            (ax, ay), (bx, by) = self.P(x - hw, y - hh), self.P(x + hw, y + hh)
            r = min(cr * self.s, (bx - ax) / 2, (by - ay) / 2)
            if r <= 0.5:
                self.d.rectangle([ax, ay, bx, by], fill=colour)
            else:
                self.d.rounded_rectangle([ax, ay, bx, by], radius=r, fill=colour)
            return
        # 24 pads on this board sit at 1.25, 15.25, 21, 111, 285.25 and 343 degrees. Walk
        # the rounded rectangle's boundary in the PAD's frame and rotate every point out,
        # the same y-down convention geom._pad_gap measures with.
        cr = max(0.0, min(cr, hw, hh))
        pts = []
        for sx, sy, a0 in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
            ox, oy = sx * (hw - cr), sy * (hh - cr)
            for k in range(7):
                th = math.radians(a0 + 15.0 * k)
                pts.append((ox + cr * math.cos(th), oy + cr * math.sin(th)))
        t = math.radians(a)
        self.polygon([(x + lx * math.cos(t) - ly * math.sin(t),
                       y + lx * math.sin(t) + ly * math.cos(t)) for lx, ly in pts], colour)

    def ring(self, x, y, r_mm, colour, w_mm):
        cx, cy = self.P(x, y)
        r = r_mm * self.s
        self.d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=colour,
                       width=max(1, int(round(w_mm * self.s))))

    def polygon(self, pts, colour):
        self.d.polygon([self.P(x, y) for x, y in pts], fill=colour)

    def finish(self, mirror=False):
        im = self.im.resize((max(1, self.w // SS), max(1, self.h // SS)), Image.LANCZOS)
        return im.transpose(Image.FLIP_LEFT_RIGHT) if mirror else im


# ------------------------------------------------------------------ the painters
def paint(c, board, base, layers, *, fills=True, highlight=True, dim=1.0):
    """Paint `layers` of `board` onto `c`. `dim` fades MouseBiteLabs' copper."""
    segs, vias, pads = geom.collect(board)
    segs = segs + [(a, b, x, y, w, l, "?") for a, b, x, y, w, l in arcs(board)]
    A_seg, A_via, A_pad = geom.added(board, base) if highlight or dim < 1.0 \
        else ([], [], [])
    a_seg = {(round(s[0], 4), round(s[1], 4), round(s[2], 4), round(s[3], 4)) for s in A_seg}
    a_via = {(round(v[0], 4), round(v[1], 4)) for v in A_via}
    a_pad = {p[0] for p in A_pad}

    def fade(rgb):
        return tuple(int(v * dim) for v in rgb) if dim < 1.0 else rgb

    if fills:
        zf = geom.fills(board)
        for lay in ORDER:                       # back-to-front, or an inner pour paints
            if lay not in layers:               # over the outer one it sits beneath
                continue
            for zl, _net, poly in zf:
                if zl == lay and len(poly) >= 3:
                    c.polygon(poly, fade(CU[lay][1]))

    for lay in ORDER:
        if lay not in layers:
            continue
        cu, _ = CU[lay]
        for ax, ay, bx, by, w, l, _n in segs:
            if l != lay:
                continue
            key = (round(ax, 4), round(ay, 4), round(bx, 4), round(by, 4))
            c.line(ax, ay, bx, by,
                   w, ADDED if (highlight and key in a_seg) else fade(cu))
        for pad in pads:
            ref, x, y, hw, hh, cr, plays, _n = pad[:8]
            if not (lay in plays or "*.Cu" in plays):
                continue
            col = ADDED if (highlight and ref in a_pad) else fade(cu)
            if abs(hw - hh) < 1e-9 and cr >= hw - 1e-9:
                c.disc(x, y, hw, col)
            else:
                c.roundrect(x, y, hw, hh, cr, col, pad[8] if len(pad) > 8 else 0.0)

    for x, y, _n in vias:
        col = ADDED if (highlight and (round(x, 4), round(y, 4)) in a_via) else \
              fade(CU["F.Cu"][0])
        c.disc(x, y, 0.35, col)

    for x, y, rx, ry in drills(board):
        c.ellipse(x, y, rx, ry, DRILL)

    for ax, ay, bx, by in geom.edge_segments(board):
        c.line(ax, ay, bx, by, 0.15, EDGE)

    return A_seg, A_via, A_pad


def flag_shorts(c, board, base, A_via, A_pad, layers=None):
    """Ring every object `geom.swallowed` says a stale pour has eaten. Returns how many.

    It does NOT re-derive the set. check [14] ledgers exactly this list, so the ring in the
    picture and the line in the gate are the same fact read twice. They were two
    computations once, and the two disagreed -- 19 against 15 -- which is what exposed the
    footprint-origin bug now recorded in check [14]'s comment.
    """
    haz = geom.swallowed(board, base)
    hazard = {lab for lab, _net, _pour in haz}
    n = 0
    for x, y, _net in A_via:
        if f"via ({x},{y})" in hazard:            # a via is on every layer by definition
            c.ring(x, y, 0.62, ALERT, 0.10)
            n += c.holds(x, y)
    for ref, x, y, hw, hh, _cr, plays, _net in (q[:8] for q in A_pad):
        if ref not in hazard:
            continue
        if layers and not any(l in plays or "*.Cu" in plays for l in layers):
            continue                              # a B.Cu-only pad is not on the front view
        c.ring(x, y, max(hw, hh) + 0.27, ALERT, 0.10)
        n += c.holds(x, y)
    return n, len(haz)


def _wrap(text, font, width_px):
    """Greedy word wrap against the real glyph metrics, so nothing runs off the edge."""
    out, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and font.getbbox(trial)[2] > width_px:
            out.append(line); line = word
        else:
            line = trial
    if line:
        out.append(line)
    return out


def caption(im, title, subtitle, keys, ppm):
    """Band a finished view with a title and a legend. Drawn at 1:1, after the downsample.

    Uses Pillow's own bundled default face rather than a system font, so the pixels do not
    depend on which fonts happen to be installed on the machine that ran it.
    """
    f_t = ImageFont.load_default(size=17)
    f_s = ImageFont.load_default(size=12)
    pad, row, gap = 10, 17, 13
    cols = max(1, min(4, im.size[0] // 176))
    wrap = _wrap(subtitle, f_s, im.size[0] - 2 * pad - 96)
    krow = (len(keys) + cols - 1) // cols
    band = pad * 2 + row + len(wrap) * gap + 4 + krow * row
    out = Image.new("RGB", (im.size[0], im.size[1] + band), (26, 26, 31))
    out.paste(im, (0, 0))
    d = ImageDraw.Draw(out)
    d.line([(0, im.size[1]), (im.size[0], im.size[1])], fill=(58, 58, 66), width=1)
    y = im.size[1] + pad
    d.text((pad, y), title, font=f_t, fill=(238, 238, 242))
    y += row + 1
    for ln in wrap:
        d.text((pad, y), ln, font=f_s, fill=(150, 150, 160))
        y += gap
    y += 4
    x, col = pad, 0
    for label, colour in keys:
        d.rectangle([x, y + 2, x + 9, y + 11], fill=colour, outline=(70, 70, 78))
        d.text((x + 14, y), label, font=f_s, fill=LABEL)
        col += 1
        if col % cols == 0:
            x, y = pad, y + row
        else:
            x += 176
    d.text((out.size[0] - pad - 128, im.size[1] + pad + 2),
           f"{ppm:.0f} px/mm", font=f_s, fill=(120, 120, 130))
    return out


# ------------------------------------------------------------------ the views
def bbox(pts, pad):
    """A crop window around `pts`, padded, squared up so neither view is a sliver."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    w, h = x1 - x0, y1 - y0
    if w < h:
        cx = (x0 + x1) / 2; x0, x1 = cx - h / 2, cx + h / 2
    elif h < w:
        cy = (y0 + y1) / 2; y0, y1 = cy - w / 2, cy + w / 2
    return (x0, y0, x1, y1)


def views(board):
    """[(filename, builder)] -- every picture this repository ships, and its crop."""
    e = geom.edge_segments(board)
    xs = [v for s in e for v in (s[0], s[2])]
    ys = [v for s in e for v in (s[1], s[3])]
    BB = (min(xs), min(ys), max(xs), max(ys))
    # Crop to WHERE THE COPPER IS, not to a footprint's origin. MOD1's origin sits 5-7 mm
    # east of its own pads (the module body extends past the landed lattice sites), so an
    # origin-centred crop cuts two of the three landings out of frame.
    _seg, _via, A_pad = geom.added(board, geom.base())
    mod = [p for p in A_pad if p[0].startswith("MOD1.")]
    LAND = bbox([(p[1], p[2]) for p in mod], 1.9)
    near = [p for p in A_pad if p[0].split(".")[0] in ("MOD1", "C7", "TP83", "TP84", "TP85")]
    WIN = bbox([(p[1], p[2]) for p in near], 4.6)
    return [
        ("agbm02_front.png",        lambda b, s: whole(b, s, ["F.Cu"], BB, False)),
        ("agbm02_back.png",         lambda b, s: whole(b, s, ["B.Cu"], BB, True)),
        ("agbm02_cxc_diff.png",     lambda b, s: diff(b, s, BB)),
        ("agbm02_cxc_placement.png",lambda b, s: window(
            b, s, WIN, 34.0,
            "The ClockxControl window -- ECO-6's placement",
            "The component-free window below the RAM that ECO-6 opens by moving C7, with "
            "the MOD1 landings, the routing to TP2/TP8/TP9 and the three wire pads. "
            "{n} of the {tot} objects a stale pour swallows are in frame.")),
        ("agbm02_cxc_landings.png", lambda b, s: window(
            b, s, LAND, 96.0,
            "The MOD1 landings, close up",
            "Three of the module's six lattice sites are landed -- an L, not a row or "
            "column. The other three exist only as F.Fab circles and are not drawn. "
            "All {n} land inside the VDD35 or VDD2 pour until someone re-pours.")),
        ("agbm02_pin1_front.png",   lambda b, s: pin1_view(b, s, "front")),
        ("agbm02_pin1_back.png",    lambda b, s: pin1_view(b, s, "back")),
        ("agbm02_cxc_fit.png",      fit),
        ("agbm02_cxc_1to1_600dpi.png", sheet),
    ]


KEY_ADDED = ("copper this fork adds", ADDED)
KEY_ALERT = ("in a foreign-net pour", ALERT)


def _keys(layers, added=True):
    k = [KEY_ADDED] if added else []
    k += [(f"{l} track / pad", CU[l][0]) for l in ORDER if l in layers]
    k += [(f"{l} pour (stored)", CU[l][1]) for l in ORDER if l in layers]
    return k + [KEY_ALERT]


def whole(board, base, layers, bb, mirror):
    ppm = 11.0
    c = Canvas(*bb, px_per_mm=ppm, pad_mm=1.2)
    _s, A_via, A_pad = paint(c, board, base, layers)
    n, tot = flag_shorts(c, board, base, A_via, A_pad, layers)
    side = "front" if layers == ["F.Cu"] else "back, mirrored so it reads as you look at it"
    im = caption(c.finish(mirror),
                 f"AGBM-02 + ClockxControl -- {layers[0]} ({side})",
                 f"MouseBiteLabs' AGBM-02_AA_1-1 with this fork's copper in yellow. "
                 f"{n} of the {tot} objects a stale pour swallows are on this layer.",
                 _keys(layers), ppm)
    return im, f"{layers[0]}, {n} object(s) ringed in a foreign pour"


def diff(board, base, bb):
    """MouseBiteLabs' copper faded to a third; this fork's at full value."""
    ppm = 11.0
    c = Canvas(*bb, px_per_mm=ppm, pad_mm=1.2)
    _s, A_via, A_pad = paint(c, board, base, ORDER, dim=0.34)
    n, tot = flag_shorts(c, board, base, A_via, A_pad)
    im = caption(c.finish(False),
                 "AGBM-02 + ClockxControl -- the copper diff, all four layers",
                 "Everything MouseBiteLabs routed is faded to a third. Everything at full "
                 f"value is what ECO-6 added or moved. All {n} objects a stale "
                 f"pour swallows are ringed.",
                 _keys(ORDER), ppm)
    return im, f"all layers, this fork's copper at full value, {n} ringed"


def window(board, base, win, ppm, title, sub):
    c = Canvas(*win, px_per_mm=ppm)
    _s, A_via, A_pad = paint(c, board, base, ORDER, dim=0.55)
    n, tot = flag_shorts(c, board, base, A_via, A_pad)
    im = caption(c.finish(False), title, sub.format(n=n, tot=tot), _keys(ORDER), ppm)
    return im, f"module window at {ppm:.0f} px/mm, {n} ringed"


# ------------------------------------------------------- where pin 1 actually lands
# The CPL exports one number per part -- `rot` -- and an assembly line turns the part by it
# from THEIR zero reference. If that reference differs from the board's, every polarised and
# every multi-pin part goes in wrong, and nothing in a netlist or a BOM can tell you.
#
# What CAN be shown is where pin 1 physically sits, which is the thing the rotation exists to
# control. These views mark it on every placed part whose orientation matters -- a bright dot
# on pin 1 and a stalk back to the part centre -- so the convention can be checked by eye,
# part by part, against the raytraced assembly renders and against a package datasheet.
#
# The 131 0603/0805 passives are deliberately NOT marked. A two-terminal symmetric chip
# resistor at 0 degrees and at 180 degrees is the same part in the same place; marking them
# would bury the 39 that matter under noise that cannot be wrong.
SYMMETRIC_2PIN = {
    "C_0603_1608Metric_Boxed_2", "R_0603_1608Metric_Boxed", "C_0805_2012Metric_Boxed_2",
    "Fuse_0805_2012Metric", "L_0603_1608Metric", "L_Taiyo-Yuden_NR-20xx_HandSoldering",
}
POLARIZED_2PIN = {
    "C_1210_3225Metric_Boxed_2", "D_SOD-323F",
    "LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder",
}
PIN1 = (120, 255, 160)
PIN1_POL = (255, 120, 200)


def rotation_sensitive(board):
    """[(ref, cx, cy, x1, y1, layer, polarised)] for every PLACED part whose rotation matters."""
    import bom_split
    _s, _v, pads = geom.collect(board)
    first = {}
    for pref, x, y, _hw, _hh, _cr, _lay, _net in (p[:8] for p in pads):
        ref, _, pn = pref.partition(".")
        if pn == "1":
            first.setdefault(ref, (x, y))
    out = []
    for fp in kisexp.footprints(board):
        if fp.at is None or "*" in (fp.ref or ""):
            continue
        if bom_split.classify(fp)[0] != "assembly":
            continue
        fam = fp.name.split(":")[-1]
        if fam in SYMMETRIC_2PIN or fp.ref not in first:
            continue
        x1, y1 = first[fp.ref]
        out.append((fp.ref, fp.at[0], fp.at[1], x1, y1, fp.layer, fam in POLARIZED_2PIN))
    return sorted(out)


def pin1_view(board, base, side):
    e = geom.edge_segments(board)
    xs = [v for sg in e for v in (sg[0], sg[2])]
    ys = [v for sg in e for v in (sg[1], sg[3])]
    layers = ["F.Cu"] if side == "front" else ["B.Cu"]
    ppm = 11.0
    c = Canvas(min(xs), min(ys), max(xs), max(ys), px_per_mm=ppm, pad_mm=1.2)
    paint(c, board, base, layers, highlight=False, dim=0.42)
    want = "F.Cu" if side == "front" else "B.Cu"
    n = pol = 0
    f = ImageFont.load_default(size=11)
    for ref, cx, cy, x1, y1, lay, is_pol in rotation_sensitive(board):
        if lay != want:
            continue
        col = PIN1_POL if is_pol else PIN1
        c.line(cx, cy, x1, y1, 0.09, col)           # stalk: centre -> pin 1
        c.disc(x1, y1, 0.30, col)
        c.ring(cx, cy, 0.16, col, 0.07)
        n += 1
        pol += is_pol
    im = c.finish(side == "back")
    d = ImageDraw.Draw(im)
    for ref, cx, cy, x1, y1, lay, is_pol in rotation_sensitive(board):
        if lay != want:
            continue
        px, py = c.P(x1, y1)
        px, py = px / SS, py / SS
        if side == "back":
            px = im.size[0] - px
        d.text((px + 5, py - 5), ref, font=f, fill=(255, 255, 255))
    return caption(
        im,
        f"Pin 1 on every rotation-sensitive part -- {want} ({side})",
        f"{n} part(s) on this side whose CPL rotation actually changes where the part goes, "
        f"{pol} of them polarised. The dot is pin 1; the stalk runs back to the placement "
        f"origin the CPL reports. The 131 symmetric 0603/0805 passives are not marked -- at "
        f"0 or 180 degrees they are the same part in the same place.",
        [("pin 1", PIN1), ("pin 1, POLARISED part", PIN1_POL)] + _keys(layers, added=False),
        ppm), f"{side}: {n} rotation-sensitive part(s), {pol} polarised"


# ------------------------------------------------------------------ the module itself
_FPGEO = re.compile(r'\(fp_(rect|circle)([\s\S]{0,400}?)\n\t\t\)')


def module_geometry(board):
    """MOD1's own body, courtyard and lattice, read off the board rather than restated.

    Returns (body, courtyard, landed, ghosts) in BOARD coords. `ghosts` are the three
    lattice sites that exist only as F.Fab circles -- the module has six, this fork lands
    three, and no document says why those three. Drawing them is the point: the open
    question in ECO-14 §14.5 is a geometric one, and prose was the wrong medium for it.
    """
    fp = kisexp.by_ref(board)["MOD1"]
    fx, fy, rot = fp.at
    a = math.radians(-rot)
    T = lambda lx, ly: (fx + lx * math.cos(a) - ly * math.sin(a),
                        fy + lx * math.sin(a) + ly * math.cos(a))
    body = crtyd = None
    ghosts = []
    for m in _FPGEO.finditer(fp.body):
        kind, blk = m.group(1), m.group(2)
        lay = re.search(r'\(layer "([^"]+)"\)', blk)
        lay = lay.group(1) if lay else ""
        pts = [(float(x), float(y)) for x, y in
               re.findall(r'\((?:start|end|center|mid) ([-\d.]+) ([-\d.]+)\)', blk)]
        if kind == "rect" and len(pts) == 2:
            r = (T(*pts[0]), T(*pts[1]))
            if lay == "F.Fab":
                body = r
            elif lay == "F.CrtYd":
                crtyd = r
        elif kind == "circle" and len(pts) == 2 and lay == "F.Fab":
            ghosts.append((T(*pts[0]), math.dist(pts[0], pts[1])))
    _s, _v, pads = geom.collect(board)
    landed = [(p[0], p[1], p[2], max(p[3], p[4])) for p in pads
              if p[0].startswith("MOD1.")]
    return body, crtyd, sorted(landed), ghosts


def fit(board, base):
    """The module body over the board, with all six lattice sites drawn."""
    body, crtyd, landed, ghosts = module_geometry(board)
    (bx0, by0), (bx1, by1) = crtyd
    ppm = 46.0
    c = Canvas(min(bx0, bx1) - 1.6, min(by0, by1) - 1.6,
               max(bx0, bx1) + 1.6, max(by0, by1) + 1.6, px_per_mm=ppm)
    _s, A_via, A_pad = paint(c, board, base, ORDER, dim=0.42)
    n, tot = flag_shorts(c, board, base, A_via, A_pad)
    for rect, colour, w in ((crtyd, (120, 200, 255), 0.08), (body, (236, 236, 214), 0.12)):
        (x0, y0), (x1, y1) = rect
        for seg in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
            c.line(*seg, w, colour)
    for (gx, gy), r in ghosts:
        c.ring(gx, gy, r, (150, 150, 160), 0.09)
        c.ring(gx, gy, r * 0.30, (150, 150, 160), 0.09)
    for _ref, lx, ly, r in landed:
        c.ring(lx, ly, r + 0.42, (120, 255, 160), 0.09)
    im = caption(
        c.finish(False),
        "MOD1 fit check -- the module body over the board",
        f"White is the module body ({abs(body[1][0]-body[0][0]):.2f} x "
        f"{abs(body[1][1]-body[0][1]):.2f} mm), blue its courtyard. Green marks the three "
        f"lattice sites this fork LANDS; grey rings the three it does not -- they exist "
        f"only as F.Fab circles. Which three are landed, and why those three, is the open "
        f"item in ECO-14 §14.5 and needs a physical module to settle. {n} of the {tot} "
        f"objects a stale pour swallows are in frame.",
        [KEY_ADDED, ("landed lattice site", (120, 255, 160)),
         ("unlanded lattice site", (150, 150, 160)), ("module body", (236, 236, 214)),
         ("courtyard", (120, 200, 255)), KEY_ALERT], ppm)
    return im, f"module fit at {ppm:.0f} px/mm, {len(landed)} landed, {len(ghosts)} not"


def sheet(board, base):
    """1:1 at 600 dpi. Print at 100% and lay a real module on the paper."""
    DPI = 600.0
    ppm = DPI / 25.4
    body, crtyd, landed, ghosts = module_geometry(board)
    (bx0, by0), (bx1, by1) = crtyd
    c = Canvas(min(bx0, bx1) - 3.0, min(by0, by1) - 3.0,
               max(bx0, bx1) + 3.0, max(by0, by1) + 8.0, px_per_mm=ppm)
    _s, A_via, A_pad = paint(c, board, base, ORDER, dim=0.42)
    flag_shorts(c, board, base, A_via, A_pad)
    (x0, y0), (x1, y1) = body
    for seg in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        c.line(*seg, 0.10, (236, 236, 214))
    for (gx, gy), r in ghosts:
        c.ring(gx, gy, r, (150, 150, 160), 0.08)
    # A 10 mm ruler, so a mis-scaled print gives itself away before anything is measured.
    rx, ry = min(x0, x1), max(by0, by1) + 5.0
    c.line(rx, ry, rx + 10.0, ry, 0.16, (236, 236, 214))
    for i in range(11):
        c.line(rx + i, ry, rx + i, ry - (0.9 if i % 5 == 0 else 0.5), 0.12, (236, 236, 214))
    im = caption(
        c.finish(False),
        "MOD1 landings, 1:1 at 600 dpi",
        "PRINT AT 100% WITH NO SCALING, then lay a real ClockxControl on the paper. The "
        "10 mm ruler above the body must measure 10 mm; if it does not, the print was "
        "scaled and nothing on this sheet can be trusted. Grey rings are the three lattice "
        "sites this fork does not land.",
        [KEY_ADDED, ("module body", (236, 236, 214)),
         ("unlanded lattice site", (150, 150, 160)), KEY_ALERT], ppm)
    return im, f"1:1 print sheet at {DPI:.0f} dpi with a 10 mm ruler"


# ------------------------------------------------------------------ drive
def digest(im):
    return hashlib.sha256(im.tobytes()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="re-render and compare pixel digests; write nothing")
    ap.add_argument("--list", action="store_true", help="name the views and exit")
    a = ap.parse_args()

    board = kisexp.load(BOARD)
    try:
        base = geom.base()
    except OSError as e:
        print(f"base board unreadable ({e})", file=sys.stderr)
        return 2
    vs = views(board)
    if a.list:
        for name, _ in vs:
            print(name)
        return 0

    import PIL
    man = {"pillow": PIL.__version__, "supersample": SS, "views": {}}
    bad = []
    for name, build in vs:
        im, caption = build(board, base)
        d = digest(im)
        man["views"][name] = {"size": list(im.size), "pixels": d, "caption": caption}
        path = os.path.join(OUTDIR, name)
        if a.check:
            if not os.path.exists(path):
                bad.append(f"{name}: not in the tree")
            else:
                have = digest(Image.open(path).convert("RGB"))
                if have != d:
                    bad.append(f"{name}: tree {have} != re-render {d}")
        else:
            im.save(path, "PNG", optimize=True)
            print(f"  {name:28s} {im.size[0]:5d}x{im.size[1]:<5d} {d}  {caption}")

    if a.check:
        old = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
        if bad:
            print("RE-RENDER DIFFERS from the tree:", file=sys.stderr)
            for b in bad:
                print("  " + b, file=sys.stderr)
            if old.get("pillow") != PIL.__version__:
                print(f"  NOTE: manifest was written by Pillow {old.get('pillow')}, "
                      f"this is {PIL.__version__} -- a rasteriser change can do this",
                      file=sys.stderr)
            return 1
        print(f"ok: all {len(vs)} views re-render to the pixels in the tree")
        return 0

    with open(MANIFEST, "w", newline="") as f:
        json.dump(man, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {len(vs)} view(s) + render-manifest.json into "
          f"{os.path.relpath(OUTDIR, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
