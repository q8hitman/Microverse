"""Verification tests for the organism database, the community model and the interaction analysis."""
import numpy as np
import pytest

from microverse import i18n
from microverse.analysis import explain_community as ec
from microverse.analysis.interactions import THRESHOLD, analyse
from microverse.core.parameters import Evidence
from microverse.core.scheduler import run
from microverse.labs import all_labs, community_lab
from microverse.labs.community import PRESETS
from microverse.library.organisms import ORGANISMS, RESOURCES, by_group
from microverse.models.community import NP, PI, Community, cpm, ctmi, water_ph
from microverse.viz.community_scene import CommunityScene

POND = ("chlorella", "tetrahymena", "brachionus")


def sim(keys, t_end=100.0, **ov):
    lab = community_lab(tuple(keys), "custom")
    return lab, run(lab.model, lab.config(ov, t_end=t_end))


# ---------------------------------------------------------------- database
def test_database_is_complete_and_consistent():
    assert len(ORGANISMS) >= 25
    for k, o in ORGANISMS.items():
        assert o.key == k and o.name and o.name_ar and o.ncbi_taxid > 0
        assert o.role and o.role_ar and o.references and o.lineage
        assert o.feeding in ("photoautotroph", "heterotroph", "predator", "chemolithotroph")
        assert o.oxygen in ("aerobe", "facultative", "anaerobe", "microaerophile")
        assert set(o.substrates) <= set(RESOURCES), k
        assert set(o.products) <= set(RESOURCES), k
        tmin, topt, tmax = o.cardinal_T
        assert tmin < topt < tmax
        pmin, popt, pmax = o.cardinal_pH
        assert pmin < popt < pmax
        assert o.mu_max > 0 and o.death >= 0 and 0 < o.yield_bio <= 1.0
        assert sum(o.products.values()) <= 1.0, f"{k} produces more mass than it consumes"
        if o.feeding == "predator":
            assert o.prey_size_max > 0 and o.ingest_max > 0 and o.ks_prey > 0
            assert not o.substrates, "predators eat organisms, not dissolved pools"
        assert isinstance(o.trait_evidence, Evidence)


def test_every_organism_is_biosafety_level_1():
    for o in ORGANISMS.values():
        text = (o.biosafety + o.name).lower()
        assert "level 1" in text or "safe food" in text or "harmless" in text, o.key
        for danger in ("anthracis", "botulinum", "pestis", "tuberculosis", "o157"):
            assert danger not in o.name.lower()


def test_grouping_covers_everything():
    assert sum(len(v) for v in by_group().values()) == len(ORGANISMS)


# ------------------------------------------------------------------ model
def test_cardinal_functions():
    assert ctmi(30, 10, 30, 40) == pytest.approx(1.0)
    assert ctmi(5, 10, 30, 40) == 0 and ctmi(45, 10, 30, 40) == 0
    assert cpm(7, 4, 7, 9) == pytest.approx(1.0)
    assert cpm(3.5, 4, 7, 9) == 0


def test_ph_falls_with_acid_and_buffer_resists():
    assert water_ph(0, 0, 10, 7.0) == pytest.approx(7.0, abs=1e-3)
    acids = np.linspace(0, 2000, 30)
    ph = [water_ph(a, 0, 5, 7.0) for a in acids]
    assert all(np.diff(ph) < 0)
    assert water_ph(1000, 0, 60, 7.0) > water_ph(1000, 0, 5, 7.0)


def test_flux_terms_match_rhs_for_organisms():
    m = Community(POND)
    p = m.default_parameters().values()
    y = m.initial_state_from(p) + 1.0
    dy = m.rhs(0, y, p)
    sums = {f"X_{o.key}": 0.0 for o in m.orgs}
    for ft in m.flux_terms(y, p):
        if ft.target in sums:
            sums[ft.target] += ft.value
    for i, o in enumerate(m.orgs):
        assert sums[f"X_{o.key}"] == pytest.approx(dy[NP + i], abs=1e-9)


def test_nothing_grows_without_its_food():
    _, tr = sim(("ecoli",), 80, sug0=0.0, poly0=0.0)      # E. coli cannot use polymers anyway
    assert tr.y[-1, NP] < tr.y[0, NP]


def test_an_organism_outside_its_limits_dies_rather_than_freezing():
    _, tr = sim(("llactis",), 200, T=60.0)                 # above its maximum temperature
    x = tr.y[:, NP]
    assert x[-1] < 0.2 * x[0]


def test_anaerobe_is_inhibited_by_oxygen():
    """L. bulgaricus is a strict anaerobe: it should do far better in a purged, sealed vessel."""
    _, hi = sim(("lbulgaricus",), 60, aeration=10.0, sug0=2000.0, buffer=60.0)
    _, lo = sim(("lbulgaricus",), 60, aeration=0.0, sug0=2000.0, buffer=60.0)
    assert lo.y[-1, NP] > 5 * hi.y[-1, NP]


def test_photoautotroph_makes_oxygen_and_needs_light():
    _, lit = sim(("chlorella",), 200, sug0=0.0, poly0=0.0, aeration=0.0, light=1.0)
    _, dark = sim(("chlorella",), 200, sug0=0.0, poly0=0.0, aeration=0.0, light=0.0)
    assert lit.y[-1, NP] > 10 * dark.y[-1, NP]
    assert lit.y[:, PI["o2"]].max() > 8.0          # it pushed oxygen above air saturation
    assert lit.y[:, PI["o2"]].max() < 60.0         # but the excess bubbles out


