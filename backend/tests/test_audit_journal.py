import json
import tempfile
import unittest
from pathlib import Path
from omega_actions.ultimate.audit_journal import AuditJournal, AuditIntegrityError

class AuditJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "events.jsonl"
        self.journal = AuditJournal(self.path)

    def test_round_trip_and_chain(self):
        a = self.journal.append({"kind": "proposed"})
        b = self.journal.append({"kind": "rejected"})
        self.assertEqual(b["prev"], a["digest"])
        self.assertEqual(self.journal.verify(), (2, b["digest"]))

    def test_tamper_detected(self):
        self.journal.append({"kind": "approved"})
        self.path.write_bytes(self.path.read_bytes().replace(b"approved", b"rejected"))
        with self.assertRaises(AuditIntegrityError):
            self.journal.verify()

    def test_truncated_record_rejected(self):
        self.journal.append({"kind": "approved"})
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaises(AuditIntegrityError):
            self.journal.verify()

    def test_invalid_event_does_not_write(self):
        with self.assertRaises(ValueError):
            self.journal.append({"nan": float("nan")})
        self.assertFalse(self.path.exists())

    def test_empty(self):
        self.assertEqual(self.journal.verify(), (0, "0" * 64))

    def test_broken_sequence(self):
        self.journal.append({"kind": "a"})
        lines = self.path.read_text().splitlines()
        item = json.loads(lines[0])
        item["seq"] = 3
        self.path.write_text(json.dumps(item) + "\n")
        with self.assertRaises(AuditIntegrityError):
            self.journal.verify()
