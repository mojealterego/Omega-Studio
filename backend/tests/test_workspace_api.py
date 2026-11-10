"""Workspace API integration contract tests."""
import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from omega_actions.ultimate.router import create_ultimate_router

class WorkspaceAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = FastAPI()
        app.include_router(create_ultimate_router(Path(self.tmp.name)))
        self.client = TestClient(app)

    def test_create_list_open(self):
        created = self.client.post('/api/ultimate/workspaces', json={'name': 'demo'})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()['path'], 'workspaces/demo')
        self.assertEqual(self.client.get('/api/ultimate/workspaces').json()['items'], ['demo'])
        self.assertEqual(self.client.get('/api/ultimate/workspaces/demo').status_code, 200)

    def test_duplicate_is_conflict(self):
        self.client.post('/api/ultimate/workspaces', json={'name': 'demo'})
        self.assertEqual(self.client.post('/api/ultimate/workspaces', json={'name': 'demo'}).status_code, 409)

    def test_traversal_is_rejected(self):
        self.assertEqual(self.client.post('/api/ultimate/workspaces', json={'name': '../escape'}).status_code, 422)
        self.assertEqual(self.client.get('/api/ultimate/workspaces/%2E%2E').status_code, 404)

    def test_missing_is_not_found(self):
        self.assertEqual(self.client.get('/api/ultimate/workspaces/unknown').status_code, 404)
