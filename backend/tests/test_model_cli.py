import struct
from pathlib import Path
from omega_actions.model_cli import main

def test_model_cli_inspect(tmp_path,capsys):
    p=tmp_path/'tiny.gguf';p.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,0))
    assert main(['inspect',str(p)])==0
    assert '"version": 3' in capsys.readouterr().out

def test_model_cli_rejects_invalid(tmp_path,capsys):
    assert main(['inspect',str(tmp_path/'missing.gguf')])==1
    assert 'ERROR:' in capsys.readouterr().err

def test_model_cli_list(tmp_path,capsys):
    assert main(['list','--root',str(tmp_path)])==0
    assert '"models": []' in capsys.readouterr().out
