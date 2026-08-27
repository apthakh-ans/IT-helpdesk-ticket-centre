"""Seeds the helpdesk DB with sample agents, customers, and a few manual tickets."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402


def main():
    db.DB_PATH.unlink(missing_ok=True)
    db.init_db()

    agents = [
        db.add_agent("Priya Nair", "priya.nair@helpdesk.local"),
        db.add_agent("Rohit Verma", "rohit.verma@helpdesk.local"),
    ]

    customers = [
        db.add_customer("Alice Fernandes", "alice@northbank.com", "NorthBank"),
        db.add_customer("Brian D'Souza", "brian@northbank.com", "NorthBank"),
        db.add_customer("Chetan Rao", "chetan@unioncu.com", "Union Credit Union"),
    ]

    tickets = [
        (customers[0], "Cannot log in to online banking portal", "User gets 'invalid session' error on every login attempt since this morning.", "P1", agents[0]),
        (customers[1], "Statement PDF not downloading", "Clicking 'Download Statement' spins forever, no file downloads.", "P2", agents[1]),
        (customers[2], "Request to update registered phone number", "Customer wants to change the phone number linked to their account.", "P3", None),
        (customers[0], "Fund transfer stuck in pending", "A transfer initiated yesterday is still showing 'Pending', funds already debited.", "P1", agents[0]),
    ]

    for customer_id, subject, description, priority, agent_id in tickets:
        ticket_id = db.create_ticket(customer_id, subject, description, priority, agent_id=agent_id)
        print(f"Created ticket #{ticket_id}: {subject} ({priority})")

    print(f"\nSeeded {len(agents)} agents, {len(customers)} customers, {len(tickets)} tickets.")


if __name__ == "__main__":
    main()
