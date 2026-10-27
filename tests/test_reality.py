"""Prediction vs Reality: CSV import, unit/timestamp validation, error metrics, immutability, reports."""
import json
import sqlite3

import numpy as np
import pytest

from microverse.analysis import reality as R
from microverse.core.scheduler import run
from microverse.data import db
from microverse.labs import community_lab, get


@pytest.fixture
def con(tmp_path):
    return db.connect(tmp_path / "t.sqlite")


def freeze(con, lab, overrides=None, hyp="test"):
    s = lab.scenarios[0]
    cfg = lab.config(overrides or s.overrides, mode=s.mode, seed=s.seed, volume_ml=s.volume_ml, t_end=s.t_end)
    tr = run(lab.model, cfg)
    summary = {"lab": lab.key, "scenario": s.key, "outcome": lab.outcome(tr)[0], **lab.summary(tr)}
    exp = db.save_experiment(con, hyp, cfg)
    return db.freeze_prediction(con, cfg, summary, hyp, exp), tr


def yog_obs():
    lab = get("yogurt")
    return lab, {o.key: o for o in R.observables_for(lab.model)}


# ---------------------------------------------------------------- reading files
def test_reads_semicolon_bom_and_comment_lines():
    t = R.read_table("﻿# my notes\ntime_h;pH;CFU\n0;6,6;1e6\n1;6,4;2e6\n", text=True)
    assert t.columns == ["time_h", "pH", "CFU"] and len(t.rows) == 2
    assert R.parse_number("6,6", decimal_comma=True) == pytest.approx(6.6)


def test_iso_timestamps_become_hours_since_first():
    t, probs = R.parse_time(["2026-10-27T08:00", "2026-10-27 09:30", "2026-10-27T12:00"], "datetime")
    assert not probs and np.allclose(t, [0, 1.5, 4.0])
    _, probs = R.parse_time(["08:00", "yesterday"], "datetime")
    assert len(probs) == 2


def test_time_units_convert():
    t, _ = R.parse_time(["0", "30", "90"], "min")
    assert np.allclose(t, [0, 0.5, 1.5])


def test_duplicate_column_names_are_rejected():
    with pytest.raises(ValueError):
        R.read_table("t,pH,pH\n0,6,6\n", text=True)


# ---------------------------------------------------------------- validation
def test_validation_catches_units_ranges_and_missing_values():
    lab, obs = yog_obs()
    table = R.read_table("t,pH,count\n0,6.6,1e6\n1,15,\n2,6.1,abc\n3,5.5,4e6\n", text=True)
    cm = R.ColumnMap("t", "h", {"pH": ("pH", "pH"), "count": ("st_cfu", "furlongs")})
    _series, errors, warnings = R.validate(table, cm, list(obs.values()), lab.model)
    assert any("outside the possible range" in e for e in errors)          # pH 15
    assert any("unit 'furlongs'" in e for e in errors)
    cm2 = R.ColumnMap("t", "h", {"count": ("st_cfu", "CFU/mL")})
    series, errors, warnings = R.validate(table, cm2, list(obs.values()), lab.model)
    assert not errors and any("skipped" in w for w in warnings)
    assert len(series[0].values) == 2


def test_log10_counts_are_converted():
    lab, obs = yog_obs()
    table = R.read_table("t,logcfu\n0,6\n2,7\n", text=True)
    series, errors, _ = R.validate(table, R.ColumnMap("t", "h", {"logcfu": ("st_cfu", "log10 CFU/mL")}),
                                   list(obs.values()), lab.model)
    assert not errors and np.allclose(series[0].values, [1e6, 1e7])


def test_infinite_and_overflowing_values_are_skipped_not_crashing():
    lab, obs = yog_obs()
    table = R.read_table("t,c,logc\n0,inf,6\n1,1e6,400\n2,2e6,7\n3,1e999,7.5\n", text=True)
    cm = R.ColumnMap("t", "h", {"c": ("st_cfu", "CFU/mL"), "logc": ("st_cfu", "log10 CFU/mL")})
    series, errors, warnings = R.validate(table, cm, list(obs.values()), lab.model)
    assert not errors
    assert all(np.isfinite(s.values).all() for s in series)
    assert [len(s.values) for s in series] == [2, 3]
    assert sum("skipped" in w for w in warnings) == 2


