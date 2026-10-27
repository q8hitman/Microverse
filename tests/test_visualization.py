"""Verification of the v0.5 visual engine: persistent identities, biologically styled transitions,
continuous motion, time interpolation, pause/replay and performance.

These tests check the RULES of the picture. They do not prove that it looks right — that needs the
screenshots in screenshots/ (scripts/ui_smoke_v05.py) and a human eye.
"""
import math
import time

import numpy as np
import pytest

from microverse.core.scheduler import run
from microverse.labs import community_lab, get
from microverse.library.morphology import DIVISION, MOTILITY, SHAPES, SPECS, spec_for
from microverse.library.organisms import ORGANISMS
from microverse.viz.population import DIVIDING, ENTERING, LIVE, VisualPopulation

FPS_DT = 1 / 30


def lab_run(lab, idx=0):
    s = lab.scenarios[idx]
    cfg = lab.config(s.overrides, mode=s.mode, seed=s.seed, volume_ml=s.volume_ml, t_end=s.t_end)
    return run(lab.model, cfg)


def play(scene, tr, speed, t0=0.0, t1=None, dt=FPS_DT):
    """Generator of frames: yields after each scene.update at simulated time t."""
    t = t0
    t1 = tr.t[-1] if t1 is None else t1
    while t <= t1:
        scene.update(tr, t, dt)
        yield t
        t += speed * dt


def snapshot(scene):
    return {a.id: (i, a.x, a.y, a.parent, a.state, a.n) for i, tr in enumerate(scene.tracks) for a in tr.pop.agents}


LABS = [
    ("chemostat", lambda: get("chemostat"), 2.0),
    ("yogurt", lambda: get("yogurt"), 0.5),
    ("pond", lambda: community_lab(("chlorella", "tetrahymena", "brachionus"), "pond"), 1.0),
    ("pickle", lambda: community_lab(("llactis", "lplantarum"), "vegetable"), 3.0),
    ("mixed", lambda: community_lab(("ecoli", "scerevisiae", "aoryzae", "paramecium", "euglena"), "custom"), 2.0),
]


@pytest.fixture(scope="module", params=LABS, ids=[x[0] for x in LABS])
def played(request):
    name, make, speed = request.param
    lab = make()
    tr = lab_run(lab)
    return lab, tr, speed


def test_no_cell_ever_appears_without_a_parent(played):
    """The core fix: new drawn cells come from a division, or swim/drift in from the edge of the field."""
    lab, tr, speed = played
    scene = lab.make_scene(3)
    prev = None
    for _ in play(scene, tr, speed, t1=min(tr.t[-1], tr.t[-1] * 0.6)):
        cur = snapshot(scene)
        if prev is not None:
            for aid, (i, x, y, parent, state, _n) in cur.items():
                if aid not in prev:
                    assert parent >= 0 or state == ENTERING, f"orphan cell {aid} appeared in track {i}"
                    if parent >= 0 and state != ENTERING:
                        f = scene.panels[scene.tracks[i].panel]
                        par = next((v for k, v in prev.items() if k == parent), None)
                        if par is not None:                       # born next to its mother
                            assert math.hypot(x - par[1], y - par[2]) < max(f.width_um * 0.25,
                                                                           scene.tracks[i].spec.length_um * 3)
        prev = cur


def test_identities_persist_without_teleporting(played):
    lab, tr, speed = played
    scene = lab.make_scene(4)
    prev = None
    for _ in play(scene, tr, speed, t1=tr.t[-1] * 0.5):
        cur = snapshot(scene)
        if prev:
            for aid, (i, x, y, *_rest) in cur.items():
                just_divided = prev.get(aid, (0,) * 6)[4] == DIVIDING and cur[aid][4] != DIVIDING
                if aid in prev and not just_divided:          # a chain that just broke re-centres on its cells
                    f = scene.panels[scene.tracks[i].panel]
                    spec = scene.tracks[i].spec
                    step = math.hypot(x - prev[aid][1], y - prev[aid][2])
                    limit = max(spec.speed_um_s, spec.length_um * 3, f.width_um * 0.03) * FPS_DT * 3 + f.width_um * 0.04
                    assert step < limit, f"{scene.tracks[i].key} jumped {step:.1f} µm in one frame"
        prev = cur


