"""No unsigned/debug or synthetic runtime may be promoted as production."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def test_release_build_requires_android_signing_environment():
    script=(ROOT/'tools/build_android_release.sh').read_text()
    for variable in ('OMEGA_KEYSTORE','OMEGA_KEYSTORE_PASSWORD','OMEGA_KEY_ALIAS','OMEGA_KEY_PASSWORD'):
        assert variable in script
    assert 'assembleRelease' in script
    assert 'assembleDebug' not in script


def test_release_build_blocks_before_gradle_when_bootstrap_absent():
    script=(ROOT/'tools/build_android_release.sh').read_text()
    assert 'verify_runtime_bundle.py' in script
    assert script.index('verify_runtime_bundle.py') < script.index('assembleRelease')


def test_release_signing_does_not_commit_secrets():
    gradle=(ROOT/'android/app/build.gradle').read_text()
    assert 'signingConfigs' in gradle
    assert 'System.getenv(' in gradle
    assert 'signingConfig signingConfigs.release' in gradle
