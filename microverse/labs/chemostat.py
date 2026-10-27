"""Lab 1 — Chemostat microcosm (algae, rotifers, nitrogen)."""
from __future__ import annotations

import numpy as np

from ..analysis.explain import explain, to_html
from ..analysis.regimes import oscillation_period, scan_dilution
from ..analysis.stability import classify
from ..i18n import L
from ..models.chemostat_rotifer import ChemostatRotifer
from .base import Lab, PlotPanel, Scenario, Series

# Categorical slots validated (adjacent pairs, dark surface) with the dataviz validator.
BLUE, AQUA, ORANGE, VIOLET = "#3987e5", "#199e70", "#d95926", "#9085e9"
REGIME_COLOURS = {"washout": "#8b949e", "rotifers_extinct": "#a371f7", "stable_equilibrium": "#3fb950",
                  "damped_oscillation": "#58a6ff", "limit_cycle": "#f85149"}
REGIME_LABELS = {"washout": "washout", "rotifers_extinct": "rotifers extinct", "stable_equilibrium": "stable",
                 "damped_oscillation": "damped oscillation", "limit_cycle": "cycles"}
REGIME_AR = {"washout": "غسل كامل: تختفي الطحالب والدوّارات",
             "rotifers_extinct": "تنقرض الدوّارات وتستقر الطحالب",
             "stable_equilibrium": "تعايش مستقر",
             "damped_oscillation": "تذبذب يخمد نحو تعايش مستقر",
             "limit_cycle": "دورات مفترس وفريسة"}


