import io
import json
import zipfile
from pathlib import Path
import pytest
from builder.omega_builder import validate_project, build_bundle, render_web, render_native_java, generate_files

BASE = {
    'schema_version': 1,
    'name': 'Moja aplikacja',
    'slug': 'moja-aplikacja',
    'package': 'pl.omega.mojaaplikacja',
    'platform': 'both',
    'pages': [
        {'id': 'home', 'title': 'Strona główna', 'components': [
            {'id': 'h1', 'type': 'heading', 'text': 'Witaj <Omega>'},
            {'id': 'p1', 'type': 'paragraph', 'text': 'Polski tekst & więcej'},
            {'id': 'input1', 'type': 'input', 'label': 'Imię'},
            {'id': 'go', 'type': 'button', 'text': 'Otwórz', 'action': 'page:about'},
        ]},
        {'id': 'about', 'title': 'O nas', 'components': [
            {'id': 'info', 'type': 'card', 'text': 'Ważne informacje'},
        ]},
    ],
}


def test_accepts_valid_polish_project():
    assert validate_project(BASE)['pages'][0]['title'] == 'Strona główna'


@pytest.mark.parametrize('field,value', [
    ('slug', '../evil'), ('package', 'java.lang'), ('platform', 'ios'),
    ('name', ''), ('pages', []),
])
def test_rejects_invalid_project(field, value):
    doc = json.loads(json.dumps(BASE)); doc[field] = value
    with pytest.raises(ValueError): validate_project(doc)


def test_rejects_unknown_actions_and_duplicate_ids():
    doc = json.loads(json.dumps(BASE))
    doc['pages'][0]['components'][3]['action'] = 'javascript:alert(1)'
    with pytest.raises(ValueError): validate_project(doc)
    doc['pages'][0]['components'][3]['action'] = 'page:about'
    doc['pages'][1]['id'] = 'home'
    with pytest.raises(ValueError): validate_project(doc)


def test_web_html_escapes_user_content_and_csp():
    html = render_web(BASE)
    assert 'Witaj &lt;Omega&gt;' in html
    assert 'Polski tekst &amp; więcej' in html
    assert 'Content-Security-Policy' in html
    assert 'unsafe-eval' not in html
    assert 'data-page="about"' in html


def test_native_source_has_native_widgets_not_webview():
    java = render_native_java(BASE)
    assert 'new TextView(this)' in java
    assert 'new EditText(this)' in java
    assert 'new Button(this)' in java
    assert 'WebView' not in java
    assert 'V2l0YWogPE9tZWdhPg==' in java  # base64 protects Java source from injection
    assert 'setOnClickListener' in java


def test_bundle_is_deterministic_and_contains_both_platforms():
    one = build_bundle(BASE)
    two = build_bundle(BASE)
    assert one == two
    with zipfile.ZipFile(io.BytesIO(one)) as z:
        assert z.testzip() is None
        names = set(z.namelist())
        assert 'web/index.html' in names
        assert 'android/app/src/main/java/pl/omega/mojaaplikacja/MainActivity.java' in names
        assert 'android/app/src/main/AndroidManifest.xml' in names
        assert 'MANIFEST_SHA256.txt' in names
        assert 'appbuilder.project.json' in names
        assert all(not x.startswith('/') and '..' not in Path(x).parts for x in names)


def test_web_only_export_does_not_include_android():
    doc = json.loads(json.dumps(BASE)); doc['platform'] = 'web'
    files = generate_files(doc)
    assert 'web/index.html' in files
    assert not any(p.startswith('android/') for p in files)


def test_android_only_export_does_not_include_web():
    doc = json.loads(json.dumps(BASE)); doc['platform'] = 'android'
    files = generate_files(doc)
    assert 'web/index.html' not in files
    assert any(p.endswith('MainActivity.java') for p in files)


def test_rejects_overlarge_component_and_dangling_page():
    doc = json.loads(json.dumps(BASE))
    doc['pages'][0]['components'][0]['text'] = 'a' * 5000
    with pytest.raises(ValueError): validate_project(doc)
    doc['pages'][0]['components'][0]['text'] = 'OK'
    doc['pages'][0]['components'][3]['action'] = 'page:missing'
    with pytest.raises(ValueError): validate_project(doc)
