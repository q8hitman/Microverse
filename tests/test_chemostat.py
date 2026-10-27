"""Verification tests for the computational core.

These check that the code solves the stated equations correctly (verification).
They say nothing about whether the equations describe real chemostats (validation).
"""
import sqlite3
from dataclasses import replace

import numpy as np
import pytest

from microverse.analysis.explain import explain, to_html
from microverse.analysis.regimes import oscillation_period, scan_dilution
from microverse.analysis.sensitivity import elasticities
from microverse.analysis.stability import classify
from microverse.core.scheduler import make_config, run
from microverse.core.trajectory import RunConfig
from microverse.data import db
from microverse.io import experiment
from microverse.models.chemostat_rotifer import ChemostatRotifer
from microverse.viz.scene import MicroscopeScene

M = ChemostatRotifer()


def P(**kw):
    return M.default_parameters().updated(**kw).values()


def test_flux_terms_sum_to_rhs():
    rng = np.random.default_rng(1)
    for _ in range(20):
        y = rng.uniform(0, 80, 4)
        y[2] = min(y[2], y[3])
        p = P(delta=float(rng.uniform(0.05, 2.0)))
        f = M.rhs(0, y, p)
        sums = {s.symbol: 0.0 for s in M.state_vars}
        for ft in M.flux_terms(y, p):
            sums[ft.target] += ft.value
        assert np.allclose([sums[s.symbol] for s in M.state_vars], f, rtol=1e-12, atol=1e-12)


def test_analytic_jacobian_matches_finite_difference():
    y = np.array([10.0, 20.0, 2.0, 5.0])
    p = P(delta=0.6)
    J = M.jacobian(y, p)
    Jfd = super(ChemostatRotifer, M).jacobian(y, p)
    assert np.allclose(J, Jfd, rtol=1e-4, atol=1e-5)


@pytest.mark.parametrize("delta", [0.2, 0.8, 1.5, 2.5])
def test_algae_only_equilibrium_is_reached(delta):
    cfg = make_config(M, t_end=300, delta=delta, initial_state=[80, 5, 0, 0])
    tr = run(M, cfg)
    eq = M.algae_only_equilibrium(cfg.parameters)
    assert np.allclose(tr.y[-1], eq, rtol=1e-4, atol=1e-6)
    # Nitrogen mass balance without rotifers: N + C -> Ni
    assert tr.y[-1, 0] + tr.y[-1, 1] == pytest.approx(cfg.parameters["Ni"], rel=1e-5)


def test_washout_threshold():
    p = P()
    dc = M.washout_threshold(p)
    assert dc == pytest.approx(3.3 * 80 / 84.3)
    above = make_config(M, t_end=200, delta=min(dc + 0.1, 3.5), initial_state=[80, 5, 0, 0])
    assert run(M, above).y[-1, 1] < 1e-3
    assert classify(M, above.parameters).key == "washout"


def test_coexistence_equilibrium_is_a_fixed_point():
    for d in [0.1, 0.5, 1.0, 1.3]:
        p = P(delta=d)
        eq = M.coexistence_equilibrium(p)
        assert eq is not None and np.all(eq > 0)
        assert np.allclose(M.rhs(0, eq, p), 0, atol=1e-9)


def test_stable_regime_converges_to_predicted_equilibrium():
    cfg = make_config(M, t_end=1500, dt_out=1.0, delta=1.2)
    tr = run(M, cfg)
    r = classify(M, cfg.parameters)
    assert r.key in ("stable_equilibrium", "damped_oscillation")
    assert np.allclose(tr.y[-1], r.equilibrium, rtol=1e-3)


