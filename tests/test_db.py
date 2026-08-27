"""Tests for SLA calculation, ticket CRUD, and status-change auditing."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db  # noqa: E402


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_helpdesk.db")
    db.init_db()
    return db


def test_sla_due_p1_is_4_hours(fresh_db):
    created = "2026-08-27T10:00:00"
    assert fresh_db.compute_sla_due(created, "P1") == "2026-08-27T14:00:00"


def test_sla_due_p3_is_72_hours(fresh_db):
    created = "2026-08-27T10:00:00"
    assert fresh_db.compute_sla_due(created, "P3") == "2026-08-30T10:00:00"


def test_create_ticket_sets_open_status_and_sla(fresh_db):
    cid = fresh_db.add_customer("Test Customer", "test@example.com")
    ticket_id = fresh_db.create_ticket(cid, "Login broken", "Cannot log in", "P1")

    tickets = fresh_db.list_tickets()
    assert len(tickets) == 1
    assert tickets[0]["status"] == "Open"
    assert tickets[0]["priority"] == "P1"
    assert tickets[0]["ticket_id"] == ticket_id


def test_create_ticket_rejects_invalid_priority(fresh_db):
    cid = fresh_db.add_customer("Test Customer", "test@example.com")
    with pytest.raises(ValueError):
        fresh_db.create_ticket(cid, "Subject", "Desc", "P9")


def test_update_status_writes_history(fresh_db):
    cid = fresh_db.add_customer("Test Customer", "test@example.com")
    ticket_id = fresh_db.create_ticket(cid, "Subject", "Desc", "P2")

    fresh_db.update_ticket_status(ticket_id, "In Progress", note="Investigating")
    fresh_db.update_ticket_status(ticket_id, "Resolved", note="Fixed the config")

    history = fresh_db.get_ticket_history(ticket_id)
    assert [h["new_status"] for h in history] == ["Open", "In Progress", "Resolved"]
    assert history[-1]["note"] == "Fixed the config"

    tickets = fresh_db.list_tickets()
    assert tickets[0]["status"] == "Resolved"
    assert tickets[0]["resolved_at"] is not None


def test_update_status_rejects_invalid_status(fresh_db):
    cid = fresh_db.add_customer("Test Customer", "test@example.com")
    ticket_id = fresh_db.create_ticket(cid, "Subject", "Desc", "P2")
    with pytest.raises(ValueError):
        fresh_db.update_ticket_status(ticket_id, "Cancelled")


def test_is_breached_false_for_future_sla(fresh_db):
    future = "2099-01-01T00:00:00"
    assert fresh_db.is_breached(future, "Open") is False


def test_is_breached_true_for_past_sla_when_open(fresh_db):
    past = "2000-01-01T00:00:00"
    assert fresh_db.is_breached(past, "Open") is True


def test_is_breached_false_for_past_sla_when_resolved(fresh_db):
    past = "2000-01-01T00:00:00"
    assert fresh_db.is_breached(past, "Resolved") is False


def test_list_tickets_filters_by_status_and_priority(fresh_db):
    cid = fresh_db.add_customer("Test Customer", "test@example.com")
    t1 = fresh_db.create_ticket(cid, "A", "desc", "P1")
    fresh_db.create_ticket(cid, "B", "desc", "P3")
    fresh_db.update_ticket_status(t1, "Resolved")

    assert len(fresh_db.list_tickets(status="Resolved")) == 1
    assert len(fresh_db.list_tickets(priority="P3")) == 1
    assert len(fresh_db.list_tickets(status="Open", priority="P1")) == 0
