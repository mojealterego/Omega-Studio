"""P0 regressions for directory-symlink isolation in OMEGA Studio."""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import unittest

from omega_actions.ultimate.workspace_registry import WorkspaceError, WorkspaceRegistry


@unittest.skipUnless(os.name == 'posix', 'directory descriptors require POSIX')
class WorkspaceRegistryHardeningTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.home = Path(self.sandbox.name) / 'home'
        self.home.mkdir()
        self.outside = Path(self.sandbox.name) / 'outside'
        self.outside.mkdir()
        self.registry = WorkspaceRegistry(self.home)

    def test_root_symlink_cannot_create_outside_workspace(self):
        (self.home / 'workspaces').symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(WorkspaceError):
            self.registry.create('project')
        self.assertFalse((self.outside / 'project').exists())

    def test_root_symlink_cannot_list_outside_workspaces(self):
        (self.outside / 'private').mkdir()
        (self.home / 'workspaces').symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(WorkspaceError):
            self.registry.list()

    def test_root_symlink_cannot_open_outside_workspaces(self):
        (self.outside / 'secret').mkdir()
        (self.home / 'workspaces').symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(WorkspaceError):
            self.registry.open('secret')

    def test_new_root_and_workspace_are_private(self):
        workspace = self.registry.create('p1')
        self.assertEqual(workspace.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.home / 'workspaces').stat().st_mode & 0o777, 0o700)

    def test_existing_valid_root_remains_compatible(self):
        (self.home / 'workspaces').mkdir()
        self.registry.create('alpha')
        self.assertEqual(self.registry.list(), ['alpha'])
        self.assertEqual(self.registry.open('alpha'), self.home / 'workspaces' / 'alpha')

    def test_missing_root_lists_no_workspaces(self):
        self.assertEqual(self.registry.list(), [])

    def test_file_instead_of_root_is_rejected(self):
        (self.home / 'workspaces').write_text('not a directory')
        with self.assertRaises(WorkspaceError):
            self.registry.create('unsafe')
        with self.assertRaises(WorkspaceError):
            self.registry.list()

    def test_held_fd_survives_root_replacement_without_escape(self):
        workspace = self.registry.create('safe')
        (workspace / 'proof.txt').write_text('inside')
        (self.outside / 'proof.txt').write_text('outside')
        with self.registry.open_fd('safe') as fd:
            (self.home / 'workspaces').rename(self.home / 'workspaces-backup')
            (self.home / 'workspaces').symlink_to(self.outside, target_is_directory=True)
            inner = os.open('proof.txt', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                self.assertEqual(os.read(inner, 100), b'inside')
            finally:
                os.close(inner)
        with self.assertRaises(WorkspaceError):
            self.registry.open('proof')

    def test_no_follow_symlink_at_leaf(self):
        self.registry.create('safe')
        (self.home / 'workspaces' / 'linked').symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(WorkspaceError):
            self.registry.open('linked')
        self.assertEqual(self.registry.list(), ['safe'])

    def test_create_rejects_invalid_name(self):
        for name in ('../escape', 'a/b', '..', '', '.hidden', 'é'):
            with self.subTest(name=name), self.assertRaises(WorkspaceError):
                self.registry.create(name)

    def test_exposes_race_resistant_directory_fd(self):
        self.registry.create('safe')
        with self.registry.open_fd('safe') as fd:
            self.assertTrue(os.fstat(fd).st_mode & 0o40000)
            self.assertEqual(os.listdir(fd), [])
        with self.assertRaises(OSError):
            os.fstat(fd)


if __name__ == '__main__':
    unittest.main()
