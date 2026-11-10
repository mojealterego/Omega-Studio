import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from omega_actions.artifacts import ArtifactStore
from omega_actions.cache import DependencyCache
from omega_actions.compiler import compile_workflow,load_workflow,expand_matrix
from omega_actions.expressions import evaluate,interpolate,ExpressionError
from omega_actions.redaction import StreamMasker,redact
from omega_actions.schedule import matches
from omega_actions.vault import SecretVault,VaultError
from omega_actions.analysis import diagnose,retry_delay
from datetime import datetime

class SecurityTests(unittest.TestCase):
    def test_redactor_secret_spanning_chunks(self):
        m=StreamMasker(['TOPSECRET','SECRET','XYZ'])
        actual=m.feed('prefix TOP')+m.feed('SEC')+m.feed('RET suffix XYZ!')+m.finish()
        self.assertEqual(actual,'prefix *** suffix ***!')
    def test_redactor_overlapping(self):
        self.assertEqual(redact('abcabc',['abc','bca']),'***')
    def test_redactor_does_not_mask_empty(self):
        self.assertEqual(redact('hello',['']),'hello')
    def test_vault_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'vault.json'; v=SecretVault(p,'password');v.set('SECRET','sensitive')
            obj=json.loads(p.read_text());obj['ciphertext']='AAAA';p.write_text(json.dumps(obj))
            with self.assertRaises(VaultError): v.get('SECRET')
    def test_artifact_secrets_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'data.txt').write_text('key=123456')
            with self.assertRaises(ValueError): ArtifactStore(p/'artifacts').upload('abc','data',['data.txt'],p,['123456'])
    def test_artifact_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'data.txt').write_text('hello')
            store=ArtifactStore(p/'artifacts');out,n,digest=store.upload('abc','data',['data.txt'],p)
            self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(),digest)
            self.assertEqual(store.download('abc','data',p/'restored'),1)
            self.assertEqual((p/'restored'/'data.txt').read_text(),'hello')
    def test_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); w=p/'work';w.mkdir();(w/'deps').mkdir();(w/'deps'/'a').write_text('cached')
            c=DependencyCache(p/'cache');self.assertEqual(c.save('linux-py',['deps'],w),1)
            (w/'deps'/'a').unlink();self.assertEqual(c.restore('other',w,['linux-']),1)
            self.assertEqual((w/'deps'/'a').read_text(),'cached')
    def test_cycle_rejected(self):
        with self.assertRaisesRegex(ValueError,'cycle'):
            compile_workflow(load_workflow('jobs:\n  a:\n    needs: b\n    steps: []\n  b:\n    needs: a\n    steps: []\n'))
    def test_duplicate_yaml_key_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            load_workflow('jobs: {}\njobs: {}\n')
    def test_matrix_include_exclude(self):
        rows=expand_matrix({'os':['linux','mac'],'python':['3.11','3.12'],
                            'exclude':[{'os':'mac','python':'3.11'}],
                            'include':[{'os':'windows','python':'3.12'}]})
        self.assertEqual(len(rows),4)
    def test_expression_disallows_code(self):
        for expr in ('__class__','a.__dict__','open("/etc/passwd")','a[0]'):
            with self.subTest(expr=expr):
                with self.assertRaises(ExpressionError): evaluate(expr,{'a':{}})
    def test_expression_context(self):
        self.assertTrue(evaluate("contains(github.ref, 'main') && !failure()",{'github':{'ref':'refs/heads/main'},'status':'success'}))
        self.assertEqual(interpolate('v-${{ matrix.py }}',{'matrix':{'py':'3.13'}}),'v-3.13')
    def test_cron(self):
        self.assertTrue(matches('*/15 8-20 * * 1-5',datetime(2026,11,10,12,30)))
        self.assertFalse(matches('*/15 8-20 * * 1-5',datetime(2026,11,10,12,31)))
    def test_retry_classifier(self):
        self.assertTrue(diagnose('connection reset by peer').retryable)
        self.assertFalse(diagnose('AssertionError').retryable)
        self.assertEqual(retry_delay(3,0.5),2.0)

if __name__=='__main__':unittest.main()
