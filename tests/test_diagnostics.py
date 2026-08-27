"""Tests for the log-parsing diagnostics engine."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db  # noqa: E402
import diagnostics  # noqa: E402

SAMPLE_LOG = """2026-08-27 01:02:11 INFO  Server started on port 8080
2026-08-27 01:20:02 ERROR Database connection pool exhausted
2026-08-27 01:20:03 ERROR Database connection pool exhausted
2026-08-27 01:30:51 WARNING Disk usage at 87%
2026-08-27 01:55:08 CRITICAL Authentication service unreachable
2026-08-27 01:55:40 CRITICAL Authentication service unreachable
"""


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_helpdesk.db")
    db.init_db()
    return db


@pytest.fixture
def sample_log_file(tmp_path):
    path = tmp_path / "sample.log"
    path.write_text(SAMPLE_LOG)
    return path


def test_parse_log_extracts_all_lines(sample_log_file):
    entries = diagnostics.parse_log(sample_log_file)
    assert len(entries) == 6
    assert entries[0]["level"] == "INFO"
    assert entries[1]["level"] == "ERROR"


def test_decide_priority_critical_is_p1():
    assert diagnostics.decide_priority("CRITICAL", occurrences=1) == "P1"


def test_decide_priority_error_is_p2():
    assert diagnostics.decide_priority("ERROR", occurrences=1) == "P2"


def test_decide_priority_single_warning_is_not_ticketed():
    assert diagnostics.decide_priority("WARNING", occurrences=1) is None


def test_decide_priority_repeated_warning_is_p3():
    assert diagnostics.decide_priority("WARNING", occurrences=2) == "P3"


def test_run_diagnostics_creates_expected_tickets(fresh_db, sample_log_file):
    created = diagnostics.run_diagnostics(sample_log_file, verbose=False)

    tickets = fresh_db.list_tickets()
    # ERROR (dedup'd to 1 group) + CRITICAL (dedup'd to 1 group) = 2 tickets.
    # The single WARNING occurrence is below the repeat threshold and isn't ticketed.
    assert len(created) == 2
    priorities = sorted(t["priority"] for t in tickets)
    assert priorities == ["P1", "P2"]


def test_run_diagnostics_does_not_duplicate_open_tickets(fresh_db, sample_log_file):
    first_run = diagnostics.run_diagnostics(sample_log_file, verbose=False)
    second_run = diagnostics.run_diagnostics(sample_log_file, verbose=False)

    assert len(first_run) == 2
    assert len(second_run) == 0  # same errors, tickets already open -> no duplicates
    assert len(fresh_db.list_tickets()) == 2
