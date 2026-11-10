"""GGUF/Hugging Face local CLI. No paid services or implicit GitHub Actions."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from .model_studio import GGUFInspector, ModelCatalog, ModelParameters, HFDownload
from .inference import LlamaCli
from .toolchains import detect_toolchains


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(prog='omega-models',description='OMEGA Studio local model manager')
    sub=p.add_subparsers(dest='cmd',required=True)
    inspect=sub.add_parser('inspect');inspect.add_argument('path',type=Path)
    ls=sub.add_parser('list');ls.add_argument('--root',type=Path,default=Path.home()/'.omega-actions/models')
    dl=sub.add_parser('download');dl.add_argument('repo');dl.add_argument('filename');dl.add_argument('--revision',default='main')
    dl.add_argument('--sha256');dl.add_argument('--root',type=Path,default=Path.home()/'.omega-actions/models')
    run=sub.add_parser('run');run.add_argument('model',type=Path);run.add_argument('prompt');run.add_argument('--llama-cli',type=Path,required=True)
    run.add_argument('--context',type=int,default=4096);run.add_argument('--threads',type=int,default=4)
    sub.add_parser('toolchains')
    args=p.parse_args(argv)
    try:
        if args.cmd=='inspect':result=GGUFInspector.inspect(args.path)
        elif args.cmd=='list':result={'models':ModelCatalog(args.root).list()}
        elif args.cmd=='download':
            root=args.root.expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
            result=HFDownload().download(args.repo,args.revision,args.filename,root/Path(args.filename).name,
                                         os.getenv('HF_TOKEN'),args.sha256)
        elif args.cmd=='run':
            result=LlamaCli(args.llama_cli).run(args.model,ModelParameters(context=args.context,threads=args.threads),args.prompt)
        else:result=detect_toolchains()
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError,RuntimeError) as e:
        print(f'ERROR: {type(e).__name__}: {e}',file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
