import csv
from dataclasses import dataclass, field
from pathlib import Path

from . import config as C

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "complaints.csv"
REQUIRED_COLUMNS = {"customer_id", "complaint_text"}


@dataclass
class LoadReport:
    total: int = 0                                   # rows found in the file
    loaded: int = 0                                  # tickets created
    skipped_duplicates: int = 0                      # already in the database
    errors: list = field(default_factory=list)       # [(csv_line_number, message)]
    fatal: str = ""                                  # file-level problem (nothing loaded)
    detail: str = ""                                 # technical traceback, if any

    @property
    def ok(self) -> bool:
        return not self.fatal and not self.errors

    def summary(self) -> str:
        if self.fatal:
            return f"Sample loading FAILED: {self.fatal}"
        parts = [f"{self.loaded} of {self.total} sample complaints loaded"]
        if self.skipped_duplicates:
            parts.append(f"{self.skipped_duplicates} already existed (skipped)")
        if self.errors:
            parts.append(f"{len(self.errors)} row(s) failed")
        return ", ".join(parts) + "."


def load_sample_complaints(workflow, path=SAMPLE_PATH, skip_duplicates=True) -> LoadReport:
    report = LoadReport()
    path = Path(path)

    # ---- 1. read and validate the file -------------------------------------
    if not path.is_file():
        report.fatal = f"sample file not found at '{path}'. Check that the data folder was uploaded."
        return report
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:     # utf-8-sig also handles Excel's BOM
            reader = csv.DictReader(fh)
            headers = {(h or "").strip() for h in (reader.fieldnames or [])}
            missing = REQUIRED_COLUMNS - headers
            if missing:
                report.fatal = f"the CSV is missing required column(s): {', '.join(sorted(missing))}."
                return report
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        report.fatal = f"could not read the CSV file ({type(exc).__name__}: {exc})."
        return report
    if not rows:
        report.fatal = "the CSV file has no complaint rows."
        return report
    report.total = len(rows)

    # ---- 2. what is already in the database (to avoid duplicates) ----------
    existing = set()
    if skip_duplicates:
        try:
            existing = {(r["customer_id"], r["complaint_text"])
                        for r in workflow.store.query("SELECT customer_id, complaint_text FROM tickets")}
        except Exception as exc:  # database problem: report it instead of crashing
            report.fatal = f"could not read the ticket database ({type(exc).__name__}: {exc})."
            return report

    # ---- 3. process row by row: one bad row must not stop the others --------
    for line_no, raw in enumerate(rows, start=2):                    # line 1 is the header
        try:
            row = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
            cid, text = row.get("customer_id", ""), row.get("complaint_text", "")
            if not cid:
                raise ValueError("customer_id is empty")
            if not text:
                raise ValueError("complaint_text is empty")
            tier = (row.get("tier") or "standard").lower()
            if tier not in C.TIER_POINTS:
                raise ValueError(f"unknown tier '{tier}'")
            prior = int(row.get("prior_contacts") or 0)
            if prior < 0:
                raise ValueError("prior_contacts cannot be negative")
            if (cid, text) in existing:
                report.skipped_duplicates += 1
                continue
            workflow.submit_complaint(cid, text, tier=tier, prior_contacts=prior)
            existing.add((cid, text))
            report.loaded += 1
        except Exception as exc:  # deliberate catch-all: record the row, keep going
            report.errors.append((line_no, f"{type(exc).__name__}: {exc}"))
    return report