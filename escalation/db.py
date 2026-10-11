import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    customer_name TEXT,
    tier TEXT DEFAULT 'standard',
    prior_contacts INTEGER DEFAULT 0,
    complaint_text TEXT NOT NULL,
    primary_category TEXT,
    risk_score REAL DEFAULT 0,
    risk_level TEXT DEFAULT 'LOW',
    escalated INTEGER DEFAULT 0,
    escalation_reason TEXT,
    queue TEXT DEFAULT 'STANDARD_SUPPORT',
    status TEXT DEFAULT 'OPEN',
    assigned_to TEXT,
    sla_due_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id),
    old_status TEXT, new_status TEXT NOT NULL,
    note TEXT, actor TEXT, changed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickets_queue_status ON tickets(queue, status);
"""


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class TicketStore:
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def insert_ticket(self, **f) -> int:
        t = now()
        cur = self.conn.execute(
            """INSERT INTO tickets (customer_id, customer_name, tier, prior_contacts, complaint_text,
               primary_category, risk_score, risk_level, escalated, escalation_reason, queue, status,
               sla_due_at, created_at, updated_at)
               VALUES (:customer_id,:customer_name,:tier,:prior_contacts,:complaint_text,:primary_category,
               :risk_score,:risk_level,:escalated,:escalation_reason,:queue,:status,:sla_due_at,:created_at,:updated_at)""",
            {**f, "created_at": t, "updated_at": t},
        )
        self.conn.commit()
        return cur.lastrowid

    def get(self, ticket_id: int):
        return self.conn.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()

    def update(self, ticket_id: int, **fields):
        fields["updated_at"] = now()
        sets = ", ".join(f"{k}=:{k}" for k in fields)
        self.conn.execute(f"UPDATE tickets SET {sets} WHERE ticket_id=:id", {**fields, "id": ticket_id})
        self.conn.commit()

    def add_history(self, ticket_id, old, new, note="", actor="system"):
        self.conn.execute(
            "INSERT INTO ticket_history (ticket_id, old_status, new_status, note, actor, changed_at) VALUES (?,?,?,?,?,?)",
            (ticket_id, old, new, note, actor, now()))
        self.conn.commit()

    def history(self, ticket_id):
        return self.conn.execute("SELECT * FROM ticket_history WHERE ticket_id=? ORDER BY id", (ticket_id,)).fetchall()

    def queue(self, queue_name, statuses=("ESCALATED", "IN_PROGRESS")):
        q = ",".join("?" * len(statuses))
        return self.conn.execute(
            f"""SELECT * FROM tickets WHERE queue=? AND status IN ({q})
                ORDER BY risk_score DESC, created_at ASC""", (queue_name, *statuses)).fetchall()

    def summary(self):
        return self.conn.execute(
            "SELECT queue, status, COUNT(*) n FROM tickets GROUP BY queue, status ORDER BY queue, status").fetchall()