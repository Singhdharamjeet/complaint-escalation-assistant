import csv, unittest
from pathlib import Path
from escalation import ComplaintAnalyzer, EscalationWorkflow, TicketStore
from escalation.workflow import InvalidTransition

DATA = Path(__file__).resolve().parent.parent / "data" / "complaints.csv"
A = ComplaintAnalyzer()


def load_rows():
    with open(DATA, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class TestRiskScoring(unittest.TestCase):
    def test_neutral_complaint_low(self):
        r = A.analyze("My order arrived two days late.")
        self.assertEqual((r.level, r.escalate, r.score), ("LOW", False, 0.0))

    def test_legal_threat_auto_escalates(self):
        r = A.analyze("I will contact my lawyer.")
        self.assertTrue(r.escalate); self.assertEqual(r.primary_category, "legal_threat")

    def test_safety_auto_escalates(self):
        self.assertTrue(A.analyze("The heater caught fire").escalate)

    def test_fraud_auto_escalates(self):
        self.assertTrue(A.analyze("There is an unauthorized transaction on my card").escalate)

    def test_billing_alone_not_escalated(self):
        r = A.analyze("I was charged twice, please refund.")
        self.assertFalse(r.escalate); self.assertEqual(r.primary_category, "billing_dispute")

    def test_stacked_signals_escalate(self):
        r = A.analyze("I was overcharged and nobody replied. Refund me immediately or I will cancel my account.")
        self.assertTrue(r.escalate)

    def test_caps_and_exclamations_add_points(self):
        base = A.analyze("this service is pathetic and I am fed up with it").score
        loud = A.analyze("THIS SERVICE IS PATHETIC AND I AM FED UP WITH IT!!!").score
        self.assertGreater(loud, base)

    def test_prior_contacts_and_tier_increase_score(self):
        t = "The router is broken and still not working."
        self.assertGreater(A.analyze(t, prior_contacts=4, tier="vip").score, A.analyze(t).score)

    def test_deescalation_lowers_score(self):
        self.assertLess(A.analyze("Refund was late but thank you, it is resolved now").score,
                        A.analyze("Refund was late").score)

    def test_deescalation_never_overrides_hard_risk(self):
        self.assertTrue(A.analyze("Thanks, but my lawyer will be in touch.").escalate)

    def test_empty_and_none_text(self):
        self.assertEqual(A.analyze("").score, 0.0); self.assertEqual(A.analyze(None).score, 0.0)

    def test_case_insensitive_and_punctuation(self):
        self.assertTrue(A.analyze("LAWYER!!!").escalate)

    def test_no_false_positive_on_substrings(self):
        self.assertFalse(A.analyze("The courtesy call and the hospitality were great").escalate)

    def test_critical_level_threshold(self):
        r = A.analyze("I will post on social media and file a legal case. URGENT, this is the third time!")
        self.assertEqual(r.level, "CRITICAL")

    def test_reasons_explain_decision(self):
        self.assertTrue(any("legal_threat" in x for x in A.analyze("my attorney").reasons))


class TestDataset(unittest.TestCase):
    def test_dataset_accuracy(self):
        rows = load_rows()
        self.assertGreaterEqual(len(rows), 25)
        wrong = []
        for r in rows:
            res = A.analyze(r["complaint_text"], int(r["prior_contacts"]), r["tier"])
            if res.escalate != bool(int(r["expected_escalate"])):
                wrong.append(r["complaint_id"])
        self.assertEqual(wrong, [], f"misclassified: {wrong}")

    def test_dataset_categories(self):
        rows = load_rows()
        wrong = [r["complaint_id"] for r in rows
                 if A.analyze(r["complaint_text"], int(r["prior_contacts"]), r["tier"]).primary_category != r["expected_category"]]
        self.assertEqual(wrong, [], f"wrong category: {wrong}")


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        self.wf = EscalationWorkflow(TicketStore())

    def test_high_risk_goes_to_senior_queue(self):
        tid, r = self.wf.submit_complaint("C1", "I will sue you", tier="gold")
        t = self.wf.store.get(tid)
        self.assertEqual((t["queue"], t["status"], t["escalated"]), ("SENIOR_SUPPORT", "ESCALATED", 1))
        self.assertIsNotNone(t["sla_due_at"])

    def test_low_risk_stays_standard(self):
        tid, _ = self.wf.submit_complaint("C2", "Where is my invoice?")
        t = self.wf.store.get(tid)
        self.assertEqual((t["queue"], t["status"], t["escalated"]), ("STANDARD_SUPPORT", "OPEN", 0))
        self.assertIsNone(t["sla_due_at"])

    def test_senior_queue_sorted_by_risk(self):
        self.wf.submit_complaint("A", "I will contact my lawyer")
        self.wf.submit_complaint("B", "Phone exploded, I was injured, urgent! My lawyer will sue.")
        scores = [t["risk_score"] for t in self.wf.senior_queue()]
        self.assertEqual(scores, sorted(scores, reverse=True)); self.assertEqual(len(scores), 2)

    def test_status_lifecycle_and_history(self):
        tid, _ = self.wf.submit_complaint("C3", "My lawyer will call you")
        self.wf.assign(tid, "agent7")
        self.wf.update_status(tid, "resolved", "fixed"); self.wf.update_status(tid, "CLOSED")
        self.assertEqual(self.wf.store.get(tid)["status"], "CLOSED")
        self.assertEqual([h["new_status"] for h in self.wf.store.history(tid)],
                         ["ESCALATED", "IN_PROGRESS", "RESOLVED", "CLOSED"])
        self.assertEqual(self.wf.store.get(tid)["assigned_to"], "agent7")

    def test_invalid_transition_rejected(self):
        tid, _ = self.wf.submit_complaint("C4", "Where is my invoice?")
        with self.assertRaises(InvalidTransition): self.wf.update_status(tid, "CLOSED")
        with self.assertRaises(InvalidTransition): self.wf.update_status(tid, "BOGUS")

    def test_closed_is_final(self):
        tid, _ = self.wf.submit_complaint("C5", "Where is my invoice?")
        self.wf.update_status(tid, "RESOLVED"); self.wf.update_status(tid, "CLOSED")
        with self.assertRaises(InvalidTransition): self.wf.update_status(tid, "IN_PROGRESS")

    def test_manual_escalation(self):
        tid, _ = self.wf.submit_complaint("C6", "Where is my invoice?")
        self.wf.manual_escalate(tid, "VIP asked for manager")
        t = self.wf.store.get(tid)
        self.assertEqual((t["queue"], t["status"]), ("SENIOR_SUPPORT", "ESCALATED"))

    def test_resolved_ticket_leaves_senior_queue(self):
        tid, _ = self.wf.submit_complaint("C7", "My lawyer will call you")
        self.wf.update_status(tid, "RESOLVED")
        self.assertEqual(len(self.wf.senior_queue()), 0)

    def test_empty_complaint_and_missing_ticket(self):
        with self.assertRaises(ValueError): self.wf.submit_complaint("C8", "   ")
        with self.assertRaises(KeyError): self.wf.update_status(999, "RESOLVED")


if __name__ == "__main__":
    unittest.main(verbosity=2)