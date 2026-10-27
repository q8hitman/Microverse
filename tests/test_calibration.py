"""Calibration: fitted parameters, uncertainty warnings, and freezing the fit as a NEW prediction."""
import json

import numpy as np
import pytest

from microverse.analysis import calibration as C
from microverse.analysis import reality as R
from microverse.core.scheduler import run
from microverse.data import db
from microverse.labs import get


@pytest.fixture
def con(tmp_path):
    return db.connect(tmp_path / "t.sqlite")


def yog_base(t_end=10.0):
    lab = get("yogurt")
    return lab, lab.config({}, t_end=t_end)


def synthetic(lab, cfg, truth, noise=True, seed=3):
    """Measurements generated from `truth`, which may lie outside the allowed ranges on purpose."""
    tr = run(lab.model, C.with_parameters(lab.model, cfg, truth))
    obs = R.observables_for(lab.model)
    by = {o.key: o for o in obs}
    rng = np.random.default_rng(seed)
    t = np.arange(0, 0.95 * cfg.t_end, 0.5)
    ph = np.interp(t, tr.t, by["pH"].getter(tr)) + (rng.normal(0, 0.03, len(t)) if noise else 0)
    st = np.interp(t, tr.t, by["st_cfu"].getter(tr)) * (10 ** rng.normal(0, 0.1, len(t)) if noise else 1)
    return obs, [R.ObservedSeries("pH", "pH", "pH", t, ph), R.ObservedSeries("st_cfu", "st", "CFU/mL", t, st)], t, ph, st


def test_recovers_known_parameters_within_their_intervals():
    lab, cfg = yog_base()
    truth = {"muS": 2.0, "muL": 0.8, "alpha": 0.55}
    obs, series, *_ = synthetic(lab, cfg, truth)
    res = C.calibrate(lab.model, cfg, obs, series, list(truth))
    assert res.success and res.cost_end < res.cost_start
    for p in res.parameters:
        assert p.ci_low < truth[p.symbol] < p.ci_high, p
        assert not p.at_limit
    for (_o, _s, before), (_o2, _s2, after) in zip(res.before, res.after):
        assert after.rmse < before.rmse


def test_noise_free_fit_is_exact():
    lab, cfg = yog_base()
    obs, series, *_ = synthetic(lab, cfg, {"muS": 2.2}, noise=False)
    res = C.calibrate(lab.model, cfg, obs, series, ["muS"])
    assert res.parameters[0].value == pytest.approx(2.2, rel=1e-3)


def test_value_beyond_the_allowed_range_is_flagged():
    lab, cfg = yog_base()
    obs, series, *_ = synthetic(lab, cfg, {"muS": 6.0}, noise=False)      # allowed range ends at 4.0
    res = C.calibrate(lab.model, cfg, obs, series, ["muS"])
    assert res.parameters[0].at_limit and res.parameters[0].value == pytest.approx(4.0, rel=1e-2)
    assert any("limit" in w for w in res.warnings) and len(res.warnings_ar) == len(res.warnings)


def test_inoculum_fit_also_changes_the_initial_state():
    lab, cfg = yog_base()
    obs, series, *_ = synthetic(lab, cfg, {"XS0": 0.3}, noise=False)
    res = C.calibrate(lab.model, cfg, obs, series, ["XS0"])
    assert res.config.initial_state[0] == pytest.approx(res.parameters[0].value)
    assert res.parameters[0].value == pytest.approx(0.3, rel=1e-2)


def test_refuses_bad_requests():
    lab, cfg = yog_base()
    obs, series, *_ = synthetic(lab, cfg, {})
    with pytest.raises(ValueError):
        C.calibrate(lab.model, cfg, obs, series, [])
    with pytest.raises(ValueError):
        C.calibrate(lab.model, cfg, obs, series, ["muS", "muL", "alpha", "betaS", "betaL", "kP"])
    with pytest.raises(ValueError):
        C.calibrate(lab.model, cfg, obs, series, ["nope"])
    few = [R.ObservedSeries("pH", "pH", "pH", np.array([1.0, 2.0]), np.array([6.4, 6.0]))]
    with pytest.raises(ValueError, match="more"):
        C.calibrate(lab.model, cfg, obs, few, ["muS", "muL"])


