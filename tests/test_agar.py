"""Virtual agar: nutrient never negative, colonies stay in the dish, morphology follows food and agar,
plate counts behave like real plate counts, deterministic for a seed."""
import numpy as np
import pytest

from microverse.agar.model import (AgarParams, Plating, dish_mask, fractal_dimension, radius_mm, simulate)


def test_fields_stay_physical_and_inside_the_dish():
    r = simulate(AgarParams(), Plating(mode="spot"), t_end=40, frames=10)
    outside = ~r.mask
    for f, n in zip(r.frames, r.nutrient):
        assert float(f.min()) >= 0 and float(n.min()) >= 0
        assert float(np.abs(f[outside]).max()) == 0
    assert r.nutrient[-1].astype(float).sum() < r.nutrient[0].astype(float).sum()   # food is eaten


def test_more_food_and_softer_agar_give_bigger_more_compact_colonies():
    poor = simulate(AgarParams(organism="bsubtilis", nutrient=0.4, softness=0.7), Plating(mode="spot"), 300, 5)
    rich = simulate(AgarParams(organism="bsubtilis", nutrient=2.0, softness=1.5), Plating(mode="spot"), 300, 5)
    assert radius_mm(rich, -1) > 2 * radius_mm(poor, -1)
    def fill(r):                                      # area ÷ area of the disc reaching the farthest tip
        z = r.frames[-1].astype(float) > 0.15
        ys, xs = np.nonzero(z)
        c = (z.shape[0] - 1) / 2
        return z.sum() / (np.pi * np.hypot(ys - c, xs - c).max() ** 2)
    assert fill(rich) > fill(poor)                     # the poor colony is branched: it fills less of its disc


def test_colonies_are_round_not_crosses():
    """The isotropic stencil: a compact colony's extent is similar along axes and diagonals."""
    r = simulate(AgarParams(organism="ecoli", nutrient=2.0, softness=1.5, heterogeneity=0.0), Plating(mode="spot"), 120, 3)
    z = r.frames[-1].astype(float) > 0.15
    c = (z.shape[0] - 1) / 2
    ys, xs = np.nonzero(z)
    d = np.hypot(ys - c, xs - c)
    ang = np.arctan2(ys - c, xs - c)
    axial = d[np.abs(np.sin(2 * ang)) < 0.2].max()
    diag = d[np.abs(np.cos(2 * ang)) < 0.2].max()
    assert 0.85 < axial / diag < 1.18


def test_plate_count_matches_the_dilution_formula():
    pl = Plating(density_cfu_ml=1.5e8, dilution_exp=6, volume_ml=0.1)        # 15 expected
    r = simulate(AgarParams(organism="llactis", seed=4), pl, t_end=30, frames=5)
    n, _ = r.counts(len(r.frames) - 1)
    assert n == r.started or abs(n - r.started) <= 2
    assert r.back_calculated_cfu(len(r.frames) - 1) == pytest.approx(n / (1e-6 * 0.1))


def test_crowded_plates_undercount():
    pl = Plating(density_cfu_ml=1e9, dilution_exp=6, volume_ml=0.5)         # 500 expected → merging
    r = simulate(AgarParams(organism="bsubtilis", nutrient=1.5, softness=1.5), pl, t_end=150, frames=4)
    n, _ = r.counts(len(r.frames) - 1)
    assert n < 0.8 * r.started


def test_started_colonies_follow_poisson():
    pl = Plating(density_cfu_ml=1e8, dilution_exp=6, volume_ml=0.1)         # mean 10
    starts = [simulate(AgarParams(seed=s, grid=60), pl, t_end=0.5, frames=1).started for s in range(40)]
    assert 7 < np.mean(starts) < 13 and np.var(starts) > 3


def test_deterministic_for_a_seed():
    a = simulate(AgarParams(seed=7), Plating(), 20, 4)
    b = simulate(AgarParams(seed=7), Plating(), 20, 4)
    assert all(np.array_equal(x, y) for x, y in zip(a.frames, b.frames))


def test_box_counting_dimension():
    yy, xx = np.mgrid[0:128, 0:128]
    disc = (xx - 64) ** 2 + (yy - 64) ** 2 < 50 ** 2
    assert fractal_dimension(disc) == pytest.approx(2.0, abs=0.15)
    line = np.zeros((128, 128), bool)
    line[64, 10:120] = True
    assert fractal_dimension(line) == pytest.approx(1.0, abs=0.15)
