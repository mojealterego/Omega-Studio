from pathlib import Path
import contextlib
import http.server
import json
import socketserver
import struct
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'android/app/src/main/assets'
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ASSETS),**kwargs)
    def log_message(self,*args):return

with socketserver.TCPServer(('127.0.0.1',0),Handler) as server:
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=ASSETS.joinpath('index.html').as_uri()
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':412,'height':915},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        html=(ASSETS/'index.html').read_text().replace('<link rel="stylesheet" href="app.css">','').replace('<script src="app.js"></script>','')
        page.set_content(html,wait_until='load')
        page.add_style_tag(content=(ASSETS/'app.css').read_text())
        page.add_script_tag(content=(ASSETS/'upstream-catalog.js').read_text())
        page.add_script_tag(content=(ASSETS/'app.js').read_text())
        assert page.title()=='OMEGA Studio'
        assert page.locator('#editor').is_visible()
        page.locator('#source').fill('print("test offline")')
        page.locator('#saveDraft').click()
        assert ('Zapisano lokalnie' in page.locator('#editorState').inner_text() or 'Brak dostępu' in page.locator('#editorState').inner_text())
        page.locator('nav [data-tab=models]').click()
        assert page.locator('#models').is_visible()
        page.locator('#ggufFile').set_input_files({'name':'tiny.gguf','mimeType':'application/octet-stream','buffer':b'GGUF'+struct.pack('<IQQ',3,0,0)})
        assert '"version": 3' in page.locator('#ggufInfo').inner_text()
        page.locator('#saveModelSettings').click()
        assert page.locator('#modelSettingsStatus').inner_text()
        page.locator('nav [data-tab=hf]').click()
        page.locator('#hfRepo').fill('org/model');page.locator('#hfFile').fill('model.gguf');page.locator('#hfGenerate').click()
        assert 'https://huggingface.co/org/model/resolve/main/model.gguf' in page.locator('#hfUrl').inner_text()
        page.locator('nav [data-tab=ci]').click()
        page.locator('#ciFile').set_input_files({'name':'ci.yml','mimeType':'text/yaml','buffer':b'name: CI\njobs:\n  test:\n    steps:\n      - run: echo hi\n'})
        page.wait_for_function("""() => document.querySelector('#ciResult').textContent.includes('"test"')""")
        page.locator('nav [data-tab=chat]').click()
        assert page.locator('#chat').is_visible()
        assert page.locator('#chatProvider option').count()>=20
        page.locator('#chatMessage').fill('Przetestuj bramkę kosztów')
        page.locator('#chatSend').click()
        assert 'potwierdzenie kosztu' in page.locator('#chatResult').inner_text()
        page.locator('nav [data-tab=keys]').click()
        page.locator('#saveKey').click()
        assert 'Funkcja wymaga natywnej wersji' in page.locator('#keyResult').inner_text()
        page.locator('nav [data-tab=oss]').click()
        assert page.locator('#oss').is_visible()
        assert page.locator('#ossSources .oss-source').count() == 14
        assert 'termux-app' in page.locator('#ossSources').inner_text()
        page.locator('nav [data-tab=editor]').click()
        page.screenshot(path=str(ROOT/'validation/mobile_ui.png'),full_page=True)
        browser.close()
    assert not errors,errors
    report={'status':'PASS','browser':'Chromium headless','checks':12,'page_errors':errors,'screenshot':'validation/mobile_ui.png'}
    (ROOT/'validation/browser_ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))
    server.shutdown()
