"""OMEGA Studio Ultimate standalone CLI for local, explicit operations."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from .archives import pack_zip, extract_zip, pack_rar, extract_rar
from .assets import make_svg, make_png, make_wav, make_gltf_animation, make_video
from .crawler import GitHubOrgCrawler, RepositoryIndex
from .remote8080 import RemoteConfig, serve
from .seal import seal_python_source
from .simulation import run_simulation
from .streamer import copy_file
from .quantum_topology import QuantumASTResonator
from .self_healing_ast import repair_python_source
from .network_chaos import simulate_mobile_network
from .holographic_memory import HolographicMemoryWeaver


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='omega-ultimate',description='OMEGA Studio local tooling')
    commands = parser.add_subparsers(dest='command',required=True)
    for command in ('zip-pack','zip-extract','rar-pack','rar-extract','copy'):
        sub = commands.add_parser(command)
        sub.add_argument('source',type=Path)
        sub.add_argument('destination',type=Path)
    sub = commands.add_parser('asset')
    sub.add_argument('kind',choices=('svg','png','wav','gltf','mp4'))
    sub.add_argument('destination',type=Path)
    sub.add_argument('--text',default='OMEGA Studio')
    sub = commands.add_parser('crawl')
    sub.add_argument('organization')
    sub.add_argument('--pages',type=int,default=20)
    sub.add_argument('--index',type=Path,default=Path('omega-repositories.sqlite3'))
    sub = commands.add_parser('search')
    sub.add_argument('query')
    sub.add_argument('--index',type=Path,default=Path('omega-repositories.sqlite3'))
    sub = commands.add_parser('seal')
    sub.add_argument('source',type=Path)
    sub.add_argument('--key-env',default='OMEGA_SEAL_KEY')
    sub = commands.add_parser('simulate')
    sub.add_argument('--seed',type=int,default=20261110)
    sub.add_argument('--jobs',type=int,default=128)
    sub = commands.add_parser('quantum')
    sub.add_argument('source', type=Path)
    sub = commands.add_parser('heal')
    sub.add_argument('source', type=Path)
    sub = commands.add_parser('network-chaos')
    sub.add_argument('--seed', type=int, default=20261110)
    sub.add_argument('--steps', type=int, default=1000)
    sub.add_argument('--loss', type=float, default=0.1)
    sub.add_argument('--jitter-ms', type=int, default=50)
    sub = commands.add_parser('holographic-index')
    sub.add_argument('source', type=Path)
    sub.add_argument('--index', type=Path, required=True)
    sub = commands.add_parser('serve')
    sub.add_argument('workspace',type=Path)
    sub.add_argument('--bind',default='127.0.0.1')
    sub.add_argument('--port',type=int,default=8080)
    sub.add_argument('--username',default='omega')
    sub.add_argument('--password-env',default='OMEGA_REMOTE_PASSWORD')
    sub.add_argument('--tls-cert',type=Path)
    sub.add_argument('--tls-key',type=Path)
    args=parser.parse_args(argv)
    if args.command=='zip-pack':result=pack_zip(args.source,args.destination)
    elif args.command=='zip-extract':result=extract_zip(args.source,args.destination)
    elif args.command=='rar-pack':result=pack_rar(args.source,args.destination)
    elif args.command=='rar-extract':result=extract_rar(args.source,args.destination)
    elif args.command=='copy':result=copy_file(args.source,args.destination)
    elif args.command=='asset':
        if args.kind=='svg':data=make_svg(args.text).encode()
        elif args.kind=='png':data=make_png(512,512,(7,8,10))
        elif args.kind=='wav':data=make_wav(440,1.0)
        elif args.kind=='mp4':
            result=make_video(args.destination)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        else:data=json.dumps(make_gltf_animation(),indent=2).encode()
        args.destination.parent.mkdir(parents=True,exist_ok=True)
        args.destination.write_bytes(data)
        result={'kind':args.kind,'bytes':len(data),'path':str(args.destination)}
    elif args.command=='crawl':
        with GitHubOrgCrawler(token=os.getenv('OMEGA_GITHUB_TOKEN')) as crawler:
            items=crawler.crawl(args.organization,pages=args.pages)
        with RepositoryIndex(args.index) as index:
            result={'indexed':index.upsert(items),'total':index.count(),'organization':args.organization}
    elif args.command=='search':
        with RepositoryIndex(args.index) as index:
            result={'results':index.search(args.query)}
    elif args.command=='seal':
        secret=os.getenv(args.key_env,'').encode()
        result=seal_python_source(args.source.read_text('utf-8'),secret=secret)
    elif args.command=='simulate':result=run_simulation(seed=args.seed,jobs=args.jobs)
    elif args.command=='quantum':result=QuantumASTResonator().analyze(args.source.read_text('utf-8'))
    elif args.command=='heal':result=repair_python_source(args.source.read_text('utf-8'))
    elif args.command=='network-chaos':
        result=simulate_mobile_network(seed=args.seed,steps=args.steps,loss=args.loss,jitter_ms=args.jitter_ms)
    elif args.command=='holographic-index':
        result=HolographicMemoryWeaver(args.index).index(args.source)
    elif args.command=='serve':
        config=RemoteConfig(bind=args.bind,port=args.port,username=args.username,
                            password=os.getenv(args.password_env,''),tls_cert=args.tls_cert,tls_key=args.tls_key)
        serve(args.workspace,config)
        return 0
    else:raise AssertionError('Unknown command')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,RuntimeError) as exc:
        print(f'OMEGA error: {exc}',file=sys.stderr)
        sys.exit(2)
