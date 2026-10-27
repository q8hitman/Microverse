"""Bilingual explanation engine for the community lab.

Every sentence is built from quantities the model computed at the chosen time.
"""
from __future__ import annotations

import html

import numpy as np

from ..i18n import L, is_ar, rtl, t
from ..library.organisms import RESOURCES
from ..models.community import NP, PI, Community

LIMIT_LABELS = {
    "temperature": ("temperature", "درجة الحرارة"), "pH": ("pH (acidity)", "الحموضة"),
    "oxygen": ("oxygen", "الأكسجين"), "food": ("not enough food", "قلة الغذاء"),
    "prey": ("not enough prey", "قلة الفرائس"), "nitrogen": ("nitrogen", "النيتروجين"),
    "light": ("light", "الضوء"), "nothing": ("nothing in particular — near its best conditions",
                                             "لا شيء تحديداً – قريب من ظروفه المثلى"), "ammonia": ("ammonia", "الأمونيا"), "absent": ("it is gone", "اختفى"),
}
ASSUMPTIONS = [
    ("The vessel is perfectly mixed: no biofilm, no clumps, no surfaces (except the 'prey refuge').",
     "الوعاء ممزوج تماماً: لا أغشية حيوية ولا تكتلات ولا أسطح (عدا ملجأ الفرائس)."),
    ("Organic matter is lumped into five pools (polymers, sugars, lactate, acetate, ethanol); real media are richer.",
     "المواد العضوية مختصرة في خمسة مخزونات (بوليمرات، سكريات، لاكتات، أسيتات، إيثانول)، والأوساط الحقيقية أغنى."),
    ("Salinity, vitamins, trace metals, phosphorus and silicate are not modelled.",
     "الملوحة والفيتامينات والمعادن النادرة والفوسفور والسيليكات غير ممثلة."),
    ("No antibiotics, bacteriocins, phages, sporulation, dormancy or evolution.",
     "لا مضادات حيوية ولا باكتريوسينات ولا فيروسات ولا تبوغ ولا سكون ولا تطور."),
    ("Grazing depends only on prey size; real grazers also select by shape, taste and toxicity.",
     "الرعي يعتمد على الحجم فقط، بينما الرعاة الحقيقيون ينتقون حسب الشكل والطعم والسمية."),
    ("Traits come from the organism database: typical textbook values, not calibrated to a dataset.",
     "الصفات مأخوذة من قاعدة بيانات الكائنات: قيم نموذجية من الكتب، وغير معايرة على بيانات حقيقية."),
]
MEASUREMENTS = [
    ("Plate counts on selective media for each organism (CFU/mL) at several time points.",
     "العد على أطباق انتقائية لكل كائن (وحدة مستعمرة/مل) في أوقات متعددة."),
    ("pH with a calibrated probe — the fastest and cheapest signal to compare with the model.",
     "قياس الحموضة بمسبار معاير – أسرع وأرخص إشارة تقارنها بالنموذج."),
    ("Dissolved oxygen with a probe, especially in sealed or photosynthetic vessels.",
     "قياس الأكسجين الذائب بمسبار، خصوصاً في الأوعية المغلقة أو التي فيها بناء ضوئي."),
    ("Substrates and acids by HPLC or enzymatic kits (glucose, lactate, acetate, ethanol).",
     "قياس الركائز والأحماض بجهاز HPLC أو عدد إنزيمية (جلوكوز، لاكتات، أسيتات، إيثانول)."),
    ("Run each organism ALONE as well as together — that is exactly what the interaction table compares.",
     "شغّل كل كائن لوحده وأيضاً مع غيره – وهذا بالضبط ما يقارنه جدول التفاعلات."),
]


def summarise(model: Community, traj) -> dict:
    p = traj.config.parameters
    ph = model.ph_series(traj)
    end = traj.y[-1]
    out = {"final_pH": float(ph[-1]), "min_pH": float(ph.min()), "final_o2": float(end[PI["o2"]]),
           "organisms": {}, "resources": {k: float(end[PI[k]]) for k in ("poly", "sug", "lac", "ace", "eth", "nh4")}}
    for i, o in enumerate(model.orgs):
        x = traj.y[:, NP + i]
        out["organisms"][o.key] = {"final": float(x[-1]), "peak": float(x.max()),
                                   "peak_time": float(traj.t[int(np.argmax(x))]),
                                   "survived": bool(x[-1] > 0.1 and x[-1] > 0.02 * max(x.max(), 1e-9))}
    return out


