from pathlib import Path
import pytest
from omega_actions.act_bridge import ActBridge,ActError

def test_act_bridge_dry_run_never_invokes_cloud(tmp_path):
    (tmp_path/'.github/workflows').mkdir(parents=True)
    wf=tmp_path/'.github/workflows/ci.yml';wf.write_text('name: Test\n')
    bridge=ActBridge(binary='act')
    cmd=bridge.command(tmp_path,wf,job='test')
    assert cmd[0]=='act' and '-W' in cmd and '-j' in cmd
    assert not any('github.com' in x for x in cmd)
    with pytest.raises(ActError):bridge.command(tmp_path,tmp_path/'outside.yml')
