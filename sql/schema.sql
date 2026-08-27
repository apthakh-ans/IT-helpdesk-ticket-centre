-- IT Helpdesk Ticket System schema.
--
-- customers  1—* tickets   (who raised it)
-- agents     1—* tickets   (who's handling it; nullable = unassigned)
-- tickets    1—* ticket_history   (every status change, audited)

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    company     TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    email    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    agent_id     INTEGER REFERENCES agents(agent_id),
    subject      TEXT NOT NULL,
    description  TEXT NOT NULL,
    priority     TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3')),
    status       TEXT NOT NULL CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Closed')) DEFAULT 'Open',
    source       TEXT NOT NULL CHECK (source IN ('manual', 'auto-diagnostic')) DEFAULT 'manual',
    created_at   TEXT NOT NULL,
    sla_due_at   TEXT NOT NULL,
    resolved_at  TEXT
);

CREATE TABLE IF NOT EXISTS ticket_history (
    history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(ticket_id),
    changed_at  TEXT NOT NULL,
    old_status  TEXT,
    new_status  TEXT NOT NULL,
    note        TEXT
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_history_ticket ON ticket_history(ticket_id);
