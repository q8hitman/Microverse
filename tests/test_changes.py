"""'What changed and why': the reported causes come from the model's flux terms and add up to the change."""
import pytest

from microverse.analysis.changes import significant_changes, to_html
from microverse.core.scheduler import run
from microverse.labs import community_lab, get


@pytest.mark.parametrize("make", [lambda: get("chemostat"), lambda: get("yogurt"),
                                  lambda: community_lab(("llactis", "lplantarum"), "vegetable")])
def test_flux_terms_account_for_the_change(make):
    lab = make()
    s = lab.scenarios[0]
    tr = run(lab.model, lab.config(s.overrides, t_end=s.t_end))
    found = False
    for idx in range(len(tr.t) // 10, len(tr.t), len(tr.t) // 10):
        for c in significant_changes(lab.model, tr, idx):
            found = True
            assert c.terms, c.symbol
            assert c.explained == pytest.approx(1.0, abs=0.12), (c.symbol, c.explained)
    assert found
    html = to_html(lab.model, tr, len(tr.t) // 3)
    assert "What changed" in html


def test_yogurt_names_the_right_cause_of_acidification():
    lab = get("yogurt")
    tr = run(lab.model, lab.config({}))
    ch = {c.symbol: c for c in significant_changes(lab.model, tr, tr.index_at(4.0))}
    assert "A" in ch and ch["A"].delta > 0
    assert ch["A"].terms[0][2] > 0                 # the largest term is a production term
