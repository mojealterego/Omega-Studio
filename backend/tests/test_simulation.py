import asyncio
import tempfile
import unittest
from pathlib import Path
from omega_actions.simulator import synthetic_event,simulate
from omega_actions.config import Settings
from omega_actions.engine import Engine
from omega_actions.storage import StateStore

class SimulationTests(unittest.TestCase):
    def test_deterministic_events(self):
        self.assertEqual(synthetic_event('push',42),synthetic_event('push',42))
        self.assertNotEqual(synthetic_event('push',42),synthetic_event('push',43))
        self.assertEqual(synthetic_event('pull_request',42)['event'],'pull_request')
    def test_digital_life_pipeline(self):
        workflow=Path(__file__).resolve().parent.parent/'examples'/'digital_life_sim.yml'
        result=asyncio.run(simulate(workflow,workflow.parent,2026))
        self.assertEqual(result['result']['status'],'success',result)
        self.assertEqual(len(result['result']['jobs']),4)
        self.assertTrue(result['secret_masked'])
        self.assertEqual(result['artifact_count'],3)
    def test_retry_recovers_from_transient_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);repo=p/'repo';repo.mkdir()
            (repo/'ci.yml').write_text('''jobs:
  flaky:
    steps:
      - run: |
          if [ -f sentinel ]; then exit 0; else touch sentinel; exit 1; fi
        x-omega-retry: 1
''')
            s=Settings(p/'home',unsafe_native=True);e=Engine(s,StateStore(s.home/'state.db'))
            result=asyncio.run(e.run(repo/'ci.yml',repo))
            self.assertEqual(result['status'],'success')
            self.assertIn('flaky candidate',str(e.store.logs(result['id'])))
    def test_repo_remains_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);repo=p/'repo';repo.mkdir();wf=repo/'ci.yml'
            wf.write_text('jobs:\n  test:\n    steps:\n      - run: echo hello > generated.txt\n')
            before={x.name:x.read_bytes() for x in repo.iterdir()}
            s=Settings(p/'home',unsafe_native=True)
            result=asyncio.run(Engine(s).run(wf,repo))
            self.assertEqual(result['status'],'success')
            self.assertEqual(before,{x.name:x.read_bytes() for x in repo.iterdir()})

if __name__=='__main__':unittest.main()

class DigitalTwinTests(unittest.TestCase):
    def test_github_check_lifecycle(self):
        from omega_actions.simulator import GitHubActionsDigitalTwin
        twin=GitHubActionsDigitalTwin(99)
        event=twin.dispatch('push')
        key=twin.create_check(event['after'],'local-ci')
        twin.complete_check(key,'success')
        twin.upload_artifact('build',b'data')
        self.assertEqual(twin.checks[key]['conclusion'],'success')
        self.assertEqual(twin.artifacts['build']['size'],4)

class VirtualWorkerTests(unittest.TestCase):
    def test_virtual_worker_determinism(self):
        from omega_actions.simulator import VirtualWorkerPool
        workflow=Path(__file__).resolve().parent.parent/'examples'/'digital_life_sim.yml'
        a=VirtualWorkerPool(42).execute(workflow)
        b=VirtualWorkerPool(42).execute(workflow)
        self.assertEqual(a,b)
        self.assertEqual(a['status'],'success')
        self.assertEqual(len(a['jobs']),4)
    def test_virtual_worker_dependency_failure(self):
        from omega_actions.simulator import VirtualWorkerPool
        workflow=Path(__file__).resolve().parent.parent/'examples'/'digital_life_sim.yml'
        result=VirtualWorkerPool(42).execute(workflow,{'language-matrix[0]'})
        self.assertEqual(result['status'],'failure')
        self.assertEqual(result['jobs']['aggregate'],'skipped')