def test_acid_producer_stops_at_its_own_ph_limit():
    lab, tr = sim(("llactis",), 200, sug0=3000.0, buffer=5.0)
    ph = lab.model.ph_series(tr)
    assert ph[-1] == pytest.approx(ORGANISMS["llactis"].cardinal_pH[0], abs=0.1)
    assert tr.y[-1, PI["sug"]] > 100          # sugar is left over because the acid stopped it


def test_mass_is_not_created_from_nothing():
    """Total carbon-ish mass (organics + biomass) must not increase in a closed vessel."""
    lab, tr = sim(("ecoli", "bsubtilis"), 150, dilution=0.0)
    pools = ["poly", "sug", "lac", "ace", "eth", "det"]
    total = tr.y[:, [PI[k] for k in pools]].sum(axis=1) + tr.y[:, NP:].sum(axis=1)
    assert total[-1] <= total[0] * 1.001


def test_predator_eats_prey_and_refuge_prevents_total_extinction():
    lab, tr = sim(("ecoli", "tetrahymena"), 200, refuge=1.0)
    prey = tr.y[:, NP]
    assert prey.min() > 0.0
    with_pred = prey[-1]
    _, alone = sim(("ecoli",), 200)
    assert with_pred < alone.y[-1, NP]


def test_grazer_cannot_eat_prey_that_is_too_large():
    """Tetrahymena (8 µm limit) must not touch the 250 µm rotifer."""
    lab, duo = sim(("tetrahymena", "brachionus"), 150)
    _, solo = sim(("brachionus",), 150)
    i = lab.model.keys.index("brachionus")
    assert duo.y[-1, NP + i] == pytest.approx(solo.y[-1, NP], rel=0.02)


# ----------------------------------------------------------- interactions
def test_interaction_types_are_detected():
    lab = community_lab(("chlorella", "brachionus"), "custom")
    cfg = lab.config({"poly0": 0.0, "sug0": 0.0}, t_end=400)
    ints, together, alone, _ = analyse(lab.model, cfg)
    assert len(ints) == 1
    it = ints[0]
    assert it.kind == "Predation (grazing)"
    assert it.effect_of_b_on_a < -THRESHOLD and it.effect_of_a_on_b > THRESHOLD
    assert any("ingest" in en for en, ar in it.why_a)


def test_cross_feeding_is_detected_as_a_benefit():
    lab = community_lab(("lbulgaricus", "pfreudenreichii"), "custom")
    cfg = lab.config({"sug0": 0.0, "poly0": 2000.0, "buffer": 60.0, "aeration": 0.0, "T": 30.0}, t_end=200)
    ints, *_ = analyse(lab.model, cfg)
    it = ints[0]
    assert it.effect_of_a_on_b > THRESHOLD          # the propionibacterium gains
    assert any("ross-feeding" in en or "polymers" in en for en, ar in it.why_b)


def test_alone_and_pair_runs_are_reproducible():
    lab = community_lab(("ecoli", "bsubtilis"), "custom")
    cfg = lab.config({}, t_end=80)
    a = analyse(lab.model, cfg)[0][0]
    b = analyse(lab.model, cfg)[0][0]
    assert a.effect_of_b_on_a == pytest.approx(b.effect_of_b_on_a)


# ------------------------------------------------------------------- labs
def test_every_preset_runs_and_explains_in_both_languages():
    for key, keys, en, ar, question, ov, t_end in PRESETS:
        lab = community_lab(keys, key)
        tr = run(lab.model, lab.config(lab.scenarios[0].overrides, t_end=lab.scenarios[0].t_end))
        assert np.all(np.isfinite(tr.y))
        assert np.all(tr.y >= -1e-9)
        for lang in ("en", "ar"):
            i18n.set_lang(lang)
            label, colour = lab.outcome(tr)
            assert label and colour.startswith("#")
            html = lab.explain_html(tr, len(tr.t) // 2, None)
            assert len(html) > 500
    i18n.set_lang("en")


def test_all_labs_have_consistent_parameter_groups():
    for lab in all_labs():
        grouped = [s for _, syms in lab.param_groups for s in syms]
        assert set(grouped) == set(lab.model.default_parameters().params), lab.key
        assert len(grouped) == len(set(grouped))
        for panel in lab.plots:
            for s in panel.series:
                tr = run(lab.model, lab.config(lab.scenarios[0].overrides, t_end=20))
                assert len(s.getter(tr)) == len(tr.t)
                break
            break


def test_scene_reads_state_only_and_reports_its_concentration():
    lab, tr = sim(POND, 300, poly0=0.0, sug0=0.0)
    before = tr.y.copy()
    sc = CommunityScene(lab.model, seed=0)
    seen = [0] * len(lab.model.orgs)
    for _ in range(300):
        sc.sync(tr, tr.index_at(80), 0.033)
        seen = [max(a, len(c)) for a, c in zip(seen, sc.cells)]
    assert np.array_equal(tr.y, before)
    assert all(c > 0 for c in sc.concentration)
    for i, o in enumerate(lab.model.orgs):
        if tr.y[tr.index_at(80), NP + i] > 0.5:
            assert seen[i] > 0, f"{o.key} was never drawn although it is present"


def test_arabic_explanation_is_right_to_left():
    lab, tr = sim(POND, 200, poly0=0.0, sug0=0.0)
    i18n.set_lang("ar")
    html = lab.explain_html(tr, len(tr.t) // 2, None)
    i18n.set_lang("en")
    assert "dir='rtl'" in html
    assert "الحموضة" in html
