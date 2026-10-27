"""Verification tests for the yoghurt model, the lab registry and the organism library."""
import numpy as np
import pytest

from microverse.analysis.explain_yogurt import milestones, time_to_end
from microverse.analysis.sensitivity import elasticities
from microverse.core.scheduler import run
from microverse.labs import all_labs, get
from microverse.library.organisms import ORGANISMS
from microverse.models.yogurt import (GAL_PER_LACTATE, LACTOSE_PER_LACTATE, PH0, Yogurt, cpm, ctmi, milk_ph)
from microverse.viz.yogurt_scene import YogurtScene

M = Yogurt()
LAB = get("yogurt")


def sim(t_end=12, **ov):
    return run(M, LAB.config(ov, t_end=t_end))


def test_cardinal_models():
    assert ctmi(42, 15, 42, 50) == pytest.approx(1.0)
    assert ctmi(14, 15, 42, 50) == 0 and ctmi(51, 15, 42, 50) == 0
    assert cpm(6.5, 4.3, 6.5) == pytest.approx(1.0)
    assert cpm(4.2, 4.3, 6.5) == 0


def test_milk_ph_curve():
    assert milk_ph(0) == pytest.approx(PH0, abs=1e-4)
    a = np.linspace(0, 20, 41)
    ph = [milk_ph(x) for x in a]
    assert all(np.diff(ph) < 0)                       # more acid -> lower pH
    assert milk_ph(7.0) == pytest.approx(4.6, abs=0.15)
    assert milk_ph(7.0, 1.4) > milk_ph(7.0, 1.0)     # stronger buffer resists acidification


def test_flux_terms_sum_to_rhs():
    rng = np.random.default_rng(0)
    p = M.default_parameters().values()
    for _ in range(20):
        y = np.array([rng.uniform(0, 20), rng.uniform(0, 20), rng.uniform(5, 47), rng.uniform(0, 10),
                      rng.uniform(0, 15), rng.uniform(0, 100), rng.uniform(0, 50)])
        sums = {s.symbol: 0.0 for s in M.state_vars}
        for ft in M.flux_terms(y, p):
            sums[ft.target] += ft.value
        assert np.allclose([sums[s.symbol] for s in M.state_vars], M.rhs(0, y, p), atol=1e-10)


def test_stoichiometry_of_lactose_galactose_lactate():
    tr = sim()
    used = tr.series("Lac")[0] - tr.series("Lac")[-1]
    lact = tr.series("A")[-1]
    assert used == pytest.approx(LACTOSE_PER_LACTATE * lact, rel=1e-5)
    assert tr.series("Gal")[-1] == pytest.approx(GAL_PER_LACTATE * lact, rel=1e-5)


def test_behaviour_protocooperation_speeds_acidification():
    """Model-behaviour check (not validation): the co-culture should acidify faster than either monoculture."""
    co = milestones(M, sim(t_end=24))["t_end_h"]
    st = milestones(M, sim(XL0=0.0, t_end=24))["t_end_h"]
    lb = milestones(M, sim(XS0=0.0, t_end=24))["t_end_h"]
    assert co is not None and st is not None
    assert co < st and (lb is None or co < lb)


def test_too_hot_fails_and_cardinal_limits_stop_growth():
    tr = sim(T=50.0)
    assert milestones(M, tr)["t_end_h"] is None
    assert tr.series("XS")[-1] == pytest.approx(tr.series("XS")[0])   # T = TmaxS -> no growth


def test_monoculture_partner_stays_absent():
    tr = sim(XL0=0.0)
    assert np.all(tr.series("XL") == 0)


def test_sensitivity_with_callable_metric():
    cfg = LAB.config({}, t_end=12)
    el = {e.symbol: e.value for e in elasticities(M, cfg, time_to_end(M), rebuild=LAB.rebuild)}
    assert el["muS"] < 0          # faster growth -> shorter time to pH 4.6
    assert el["buf"] > 0          # stronger buffering -> longer


def test_every_scenario_of_every_lab_runs_and_explains():
    for lab in all_labs():
        if lab.key == "community":
            continue          # covered in detail by tests/test_community.py
        assert set(lab.organisms) <= set(ORGANISMS)
        params = lab.model.default_parameters().params
        grouped = [s for _, syms in lab.param_groups for s in syms]
        assert set(grouped) == set(params), f"{lab.key}: every parameter must appear in exactly one group"
        assert len(grouped) == len(set(grouped))
        for sc in lab.scenarios:
            tr = run(lab.model, lab.config(sc.overrides, mode=sc.mode, seed=sc.seed, volume_ml=sc.volume_ml,
                                           t_end=sc.t_end))
            label, colour = lab.outcome(tr)
            assert label and colour.startswith("#")
            html = lab.explain_html(tr, len(tr.t) // 2, None)
            assert "validated" in html.lower() or "exploratory" in html.lower()
            for panel in lab.plots:
                for s in panel.series:
                    assert len(s.getter(tr)) == len(tr.t)


def test_yogurt_scene_reads_state_only():
    tr = sim()
    before = tr.y.copy()
    sc = YogurtScene(M, seed=0)
    i = tr.index_at(3.0)
    for _ in range(300):
        sc.sync(tr, i, 0.05)
    assert np.array_equal(tr.y, before)
    e_st, e_lb = sc.expected_counts(tr.y[i])
    assert abs(sc.st_cells() - e_st) <= max(1.5, 0.1 * e_st)
    assert abs(sc.tracks[1].pop.cells() - e_lb) <= max(1.5, 0.1 * e_lb)


def test_organisms_used_by_the_fixed_labs_are_mapped_to_model_variables():
    """The four organisms of the chemostat and yoghurt labs say which variable represents them."""
    for key in ("chlorella", "brachionus", "sthermophilus", "lbulgaricus"):
        o = ORGANISMS[key]
        assert o.model_variables and o.references


def test_peptide_pool_never_needs_clipping():
    """v1.1 fix: integrated WITHOUT the scheduler's clipping, peptides stay ≥ 0 in every scenario."""
    from scipy.integrate import solve_ivp
    from microverse.labs import get as get_lab
    lab = get_lab("yogurt")
    for s in lab.scenarios:
        cfg = lab.config(s.overrides, t_end=s.t_end)
        p = dict(cfg.parameters)
        sol = solve_ivp(lambda t, y: lab.model.rhs(t, y, p), (0, cfg.t_end), np.array(cfg.initial_state),
                        method="LSODA", rtol=1e-8, atol=1e-10)
        assert sol.y[5].min() > -1e-6, s.key
