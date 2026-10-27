"""Community microscope: two fields of view (by organism size) and the vessel beside them."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPen

from ..i18n import L
from ..viz.community_scene import CommunityScene
from .specimen_view import SpecimenView


class CommunityWidget(SpecimenView):
    side_width = 0.13

    def __init__(self, scene: CommunityScene, parent=None):
        super().__init__(scene, parent)
        self.time_unit = "h"

    def panel_title(self, name):
        return (L("100× oil — small cells (≤ 15 µm)", "100× زيت – الخلايا الصغيرة (≤ 15 ميكرومتر)")
                if name == "small" else
                L("10× — large organisms (> 15 µm)", "10× – الكائنات الكبيرة (> 15 ميكرومتر)"))

    def panel_background(self, name):
        inner, outer = super().panel_background(name)
        t = self.scene.turbidity * 0.5 if self.scene.mode != "microscope" else 0.0
        return inner.darker(int(100 + 12 * t)), outer.darker(int(100 + 18 * t))

    def paint_side(self, p, area):
        s = self.scene
        p.setPen(QColor("#c9d1d9"))
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(QRectF(area.x(), area.y() - 16, area.width(), 14), Qt.AlignLeft | Qt.AlignVCenter,
                   L("The vessel", "الوعاء"))
        jw = min(area.width() * 0.8, area.height() * 0.42)
        jar = QRectF(area.x() + (area.width() - jw) / 2, area.y() + 8, jw, jw * 1.1)
        p.setPen(QPen(QColor(200, 210, 220, 150), 2))
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(jar, 8, 8)
        fill = jar.adjusted(4, jar.height() * 0.2, -4, -4)
        tint = s.turbidity
        grad = QLinearGradient(fill.topLeft(), fill.bottomLeft())
        grad.setColorAt(0, QColor.fromRgbF(0.85 - 0.25 * tint, 0.86 - 0.18 * tint, 0.80 - 0.3 * tint, 0.95))
        grad.setColorAt(1, QColor.fromRgbF(0.70 - 0.3 * tint, 0.72 - 0.25 * tint, 0.65 - 0.35 * tint, 0.95))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(fill)
        if s.o2 > 1.0:                                       # oxygen bubbles
            p.setBrush(QColor(255, 255, 255, 90))
            n = int(min(s.o2, 20))
            for j in range(n):
                bx = fill.left() + (j * 37 % max(fill.width() - 8, 1)) + 4
                by = fill.bottom() - ((j * 53 + self.time_d * 40) % fill.height())
                p.drawEllipse(QPointF(bx, by), 2.0, 2.0)
        y = jar.bottom() + 10
        p.setFont(QFont("Segoe UI", 9))
        for label, value, colour in [
            (L("pH", "الحموضة"), f"{s.ph:.2f}", "#f0883e" if s.ph < 5 else "#3fb950"),
            (L("O₂ mg/L", "أكسجين ملغم/ل"), f"{s.o2:.1f}", "#58a6ff" if s.o2 > 1 else "#8b949e"),
            (L("turbidity", "العكارة"), f"{tint * 100:.0f}%", "#c9d1d9"),
        ]:
            p.setPen(QColor("#8b949e"))
            p.drawText(QRectF(area.x(), y, area.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, label)
            p.setPen(QColor(colour))
            p.drawText(QRectF(area.x(), y, area.width(), 16), Qt.AlignRight | Qt.AlignVCenter, value)
            y += 18
