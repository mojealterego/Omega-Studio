"""The custom Termux build must consume the pinned OSS lock, never arbitrary refs."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/build_custom_termux.sh'


def test_help_documents_lock():
    result = subprocess.run(['bash', str(SCRIPT), '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert '--lock' in result.stdout


def test_build_rejects_revision_not_in_source_lock(tmp_path):
    editor = tmp_path / 'editor'
    work = tmp_path / 'work'
    editor.mkdir()
    work.mkdir()
    result = subprocess.run(['bash', str(SCRIPT), '--termux-ref', 'f' * 40,
                             '--editor-prefix', str(editor), '--work-dir', str(work)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert 'source lock' in result.stderr.lower()
    assert not (work / 'termux-packages').exists()
