"""SQLite CRM ticket store with status history."""
import sqlite3
import threading
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
    """SQLite ticket store, safe to share between threads.

    Streamlit runs every user interaction in its own thread. One SQLite connection must not be used by
    two threads at the same time (it raises InterfaceError: "bad parameter or other API misuse"), so every
    database call below runs inside a single re-entrant lock.
    """

    def __init__(self, path=":memory:"):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)   # safe only because of self._lock
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)

    def query(self, sql, params=()):
        """Run a SELECT and return all rows (fetched while the lock is held)."""
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    def scalar(self, sql, params=()):
        """Run a SELECT that returns one value, e.g. COUNT(*)."""
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
            return row[0] if row else None

    def _write(self, sql, params=()):
        with self._lock:
            try:
                cur = self.conn.execute(sql, params)
                self.conn.commit()
                return cur.lastrowid
            except Exception:
                self.conn.rollback()
                raise

    def insert_ticket(self, **f) -> int:
        t = now()
        return self._write(
            """INSERT INTO tickets (customer_id, customer_name, tier, prior_contacts, complaint_text,
               primary_category, risk_score, risk_level, escalated, escalation_reason, queue, status,
               sla_due_at, created_at, updated_at)
               VALUES (:customer_id,:customer_name,:tier,:prior_contacts,:complaint_text,:primary_category,
               :risk_score,:risk_level,:escalated,:escalation_reason,:queue,:status,:sla_due_at,:created_at,:updated_at)""",
            {**f, "created_at": t, "updated_at": t})

    def get(self, ticket_id: int):
        rows = self.query("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,))
        return rows[0] if rows else None

    def update(self, ticket_id: int, **fields):
        fields["updated_at"] = now()
        sets = ", ".join(f"{k}=:{k}" for k in fields)
        self._write(f"UPDATE tickets SET {sets} WHERE ticket_id=:id", {**fields, "id": ticket_id})

    def add_history(self, ticket_id, old, new, note="", actor="system"):
        self._write(
            "INSERT INTO ticket_history (ticket_id, old_status, new_status, note, actor, changed_at) VALUES (?,?,?,?,?,?)",
            (ticket_id, old, new, note, actor, now()))

    def history(self, ticket_id):
        return self.query("SELECT * FROM ticket_history WHERE ticket_id=? ORDER BY id", (ticket_id,))

    def queue(self, queue_name, statuses=("ESCALATED", "IN_PROGRESS")):
        q = ",".join("?" * len(statuses))
        return self.query(
            f"""SELECT * FROM tickets WHERE queue=? AND status IN ({q})
                ORDER BY risk_score DESC, created_at ASC""", (queue_name, *statuses))

    def summary(self):
        return self.query(
            "SELECT queue, status, COUNT(*) n FROM tickets GROUP BY queue, status ORDER BY queue, status")