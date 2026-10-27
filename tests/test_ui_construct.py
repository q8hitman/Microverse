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


def test_calibration_dialog_fits_and_shows_results(app):
    from microverse.analysis import calibration as C
    from microverse.analysis import reality as R
    from microverse.core.scheduler import run
    from microverse.data import db
    from microverse.labs import get
    from microverse.ui.calibration_dialog import CalibrationDialog
    lab = get("yogurt")
    cfg = lab.config({}, t_end=10.0)
    con = db.connect()
    pid = db.freeze_prediction(con, cfg, {"lab": "yogurt", "scenario": "classic", "outcome": "x"}, "ui",
                               db.save_experiment(con, "ui", cfg))
    fp = R.load_prediction(con, pid)
    tr = run(lab.model, C.with_parameters(lab.model, cfg, {"muS": 2.0}))
    obs = R.observables_for(lab.model)
    t = __import__("numpy").arange(0, 9.5, 0.5)
    series = [R.ObservedSeries("pH", "pH", "pH", t, __import__("numpy").interp(t, tr.t, obs[0].getter(tr)))]
    table = R.read_table("t,pH\n0,6.6\n1,6.5\n", text=True)
    dlg = CalibrationDialog(fp, lab, table, R.ColumnMap("t", "h", {"pH": ("pH", "pH")}), obs, series)
    assert dlg.chosen() == list(C.SUGGESTED["yogurt"])
    res = C.calibrate(lab.model, cfg, obs, series, ["muS"])
    dlg._done(dlg.token, res)
    assert dlg.btn_freeze.isEnabled() and "muS" in dlg.report.toHtml()
    dlg.grab()


def test_changing_inputs_after_compare_blocks_a_stale_save(app, tmp_path, monkeypatch):
    """Results may only be saved together with the inputs they were computed from."""
    from microverse.core.scheduler import run
    from microverse.data import db
    from microverse.labs import get
    from microverse.ui import reality_page
    from microverse.ui.reality_page import RealityPage
    monkeypatch.setattr(reality_page, "EXAMPLE", tmp_path)       # keep the synthetic CSV out of data/
    lab = get("yogurt")
    con = db.connect()
    for _ in range(2):
        cfg = lab.config({}, t_end=10.0)
        db.freeze_prediction(con, cfg, {"lab": "yogurt", "scenario": "classic", "outcome": "x"}, "ui",
                             db.save_experiment(con, "ui", cfg))
    page = RealityPage()
    page.refresh()
    page._example()
    page._compare()
    assert page.results and page.btn_save.isEnabled() and page._snap[0] is page.fp
    page.offset.setValue(page.offset.value() + 1)                # edit the mapping
    assert not page.results and not page.btn_save.isEnabled()
    page._compare()
    assert page.btn_save.isEnabled()
    page.pred_combo.setCurrentIndex((page.pred_combo.currentIndex() + 1) % page.pred_combo.count())
    assert not page.results and not page.btn_save.isEnabled()   # another prediction selected


def test_school_mode_hides_advanced_controls_but_runs_the_same_model(app):
    from microverse import i18n
    from microverse.ui.main_window import MainWindow
    from microverse.ui.workspace import Workspace
    lab = labs()[0]
    sc = lab.scenarios[0]
    research = Workspace(lab, sc)
    try:
        i18n.set_mode("school")
        school = Workspace(lab, sc)
        if lab.supports_stochastic:                                          # hidden, not removed
            assert research.center_tabs.isTabVisible(research.rep_tab)
            assert not school.center_tabs.isTabVisible(school.rep_tab)
        assert set(school.spins) == set(research.spins)                     # nothing removed, only hidden
        assert school.current_config().hash() == research.current_config().hash()
        assert any(not s.isVisibleTo(school) for s in school.spins.values()) or not lab.param_groups
        w = MainWindow()
        w.change_mode("research")
        assert not i18n.is_school() and w.start.mode.currentData() == "research"
        for x in (school, w):
            x.deleteLater()
    finally:
        i18n.set_mode("research")
        research.deleteLater()


def test_switching_mode_keeps_open_work(app, tmp_path, monkeypatch):
    """The mode only hides or shows controls: open pages, imported data and edited values survive the switch."""
    from microverse import i18n
    from microverse.data import db
    from microverse.labs import get
    from microverse.ui import reality_page
    from microverse.ui.main_window import MainWindow
    monkeypatch.setattr(reality_page, "EXAMPLE", tmp_path)
    lab = get("yogurt")
    con = db.connect()
    cfg = lab.config({}, t_end=10.0)
    db.freeze_prediction(con, cfg, {"lab": "yogurt", "scenario": "classic", "outcome": "x"}, "ui",
                         db.save_experiment(con, "ui", cfg))
    w = MainWindow()
    try:
        w.open_lab(lab, lab.scenarios[0])
        ws = w.workspace
        ws.spins["Lac0"].setValue(ws.spins["Lac0"].value() * 0.8)          # an experimenter control, not "CONTROL"
        edited = ws.spins["Lac0"].value()
        w.open_reality()
        page = w.reality
        page._example()
        page._compare()
        w.show()
        w.change_mode("school")
        assert w.workspace is ws and w.reality is page                    # nothing rebuilt
        assert page.results and page.btn_save.isEnabled() and page.btn_calib.isHidden()
        assert ws.spins["Lac0"].value() == edited
        app.processEvents()
        w.stack.setCurrentWidget(ws)
        app.processEvents()
        assert ws.spins["Lac0"].isVisibleTo(ws) and ws.spins["T"].isVisibleTo(ws)   # whole process group stays
        assert not ws.spins["muS"].isVisibleTo(ws)                                  # organism trait hidden
        w.change_mode("research")
        assert not page.btn_calib.isHidden() and not ws.spins["muS"].parentWidget().parentWidget().isHidden()
    finally:
        i18n.set_mode("research")
        __import__("PySide6.QtCore", fromlist=["QThreadPool"]).QThreadPool.globalInstance().waitForDone()
        w.deleteLater()


def test_suggested_incubation_never_overrides_the_users_choice(app):
    from microverse.ui.agar_page import AgarPage
    a = AgarPage()
    a.org.setCurrentIndex(a.org.findData("scerevisiae"))
    assert a.tend.value() == 48
    a.org2.setCurrentIndex(a.org2.findData("aoryzae"))
    a.delay.setValue(10)
    assert a.tend.value() == 10 + 72                                       # the second organism's delay counts
    a.tend.setValue(96)                                                    # the user decides
    a.org.setCurrentIndex(a.org.findData("ecoli"))
    a.delay.setValue(48)
    assert a.tend.value() == 96
