"""CLI contract: explicit workspace, password and safe network binding."""
import os
from pathlib import Path
import subprocess
import sys


def invoke(tmp_path, *args, env=None):
    settings = dict(os.environ)
    settings['PYTHONPATH'] = str(Path(__file__).resolve().parents[2]/'backend')
    settings.pop('OMEGA_REMOTE_PASSWORD', None)
    settings.update(env or {})
    return subprocess.run([sys.executable, '-m', 'omega_actions.ultimate.serve', str(tmp_path), *args],
                          capture_output=True, text=True, env=settings, timeout=10)


def test_serve_cli_rejects_missing_password(tmp_path):
    result = invoke(tmp_path)
    assert result.returncode == 2
    assert 'password' in result.stderr.lower()


def test_serve_cli_rejects_unsecured_lan(tmp_path):
    result = invoke(tmp_path, '--bind', '0.0.0.0', env={'OMEGA_REMOTE_PASSWORD':'long-secret-123'})
    assert result.returncode == 2
    assert 'TLS' in result.stderr
