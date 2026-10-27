"""Lab 3 — Community Builder: pick any organisms and watch them interact."""
from __future__ import annotations

import numpy as np

from ..analysis import explain_community as ec
from ..models.community import NP, PI, Community
from .base import Lab, PlotPanel, Scenario, Series

# Preset communities. Each one is a question the simulation can answer.
PRESETS = [
    ("pond", ("chlorella", "tetrahymena", "brachionus"),
     "Pond food web: alga → ciliate → rotifer", "شبكة غذائية في بركة: طحلب ← هدبي ← دولاب",
     "Can three levels of a food web coexist, and do their numbers rise and fall in turn?",
     dict(poly0=0.0, sug0=0.0, nh40=60.0), 600.0),
    ("vegetable", ("llactis", "lplantarum"),
     "Pickle jar: acid succession", "مرطبان مخلل: تعاقب الحموضة",
     "Which lactic acid bacterium finishes the fermentation, and at what pH does each one stop?",
     dict(sug0=2000.0, buffer=5.0, aeration=0.0), 120.0),
    ("cheese", ("lbulgaricus", "pfreudenreichii"),
     "Swiss cheese: cross-feeding on lactate", "الجبن السويسري: تغذية تبادلية على اللاكتات",
     "Can one organism live on the waste product of another?",
     dict(sug0=0.0, poly0=2000.0, buffer=60.0, aeration=0.0, T=30.0), 200.0),
    ("vinegar", ("scerevisiae", "aaceti"),
     "Wine to vinegar: yeast and Acetobacter", "من النبيذ إلى الخل: خميرة وأسيتوباكتر",
     "Does adding the vinegar bacterium at the same time help or hurt?",
     dict(sug0=2000.0, aeration=6.0, T=30.0), 150.0),
    ("digester", ("lbulgaricus", "pfreudenreichii", "methanosarcina"),
     "Anaerobic digester: a three-step chain", "مخمّر لاهوائي: سلسلة من ثلاث خطوات",
     "Polymers → lactate → acetate → methane: does each organism depend on the one before it?",
     dict(sug0=1500.0, poly0=500.0, buffer=60.0, aeration=0.0, T=37.0), 300.0),
    ("sealed", ("chlorella", "pputida"),
     "Sealed jar: who supplies the oxygen?", "وعاء مغلق: من يوفّر الأكسجين؟",
     "In a closed vessel, can an alga keep an aerobic bacterium alive? What happens in the dark?",
     dict(sug0=400.0, poly0=0.0, aeration=0.0), 300.0),
    ("spoilage", ("ecoli", "bsubtilis", "llactis"),
     "Race for a rich medium", "سباق على وسط غني",
     "Three fast growers, one pot of sugar: who wins, and does the acid decide it?",
     dict(sug0=2000.0, poly0=500.0, aeration=2.0, T=30.0), 150.0),
    ("decomposer", ("aoryzae", "ecoli"),
     "Only polymers: who can open the food?", "بوليمرات فقط: من يفتح الغذاء؟",
     "With no free sugar, can a bacterium survive next to a mould that makes enzymes?",
     dict(sug0=0.0, poly0=2000.0, aeration=3.0, T=30.0), 150.0),
    ("nitrogen", ("chlorella", "azotobacter", "nitrosomonas"),
     "The nitrogen cycle in one vessel", "دورة النيتروجين في وعاء واحد",
     "Who competes for nitrogen, and who brings new nitrogen in?",
     dict(sug0=800.0, poly0=0.0, nh40=15.0), 400.0),
]
POOL_COLOURS = {"sug": "#3987e5", "poly": "#9085e9", "lac": "#d95926", "ace": "#199e70",
                "eth": "#e3b341", "nh4": "#79c0ff", "det": "#8b949e", "o2": "#58a6ff"}


