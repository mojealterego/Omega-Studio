"""Fail-closed CI improvement proposals with human authorization and HMAC receipts.

Does not replicate, self-deploy or execute unreviewed third-party code.
"""
from __future__ import annotations
import hashlib
import hmac
import json
from pathlib import Path
import re


class CIProposalError(ValueError):
    pass


class AdaptiveCIGate:
    _TASK = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
    _ALLOWED = {'python', 'python3', 'pytest', 'node', 'npm', 'cargo', 'git'}

    def __init__(self, workspace: Path, *, signing_key: bytes):
        if len(signing_key) < 24:
            raise CIProposalError('At least 24 bytes of independent signing key required')
        self.workspace = Path(workspace).resolve(strict=True)
        if not self.workspace.is_dir():
            raise CIProposalError('Workspace must exist')
        self.key = signing_key

    def propose(self, task: str, command: list[str], *, max_seconds: int = 60) -> dict:
        if not isinstance(task, str) or not self._TASK.fullmatch(task):
            raise CIProposalError('Invalid task name')
        if not isinstance(command, list) or not 1 <= len(command) <= 32 or any(
                not isinstance(arg, str) or not arg or len(arg) > 512 or '\x00' in arg or '\n' in arg
                for arg in command):
            raise CIProposalError('Invalid command')
        if command[0] not in self._ALLOWED or any(arg in ('-c', '--eval', '-e') for arg in command[1:]):
            raise CIProposalError('Command requires manual security review')
        if any(arg.startswith('/') or '..' in Path(arg).parts for arg in command[1:]):
            raise CIProposalError('Absolute paths and traversal are not allowed')
        if not 1 <= max_seconds <= 600:
            raise CIProposalError('Invalid timeout')
        return {'version':1,'task':task,'command':command[:], 'max_seconds':max_seconds,
                'workspace':str(self.workspace),'status':'awaiting_approval'}

    @staticmethod
    def _canonical(value: dict) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    def approve(self, proposal: dict, *, approval: str) -> dict:
        if not isinstance(proposal, dict) or proposal.get('status') != 'awaiting_approval':
            raise CIProposalError('Proposal not awaiting approval')
        if approval != 'approve:' + str(proposal.get('task')):
            raise CIProposalError('Explicit task-specific approval required')
        expected = self.propose(proposal['task'], proposal['command'], max_seconds=proposal['max_seconds'])
        if proposal != expected:
            raise CIProposalError('Proposal has been modified')
        approved = {**expected, 'status':'approved'}
        approved['hmac_sha3_256'] = hmac.new(self.key, self._canonical(approved), hashlib.sha3_256).hexdigest()
        return approved

    def verify(self, approved: dict) -> bool:
        if not isinstance(approved, dict) or approved.get('status') != 'approved':
            return False
        unsigned = {k:v for k,v in approved.items() if k != 'hmac_sha3_256'}
        try:
            expected = self.propose(unsigned['task'], unsigned['command'], max_seconds=unsigned['max_seconds'])
        except (KeyError, TypeError, CIProposalError):
            return False
        if unsigned != {**expected, 'status':'approved'}:
            return False
        expected_mac = hmac.new(self.key, self._canonical(unsigned), hashlib.sha3_256).hexdigest()
        return hmac.compare_digest(expected_mac, str(approved.get('hmac_sha3_256', '')))
