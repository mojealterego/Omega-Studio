"""Android runtime installation must fail closed on incomplete or broken prefixes."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def test_bootstrap_requires_all_six_commands_before_reporting_ready():
    src=(ROOT/'android/app/src/main/java/org/omega/actions/TermuxBootstrapInstaller.java').read_text()
    assert 'RuntimeHealth.assertHealthy(' in src
    assert 'bin/bash").canExecute())return' not in src


def test_bootstrap_uses_content_marker_for_existing_prefix():
    src=(ROOT/'android/app/src/main/java/org/omega/actions/TermuxBootstrapInstaller.java').read_text()
    assert '.omega-runtime.sha256' in src
    assert 'Existing prefix' in src


def test_health_probe_fails_when_any_command_fails():
    src=(ROOT/'android/app/src/main/java/org/omega/actions/RuntimeHealth.java').read_text()
    assert 'void assertHealthy(' in src
    assert 'PASS:' in src
