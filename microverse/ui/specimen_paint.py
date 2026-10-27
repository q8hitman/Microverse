"""Procedural drawing of organisms from their MorphSpec, in three display modes.

Everything is drawn in the agent's own frame: origin at the agent position, x along its heading,
1 µm = `k` pixels. Shapes come from typical microscopy (see library/morphology.py); structures that
are invisible in a light microscope (bacterial flagella, 20 nm wide) are drawn ONLY in the
explanation mode, and are labelled as schematic there.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QRadialGradient

from ..library.morphology import MorphSpec
from ..viz.population import DIVIDING, DYING, GRAZED, Agent


class Look:
    """Colours for one display mode."""

    def __init__(self, mode: str, stain: str = ""):
        self.mode, self.stain = mode, stain

    def body(self, natural: str, alpha: float) -> tuple[QColor, QColor]:
        """(fill, outline) for a cell body."""
        if self.mode == "microscope":
            if self.stain == "gram":                         # crystal violet: Gram-positive cells stain purple
                f = QColor(104, 52, 150)
                f.setAlphaF(0.92 * alpha)
                o = QColor(60, 25, 100)
                o.setAlphaF(alpha)
                return f, o
            f = QColor(70, 72, 76)                            # phase contrast: dark cells, bright halo
            f.setAlphaF(0.88 * alpha)
            o = QColor(235, 238, 240)
            o.setAlphaF(0.55 * alpha)
            return f, o
        c = QColor(natural)
        f = QColor(c)
        f.setAlphaF(0.78 * alpha)
        o = c.darker(175)
        o.setAlphaF(0.9 * alpha)
        return f, o

    def detail(self, natural: str, alpha: float) -> QColor:
        if self.mode == "microscope":
            c = QColor(30, 30, 34) if self.stain != "gram" else QColor(50, 20, 80)
        else:
            c = QColor(natural)
        c.setAlphaF(alpha)
        return c


def _capsule(length: float, width: float, cx: float = 0.0) -> QPainterPath:
    p = QPainterPath()
    p.addRoundedRect(QRectF(cx - length / 2, -width / 2, length, width), width / 2, width / 2)
    return p


def _fill(p: QPainter, path: QPainterPath, look: Look, natural: str, alpha: float, k_outline: float):
    fill, outline = look.body(natural, alpha)
    if look.mode == "microscope" and look.stain != "gram":
        p.setPen(QPen(outline, max(1.2, k_outline * 3), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)                                      # halo
        p.setPen(Qt.NoPen)
    else:
        p.setPen(QPen(outline, max(0.6, k_outline), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(fill)
    p.drawPath(path)


def paint_agent(p: QPainter, spec: MorphSpec, a: Agent, k: float, look: Look, extra: dict | None = None) -> None:
    """Draw one agent. `k` = pixels per µm."""
    extra = extra or {}
    alpha = 1.0
    scale = (0.55 + 0.45 * a.grow) * a.size
    if a.state == DYING:
        alpha = max(0.0, 1.0 - a.progress)
        scale *= 1.0 + 0.15 * a.progress                     # cells swell slightly before lysis
    elif a.state == GRAZED:
        scale *= max(0.05, 1.0 - a.progress)
        alpha = max(0.2, 1.0 - a.progress * 0.6)
    if alpha <= 0.01:
        return
    L = spec.length_um * scale * k
    W = spec.width_um * scale * k
    q = a.progress if a.state == DIVIDING else 0.0
    p.save()
    p.translate(a.x * k, a.y * k)
    p.rotate(math.degrees(a.heading))
    lw = max(0.5, W * 0.06)
    shape = spec.shape
    col = spec.colour
    if shape in ("rod", "club_rod"):
        _rod(p, spec, a, L, W, q, look, col, alpha, lw)
    elif shape in ("coccus", "ovococcus"):
        _chain(p, spec, a, L, W, q, look, col, alpha, lw)
    elif shape == "packet":
        _packet(p, a, L, q, look, col, alpha, lw)
    elif shape == "oval":
        _oval(p, spec, a, L, W, q, look, col, alpha, lw)
    elif shape == "sphere":
        _sphere(p, a, L, q, look, col, alpha, lw)
    elif shape == "coenobium":
        _coenobium(p, a, L, W, q, look, col, alpha, lw)
    elif shape == "boat":
        _diatom(p, a, L, W, q, look, col, alpha, lw)
    elif shape == "spindle":
        _euglena(p, a, L, W, q, look, col, alpha, lw)
    elif shape in ("pear", "slipper"):
        _ciliate(p, spec, a, L, W, q, look, col, alpha, lw)
    elif shape == "amoeboid":
        _amoeba(p, a, L, W, q, look, col, alpha, lw)
    elif shape == "bell":
        _vorticella(p, a, L, W, q, look, col, alpha, lw)
    elif shape == "rotifer_lorica":
        _brachionus(p, a, L, W, q, look, col, alpha, lw, extra.get("eggs", 0))
    elif shape == "rotifer_bdelloid":
        _bdelloid(p, a, L, W, q, look, col, alpha, lw)
    elif shape == "hypha":
        _hypha(p, spec, a, L, W, q, look, col, alpha, lw)
    else:
        _fill(p, _capsule(L, W), look, col, alpha, lw)
    p.restore()


# ---------------------------------------------------------------- bacteria & archaea
def _rod(p, spec, a, L, W, q, look, col, alpha, lw):
    W = max(W, 1.2)
    L = max(L, W * 1.05)
    n = max(a.n, 1)
    total = L * n
    x0 = -total / 2 + L / 2
    for j in range(n):
        cx = x0 + j * L
        if j == 0 and q > 0:                                  # elongate, then constrict in the middle
            Lt = L * (1 + 0.54 * q)
            half = Lt / 2 + W * (1 - q) * 0.5
            path = _capsule(half, W, cx - Lt / 4).united(_capsule(half, W, cx + Lt / 4))
        elif spec.shape == "club_rod":
            path = QPainterPath()
            path.moveTo(cx - L / 2, -W * 0.32)
            path.lineTo(cx + L / 2 - W * 0.55, -W * 0.58)
            path.arcTo(QRectF(cx + L / 2 - W * 1.1, -W * 0.58, W * 1.1, W * 1.16), 90, -180)
            path.lineTo(cx - L / 2, W * 0.32)
            path.arcTo(QRectF(cx - L / 2 - W * 0.32, -W * 0.32, W * 0.64, W * 0.64), 270, -180)
            path.closeSubpath()
        else:
            path = _capsule(L, W, cx)
        fade = alpha * (1 - a.tail_fade) if (j == n - 1 and a.tail_fade > 0) else alpha
        _fill(p, path, look, col, fade, lw)
        if "gas_vesicles" in spec.features and look.mode != "microscope" and L > 6:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(70 * fade)))
            p.drawEllipse(QPointF(cx - L * 0.15, 0), W * 0.18, W * 0.14)
            p.drawEllipse(QPointF(cx + L * 0.2, 0), W * 0.15, W * 0.12)
    if look.mode == "explain" and L > 6:                       # schematic flagella (not visible in light microscopy)
        pen = QPen(QColor(120, 120, 120, int(150 * alpha)), max(0.5, W * 0.05))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if "polar_flagellum" in spec.features:
            _wave(p, -total / 2, 0, -1, L * 1.4, W * 0.25, a.phase * 18)
        elif "peritrichous_flagella" in spec.features:
            for j, (sx, sy) in enumerate(((-0.3, -1), (0.1, -1), (0.35, 1), (-0.1, 1))):
                p.save()
                p.translate(sx * total, sy * W / 2)
                p.rotate(160 if sy < 0 else -160)
                _wave(p, 0, 0, 1, L * 0.9, W * 0.2, a.phase * 15 + j)
                p.restore()


def _wave(p, x, y, direction, length, amp, phase):
    path = QPainterPath(QPointF(x, y))
    steps = 14
    for i in range(1, steps + 1):
        t = i / steps
        path.lineTo(x + direction * length * t, y + amp * math.sin(t * 12 + phase))
    p.drawPath(path)


def _chain(p, spec, a, L, W, q, look, col, alpha, lw):
    r_long = max(L / 2, 0.8)
    r_short = max(W / 2, 0.8)
    if spec.shape == "coccus":
        r_long = r_short = max(r_long, r_short)
    n = max(a.n, 1)
    dividing = a.gain if q > 0 else 0
    curve = (a.variant - 0.5) * 0.25
    # lay out cell centres along a gently curved chain
    units = []
    for j in range(n):
        units.append(("split" if j < dividing else "cell", j))
    step = r_long * 1.9
    total = step * (n + dividing * q * 0.55)
    x, y, ang = -total / 2 + r_long, 0.0, -curve * n / 2
    for kind, j in units:
        fade = alpha * (1 - a.tail_fade) if (j == n - 1 and a.tail_fade > 0) else alpha
        if kind == "split":
            off = r_long * 0.55 * q
            c1 = QPointF(x - math.cos(ang) * off, y - math.sin(ang) * off)
            c2 = QPointF(x + math.cos(ang) * off, y + math.sin(ang) * off)
            path = QPainterPath()
            path.addEllipse(c1, r_long, r_short)
            p2 = QPainterPath()
            p2.addEllipse(c2, r_long, r_short)
            _fill(p, path.united(p2), look, col, fade, lw)
            adv = step * (1 + 0.55 * q)
        else:
            path = QPainterPath()
            path.addEllipse(QPointF(x, y), r_long, r_short)
            _fill(p, path, look, col, fade, lw)
            adv = step
        x += math.cos(ang) * adv
        y += math.sin(ang) * adv
        ang += curve
    if "capsule" in spec.features and look.mode == "explain":
        p.setPen(QPen(QColor(200, 200, 200, 90), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(-total / 2 - r_long * 0.4, -r_short * 1.6, total + r_long * 0.8, r_short * 3.2),
                          r_short * 1.6, r_short * 1.6)


def _packet(p, a, L, q, look, col, alpha, lw):
    r = max(L / 2, 0.8)
    n = max(a.n, 1)
    cols = 2
    for j in range(n):
        gx, gy = (j % cols) - 0.5, (j // cols) - (math.ceil(n / cols) - 1) / 2
        jitter = math.sin(a.variant * 50 + j * 2.3) * r * 0.12
        c = QPointF(gx * r * 1.85 + jitter, gy * r * 1.85 - jitter)
        path = QPainterPath()
        if j < (a.gain if q > 0 else 0):
            off = r * 0.5 * q
            path.addEllipse(c + QPointF(-off, 0), r * 0.95, r)
            p2 = QPainterPath()
            p2.addEllipse(c + QPointF(off, 0), r * 0.95, r)
            path = path.united(p2)
        else:
            path.addEllipse(c, r * 0.95, r)
        fade = alpha * (1 - a.tail_fade) if (j == n - 1 and a.tail_fade > 0) else alpha
        _fill(p, path, look, col, fade, lw)


def _oval(p, spec, a, L, W, q, look, col, alpha, lw):
    n = max(a.n, 1)
    if spec.division == "budding":
        rx, ry = max(L / 2, 1.0), max(W / 2, 1.0)
        body = QPainterPath()
        body.addEllipse(QPointF(0, 0), rx, ry)
        if q > 0:                                             # the bud grows from one pole
            ang = a.variant * 0.6 - 0.3
            br = rx * 0.68 * q
            bc = QPointF(math.cos(ang) * (rx + br * 0.75), math.sin(ang) * (rx + br * 0.75))
            bud = QPainterPath()
            bud.addEllipse(bc, br, br * 0.92)
            body = body.united(bud)
        _fill(p, body, look, col, alpha, lw)
        if look.mode != "microscope" and rx > 4:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(60 * alpha)))                # vacuole
            p.drawEllipse(QPointF(-rx * 0.15, ry * 0.1), rx * 0.35, ry * 0.33)
            if "bud_scar" in spec.features and a.variant > 0.4:
                p.setPen(QPen(look.detail(col, 0.5 * alpha).darker(150), max(0.5, rx * 0.04)))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(-rx * 0.75, -ry * 0.4), rx * 0.12, rx * 0.12)
        return
    # Azotobacter: large ovoid cells in pairs
    step = L * 0.98
    total = step * n
    for j in range(n):
        cx = -total / 2 + step / 2 + j * step
        path = QPainterPath()
        if j == 0 and q > 0:
            off = L * 0.27 * q
            path.addEllipse(QPointF(cx - off, 0), L / 2, W / 2)
            p2 = QPainterPath()
            p2.addEllipse(QPointF(cx + off, 0), L / 2, W / 2)
            path = path.united(p2)
        else:
            path.addEllipse(QPointF(cx, 0), L / 2, W / 2)
        fade = alpha * (1 - a.tail_fade) if (j == n - 1 and a.tail_fade > 0) else alpha
        _fill(p, path, look, col, fade, lw)


# ---------------------------------------------------------------- algae
def _sphere(p, a, L, q, look, col, alpha, lw):
    r = max(L / 2, 1.0) * (1 + 0.35 * q)                       # the mother swells before releasing autospores
    if look.mode == "microscope":
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), r, r)
        _fill(p, path, look, col, alpha, lw)
    else:
        g = QRadialGradient(QPointF(-r * 0.3, -r * 0.3), r * 1.3)
        c = QColor(col)
        g.setColorAt(0, c.lighter(150))
        g.setColorAt(0.7, c)
        g.setColorAt(1, c.darker(160))
        p.setPen(QPen(c.darker(220), max(0.6, r * 0.06)))
        p.setBrush(QBrush(g))
        p.setOpacity(alpha)
        p.drawEllipse(QPointF(0, 0), r, r)
        p.setOpacity(1.0)
    if r < 2.5:
        return
    if q > 0.25:                                              # autospores inside the mother wall
        k_n = a.gain + 1
        s = min(1.0, (q - 0.25) / 0.5)
        p.setPen(QPen(look.detail(col, 0.6 * alpha * s).darker(140), max(0.5, r * 0.04)))
        p.setBrush(look.detail(col, 0.55 * alpha * s))
        for j in range(k_n):
            ang = j * 2 * math.pi / k_n + a.variant * 6
            p.drawEllipse(QPointF(math.cos(ang) * r * 0.42, math.sin(ang) * r * 0.42), r * 0.4, r * 0.4)
        return
    if look.mode != "microscope":                             # cup-shaped chloroplast and pyrenoid
        c = QColor(col).darker(150)
        c.setAlphaF(0.85 * alpha)
        p.setPen(QPen(c, max(1.0, r * 0.32)))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(-r * 0.68, -r * 0.68, r * 1.36, r * 1.36), int(a.variant * 360 * 16), 220 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(225, 240, 205, int(190 * alpha)))
        p.drawEllipse(QPointF(r * 0.12, r * 0.08), r * 0.17, r * 0.17)


def _coenobium(p, a, L, W, q, look, col, alpha, lw):
    cells = 4
    cw = W * 0.95
    cl = L * 0.75
    for layer, (dy, s) in enumerate(((0.0, 1.0), (W * 1.1 * q, q))):
        if s <= 0.02:
            continue
        for j in range(cells):
            y = (j - (cells - 1) / 2) * cw / 2.1 * 1.0 + dy
            path = QPainterPath()
            path.addEllipse(QPointF(0, y), cl / 2 * s, cw / 4.4 * s)
            _fill(p, path, look, col, alpha * (0.6 + 0.4 * s), lw)
        if look.mode != "microscope" and s > 0.6:
            p.setPen(QPen(look.detail(col, 0.8 * alpha).darker(150), max(0.5, W * 0.03)))
            y_top = -(cells - 1) / 2 * cw / 2.1 + dy
            y_bot = (cells - 1) / 2 * cw / 2.1 + dy
            for (x, y, sx, sy) in ((-cl / 2, y_top, -1, -1), (cl / 2, y_top, 1, -1),
                                   (-cl / 2, y_bot, -1, 1), (cl / 2, y_bot, 1, 1)):
                p.drawLine(QPointF(x * 0.9, y), QPointF(x * 0.9 + sx * cl * 0.25, y + sy * W * 0.35))


def _diatom(p, a, L, W, q, look, col, alpha, lw):
    for side, s in ((-1, 1.0), (1, 1.0)) if q > 0 else ((0, 1.0),):
        dy = side * W * 0.55 * q
        path = QPainterPath()
        path.moveTo(-L / 2, dy)
        path.cubicTo(-L * 0.3, dy - W * 0.62, L * 0.3, dy - W * 0.62, L / 2, dy)
        path.cubicTo(L * 0.3, dy + W * 0.62, -L * 0.3, dy + W * 0.62, -L / 2, dy)
        _fill(p, path, look, col, alpha, lw)
        if L < 8:
            continue
        det = look.detail(col, 0.7 * alpha).darker(170)
        p.setPen(QPen(det, max(0.5, L * 0.012)))
        p.drawLine(QPointF(-L * 0.4, dy), QPointF(-L * 0.04, dy))          # raphe with central nodule
        p.drawLine(QPointF(L * 0.04, dy), QPointF(L * 0.4, dy))
        for j in range(-6, 7):                                              # striae
            x = j * L * 0.065
            hh = W * 0.38 * math.sqrt(max(0.0, 1 - (x / (L * 0.5)) ** 2))
            p.drawLine(QPointF(x, dy - hh), QPointF(x, dy - W * 0.06))
            p.drawLine(QPointF(x, dy + W * 0.06), QPointF(x, dy + hh))
        if look.mode == "natural":                                          # two plate-like plastids
            c = QColor("#8a6d1f")
            c.setAlphaF(0.45 * alpha)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(-L * 0.35, dy - W * 0.3, L * 0.7, W * 0.18), W * 0.09, W * 0.09)
            p.drawRoundedRect(QRectF(-L * 0.35, dy + W * 0.12, L * 0.7, W * 0.18), W * 0.09, W * 0.09)


# ---------------------------------------------------------------- protists
def _spindle_path(L, W, wobble):
    path = QPainterPath()
    path.moveTo(L / 2, 0)
    path.cubicTo(L * 0.25, -W * (0.6 + wobble), -L * 0.2, -W * 0.55, -L / 2, 0)
    path.cubicTo(-L * 0.2, W * 0.55, L * 0.25, W * (0.6 - wobble), L / 2, 0)
    return path


def _euglena(p, a, L, W, q, look, col, alpha, lw):
    wob = 0.12 * math.sin(a.phase * 1.3)                                    # metaboly: slow shape change
    for side in ((-1, 1) if q > 0 else (0,)):
        p.save()
        p.translate(0, side * W * 0.55 * q)
        p.rotate(side * 8 * q)
        w = W * (1 - 0.35 * q) if q > 0 else W
        _fill(p, _spindle_path(L, w, wob), look, col, alpha, lw)
        if look.mode != "microscope" and L > 15:
            p.setPen(Qt.NoPen)
            c = QColor(col).darker(140)
            c.setAlphaF(0.7 * alpha)
            p.setBrush(c)
            for j in range(7):                                              # disc chloroplasts
                x = -L * 0.32 + j * L * 0.1
                y = math.sin(j * 2.1 + a.variant * 9) * w * 0.18
                p.drawEllipse(QPointF(x, y), L * 0.04, w * 0.14)
            p.setBrush(QColor(220, 40, 30, int(220 * alpha)))               # eyespot (stigma)
            p.drawEllipse(QPointF(L * 0.33, -w * 0.12), L * 0.025, L * 0.025)
        if L > 12:                                                          # the flagellum: thick enough to see
            p.setPen(QPen(look.detail(col, 0.55 * alpha).darker(130), max(0.6, L * 0.012)))
            p.setBrush(Qt.NoBrush)
            _wave(p, L / 2, 0, 1, L * 0.9, L * 0.05, a.phase * 9)
        p.restore()


def _ciliate_path(spec, L, W):
    path = QPainterPath()
    if spec.shape == "pear":                                                # Tetrahymena: pear-shaped
        path.moveTo(L / 2, 0)
        path.cubicTo(L * 0.45, -W * 0.45, L * 0.05, -W * 0.55, -L * 0.3, -W * 0.48)
        path.cubicTo(-L * 0.55, -W * 0.38, -L * 0.55, W * 0.38, -L * 0.3, W * 0.48)
        path.cubicTo(L * 0.05, W * 0.55, L * 0.45, W * 0.45, L / 2, 0)
    else:                                                                   # Paramecium: slipper
        path.moveTo(L / 2, 0)
        path.cubicTo(L * 0.48, -W * 0.5, -L * 0.25, -W * 0.62, -L / 2, -W * 0.12)
        path.cubicTo(-L * 0.55, W * 0.3, -L * 0.2, W * 0.5, L * 0.05, W * 0.3)
        path.cubicTo(L * 0.2, W * 0.42, L * 0.48, W * 0.45, L / 2, 0)
    return path


def _ciliate(p, spec, a, L, W, q, look, col, alpha, lw):
    if q > 0:                                                               # transverse fission: front & back halves
        Lt = L * (1 + 0.5 * q)
        for side in (-1, 1):
            p.save()
            p.translate(side * Lt / 4 * (0.6 + 0.4 * q), 0)
            body = _ciliate_path(spec, L * (0.55 + 0.45 * (1 - q * 0.4)), W * (1 - 0.12 * q))
            _fill(p, body, look, col, alpha, lw)
            p.restore()
        return
    body = _ciliate_path(spec, L, W)
    _fill(p, body, look, col, alpha, lw)
    if L < 10:
        return
    # cilia: a fine shimmering fringe (individual cilia are ≈0.25 µm wide)
    pen = QPen(look.detail(col, 0.45 * alpha).darker(120), max(0.4, L * 0.004))
    p.setPen(pen)
    n = 46 if L > 60 else 26
    for j in range(n):
        t = j / n
        pt = body.pointAtPercent(t)
        ang = body.angleAtPercent(t)
        beat = 25 * math.sin(a.phase * 14 + j * 0.7)                         # metachronal wave
        rad = math.radians(-(ang + 90 + beat))
        ln = L * 0.035
        p.drawLine(pt, QPointF(pt.x() + math.cos(rad) * ln, pt.y() + math.sin(rad) * ln))
    if look.mode == "microscope":
        return
    det = look.detail(col, 0.55 * alpha).darker(160)
    p.setPen(QPen(det, max(0.6, L * 0.01)))
    p.setBrush(Qt.NoBrush)
    oral = QPainterPath()                                                   # oral groove
    oral.moveTo(L * 0.42, -W * 0.05)
    oral.cubicTo(L * 0.25, W * 0.2, L * 0.05, W * 0.25, -L * 0.02, W * 0.12)
    p.drawPath(oral)
    p.setPen(Qt.NoPen)
    p.setBrush(look.detail(col, 0.35 * alpha).darker(150))                  # macronucleus
    p.drawEllipse(QPointF(-L * 0.05, -W * 0.05), L * 0.12, W * 0.18)
    if "contractile_vacuole" in spec.features:                              # pulsing contractile vacuoles
        pulse = 0.5 + 0.5 * math.sin(a.phase * 1.6 + a.variant * 6)
        p.setBrush(QColor(240, 248, 255, int(150 * alpha)))
        for x in ((-L * 0.3, L * 0.28) if spec.shape == "slipper" else (-L * 0.32,)):
            p.drawEllipse(QPointF(x, -W * 0.18), W * (0.05 + 0.07 * pulse), W * (0.05 + 0.07 * pulse))
    if "food_vacuoles" in spec.features:
        p.setBrush(QColor(110, 150, 70, int(110 * alpha)))
        for j in range(5):
            p.drawEllipse(QPointF(-L * 0.2 + j * L * 0.08, math.sin(j * 1.7 + a.variant * 5) * W * 0.15),
                          W * 0.06, W * 0.06)


def _amoeba(p, a, L, W, q, look, col, alpha, lw):
    R = L / 2
    amp = 0.32 * (1 - q)                                                     # rounds up before dividing
    seeds = [a.variant * 13.1 + j * 1.7 for j in range(4)]
    path = QPainterPath()
    if q > 0.3:
        R2 = R * 0.62
        sep = R * 0.62 * (q - 0.3) / 0.7
        for side in (-1, 1):
            sub = QPainterPath()
            sub.addEllipse(QPointF(side * sep, 0), R2, R2 * 0.85)
            path = path.united(sub) if not path.isEmpty() else sub
    else:
        n = 48
        for j in range(n + 1):
            th = j / n * 2 * math.pi
            rr = R * (0.7 + amp * sum(max(0.0, math.sin(th * (2 + i) + s + a.phase * 0.25 * (i + 1))) ** 3
                                      for i, s in enumerate(seeds)) / 1.4)
            pt = QPointF(math.cos(th) * rr, math.sin(th) * rr * 0.8)
            if j == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        path.closeSubpath()
    _fill(p, path, look, col, alpha * 0.85, lw)
    if look.mode == "microscope" or R < 8:
        return
    p.setPen(Qt.NoPen)
    p.setBrush(look.detail(col, 0.25 * alpha).darker(130))                   # granular endoplasm
    for j in range(22):
        ang = j * 2.4 + a.variant * 7
        rr = R * 0.45 * ((j * 37) % 11) / 11
        p.drawEllipse(QPointF(math.cos(ang) * rr, math.sin(ang) * rr * 0.8), R * 0.025, R * 0.025)
    p.setBrush(look.detail(col, 0.45 * alpha).darker(160))                   # nucleus
    p.drawEllipse(QPointF(R * 0.08, -R * 0.05), R * 0.11, R * 0.09)
    pulse = 0.5 + 0.5 * math.sin(a.phase * 0.9)
    p.setBrush(QColor(240, 248, 255, int(140 * alpha)))                      # contractile vacuole
    p.drawEllipse(QPointF(-R * 0.25, R * 0.2), R * 0.06 * (0.5 + pulse), R * 0.06 * (0.5 + pulse))


def _vorticella(p, a, L, W, q, look, col, alpha, lw):
    p.rotate(-math.degrees(a.heading) + 25 * math.sin(a.variant * 6))        # stalk rises from its anchor
    stalk_len = L * 1.8 * (1 - 0.7 * a.contract)
    det = look.detail(col, 0.7 * alpha).darker(150)
    p.setPen(QPen(det, max(0.7, L * 0.025)))
    p.setBrush(Qt.NoBrush)
    stalk = QPainterPath(QPointF(0, 0))
    coils = 7 + 10 * a.contract
    for j in range(1, 25):
        t = j / 24
        stalk.lineTo(math.sin(t * coils * math.pi) * L * 0.06 * (0.3 + a.contract), -t * stalk_len)
    p.drawPath(stalk)
    p.translate(0, -stalk_len)
    for side in ((-1, 1) if q > 0 else (0,)):
        p.save()
        p.translate(side * W * 0.5 * q, 0)
        w = W * (1 - 0.4 * q) if q > 0 else W
        shrink = 1 - 0.3 * a.contract                                       # bell closes when the stalk contracts
        bell = QPainterPath()
        bell.moveTo(0, 0)
        bell.cubicTo(-w * 0.5, -L * 0.1, -w * 0.62 * shrink, -L * 0.7, -w * 0.5 * shrink, -L * 0.85)
        bell.lineTo(w * 0.5 * shrink, -L * 0.85)
        bell.cubicTo(w * 0.62 * shrink, -L * 0.7, w * 0.5, -L * 0.1, 0, 0)
        _fill(p, bell, look, col, alpha, lw)
        if look.mode != "microscope" and L > 10 and a.contract < 0.3:
            p.setPen(QPen(det, max(0.4, L * 0.006)))
            for j in range(12):                                              # peristomial cilia
                x = -w * 0.48 + j * w * 0.96 / 11
                beat = 0.3 * math.sin(a.phase * 12 + j * 0.8)
                p.drawLine(QPointF(x, -L * 0.85), QPointF(x + math.sin(beat) * L * 0.06, -L * 0.97))
            p.setPen(Qt.NoPen)
            p.setBrush(look.detail(col, 0.4 * alpha).darker(150))
            mac = QPainterPath()                                             # C-shaped macronucleus
            mac.addEllipse(QPointF(0, -L * 0.45), w * 0.12, L * 0.22)
            p.drawPath(mac)
        p.restore()


# ---------------------------------------------------------------- rotifers
def _brachionus(p, a, L, W, q, look, col, alpha, lw, eggs):
    p.rotate(90)                                                             # body axis along the heading
    w = W
    body = QPainterPath()
    body.moveTo(-w / 2, -L * 0.30)
    body.cubicTo(-w * 0.62, L * 0.05, -w * 0.40, L * 0.32, 0, L * 0.36)
    body.cubicTo(w * 0.40, L * 0.32, w * 0.62, L * 0.05, w / 2, -L * 0.30)
    body.closeSubpath()
    p.save()                                                                 # anterior (spines) leads
    _fill(p, body, look, col, alpha, lw)
    det = look.detail(col, 0.75 * alpha).darker(150)
    p.setBrush(look.body(col, alpha)[0])
    p.setPen(QPen(det, max(0.5, L * 0.008)))
    for i in range(6):                                                       # anterior spines of the lorica
        x = -w / 2 + w * (i + 0.5) / 6
        hgt = L * (0.10 if i in (0, 5) else 0.06)
        sp = QPainterPath()
        sp.moveTo(x - w * 0.05, -L * 0.30)
        sp.lineTo(x, -L * 0.30 - hgt)
        sp.lineTo(x + w * 0.05, -L * 0.30)
        p.drawPath(sp)
    if L > 12:
        p.setPen(QPen(det, max(0.4, L * 0.006)))
        for side in (-1, 1):                                                 # ciliated corona, two lobes
            cx = side * w * 0.22
            for j in range(9):
                ang = math.pi * (j / 8) + math.pi
                beat = 0.3 * math.sin(a.phase * 14 + j)
                x0, y0 = cx + math.cos(ang) * w * 0.2, -L * 0.33 + math.sin(ang) * L * 0.06
                p.drawLine(QPointF(x0, y0), QPointF(x0 + math.cos(ang + beat) * L * 0.05,
                                                    y0 + math.sin(ang + beat) * L * 0.05))
        if look.mode != "microscope":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(110, 150, 70, int(120 * alpha)))               # gut with algae
            p.drawEllipse(QPointF(0, -L * 0.02), w * 0.18, L * 0.14)
            p.setBrush(QColor(90, 70, 50, int(150 * alpha)))                 # mastax (jaws)
            p.drawEllipse(QPointF(0, -L * 0.2), w * 0.08, L * 0.05)
    p.setPen(QPen(look.detail(col, 0.8 * alpha), max(0.8, L * 0.04), Qt.SolidLine, Qt.RoundCap))
    sway = math.sin(a.phase * 2) * L * 0.05                                  # foot with two toes
    p.drawLine(QPointF(0, L * 0.36), QPointF(sway, L * 0.55))
    p.drawLine(QPointF(sway, L * 0.55), QPointF(sway - L * 0.03, L * 0.62))
    p.drawLine(QPointF(sway, L * 0.55), QPointF(sway + L * 0.03, L * 0.62))
    n_eggs = max(eggs, 1 if q > 0 else 0)
    for e in range(n_eggs):                                                  # eggs at the posterior
        s = q if (q > 0 and e == n_eggs - 1) else 1.0
        p.setPen(QPen(det, max(0.5, L * 0.008)))
        p.setBrush(QColor(232, 222, 178, int(220 * alpha)) if look.mode != "microscope" else look.body(col, alpha)[0])
        p.drawEllipse(QPointF((e - (n_eggs - 1) / 2) * w * 0.38, L * 0.42), w * 0.17 * (0.4 + 0.6 * s),
                      L * 0.10 * (0.4 + 0.6 * s))
    p.restore()


def _bdelloid(p, a, L, W, q, look, col, alpha, lw):
    creeping = a.tumbling
    stretch = 1.0 + (0.25 * math.sin(a.phase * 2.2) if creeping else 0.0)
    Ls = L * stretch
    segs = 6
    path = QPainterPath()
    for j in range(segs):
        t = j / (segs - 1)
        x = Ls / 2 - t * Ls
        r = W / 2 * (0.65 + 0.35 * math.sin(math.pi * min(1.0, t * 1.2 + 0.1)))
        sub = QPainterPath()
        sub.addEllipse(QPointF(x, 0), Ls / (segs * 1.4), r)
        path = path.united(sub) if j else sub
    _fill(p, path, look, col, alpha, lw)
    det = look.detail(col, 0.7 * alpha).darker(150)
    if not creeping and L > 12:                                              # two ciliated wheels when swimming
        p.setPen(QPen(det, max(0.4, L * 0.005)))
        for side in (-1, 1):
            c = QPointF(Ls / 2 + W * 0.15, side * W * 0.25)
            for j in range(10):
                ang = j / 10 * 2 * math.pi + a.phase * 10 * side
                p.drawLine(c, QPointF(c.x() + math.cos(ang) * W * 0.22, c.y() + math.sin(ang) * W * 0.22))
    if look.mode != "microscope" and L > 12:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(200, 70, 60, int(120 * alpha)))                    # reddish gut
        p.drawEllipse(QPointF(0, 0), Ls * 0.12, W * 0.18)
    if q > 0:
        p.setPen(QPen(det, 0.6))
        p.setBrush(QColor(232, 222, 178, int(200 * alpha)))
        p.drawEllipse(QPointF(-Ls * 0.15, 0), W * 0.2 * q, W * 0.13 * q)


# ---------------------------------------------------------------- fungi
def _hypha(p, spec, a, L, W, q, look, col, alpha, lw):
    length = L * max(a.grow, 0.02) / max(0.55 + 0.45 * a.grow, 1e-6)        # extension = maturity (not scale)
    W = max(W / max(0.55 + 0.45 * a.grow, 1e-6), 1.0)
    n = 10
    pts = []
    bend = (a.variant - 0.5) * 0.5
    for j in range(n + 1):
        t = j / n
        pts.append(QPointF(t * length, math.sin(t * 3.0 + a.variant * 9) * length * 0.04 + bend * (t * length) * t * 0.3))
    path = QPainterPath(pts[0])
    for pt in pts[1:]:
        path.lineTo(pt)
    fill, outline = look.body(col, alpha)
    if look.mode == "microscope" and look.stain != "gram":
        p.setPen(QPen(outline, W + 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
    p.setPen(QPen(fill.darker(130), W + max(0.8, W * 0.12), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)
    p.setPen(QPen(fill, W, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)
    if "septa" in spec.features and length > W * 6:                           # cross walls
        p.setPen(QPen(fill.darker(180), max(0.5, W * 0.1)))
        for j in range(2, n, 3):
            pt = pts[j]
            p.drawLine(QPointF(pt.x(), pt.y() - W * 0.45), QPointF(pt.x(), pt.y() + W * 0.45))
    tip = pts[-1]
    if q > 0:                                                                # a new branch starts behind the tip
        p.setPen(QPen(fill, W * 0.9, Qt.SolidLine, Qt.RoundCap))
        b = pts[-3]
        side = 1 if a.variant > 0.5 else -1
        p.drawLine(b, QPointF(b.x() + math.cos(side * 0.7) * L * 0.12 * q, b.y() + math.sin(side * 0.7) * L * 0.12 * q))
    if a.grow >= 1.0 and a.variant > 0.55 and look.mode != "microscope":       # reproductive structures on mature hyphae
        mid = pts[n // 2]
        det = look.detail(col, 0.8 * alpha)
        p.setPen(QPen(fill, W * 0.7, Qt.SolidLine, Qt.RoundCap))
        top = QPointF(mid.x(), mid.y() - L * 0.28)
        p.drawLine(mid, top)
        p.setPen(Qt.NoPen)
        if "conidiophore" in spec.features:                                  # Aspergillus: vesicle + radiating conidia
            p.setBrush(det.darker(110))
            p.drawEllipse(top, W * 1.1, W * 1.1)
            p.setBrush(QColor(170, 190, 120, int(220 * alpha)))
            for j in range(14):
                ang = math.pi + j / 13 * math.pi
                p.drawEllipse(QPointF(top.x() + math.cos(ang) * W * 1.8, top.y() + math.sin(ang) * W * 1.8),
                              W * 0.35, W * 0.35)
        elif "penicillus" in spec.features:                                  # Penicillium: brush of chains
            p.setPen(QPen(QColor(110, 160, 130, int(220 * alpha)), max(0.6, W * 0.3)))
            for j in (-1.5, -0.5, 0.5, 1.5):
                end = QPointF(top.x() + j * W * 0.9, top.y() - W * 2.5)
                p.drawLine(top, end)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(90, 150, 120, int(220 * alpha)))
                for m in range(3):
                    p.drawEllipse(QPointF(end.x(), end.y() - m * W * 0.7), W * 0.3, W * 0.3)
                p.setPen(QPen(QColor(110, 160, 130, int(220 * alpha)), max(0.6, W * 0.3)))
        elif "sporangium" in spec.features:                                  # Rhizopus: dark round sporangium
            p.setBrush(QColor(60, 60, 55, int(220 * alpha)))
            p.drawEllipse(top, W * 1.6, W * 1.6)
    p.setPen(Qt.NoPen)
    p.setBrush(fill.lighter(115))
    p.drawEllipse(tip, W * 0.5, W * 0.5)
