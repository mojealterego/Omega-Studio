"""Native Android must not expose its privileged JS bridge to code-server origin."""
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def test_code_server_activity_has_no_privileged_bridge():
    src=(ROOT/'android/app/src/main/java/org/omega/actions/CodeEditorActivity.java').read_text()
    assert 'addJavascriptInterface' not in src
    assert 'CodeServerManager.get().activeUrl()' in src
    assert 'setAllowFileAccess(false)' in src


def test_runtime_health_probe_checks_six_commands():
    src=(ROOT/'android/app/src/main/java/org/omega/actions/RuntimeHealth.java').read_text()
    for cmd in ('bash','python','git','llama-cli','node','code-server'):
        assert '"'+cmd+'"' in src
    assert 'waitFor(' in src and 'TimeUnit.SECONDS' in src


def test_localhost_only_cleartext_network_policy():
    xml=ET.parse(ROOT/'android/app/src/main/res/xml/network_security_config.xml')
    domains=[e.text for e in xml.findall('.//domain')]
    assert '127.0.0.1' in domains
    assert 'localhost' in domains
    manifest=(ROOT/'android/app/src/main/AndroidManifest.xml').read_text()
    assert 'android:networkSecurityConfig="@xml/network_security_config"' in manifest
    assert 'CodeEditorActivity' in manifest


def test_vscode_entrypoint_uses_password_and_loopback():
    src=(ROOT/'android/app/src/main/java/org/omega/actions/CodeServerManager.java').read_text()
    bridge=(ROOT/'android/app/src/main/java/org/omega/actions/NativeBridge.java').read_text()
    assert '"--bind-addr","127.0.0.1:"+port' in src
    assert '"--auth","password"' in src
    assert 'env.put("PASSWORD",password)' in src
    assert 'public void runtimeHealth(' in bridge
    assert 'public void startCodeServer(' in bridge