def build() -> Lab:
    m = ChemostatRotifer()

    def outcome(tr):
        r = classify(m, tr.config.parameters)
        if tr.config.mode == "stochastic" and tr.y[-1, 3] == 0 and r.key not in ("washout", "rotifers_extinct"):
            return (L("This replicate: rotifers went extinct by chance (demographic noise)",
                      "في هذه النسخة: انقرضت الدوّارات بالصدفة (ضجيج ديموغرافي)"), "#a371f7")
        return (L(r.label, REGIME_AR[r.key]), REGIME_COLOURS[r.key])

    def summary(tr):
        r = classify(m, tr.config.parameters)
        tail = tr.y[int(len(tr.t) * 0.6):]
        return {"regime": r.key, "regime_label": r.label, "reasoning": r.reasoning,
                "equilibrium": None if r.equilibrium is None else [float(x) for x in r.equilibrium],
                "simulated_period_d": oscillation_period(tr.t, tr.series("C")),
                "tail_range": {s: [float(tail[:, i].min()), float(tail[:, i].max())]
                               for i, s in enumerate(tr.state_symbols)}}

    def scan_compute(lab, cfg, progress):
        return scan_dilution(m, cfg, np.round(np.arange(0.05, 3.31, 0.05), 3), progress=progress)

    def scan_plot(plot, pts, cfg):
        plot.setLabel("bottom", "dilution rate δ", "1/d")
        plot.setLabel("left", "algae C, long-run min & max (µmol N/L)")
        for key, col in REGIME_COLOURS.items():
            sel = [p for p in pts if p.regime == key]
            if sel:
                d = [p.delta for p in sel]
                plot.plot(d, [p.c_max for p in sel], pen=None, symbol="t", symbolBrush=col, symbolPen=None,
                          symbolSize=9, name=f"{REGIME_LABELS[key]} (▼ max, ▲ min)")
                plot.plot(d, [p.c_min for p in sel], pen=None, symbol="t1", symbolBrush=col, symbolPen=None, symbolSize=9)
        return cfg.parameters["delta"]

    def scene(seed):
        from ..viz.scene import MicroscopeScene
        return MicroscopeScene(m, seed)

    def widget(sc):
        from ..ui.microscope_widget import MicroscopeWidget
        return MicroscopeWidget(sc)

    return Lab(
        key="chemostat",
        title="Chemostat Microcosm", title_ar="مختبر الكيموستات: طحالب ودوّارات",
        tagline="Predator–prey dynamics: nitrogen → green alga → rotifer",
        tagline_ar="ديناميكية المفترس والفريسة: نيتروجين ← طحلب ← دولاب",
        description=("A continuously diluted culture vessel. Chlorella takes up nitrogen; the rotifer Brachionus eats "
                     "Chlorella. Changing the dilution rate alone switches the system between steady coexistence, "
                     "predator–prey cycles and extinction — as observed in real chemostats "
                     "(Fussmann et al. 2000, Science)."),
        status="Mechanistic model · verified by tests · literature parameters pending source check · not validated",
        status_colour="#d29922",
        model=m,
        organisms=("chlorella", "brachionus"),
        scenarios=(
            Scenario("cycles", "Classic predator–prey cycles", "دورات المفترس والفريسة",
                     "At an intermediate dilution rate, do algae and rotifers oscillate instead of settling?",
                     {"delta": 0.5}),
            Scenario("low", "Slow dilution — damped oscillations", "تخفيف بطيء – تذبذب يخمد",
                     "With very slow medium exchange, do the oscillations die out?", {"delta": 0.1}, t_end=400),
            Scenario("stable", "Fast dilution — stable coexistence", "تخفيف سريع – تعايش مستقر",
                     "Near the rotifers' limit, do both species settle at a steady level?", {"delta": 1.35}, t_end=300),
            Scenario("extinct", "Rotifers cannot keep up", "الدوّارات ما تلحق",
                     "If the vessel is diluted faster than rotifers can reproduce, what happens to each species?",
                     {"delta": 1.8}),
            Scenario("washout", "Washout of everything", "غسل كامل للنظام",
                     "Above which dilution rate can even the algae not persist?", {"delta": 3.3}, t_end=60),
            Scenario("enrich", "Paradox of enrichment", "مفارقة الإثراء",
                     "Does adding more nutrient (Nᵢ = 160) destabilise a system that was stable?",
                     {"delta": 1.2, "Ni": 160.0}, t_end=300),
            Scenario("noise", "Small vessel — chance extinction", "وعاء صغير – انقراض بالصدفة",
                     "In a 5 mL vessel, can random births and deaths wipe out the rotifers during a cycle trough?",
                     {"delta": 0.5}, mode="stochastic", volume_ml=5.0),
        ),
        param_groups=(
            ("Vessel & medium (what the experimenter controls)", ("delta", "Ni")),
            ("Chlorella vulgaris (prey)", ("bC", "KC")),
            ("Brachionus calyciflorus (predator)", ("bB", "KB", "eps", "m", "lam")),
        ),
        plots=(PlotPanel("Populations and nutrient", "µmol N/L", (
            Series("N — dissolved nitrogen", lambda t: t.series("N"), BLUE),
            Series("C — Chlorella", lambda t: t.series("C"), AQUA),
            Series("B — all rotifers", lambda t: t.series("B"), ORANGE),
            Series("R — egg-bearing rotifers", lambda t: t.series("R"), VIOLET, dashed=True),
        )),),
        default_t_end=200.0, dt_out=0.1,
        explain_html=lambda tr, i, sens: to_html(explain(m, tr, i, sens), m),
        outcome=outcome, summary=summary,
        sensitivity_metric="B", sensitivity_label="long-run mean rotifer biomass",
        make_scene=scene, make_widget=widget,
        scan_title="Regime scan (δ)",
        scan_info=("Long-run algal minimum and maximum versus dilution rate δ (deterministic, last 300 of 800 days). "
                   "Colour = regime from linear stability analysis. Fussmann et al. (2000) ran this experiment in real "
                   "chemostats — compare the pattern, not exact numbers."),
        scan_compute=scan_compute, scan_plot=scan_plot,
        supports_stochastic=True, accent=AQUA,
    )
