"""Yoghurt microscope: a drop of the milk under oil immersion, plus the jar (gel indicator and pH meter)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainterPath, QPen

from ..analysis.explain_yogurt import END_PH, GEL_ONSET_PH
from ..i18n import L
from ..viz.yogurt_scene import YogurtScene
from .specimen_view import SpecimenView


class YogurtWidget(SpecimenView):
    side_width = 0.24
    stain = "gram"                                   # microscope mode = Gram-stained smear
    background = ((0.97, 0.96, 0.94), (0.82, 0.81, 0.78))   # milk: bright, slightly turbid

    def __init__(self, scene: YogurtScene, parent=None):
        super().__init__(scene, parent)
        self.time_unit = "h"

    def panel_title(self, name):
        if self.scene.mode == "microscope":
            return L("Gram stain, 100× oil — both species are Gram-positive (purple)",
                     "صبغة جرام، 100× زيت – النوعان موجبا الجرام (بنفسجي)")
        return L("Wet mount of the milk, 100× oil immersion", "قطرة من الحليب، 100× زيت")

    def paint_side(self, p, area):
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
