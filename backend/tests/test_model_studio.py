import hashlib
import json
import struct
from pathlib import Path
import httpx
import pytest
from omega_actions.model_studio import GGUFError, GGUFInspector, ModelParameters, ModelCatalog, HFDownload, HFError, hf_resolve_url


def gguf_bytes():
    def s(v):
        b=v.encode(); return struct.pack('<Q',len(b))+b
    return (b'GGUF'+struct.pack('<IQQ',3,0,3)
            +s('general.name')+struct.pack('<I',8)+s('Test Model')
            +s('llama.context_length')+struct.pack('<II',4,4096)
            +s('tokenizer.ggml.tokens')+struct.pack('<IIQ',9,8,2)+s('a')+s('b'))


def test_inspect_valid_gguf(tmp_path):
    p=tmp_path/'model.gguf';p.write_bytes(gguf_bytes())
    d=GGUFInspector.inspect(p)
    assert d['version']==3 and d['tensor_count']==0
    assert d['metadata']['general.name']=='Test Model'
    assert d['metadata']['llama.context_length']==4096
    assert d['metadata']['tokenizer.ggml.tokens']==['a','b']


def test_reject_truncated_and_malicious_gguf(tmp_path):
    p=tmp_path/'bad.gguf';p.write_bytes(b'GGUF'+b'\x00'*4)
    with pytest.raises(GGUFError): GGUFInspector.inspect(p)
    p.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,1)+struct.pack('<Q',2**63))
    with pytest.raises(GGUFError): GGUFInspector.inspect(p)


def test_model_parameters_reject_invalid():
    p=ModelParameters(context=4096,threads=4,temperature=.7,top_k=40,top_p=.9,gpu_layers=0,seed=42)
    assert p.to_dict()['context']==4096
    with pytest.raises(ValueError): ModelParameters(context=0)
    with pytest.raises(ValueError): ModelParameters(temperature=float('nan'))
    with pytest.raises(ValueError): ModelParameters(threads=4096)


def test_hf_urls_and_path_validation():
    assert hf_resolve_url('TheBloke/Model-GGUF','main','model.Q4_K_M.gguf').startswith('https://huggingface.co/')
    for repo,rev,path in [('org/x','main','../secret'),('org/x','../main','x.gguf'),('https://evil/x','main','x.gguf'),('org/x','main','x.txt')]:
        with pytest.raises(ValueError): hf_resolve_url(repo,rev,path)


def test_hf_download_resume_and_integrity(tmp_path):
    data=b'GGUF'+b'a'*200
    target=tmp_path/'test.gguf';(tmp_path/'test.gguf.part').write_bytes(data[:33])
    seen=[]
    def handler(request):
        seen.append(request)
        assert request.headers['range']=='bytes=33-'
        return httpx.Response(206,headers={'Content-Range':f'bytes 33-{len(data)-1}/{len(data)}'},content=data[33:])
    client=httpx.Client(transport=httpx.MockTransport(handler),follow_redirects=False)
    r=HFDownload(client=client).download('org/model','main','test.gguf',target,expected_sha256=hashlib.sha256(data).hexdigest())
    assert r['sha256']==hashlib.sha256(data).hexdigest() and target.read_bytes()==data and len(seen)==1


def test_hf_download_does_not_forward_token_to_external_redirect(tmp_path):
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(302,headers={'Location':'https://example.org/private'})),follow_redirects=False)
    with pytest.raises(HFError): HFDownload(client=client).download('org/model','main','test.gguf',tmp_path/'test.gguf',token='secret')
    assert not (tmp_path/'test.gguf').exists()


def test_catalog_prevents_outside_root(tmp_path):
    root=tmp_path/'models';root.mkdir();(root/'m.gguf').write_bytes(gguf_bytes())
    catalog=ModelCatalog(root)
    assert catalog.inspect('m.gguf')['metadata']['general.name']=='Test Model'
    with pytest.raises(ValueError): catalog.inspect('../m.gguf')
