import unittest
from omega_actions.compiler import load_workflow, compile_workflow
from omega_actions.expressions import evaluate
from omega_actions.vault import SecretVault
from omega_actions.cache import CAS

class ContractTests(unittest.TestCase):
    def test_yaml_on_key(self):
        w = load_workflow('name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n')
        self.assertEqual(w['on'], ['push'])

    def test_matrix_dag(self):
        w = load_workflow('jobs:\n  build:\n    strategy:\n      matrix:\n        os: [ubuntu, windows]\n        py: ["3.11", "3.12"]\n    steps:\n      - run: echo ok\n  finish:\n    needs: build\n    steps:\n      - run: echo done\n')
        compiled = compile_workflow(w)
        self.assertEqual(len(compiled.jobs), 5)
        self.assertEqual(len(compiled.jobs['finish'].needs), 4)

    def test_safe_expression(self):
        self.assertTrue(evaluate("matrix.os == 'linux' && success()", {'matrix':{'os':'linux'}, 'status':'success'}))
        with self.assertRaises(Exception):
            evaluate("__import__('os').system('id')", {})

    def test_vault_roundtrip(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            v=SecretVault(Path(d)/'vault.json', 'password')
            v.set('TOKEN', 'my-secret')
            self.assertEqual(v.get('TOKEN'), 'my-secret')
            with self.assertRaises(Exception):
                SecretVault(Path(d)/'vault.json', 'wrong').get('TOKEN')

    def test_cas(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            c=CAS(Path(d)/'cache')
            h=c.put(b'hello')
            self.assertEqual(c.get(h), b'hello')

if __name__ == '__main__': unittest.main()