def test_unstable_regime_produces_sustained_cycles():
    cfg = make_config(M, t_end=800, dt_out=0.25, delta=0.5)
    tr = run(M, cfg)
    assert classify(M, cfg.parameters).key == "limit_cycle"
    tail = tr.series("C")[len(tr.t) // 2:]
    assert np.ptp(tail) > 10            # does not settle
    per = oscillation_period(tr.t, tr.series("C"))
    assert per is not None and 3 < per < 40


def test_rotifers_extinct_when_they_cannot_recruit_fast_enough():
    cfg = make_config(M, t_end=600, delta=1.8)
    assert classify(M, cfg.parameters).key == "rotifers_extinct"
    assert run(M, cfg).y[-1, 3] < 1e-3


def test_deterministic_runs_are_reproducible_and_hash_is_stable():
    cfg = make_config(M, t_end=100, delta=0.5)
    a, b = run(M, cfg), run(M, cfg)
    assert np.array_equal(a.y, b.y)
    assert cfg.hash() == RunConfig.from_dict(cfg.to_dict()).hash()
    assert cfg.hash() != replace(cfg, seed=1).hash()


def test_stochastic_seed_reproducibility():
    cfg = make_config(M, t_end=20, dt_out=0.5, mode="stochastic", seed=42, volume_ml=5)
    a, b = run(M, cfg), run(M, cfg)
    assert np.array_equal(a.y, b.y)
    c = run(M, replace(cfg, seed=43))
    assert not np.array_equal(a.y, c.y)


def test_stochastic_extinction_is_exact_and_reported():
    # tiny vessel: a handful of rotifers, deep troughs -> extinction is likely for some seed
    for seed in range(10):
        tr = run(M, make_config(M, t_end=150, dt_out=0.5, delta=0.5, mode="stochastic", seed=seed, volume_ml=2))
        if tr.y[-1, 3] == 0.0:
            assert tr.y[-1, 2] == 0.0
            assert any("B reached zero" in e for e in tr.events)
            return
    pytest.fail("no extinction in 10 replicates of a 2 mL vessel")


def test_stochastic_mean_approaches_deterministic_in_large_volume():
    det = run(M, make_config(M, t_end=30, dt_out=1.0, delta=1.2))
    sto = run(M, make_config(M, t_end=30, dt_out=1.0, delta=1.2, mode="stochastic", seed=3, volume_ml=1e4))
    assert np.allclose(sto.y[-1], det.y[-1], rtol=0.05, atol=0.05)


def test_parameter_bounds_enforced():
    with pytest.raises(ValueError):
        M.default_parameters().updated(delta=-1)


def test_explanation_is_derived_from_numbers():
    tr = run(M, make_config(M, t_end=300, delta=0.5))
    ex = explain(M, tr, len(tr.t) - 1)
    assert ex.regime.key == "limit_cycle"
    for s, ts in ex.terms.items():
        assert sum(v for _, v, _ in ts) == pytest.approx(ex.rates[s], abs=1e-9)
    html = to_html(ex, M)
    assert "not biologically validated" in html


def test_sensitivity_signs_make_sense_in_stable_regime():
    cfg = make_config(M, t_end=1500, dt_out=1.0, delta=1.2)
    el = {e.symbol: e.value for e in elasticities(M, cfg, "B")}
    assert el["Ni"] > 0          # more nutrient supply -> more rotifers
    assert el["m"] < 0           # higher rotifer mortality -> fewer rotifers


def test_regime_scan_covers_qualitative_pattern():
    cfg = make_config(M)
    pts = scan_dilution(M, cfg, [0.1, 0.5, 1.4, 1.8, 3.3], t_end=600, tail_days=200)
    keys = [p.regime for p in pts]
    assert keys[1] == "limit_cycle"
    assert keys[3] == "rotifers_extinct" and keys[4] == "washout"
    assert pts[1].c_max - pts[1].c_min > 10 * (pts[0].c_max - pts[0].c_min + 1e-9)


def test_database_predictions_are_immutable(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    db.seed_model(con, M)
    cfg = make_config(M)
    pid = db.freeze_prediction(con, cfg, {"regime": "limit_cycle"}, "cycles at δ=0.5")
    assert db.verify_prediction(con, pid)
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE predictions SET summary_json='{}' WHERE id=?", (pid,))
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM predictions WHERE id=?", (pid,))
    n = con.execute("SELECT COUNT(*) FROM parameters WHERE model_id=?", (M.id,)).fetchone()[0]
    assert n == len(M.default_parameters().params)


def test_experiment_file_roundtrip_and_tamper_detection(tmp_path):
    cfg = make_config(M, delta=0.7, seed=5)
    f = tmp_path / "e.json"
    experiment.save(f, cfg, "test")
    assert experiment.load(f) == cfg
    f.write_text(f.read_text().replace('"seed": 5', '"seed": 6'))
    with pytest.raises(ValueError):
        experiment.load(f)


def test_renderer_reads_state_but_never_changes_it():
    tr = run(M, make_config(M, t_end=50, delta=0.5))
    before = tr.y.copy()
    scene = MicroscopeScene(M, seed=0)
    for i in range(0, len(tr.t), 10):
        scene.sync(tr, i, dt_real=0.05)
    assert np.array_equal(tr.y, before)
    # drawn counts follow the state (persistent agents settle on the expected value; see test_visualization)
    i = len(tr.t) - 1
    for _ in range(200):
        scene.sync(tr, i, dt_real=0.05)
    exp_alg, _ = scene.expected_counts(tr.y[i])
    assert abs(scene.tracks[0].pop.cells() - exp_alg) <= max(1.5, 0.1 * exp_alg)
