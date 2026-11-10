import struct
import tempfile
import unittest
from pathlib import Path

from omega_actions.ultimate.gguf_inspector import GGUFError, inspect_gguf


class GGUFInspectorTests(unittest.TestCase):
    def inspect(self, content: bytes):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'model.gguf'
            path.write_bytes(content)
            return inspect_gguf(path)

    def test_valid_empty_v3_header(self):
        result = self.inspect(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
        self.assertEqual(result['version'], 3)
        self.assertEqual(result['tensor_count'], 0)
        self.assertEqual(result['metadata_count'], 0)

    def test_rejects_invalid_magic(self):
        with self.assertRaises(GGUFError):
            self.inspect(b'NOPE' + struct.pack('<IQQ', 3, 0, 0))

    def test_rejects_truncated_header(self):
        with self.assertRaises(GGUFError):
            self.inspect(b'GGUF\x03')

    def test_rejects_unsupported_version(self):
        with self.assertRaises(GGUFError):
            self.inspect(b'GGUF' + struct.pack('<IQQ', 999, 0, 0))

    def test_rejects_unbounded_counts(self):
        with self.assertRaises(GGUFError):
            self.inspect(b'GGUF' + struct.pack('<IQQ', 3, 10**12, 0))

    def test_reports_metadata_count_without_parsing_payload(self):
        result = self.inspect(b'GGUF' + struct.pack('<IQQ', 3, 0, 1))
        self.assertEqual(result['metadata_count'], 1)


if __name__ == '__main__':
    unittest.main()
