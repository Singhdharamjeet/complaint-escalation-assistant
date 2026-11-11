import os, tempfile, threading, unittest
from escalation import EscalationWorkflow, TicketStore, load_sample_complaints


class TestThreadSafety(unittest.TestCase):
    def hammer(self, wf, threads=8, per_thread=40):
        errors = []

        def worker(i):
            for j in range(per_thread):
                try:
                    wf.submit_complaint(f"C{i}", f"I will contact my lawyer {i}-{j}")
                    wf.store.scalar("SELECT COUNT(*) FROM tickets")
                    wf.senior_queue()
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}: {exc}")

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
        [t.start() for t in ts]; [t.join() for t in ts]
        return errors

    def test_concurrent_inserts_file_database(self):
        path = os.path.join(tempfile.mkdtemp(), "t.db")
        wf = EscalationWorkflow(TicketStore(path))
        self.assertEqual(self.hammer(wf), [])
        self.assertEqual(wf.store.scalar("SELECT COUNT(*) FROM tickets"), 8 * 40)

    def test_concurrent_inserts_memory_database(self):
        wf = EscalationWorkflow(TicketStore())
        self.assertEqual(self.hammer(wf), [])
        self.assertEqual(wf.store.scalar("SELECT COUNT(*) FROM tickets"), 8 * 40)

    def test_concurrent_sample_loads_create_no_errors(self):
        wf = EscalationWorkflow(TicketStore())
        reports = []
        ts = [threading.Thread(target=lambda: reports.append(load_sample_complaints(wf))) for _ in range(4)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertTrue(all(not r.fatal and not r.errors for r in reports))
        self.assertGreaterEqual(wf.store.scalar("SELECT COUNT(*) FROM tickets"), 28)

    def test_failed_write_rolls_back_and_store_keeps_working(self):
        wf = EscalationWorkflow(TicketStore())
        with self.assertRaises(Exception):
            wf.store.insert_ticket(customer_id=None)          
        tid, _ = wf.submit_complaint("C1", "Where is my invoice?")
        self.assertEqual(tid, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)