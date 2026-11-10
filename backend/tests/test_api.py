import asyncio
import tempfile
import unittest
from pathlib import Path
import httpx
from omega_actions.api import create_app
from omega_actions.config import Settings

class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_compile_and_run(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); repo=root/'repo';repo.mkdir()
            (repo/'ci.yml').write_text('jobs:\n  test:\n    steps:\n      - run: echo api-success\n')
            app=create_app(Settings(root/'state',unsafe_native=True))
            transport=httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1') as client:
                self.assertEqual((await client.get('/api/runs')).status_code,401)
                headers={'X-OMEGA-Token':app.state.token}
                bad=await client.post('/api/compile',headers={**headers,'Origin':'https://evil.example'},json={'workflow':str(repo/'ci.yml')})
                self.assertEqual(bad.status_code,403)
                ok=await client.post('/api/compile',headers=headers,json={'workflow':str(repo/'ci.yml')})
                self.assertEqual(ok.status_code,200)
                self.assertEqual(len(ok.json()['jobs']),1)
                start=await client.post('/api/runs',headers=headers,json={'workflow':str(repo/'ci.yml'),'repo':str(repo),'executor':'native'})
                self.assertEqual(start.status_code,200,start.text)
                rid=start.json()['id']
                for _ in range(60):
                    result=(await client.get('/api/runs/'+rid,headers=headers))
                    if result.status_code==200 and result.json()['status'] in ('success','failure','cancelled'):break
                    await asyncio.sleep(0.05)
                self.assertEqual(result.json()['status'],'success',result.text)
                self.assertIn('api-success',str(app.state.engine.store.logs(rid)))
                page=await client.get('/')
                self.assertIn('OMEGA',page.text)
                self.assertIn(app.state.token,page.text)

if __name__=='__main__':unittest.main()

class ArtifactApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_artifact_download_and_live_log(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);repo=root/'repo';repo.mkdir()
            (repo/'ci.yml').write_text('''jobs:
  build:
    steps:
      - run: echo payload > file.txt
      - uses: actions/upload-artifact@v4
        with:
          name: result
          path: file.txt
''')
            app=create_app(Settings(root/'state',unsafe_native=True))
            h={'X-OMEGA-Token':app.state.token}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1') as client:
                started=await client.post('/api/runs',headers=h,json={'repo':str(repo),'workflow':str(repo/'ci.yml'),'executor':'native'})
                rid=started.json()['id']
                for _ in range(100):
                    res=await client.get(f'/api/runs/{rid}',headers=h)
                    if res.status_code==200 and res.json()['status'] in ('success','failure'):break
                    await asyncio.sleep(.05)
                self.assertEqual(res.json()['status'],'success')
                zipres=await client.get(f'/api/artifacts/{rid}/result',headers=h)
                self.assertEqual(zipres.status_code,200)
                self.assertTrue(zipres.content.startswith(b'PK'))
                stream=await client.get(f'/api/runs/{rid}/events',headers=h)
                self.assertIn('data:',stream.text)
                self.assertIn('event: done',stream.text)
