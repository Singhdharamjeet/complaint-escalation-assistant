"""Complaint -> Risk Analysis -> Escalation Flag -> Senior Queue -> Status Tracking."""

from datetime import datetime, timedelta, timezone
from . import config as C
from .analyzer import ComplaintAnalyzer
from .db import TicketStore

class InvalidTransition(ValueError):
    pass

class EscalationWorkflow:
    def __init__(self, store: TicketStore = None, analyzer: ComplaintAnalyzer = None):
        self.store = store or TicketStore()
        self.analyzer = analyzer or ComplaintAnalyzer()

    def submit_complaint(self, customer_id, text, customer_name="", tier="standard", prior_contacts=0):
        """Analyse, flag, create CRM ticket, and route to the right queue."""
        if not text or not text.strip():
            raise ValueError("complaint text is empty")
        r = self.analyzer.analyze(text, prior_contacts=prior_contacts, tier=tier)
        status = "ESCALATED" if r.escalate else "OPEN"
        queue = C.QUEUES["senior" if r.escalate else "standard"]
        sla = None
        if r.escalate:
            sla = (datetime.now(timezone.utc) + timedelta(hours=C.SLA_HOURS[r.level])).replace(microsecond=0).isoformat()
        tid = self.store.insert_ticket(
            customer_id=customer_id, customer_name=customer_name, tier=tier, prior_contacts=prior_contacts,
            complaint_text=text.strip(), primary_category=r.primary_category, risk_score=r.score,
            risk_level=r.level, escalated=int(r.escalate), escalation_reason="; ".join(r.reasons), queue=queue,
            status=status, sla_due_at=sla)
        note = f"Auto-created. Risk {r.score} ({r.level})." + (" Escalated to senior queue." if r.escalate else "")
        self.store.add_history(tid, None, status, note)
        return tid, r

    def senior_queue(self):
        return self.store.queue(C.QUEUES["senior"])

    def assign(self, ticket_id, agent):
        t = self._must_get(ticket_id)
        self.store.update(ticket_id, assigned_to=agent)
        if t["status"] in ("OPEN", "ESCALATED"):
            self.update_status(ticket_id, "IN_PROGRESS", note=f"Assigned to {agent}", actor=agent)

    def update_status(self, ticket_id, new_status, note="", actor="agent"):
        t = self._must_get(ticket_id)
        new_status = new_status.upper()
        if new_status not in C.STATUSES:
            raise InvalidTransition(f"unknown status {new_status}")
        if new_status not in C.TRANSITIONS[t["status"]]:
            raise InvalidTransition(f"{t['status']} -> {new_status} not allowed")
        fields = {"status": new_status}
        if new_status == "ESCALATED":                           # manual escalation 
            fields.update(queue=C.QUEUES["senior"], escalated=1)
        self.store.update(ticket_id, **fields)
        self.store.add_history(ticket_id, t["status"], new_status, note, actor)

    def manual_escalate(self, ticket_id, reason, actor="agent"):
        self.update_status(ticket_id, "ESCALATED", note=f"Manual escalation: {reason}", actor=actor)

    def _must_get(self, ticket_id):
        t = self.store.get(ticket_id)
        if t is None:
            raise KeyError(f"ticket {ticket_id} not found")
        return t

