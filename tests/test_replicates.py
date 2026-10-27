"""Repeated stochastic runs: reproducible, sensible extinction statistics, correct confidence interval."""
import numpy as np
import pytest

from microverse.analysis.replicates import describe, run_replicates, wilson
from microverse.labs import get


def test_wilson_interval_known_values():
    lo, hi = wilson(0, 30)
    assert lo == 0.0 and 0.10 < hi < 0.13                # rule of three ≈ 0.1
    lo, hi = wilson(15, 30)
    assert lo == pytest.approx(0.332, abs=0.01) and hi == pytest.approx(0.668, abs=0.01)


def test_replicates_are_reproducible_and_summarised():
    lab = get("chemostat")
    sc = next(s for s in lab.scenarios if s.mode == "stochastic")
    cfg = lab.config(sc.overrides, mode="stochastic", seed=1, volume_ml=sc.volume_ml, t_end=60)
    a = run_replicates(lab.model, cfg, n=8)
    b = run_replicates(lab.model, cfg, n=8)
    assert np.array_equal(a.mean, b.mean) and a.extinct == b.extinct
    assert set(a.extinct) == {"C", "R", "B"}               # N is a dissolved pool
    assert np.all(a.lo <= a.mean + 1e-9) and np.all(a.mean <= a.hi + 1e-9)
    assert any("95% CI" in line for line in describe(a, {}, "d"))


def test_tiny_vessel_goes_extinct_more_often_than_large_one():
    lab = get("chemostat")
    small = run_replicates(lab.model, lab.config({"delta": 0.5}, mode="stochastic", seed=1, volume_ml=0.05, t_end=80), n=12)
    large = run_replicates(lab.model, lab.config({"delta": 0.5}, mode="stochastic", seed=1, volume_ml=50, t_end=80), n=12)
    assert small.extinct["B"] >= large.extinct["B"]
