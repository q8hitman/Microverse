"""Chemostat microscope: rotifers (4×) and Chlorella (40×), plus the chemostat vessel."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainterPath, QPen

from ..i18n import L
from ..viz.scene import MicroscopeScene
from .specimen_view import SpecimenView


class MicroscopeWidget(SpecimenView):
    side_width = 0.14

    def __init__(self, scene: MicroscopeScene, parent=None):
        super().__init__(scene, parent)
        self.time_unit = "d"

    def panel_title(self, name):
        if name == "rotifers":
            return L("Brachionus — 4× objective, sieved sample", "براكيونس – عدسة 4×، عينة مُصفّاة")
        return L("Chlorella — 40× objective, counting chamber", "كلوريلا – عدسة 40×، شريحة عدّ")

    def panel_background(self, name):
        inner, outer = super().panel_background(name)
        if name == "rotifers" and self.scene.mode != "microscope":       # culture colour follows algal density
            t = self.scene.tint
            inner = QColor.fromRgbF(0.94 - 0.30 * t, 0.95 - 0.10 * t, 0.88 - 0.36 * t)
            outer = QColor.fromRgbF(0.62 - 0.22 * t, 0.64 - 0.10 * t, 0.56 - 0.25 * t)
        return inner, outer

    def agent_extra(self, track_index, agent):
        return {"eggs": self.scene.eggs_of(agent)} if track_index == 1 else {}

    def paint_side(self, p, area):
        s = self.scene
        p.setPen(QColor("#c9d1d9"))
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(QRectF(area.x(), area.y() - 16, area.width(), 14), Qt.AlignLeft | Qt.AlignVCenter,
                   L("The chemostat", "الكيموستات"))
        jw = min(area.width() * 0.7, area.height() * 0.4)
        jar = QRectF(area.x() + (area.width() - jw) / 2, area.y() + 24, jw, jw * 1.2)
        p.setPen(QPen(QColor(200, 210, 220, 150), 2))
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(jar, 8, 8)
        fill = jar.adjusted(4, jar.height() * 0.15, -4, -4)
        t = s.tint
        g = QLinearGradient(fill.topLeft(), fill.bottomLeft())
        g.setColorAt(0, QColor.fromRgbF(0.80 - 0.45 * t, 0.86 - 0.2 * t, 0.78 - 0.5 * t, 0.95))
        g.setColorAt(1, QColor.fromRgbF(0.66 - 0.4 * t, 0.74 - 0.2 * t, 0.62 - 0.45 * t, 0.95))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRect(fill)
        p.setPen(QPen(QColor("#58a6ff"), 2))                         # inflow and outflow (dilution)
        p.drawLine(QPointF(jar.left() - 14, jar.top() + 6), QPointF(jar.left() + 6, jar.top() + 6))
        p.drawLine(QPointF(jar.right() - 6, fill.top() + 6), QPointF(jar.right() + 14, fill.top() + 6))
        y = jar.bottom() + 12
        p.setFont(QFont("Segoe UI", 9))
        y_state = s.y if s.y is not None else [0, 0, 0, 0]
        for label, value in [
            (L("N µmol/L", "النيتروجين"), f"{y_state[0]:.1f}"),
            (L("Chlorella", "كلوريلا"), f"{y_state[1]:.1f}"),
            (L("rotifers", "الدوّارات"), f"{y_state[3]:.2f}"),
            (L("with eggs", "تحمل بيضاً"), f"{s.egg_fraction * 100:.0f}%"),
        ]:
            p.setPen(QColor("#8b949e"))
            p.drawText(QRectF(area.x(), y, area.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, label)
            p.setPen(QColor("#e6edf3"))
            p.drawText(QRectF(area.x(), y, area.width(), 16), Qt.AlignRight | Qt.AlignVCenter, value)
            y += 18
        p.setPen(QColor("#6e7681"))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(QRectF(area.x(), y + 4, area.width(), 40), Qt.TextWordWrap,
                   L("biomass in µmol N/L; culture colour ∝ algal density",
                     "الكتلة بالميكرومول نيتروجين/لتر؛ لون المزرعة يتبع كثافة الطحالب"))

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