def test_unsorted_times_are_sorted_with_a_warning():
    lab, obs = yog_obs()
    table = R.read_table("t,pH\n2,6.0\n0,6.6\n1,6.4\n", text=True)
    series, errors, warnings = R.validate(table, R.ColumnMap("t", "h", {"pH": ("pH", "pH")}), list(obs.values()),
                                          lab.model)
    assert not errors and any("sorted" in w for w in warnings)
    assert np.all(np.diff(series[0].t_model) > 0) and series[0].values[0] == 6.6


def test_chemostat_times_in_hours_are_converted_to_days():
    lab = get("chemostat")
    obs = R.observables_for(lab.model)
    table = R.read_table("hours,algae\n0,1e5\n48,2e5\n", text=True)
    series, errors, _ = R.validate(table, R.ColumnMap("hours", "h", {"algae": ("algae_cells", "cells/mL")}), obs,
                                   lab.model)
    assert not errors and np.allclose(series[0].t_model, [0, 2])


# ---------------------------------------------------------------- metrics
def test_perfect_data_give_zero_error():
    lab, obs = yog_obs()
    tr = run(lab.model, lab.config({}))
    t = np.linspace(0.5, 6, 12)
    s = R.ObservedSeries("pH", "pH", "pH", t, R.predicted_at(tr, obs["pH"], t))
    m, _ = R.compare(tr, obs["pH"], s)
    assert m.rmse == pytest.approx(0, abs=1e-12) and m.bias == pytest.approx(0, abs=1e-12)
    assert m.r2 == pytest.approx(1.0)


def test_metrics_match_hand_calculation():
    lab, obs = yog_obs()
    tr = run(lab.model, lab.config({}))
    t = np.array([1.0, 2.0, 3.0, 4.0])
    pred = R.predicted_at(tr, obs["pH"], t)
    meas = pred + np.array([0.1, -0.1, 0.2, 0.0])
    m, _ = R.compare(tr, obs["pH"], R.ObservedSeries("pH", "pH", "pH", t, meas))
    res = pred - meas
    assert m.rmse == pytest.approx(np.sqrt(np.mean(res ** 2)))
    assert m.mae == pytest.approx(np.mean(np.abs(res)))
    assert m.bias == pytest.approx(np.mean(res))
    assert m.n == 4 and m.scale == "linear"


def test_counts_are_compared_on_a_log_scale():
    lab, obs = yog_obs()
    tr = run(lab.model, lab.config({}))
    t = np.array([1.0, 2.0, 3.0])
    meas = R.predicted_at(tr, obs["st_cfu"], t) * 10            # exactly one decade too high
    m, _ = R.compare(tr, obs["st_cfu"], R.ObservedSeries("st_cfu", "c", "CFU/mL", t, meas))
    assert m.scale == "log10" and m.bias == pytest.approx(-1.0) and m.rmse == pytest.approx(1.0)


def test_time_shift_is_detected_and_explained():
    lab, obs = yog_obs()
    tr = run(lab.model, lab.config({}))
    t = np.linspace(1, 7, 25)
    meas = R.predicted_at(tr, obs["pH"], t - 0.6)                 # reality lags the model by 0.6 h
    m, _ = R.compare(tr, obs["pH"], R.ObservedSeries("pH", "pH", "pH", t, meas))
    assert m.shift == pytest.approx(-0.6, abs=0.1)               # the model is EARLY
    text = " ".join(R.explain(m, obs["pH"], "h"))
    assert "EARLY" in text
    assert "متقدم" in " ".join(R.explain(m, obs["pH"], "h", ar=True))


