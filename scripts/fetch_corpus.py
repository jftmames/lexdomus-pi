"""Download unreviewed candidates outside the repository; never update active corpus.

Requires an explicit plan and new destination. Network access is manual only.
A successful HTTP response or an allowed host is NOT legal source approval.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlsplit
import requests

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {'www.boe.es', 'eur-lex.europa.eu', 'www.wipo.int', 'www.law.cornell.edu'}
MAX_BYTES = 8 * 1024 * 1024
CONTENT_TYPES = {'text/html', 'text/plain', 'application/pdf', 'application/xml', 'text/xml'}


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {'purpose', 'sources'} or plan['purpose'] != 'download_for_review':
        raise ValueError('Explicit download-for-review plan required')
    sources = plan['sources']
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        raise ValueError('Plan must contain 1–20 sources')
    seen = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {'id', 'url'}:
            raise ValueError('Source id and URL required')
        identifier = source['id']
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', identifier) or identifier in seen:
            raise ValueError('Unique safe identifiers required')
        seen.add(identifier)
        if not isinstance(source['url'], str) or any(c.isspace() for c in source['url']):
            raise ValueError('Invalid URL')
        url = urlsplit(source['url'])
        if (url.scheme != 'https' or url.hostname not in HOSTS or url.username or url.password
                or url.port not in (None, 443) or url.fragment):
            raise ValueError('Only explicit HTTPS URLs on supported hosts are allowed')
    return sources


def download(plan_bytes, destination):
    sources = validate_plan(json.loads(plan_bytes))
    destination = Path(destination)
    if not destination.is_absolute() or destination.resolve().is_relative_to(ROOT):
        raise ValueError('Destination must be absolute and outside the repository')
    destination.mkdir(parents=False, exist_ok=False)
    try:
        records = []
        with requests.Session() as session:
            session.trust_env = False  # Do not inherit proxies or netrc credentials.
            for source in sources:
                with session.get(source['url'], stream=True, allow_redirects=False, timeout=(10, 30)) as response:
                    if response.status_code != 200:
                        raise ValueError('Download did not return 200; redirects require separate review')
                    content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                    if content_type not in CONTENT_TYPES:
                        raise ValueError('Unsupported content type')
                    length = response.headers.get('Content-Length')
                    if length is not None and (not length.isdigit() or int(length) > MAX_BYTES):
                        raise ValueError('Invalid or excessive content length')
                    filename = source['id'] + '.body'
                    count = 0
                    digest = hashlib.sha256()
                    with (destination / filename).open('xb') as output:
                        for part in response.iter_content(chunk_size=65536):
                            count += len(part)
                            if count > MAX_BYTES:
                                raise ValueError('Download exceeds size bound')
                            output.write(part)
                            digest.update(part)
                    if not count:
                        raise ValueError('Empty source')
                    records.append({**source, 'file': filename, 'bytes': count, 'sha256': digest.hexdigest(),
                                    'content_type': content_type, 'state': 'unreviewed'})
        manifest = {'schema_version': 1, 'purpose': 'download_for_review', 'state': 'unreviewed',
                    'activated': False, 'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(),
                    'downloaded_at': datetime.now(timezone.utc).isoformat(), 'sources': records}
        (destination / 'download-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        (destination / 'README.txt').write_text(
            'UNREVIEWED DOWNLOADS. Not admitted corpus, not a T05 candidate or T06 snapshot.\n'
            'Verify identity, version, reuse and professional review before separate ingestion.\n', encoding='utf-8')
        return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = download(args.plan.read_bytes(), args.output_dir)
        print(f"Downloaded {len(manifest['sources'])} unreviewed candidate(s); no corpus activated")
        return 0
    except Exception:
        print('Download BLOCKED: review plan, destination and HTTP response; no corpus activated', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
