"""Interaction network for the organisms of a lab: what the traits suggest, and (if measured) what happened.

Nodes = organisms (portrait colour). Arrows from `relations()` (trait-based expectations):
eats, feeds (cross-feeding), opens (hydrolysis), oxygen, acid, compete. If the interaction analysis was
run, each measured pair gets a labelled bar under the graph with its classification and effect sizes.
Kind is shown by colour AND a text label on the arrow, so colour is never the only cue.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..i18n import L
from ..library.functions import relations
from ..library.organisms import ORGANISMS

KIND = {
    "eats": ("#d95926", ("eats", "يأكل")),
    "feeds": ("#199e70", ("feeds", "يغذي")),
    "opens": ("#9085e9", ("frees sugar", "يحرر السكر")),
    "oxygen": ("#3987e5", ("O₂", "أكسجين")),
    "acid": ("#e3b341", ("acid", "حمض")),
    "compete": ("#8b949e", ("compete", "تنافس")),
}


def short_name(key: str) -> str:
    o = ORGANISMS[key]
    if L("en", "ar") == "ar":
        return o.name_ar.split(" ")[0]
    parts = o.name.split(" ")
    return f"{parts[0][0]}. {parts[1]}" if len(parts) > 1 and parts[1][0].islower() else parts[0]


class InteractionGraph(QWidget):
    H = 290
    def __init__(self, keys: tuple[str, ...], parent=None):
        super().__init__(parent)
        self.keys = keys
        self.rel = relations(keys)
        self.measured = []                       # list of Interaction from analysis.interactions
        self.setMinimumHeight(self.H + 30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_measured(self, inter):
        self.measured = list(inter or [])
        self.setMinimumHeight(self.H + 30 + 18 * len(self.measured))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.H - 30
        n = len(self.keys)
        cx, cy, R = w / 2, h / 2 + 6, min(w * 0.8, h) * 0.36
        self.labels = len(self.rel) <= 8
        pos = {}
        for i, k in enumerate(self.keys):
            a = -math.pi / 2 + 2 * math.pi * i / max(n, 1)
            pos[k] = QPointF(cx + R * math.cos(a), cy + R * math.sin(a))
        # arrows (offset parallel arrows between the same pair so they do not overlap)
        pair_count: dict[tuple[str, str], int] = {}
        for a, b, kind, _en, _ar in self.rel:
            key = tuple(sorted((a, b)))
            j = pair_count.get(key, 0)
            pair_count[key] = j + 1
            self._arrow(p, pos[a], pos[b], kind, j, a < b)
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        for k, c in pos.items():
            o = ORGANISMS[k]
            p.setPen(QPen(QColor(o.colour).darker(150), 2))
            p.setBrush(QColor(o.colour))
            p.drawEllipse(c, 12, 12)
            ux, uy = (c.x() - cx) / max(R, 1), (c.y() - cy) / max(R, 1)       # name outside the circle
            tx, ty = c.x() + ux * 26, c.y() + uy * 22
            align = (Qt.AlignLeft if ux > 0.3 else Qt.AlignRight if ux < -0.3 else Qt.AlignHCenter) | Qt.AlignVCenter | Qt.AlignAbsolute
            box = QRectF(tx - (0 if ux > 0.3 else 120 if ux < -0.3 else 60), ty - 8, 120, 16)
            p.setPen(QColor("#e6edf3"))
            p.drawText(box, align, short_name(k))
        if not self.labels:                                                   # legend instead of arrow labels
            used = []
            for _a, _b, kind, _e, _r in self.rel:
                if kind not in used:
                    used.append(kind)
            x = 8
            p.setFont(QFont("Segoe UI", 7))
            for kind in used:
                col, label = KIND.get(kind, ("#8b949e", (kind, kind)))
                p.setPen(QPen(QColor(col), 2))
                p.drawLine(QPointF(x, h + 2), QPointF(x + 14, h + 2))
                t = L(*label)
                p.drawText(QRectF(x + 17, h - 5, 90, 14), Qt.AlignLeft | Qt.AlignVCenter, t)
                x += 24 + p.fontMetrics().horizontalAdvance(t)
        y = h + 14
        p.setFont(QFont("Segoe UI", 8))
        if not self.rel:
            p.setPen(QColor("#8b949e"))
            p.drawText(QRectF(8, 8, w - 16, 16), Qt.AlignLeft,
                       L("The traits suggest no direct interaction.", "الصفات لا توحي بتفاعل مباشر."))
        for it in self.measured:
            p.setPen(QColor(it.colour))
            text = (f"{L('measured', 'مقاس')}: {L(ORGANISMS[it.a].name, ORGANISMS[it.a].name_ar)} ↔ "
                    f"{L(ORGANISMS[it.b].name, ORGANISMS[it.b].name_ar)} — {L(it.kind, it.kind_ar)} "
                    f"(log10 effects {it.effect_of_b_on_a:+.2f} / {it.effect_of_a_on_b:+.2f})")
            p.drawText(QRectF(8, y, w - 16, 16), Qt.AlignLeft | Qt.AlignVCenter, text)
            y += 18
        p.end()

    def _arrow(self, p, a: QPointF, b: QPointF, kind: str, j: int, flip: bool):
        col, label = KIND.get(kind, ("#8b949e", (kind, kind)))
        dx, dy = b.x() - a.x(), b.y() - a.y()
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        nx, ny = -uy, ux
        bend = (12 + 14 * j) * (1 if flip else -1)
        s = QPointF(a.x() + ux * 16, a.y() + uy * 16)
        e = QPointF(b.x() - ux * 18, b.y() - uy * 18)
        mid = QPointF((s.x() + e.x()) / 2 + nx * bend, (s.y() + e.y()) / 2 + ny * bend)
        path = QPainterPath(s)
        path.quadTo(mid, e)
        pen = QPen(QColor(col), 1.8, Qt.DashLine if kind == "compete" else Qt.SolidLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        ang = math.atan2(e.y() - mid.y(), e.x() - mid.x())
        head = QPolygonF([e, QPointF(e.x() - 9 * math.cos(ang - 0.4), e.y() - 9 * math.sin(ang - 0.4)),
                          QPointF(e.x() - 9 * math.cos(ang + 0.4), e.y() - 9 * math.sin(ang + 0.4))])
        p.setBrush(QColor(col))
        p.drawPolygon(head)
        if not self.labels:
            return
        p.setFont(QFont("Segoe UI", 7))
        lbl = L(*label)
        tp = path.pointAtPercent(0.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(13, 17, 23, 210))
        fw = p.fontMetrics().horizontalAdvance(lbl) + 6
        p.drawRoundedRect(QRectF(tp.x() - fw / 2, tp.y() - 7, fw, 14), 3, 3)
        p.setPen(QColor(col))
        p.drawText(QRectF(tp.x() - fw / 2, tp.y() - 7, fw, 14), Qt.AlignCenter, lbl)
