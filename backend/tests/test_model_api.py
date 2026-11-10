from pathlib import Path
from fastapi.testclient import TestClient
from omega_actions.api import create_app
from omega_actions.config import Settings
from omega_actions.model_studio import ModelParameters

def test_model_api_requires_token(tmp_path):
    app=create_app(Settings(home=tmp_path/'home'))
    with TestClient(app,base_url="http://localhost") as client:
        assert client.get('/api/models').status_code==401
        h={'X-OMEGA-Token':app.state.token}
        assert client.get('/api/models',headers=h).json()=={'models':[]}
        r=client.post('/api/models/parameters',json={'context':4096,'threads':4},headers=h)
        assert r.status_code==200 and r.json()['context']==4096
        assert client.post('/api/models/parameters',json={'context':0},headers=h).status_code==422

def test_model_api_gguf_inspection(tmp_path):
    import struct
    p=tmp_path/'home'/'models'/'tiny.gguf';p.parent.mkdir(parents=True)
    p.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,0))
    app=create_app(Settings(home=tmp_path/'home'))
    with TestClient(app,base_url="http://localhost") as client:
        h={'X-OMEGA-Token':app.state.token}
        assert client.get('/api/models',headers=h).json()['models'][0]['name']=='tiny.gguf'
        assert client.get('/api/models/tiny.gguf',headers=h).json()['version']==3
        assert client.get('/api/models/..%2Foutside.gguf',headers=h).status_code in (404,422)
