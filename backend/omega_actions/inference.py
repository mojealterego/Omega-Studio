"""Explicit opt-in llama.cpp subprocess adapter for installed local binaries."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
from .model_studio import ModelParameters

class InferenceError(RuntimeError):
    pass

class LlamaCli:
    def __init__(self, executable:Path):
        self.executable=Path(executable).expanduser().resolve()

    def build_command(self, model:Path, settings:ModelParameters, prompt:str)->list[str]:
        if not self.executable.is_file():raise InferenceError('llama-cli executable not installed')
        model=Path(model).expanduser().resolve()
        if not model.is_file() or model.suffix.lower()!='.gguf':raise InferenceError('GGUF model not found')
        if not isinstance(prompt,str) or not 0<len(prompt)<=65536:raise ValueError('Prompt length must be 1..65536')
        return [str(self.executable),'-m',str(model),'-c',str(settings.context),'-t',str(settings.threads),
                '-b',str(settings.batch),'-ngl',str(settings.gpu_layers),
                '--temp',str(settings.temperature),'--top-k',str(settings.top_k),
                '--top-p',str(settings.top_p),'--min-p',str(settings.min_p),
                '--repeat-penalty',str(settings.repeat_penalty),'-s',str(settings.seed),
                '-n',str(settings.max_tokens),'-p',prompt]

    def run(self,model:Path,settings:ModelParameters,prompt:str,timeout:int=300)->dict:
        if not 1<=timeout<=3600:raise ValueError('Timeout must be 1..3600 seconds')
        argv=self.build_command(model,settings,prompt)
        env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','LD_LIBRARY_PATH')}
        try:
            result=subprocess.run(argv,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,
                                  timeout=timeout,check=False)
        except subprocess.TimeoutExpired as exc:raise InferenceError('Inference timeout exceeded') from exc
        except OSError as exc:raise InferenceError(f'Unable to launch llama-cli: {type(exc).__name__}') from exc
        return {'exit_code':result.returncode,'output':result.stdout[:1024*1024],
                'stderr':result.stderr[:16384],'truncated':len(result.stdout)>1024*1024}
