# 🎫 IT Helpdesk Ticket System

A small helpdesk/support-ticket platform: SQL-backed ticket lifecycle with SLA tracking, an agent-facing Streamlit queue, and a log-diagnostics engine that auto-opens tickets from server log errors.

Built to mirror the day-to-day of an application support role, rather than being a data/ML project — SQL schema design, ticket triage, SLA management, and log troubleshooting are the actual subject, not a side feature.

## Schema

```text
customers(customer_id PK, name, email, company)
agents(agent_id PK, name, email)
tickets(ticket_id PK, customer_id FK, agent_id FK nullable, subject, description,
        priority [P1|P2|P3], status [Open|In Progress|Resolved|Closed],
        source [manual|auto-diagnostic], created_at, sla_due_at, resolved_at)
ticket_history(history_id PK, ticket_id FK, changed_at, old_status, new_status, note)
```

`customers 1—* tickets`, `agents 1—* tickets`, `tickets 1—* ticket_history` (every status change is audited).

## SLA policy

| Priority | SLA |
|---|---|
| P1 | 4 hours |
| P2 | 24 hours |
| P3 | 72 hours |

`sla_due_at` is computed at ticket creation; the UI flags any open ticket past its deadline as SLA-breached.

## Log diagnostics

`src/diagnostics.py` parses a server log (`data/sample_logs/app_server.log`), groups repeated identical lines (so a burst of the same error doesn't flood the queue), and opens tickets based on severity/frequency:

| Log level | Rule |
|---|---|
| CRITICAL | always → P1 |
| ERROR | always → P2 |
| WARNING | only if it repeats ≥2 times → P3 (a one-off warning is noise; a repeated one is a trend) |
| INFO | ignored |

Re-running diagnostics against the same log doesn't create duplicate tickets — it checks for an already-open ticket with the same subject first.

## Running it

```bash
pip install -r requirements.txt
python src/seed_data.py      # creates helpdesk.db with sample agents/customers/tickets
python src/diagnostics.py    # parses the sample log, auto-opens tickets
streamlit run app.py         # agent UI: ticket queue, filters, SLA-breach flags, status updates
```

## Tests

```bash
pytest tests/ -v
```

17 tests covering SLA computation, ticket CRUD, status-history auditing, log parsing, severity/frequency decisions, and diagnostic de-duplication.

## Tech Stack

Python, SQLite, Streamlit, pandas, pytest.

## Author

**Yashas K** — MCA, REVA University, Bengaluru
GitHub: [yashaskshetty](https://github.com/yashaskshetty)
