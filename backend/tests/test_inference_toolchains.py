from pathlib import Path
import pytest
from omega_actions.inference import LlamaCli, InferenceError
from omega_actions.model_studio import ModelParameters
from omega_actions.toolchains import detect_toolchains, LANGUAGES


def test_build_llama_command_without_shell(tmp_path):
    exe=tmp_path/'llama-cli';exe.write_text('')
    model=tmp_path/'model.gguf';model.write_bytes(b'GGUF')
    r=LlamaCli(exe)
    argv=r.build_command(model,ModelParameters(context=2048,threads=4,temperature=.8), 'hello; rm -rf /')
    assert argv[0]==str(exe) and '-m' in argv and '-c' in argv
    assert argv[-1]=='hello; rm -rf /'
    assert all('sh -c' not in x for x in argv)


def test_missing_binary_is_rejected(tmp_path):
    with pytest.raises(InferenceError):LlamaCli(tmp_path/'not-installed').build_command(tmp_path/'model.gguf',ModelParameters(),'hi')


def test_toolchains_detects_installed_and_missing(tmp_path):
    d=detect_toolchains(['python3','nonexistent-omega-language-9876'])
    assert d['python3']['available'] is True
    assert d['nonexistent-omega-language-9876']['available'] is False
    assert 'rust' in LANGUAGES and 'typescript' in LANGUAGES