def outcome(model: Community, traj) -> tuple[str, str]:
    s = summarise(model, traj)
    alive = [o for o in model.orgs if s["organisms"][o.key]["survived"]]
    gone = [o for o in model.orgs if not s["organisms"][o.key]["survived"]]
    nm = (lambda o: o.name_ar) if is_ar() else (lambda o: o.name.split(" subsp.")[0])
    if not alive:
        return (L("Everything died", "ماتت كل الكائنات"), "#f85149")
    winner = max(alive, key=lambda o: s["organisms"][o.key]["final"])
    ph = s["final_pH"]
    bits = [L(f"{nm(winner)} dominates", f"{nm(winner)} هو المسيطر")]
    if len(alive) > 1:
        bits.append(L(f"{len(alive)} of {len(model.orgs)} coexist", f"{len(alive)} من {len(model.orgs)} تتعايش"))
    if gone:
        bits.append(L(f"{', '.join(nm(o) for o in gone)} died out",
                      f"اختفى {'، '.join(nm(o) for o in gone)}"))
    bits.append(L(f"final pH {ph:.2f}", f"الحموضة النهائية {ph:.2f}"))
    if all(s["organisms"][o.key]["final"] < 0.3 * s["organisms"][o.key]["peak"] for o in alive):
        bits.append(L("all declining — the food has run out", "الجميع في تراجع – نفد الغذاء"))
    colour = "#3fb950" if len(alive) == len(model.orgs) else ("#d29922" if alive else "#f85149")
    return (" · ".join(bits), colour)


