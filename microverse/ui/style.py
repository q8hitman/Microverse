"""Shared colours and the application stylesheet."""

BG = "#0d1117"
PANEL = "#161b22"
PANEL_2 = "#1c2230"
BORDER = "#30363d"
TEXT = "#e6edf3"
TEXT_2 = "#9da7b3"
MUTED = "#6e7681"
ACCENT = "#58a6ff"

STYLESHEET = f"""
QWidget {{ font-family: 'Segoe UI'; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QStackedWidget {{ background: {BG}; }}
QDockWidget::title {{ background: {PANEL}; padding: 6px 8px; font-weight: 600; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 8px; margin-top: 14px; padding: 8px 6px 6px 6px;
             background: {PANEL}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {TEXT_2}; font-weight: 600; }}
QPushButton {{ background: #21262d; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 12px; }}
QPushButton:hover {{ background: #30363d; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#primary {{ background: #238636; border-color: #2ea043; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: #2ea043; }}
QPushButton#link {{ background: transparent; border: none; color: {ACCENT}; padding: 2px 4px; }}
QDoubleSpinBox, QSpinBox, QComboBox {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 5px; padding: 3px 6px; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 6px; top: -1px; }}
QTabBar::tab {{ background: {PANEL}; border: 1px solid {BORDER}; padding: 6px 14px; border-top-left-radius: 6px;
                border-top-right-radius: 6px; margin-right: 2px; color: {TEXT_2}; }}
QTabBar::tab:selected {{ background: {PANEL_2}; color: {TEXT}; }}
QTextBrowser {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#card:hover {{ border-color: #484f58; }}
QFrame#cardSelected {{ background: {PANEL_2}; border: 2px solid {ACCENT}; border-radius: 10px; }}
QLabel#h1 {{ font-size: 20pt; font-weight: 700; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 600; margin-top: 4px; }}
/* keyboard focus must always be visible */
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus,
QCheckBox:focus, QRadioButton:focus {{ outline: none; border: 2px solid {ACCENT}; }}
QFrame#card:focus {{ border: 2px solid {ACCENT}; }}
QLineEdit {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px; }}
QPushButton#fold {{ background: transparent; border: none; text-align: left; font-weight: 600;
                    color: {TEXT_2}; padding: 4px 2px; }}
QPushButton#fold:hover {{ color: {TEXT}; }}
QPushButton#fold:checked {{ color: {TEXT}; }}
QLabel#muted {{ color: {TEXT_2}; }}
QLabel#chip {{ border-radius: 9px; padding: 2px 8px; font-size: 8pt; }}
QProgressBar {{ border: 1px solid {BORDER}; border-radius: 5px; text-align: center; background: {BG}; }}
QProgressBar::chunk {{ background: #1f6feb; border-radius: 4px; }}
"""
