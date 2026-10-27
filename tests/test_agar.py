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
    poor = simulate(AgarParams(organism="bsubtilis", nutrient=0.4, softness=0.7, spot_res=1.0), Plating(mode="spot"), 100, 5)
    rich = simulate(AgarParams(organism="bsubtilis", nutrient=2.0, softness=1.5, spot_res=1.0), Plating(mode="spot"), 100, 5)
    assert radius_mm(rich, -1) > 2 * radius_mm(poor, -1)
    def fill(r):                                      # area ÷ area of the disc reaching the farthest tip
        z = r.frames[-1].astype(float) > 0.15
        ys, xs = np.nonzero(z)
        c = (z.shape[0] - 1) / 2
        return z.sum() / (np.pi * np.hypot(ys - c, xs - c).max() ** 2)
    assert fill(rich) > fill(poor)                     # the poor colony is branched: it fills less of its disc


def test_colonies_are_round_not_crosses():
    """The isotropic stencil: a compact colony's extent is similar along axes and diagonals."""
    r = simulate(AgarParams(organism="ecoli", nutrient=2.0, softness=1.5, heterogeneity=0.0, spot_res=1.0), Plating(mode="spot"), 120, 3)
    z = r.frames[-1].astype(float) > 0.15
    c = (z.shape[0] - 1) / 2
    ys, xs = np.nonzero(z)
    d = np.hypot(ys - c, xs - c)
    ang = np.arctan2(ys - c, xs - c)
    axial = d[np.abs(np.sin(2 * ang)) < 0.2].max()
    diag = d[np.abs(np.cos(2 * ang)) < 0.2].max()
    assert 0.85 < axial / diag < 1.18


def test_plate_count_matches_the_dilution_formula():
    pl = Plating(density_cfu_ml=6e7, dilution_exp=6, volume_ml=0.1)          # 6 expected: sparse plate
    r = simulate(AgarParams(organism="llactis", seed=4), pl, t_end=20, frames=5)
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


# ---------------------------------------------------------------- v0.5.1: two organisms, acid, finer spot grid
import dataclasses  # noqa: E402

import microverse.agar.model as M  # noqa: E402

OVERLAY = Plating(density_cfu_ml=3e9, dilution_exp=6, volume_ml=0.1, mix2=0.95, delay2_h=24)


def test_dish_wall_is_no_flux():
    m = dish_mask(50)
    f = np.random.default_rng(0).random((50, 50)) * m
    g = M._Grid(m, 0.7)
    assert abs(float(g.lap(f).sum())) < 1e-9                          # diffusion only moves material around
    assert abs(float(g.div_flux(f, f * 0.3 + m).sum())) < 1e-9


def test_finer_spot_grid_keeps_the_same_physics():
    a = simulate(AgarParams(organism="ecoli", spot_res=1.0), Plating(mode="spot"), 30, 2)
    b = simulate(AgarParams(organism="ecoli"), Plating(mode="spot"), 30, 2)
    assert b.grid == 240 and b.mm_per_cell == pytest.approx(90 / 240)
    # same colony within 20 % (the coarse grid smears the edge a little outwards)
    assert radius_mm(b, -1) == pytest.approx(radius_mm(a, -1), rel=0.2)


def test_only_lactic_acid_bacteria_make_acid_and_it_is_bounded():
    assert not simulate(AgarParams(organism="ecoli"), Plating(mode="spot"), 10, 2).acid
    r = simulate(AgarParams(organism="llactis"), Plating(mode="spot"), 24, 3)
    o = M.ORGANISMS["llactis"]
    top = float(r.acid[-1].max())
    assert 0 < top <= o.acid * M.NUTRIENT_SCALE * 1.01                # acid comes from food fermented
    c = r.grid // 2
    assert float(r.acid[-1][c, c]) > float(r.acid[-1][c, c + int(12 / r.mm_per_cell)])   # it spreads outwards


def test_two_organisms_are_planted_and_counted_separately():
    r = simulate(AgarParams(organism="ecoli", organism2="scerevisiae", seed=5),
                 Plating(density_cfu_ml=4e8, dilution_exp=6, volume_ml=0.1, mix2=0.5), 12, 2)
    assert 0 < r.started2 < r.started
    a, b = r.counts_by_species(len(r.frames) - 1)
    assert a + b == r.counts(len(r.frames) - 1)[0] and a > 0 and b > 0


def test_deferred_organism_appears_only_after_the_delay():
    r = simulate(AgarParams(organism="llactis", organism2="ecoli"), OVERLAY, 30, 10)
    before = [float(f.astype(float).sum()) for t, f in zip(r.times, r.frames2) if t < 24 - 1e-6]
    after = [float(f.astype(float).sum()) for t, f in zip(r.times, r.frames2) if t > 25]
    assert max(before) == 0 and min(after) > 0


_PLATES = {}


def _plate(org2, acid, buffering):
    """48 h overlay plate, cached: several tests compare the same plates."""
    key = (org2, acid, buffering)
    if key not in _PLATES:
        saved = M.ORGANISMS["llactis"]
        if not acid:
            M.ORGANISMS["llactis"] = dataclasses.replace(saved, acid=0.0)
        try:
            _PLATES[key] = simulate(AgarParams(organism="llactis", organism2=org2, seed=3, buffering=buffering),
                                    OVERLAY, 48, 2)
        finally:
            M.ORGANISMS["llactis"] = saved
    return _PLATES[key]


def _partner_in_acid_zone(org2="ecoli", acid=True, buffering=1.0):
    ref = _plate(org2, True, 1.0)
    lab = ref.frames[-1].astype(float) - ref.frames2[-1].astype(float)
    # the halo: acid has spread there in the normal plate, but no lactic colony grows there (so food use is the
    # same with or without acid)
    zone = (ref.acid[-1].astype(float) > 0.6) & (lab < 0.05) & ref.mask
    return float(_plate(org2, acid, buffering).frames2[-1].astype(float)[zone].mean())


def test_acid_from_lactic_bacteria_holds_back_a_sensitive_neighbour():
    with_acid = _partner_in_acid_zone()
    without = _partner_in_acid_zone(acid=False)
    buffered = _partner_in_acid_zone(buffering=4.0)
    assert with_acid < 0.8 * without                                   # same places, same food use: acid matters
    assert buffered > 1.15 * with_acid                                 # buffering the agar protects the neighbour


def test_acid_tolerant_yeast_is_held_back_less():
    rel = {}
    for org2 in ("ecoli", "scerevisiae"):
        rel[org2] = _partner_in_acid_zone(org2) / _partner_in_acid_zone(org2, acid=False)
    assert rel["scerevisiae"] > 0.95 > 0.8 > rel["ecoli"]


def test_fill_fraction_tells_round_from_lobed():
    rich = simulate(AgarParams(organism="ecoli", nutrient=2.0, softness=1.5, heterogeneity=0.0, spot_res=1.0),
                    Plating(mode="spot"), 40, 2)
    poor = simulate(AgarParams(organism="bsubtilis", nutrient=0.4, softness=0.7, spot_res=1.0), Plating(mode="spot"), 150, 2)
    assert M.fill_fraction(rich, -1) > 0.75                            # pixel edges keep a disc below 1
    assert M.fill_fraction(poor, -1) < M.fill_fraction(rich, -1) - 0.15
