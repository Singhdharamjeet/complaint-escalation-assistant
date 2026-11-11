import os, tempfile, unittest
from pathlib import Path
from escalation import EscalationWorkflow, TicketStore, load_sample_complaints
from escalation.loader import SAMPLE_PATH

HEADER = "complaint_id,customer_id,tier,prior_contacts,complaint_text,expected_escalate,expected_category\n"


def write_csv(content, encoding="utf-8"):
    f = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
    f.write(content.encode(encoding)); f.close()
    return f.name


class TestSampleLoader(unittest.TestCase):
    def setUp(self):
        self.wf = EscalationWorkflow(TicketStore())
        self.tmp = []

    def tearDown(self):
        for p in self.tmp:
            os.remove(p)

    def csv(self, content, encoding="utf-8"):
        p = write_csv(content, encoding); self.tmp.append(p); return p

    def count(self):
        return self.wf.store.conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

    def test_loads_all_real_samples(self):
        rep = load_sample_complaints(self.wf)
        self.assertTrue(rep.ok); self.assertEqual((rep.total, rep.loaded), (28, 28)); self.assertEqual(self.count(), 28)

    def test_second_click_does_not_duplicate(self):
        load_sample_complaints(self.wf)
        rep = load_sample_complaints(self.wf)
        self.assertEqual((rep.loaded, rep.skipped_duplicates), (0, 28)); self.assertEqual(self.count(), 28)

    def test_missing_file_reports_instead_of_crashing(self):
        rep = load_sample_complaints(self.wf, path="/no/such/file.csv")
        self.assertIn("not found", rep.fatal); self.assertFalse(rep.ok); self.assertEqual(self.count(), 0)

    def test_missing_required_column(self):
        p = self.csv("customer_id,tier\nC1,gold\n")
        self.assertIn("complaint_text", load_sample_complaints(self.wf, p).fatal)

    def test_empty_file_and_header_only(self):
        self.assertTrue(load_sample_complaints(self.wf, self.csv("")).fatal)
        self.assertIn("no complaint rows", load_sample_complaints(self.wf, self.csv(HEADER)).fatal)

    def test_bad_rows_are_reported_but_good_rows_still_load(self):
        p = self.csv(HEADER +
                     '1,C1,standard,0,"I will contact my lawyer",1,legal_threat\n'
                     '2,C2,platinum,0,"Bad tier",0,general\n'
                     '3,C3,standard,abc,"Bad number",0,general\n'
                     '4,,standard,0,"No customer",0,general\n'
                     '5,C5,standard,0,,0,general\n'
                     '6,C6,gold,1,"Where is my invoice?",0,general\n')
        rep = load_sample_complaints(self.wf, p)
        self.assertEqual((rep.total, rep.loaded, len(rep.errors)), (6, 2, 4))
        self.assertFalse(rep.ok); self.assertEqual(self.count(), 2)
        self.assertEqual([n for n, _ in rep.errors], [3, 4, 5, 6])      # CSV line numbers (header = line 1)

    def test_excel_bom_and_missing_optional_columns(self):
        p = self.csv("\ufeffcustomer_id,complaint_text\nC1,Where is my invoice?\n", encoding="utf-8")
        rep = load_sample_complaints(self.wf, p)
        self.assertEqual((rep.ok, rep.loaded), (True, 1))

    def test_short_row_does_not_crash(self):
        p = self.csv(HEADER + '1,C1\n2,C2,standard,0,"Where is my invoice?",0,general\n')
        rep = load_sample_complaints(self.wf, p)
        self.assertEqual(rep.loaded, 1); self.assertEqual(len(rep.errors), 1)

    def test_invalid_encoding_reported(self):
        p = self.csv(HEADER + '1,C1,standard,0,"caf\xe9 problem",0,general\n', encoding="latin-1")
        rep = load_sample_complaints(self.wf, p)
        self.assertTrue(rep.fatal or rep.loaded == 1)       # must not raise either way

    def test_database_failure_reported(self):
        self.wf.store.conn.close()
        rep = load_sample_complaints(self.wf)
        self.assertIn("database", rep.fatal)

    def test_summary_text(self):
        rep = load_sample_complaints(self.wf)
        self.assertIn("28 of 28", rep.summary())

    def test_sample_file_ships_with_project(self):
        self.assertTrue(Path(SAMPLE_PATH).is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)