def to_html(model: Community, traj, idx: int, extra=None) -> str:
    e = html.escape
    sens, inter = (extra or (None, None)) if isinstance(extra, tuple) else (extra, None)
    p = traj.config.parameters
    y = traj.y[idx]
    time = float(traj.t[idx])
    f = model.factors(y, p)
    det = model.details(y, p)
    s = summarise(model, traj)
    nm = (lambda o: o.name_ar) if is_ar() else (lambda o: o.name)
    out = [f"<h3>{L('State at', 'الحالة عند')} t = {time:.1f} {L('h', 'ساعة')}</h3>",
           f"<p style='color:#d29922'><b>{t('status')}:</b> {e(t('exploratory'))}</p>"]

    # --- environment now
    out.append(f"<h4>{t('environment')}</h4><ul>")
    out.append(L(f"<li>pH <b>{f['pH']:.2f}</b> (started at {p['ph_base']:.1f}), dissolved oxygen "
                 f"<b>{y[PI['o2']]:.2f} mg/L</b>, temperature {p['T']:.0f} °C, light {p['light']:.1f}×.</li>",
                 f"<li>الحموضة <b>{f['pH']:.2f}</b> (بدأت من {p['ph_base']:.1f})، الأكسجين الذائب "
                 f"<b>{y[PI['o2']]:.2f} ملغم/ل</b>، الحرارة {p['T']:.0f} مئوية، الضوء {p['light']:.1f}×.</li>"))
    pools = ", ".join(f"{L(RESOURCES[k][0], RESOURCES[k][1])} {y[PI[k]]:.0f}"
                      for k in ("poly", "sug", "lac", "ace", "eth", "nh4"))
    out.append(f"<li>{L('Resources (mg/L)', 'الموارد (ملغم/ل)')}: {e(pools)}.</li></ul>")

    # --- each organism
    out.append(f"<h4>{t('now')}</h4><ul>")
    for i, d in enumerate(det):
        o = d["org"]
        bio = y[NP + i]
        mu = d["mu"]
        lim = LIMIT_LABELS.get(d["limiting"], (d["limiting"], d["limiting"]))
        limtxt = L(lim[0], lim[1])
        if bio < 0.01:
            out.append(L(f"<li><b style='color:{o.colour}'>{e(nm(o))}</b>: effectively gone ({bio:.3g} mg/L).</li>",
                         f"<li><b style='color:{o.colour}'>{e(nm(o))}</b>: اختفى تقريباً ({bio:.3g} ملغم/ل).</li>"))
            continue
        if mu > 1e-5:
            dbl = np.log(2) / mu
            grow = L(f"growing at µ = {mu:.3f}/h (doubles every {dbl:.1f} h)",
                     f"ينمو بمعدل µ = {mu:.3f}/ساعة (يتضاعف كل {dbl:.1f} ساعة)")
        else:
            grow = L("not growing", "لا ينمو")
        fo = f["per_org"][i]
        detail = L(f"temperature factor {fo['fT']:.2f}, pH factor {fo['fpH']:.2f}, oxygen factor {fo['fO2']:.2f}",
                   f"معامل الحرارة {fo['fT']:.2f}، معامل الحموضة {fo['fpH']:.2f}، معامل الأكسجين {fo['fO2']:.2f}")
        line = (f"<li><b style='color:{o.colour}'>{e(nm(o))}</b> — {bio:.2f} mg/L, {grow}. "
                f"{L('Most limiting', 'العامل الأكثر تقييداً')}: <b>{e(limtxt)}</b>. <span style='color:#8b949e'>{e(detail)}</span>")
        if d.get("uptake"):
            up = ", ".join(f"{L(RESOURCES[k][0], RESOURCES[k][1])} {v:.2f}" for k, v in d["uptake"].items() if v > 1e-6)
            if up:
                line += f"<br>&nbsp;&nbsp;{L('eats', 'يأكل')} (mg/L/h): {e(up)}"
        if d.get("prey"):
            pr = ", ".join(f"{e(nm(model.orgs[[q.key for q in model.orgs].index(k)]))} {v:.2f}"
                           for k, v in d["prey"].items() if v > 1e-6)
            if pr:
                line += f"<br>&nbsp;&nbsp;{L('eats', 'يأكل')} (mg/L/h): {pr}"
        if d.get("hydrolysis"):
            line += f"<br>&nbsp;&nbsp;{L('breaks down polymers', 'يحلل البوليمرات')}: {d['hydrolysis']:.2f} mg/L/h"
        if o.products:
            prods = ", ".join(L(RESOURCES[k][0], RESOURCES[k][1]) for k in o.products)
            line += f"<br>&nbsp;&nbsp;{L('releases', 'يطلق')}: {e(prods)}"
        out.append(line + "</li>")
    out.append("</ul>")

    # --- outcome
    out.append(f"<h4>{t('outcome')}</h4><ul>")
    for o in model.orgs:
        st = s["organisms"][o.key]
        verdict = L("survives", "ينجو") if st["survived"] else L("dies out", "يختفي")
        out.append(f"<li><b style='color:{o.colour}'>{e(nm(o))}</b>: {verdict} — "
                   + L(f"peak {st['peak']:.1f} mg/L at {st['peak_time']:.0f} h, final {st['final']:.2f} mg/L",
                       f"الذروة {st['peak']:.1f} ملغم/ل عند {st['peak_time']:.0f} ساعة، والنهاية {st['final']:.2f} ملغم/ل")
                   + "</li>")
    out.append(L(f"<li>pH ends at {s['final_pH']:.2f} (lowest {s['min_pH']:.2f}); oxygen ends at {s['final_o2']:.2f} mg/L.</li>",
                 f"<li>الحموضة تنتهي عند {s['final_pH']:.2f} (أدنى قيمة {s['min_pH']:.2f})، والأكسجين {s['final_o2']:.2f} ملغم/ل.</li>"))
    out.append("</ul>")

    # --- interactions
    if inter:
        out.append(f"<h4>{t('interactions')}</h4>"
                   + L("<p style='color:#8b949e'>Measured by re-running each organism alone and each pair together, "
                       "then comparing the final biomass. Numbers are log₁₀ ratios: +1 means ten times more.</p>",
                       "<p style='color:#8b949e'>تُقاس بإعادة تشغيل كل كائن لوحده وكل زوج معاً، ثم مقارنة الكتلة "
                       "النهائية. الأرقام لوغاريتمية: ‎+1 تعني عشرة أضعاف.</p>"))
        for it in inter:
            A = next(o for o in model.orgs if o.key == it.a)
            B = next(o for o in model.orgs if o.key == it.b)
            out.append(f"<p><b style='color:{it.colour}'>{e(L(it.kind, it.kind_ar))}</b> — "
                       f"<span style='color:{A.colour}'>{e(nm(A))}</span> ↔ "
                       f"<span style='color:{B.colour}'>{e(nm(B))}</span><br>")
            out.append(L(f"Effect on {e(nm(A))}: {it.effect_of_b_on_a:+.2f}",
                         f"الأثر على {e(nm(A))}: {it.effect_of_b_on_a:+.2f}") + "<br>")
            for en, ar in it.why_a:
                out.append(f"&nbsp;&nbsp;• {e(L(en, ar))}<br>")
            out.append(L(f"Effect on {e(nm(B))}: {it.effect_of_a_on_b:+.2f}",
                         f"الأثر على {e(nm(B))}: {it.effect_of_a_on_b:+.2f}") + "<br>")
            for en, ar in it.why_b:
                out.append(f"&nbsp;&nbsp;• {e(L(en, ar))}<br>")
            out.append("</p>")
    else:
        out.append(f"<h4>{t('interactions')}</h4>"
                   + L("<p>Press <b>Measure interactions</b> to find out how each pair affects the other.</p>",
                       "<p>اضغط <b>قياس التفاعلات</b> لمعرفة كيف يؤثر كل زوج على الآخر.</p>"))

    if sens:
        out.append(f"<h4>{t('sensitivity')}</h4><table cellpadding=2>")
        for x in sens[:10]:
            out.append(f"<tr><td>{e(x.symbol)}</td><td align=right>{x.value:+.2f}</td></tr>")
        out.append("</table>")

    out.append(f"<h4>{t('assumptions')}</h4><ul>" + "".join(f"<li>{e(L(a, b))}</li>" for a, b in ASSUMPTIONS) + "</ul>")
    out.append(f"<h4>{t('measure')}</h4><ul>" + "".join(f"<li>{e(L(a, b))}</li>" for a, b in MEASUREMENTS) + "</ul>")
    return rtl("\n".join(out))
