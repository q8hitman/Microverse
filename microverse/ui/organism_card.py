"""Organism information card with a small drawn portrait, in the selected language."""
from __future__ import annotations

import html
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..i18n import L, is_ar
from ..library.functions import functions_of, is_derived
from ..library.organisms import RESOURCES, Organism
from .style import TEXT_2


class Portrait(QWidget):
    """Schematic portrait, drawn with the same shape vocabulary as the microscope view."""

    def __init__(self, org: Organism, small: bool = False, parent=None):
        super().__init__(parent)
        self.org = org
        self.size_px = 44 if small else 110
        self.setFixedSize(self.size_px, self.size_px)

    def paintEvent(self, _):
        from ..library.morphology import spec_for
        from ..viz.population import Agent
        from .specimen_paint import Look, paint_agent
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        s = self.size_px
        p.setBrush(QColor("#e9e6dc"))                     # brightfield disc
        p.drawEllipse(QRectF(2, 2, s - 4, s - 4))
        spec = spec_for(self.org.key)
        n = min(max(spec.max_chain, 1), 4)
        units = n if spec.shape in ("coccus", "ovococcus", "rod", "oval") else 1
        span = spec.length_um * (units if spec.shape != "packet" else 1.2)
        if spec.shape in ("bell", "hypha"):
            span *= 1.9
        k = s * 0.66 / max(span, 1e-6)
        a = Agent(0, 0.0, 0.0, -0.45 if spec.shape not in ("bell",) else 0.0, n=n, variant=0.7, phase=1.0)
        p.translate(s / 2, s / 2)
        if spec.shape == "hypha":
            p.translate(-s * 0.3, s * 0.15)
        elif spec.shape == "bell":
            p.translate(0, s * 0.3)
        paint_agent(p, spec, a, k, Look("natural"))
        p.end()


def badges_html(key: str, size_pt: int = 8) -> str:
    """Coloured function chips; the tooltip-free HTML version used inside rich text."""
    out = []
    for f in functions_of(key):
        out.append(f"<span style='background:{f.colour}33; color:{f.colour}; border-radius:6px; "
                   f"padding:1px 6px; font-size:{size_pt}pt'>&nbsp;{html.escape(f.icon)} "
                   f"{html.escape(L(f.name, f.name_ar))}&nbsp;</span>")
    return " ".join(out)


def functions_table(key: str) -> str:
    """'What it does' rows: each function, what it means, and how the simulation represents it."""
    rows = []
    for f in functions_of(key):
        how = L(f.in_model, f.in_model_ar) if f.in_model else L("Not simulated — information only.",
                                                                "غير ممثل في المحاكاة – للمعلومة فقط.")
        src = L("from its traits", "من صفاته") if is_derived(key, f.key) else L("assigned by hand", "مُضاف يدوياً")
        rows.append(f"<tr><td valign=top style='color:{f.colour}; white-space:nowrap'><b>{html.escape(f.icon)} "
                    f"{html.escape(L(f.name, f.name_ar))}</b></td><td>{html.escape(L(f.meaning, f.meaning_ar))}"
                    f"<br><span style='color:{TEXT_2}'>{L('In the simulation', 'في المحاكاة')}: {html.escape(how)} "
                    f"<i>({src})</i></span></td></tr>")
    return "<table cellpadding=3>" + "".join(rows) + "</table>"


