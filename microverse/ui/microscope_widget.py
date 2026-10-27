"""Paints the MicroscopeScene. Drawing only — all numbers come from the scene/state."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..viz.scene import ALGAE_FIELD, ROTIFER_FIELD, MicroscopeScene


class MicroscopeWidget(QWidget):
    def __init__(self, scene: MicroscopeScene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.expected = (0.0, 0.0)
        self.time_d = 0.0
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#101418"))
        w, h = self.width(), self.height()
        gap = 10
        lw = (w - 3 * gap) * 0.58
        rect_r = QRectF(gap, gap + 18, lw, h - 2 * gap - 36)
        rect_a = QRectF(2 * gap + lw, gap + 18, w - 3 * gap - lw, h - 2 * gap - 36)
        self._rotifer_field(p, self._fit(rect_r, ROTIFER_FIELD))
        self._algae_field(p, self._fit(rect_a, ALGAE_FIELD))
        p.setPen(QColor("#8a96a3"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(gap, h - 20, w - 2 * gap, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   f"t = {self.time_d:.1f} d  ·  Rendered FROM the simulation state: counts are Poisson samples of "
                   "density × sampled volume; positions, orientation and swimming are visual only.")
        p.end()

    @staticmethod
    def _fit(r: QRectF, f) -> QRectF:
        aspect = f.width_um / f.height_um
        if r.width() / r.height() > aspect:
            ww = r.height() * aspect
            return QRectF(r.x() + (r.width() - ww) / 2, r.y(), ww, r.height())
        hh = r.width() / aspect
        return QRectF(r.x(), r.y() + (r.height() - hh) / 2, r.width(), hh)

    def _frame(self, p, rect, field, bg_inner, bg_outer, title, count, expected):
        g = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.65)
        g.setColorAt(0, bg_inner)
        g.setColorAt(1, bg_outer)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(rect, 6, 6)
        p.setPen(QColor("#c9d3dd"))
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(QRectF(rect.x(), rect.y() - 18, rect.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.setFont(QFont("Segoe UI", 8))
        label = QRectF(rect.right() - 170, rect.y() + 6, 164, 18)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawRoundedRect(label, 4, 4)
        p.setPen(QColor("#f0f3f6"))
        p.drawText(label, Qt.AlignCenter, f"drawn {count} · expected {expected:.1f}")

    def _scale_bar(self, p, rect, field, um, label):
        px = um / field.width_um * rect.width()
        x0, y0 = rect.right() - px - 12, rect.bottom() - 12
        p.setPen(QPen(QColor(20, 20, 20, 220), 3))
        p.drawLine(QPointF(x0, y0), QPointF(x0 + px, y0))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(x0 - 20, y0 - 18, px + 40, 14), Qt.AlignCenter, label)

    # ---- rotifers ---------------------------------------------------------
    def _rotifer_field(self, p, rect):
        s = self.scene
        t = s.tint
        inner = QColor.fromRgbF(0.93 - 0.35 * t, 0.94 - 0.12 * t, 0.86 - 0.40 * t)
        outer = QColor.fromRgbF(0.55 - 0.25 * t, 0.57 - 0.12 * t, 0.50 - 0.28 * t)
        self._frame(p, rect, ROTIFER_FIELD, inner, outer, ROTIFER_FIELD.title, len(s.rotifers), self.expected[1])
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, 6, 6)
        p.setClipPath(clip)
        k = rect.width() / ROTIFER_FIELD.width_um
        for x, y, heading, eggs, length, phase in s.rotifers:
            self._rotifer(p, QPointF(rect.x() + x * k, rect.y() + y * k), heading, int(eggs), length * k, phase)
        p.restore()
        p.setPen(QColor(30, 50, 30))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignLeft | Qt.AlignBottom,
                   f"background tint ∝ algal density C (culture colour)")
        self._scale_bar(p, rect, ROTIFER_FIELD, 1000, "1 mm")

    @staticmethod
    def _rotifer(p, c, heading, eggs, L, phase):
        p.save()
        p.translate(c)
        p.rotate(math.degrees(heading) + 90)       # body axis along heading, head first
        w = L * 0.55
        body = QPainterPath()
        body.moveTo(-w / 2, -L * 0.30)
        body.cubicTo(-w * 0.62, L * 0.05, -w * 0.40, L * 0.32, 0, L * 0.36)
        body.cubicTo(w * 0.40, L * 0.32, w * 0.62, L * 0.05, w / 2, -L * 0.30)
        body.closeSubpath()
        grad = QLinearGradient(-w / 2, 0, w / 2, 0)
        grad.setColorAt(0, QColor(196, 186, 160, 200))
        grad.setColorAt(0.5, QColor(236, 230, 212, 150))
        grad.setColorAt(1, QColor(190, 180, 154, 200))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(110, 100, 80, 220), max(0.8, L * 0.015)))
        p.drawPath(body)
        # anterior spines of the lorica
        p.setBrush(QColor(200, 190, 165, 220))
        for i in range(6):
            x = -w / 2 + w * (i + 0.5) / 6
            hgt = L * (0.10 if i in (0, 5) else 0.06)
            sp = QPainterPath()
            sp.moveTo(x - w * 0.05, -L * 0.30)
            sp.lineTo(x, -L * 0.30 - hgt)
            sp.lineTo(x + w * 0.05, -L * 0.30)
            p.drawPath(sp)
        # ciliated corona (two lobes) with beating cilia
        p.setPen(QPen(QColor(90, 80, 60, 170), max(0.6, L * 0.008)))
        for side in (-1, 1):
            cx = side * w * 0.22
            for j in range(9):
                a = math.pi * (j / 8) + math.pi
                beat = 0.25 * math.sin(phase * 12 + j)
                x0, y0 = cx + math.cos(a) * w * 0.2, -L * 0.33 + math.sin(a) * L * 0.06
                p.drawLine(QPointF(x0, y0), QPointF(x0 + math.cos(a + beat) * L * 0.05,
                                                    y0 + math.sin(a + beat) * L * 0.05))
        # gut / mastax hint
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(120, 150, 70, 120))
        p.drawEllipse(QPointF(0, -L * 0.02), w * 0.18, L * 0.14)
        p.setBrush(QColor(90, 70, 50, 140))
        p.drawEllipse(QPointF(0, -L * 0.20), w * 0.08, L * 0.05)
        # foot with toes
        p.setPen(QPen(QColor(150, 138, 110, 200), max(1.0, L * 0.04), Qt.SolidLine, Qt.RoundCap))
        sway = math.sin(phase * 2) * L * 0.05
        p.drawLine(QPointF(0, L * 0.36), QPointF(sway, L * 0.55))
        p.drawLine(QPointF(sway, L * 0.55), QPointF(sway - L * 0.03, L * 0.62))
        p.drawLine(QPointF(sway, L * 0.55), QPointF(sway + L * 0.03, L * 0.62))
        # eggs attached near the posterior (only on egg-bearing females, from R/B)
        p.setPen(QPen(QColor(120, 110, 80, 200), max(0.6, L * 0.01)))
        p.setBrush(QColor(225, 215, 170, 220))
        for e in range(eggs):
            p.drawEllipse(QPointF((e - (eggs - 1) / 2) * w * 0.38, L * 0.42), w * 0.17, L * 0.10)
        p.restore()

    # ---- algae ------------------------------------------------------------
    def _algae_field(self, p, rect):
        s = self.scene
        self._frame(p, rect, ALGAE_FIELD, QColor(246, 244, 236), QColor(178, 176, 166),
                    ALGAE_FIELD.title.split(" — ")[0] + " — 40×", len(s.algae), self.expected[0])
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, 6, 6)
        p.setClipPath(clip)
        k = rect.width() / ALGAE_FIELD.width_um
        n_auto = int(len(s.algae) * s.autospore_fraction)
        for i, (x, y, d, ph) in enumerate(s.algae):
            self._alga(p, QPointF(rect.x() + x * k, rect.y() + y * k), d * k / 2, ph, i < n_auto)
        p.restore()
        self._scale_bar(p, rect, ALGAE_FIELD, 50, "50 µm")

    def _alga(self, p, c, r, phase, autospores):
        r = max(r, 1.5)
        g = QRadialGradient(c + QPointF(-r * 0.3, -r * 0.3), r * 1.2)
        g.setColorAt(0, QColor(150, 205, 120))
        g.setColorAt(0.7, QColor(60, 140, 55))
        g.setColorAt(1, QColor(30, 85, 35))
        p.setPen(QPen(QColor(25, 60, 25, 200), 0.8))
        p.setBrush(QBrush(g))
        p.drawEllipse(c, r, r)
        if r < 3:
            return
        if autospores:
            p.setBrush(QColor(40, 110, 40, 180))
            p.setPen(Qt.NoPen)
            for j in range(4):
                a = phase * 6.28 + j * math.pi / 2
                p.drawEllipse(c + QPointF(math.cos(a) * r * 0.42, math.sin(a) * r * 0.42), r * 0.38, r * 0.38)
            return
        # cup-shaped chloroplast + pyrenoid
        p.setPen(QPen(QColor(25, 90, 30, 200), max(1.0, r * 0.35)))
        start = int((phase * 360) * 16)
        p.drawArc(QRectF(c.x() - r * 0.7, c.y() - r * 0.7, r * 1.4, r * 1.4), start, 220 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(210, 230, 190, 200))
        p.drawEllipse(c + QPointF(r * 0.15, r * 0.1), r * 0.18, r * 0.18)
