#!/usr/bin/env python3
"""Serve the three observed LLMail misses for local, task-relative owner review."""

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.local-data/corpus-review-01/prepared/candidates.jsonl'
SUMMARY = ROOT / '.local-data/feature-v4-llmail-cutoff-01/summary.json'
OUTPUT = ROOT / '.local-data/feature-v4-llmail-owner-review-01'
HTML = ROOT / 'scripts/llmail_miss_review.html'
EXPECTED_SUMMARY_SHA256 = '315904c54076f355abd13dc57ab56629cdc55c487071f7b82c10eda1d3975629'
EXPECTED_SOURCE_SHA256 = '842b73014b1fc071cf9a61f1daccdd144be899ebf427970b7c8ea3bc539aec9e'
LABELS = {'attack', 'benign', 'unclear'}
BOUNDARY = {'yes', 'no', 'unclear'}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_packet() -> tuple[list[dict], str, dict]:
    summary_raw = SUMMARY.read_bytes()
    if sha(summary_raw) != EXPECTED_SUMMARY_SHA256:
        raise ValueError('LLMail diagnostic summary changed')
    summary = json.loads(summary_raw)
    ids = summary['missed_attack_ids']
    if len(ids) != 3 or len(set(ids)) != 3:
        raise ValueError('expected three distinct missed IDs')
    source_raw = SOURCE.read_bytes()
    if sha(source_raw) != EXPECTED_SOURCE_SHA256:
        raise ValueError('pinned candidate source changed')
    found = {}
    for line in source_raw.splitlines():
        row = json.loads(line)
        if row['id'] in ids:
            if row['id'] in found:
                raise ValueError('duplicate missed candidate ID')
            found[row['id']] = row
    if set(found) != set(ids):
        raise ValueError('missed candidates not found in pinned source')
    rows = []
    for index, candidate_id in enumerate(ids, 1):
        row = found[candidate_id]
        if (row['source_origin'] != 'microsoft/llmail-inject-challenge'
                or row['source_revision'] != '1063bdf01ec8762b812d5e06ee768a06faa5a6f7'
                or row['native_role'] != 'email' or row['label'] != 1
                or not row['trusted_task'] or not row['untrusted_text']):
            raise ValueError('unexpected missed candidate provenance')
        rows.append({'review_key': f'M{index:02d}', 'candidate_id': candidate_id,
                     'trusted_task': row['trusted_task'], 'untrusted_text': row['untrusted_text'],
                     'native_role': row['native_role']})
    packet_raw = json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()
    provenance = {'diagnostic_summary_sha256': sha(summary_raw),
                  'candidate_source_sha256': sha(source_raw),
                  'source_revision': '1063bdf01ec8762b812d5e06ee768a06faa5a6f7',
                  'selection': 'all three false negatives at the observed diagnostic cutoff',
                  'already_observed_development_data': True}
    return rows, sha(packet_raw), provenance


def validate(payload: dict, rows: list[dict], packet_sha: str, provenance: dict) -> dict:
    if set(payload) != {'packet_sha256', 'reviewer_id', 'answers'} or payload['packet_sha256'] != packet_sha:
        raise ValueError('packet version or fields differ')
    reviewer = payload['reviewer_id']
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100:
        raise ValueError('enter your name or initials')
    answers = payload['answers']
    if not isinstance(answers, list) or len(answers) != len(rows):
        raise ValueError('review all three cases')
    validated = []
    for expected, answer in zip(rows, answers):
        if not isinstance(answer, dict) or set(answer) != {'review_key', 'label', 'boundary_clear', 'reason'}:
            raise ValueError('answer fields differ')
        reason = answer['reason']
        if (answer['review_key'] != expected['review_key'] or answer['label'] not in LABELS
                or answer['boundary_clear'] not in BOUNDARY or not isinstance(reason, str)
                or not reason.strip() or len(reason) > 2000):
            raise ValueError(f"{expected['review_key']}: choose a label and boundary answer, and explain why")
        validated.append({'review_key': expected['review_key'], 'candidate_id': expected['candidate_id'],
                          'human_judgment': answer['label'], 'task_boundary_clear': answer['boundary_clear'],
                          'reason': reason.strip()})
    return {'kind': 'llmail-missed-case-owner-review-01', 'packet_sha256': packet_sha,
            'provenance': provenance, 'reviewer_id': reviewer.strip(),
            'reviewed_at_utc': datetime.now(timezone.utc).isoformat(), 'answers': validated,
            'note': 'Review of already observed development data; not a new final test.'}


class Handler(BaseHTTPRequestHandler):
    rows: list[dict] = []
    packet_sha: str = ''
    provenance: dict = {}

    def send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, value: dict) -> None:
        self.send(status, json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def local_host(self) -> bool:
        port = self.server.server_port
        return self.headers.get('Host') in {f'127.0.0.1:{port}', f'localhost:{port}'}

    def do_GET(self) -> None:
        if not self.local_host():
            self.send_json(403, {'error': 'local host required'})
            return
        if self.path in ('/', '/index.html'):
            self.send(200, HTML.read_bytes(), 'text/html; charset=utf-8')
        elif self.path == '/cases':
            self.send_json(200, {'packet_sha256': self.packet_sha, 'cases': self.rows})
        elif self.path == '/health':
            self.send_json(200, {'status': 'ready', 'cases': len(self.rows)})
        else:
            self.send_json(404, {'error': 'not found'})

    def do_POST(self) -> None:
        if not self.local_host():
            self.send_json(403, {'error': 'local host required'})
            return
        if self.path != '/submit':
            self.send_json(404, {'error': 'not found'})
            return
        allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
        if self.headers.get('Origin') not in allowed:
            self.send_json(403, {'error': 'open the local review page to submit'})
            return
        try:
            size = int(self.headers.get('Content-Length', '-1'))
            if size < 0 or size > 16_384 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('invalid submission size or content type')
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError('submission must be an object')
            result = validate(payload, self.rows, self.packet_sha, self.provenance)
        except (ValueError, TypeError, KeyError) as exc:
            self.send_json(400, {'error': str(exc)})
            return
        OUTPUT.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        filename = f'owner-review-{stamp}-{secrets.token_hex(3)}.json'
        raw = (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode()
        try:
            with os.fdopen(os.open(OUTPUT / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
                file.write(raw)
                file.flush()
                os.fsync(file.fileno())
        except OSError:
            self.send_json(500, {'error': 'could not save review'})
            return
        self.send_json(200, {'saved': True, 'filename': filename, 'count': len(self.rows)})

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    Handler.rows, Handler.packet_sha, Handler.provenance = load_packet()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
