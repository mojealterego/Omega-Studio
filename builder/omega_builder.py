"""Validated, deterministic exporter for native Android and static web applications."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

_COMPONENTS = frozenset({'heading', 'paragraph', 'card', 'button', 'input', 'divider'})
_PLATFORMS = frozenset({'web', 'android', 'both'})
_THEMES = {
    'obsidian-gold': ('#080A0E', '#131820', '#D4AF37', '#F6F2E8'),
    'graphite-silver': ('#101319', '#1C222B', '#BAC7D6', '#F4F6F9'),
    'midnight-blue': ('#071222', '#12263E', '#6CC7F7', '#E9F6FF'),
}
_ID = re.compile(r'^[a-z][a-z0-9_-]{0,47}$')
_PACKAGE = re.compile(r'^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,5}$')


def _string(value: Any, name: str, limit: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not allow_empty and not value.strip()):
        raise ValueError(f'{name}: wymagany niepusty tekst do {limit} znaków')
    if any(ord(ch) < 32 and ch not in '\n\t' for ch in value):
        raise ValueError(f'{name}: niedozwolony znak sterujący')
    return value


def validate_project(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError('Projekt musi być obiektem JSON')
    if document.get('schema_version') != 1:
        raise ValueError('Nieobsługiwana wersja schematu')
    project = copy.deepcopy(document)
    project['name'] = _string(project.get('name'), 'name', 80)
    slug = _string(project.get('slug'), 'slug', 48)
    if not _ID.fullmatch(slug):
        raise ValueError('Niepoprawny slug')
    package = _string(project.get('package'), 'package', 128)
    if not _PACKAGE.fullmatch(package) or package.startswith(('java.', 'android.', 'com.android.')):
        raise ValueError('Niepoprawny identyfikator pakietu Android')
    if project.get('platform') not in _PLATFORMS:
        raise ValueError('Nieobsługiwana platforma')
    project['theme'] = project.get('theme', 'obsidian-gold')
    if project['theme'] not in _THEMES:
        raise ValueError('Nieobsługiwany motyw')
    pages = project.get('pages')
    if not isinstance(pages, list) or not 1 <= len(pages) <= 16:
        raise ValueError('Projekt musi zawierać 1–16 stron')
    ids: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError('Niepoprawna strona')
        pid = _string(page.get('id'), 'page.id', 48)
        if not _ID.fullmatch(pid) or pid in ids:
            raise ValueError('Niepoprawny lub powtórzony identyfikator strony')
        ids.add(pid)
        page['title'] = _string(page.get('title'), 'page.title', 80)
        components = page.get('components')
        if not isinstance(components, list) or len(components) > 100:
            raise ValueError('Strona może zawierać maksymalnie 100 komponentów')
        component_ids: set[str] = set()
        for component in components:
            if not isinstance(component, dict) or component.get('type') not in _COMPONENTS:
                raise ValueError('Nieobsługiwany komponent')
            cid = _string(component.get('id'), 'component.id', 48)
            if not _ID.fullmatch(cid) or cid in component_ids:
                raise ValueError('Niepoprawny lub powtórzony identyfikator komponentu')
            component_ids.add(cid)
            component['text'] = _string(component.get('text', ''), 'component.text', 2000, True)
            component['label'] = _string(component.get('label', ''), 'component.label', 120, True)
            action = component.get('action', '')
            if not isinstance(action, str) or (action and not re.fullmatch(r'page:[a-z][a-z0-9_-]{0,47}', action)):
                raise ValueError('Akcja musi wskazywać stronę projektu')
            component['action'] = action
    for page in pages:
        for component in page['components']:
            if component['action'] and component['action'][5:] not in ids:
                raise ValueError('Akcja wskazuje nieistniejącą stronę')
    return project


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _web_component(c: dict[str, str]) -> str:
    t, text = c['type'], _esc(c['text'])
    if t == 'heading':
        return f'<h2>{text}</h2>'
    if t == 'paragraph':
        return f'<p>{text}</p>'
    if t == 'card':
        return f'<article class="feature">{text}</article>'
    if t == 'divider':
        return '<hr>'
    if t == 'input':
        return f'<label class="field">{_esc(c["label"])}<input type="text" maxlength="200" autocomplete="off"></label>'
    action = c['action'][5:] if c['action'] else ''
    return f'<button type="button" class="cta" data-target="{_esc(action)}">{text}</button>'


def render_web(document: dict[str, Any]) -> str:
    project = validate_project(document)
    pages = '\n'.join(
        f'<section class="page" data-page="{_esc(page["id"])}" {"" if i == 0 else "hidden"}>'
        f'<p class="overline">OMEGA APP BUILDER</p><h1>{_esc(page["title"])}</h1>'
        + '\n'.join(_web_component(c) for c in page['components']) + '</section>'
        for i, page in enumerate(project['pages'])
    )
    bg, panel, gold, fg = _THEMES[project['theme']]
    return ('''<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>''' + _esc(project['name']) + '''</title><link rel="stylesheet" href="style.css"></head><body>
<header><span class="brand">Ω</span><span>''' + _esc(project['name']) + '''</span></header>
<main>''' + pages + '''</main>
<nav aria-label="Nawigacja">''' + ''.join(f'<button type="button" data-target="{_esc(p["id"])}">{_esc(p["title"])}</button>' for p in project['pages']) + '''</nav>
<script src="app.js"></script></body></html>''')


def _web_css(theme: str) -> str:
    bg, panel, gold, fg = _THEMES[theme]
    return f'''*{{box-sizing:border-box}}:root{{--bg:{bg};--panel:{panel};--accent:{gold};--fg:{fg}}}
html,body{{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,sans-serif;min-height:100%}}
header{{display:flex;gap:16px;align-items:center;border-bottom:1px solid #7775;padding:24px max(20px,5vw);letter-spacing:.08em;font-weight:650}}
.brand{{font:40px Georgia,serif;color:var(--accent)}}main{{max-width:850px;margin:auto;padding:44px 24px 140px}}
.page[hidden]{{display:none}}.overline{{letter-spacing:.28em;font-size:11px;color:var(--accent)}}h1{{font:500 clamp(32px,7vw,58px) Georgia,serif;margin:12px 0 36px}}
h2{{font-size:26px;margin:24px 0 12px}}p{{line-height:1.75;color:#c6c8cf}}.feature{{padding:26px;border:1px solid #bda26355;border-radius:16px;background:var(--panel);margin:18px 0}}
.field{{display:block;margin:24px 0}}input{{display:block;background:var(--panel);border:1px solid #7776;color:var(--fg);padding:14px;width:100%;border-radius:8px;margin-top:8px}}
button{{cursor:pointer}}.cta{{background:var(--accent);color:#090a0b;padding:14px 22px;border:0;border-radius:9px;font-weight:700}}
nav{{position:fixed;bottom:0;left:0;right:0;background:var(--panel);border-top:1px solid #7775;display:flex;gap:8px;overflow-x:auto;padding:14px}}
nav button{{background:transparent;color:var(--fg);border:1px solid #7776;padding:10px 15px;border-radius:10px;white-space:nowrap}}
nav button[aria-current="page"]{{color:var(--accent);border-color:var(--accent)}}
'''


_WEB_JS = ''''use strict';
const pages=[...document.querySelectorAll('.page')];
function openPage(id){
 if(!pages.some(p=>p.dataset.page===id))return;
 for(const page of pages)page.hidden=page.dataset.page!==id;
 for(const button of document.querySelectorAll('nav button')){
  if(button.dataset.target===id)button.setAttribute('aria-current','page');
  else button.removeAttribute('aria-current');
 }
 window.scrollTo(0,0);
}
document.addEventListener('click',e=>{
 const button=e.target.closest('button[data-target]');
 if(button && button.dataset.target)openPage(button.dataset.target);
});
openPage(pages[0].dataset.page);
'''


def _b64(text: str) -> str:
    return base64.b64encode(text.encode('utf-8')).decode('ascii')


def _native_component(c: dict[str, str]) -> str:
    t = c['type']
    if t == 'divider':
        return 'divider(root);'
    if t == 'input':
        return f'field(root, dec("{_b64(c["label"])}"));'
    if t == 'button':
        action = c['action'][5:] if c['action'] else ''
        return f'button(root, dec("{_b64(c["text"])}"), "{action}");'
    method = {'heading': 'heading', 'paragraph': 'paragraph', 'card': 'card'}[t]
    return f'{method}(root, dec("{_b64(c["text"])}"));'


def render_native_java(document: dict[str, Any]) -> str:
    project = validate_project(document)
    bg, panel, gold, fg = _THEMES[project['theme']]
    pages = '\n'.join(
        f'case "{p["id"]}": title(dec("{_b64(p["title"])}"));\n' +
        '\n'.join(_native_component(c) for c in p['components']) + '\nbreak;'
        for p in project['pages']
    )
    nav = '\n'.join(f'button(nav,dec("{_b64(p["title"])}"),"{p["id"]}");' for p in project['pages'])
    return '''package ''' + project['package'] + ''';
import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.util.Base64;
import java.nio.charset.StandardCharsets;

public final class MainActivity extends Activity {
 private LinearLayout root;
 private final int BG=Color.parseColor("''' + bg + '''");
 private final int PANEL=Color.parseColor("''' + panel + '''");
 private final int GOLD=Color.parseColor("''' + gold + '''");
 private final int FG=Color.parseColor("''' + fg + '''");
 private static String dec(String s){return new String(Base64.decode(s,Base64.NO_WRAP),StandardCharsets.UTF_8);}
 private int dp(int x){return (int)(getResources().getDisplayMetrics().density*x+.5f);}
 private GradientDrawable shape(int color){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(12));return d;}
 private TextView text(String s,int size,int color){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(color);t.setPadding(dp(4),dp(12),dp(4),dp(12));return t;}
 private void heading(LinearLayout l,String s){TextView t=text(s,27,FG);t.setTypeface(Typeface.SERIF,Typeface.BOLD);l.addView(t);}
 private void title(String s){TextView t=text(s,34,GOLD);t.setTypeface(Typeface.SERIF,Typeface.NORMAL);root.addView(t);}
 private void paragraph(LinearLayout l,String s){l.addView(text(s,16,FG));}
 private void card(LinearLayout l,String s){TextView t=text(s,17,FG);t.setPadding(dp(20),dp(22),dp(20),dp(22));t.setBackground(shape(PANEL));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(12),0,dp(12));l.addView(t,p);}
 private void divider(LinearLayout l){View v=new View(this);v.setBackgroundColor(GOLD);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(1));p.setMargins(0,dp(12),0,dp(12));l.addView(v,p);}
 private void field(LinearLayout l,String label){l.addView(text(label,14,GOLD));EditText e=new EditText(this);e.setSingleLine(true);e.setTextColor(FG);e.setHintTextColor(GOLD);e.setBackground(shape(PANEL));e.setPadding(dp(14),dp(12),dp(14),dp(12));l.addView(e);}
 private void button(LinearLayout l,String label,String target){Button b=new Button(this);b.setText(label);b.setTextColor(BG);b.setAllCaps(false);b.setBackground(shape(GOLD));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(8),0,dp(8));l.addView(b,p);if(!target.isEmpty())b.setOnClickListener(v->showPage(target));}
 @Override public void onCreate(Bundle b){super.onCreate(b);showPage("''' + project['pages'][0]['id'] + '''");}
 private void showPage(String id){
  ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(BG);
  root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(20),dp(30),dp(20),dp(30));scroll.addView(root);
  switch(id){
''' + pages + '''
   default: throw new IllegalArgumentException("Unknown page");
  }
  divider(root);
  LinearLayout nav=new LinearLayout(this);nav.setOrientation(LinearLayout.VERTICAL);
''' + nav + '''
  root.addView(nav);setContentView(scroll);
 }
}
'''


def generate_files(document: dict[str, Any]) -> dict[str, bytes]:
    project = validate_project(document)
    files: dict[str, bytes] = {
        'appbuilder.project.json': (json.dumps(project, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8'),
    }
    if project['platform'] in ('web', 'both'):
        files.update({
            'web/index.html': render_web(project).encode('utf-8'),
            'web/style.css': _web_css(project['theme']).encode('utf-8'),
            'web/app.js': _WEB_JS.encode('utf-8'),
        })
    if project['platform'] in ('android', 'both'):
        pkg_path = project['package'].replace('.', '/')
        files.update({
            f'android/app/src/main/java/{pkg_path}/MainActivity.java': render_native_java(project).encode('utf-8'),
            'android/app/src/main/AndroidManifest.xml': (f'<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:label="{_esc(project["name"])}" android:theme="@android:style/Theme.Material.NoActionBar" android:usesCleartextTraffic="false" android:allowBackup="false"><activity android:name=".MainActivity" android:exported="true"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity></application></manifest>\n').encode('utf-8'),
            'android/app/build.gradle': (f'''plugins {{ id 'com.android.application' }}\nandroid {{\n namespace '{project['package']}'\n compileSdk 35\n defaultConfig {{ applicationId '{project['package']}'; minSdk 26; targetSdk 35; versionCode 1; versionName '1.0.0' }}\n compileOptions {{ sourceCompatibility JavaVersion.VERSION_17; targetCompatibility JavaVersion.VERSION_17 }}\n}}\n''').encode('utf-8'),
            'android/build.gradle': b"plugins { id 'com.android.application' version '8.7.3' apply false }\n",
            'android/settings.gradle': b"pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\ndependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }\nrootProject.name='OmegaGeneratedApp'\ninclude ':app'\n",
            'android/gradle.properties': b'org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8\nandroid.useAndroidX=true\n',
        })
    files['README.md'] = (f'''# {project['name']}\n\nProjekt wyeksportowany przez OMEGA AppBuilder.\n\n- Web: pliki `web/` działają na lokalnym serwerze HTTP bez usług zewnętrznych.\n- Android: `cd android && gradle assembleDebug` przy zainstalowanym Android SDK 35 i Gradle 8.\n- Aplikacja natywna korzysta z `TextView`, `Button`, `EditText`, bez WebView.\n- Generator nie wysyła kluczy ani danych do chmury.\n''').encode('utf-8')
    manifest = ''.join(f'{hashlib.sha256(content).hexdigest()}  {path}\n' for path, content in sorted(files.items()))
    files['MANIFEST_SHA256.txt'] = manifest.encode('ascii')
    return files


def build_bundle(document: dict[str, Any]) -> bytes:
    files = generate_files(document)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description='OMEGA Studio NoCode AppBuilder')
    parser.add_argument('command', choices=['build', 'validate'])
    parser.add_argument('project', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    project = json.loads(args.project.read_text(encoding='utf-8'))
    validated = validate_project(project)
    if args.command == 'validate':
        print(f'VALID: {validated["slug"]} / {len(validated["pages"])} pages')
    else:
        if args.output is None:
            parser.error('--output jest wymagane przy build')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(build_bundle(validated))
        print(f'BUILT: {args.output} ({args.output.stat().st_size} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
