import tempfile
import unittest
import zipfile
from pathlib import Path
from omega_actions.ultimate.skills_inventory import inventory, SkillArchiveError

class SkillsInventoryTests(unittest.TestCase):
    def archive(self, members):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "skills.zip"
        with zipfile.ZipFile(path, "w") as out:
            for name, data in members:
                out.writestr(name, data)
        return path

    def test_counts_skill_and_hashes_contents(self):
        result = inventory(self.archive([("bundle/foo/SKILL.md", b"hello")]))
        self.assertEqual(result["skill_count"], 1)
        self.assertEqual(result["skills"][0]["bytes"], 5)
        self.assertEqual(len(result["skills"][0]["sha256"]), 64)

    def test_rejects_traversal(self):
        with self.assertRaises(SkillArchiveError):
            inventory(self.archive([("../SKILL.md", b"x")]))

    def test_rejects_case_insensitive_duplicates(self):
        with self.assertRaises(SkillArchiveError):
            inventory(self.archive([("A/SKILL.md", b"a"), ("a/skill.md", b"b")]))

    def test_rejects_size_limit(self):
        with self.assertRaises(SkillArchiveError):
            inventory(self.archive([("a/SKILL.md", b"123")]), max_total_bytes=2)

    def test_rejects_invalid_utf8(self):
        with self.assertRaises(SkillArchiveError):
            inventory(self.archive([("a/SKILL.md", b"\xff")]))

    def test_does_not_count_other_files(self):
        self.assertEqual(inventory(self.archive([("README.md", b"ok")]))["skill_count"], 0)
