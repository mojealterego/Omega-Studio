"""Visual/DOM E2E of the VS Code UI, not of the native code-server binary."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
assets=root/'android/app/src/main/assets'
html=(assets/'index.html').read_text().replace('<link rel="stylesheet" href="app.css">','<style>'+(assets/'app.css').read_text()+'</style>')
for name in ('app.js','builder.js','builder-ui.js'):
    html=html.replace(f'<script src="{name}"></script>','<script>'+(assets/name).read_text().replace('</script>','<\\/script>')+'</script>')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1366,'height':900},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html,wait_until='load')
    page.locator('nav [data-tab="vscode"]').click()
    assert page.locator('#vscode').is_visible()
    assert page.locator('#vscodeStart').is_visible()
    page.locator('#vscodeStart').click()
    page.wait_for_function("() => document.querySelector('#vscodeStatus').textContent.includes('BŁĄD')")
    assert 'natywnej wersji' in page.locator('#vscodeStatus').inner_text()
    page.screenshot(path=str(root/'validation/vscode_desktop_v13.png'),full_page=True)
    page.set_viewport_size({'width':412,'height':915})
    page.screenshot(path=str(root/'validation/vscode_mobile_v13.png'),full_page=True)
    assert not errors,errors
    browser.close()
result={'status':'PASS','scope':'UI_ONLY','checks':5,'page_errors':[],'runtime_binary_verified':False}
(root/'validation/vscode_browser_v13.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
