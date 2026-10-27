"""Every screen can be built and ticked without errors (off-screen Qt). Catches wiring regressions that
unit tests of the models cannot see. It does not judge how anything looks — see the screenshots for that."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    os.environ["MICROVERSE_DB"] = str(tmp_path_factory.mktemp("db") / "ui.sqlite")
    import microverse.data.db as db
    db.DEFAULT_DB = __import__("pathlib").Path(os.environ["MICROVERSE_DB"])
    return QApplication.instance() or QApplication([])


def labs():
    from microverse.labs import community_lab, fixed_labs
    return list(fixed_labs()) + [community_lab(("chlorella", "tetrahymena", "brachionus"), "pond"),
                                 community_lab(("ecoli", "scerevisiae", "aoryzae", "paramecium", "euglena"), "custom")]


@pytest.mark.parametrize("i", range(4))
def test_workspace_builds_runs_and_switches_modes(app, i):
    from microverse.core.scheduler import run
    from microverse.ui.workspace import Workspace
    lab = labs()[i]
    w = Workspace(lab, lab.scenarios[0])
    s = lab.scenarios[0]
    w.traj = run(lab.model, lab.config(s.overrides, mode=s.mode, seed=s.seed, volume_ml=s.volume_ml, t_end=s.t_end))
    for m in range(w.mode_combo.count()):
        w.mode_combo.setCurrentIndex(m)
        w._seek(w.traj.t[-1] * (m + 1) / 4)
        for _ in range(5):
            w._tick()
        w.micro.grab()                                   # paints every mode
    w._replay()
    w._refresh_explanation(force=True)
    assert "What changed" in w.explain_view.toHtml() or "ماذا تغيّر" in w.explain_view.toHtml()
    w.anim.stop()
    w.explain_timer.stop()
    w.deleteLater()


def test_pages_build(app):
    from microverse.ui.agar_page import AgarPage
    from microverse.ui.main_window import MainWindow
    from microverse.ui.reality_page import RealityPage
    RealityPage().grab()
    AgarPage().grab()
    w = MainWindow()
    w.open_reality()
    w.open_agar()
    w.change_language("ar")
    w.change_language("en")
    w.grab()
