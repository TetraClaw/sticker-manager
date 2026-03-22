#!/usr/bin/env python3
"""Batch collector for stickers from URLs or local files."""
from __future__ import annotations
import argparse
import hashlib
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests

from common import get_lang, SUPPORTED_EXTS, build_vision_plan

DEFAULT_TARGET_COUNT = 15
DEFAULT_MIN_BYTES = 10 * 1024
DEFAULT_WORKERS = 1


def build_semantic_batch(final_items: list[dict], lang: str) -> dict:
    return {
        'task': 'After collection, analyze each selected sticker image for meaning, emotion, scene, and suitable reaction use.',
        'language': lang,
        'items': [
            {
                'name': item['name'],
                'path': item['path'],
                'vision_plan': build_vision_plan(item['path'], 'Describe sticker meaning, emotion, scene, and reaction use.', lang),
            }
            for item in final_items
        ],
    }


def infer_extension(source: str, fallback: str = '.bin') -> str:
    parsed = urlparse(source)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext in SUPPORTED_EXTS:
        return ext
    local_ext = os.path.splitext(source)[1].lower()
    if local_ext in SUPPORTED_EXTS:
        return local_ext
    return fallback


def load_sources(args_sources: list[str], sources_file: str | None) -> list[str]:
    values = list(args_sources)
    if sources_file:
        for line in Path(sources_file).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                values.append(line)
    return values


def read_bytes(source: str) -> bytes:
    if source.startswith('http://') or source.startswith('https://'):
        r = requests.get(source, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.google.com/'}, timeout=30)
        r.raise_for_status()
        return r.content
    return Path(source).read_bytes()


def collect_one(item: tuple[int, str], prefix: str, out_dir: Path, min_bytes: int) -> dict:
    idx, source = item
    data = read_bytes(source)
    size = len(data)
    if size < min_bytes:
        return {'source': source, 'status': 'low_quality', 'size': size}
    ext = infer_extension(source, '.gif')
    digest = hashlib.md5(data).hexdigest()
    name = f'{prefix}_{idx:02d}{ext}'
    path = out_dir / name
    path.write_bytes(data)
    return {'source': source, 'status': 'saved', 'size': size, 'hash': digest, 'path': str(path), 'name': name}


def dedupe_saved(results: list[dict]) -> tuple[list[dict], list[dict]]:
    seen = {}
    keep = []
    dropped = []
    for item in results:
        if item.get('status') != 'saved':
            continue
        digest = item['hash']
        if digest in seen:
            Path(item['path']).unlink(missing_ok=True)
            item['status'] = 'duplicate'
            dropped.append(item)
        else:
            seen[digest] = item['path']
            keep.append(item)
    return keep, dropped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('sources', nargs='*')
    parser.add_argument('--sources-file')
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--prefix', default='sticker')
    parser.add_argument('--target-count', type=int, default=DEFAULT_TARGET_COUNT)
    parser.add_argument('--min-bytes', type=int, default=DEFAULT_MIN_BYTES)
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS, help='Deprecated. Collector now runs in single-thread mode; values other than 1 are ignored.')
    parser.add_argument('--lang')
    parser.add_argument('--no-semantic-plan', action='store_true')
    args = parser.parse_args()

    lang = get_lang(args.lang)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = load_sources(args.sources, args.sources_file)
    if not sources:
        print('No sources provided.')
        return 1

    indexed = list(enumerate(sources, start=1))
    results = []
    effective_workers = 1
    if args.workers != 1:
        print(f'WORKERS_IGNORED={args.workers}')
    print(f'EFFECTIVE_WORKERS={effective_workers}')
    for item in indexed:
        results.append(collect_one(item, args.prefix, out_dir, args.min_bytes))

    keep, dropped = dedupe_saved(results)
    low_quality = [r for r in results if r.get('status') == 'low_quality']
    kept_sorted = sorted(keep, key=lambda x: x['size'], reverse=True)
    final = kept_sorted[:args.target_count]
    extra = kept_sorted[args.target_count:]
    for item in extra:
        Path(item['path']).unlink(missing_ok=True)
        item['status'] = 'trimmed'

    print(f'TARGET_COUNT={args.target_count}')
    print(f'SAVED_UNIQUE={len(keep)}')
    print(f'LOW_QUALITY={len(low_quality)}')
    print(f'DUPLICATES={len(dropped)}')
    print(f'FINAL_COUNT={len(final)}')
    for item in final:
        print(f"KEEP {item['name']} {item['size']}")
    if not args.no_semantic_plan:
        import json
        print('__SEMANTIC_BATCH__:' + json.dumps(build_semantic_batch(final, lang), ensure_ascii=False))
    if len(final) < args.target_count:
        print(f'NEED_MORE={args.target_count - len(final)}')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
