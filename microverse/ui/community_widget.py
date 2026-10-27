"""Draws the community scene: two microscope panels (by organism size), a legend and the vessel."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..i18n import L
from ..viz.community_scene import LARGE_FIELD, SMALL_FIELD, CommunityScene


class CommunityWidget(QWidget):
    def __init__(self, scene: CommunityScene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.expected = ()
        self.time_d = 0.0
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d1117"))
        s = self.scene
        w, h = self.width(), self.height()
        gap = 12
        vw = min(170, w * 0.18)
        legend_h = 20 * ((len(s.model.orgs) + 1) // 2) + 8
        area = QRectF(gap, gap + 20, w - 3 * gap - vw, h - 2 * gap - 44 - legend_h)
        panels = s.panels
        pw = (area.width() - gap * (len(panels) - 1)) / max(len(panels), 1)
        aspect = SMALL_FIELD.width_um / SMALL_FIELD.height_um          # both panels share this aspect
        ph_ = min(area.height(), pw / aspect)
        pw_ = ph_ * aspect
        total = pw_ * len(panels) + gap * (len(panels) - 1)
        x0 = area.x() + (area.width() - total) / 2
        for j, panel in enumerate(panels):
            field = SMALL_FIELD if panel == "small" else LARGE_FIELD
            self._panel(p, QRectF(x0 + j * (pw_ + gap), area.y(), pw_, ph_), panel, field)
        self._legend(p, QRectF(gap, area.y() + ph_ + 10, w - 3 * gap - vw, legend_h))
        self._vessel(p, QRectF(w - gap - vw, gap + 18, vw, h - 2 * gap - 36))
        p.setPen(QColor("#8b949e"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(gap, h - 18, w - 2 * gap, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   L(f"t = {self.time_d:.1f} h · Drawn from the simulated biomass, true relative size inside each panel. "
                     "Counts are concentrated per species (× in the legend) — read real numbers from the graph.",
                     f"t = {self.time_d:.1f} ساعة · مرسومة من الكتلة المحسوبة، وبحجمها الحقيقي داخل كل نافذة. "
                     "العدد مركّز لكل نوع (× في الدليل) – الأعداد الحقيقية في الرسم البياني."))
        p.end()

    def _panel(self, p, rect, panel, field):
        s = self.scene
        tint = s.turbidity
        g = QRadialGradient(rect.center(), rect.width() * 0.7)
        g.setColorAt(0, QColor.fromRgbF(0.97 - 0.08 * tint, 0.96 - 0.06 * tint, 0.93 - 0.08 * tint))
        g.setColorAt(1, QColor.fromRgbF(0.74 - 0.18 * tint, 0.73 - 0.16 * tint, 0.70 - 0.18 * tint))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(rect, 8, 8)
        title = (L("100× oil — small cells (≤ 15 µm)", "100× زيت – الخلايا الصغيرة (≤ 15 ميكرومتر)")
                 if panel == "small" else
                 L("10× — large organisms (> 15 µm)", "10× – الكائنات الكبيرة (> 15 ميكرومتر)"))
        p.setPen(QColor("#e6edf3"))
        p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        p.drawText(QRectF(rect.x(), rect.y() - 18, rect.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, 8, 8)
        p.setClipPath(clip)
        k = rect.width() / field.width_um
        order = sorted((i for i in range(len(s.model.orgs)) if s.panel_of[i] == panel),
                       key=lambda i: -s.model.orgs[i].size_um)
        for i in order:
            o = s.model.orgs[i]
            col = QColor(o.colour)
            for x, y, ang, sc, ph in s.cells[i]:
                CommunityWidget._draw_cell(p, o, QPointF(rect.x() + x * k, rect.y() + y * k), ang,
                                           max(o.size_um * k * sc, 2.0), ph, col)
        p.restore()
        bar_um = 10 if panel == "small" else 200
        px = bar_um * k
        p.setPen(QPen(QColor(30, 30, 30), 3))
        p.drawLine(QPointF(rect.right() - px - 12, rect.bottom() - 12), QPointF(rect.right() - 12, rect.bottom() - 12))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(rect.right() - px - 32, rect.bottom() - 30, px + 40, 14), Qt.AlignCenter, f"{bar_um} µm")

    def _legend(self, p, area):
        """Outside the images, on a solid plate, so it is always readable."""
        s = self.scene
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#161b22"))
        p.drawRoundedRect(area, 6, 6)
        p.setFont(QFont("Segoe UI", 9))
        col_w = area.width() / 2
        for i, o in enumerate(s.model.orgs):
            x = area.x() + 10 + (i % 2) * col_w
            y = area.y() + 4 + (i // 2) * 20
            p.setBrush(QColor(o.colour))
            p.drawEllipse(QPointF(x + 5, y + 9), 5, 5)
            c = s.concentration[i]
            fac = f"×{c:,.0f}" if c >= 2 else (f"÷{1 / c:,.0f}" if c <= 0.5 else "×1")
            p.setPen(QColor("#e6edf3"))
            p.drawText(QRectF(x + 16, y, col_w - 30, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{L(o.name.split(' subsp.')[0], o.name_ar)}   {len(s.cells[i])}   {fac}")
            p.setPen(Qt.NoPen)

    # ---- shapes ----------------------------------------------------------
    @staticmethod
    def _draw_cell(p, o, c, ang, size, phase, col):
        d = o.draw
        p.setPen(QPen(col.darker(160), max(0.5, size * 0.04)))
        p.setBrush(col)
        if d in ("coccus", "sphere"):
            r = size / 2
            g = QRadialGradient(c + QPointF(-r * 0.3, -r * 0.3), r * 1.3)
            g.setColorAt(0, col.lighter(140))
            g.setColorAt(1, col.darker(130))
            p.setBrush(QBrush(g))
            p.drawEllipse(c, r, r)
            if d == "sphere" and r > 3:                      # chloroplast arc
                p.setPen(QPen(col.darker(170), max(1.0, r * 0.35)))
                p.drawArc(QRectF(c.x() - r * 0.65, c.y() - r * 0.65, r * 1.3, r * 1.3), int(phase * 300) * 16, 220 * 16)
        elif d == "chain":
            r = max(size / 2, 1.5)
            a = ang
            x, y = c.x(), c.y()
            for j in range(4):
                p.drawEllipse(QPointF(x, y), r, r * 0.92)
                x += math.cos(a) * r * 2.0
                y += math.sin(a) * r * 2.0
                a += 0.15
        elif d == "rod":
            L_ = size
            w = max(size * 0.32, 1.6)
            p.save()
            p.translate(c)
            p.rotate(math.degrees(ang))
            p.drawRoundedRect(QRectF(-L_ / 2, -w / 2, L_, w), w / 2, w / 2)
            p.restore()
        elif d == "yeast":
            r = size / 2
            p.drawEllipse(c, r, r * 0.82)
            p.drawEllipse(c + QPointF(r * 0.9, -r * 0.5), r * 0.45, r * 0.45)      # bud
        elif d == "colony":
            r = max(size / 5, 1.5)
            for j in range(4):
                p.drawEllipse(QPointF(c.x() + (j - 1.5) * r * 2.05, c.y()), r, r * 1.5)
        elif d == "hypha":
            p.setPen(QPen(col, max(1.5, size * 0.07), Qt.SolidLine, Qt.RoundCap))
            x, y, a = c.x(), c.y(), ang
            for j in range(5):
                nx, ny = x + math.cos(a) * size * 0.25, y + math.sin(a) * size * 0.25
                p.drawLine(QPointF(x, y), QPointF(nx, ny))
                if j == 2:
                    p.drawLine(QPointF(nx, ny), QPointF(nx + math.cos(a + 0.9) * size * 0.2,
                                                        ny + math.sin(a + 0.9) * size * 0.2))
                x, y, a = nx, ny, a + 0.15
        elif d in ("ciliate", "flagellate", "vorticella", "rotifer", "amoeba", "diatom"):
            CommunityWidget._big(p, d, c, ang, size, phase, col)
        else:
            p.drawEllipse(c, size / 2, size / 2)

    @staticmethod
    def _big(p, d, c, ang, size, phase, col):
        p.save()
        p.translate(c)
        p.rotate(math.degrees(ang))
        L_ = size
        w = L_ * 0.55
        if d == "ciliate":
            path = QPainterPath()
            path.addEllipse(QRectF(-L_ / 2, -w / 2, L_, w))
            p.setBrush(col.lighter(120))
            p.drawPath(path)
            p.setPen(QPen(col.darker(150), max(0.6, L_ * 0.012)))
            for j in range(16):                                   # cilia
                a = j / 16 * 2 * math.pi
                x0, y0 = math.cos(a) * L_ / 2, math.sin(a) * w / 2
                beat = 0.3 * math.sin(phase * 8 + j)
                p.drawLine(QPointF(x0, y0), QPointF(x0 * 1.18 + math.cos(a + beat) * L_ * 0.04,
                                                    y0 * 1.18 + math.sin(a + beat) * L_ * 0.04))
            p.setBrush(col.darker(140))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(-L_ * 0.12, 0), L_ * 0.1, w * 0.18)      # macronucleus
        elif d == "flagellate":
            path = QPainterPath()
            path.moveTo(-L_ / 2, 0)
            path.cubicTo(-L_ * 0.2, -w / 2, L_ * 0.2, -w / 2, L_ / 2, 0)
            path.cubicTo(L_ * 0.2, w / 2, -L_ * 0.2, w / 2, -L_ / 2, 0)
            p.setBrush(col.lighter(115))
            p.drawPath(path)
            p.setPen(QPen(col.darker(150), max(0.7, L_ * 0.02)))
            fl = QPainterPath()
            fl.moveTo(L_ / 2, 0)
            for j in range(1, 7):
                fl.lineTo(L_ / 2 + j * L_ * 0.09, math.sin(phase * 6 + j) * L_ * 0.05)
            p.drawPath(fl)
            p.setBrush(QColor("#e5534b"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(L_ * 0.25, -w * 0.12), L_ * 0.04, L_ * 0.04)    # eyespot
        elif d == "vorticella":
            p.setPen(QPen(col.darker(150), max(1.0, L_ * 0.03)))
            stalk = QPainterPath()
            stalk.moveTo(0, L_ * 0.3)
            for j in range(1, 9):
                stalk.lineTo(math.sin(j * 1.6 + phase) * L_ * 0.07, L_ * 0.3 + j * L_ * 0.09)
            p.drawPath(stalk)
            p.setBrush(col.lighter(115))
            bell = QPainterPath()
            bell.moveTo(-w / 2, -L_ * 0.25)
            bell.cubicTo(-w / 2, L_ * 0.25, w / 2, L_ * 0.25, w / 2, -L_ * 0.25)
            bell.closeSubpath()
            p.drawPath(bell)
        elif d == "rotifer":
            from .microscope_widget import MicroscopeWidget
            p.rotate(90)
            MicroscopeWidget._rotifer(p, QPointF(0, 0), -math.pi / 2, 1, L_, phase)
        elif d == "amoeba":
            path = QPainterPath()
            n = 11
            for j in range(n + 1):
                a = j / n * 2 * math.pi
                rr = L_ / 2 * (0.6 + 0.4 * abs(math.sin(a * 1.5 + phase * 0.6)))
                pt = QPointF(math.cos(a) * rr, math.sin(a) * rr * 0.8)
                path.moveTo(pt) if j == 0 else path.lineTo(pt)
            path.closeSubpath()
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 150))
            p.drawPath(path)
            p.setBrush(col.darker(130))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(0, 0), L_ * 0.09, L_ * 0.09)
        elif d == "diatom":
            p.setBrush(col.lighter(125))
            path = QPainterPath()
            path.moveTo(-L_ / 2, 0)
            path.cubicTo(-L_ * 0.3, -w * 0.5, L_ * 0.3, -w * 0.5, L_ / 2, 0)
            path.cubicTo(L_ * 0.3, w * 0.5, -L_ * 0.3, w * 0.5, -L_ / 2, 0)
            p.drawPath(path)
            p.setPen(QPen(col.darker(160), max(0.5, L_ * 0.015)))
            p.drawLine(QPointF(-L_ * 0.4, 0), QPointF(L_ * 0.4, 0))                 # raphe
            for j in range(-4, 5):                                                   # striae
                x = j * L_ * 0.09
                p.drawLine(QPointF(x, -w * 0.3), QPointF(x, w * 0.3))
        p.restore()

    # ---- vessel ----------------------------------------------------------
    def _vessel(self, p, area):
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
