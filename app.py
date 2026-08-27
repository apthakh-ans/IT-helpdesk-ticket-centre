"""Streamlit UI for the IT Helpdesk Ticket System — agent-facing ticket queue."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import db  # noqa: E402
import diagnostics  # noqa: E402

st.set_page_config(page_title="IT Helpdesk", page_icon="🎫", layout="wide")

if not db.DB_PATH.exists():
    db.init_db()

PRIORITY_COLOR = {"P1": "🔴", "P2": "🟠", "P3": "🟡"}
STATUS_OPTIONS = ["Open", "In Progress", "Resolved", "Closed"]

st.title("🎫 IT Helpdesk — Ticket Queue")

with st.sidebar:
    st.header("Filters")
    status_filter = st.selectbox("Status", ["All"] + STATUS_OPTIONS)
    priority_filter = st.selectbox("Priority", ["All", "P1", "P2", "P3"])

    st.divider()
    st.header("Diagnostics")
    st.caption("Parses the sample server log and auto-opens tickets for errors/repeated warnings.")
    if st.button("Run log diagnostics"):
        log_path = Path(__file__).resolve().parent / "data" / "sample_logs" / "app_server.log"
        new_ids = diagnostics.run_diagnostics(log_path, verbose=False)
        if new_ids:
            st.success(f"Created {len(new_ids)} new ticket(s): {new_ids}")
        else:
            st.info("No new tickets — nothing crossed the severity/frequency threshold, or tickets already open.")
        st.rerun()

tickets = db.list_tickets(
    status=None if status_filter == "All" else status_filter,
    priority=None if priority_filter == "All" else priority_filter,
)

if not tickets:
    st.info("No tickets match the current filter.")
else:
    df = pd.DataFrame(tickets)
    df["breached"] = df.apply(lambda r: db.is_breached(r["sla_due_at"], r["status"]), axis=1)

    open_count = sum(1 for t in tickets if t["status"] in ("Open", "In Progress"))
    breached_count = int(df["breached"].sum())
    col1, col2, col3 = st.columns(3)
    col1.metric("Tickets shown", len(tickets))
    col2.metric("Open / In Progress", open_count)
    col3.metric("SLA breached", breached_count, delta=None)

    st.divider()

    for t in tickets:
        breached = db.is_breached(t["sla_due_at"], t["status"])
        badge = "🔥 SLA BREACHED" if breached else ""
        header = f"{PRIORITY_COLOR[t['priority']]} #{t['ticket_id']} · {t['subject']} — {t['status']} {badge}"

        with st.expander(header):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**Customer:** {t['customer_name']}")
                st.write(f"**Description:** {t['description']}")
                st.write(f"**Source:** {t['source']}")
            with c2:
                st.write(f"**Priority:** {t['priority']}")
                st.write(f"**Agent:** {t['agent_name'] or 'Unassigned'}")
                st.write(f"**Created:** {t['created_at']}")
                st.write(f"**SLA due:** {t['sla_due_at']}")

            new_status = st.selectbox(
                "Update status", STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(t["status"]),
                key=f"status_{t['ticket_id']}",
            )
            note = st.text_input("Note (optional)", key=f"note_{t['ticket_id']}")
            if st.button("Save", key=f"save_{t['ticket_id']}"):
                if new_status != t["status"]:
                    db.update_ticket_status(t["ticket_id"], new_status, note=note or None)
                    st.rerun()

            history = db.get_ticket_history(t["ticket_id"])
            if history:
                st.caption("History")
                st.dataframe(
                    pd.DataFrame(history)[["changed_at", "old_status", "new_status", "note"]],
                    hide_index=True, use_container_width=True,
                )
