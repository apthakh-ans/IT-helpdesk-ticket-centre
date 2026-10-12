"""
Database layer for the helpdesk system: connection handling, schema init,
SLA calculation, and CRUD/audit operations for tickets.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "helpdesk.db"
SCHEMA_PATH = BASE / "sql" / "schema.sql"

# Standard helpdesk SLA tiers, in hours, by priority.
SLA_HOURS = {"P1": 4, "P2": 24, "P3": 72}

ISO_FMT = "%Y-%m-%dT%H:%M:%S"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now().strftime(ISO_FMT)


def compute_sla_due(created_at: str, priority: str) -> str:
    created = datetime.strptime(created_at, ISO_FMT)
    due = created + timedelta(hours=SLA_HOURS[priority])
    return due.strftime(ISO_FMT)


def is_breached(sla_due_at: str, status: str) -> bool:
    if status in ("Resolved", "Closed"):
        return False
    return datetime.strptime(sla_due_at, ISO_FMT) < datetime.now()


def add_customer(name, email, company=None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO customers (name, email, company) VALUES (?, ?, ?)",
        (name, email, company),
    )
    conn.commit()
    customer_id = cur.lastrowid
    conn.close()
    return customer_id


def add_agent(name, email):
    conn = get_connection()
    cur = conn.execute("INSERT INTO agents (name, email) VALUES (?, ?)", (name, email))
    conn.commit()
    agent_id = cur.lastrowid
    conn.close()
    return agent_id


def create_ticket(customer_id, subject, description, priority, agent_id=None, source="manual"):
    if priority not in SLA_HOURS:
        raise ValueError(f"Invalid priority: {priority}")

    created_at = now_iso()
    sla_due_at = compute_sla_due(created_at, priority)

    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO tickets
           (customer_id, agent_id, subject, description, priority, status, source, created_at, sla_due_at)
           VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?)""",
        (customer_id, agent_id, subject, description, priority, source, created_at, sla_due_at),
    )
    ticket_id = cur.lastrowid
    conn.execute(
        "INSERT INTO ticket_history (ticket_id, changed_at, old_status, new_status, note) VALUES (?, ?, ?, ?, ?)",
        (ticket_id, created_at, None, "Open", "Ticket created"),
    )
    conn.commit()
    conn.close()
    return ticket_id


def update_ticket_status(ticket_id, new_status, note=None, agent_id=None):
    valid = {"Open", "In Progress", "Resolved", "Closed"}
    if new_status not in valid:
        raise ValueError(f"Invalid status: {new_status}")

    conn = get_connection()
    row = conn.execute("SELECT status FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"No ticket with id {ticket_id}")
    old_status = row["status"]

    changed_at = now_iso()
    resolved_at = changed_at if new_status in ("Resolved", "Closed") else None

    if agent_id is not None:
        conn.execute(
            "UPDATE tickets SET status = ?, agent_id = ?, resolved_at = ? WHERE ticket_id = ?",
            (new_status, agent_id, resolved_at, ticket_id),
        )
    else:
        conn.execute(
            "UPDATE tickets SET status = ?, resolved_at = ? WHERE ticket_id = ?",
            (new_status, resolved_at, ticket_id),
        )

    conn.execute(
        "INSERT INTO ticket_history (ticket_id, changed_at, old_status, new_status, note) VALUES (?, ?, ?, ?, ?)",
        (ticket_id, changed_at, old_status, new_status, note),
    )
    conn.commit()
    conn.close()


def list_tickets(status=None, priority=None):
    conn = get_connection()
    query = """
        SELECT t.*, c.name AS customer_name, a.name AS agent_name
        FROM tickets t
        JOIN customers c ON c.customer_id = t.customer_id
        LEFT JOIN agents a ON a.agent_id = t.agent_id
        WHERE 1 = 1
    """
    params = []
    if status:
        query += " AND t.status = ?"
        params.append(status)
    if priority:
        query += " AND t.priority = ?"
        params.append(priority)
    query += " ORDER BY t.sla_due_at ASC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ticket_history(ticket_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM ticket_history WHERE ticket_id = ? ORDER BY changed_at ASC",
        (ticket_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_or_create_system_customer():
    """Auto-diagnostic tickets need a customer_id; use a fixed 'System Monitoring' pseudo-customer."""
    conn = get_connection()
    row = conn.execute("SELECT customer_id FROM customers WHERE email = 'system@monitoring.local'").fetchone()
    conn.close()
    if row:
        return row["customer_id"]
    return add_customer("System Monitoring", "system@monitoring.local", "Internal")
