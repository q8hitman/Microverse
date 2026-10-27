"""Lab 2 — Yoghurt fermentation (S. thermophilus + L. bulgaricus in milk)."""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..analysis import explain_yogurt as ey
from ..core.scheduler import run
from ..i18n import L
from ..models.yogurt import Yogurt
from .base import Lab, PlotPanel, Scenario, Series

BLUE, ORANGE, AQUA = "#3987e5", "#d95926", "#199e70"


def build() -> Lab:
    m = Yogurt()

    def outcome(tr):
        ms = ey.milestones(m, tr)
        if ms["t_end_h"] is None:
            return (L(f"pH 4.6 not reached in {tr.t[-1]:.0f} h (final pH {ms['final_pH']:.2f})",
                      f"لم تصل الحموضة إلى 4.6 خلال {tr.t[-1]:.0f} ساعة (الحموضة النهائية {ms['final_pH']:.2f})"),
                    "#f85149")
        over = ms["final_pH"] < 4.2
        extra = L(" · over-acidified (no cooling)", " · تحمّض زائد (بدون تبريد)") if over else ""
        return (L(f"Set yoghurt: pH 4.6 at {ms['t_end_h']:.1f} h · final pH {ms['final_pH']:.2f}{extra}",
                  f"لبن متماسك: الحموضة 4.6 عند {ms['t_end_h']:.1f} ساعة · النهائية {ms['final_pH']:.2f}{extra}"),
                "#d29922" if over else "#3fb950")

    def summary(tr):
        return {"milestones": ey.milestones(m, tr), "status": "exploratory prediction (not validated)"}

    temps = np.arange(30.0, 53.0, 1.0)

    def scan_compute(lab, cfg, progress):
        rows = []
        variants = [("co-culture", {}), ("S. thermophilus alone", {"XL0": 0.0}), ("L. bulgaricus alone", {"XS0": 0.0})]
        n = len(temps) * len(variants)
        k = 0
        for name, ov in variants:
            pts = []
            for T in temps:
                c = replace(cfg, mode="deterministic", t_end=24.0, dt_out=0.05,
                            parameters={**cfg.parameters, **ov, "T": float(T)})
                c = lab.rebuild(c)
                t_end = ey.milestones(m, run(m, c))["t_end_h"]
                pts.append(np.nan if t_end is None else t_end)
                k += 1
                progress(k, n)
            rows.append((name, pts))
        return rows

    def scan_plot(plot, rows, cfg):
        plot.setLabel("bottom", "incubation temperature", "°C")
        plot.setLabel("left", "time to reach pH 4.6 (h)  — gaps = never within 24 h")
        for (name, pts), col in zip(rows, (AQUA, BLUE, ORANGE)):
            plot.plot(temps, pts, pen={"color": col, "width": 2}, symbol="o", symbolSize=7, symbolBrush=col,
                      symbolPen=None, name=name, connect="finite")
        return cfg.parameters["T"]

    def scene(seed):
        from ..viz.yogurt_scene import YogurtScene
        return YogurtScene(m, seed)

    def widget(sc):
        from ..ui.yogurt_widget import YogurtWidget
        return YogurtWidget(sc)

    return Lab(
        key="yogurt",
        title="Yoghurt Fermentation", title_ar="مختبر تخمير اللبن (الزبادي)",
        tagline="Two bacteria that help each other turn milk into yoghurt",
        tagline_ar="بكتيريتان تساعدان بعض لتحويل الحليب إلى لبن",
        description=("Streptococcus thermophilus and Lactobacillus bulgaricus ferment lactose into lactic acid. "
                     "As the pH falls, casein proteins aggregate and the milk sets into a gel. The two species "
                     "stimulate each other (protocooperation): explore temperature, inoculum, monocultures, milk "
                     "buffering and post-acidification."),
        status="Exploratory model · equations verified · parameters illustrative (calibrate with your own pH curves)",
        status_colour="#f0883e",
        model=m,
        organisms=("sthermophilus", "lbulgaricus"),
        scenarios=(
            Scenario("classic", "Classic yoghurt at 43 °C", "لبن كلاسيكي على 43 درجة",
                     "With a 1:1 starter at 43 °C, how long until the milk sets at pH 4.6?", {}),
            Scenario("st_only", "S. thermophilus alone", "S. thermophilus لحاله",
                     "Without its partner, how much slower is acidification, and where does it stop?", {"XL0": 0.0}, t_end=16),
            Scenario("lb_only", "L. bulgaricus alone", "L. bulgaricus لحاله",
                     "Can the rod acidify milk on its own in a normal fermentation time?", {"XS0": 0.0}, t_end=16),
            Scenario("cool", "Cooler incubation (37 °C)", "حضانة أبرد (37 درجة)",
                     "What does a lower temperature do to timing and to the balance between the species?", {"T": 37.0}, t_end=12),
            Scenario("hot", "Too hot (50 °C)", "حرارة عالية (50 درجة)",
                     "Near the cardinal maximum, which organism fails first?", {"T": 50.0}, t_end=12),
            Scenario("post", "No cooling — post-acidification", "بدون تبريد – تحمّض زائد",
                     "If the yoghurt is left warm for 16 h, how sour does it become and who keeps acidifying?", {}, t_end=16),
            Scenario("fortified", "Milk fortified with solids", "حليب مدعّم بالمواد الصلبة",
                     "With stronger milk buffering (×1.4), how much longer to pH 4.6?", {"buf": 1.4}),
            Scenario("rods", "Rod-rich starter (1:5)", "بادئ غني بالعصيات (1:5)",
                     "Does changing the starter ratio change speed and final composition?", {"XS0": 0.02, "XL0": 0.1}),
        ),
        param_groups=(
            ("Process (what you control)", ("T", "XS0", "XL0", "Lac0", "buf")),
            ("Streptococcus thermophilus", ("muS", "ToptS", "TminS", "TmaxS", "pHminS", "aS", "yP", "yF", "betaS")),
            ("Lactobacillus bulgaricus", ("muL", "ToptL", "TminL", "TmaxL", "pHminL", "aL", "kP", "betaL")),
            ("Shared chemistry", ("alpha", "KP", "P0", "KF", "F0")),
        ),
        plots=(
            PlotPanel("Bacteria", "CFU/mL (log scale)", (
                Series("S. thermophilus", lambda t: t.series("XS") * 1e8, BLUE),
                Series("L. bulgaricus", lambda t: t.series("XL") * 1e8, ORANGE),
            ), log_y=True),
            PlotPanel("pH", "pH", (Series("pH of the milk", lambda t: m.ph_series(t), AQUA),),
                      ref_lines=((5.2, "gel onset"), (4.6, "end point"))),
            PlotPanel("Sugar and acid", "g/L", (
                Series("lactose", lambda t: t.series("Lac"), BLUE),
                Series("lactic acid", lambda t: t.series("A"), ORANGE),
                Series("galactose", lambda t: t.series("Gal"), AQUA),
            )),
        ),
        default_t_end=8.0, dt_out=0.02,
        explain_html=lambda tr, i, sens: ey.to_html(m, tr, i, sens),
        outcome=outcome, summary=summary,
        sensitivity_metric=ey.time_to_end(m), sensitivity_label="time to pH 4.6",
        make_scene=scene, make_widget=widget,
        scan_title="Temperature scan",
        scan_info=("Time to reach pH 4.6 versus incubation temperature for the co-culture and each species alone "
                   "(deterministic, up to 24 h). The gap between the curves is the model's estimate of the benefit of "
                   "protocooperation; the optimum comes from the cardinal temperature parameters."),
        scan_compute=scan_compute, scan_plot=scan_plot,
        supports_stochastic=False, accent=BLUE,
        initial_state=Yogurt.initial_state_from,
    )
