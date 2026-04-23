import pytest
from services import update_check
from services.update_check import UpdateChecker, parse_version


@pytest.mark.parametrize("raw, expected", [
    ("0.0.1", (0, 0, 1)),
    ("v0.0.1", (0, 0, 1)),
    ("1.2.3", (1, 2, 3)),
    ("v10.20.30", (10, 20, 30)),
    ("0.0.0+dev", (0, 0, 0)),
    ("1.2.3-rc1", (1, 2, 3)),
    ("garbage", (0, 0, 0)),
    ("", (0, 0, 0)),
])
def test_parse_version(raw, expected):
    assert parse_version(raw) == expected


def test_ordering_detects_newer():
    assert parse_version("v0.0.2") > parse_version("0.0.1")
    assert parse_version("1.0.0") > parse_version("0.9.99")
    assert not (parse_version("0.0.1") > parse_version("v0.0.1"))


class _Recorder:
    def __init__(self):
        self.emitted = []
        self.finished_count = 0
        self.update_available = type("S", (), {"emit": lambda _, v: self.emitted.append(v)})()
        self.finished = type("S", (), {"emit": lambda _: self._finish()})()

    def _finish(self):
        self.finished_count += 1


def _run_checker(current, latest, monkeypatch):
    monkeypatch.setattr(update_check, "fetch_latest_tag", lambda timeout=5.0: latest)
    checker = UpdateChecker.__new__(UpdateChecker)
    checker.current = current
    rec = _Recorder()
    checker.update_available = rec.update_available
    checker.finished = rec.finished
    checker.run()
    return rec


def test_run_skips_dev_build(monkeypatch):
    called = []
    monkeypatch.setattr(update_check, "fetch_latest_tag",
                        lambda timeout=5.0: called.append(1) or "v9.9.9")
    rec = _run_checker("0.0.0+dev", "v9.9.9", monkeypatch)
    assert rec.emitted == []
    assert rec.finished_count == 1


def test_run_emits_when_newer(monkeypatch):
    rec = _run_checker("0.0.1", "v0.0.2", monkeypatch)
    assert rec.emitted == ["v0.0.2"]
    assert rec.finished_count == 1


def test_run_silent_when_same_or_older(monkeypatch):
    rec = _run_checker("1.2.3", "v1.2.3", monkeypatch)
    assert rec.emitted == []
    rec = _run_checker("1.2.3", "v1.0.0", monkeypatch)
    assert rec.emitted == []


def test_run_silent_on_fetch_failure(monkeypatch):
    rec = _run_checker("0.0.1", None, monkeypatch)
    assert rec.emitted == []
    assert rec.finished_count == 1
