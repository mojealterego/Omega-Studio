import asyncio
import tempfile
import unittest
from pathlib import Path
from omega_actions.config import Settings
from omega_actions.engine import Engine
from omega_actions.storage import StateStore

class EngineTests(unittest.TestCase):
    def test_dag_matrix_artifacts_outputs_and_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); repo=root/'repo'; repo.mkdir()
            (repo/'ci.yml').write_text('''name: Integration
on: [push]
jobs:
  build:
    strategy:
      matrix:
        language: [python, rust, typescript]
    steps:
      - run: |
          echo "token=${{ secrets.API_TOKEN }}"
          echo "LANG=${{ matrix.language }}" >> "$GITHUB_ENV"
          echo "result=ok" >> "$GITHUB_OUTPUT"
          echo "${{ matrix.language }}" > "${{ matrix.language }}.txt"
      - uses: actions/upload-artifact@v4
        with:
          name: out-${{ matrix.language }}
          path: '*.txt'
  finish:
    needs: build
    steps:
      - run: echo finished
''')
            settings=Settings(root/'home',unsafe_native=True,max_parallel=3)
            settings.prepare()
            engine=Engine(settings,StateStore(settings.home/'state.db'))
            result=asyncio.run(engine.run(repo/'ci.yml',repo,secrets={'API_TOKEN':'VERYSECRET'}))
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(len(result['jobs']),4)
            self.assertNotIn('VERYSECRET',str(engine.store.logs(result['id'])))
            self.assertEqual(len(list((settings.home/'artifacts'/result['id']).glob('*.zip'))),3)

    def test_failed_dependency_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); repo=root/'repo'; repo.mkdir()
            (repo/'ci.yml').write_text('''jobs:
  broken:
    steps:
      - run: exit 7
  after:
    needs: broken
    steps:
      - run: echo must-not-run
''')
            s=Settings(root/'home',unsafe_native=True); s.prepare()
            result=asyncio.run(Engine(s,StateStore(s.home/'state.db')).run(repo/'ci.yml',repo))
            self.assertEqual(result['status'],'failure')
            self.assertEqual(result['jobs']['after'],'skipped')

if __name__=='__main__': unittest.main()