def test_cells_stay_inside_the_field(played):
    lab, tr, speed = played
    scene = lab.make_scene(5)
    for _ in play(scene, tr, speed, t1=tr.t[-1] * 0.4):
        pass
    for tr_ in scene.tracks:
        f = scene.panels[tr_.panel]
        for a in tr_.pop.agents:
            if a.state in (LIVE, DIVIDING):
                assert -1e-6 <= a.x <= f.width_um + 1e-6 and -1e-6 <= a.y <= f.height_um + 1e-6


def test_drawn_counts_follow_the_model(played):
    """Drawn cells track density × field volume × the run's fixed sample factor."""
    lab, tr, speed = played
    scene = lab.make_scene(6)
    errs = []
    for _ in play(scene, tr, speed):
        for d, e in zip(scene.drawn_counts(), scene.expected_counts(scene.y)):
            errs.append(abs(d - e) / max(e, 5.0))
    assert np.median(errs) < 0.4


def test_sample_factor_is_fixed_for_a_run(played):
    lab, tr, speed = played
    scene = lab.make_scene(7)
    factors = None
    for _ in play(scene, tr, speed * 4):
        f = [t.concentration for t in scene.tracks]
        factors = factors or f
        assert f == factors


def test_pause_starts_no_new_biology_and_settles(played):
    lab, tr, speed = played
    scene = lab.make_scene(8)
    t_mid = tr.t[-1] * 0.5
    scene.update(tr, 0.0, FPS_DT)
    scene.update(tr, t_mid, FPS_DT)                     # a jump of the time slider
    for _ in range(int(10 / FPS_DT)):                   # paused: the view settles (≈1–4 s)
        scene.update(tr, t_mid, FPS_DT)
        busy = any(a.state != LIVE or a.tail_fade > 0 for t in scene.tracks for a in t.pop.agents)
        if not busy and all(abs(t.pop.cells() - t.target) < 0.75 for t in scene.tracks):
            break
    settled = scene.drawn_counts()
    for d, e in zip(settled, scene.expected_counts(scene.y)):
        assert abs(d - e) <= max(1.5, 0.1 * e)
    ids = set(snapshot(scene))
    events = [dict(t.pop.events) for t in scene.tracks]
    for _ in range(int(3 / FPS_DT)):                    # 3 more seconds paused: nothing is born or dies
        scene.update(tr, t_mid, FPS_DT)
    assert set(snapshot(scene)) == ids
    assert [t.pop.events for t in scene.tracks] == events


def test_replay_starts_from_a_fresh_sample_at_time_zero():
    lab = get("yogurt")
    tr = lab_run(lab)
    scene = lab.make_scene(1)
    for _ in play(scene, tr, 2.0):
        pass
    scene.replay(tr, 0.0)
    for d, e in zip(scene.drawn_counts(), scene.expected_counts(tr.y[0])):
        assert abs(d - e) <= 1.0


def test_renderer_never_changes_the_trajectory():
    lab = get("chemostat")
    tr = lab_run(lab)
    before = tr.y.copy()
    scene = lab.make_scene(1)
    for _ in play(scene, tr, 4.0, t1=40):
        pass
    assert np.array_equal(tr.y, before)


def test_visual_engine_is_deterministic_for_a_seed():
    lab = get("chemostat")
    tr = lab_run(lab)
    a, b = lab.make_scene(9), lab.make_scene(9)
    for _ in play(a, tr, 2.0, t1=20):
        pass
    for _ in play(b, tr, 2.0, t1=20):
        pass
    assert snapshot(a) == snapshot(b)


# ---------------------------------------------------------------- interpolation
def test_state_is_interpolated_between_output_rows():
    lab = get("chemostat")
    tr = lab_run(lab)
    j = 10
    mid = (tr.t[j] + tr.t[j + 1]) / 2
    assert np.allclose(tr.state_at(mid), (tr.y[j] + tr.y[j + 1]) / 2)
    assert np.allclose(tr.state_at(tr.t[j]), tr.y[j])
    assert np.allclose(tr.state_at(-5), tr.y[0]) and np.allclose(tr.state_at(1e9), tr.y[-1])


