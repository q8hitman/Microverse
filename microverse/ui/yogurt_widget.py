"""Paints the yoghurt scene: stained smear + jar with a conceptual gel indicator and pH meter."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..analysis.explain_yogurt import END_PH, GEL_ONSET_PH
from ..viz.yogurt_scene import SMEAR_FIELD, YogurtScene


class YogurtWidget(QWidget):
    def __init__(self, scene: YogurtScene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.expected = (0.0, 0.0)
        self.time_d = 0.0
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d1117"))
        w, h = self.width(), self.height()
        gap = 10
        lw = (w - 3 * gap) * 0.66
        r = QRectF(gap, gap + 18, lw, h - 2 * gap - 36)
        aspect = SMEAR_FIELD.width_um / SMEAR_FIELD.height_um
        if r.width() / r.height() > aspect:
            ww = r.height() * aspect
            r = QRectF(r.x() + (r.width() - ww) / 2, r.y(), ww, r.height())
        else:
            hh = r.width() / aspect
            r = QRectF(r.x(), r.y() + (r.height() - hh) / 2, r.width(), hh)
        self._smear(p, r)
        self._jar(p, QRectF(2 * gap + lw, gap + 18, w - 3 * gap - lw, h - 2 * gap - 36))
        p.setPen(QColor("#8b949e"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(gap, h - 20, w - 2 * gap, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   f"t = {self.time_d:.2f} h  ·  Rendered FROM the simulation state (counts = density × smear volume, "
                   "Poisson). Positions are visual only; the gel indicator is conceptual (derived from pH).")
        p.end()

    def _smear(self, p, rect):
        s = self.scene
        g = QRadialGradient(rect.center(), rect.width() * 0.7)
        g.setColorAt(0, QColor(250, 236, 238))
        g.setColorAt(1, QColor(205, 180, 188))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(rect, 6, 6)
        p.setPen(QColor("#c9d1d9"))
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(QRectF(rect.x(), rect.y() - 18, rect.width(), 16), Qt.AlignLeft | Qt.AlignVCenter,
                   "Gram stain, 100× oil — both species are Gram-positive (purple)")
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, 6, 6)
        p.setClipPath(clip)
        k = rect.width() / SMEAR_FIELD.width_um
        # L. bulgaricus rods
        pen = QPen(QColor(92, 45, 140, 235), max(1.5, 0.65 * k), Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        for x, y, ang, L in s.lb_rods:
            dx, dy = math.cos(ang) * L * k / 2, math.sin(ang) * L * k / 2
            cx, cy = rect.x() + x * k, rect.y() + y * k
            p.drawLine(QPointF(cx - dx, cy - dy), QPointF(cx + dx, cy + dy))
        # S. thermophilus chains
        p.setPen(QPen(QColor(60, 25, 100, 200), 0.6))
        p.setBrush(QColor(118, 62, 170, 235))
        d = 0.8 * k
        for x, y, ang, n, curv in s.st_chains:
            cx, cy = rect.x() + x * k, rect.y() + y * k
            a = ang
            for i in range(int(n)):
                p.drawEllipse(QPointF(cx, cy), d * 0.55, d * 0.48)
                cx += math.cos(a) * d * 1.02
                cy += math.sin(a) * d * 1.02
                a += curv
        p.restore()
        e_st, e_lb = self.expected
        label = QRectF(rect.x() + 6, rect.y() + 6, 360, 34)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 130))
        p.drawRoundedRect(label, 4, 4)
        p.setPen(QColor("#f0f3f6"))
        p.setFont(QFont("Segoe UI", 8))
        cap = "  (drawing capped)" if s.capped else ""
        p.drawText(label.adjusted(6, 2, -4, -2), Qt.AlignLeft | Qt.AlignVCenter,
                   f"● S. thermophilus (cocci in chains): {s.st_cells()} drawn · {e_st:.1f} expected\n"
                   f"▬ L. bulgaricus (rods): {len(s.lb_rods)} drawn · {e_lb:.1f} expected{cap}")
        # scale bar 5 µm
        px = 5 * k
        p.setPen(QPen(QColor(30, 30, 30), 3))
        p.drawLine(QPointF(rect.right() - px - 12, rect.bottom() - 12), QPointF(rect.right() - 12, rect.bottom() - 12))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(rect.right() - px - 32, rect.bottom() - 30, px + 40, 14), Qt.AlignCenter, "5 µm")

    def _jar(self, p, area):
        ph = self.scene.ph
        gel = max(0.0, min(1.0, (GEL_ONSET_PH + 0.1 - ph) / (GEL_ONSET_PH + 0.1 - END_PH)))
        p.setPen(QColor("#c9d1d9"))
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(QRectF(area.x(), area.y() - 18, area.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, "The milk (macro view)")
        jw = min(area.width() * 0.62, area.height() * 0.55)
        jar = QRectF(area.x() + (area.width() - jw) / 2, area.y() + 20, jw, jw * 1.15)
        # glass
        p.setPen(QPen(QColor(200, 210, 220, 160), 2))
        p.setBrush(QColor(255, 255, 255, 18))
        p.drawRoundedRect(jar, 10, 10)
        fill = jar.adjusted(5, jar.height() * 0.18, -5, -5)
        grad = QLinearGradient(fill.topLeft(), fill.bottomLeft())
        top = QColor.fromRgbF(0.97, 0.96, 0.92 - 0.05 * gel)
        grad.setColorAt(0, top)
        grad.setColorAt(1, QColor.fromRgbF(0.90 - 0.04 * gel, 0.89 - 0.04 * gel, 0.84 - 0.06 * gel))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        surf = QPainterPath()
        amp = 4 * (1 - gel)                                   # liquid surface ripples; a set gel is flat
        surf.moveTo(fill.left(), fill.top())
        for i in range(1, 21):
            x = fill.left() + fill.width() * i / 20
            surf.lineTo(x, fill.top() + amp * math.sin(i * 0.9 + self.time_d * 8))
        surf.lineTo(fill.right(), fill.bottom())
        surf.lineTo(fill.left(), fill.bottom())
        surf.closeSubpath()
        p.drawPath(surf)
        if ph < 4.2:                                           # whey on top when over-acidified
            p.setBrush(QColor(225, 228, 170, int(120 * min(1, (4.2 - ph) / 0.3))))
            p.drawRect(QRectF(fill.left(), fill.top() - 2, fill.width(), 6))
        state = "liquid milk" if gel <= 0 else ("gel forming" if gel < 1 else "set yoghurt gel")
        if ph < 4.2:
            state += " · post-acidified"
        p.setPen(QColor("#e6edf3"))
        p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        p.drawText(QRectF(area.x(), jar.bottom() + 6, area.width(), 18), Qt.AlignCenter, state)
        # pH meter bar
        bar = QRectF(area.x() + 12, jar.bottom() + 34, area.width() - 24, 14)
        g = QLinearGradient(bar.topLeft(), bar.topRight())
        for pos, col in [(0, "#d73a49"), (0.35, "#f0883e"), (0.6, "#e3b341"), (1, "#3fb950")]:
            g.setColorAt(pos, QColor(col))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(bar, 4, 4)
        lo, hi = 3.5, 7.0
        x = bar.left() + (min(max(ph, lo), hi) - lo) / (hi - lo) * bar.width()
        p.setBrush(QColor("#ffffff"))
        p.drawPolygon([QPointF(x, bar.top() - 2), QPointF(x - 6, bar.top() - 10), QPointF(x + 6, bar.top() - 10)])
        for mark in (END_PH, GEL_ONSET_PH):
            mx = bar.left() + (mark - lo) / (hi - lo) * bar.width()
            p.setPen(QPen(QColor(255, 255, 255, 160), 1, Qt.DashLine))
            p.drawLine(QPointF(mx, bar.top()), QPointF(mx, bar.bottom() + 4))
        p.setPen(QColor("#e6edf3"))
        p.setFont(QFont("Segoe UI", 16, QFont.Bold))
        p.drawText(QRectF(area.x(), bar.bottom() + 6, area.width(), 26), Qt.AlignCenter, f"pH {ph:.2f}")
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QColor("#8b949e"))
        p.drawText(QRectF(area.x(), bar.bottom() + 32, area.width(), 14), Qt.AlignCenter,
                   f"dashed: gel onset ≈ {GEL_ONSET_PH} · end point {END_PH}")