def test_suggested_parameters_exist_in_each_model():
    for key in ("yogurt", "chemostat"):
        m = get(key).model
        assert C.suggested_parameters(m) and set(C.suggested_parameters(m)) <= set(m.default_parameters().params)


def test_freezing_creates_a_new_prediction_and_leaves_the_old_one(con):
    lab, cfg = yog_base()
    tr0 = run(lab.model, cfg)
    exp = db.save_experiment(con, "base", cfg)
    pid0 = db.freeze_prediction(con, cfg, {"lab": "yogurt", "scenario": "classic", "outcome": "x"}, "base", exp)
    row0 = dict(con.execute("SELECT * FROM predictions WHERE id=?", (pid0,)).fetchone())
    fp0 = R.load_prediction(con, pid0)

    obs, series, t, ph, st = synthetic(lab, cfg, {"muS": 2.0, "alpha": 0.55})
    csv = "time_h,pH,st\n" + "\n".join(f"{a},{b},{c}" for a, b, c in zip(t, ph, st))
    table = R.read_table(csv, text=True)
    cmap = R.ColumnMap("time_h", "h", {"pH": ("pH", "pH"), "st": ("st_cfu", "CFU/mL")})
    series2, errors, _ = R.validate(table, cmap, obs, lab.model)
    assert not errors
    res = C.calibrate(lab.model, fp0.config, obs, series2, ["muS", "alpha"])
    pid1 = C.freeze_calibrated(con, fp0, res, table, cmap, lab, "test on batch B")

    assert pid1 != pid0
    assert dict(con.execute("SELECT * FROM predictions WHERE id=?", (pid0,)).fetchone()) == row0
    fp1 = R.load_prediction(con, pid1)
    assert fp1.record_ok and fp1.config_ok
    cal = fp1.summary["calibration"]
    assert cal["from_prediction"] == pid0 and cal["sha256"] == table.sha256
    assert set(cal["fitted"]) == {"muS", "alpha"} and "calibrated" in fp1.summary["status"]
    # the new prediction re-simulates to the fitted curve, the old one to the original
    _lab, tr1 = R.resimulate(fp1)
    assert np.allclose(tr1.y, res.traj.y)
    assert np.allclose(R.resimulate(fp0)[1].y, tr0.y)
    # provenance rows
    rows = con.execute("SELECT symbol, evidence, model_version_id FROM parameters WHERE evidence='fitted'").fetchall()
    assert {r["symbol"] for r in rows} == {"muS", "alpha"}
    mv = con.execute("SELECT calibration_data FROM model_versions WHERE id=?", (rows[0]["model_version_id"],)).fetchone()
    assert json.loads(mv["calibration_data"])["sha256"] == table.sha256
    # comparing with the fitting file is flagged; a different file is not
    assert C.same_data_warning(fp1, table) and C.same_data_warning(fp1, table, ar=True)
    other = R.read_table(csv + "\n9.5,4.5,1e9", text=True)
    assert C.same_data_warning(fp1, other) is None
    assert C.same_data_warning(fp0, table) is None


def test_report_on_the_fitting_data_carries_the_warning(con, tmp_path):
    lab, cfg = yog_base()
    obs, series, t, ph, st = synthetic(lab, cfg, {"muS": 2.0})
    table = R.read_table("time_h,pH\n" + "\n".join(f"{a},{b}" for a, b in zip(t, ph)), text=True)
    cmap = R.ColumnMap("time_h", "h", {"pH": ("pH", "pH")})
    s2, _e, _w = R.validate(table, cmap, obs, lab.model)
    pid0 = db.freeze_prediction(con, cfg, {"lab": "yogurt", "scenario": "classic", "outcome": "x"}, "b",
                                db.save_experiment(con, "b", cfg))
    fp0 = R.load_prediction(con, pid0)
    res = C.calibrate(lab.model, cfg, obs, s2, ["muS"])
    fp1 = R.load_prediction(con, C.freeze_calibrated(con, fp0, res, table, cmap, lab))
    _lab, tr1 = R.resimulate(fp1)
    by = {o.key: o for o in obs}
    results = [(by["pH"], s2[0], *R.compare(tr1, by["pH"], s2[0]))]
    path = R.save_report(con, fp1, table, cmap, results, tmp_path, lab, tr1)
    assert "fit, not a test" in path.read_text(encoding="utf-8")
    assert "warning" in json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