class OrganismCard(QFrame):
    def __init__(self, org: Organism, compact: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        e = html.escape
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.addWidget(Portrait(org), 0, Qt.AlignTop)
        v = QVBoxLayout()
        title = QLabel(
            f"<span style='font-size:12pt; font-weight:700; color:{org.colour}'><i>{e(org.name)}</i></span>"
            f"<br><span style='color:{TEXT_2}'>{e(org.common)} · {e(org.group)}</span>"
            f"<br><span style='font-size:11pt'>{e(org.name_ar)} — {e(org.common_ar)} · {e(org.group_ar)}</span>")
        title.setWordWrap(True)
        v.addWidget(title)
        chips = QLabel(badges_html(org.key))
        chips.setWordWrap(True)
        chips.setToolTip("<br>".join(f"<b>{f.icon} {L(f.name, f.name_ar)}</b>: {L(f.meaning, f.meaning_ar)}"
                                     for f in functions_of(org.key)))
        v.addWidget(chips)

        eats = ", ".join(L(RESOURCES[s][0], RESOURCES[s][1]) for s in org.substrates) or L("other organisms", "كائنات أخرى")
        makes = ", ".join(L(RESOURCES[s][0], RESOURCES[s][1]) for s in org.products) or "—"
        rows = [
            (L("What it does", "وظيفته"), f"{e(org.role)}<br><span dir='rtl'>{e(org.role_ar)}</span>"),
            (L("How it feeds", "كيف يتغذى"), e(L(*org.feeding_label))),
            (L("Oxygen", "الأكسجين"), e(L(*org.oxygen_label))),
            (L("Eats", "يأكل"), e(eats)),
            (L("Produces", "ينتج"), e(makes)),
            (L("Size & shape", "الحجم والشكل"),
             f"{e(org.size_text)}. {e(org.shape)}<br><span dir='rtl'>{e(org.shape_ar)}</span>"),
            (L("Grows best at", "أفضل نمو عند"),
             L(f"{org.cardinal_T[1]:g} °C (range {org.cardinal_T[0]:g}–{org.cardinal_T[2]:g}), "
               f"pH {org.cardinal_pH[1]:g} (range {org.cardinal_pH[0]:g}–{org.cardinal_pH[2]:g})",
               f"{org.cardinal_T[1]:g} مئوية (المدى {org.cardinal_T[0]:g}–{org.cardinal_T[2]:g})، "
               f"وحموضة {org.cardinal_pH[1]:g} (المدى {org.cardinal_pH[0]:g}–{org.cardinal_pH[2]:g})")),
        ]
        if not compact:
            rows.insert(1, (L("Its functions", "وظائفه بالتفصيل"), functions_table(org.key)))
            rows += [
                (L("Classification", "التصنيف"), " › ".join(org.lineage) + f"  (NCBI Taxonomy {org.ncbi_taxid})"),
                (L("Movement", "الحركة"), f"{e(org.motility)}<br><span dir='rtl'>{e(org.motility_ar)}</span>"),
                (L("Metabolism", "الأيض"), f"{e(org.metabolism)}<br><span dir='rtl'>{e(org.metabolism_ar)}</span>"),
                (L("Habitat", "الموطن"), f"{e(org.habitat)} — <span dir='rtl'>{e(org.habitat_ar)}</span>"),
                (L("Reproduction", "التكاثر"), f"{e(org.reproduction)}<br><span dir='rtl'>{e(org.reproduction_ar)}</span>"),
                (L("Uses", "الاستخدامات"), f"{e(org.applications)} — <span dir='rtl'>{e(org.applications_ar)}</span>"),
                (L("Strain described", "السلالة الموصوفة"), e(org.strain) if org.strain else L("not strain-specific", "غير خاص بسلالة")),
                (L("Biosafety", "السلامة الحيوية"), f"{e(org.biosafety)}<br><span dir='rtl'>{e(org.biosafety_ar)}</span>"),
                (L("Traits in the model", "الصفات في النموذج"),
                 L(f"max growth {org.mu_max:g} /h · half-saturation {org.ks:g} mg/L · yield {org.yield_bio:g} · "
                   f"death {org.death:g} /h · evidence: {org.trait_evidence.value}",
                   f"أقصى نمو {org.mu_max:g}/ساعة · ثابت نصف التشبع {org.ks:g} ملغم/ل · العائد {org.yield_bio:g} · "
                   f"الموت {org.death:g}/ساعة · مستوى الدليل: {org.trait_evidence.value}")),
            ]
            if org.feeding == "predator":
                rows.append((L("Grazing", "الرعي"),
                             L(f"eats prey up to {org.prey_size_max:g} µm, up to {org.ingest_max:g} mg prey per mg of "
                               f"itself per hour", f"يأكل فرائس حتى {org.prey_size_max:g} ميكرومتر، وحتى "
                               f"{org.ingest_max:g} ملغم فريسة لكل ملغم من كتلته في الساعة")))
            if org.model_variables:
                rows.append((L("In the models", "في النماذج"), "<br>".join(e(x) for x in org.model_variables)))
            if org.notes:
                rows.append((L("Notes", "ملاحظات"), "<br>".join(e(n) for n in org.notes)))
            rows.append((L("References", "المراجع"), "<br>".join(e(r) for r in org.references)))
        body = "<table cellpadding=3>" + "".join(
            f"<tr><td valign=top style='color:{TEXT_2}; white-space:nowrap'>{k}</td><td>{val}</td></tr>"
            for k, val in rows) + "</table>"
        info = QLabel(body)
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        v.addWidget(info)
        lay.addLayout(v, 1)
