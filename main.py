import csv, sys
from pathlib import Path
from escalation import EscalationWorkflow, TicketStore
from escalation.nlp import NLTK_AVAILABLE

DB = Path(__file__).parent / "crm.db"
DATA = Path(__file__).parent / "data" / "complaints.csv"


def demo():
    DB.unlink(missing_ok=True)
    wf = EscalationWorkflow(TicketStore(str(DB)))
    print(f"NLTK available: {NLTK_AVAILABLE}\n")
    with open(DATA, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid, r = wf.submit_complaint(row["customer_id"], row["complaint_text"], tier=row["tier"],
                                         prior_contacts=int(row["prior_contacts"]))
            print(f"#{tid:<3} {r.level:<8} score={r.score:<5} escalate={'YES' if r.escalate else 'no ':<3} {r.primary_category}")
    print("\n--- SENIOR QUEUE (highest risk first) ---")
    for t in wf.senior_queue():
        print(f"#{t['ticket_id']:<3} {t['risk_level']:<8} {t['risk_score']:<5} SLA {t['sla_due_at']}  {t['complaint_text'][:60]}")

# status tracking walkthrough

    top = wf.senior_queue()[0]["ticket_id"]
    wf.assign(top, "senior_agent_1"); wf.update_status(top, "RESOLVED", "Issue fixed, customer contacted"); wf.update_status(top, "CLOSED")
    print(f"\n--- HISTORY for ticket #{top} ---")
    for h in wf.store.history(top):
        print(f"{h['changed_at']}  {h['old_status']} -> {h['new_status']}  ({h['actor']}) {h['note']}")
    print("\n--- SUMMARY ---")
    for s in wf.store.summary():
        print(f"{s['queue']:<18} {s['status']:<12} {s['n']}")

def analyze(text):
    from escalation import ComplaintAnalyzer
    r = ComplaintAnalyzer().analyze(text)
    print(f"score={r.score} level={r.level} escalate={r.escalate} category={r.primary_category}")
    for x in r.reasons:
        print(" -", x)

def queue():
    wf = EscalationWorkflow(TicketStore(str(DB)))
    for t in wf.senior_queue():
        print(f"#{t['ticket_id']} {t['risk_level']} {t['risk_score']} {t['status']} {t['complaint_text'][:70]}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    {"demo": demo, "queue": queue}.get(cmd, lambda: analyze(" ".join(sys.argv[2:])))()