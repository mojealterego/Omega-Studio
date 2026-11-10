import tempfile
import unittest
from pathlib import Path
from omega_actions.ultimate.workspace_registry import WorkspaceRegistry, WorkspaceError

class WorkspaceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.registry=WorkspaceRegistry(Path(self.tmp.name))
    def test_create_and_list(self):
        path=self.registry.create('my-project')
        self.assertTrue(path.is_dir())
        self.assertEqual(self.registry.list(),['my-project'])
    def test_duplicate_rejected(self):
        self.registry.create('a')
        with self.assertRaises(WorkspaceError):self.registry.create('a')
    def test_traversal_rejected(self):
        for name in ('../escape','a/b','..','', '.hidden'):
            with self.subTest(name=name),self.assertRaises(WorkspaceError):self.registry.create(name)
    def test_symlink_rejected(self):
        (Path(self.tmp.name)/'outside').mkdir()
        (Path(self.tmp.name)/'workspaces').mkdir()
        (Path(self.tmp.name)/'workspaces'/'linked').symlink_to(Path(self.tmp.name)/'outside',target_is_directory=True)
        with self.assertRaises(WorkspaceError):self.registry.open('linked')