# ---------------------------------------------------------------- reproduction styles
@pytest.mark.parametrize("key", sorted(SPECS))
def test_each_division_style_keeps_the_mother_and_adds_daughters_nearby(key):
    spec = spec_for(key)
    pop = VisualPopulation(spec, 1000.0, 1000.0, seed=1)
    pop.seed(1)
    mother = pop.agents[0]
    mother.x, mother.y, mother.grow = 500.0, 500.0, 1.0
    before = pop.cells()
    for _ in range(400):                                  # ask for one more cell and let the division finish
        pop.step(before + 1, FPS_DT, True)
        if pop.cells() > before:
            break
    assert pop.cells() >= before + 1
    assert any(a.id == mother.id for a in pop.agents), "the mother keeps its identity"
    for a in pop.agents:
        if a.id != mother.id:
            assert a.parent == mother.id or a.parent == -1
            assert math.hypot(a.x - mother.x, a.y - mother.y) < spec.length_um * 4 + 60


def test_division_styles_differ_between_organism_groups():
    styles = {SPECS[k].division for k in ("ecoli", "sthermophilus", "scerevisiae", "chlorella", "aoryzae",
                                          "paramecium", "euglena", "navicula", "amoeba", "brachionus")}
    assert len(styles) >= 9


def test_diatom_daughters_get_slightly_smaller():
    pop = VisualPopulation(spec_for("navicula"), 1000, 1000, seed=2)
    pop.seed(1)
    m = pop.agents[0]
    m.grow, m.size = 1.0, 1.0
    for _ in range(400):
        pop.step(2, FPS_DT, True)
        if len(pop.agents) == 2:
            break
    child = next(a for a in pop.agents if a.id != m.id)
    assert child.size == pytest.approx(0.97)


def test_chains_lengthen_then_break():
    pop = VisualPopulation(spec_for("sthermophilus"), 50, 50, seed=3)
    pop.seed(2)
    for _ in range(3000):
        pop.step(40, FPS_DT, True)
    assert pop.cells() >= 38
    assert all(a.n <= spec_for("sthermophilus").max_chain for a in pop.agents)
    assert len(pop.agents) >= 4


# ---------------------------------------------------------------- movement
def test_motility_styles_are_distinct_and_continuous():
    speeds = {}
    for key in ("ecoli", "paramecium", "amoeba", "chlorella", "navicula", "vorticella", "aoryzae"):
        spec = spec_for(key)
        pop = VisualPopulation(spec, 5000, 5000, seed=4)
        pop.seed(1)
        a = pop.agents[0]
        a.x = a.y = 2500.0
        a.grow = 1.0
        path = []
        for _ in range(300):
            pop.step(1, FPS_DT, False)
            path.append((a.x, a.y))
        d = np.diff(np.array(path), axis=0)
        v = np.hypot(d[:, 0], d[:, 1]) / FPS_DT
        speeds[key] = float(np.median(v))
        assert v.max() < max(spec.speed_um_s * 3, 30), f"{key} moved discontinuously"
    assert speeds["paramecium"] > speeds["ecoli"] > speeds["amoeba"]
    assert speeds["vorticella"] == 0 and speeds["aoryzae"] == 0
    assert speeds["chlorella"] < 5                        # Brownian only


def test_run_and_tumble_reorients():
    pop = VisualPopulation(spec_for("ecoli"), 10000, 10000, seed=5)
    pop.seed(1)
    a = pop.agents[0]
    a.x = a.y = 5000.0
    headings = []
    for _ in range(900):                                  # 30 s
        pop.step(1, FPS_DT, False)
        headings.append(a.heading)
    turns = np.abs(np.diff(np.unwrap(headings)))
    assert (turns > 0.3).sum() >= 5                       # several tumbles in 30 s (≈1 per second expected)


# ---------------------------------------------------------------- morphology records
def test_every_organism_has_a_morphology_record():
    for key in ORGANISMS:
        assert key in SPECS, key
        s = SPECS[key]
        assert s.shape in SHAPES and s.motility in MOTILITY and s.division in DIVISION
        assert s.length_um >= s.width_um > 0
        assert s.reference


def test_shapes_are_not_all_generic():
    assert len({s.shape for s in SPECS.values()}) >= 12


# ---------------------------------------------------------------- performance
def test_scene_update_is_fast_enough_for_30_fps():
    lab = community_lab(("ecoli", "scerevisiae", "aoryzae", "paramecium", "euglena"), "custom")
    tr = lab_run(lab)
    scene = lab.make_scene(1)
    n, t0 = 0, time.perf_counter()
    for _ in play(scene, tr, 3.0):
        n += 1
    per_frame = (time.perf_counter() - t0) / n
    assert per_frame < 0.008, f"{per_frame * 1000:.1f} ms per frame"
