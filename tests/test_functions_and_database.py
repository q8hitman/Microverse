"""Tests for the function reference, the SQLite organism database and the printable guide."""
import csv
import sqlite3

import pytest

from microverse.data import db
from microverse.library.functions import (FUNCTIONS, MANUAL, derived_functions, functions_of, is_derived,
                                          organisms_with, relations)
from microverse.library.guide import guide_html
from microverse.library.organisms import ORGANISMS


def test_every_organism_has_at_least_one_function():
    for k in ORGANISMS:
        assert functions_of(k), k


def test_every_function_is_documented_in_both_languages():
    for f in FUNCTIONS.values():
        assert f.name and f.name_ar and f.meaning and f.meaning_ar and f.example and f.example_ar
        simulated = any(is_derived(o.key, f.key) for o in ORGANISMS.values())
        if simulated:
            assert f.in_model and f.in_model_ar, f"{f.key} is derived from traits so must say how it is simulated"


def test_manual_tags_only_use_known_functions_and_organisms():
    for k, tags in MANUAL.items():
        assert k in ORGANISMS
        assert set(tags) <= set(FUNCTIONS)


@pytest.mark.parametrize("key,expected,absent", [
    ("chlorella", {"producer", "oxygen"}, {"lactic"}),
    ("llactis", {"lactic", "acidifier"}, {"producer"}),
    ("pfreudenreichii", {"crossfeeder"}, {"acidifier"}),     # eats lactate: replaces a strong acid
    ("ecoli", {"acidifier"}, {"lactic"}),                     # mixed-acid, not a lactic fermenter
    ("aoryzae", {"decomposer"}, set()),
    ("tetrahymena", {"bacterivore"}, {"algivore"}),
    ("paramecium", {"bacterivore", "algivore"}, set()),
    ("amoeba", {"toppredator"}, set()),
    ("azotobacter", {"nfixer"}, set()),
    ("nitrosomonas", {"nitrifier"}, set()),
    ("methanosarcina", {"methanogen"}, set()),
    ("euglena", {"mixotroph"}, set()),
    ("scerevisiae", {"alcohol"}, {"lactic"}),
])
def test_functions_follow_the_biology(key, expected, absent):
    got = {f.key for f in functions_of(key)}
    assert expected <= got, (key, got)
    assert not (absent & got), (key, got)


def test_derived_functions_agree_with_simulation_traits():
    """A label read from traits must be consistent with the trait it came from."""
    for o in ORGANISMS.values():
        d = derived_functions(o)
        if "producer" in d:
            assert o.feeding == "photoautotroph"
        if "decomposer" in d:
            assert o.hydrolysis > 0
        if "methanogen" in d:
            assert o.oxygen == "anaerobe" and "ace" in o.substrates
        if "nfixer" in d:
            assert o.n_quota == 0


def test_lookup_by_function_is_the_inverse_of_functions_of():
    for f in FUNCTIONS:
        for o in organisms_with(f):
            assert f in {x.key for x in functions_of(o.key)}


def test_relations_are_read_from_traits():
    rel = relations(("chlorella", "tetrahymena", "brachionus"))
    kinds = {(a, b, k) for a, b, k, _, _ in rel}
    assert ("tetrahymena", "chlorella", "eats") in kinds
    assert ("brachionus", "chlorella", "eats") in kinds
    assert ("chlorella", "tetrahymena", "oxygen") in kinds
    rel2 = relations(("lbulgaricus", "pfreudenreichii"))
    assert any(k == "feeds" and a == "lbulgaricus" for a, b, k, _, _ in rel2)


def test_sqlite_database_holds_every_organism_and_function(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    n = db.seed_organisms(con)
    assert n == len(ORGANISMS)
    assert con.execute("SELECT COUNT(*) FROM organism_db").fetchone()[0] == len(ORGANISMS)
    assert con.execute("SELECT COUNT(*) FROM functions").fetchone()[0] == len(FUNCTIONS)
    links = con.execute("SELECT COUNT(*) FROM organism_functions").fetchone()[0]
    assert links == sum(len(functions_of(k)) for k in ORGANISMS)
    row = con.execute("SELECT name_ar, feeding, t_opt FROM organism_db WHERE key='chlorella'").fetchone()
    assert row["name_ar"] == ORGANISMS["chlorella"].name_ar and row["feeding"] == "photoautotroph"
    # re-seeding replaces, it does not duplicate
    db.seed_organisms(con)
    assert con.execute("SELECT COUNT(*) FROM organism_db").fetchone()[0] == len(ORGANISMS)


def test_csv_export_opens_with_arabic(tmp_path):
    path = tmp_path / "o.csv"
    db.export_organisms_csv(path)
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")          # BOM so Excel detects UTF-8
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    assert len(rows) == len(ORGANISMS)
    assert rows[0]["name_ar"] and rows[0]["functions"]


def test_guide_contains_every_organism_and_function():
    html = guide_html()
    for o in ORGANISMS.values():
        assert o.name in html
    for f in FUNCTIONS.values():
        assert f.name in html


def test_every_parameter_has_an_arabic_name():
    from microverse.i18n import PARAM_AR
    from microverse.labs import community_lab, fixed_labs
    for lab in list(fixed_labs()) + [community_lab(("chlorella", "ecoli"), "custom")]:
        for p in lab.model.default_parameters().params.values():
            assert p.symbol in PARAM_AR, (lab.key, p.symbol)


def test_every_scenario_question_and_plot_label_has_arabic():
    from microverse.i18n import TERMS_AR
    from microverse.labs import all_labs
    for lab in all_labs():
        for s in lab.scenarios:
            assert s.question in TERMS_AR, s.question
        for pnl in lab.plots:
            assert pnl.title in TERMS_AR, pnl.title
