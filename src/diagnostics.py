"""
Log-diagnostics: parses a server log file, groups repeated errors/warnings
(so a burst of the same error doesn't flood the queue with duplicate tickets),
and auto-opens tickets for anything that crosses a severity/frequency threshold.

Severity policy:
    CRITICAL           -> always P1 (service-down class issues)
    ERROR              -> always P2
    WARNING (>=2 times) -> P3 (a one-off warning is noise; a repeated one is a trend)
    WARNING (1 time)    -> logged, not ticketed
    INFO                -> ignored
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|WARNING|ERROR|CRITICAL)\s+"
    r"(?P<message>.+)$"
)


def parse_log(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = LOG_LINE_RE.match(line)
            if match:
                entries.append(match.groupdict())
            else:
                entries.append({"timestamp": None, "level": "UNPARSED", "message": line})
    return entries


def group_by_message(entries, levels):
    groups = defaultdict(list)
    for e in entries:
        if e["level"] in levels:
            groups[(e["level"], e["message"])].append(e["timestamp"])
    return groups


def decide_priority(level, occurrences):
    if level == "CRITICAL":
        return "P1"
    if level == "ERROR":
        return "P2"
    if level == "WARNING" and occurrences >= 2:
        return "P3"
    return None


def ticket_already_open(subject):
    open_tickets = db.list_tickets()
    return any(
        t["subject"] == subject and t["status"] not in ("Resolved", "Closed")
        for t in open_tickets
    )


def run_diagnostics(log_path, verbose=True):
    entries = parse_log(log_path)
    groups = group_by_message(entries, levels={"WARNING", "ERROR", "CRITICAL"})
    system_customer_id = db.get_or_create_system_customer()

    created = []
    for (level, message), timestamps in groups.items():
        priority = decide_priority(level, len(timestamps))
        if priority is None:
            if verbose:
                print(f"[skip]   {level:<9} x{len(timestamps)}  {message}")
            continue

        subject = f"[{level}] {message[:90]}"
        if ticket_already_open(subject):
            if verbose:
                print(f"[dup]    {level:<9} x{len(timestamps)}  {message} (open ticket already exists)")
            continue

        description = (
            f"Detected {len(timestamps)} occurrence(s) of this {level} log line.\n"
            f"First seen: {timestamps[0]}\n"
            f"Last seen:  {timestamps[-1]}\n\n"
            f"Raw message: {message}"
        )
        ticket_id = db.create_ticket(
            customer_id=system_customer_id,
            subject=subject,
            description=description,
            priority=priority,
            source="auto-diagnostic",
        )
        created.append(ticket_id)
        if verbose:
            print(f"[ticket] {level:<9} x{len(timestamps)}  {message} -> ticket #{ticket_id} ({priority})")

    return created


if __name__ == "__main__":
    log_file = Path(__file__).resolve().parent.parent / "data" / "sample_logs" / "app_server.log"
    print(f"Running diagnostics on {log_file}\n")
    new_tickets = run_diagnostics(log_file)
    print(f"\n{len(new_tickets)} new ticket(s) created: {new_tickets}")