def test_time_shift_cannot_win_by_dropping_points():
    """Every shift is scored on the same measurements: a flat prediction has no timing to correct."""
    lab, obs = yog_obs()
    tr = run(lab.model, lab.config({}))
    t = tr.t[(tr.t > tr.t[0]) & (tr.t < tr.t[-1])][::max(1, len(tr.t) // 8)][:6]
    meas = R.predicted_at(tr, obs["pH"], t)
    meas[0] += 1.0                                                # one awkward early point
    m, _ = R.compare(tr, obs["pH"], R.ObservedSeries("pH", "pH", "pH", t, meas))
    # the shifted error is computed on all points, so it cannot drop to ~0 by excluding the outlier
    assert m.rmse_shifted > 0.3


def test_points_beyond_the_simulation_are_reported():
    lab, obs = yog_obs()
    tr = run(lab.model, lab.config({}))
    t = np.array([1.0, 2.0, 50.0])
    m, _ = R.compare(tr, obs["pH"], R.ObservedSeries("pH", "pH", "pH", t, np.array([6.5, 6.3, 4.0])))
    assert m.outside == 1 and m.n == 2


# ---------------------------------------------------------------- frozen predictions
def test_frozen_prediction_is_resimulated_exactly(con):
    lab = get("yogurt")
    pid, tr = freeze(con, lab)
    fp = R.load_prediction(con, pid)
    assert fp.record_ok and fp.config_ok and not fp.version_note
    lab2, tr2 = R.resimulate(fp)
    assert lab2.model.id == lab.model.id and np.array_equal(tr.y, tr2.y)


def test_community_predictions_can_be_resimulated(con):
    lab = community_lab(("llactis", "lplantarum"), "vegetable")
    pid, tr = freeze(con, lab)
    _lab, tr2 = R.resimulate(R.load_prediction(con, pid))
    assert np.allclose(tr.y, tr2.y)


def test_saving_a_comparison_never_changes_the_prediction(con, tmp_path):
    lab = get("yogurt")
    pid, tr = freeze(con, lab)
    before = dict(con.execute("SELECT * FROM predictions WHERE id=?", (pid,)).fetchone())
    obs = {o.key: o for o in R.observables_for(lab.model)}
    t = np.linspace(0.5, 6, 8)
    csv_text = "time_h,pH\n" + "\n".join(f"{a:.3f},{b + 0.05:.4f}" for a, b in zip(t, R.predicted_at(tr, obs["pH"], t)))
    table = R.read_table(csv_text, text=True)
    cmap = R.ColumnMap("time_h", "h", {"pH": ("pH", "pH")})
    series, errors, _ = R.validate(table, cmap, list(obs.values()), lab.model)
    assert not errors
    fp = R.load_prediction(con, pid)
    lab2, tr2 = R.resimulate(fp)
    results = []
    for s in series:
        m, pred = R.compare(tr2, obs[s.key], s)
        results.append((obs[s.key], s, m, pred))
    path = R.save_report(con, fp, table, cmap, results, tmp_path / "reports", lab2, tr2)
    assert path.exists() and path.with_suffix(".json").exists()
    payload = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["metrics"][0]["bias"] == pytest.approx(-0.05, abs=1e-3)
    html = path.read_text(encoding="utf-8")
    assert "<svg" in html and "not modified" in html
    after = dict(con.execute("SELECT * FROM predictions WHERE id=?", (pid,)).fetchone())
    assert before == after and db.verify_prediction(con, pid)
    assert con.execute("SELECT COUNT(*) FROM observations WHERE prediction_id=?", (pid,)).fetchone()[0] == 8
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE predictions SET summary_json='{}' WHERE id=?", (pid,))
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM comparisons")


def test_tampered_prediction_is_detected(tmp_path):
    con = db.connect(tmp_path / "x.sqlite")
    lab = get("yogurt")
    pid, _ = freeze(con, lab)
    con.execute("DROP TRIGGER predictions_no_update")            # someone edits the file by hand
    con.execute("UPDATE predictions SET summary_json='{\"outcome\": \"edited\"}' WHERE id=?", (pid,))
    assert not R.load_prediction(con, pid).record_ok


def test_list_predictions(con):
    lab = get("yogurt")
    freeze(con, lab, hyp="first")
    freeze(con, lab, hyp="second")
    rows = R.list_predictions(con)
    assert [r["hypothesis"] for r in rows] == ["second", "first"] and rows[0]["has_config"]
