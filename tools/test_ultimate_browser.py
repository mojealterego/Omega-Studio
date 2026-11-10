"""Chromium DOM E2E plus real HTTP API smoke; browser network is sandbox-blocked."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import httpx
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
PORT=18080
ENV={**os.environ,'PYTHONPATH':str(ROOT/'backend'),
     'OMEGA_ACTIONS_HOME':str(ROOT/'validation'/'ultimate'/'browser_home')}
log_path=ROOT/'validation'/'ultimate'/'browser_server.log'
log=log_path.open('w')
server=subprocess.Popen([sys.executable,'-m','uvicorn','omega_actions.api:create_app',
                         '--factory','--host','127.0.0.1','--port',str(PORT),'--no-access-log'],
                        cwd=ROOT,env=ENV,stdout=log,stderr=subprocess.STDOUT)
try:
    for _ in range(60):
        if server.poll() is not None:raise RuntimeError('Backend terminated before listening')
        try:
            response=httpx.get(f'http://127.0.0.1:{PORT}/ultimate',timeout=1)
            if response.status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.2)
    else:raise RuntimeError('Backend did not start')
    token=re.search(r'<meta name="omega-token" content="([^"]+)"',response.text).group(1)
    headers={'X-OMEGA-Token':token}
    assert httpx.get(f'http://127.0.0.1:{PORT}/api/ultimate/status',headers=headers).status_code==200
    assert httpx.post(f'http://127.0.0.1:{PORT}/api/ultimate/nocode',headers=headers,json={'description':'Omega app'}).status_code==200
    assert httpx.get(f'http://127.0.0.1:{PORT}/api/ultimate/status').status_code==401
    html=(ROOT/'backend'/'omega_actions'/'static'/'ultimate.html').read_text().replace('OMEGA_SESSION_TOKEN','test-session-token')
    css=(ROOT/'backend'/'omega_actions'/'static'/'ultimate.css').read_text()
    js=(ROOT/'backend'/'omega_actions'/'static'/'ultimate.js').read_text()
    # Replace external asset tags; Chromium in this sandbox disallows navigation to local HTTP.
    html=html.replace('<link rel="stylesheet" href="/static/ultimate.css">','').replace('<script defer src="/static/ultimate.js"></script>','')
    mock_js='''window.__upstreamSyncCalls = []; window.fetch = async (url, options={}) => {
      const path = String(url);
      if (path.includes('/upstreams/sync')) window.__upstreamSyncCalls.push(JSON.parse(options.body || '{}'));
      const body = path.includes('/upstreams/sync') ? {name:'termux-app',commit:'abc123',upstream_source_executed:false} :
        path.includes('/upstreams') ? {sources:[{name:'termux-app',repository:'https://github.com/termux/termux-app.git',commit:'8629e632fcb95da272221be327db653fb24befe9',license:'GPL-3.0-only',role:'android'}]} :
        path.includes('/status') ? {features:{repo_crawler:'ready'}} :
        path.includes('/search') ? {total:20,items:[]} :
        path.includes('/nocode') ? {html:'<h1>Moja aplikacja premium</h1>'} :
        path.includes('/hyper/ast') ? {model:'classical-complex-hilbert',dimension:24,findings:[]} :
        path.includes('/hyper/heal') ? {source:'def f():\\n    return 1\\n',repaired:true,changes:[{line:1,rule:'missing_header_colon'}]} :
        path.includes('/hyper/network') ? {model:'deterministic-state-machine',sent:100,lost:10,delivered:90,reconnects:2} :
        path.includes('/analyze') ? {mode:'leak',syntax_valid:true,verified:true,analyzers:4,findings:[]} :
        path.includes('/simulate') ? {status:'PASS',seed:20261110,jobs:128,invariants:{crawler:true},external_twin:{invariants:{safe:true}}} :
        {indexed:20,total:20};
      return new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}});
    };'''
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.set_content(html,wait_until='load')
        page.add_style_tag(content=css)
        page.evaluate(mock_js)
        page.add_script_tag(content=js)
        page.locator('#systemState').get_by_text('LOCAL READY').wait_for(timeout=10000)
        page.screenshot(path=str(ROOT/'validation'/'ultimate'/'premium_desktop.png'),full_page=True)
        page.wait_for_function("document.querySelectorAll('#upstreamSelect option').length > 0", timeout=10000)
        page.locator('#upstreamFetch').click()
        assert page.evaluate('window.__upstreamSyncCalls.length') == 0
        page.locator('#upstreamConsent').check()
        page.locator('#upstreamFetch').click()
        page.get_by_text('Pobrano źródła termux-app').wait_for(timeout=10000)
        assert page.evaluate('window.__upstreamSyncCalls.length') == 1
        page.locator('#generateButton').click()
        page.wait_for_function("!document.getElementById('exportButton').disabled", timeout=10000)
        assert 'Moja aplikacja premium' in page.locator('#nocodePreview').get_attribute('srcdoc')
        page.locator('#analyzeButton').click()
        page.get_by_text('\"analyzers\": 4').wait_for(timeout=10000)
        page.locator('#hyperAstButton').click()
        page.get_by_text('classical-complex-hilbert').wait_for(timeout=10000)
        page.locator('#hyperNetworkButton').click()
        page.get_by_text('deterministic-state-machine').wait_for(timeout=10000)
        page.locator('#simulateButton').click()
        page.get_by_text('"status": "PASS"').wait_for(timeout=10000)
        page.screenshot(path=str(ROOT/'validation'/'ultimate'/'premium_simulation.png'),full_page=True)
        mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
        mobile.on('pageerror',lambda error:errors.append(str(error)))
        mobile.set_content(html,wait_until='load')
        mobile.add_style_tag(content=css)
        mobile.evaluate(mock_js)
        mobile.add_script_tag(content=js)
        mobile.screenshot(path=str(ROOT/'validation'/'ultimate'/'premium_mobile.png'),full_page=True)
        assert mobile.locator('h1').first.is_visible()
        assert not errors,errors
        result={'status':'PASS','http_smoke_port':PORT,'http_smoke':'REAL_LOCAL_HTTP',
                'chromium_ui':'MOCKED_FETCH_BECAUSE_BROWSER_NETWORK_POLICY',
                'checks':['real HTTP 200','real API auth 401','real NoCode API','desktop DOM','NoCode preview',
                          'simulated UI status','mobile viewport','0 JS page errors'],
                'page_errors':errors,'screenshots':['premium_desktop.png','premium_simulation.png','premium_mobile.png']}
        (ROOT/'validation'/'ultimate'/'browser_result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
        browser.close()
finally:
    server.terminate()
    try:server.wait(timeout=5)
    except subprocess.TimeoutExpired:server.kill();server.wait()
    log.close()
