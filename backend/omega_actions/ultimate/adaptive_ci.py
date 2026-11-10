"""Explicitly approved, bounded local CI plan execution.

No autonomous deployment, self-replication, network access or code execution is
performed without an operator-approved plan. The built-in compile check does
not execute project source; tests are not run implicitly.
"""
from __future__ import annotations
import hashlib
import hmac
import json
from pathlib import Path
import subprocess
import sys


class PlanRejected(ValueError):
    pass


class AdaptiveCI:
    def __init__(self, workspace: Path, *, secret: bytes):
        if not isinstance(secret, bytes) or len(secret) < 16:
            raise ValueError('Approval key must be at least 128 bits')
        self.workspace = Path(workspace).resolve(strict=True)
        if not self.workspace.is_dir() or self.workspace.is_symlink():
            raise ValueError('Workspace must be a directory')
        self.secret = secret

    @staticmethod
    def _digest(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def propose_python_compile(self) -> dict:
        payload = {'schema': 1, 'kind': 'python_compile', 'argv': ['python', '-m', 'compileall', '-q', '.'],
                   'workspace': str(self.workspace), 'requires_explicit_approval': True}
        return {**payload, 'sha256': self._digest(payload)}

    def _validate(self, plan: dict) -> str:
        if not isinstance(plan, dict) or set(plan) != {'schema', 'kind', 'argv', 'workspace', 'requires_explicit_approval', 'sha256'}:
            raise PlanRejected('Plan fields invalid')
        if plan['schema'] != 1 or plan['kind'] != 'python_compile' or plan['argv'] != ['python', '-m', 'compileall', '-q', '.']:
            raise PlanRejected('Plan command not allowlisted')
        if plan['workspace'] != str(self.workspace) or plan['requires_explicit_approval'] is not True:
            raise PlanRejected('Plan workspace or approval policy mismatch')
        content = {k: v for k, v in plan.items() if k != 'sha256'}
        digest = self._digest(content)
        if not hmac.compare_digest(digest, str(plan['sha256'])):
            raise PlanRejected('Plan modified')
        return digest

    def approve(self, plan: dict, *, operator_confirmed: bool = False) -> str:
        if not operator_confirmed:
            raise PlanRejected('Operator must explicitly confirm approval')
        digest = self._validate(plan)
        return hmac.new(self.secret, digest.encode(), hashlib.sha256).hexdigest()

    def execute(self, plan: dict, *, approval: str, timeout: int = 30) -> dict:
        digest = self._validate(plan)
        expected = hmac.new(self.secret, digest.encode(), hashlib.sha256).hexdigest()
        if not isinstance(approval, str) or not hmac.compare_digest(expected, approval):
            raise PlanRejected('Missing or invalid operator approval')
        if not 1 <= timeout <= 120:
            raise ValueError('Timeout outside safety policy')
        try:
            proc = subprocess.run([sys.executable, '-m', 'compileall', '-q', '.'],
                                  cwd=self.workspace, capture_output=True, timeout=timeout,
                                  check=False)
        except subprocess.TimeoutExpired as exc:
            raise PlanRejected('Local compile check timed out') from exc
        return {'returncode': proc.returncode, 'verified_plan_sha256': digest,
                'stdout': proc.stdout[:8192].decode('utf-8', 'replace'),
                'stderr': proc.stderr[:8192].decode('utf-8', 'replace'),
                'scope': 'approved-local-python-syntax-check'}
