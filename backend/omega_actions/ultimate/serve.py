"""Run the OMEGA browser IDE on loopback or authenticated TLS endpoint."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
from .remote8080 import RemoteConfig, RemoteError, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='OMEGA Studio authenticated browser IDE')
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--username', default='omega')
    parser.add_argument('--password-env', default='OMEGA_REMOTE_PASSWORD')
    parser.add_argument('--tls-cert', type=Path)
    parser.add_argument('--tls-key', type=Path)
    args = parser.parse_args(argv)
    try:
        config = RemoteConfig(bind=args.bind, port=args.port, username=args.username,
                              password=os.getenv(args.password_env, ''),
                              tls_cert=args.tls_cert, tls_key=args.tls_key)
        workspace = args.workspace.resolve(strict=True)
        if not workspace.is_dir():
            raise RemoteError('Workspace must be a directory')
        serve(workspace, config)
        return 0
    except (RemoteError, OSError) as exc:
        print('OMEGA remote server: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
