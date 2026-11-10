#!/usr/bin/env python3
"""Acquire official pinned upstream source trees; never executes downloaded code."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from omega_actions.ultimate.upstream_sources import (  # noqa: E402
    CatalogError, SourceSyncError, SourceCatalog, UpstreamSourceManager,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='OMEGA Studio pinned upstream source manager')
    parser.add_argument('--root', type=Path, default=ROOT / 'upstream-sources',
                        help='Existing directory for independent upstream checkouts')
    parser.add_argument('--lock', type=Path, default=ROOT / 'config/upstream_sources.lock.json')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='List pinned source repositories; no network access')
    sync = sub.add_parser('sync', help='Download pinned source(s) after explicit consent')
    sync.add_argument('name', help='Catalog name or all')
    sync.add_argument('--consent', action='store_true', help='Accept download and upstream license obligations')
    verify = sub.add_parser('verify', help='Verify checkout SHA, cleanliness and license digest')
    verify.add_argument('name')
    args = parser.parse_args(argv)
    try:
        catalog = SourceCatalog.load(args.lock)
        if args.command == 'list':
            print(json.dumps({'count': len(catalog.sources), 'sources': catalog.public_info()}, indent=2))
            return 0
        if args.command == 'sync' and not args.consent:
            raise SourceSyncError('Explicit --consent is required before network access and license acceptance')
        if not args.root.is_dir() or args.root.is_symlink():
            raise SourceSyncError('Create an independent non-symlink source directory before synchronization')
        manager = UpstreamSourceManager(catalog, args.root)
        if args.command == 'verify':
            result = manager.verify(args.name)
        elif args.name == 'all':
            result = [manager.sync(item.name, consent=True) for item in catalog.sources]
        else:
            result = manager.sync(args.name, consent=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CatalogError, SourceSyncError, OSError) as exc:
        print('OMEGA source sync blocked: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
