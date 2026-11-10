import asyncio
import tempfile
import unittest
from pathlib import Path
from omega_actions.config import Settings
from omega_actions.engine import Engine
from omega_actions.storage import StateStore

class RuntimeTests(unittest.TestCase):
    def test_job_outputs_and_needs(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=p/'repo';r.mkdir()
            (r/'ci.yml').write_text('''jobs:
  producer:
    outputs:
      version: ${{ steps.version.outputs.number }}
    steps:
      - id: version
        run: echo 'number=42' >> "$GITHUB_OUTPUT"
  consumer:
    needs: producer
    if: ${{ needs.producer.outputs.version == '42' }}
    steps:
      - run: test "${{ needs.producer.outputs.version }}" = '42'
''')
            s=Settings(p/'state',unsafe_native=True)
            result=asyncio.run(Engine(s).run(r/'ci.yml',r))
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(result['jobs']['consumer'],'success')
    def test_timeout_kills_job(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=p/'repo';r.mkdir()
            (r/'ci.yml').write_text('''jobs:
  slow:
    steps:
      - run: sleep 5
        timeout-minutes: 0
''')
            s=Settings(p/'state',unsafe_native=True)
            # Per-step minimum is 1 second, so this test runs for ~1s.
            result=asyncio.run(Engine(s).run(r/'ci.yml',r))
            self.assertEqual(result['status'],'failure')
    def test_untrusted_native_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=p/'repo';r.mkdir()
            (r/'ci.yml').write_text('jobs:\n  test:\n    steps:\n      - run: echo no\n')
            result=asyncio.run(Engine(Settings(p/'state')).run(r/'ci.yml',r))
            self.assertEqual(result['status'],'failure')

if __name__=='__main__':unittest.main()
