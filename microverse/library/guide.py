"""Printable organism guide (HTML → PDF) — a reference for students and lecturers."""
from __future__ import annotations

import html
from datetime import date

from ..i18n import L, is_ar
from .functions import FUNCTIONS, functions_of, organisms_with
from .organisms import ORGANISMS, RESOURCES, by_group


def guide_html() -> str:
    e = html.escape
    d = "rtl" if is_ar() else "ltr"
    align = "right" if is_ar() else "left"
    css = (f"body{{font-family:'Segoe UI',Tahoma,Arial; font-size:9.5pt; color:#111; direction:{d}; text-align:{align}}}"
           "h1{font-size:20pt; margin:0} h2{font-size:14pt; border-bottom:2px solid #333; margin-top:18px}"
           "h3{font-size:11.5pt; margin:12px 0 2px 0} .muted{color:#555} td{vertical-align:top; padding:2px 6px}"
           ".chip{border-radius:5px; padding:0 5px; font-size:8pt}")
    out = [f"<html><head><style>{css}</style></head><body>"]
    out.append(f"<h1>MicroVerse — {e(L('Organism guide', 'دليل الكائنات'))}</h1>")
    out.append(f"<p class='muted'>{e(L(f'{len(ORGANISMS)} organisms · {len(FUNCTIONS)} functions · generated {date.today()}', f'{len(ORGANISMS)} كائناً · {len(FUNCTIONS)} وظيفة · أُنشئ في {date.today()}'))}<br>"
               + e(L("The usual teaching/food strains of all organisms are Risk Group 1; classification is per strain and country. Functions marked 'from traits' are read directly from the "
                     "numbers the simulation uses. Traits are textbook estimates and are not yet validated.",
                     "السلالات المعتادة لكل الكائنات من مجموعة الخطورة 1، والتصنيف يعتمد على السلالة والدولة. الوظائف المعلَّمة «من صفاته» مأخوذة مباشرة من الأرقام التي "
                     "تستخدمها المحاكاة. الصفات تقديرات من الكتب وغير متحقق منها مخبرياً بعد.")) + "</p>")

    # Part 1: functions
    out.append(f"<h2>{e(L('Part 1 — Functions: what organisms do', 'الجزء الأول – الوظائف: ماذا تفعل الكائنات'))}</h2>")
    out.append("<table>")
    for f in FUNCTIONS.values():
        who = ", ".join(L(o.name, o.name_ar) for o in organisms_with(f.key)) or "—"
        out.append(f"<tr><td style='color:{f.colour}; white-space:nowrap'><b>{e(f.icon)} {e(L(f.name, f.name_ar))}</b></td>"
                   f"<td>{e(L(f.meaning, f.meaning_ar))}"
                   + (f"<br><span class='muted'>{e(L('In the simulation', 'في المحاكاة'))}: {e(L(f.in_model, f.in_model_ar))}</span>" if f.in_model else "")
                   + f"<br><i>{e(L('Who', 'من يقوم بها'))}: {e(who)}</i></td></tr>")
    out.append("</table>")

    # Part 2: organisms
    out.append(f"<h2>{e(L('Part 2 — Organisms', 'الجزء الثاني – الكائنات'))}</h2>")
    for group, items in by_group().items():
        out.append(f"<h3 style='color:#444'>{e(L(group, items[0].group_ar.split(' –')[0]))}</h3>")
        for o in items:
            fs = " · ".join(f"{f.icon} {L(f.name, f.name_ar)}" for f in functions_of(o.key))
            eats = ", ".join(L(RESOURCES[s][0], RESOURCES[s][1]) for s in o.substrates) or L("other organisms", "كائنات أخرى")
            makes = ", ".join(L(RESOURCES[s][0], RESOURCES[s][1]) for s in o.products) or "—"
            out.append(
                f"<p><b><i>{e(o.name)}</i></b> — {e(o.name_ar)}<br>"
                f"<span style='color:{o.colour}'>{e(fs)}</span><br>"
                f"<b>{e(L('What it does', 'وظيفته'))}:</b> {e(L(o.role, o.role_ar))}<br>"
                f"<b>{e(L('Eats', 'يأكل'))}:</b> {e(eats)} · <b>{e(L('Produces', 'ينتج'))}:</b> {e(makes)} · "
                f"<b>{e(L('Oxygen', 'الأكسجين'))}:</b> {e(L(*o.oxygen_label))}<br>"
                f"<b>{e(L('Best at', 'أفضل نمو'))}:</b> {o.cardinal_T[1]:g} °C, pH {o.cardinal_pH[1]:g} · "
                f"<b>{e(L('Size', 'الحجم'))}:</b> {e(o.size_text)}<br>"
                f"<span class='muted'>{e(' › '.join(o.lineage))} (NCBI {o.ncbi_taxid}) · "
                f"{e(L(o.applications, o.applications_ar))}</span></p>")
    out.append("</body></html>")
    return "\n".join(out)


def export_pdf(path: str) -> None:
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(14, 14, 14, 14), QPageLayout.Millimeter)
    writer.setResolution(150)
    doc = QTextDocument()
    doc.setHtml(guide_html())
    rect = writer.pageLayout().paintRectPixels(writer.resolution())
    doc.setPageSize(QSizeF(rect.width(), rect.height()))
    doc.print_(writer)
