from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
assets=root/'android/app/src/main/assets'
html=(assets/'index.html').read_text()
html=html.replace('<link rel="stylesheet" href="app.css">','<style>'+ (assets/'app.css').read_text()+'</style>')
for name in ('app.js','builder.js','builder-ui.js'):
    html=html.replace(f'<script src="{name}"></script>','<script>'+ (assets/name).read_text().replace('</script>','<\\/script>')+'</script>')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1366,'height':900},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.set_content(html,wait_until='load')
    page.locator('nav button[data-tab="builder"]').click()
    assert page.locator('#builder').is_visible()
    print('count',page.locator('#builderComponents .builder-component').count(),'errors',errors,'status',page.locator('#builderStatus').inner_text())
    assert page.locator('#builderComponents .builder-component').count()==4
    page.locator('#builderPalette [data-type="input"]').click()
    assert page.locator('#builderComponents .builder-component').count()==5
    page.locator('#builderName').fill('OMEGA Premium App')
    assert 'OMEGA Premium App' in page.locator('#builderPreview').get_attribute('srcdoc')
    page.screenshot(path=str(root/'validation/builder_desktop.png'),full_page=True)
    page.set_viewport_size({'width':412,'height':915})
    page.screenshot(path=str(root/'validation/builder_mobile.png'),full_page=True)
    assert not errors, errors
    browser.close()
print('Browser E2E PASS: add component, edit title, live preview, mobile and desktop rendering, no page errors')
