"""Shared microscope widget: fields of view, legend, zoom/pan, organism inspector and display modes.

Lab widgets subclass it and paint their own side panel (vessel, jar, culture) in `paint_side`.
All numbers come from the Specimen (which reads the simulation state); this class only draws.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..i18n import L, is_ar
from ..library.morphology import DIVISION, MOTILITY
from ..viz.population import DIVIDING, DYING, ENTERING, GRAZED, LEAVING, STATE_NAMES
from ..viz.specimen import Specimen
from .specimen_paint import Look, paint_agent

STATE_AR = ("حية", "تنقسم", "تموت", "تُؤكل", "تدخل مجال الرؤية", "تخرج من مجال الرؤية")


class SpecimenView(QWidget):
    side_width = 0.0            # fraction of the width reserved for the side panel (0 = none)
    stain = ""                  # "gram" for stained smears in microscope mode
    background = ((0.97, 0.96, 0.93), (0.76, 0.75, 0.72))

    def __init__(self, scene: Specimen, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.expected = ()
        self.time_d = 0.0
        self.time_unit = "d"
        self.zoom = 1.0
        self.center = (0.5, 0.5)                 # view centre in field-normalised coordinates
        self._drag = None
        self._panel_rects: dict[str, QRectF] = {}
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setToolTip(L("Wheel: zoom · drag: pan · double-click: reset view · click an organism to inspect it",
                          "العجلة: تكبير · السحب: تحريك · نقرتان: إرجاع العرض · انقر على كائن لتفحصه"))

    # ------------------------------------------------------------------ layout
    def layout_rects(self) -> tuple[QRectF, QRectF | None, QRectF]:
        w, h = self.width(), self.height()
        gap = 10
        side = QRectF(w - gap - w * self.side_width, gap + 18, w * self.side_width, h - 2 * gap - 36) \
            if self.side_width > 0 else None
        n_tr = len(self.scene.tracks)
        legend_h = 20 * ((n_tr + 1) // 2) + 8
        right = side.left() - gap if side else w - gap
        area = QRectF(gap, gap + 20, right - gap, h - 2 * gap - 46 - legend_h)
        rects = self.panel_rects(area)
        bottom = max((r.bottom() for r in rects.values()), default=area.bottom())
        spare = area.bottom() - bottom                       # centre the panels + legend block vertically
        area.translate(0, spare / 2)
        legend = QRectF(gap, bottom + spare / 2 + 8, right - gap, legend_h)
        return area, side, legend

    def panel_rects(self, area: QRectF) -> dict[str, QRectF]:
        names = self.scene.panel_names
        gap = 12
        out = {}
        n = max(len(names), 1)
        pw = (area.width() - gap * (n - 1)) / n
        x = area.x()
        for name in names:
            f = self.scene.panels[name]
            aspect = f.width_um / f.height_um
            rw, rh = pw, area.height()
            if rw / rh > aspect:
                rw = rh * aspect
            else:
                rh = rw / aspect
            out[name] = QRectF(x + (pw - rw) / 2, area.y(), rw, rh)
            x += pw + gap
        return out

    # ------------------------------------------------------------------ painting
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d1117"))
        area, side, legend = self.layout_rects()
        self._panel_rects = self.panel_rects(area)
        for name, rect in self._panel_rects.items():
            self._panel(p, name, rect)
        self._legend(p, legend)
        if side is not None:
            self.paint_side(p, side)
        self._footer(p)
        self._inspector(p)
        p.end()

    def panel_title(self, name: str) -> str:
        return self.scene.panels[name].title

    def panel_background(self, name: str) -> tuple[QColor, QColor]:
        if self.scene.mode == "microscope":
            if self.stain == "gram":
                return QColor(246, 226, 232), QColor(206, 176, 186)
            return QColor(150, 154, 158), QColor(96, 100, 104)
        (a, b, c), (d, e, f) = self.background
        return QColor.fromRgbF(a, b, c), QColor.fromRgbF(d, e, f)

    def _view_transform(self, rect: QRectF, field) -> tuple[float, float, float]:
        """Pixels per µm and the µm coordinate of the rect's top-left corner, for the current zoom/pan."""
        k = rect.width() / field.width_um * self.zoom
        vw, vh = field.width_um / self.zoom, field.height_um / self.zoom
        cx = min(max(self.center[0] * field.width_um, vw / 2), field.width_um - vw / 2)
        cy = min(max(self.center[1] * field.height_um, vh / 2), field.height_um - vh / 2)
        return k, cx - vw / 2, cy - vh / 2

    def _panel(self, p: QPainter, name: str, rect: QRectF):
        s = self.scene
        field = s.panels[name]
        inner, outer = self.panel_background(name)
        g = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.68)
        g.setColorAt(0, inner)
        g.setColorAt(1, outer)                                              # vignetting of the objective
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(rect, 8, 8)
        p.setPen(QColor("#e6edf3"))
        p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        title = self.panel_title(name) + (f"   ·   {self.zoom:.1f}× zoom" if self.zoom > 1.01 else "")
        p.drawText(QRectF(rect.x(), rect.y() - 19, rect.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(rect, 8, 8)
        p.setClipPath(clip)
        k, ox, oy = self._view_transform(rect, field)
        p.translate(rect.x() - ox * k, rect.y() - oy * k)
        look = Look(s.mode, self.stain)
        order = sorted((i for i, tr in enumerate(s.tracks) if tr.panel == name),
                       key=lambda i: -s.tracks[i].spec.length_um)
        for i in order:
            tr = s.tracks[i]
            for a in tr.pop.agents:
                paint_agent(p, tr.spec, a, k, look, self.agent_extra(i, a))
        if s.mode == "explain":
            self._overlays(p, name, k)
        p.restore()
        self._scale_bar(p, rect, field)

    def agent_extra(self, track_index: int, agent) -> dict:
        return {}

    def _overlays(self, p: QPainter, name: str, k: float):
        """Explanation mode: mark what each drawn organism is doing, and who eats whom."""
        s = self.scene
        p.setFont(QFont("Segoe UI", 7))
        for i, tr in enumerate(s.tracks):
            if tr.panel != name:
                continue
            col = QColor(tr.colour)
            for a in tr.pop.agents:
                c = QPointF(a.x * k, a.y * k)
                r = max(tr.spec.length_um * k * 0.7, 6)
                if a.state == DIVIDING:
                    p.setPen(QPen(QColor(63, 185, 80, 220), 1.4, Qt.DashLine))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(c, r, r)
                elif a.state in (DYING, LEAVING):
                    p.setPen(QPen(QColor(248, 81, 73, 200), 1.2, Qt.DotLine))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(c, r, r)
                elif a.state == GRAZED:
                    pred = next((b for j in tr.predators for b in s.tracks[j].pop.agents if b.id == a.prey_of), None)
                    if pred is not None:
                        p.setPen(QPen(QColor(240, 136, 62, 230), 1.4))
                        p.drawLine(c, QPointF(pred.x * k, pred.y * k))
                if s.selected == (i, a.id):
                    p.setPen(QPen(col.lighter(130), 2))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(c, r + 3, r + 3)
        if s.selected and s.mode != "explain":
            pass

    def _scale_bar(self, p: QPainter, rect: QRectF, field):
        target_px = rect.width() * 0.18
        um_per_px = field.width_um / (rect.width() * self.zoom)
        raw = target_px * um_per_px
        mag = 10 ** math.floor(math.log10(max(raw, 1e-9)))
        um = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw * 0.6)
        px = um / um_per_px
        dark = self.scene.mode != "microscope" or self.stain == "gram"
        col = QColor(25, 25, 25) if dark else QColor(245, 245, 245)
        p.setPen(QPen(col, 3))
        p.drawLine(QPointF(rect.right() - px - 12, rect.bottom() - 12), QPointF(rect.right() - 12, rect.bottom() - 12))
        p.setFont(QFont("Segoe UI", 8))
        label = f"{um:g} µm" if um < 1000 else f"{um / 1000:g} mm"
        p.drawText(QRectF(rect.right() - px - 32, rect.bottom() - 30, px + 40, 14), Qt.AlignCenter, label)

    def _legend(self, p: QPainter, area: QRectF):
        s = self.scene
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#161b22"))
        p.drawRoundedRect(area, 6, 6)
        p.setFont(QFont("Segoe UI", 9))
        col_w = area.width() / 2
        drawn = s.drawn_counts()
        for i, tr in enumerate(s.tracks):
            x = area.x() + 10 + (i % 2) * col_w
            y = area.y() + 4 + (i // 2) * 20
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(tr.colour))
            p.drawEllipse(QPointF(x + 5, y + 9), 5, 5)
            p.setPen(QColor("#e6edf3"))
            name = L(tr.label.split(" subsp.")[0], tr.label_ar)
            text = L(f"{name}  ·  {drawn[i]} in view  ·  sample {tr.factor_text()}",
                     f"{name}  ·  {drawn[i]} في المجال  ·  العينة {tr.factor_text()}")
            p.drawText(QRectF(x + 16, y, col_w - 30, 18), Qt.AlignLeft | Qt.AlignVCenter, text)

    def footer_text(self) -> str:
        u = self.time_unit
        return L(f"t = {self.time_d:.2f} {u} · growth & division: time-lapse of the model · swimming: real time · "
                 "each drawn cell represents a cohort",
                 f"t = {self.time_d:.2f} {'يوم' if u == 'd' else 'ساعة'} · النمو والانقسام: تسريع للنموذج · "
                 "السباحة: سرعة حقيقية · كل خلية مرسومة تمثل مجموعة")

    def _footer(self, p: QPainter):
        p.setPen(QColor("#8b949e"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(10, self.height() - 18, self.width() - 20, 16),
                   (Qt.AlignRight if is_ar() else Qt.AlignLeft) | Qt.AlignVCenter, self.footer_text())

    def paint_side(self, p: QPainter, rect: QRectF):
        """Override to draw the vessel / jar beside the microscope."""

    # ------------------------------------------------------------------ inspector
    def _inspector(self, p: QPainter):
        info = self.scene.inspect()
        if not info:
            return
        tr, a = info["track"], info["agent"]
        spec = tr.spec
        mot, div = spec.describe()
        if a is None:
            lines = [L(tr.label, tr.label_ar), L("This organism is no longer in view.", "هذا الكائن لم يعد في مجال الرؤية.")]
        else:
            field = self.scene.panels[tr.panel]
            per_ml = 1.0 / max(tr.concentration * field.sampled_volume_ml, 1e-30)
            state = STATE_AR[a.state] if is_ar() else STATE_NAMES[a.state]
            size = spec.length_um * a.size * (0.55 + 0.45 * a.grow)
            lines = [
                L(tr.label, tr.label_ar),
                L(f"Drawn unit #{a.id % 1_000_000} · {state}" + (f" ({a.progress * 100:.0f} %)" if a.state != 0 else ""),
                  f"الوحدة المرسومة #{a.id % 1_000_000} · {state}" + (f" ({a.progress * 100:.0f}٪)" if a.state != 0 else "")),
                L(f"Length ≈ {size:.1f} µm" + (f" · {a.n} cells" if a.n > 1 else ""),
                  f"الطول ≈ {size:.1f} ميكرومتر" + (f" · {a.n} خلايا" if a.n > 1 else "")),
                L(f"Represents ≈ {per_ml:.3g} cells per mL of culture", f"تمثل ≈ {per_ml:.3g} خلية في كل مل من المزرعة"),
                L(f"Moves: {mot}", f"الحركة: {mot}"),
                L(f"Divides: {div}", f"الانقسام: {div}"),
                L("Shape from: " + (spec.reference.split(";")[0] or spec.provenance),
                  "مصدر الشكل: " + (spec.reference.split(";")[0] or spec.provenance)),
            ]
        p.setFont(QFont("Segoe UI", 8))
        fm = p.fontMetrics()
        w = min(max(fm.horizontalAdvance(t) for t in lines) + 20, self.width() * 0.6)
        h = 16 * len(lines) + 12
        box = QRectF(14, 32, w, h)
        p.setPen(QPen(QColor(tr.colour), 1.2))
        p.setBrush(QColor(13, 17, 23, 228))
        p.drawRoundedRect(box, 6, 6)
        p.setPen(QColor("#e6edf3"))
        for j, t in enumerate(lines):
            p.setFont(QFont("Segoe UI", 9 if j == 0 else 8, QFont.DemiBold if j == 0 else QFont.Normal))
            p.drawText(QRectF(box.x() + 10, box.y() + 6 + j * 16, w - 16, 16), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(t, Qt.ElideRight, int(w - 16)))

    # ------------------------------------------------------------------ interaction
    def _hit(self, pos) -> tuple[str, float, float] | None:
        for name, rect in self._panel_rects.items():
            if rect.contains(pos):
                field = self.scene.panels[name]
                k, ox, oy = self._view_transform(rect, field)
                return name, ox + (pos.x() - rect.x()) / k, oy + (pos.y() - rect.y()) / k
        return None

    def wheelEvent(self, e):
        hit = self._hit(e.position())
        old = self.zoom
        self.zoom = float(min(max(self.zoom * (1.25 if e.angleDelta().y() > 0 else 0.8), 1.0), 12.0))
        if hit and self.zoom != old:
            name, xu, yu = hit
            f = self.scene.panels[name]
            # keep the point under the mouse fixed
            cx, cy = self.center
            fx, fy = xu / f.width_um, yu / f.height_um
            self.center = (fx + (cx - fx) * old / self.zoom, fy + (cy - fy) * old / self.zoom)
        if self.zoom <= 1.0:
            self.center = (0.5, 0.5)
        self.update()

    def mousePressEvent(self, e):
        self._drag = (e.position(), self.center, False)

    def mouseMoveEvent(self, e):
        if self._drag is None or not (e.buttons() & Qt.LeftButton):
            return
        start, c0, _ = self._drag
        d = e.position() - start
        if abs(d.x()) + abs(d.y()) > 4:
            self._drag = (start, c0, True)
        rect = next(iter(self._panel_rects.values()), None)
        if rect is None or self.zoom <= 1.0:
            return
        self.center = (c0[0] - d.x() / (rect.width() * self.zoom), c0[1] - d.y() / (rect.height() * self.zoom))
        self.update()

    def mouseReleaseEvent(self, e):
        if self._drag and not self._drag[2]:                       # a click, not a drag: inspect
            hit = self._hit(e.position())
            if hit:
                name, xu, yu = hit
                rect = self._panel_rects[name]
                k = rect.width() / self.scene.panels[name].width_um * self.zoom
                found = self.scene.agent_at(name, xu, yu, tol_um=8 / k)
                self.scene.selected = (found[0], found[1].id) if found else None
            else:
                self.scene.selected = None
            self.update()
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.zoom, self.center = 1.0, (0.5, 0.5)
        self.update()