def build(keys: tuple[str, ...], preset_key: str = "custom") -> Lab:
    m = Community(keys)
    orgs = m.orgs

    def scan_compute(lab, cfg, progress):
        """Temperature scan: final biomass of each organism from 5 to 50 °C."""
        temps = np.arange(5.0, 50.1, 2.5)
        rows = {o.key: [] for o in orgs}
        from ..core.scheduler import run
        from dataclasses import replace
        for i, T in enumerate(temps):
            c = replace(cfg, mode="deterministic", parameters={**cfg.parameters, "T": float(T)})
            c = lab.rebuild(c)
            tr = run(m, c)
            for j, o in enumerate(orgs):
                rows[o.key].append(float(np.mean(tr.y[-max(len(tr.t) // 10, 1):, NP + j])))
            progress(i + 1, len(temps))
        return (temps, rows)

    def scan_plot(plot, data, cfg):
        temps, rows = data
        plot.setLabel("bottom", "temperature", "°C")
        plot.setLabel("left", "final biomass (mg/L)")
        for o in orgs:
            plot.plot(temps, rows[o.key], pen={"color": o.colour, "width": 2}, symbol="o", symbolSize=6,
                      symbolBrush=o.colour, symbolPen=None, name=o.name.split(" subsp.")[0])
        return cfg.parameters["T"]

    org_series = tuple(Series(o.name.split(" subsp.")[0], (lambda t, k=f"X_{o.key}": t.series(k)), o.colour)
                       for o in orgs)
    res_series = tuple(Series(name, (lambda t, k=k: t.series(k)), POOL_COLOURS[k])
                       for k, name in [("sug", "sugars"), ("poly", "polymers"), ("lac", "lactate"),
                                       ("ace", "acetate"), ("eth", "ethanol"), ("nh4", "nitrogen")])

    title_en = "Community Builder"
    title_ar = "باني المجتمعات الميكروبية"
    scenarios = tuple(
        Scenario(k, en, ar, q, ov, t_end=te) for k, ks, en, ar, q, ov, te in PRESETS if ks == keys) or (
        Scenario("custom", "Your own community", "مجتمعك الخاص",
                 "Which organisms survive together, and how do they change each other?", {}, t_end=200.0),)

    return Lab(
        key="community",
        title=title_en, title_ar=title_ar,
        tagline="Choose any organisms and see how they really affect each other",
        tagline_ar="اختر أي كائنات وشوف كيف تؤثر على بعضها فعلاً",
        description=("You choose the organisms and the environment; the equations are built from each organism's "
                     "traits. Competition, predation, cross-feeding, acid inhibition and oxygen exchange all emerge "
                     "from the mechanisms — nothing is written in by hand. The interaction table is measured by "
                     "re-running each organism alone and each pair together."),
        status="Exploratory model · equations verified by tests · traits are textbook estimates · not validated",
        status_colour="#f0883e",
        model=m,
        organisms=keys,
        scenarios=scenarios,
        param_groups=(
            ("Environment you control", ("T", "light", "aeration", "ph_base", "buffer")),
            ("Food you add", ("poly0", "sug0", "nh40", "inoculum")),
            ("Vessel behaviour", ("dilution", "refuge", "det_rate", "mu_scale")),
        ),
        plots=(
            PlotPanel("Organisms", "biomass (mg/L)", org_series, log_y=False),
            PlotPanel("pH and oxygen", "pH  /  O₂ (mg/L)", (
                Series("pH", lambda t: m.ph_series(t), "#f0883e"),
                Series("oxygen (mg/L)", lambda t: t.series("o2"), "#58a6ff"),
            )),
            PlotPanel("Food and products", "mg/L", res_series),
        ),
        default_t_end=200.0, dt_out=0.25,
        explain_html=lambda tr, i, extra: ec.to_html(m, tr, i, extra),
        outcome=lambda tr: ec.outcome(m, tr),
        summary=lambda tr: ec.summarise(m, tr),
        sensitivity_metric=lambda tr: float(np.mean(tr.y[-max(len(tr.t) // 10, 1):, NP:].sum(axis=1))),
        sensitivity_label="total final biomass",
        make_scene=lambda seed: __import__("microverse.viz.community_scene", fromlist=["x"]).CommunityScene(m, seed),
        make_widget=lambda sc: __import__("microverse.ui.community_widget", fromlist=["x"]).CommunityWidget(sc),
        scan_title="Temperature scan",
        scan_info=("Final biomass of each organism after the same run at different incubation temperatures. "
                   "Where the curves cross, the winner of the community changes — a prediction you can test with "
                   "two incubators."),
        scan_compute=scan_compute, scan_plot=scan_plot,
        supports_stochastic=False, accent="#2dd4bf",
        initial_state=m.initial_state_from,
    )
