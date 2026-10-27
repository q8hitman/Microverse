"""Background computation so the UI never freezes."""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QRunnable, Signal


class _Signals(QObject):
    done = Signal(object, object)       # (token, result)
    failed = Signal(object, str)
    progress = Signal(int, int)


class Job(QRunnable):
    def __init__(self, token, fn, *args, with_progress=False, **kwargs):
        super().__init__()
        self.token, self.fn, self.args, self.kwargs = token, fn, args, kwargs
        self.with_progress = with_progress
        self.signals = _Signals()

    def run(self):
        try:
            if self.with_progress:
                self.kwargs["progress"] = lambda i, n: self.signals.progress.emit(i, n)
            self.signals.done.emit(self.token, self.fn(*self.args, **self.kwargs))
        except Exception:
            self.signals.failed.emit(self.token, traceback.format_exc())
