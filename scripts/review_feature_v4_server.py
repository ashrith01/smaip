#!/usr/bin/env python3
"""Local-only, answer-free form for human review of the Feature V4 packet."""

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIRECTORY = ROOT / '.local-data/feature-v4-reviewer-packet-01'
PACKET_PATH = REVIEW_DIRECTORY / 'blind-packet.jsonl'
HTML_PATH = ROOT / 'scripts/feature_v4_review.html'
EXPECTED_PACKET_SHA256 = '2d758a233dd770c8f2d0ab5b64e0670294f0c1fed8c88f07272f8c7b2982d61c'
VALID_JUDGMENTS = {'attack', 'benign', 'unclear'}


def load_packet() -> list[dict]:
    raw = PACKET_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_PACKET_SHA256:
        raise ValueError('review packet hash mismatch')
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) != 32 or len({row['review_key'] for row in rows}) != 32:
        raise ValueError('expected 32 unique review cases')
    allowed = {'review_key', 'source_origin', 'native_role', 'trusted_task', 'untrusted_text'}
    if any(set(row) != allowed for row in rows):
        raise ValueError('unexpected fields in blind packet')
    return rows


def validate_submission(payload: dict, keys: list[str]) -> list[dict]:
    if payload.get('packet_sha256') != EXPECTED_PACKET_SHA256:
        raise ValueError('packet version mismatch')
    reviewer_id = payload.get('reviewer_id', '')
    if not isinstance(reviewer_id, str) or len(reviewer_id) > 100:
        raise ValueError('reviewer name is invalid')
    submitted = payload.get('answers')
    if not isinstance(submitted, list) or len(submitted) != len(keys):
        raise ValueError('all 32 answers are required')
    if [item.get('review_key') for item in submitted if isinstance(item, dict)] != keys:
        raise ValueError('review keys must be in packet order')
    now = datetime.now(timezone.utc).isoformat()
    result = []
    for item in submitted:
        if set(item) != {'review_key', 'judgment', 'reason'}:
            raise ValueError('answer has unexpected fields')
        judgment, reason = item['judgment'], item['reason']
        if judgment not in VALID_JUDGMENTS or not isinstance(reason, str) or len(reason) > 2000:
            raise ValueError(f"{item['review_key']}: invalid judgment or note")
        if judgment == 'unclear' and not reason.strip():
            raise ValueError(f"{item['review_key']}: unclear choice requires a note")
        result.append({'review_key': item['review_key'],
                       'human_judgment': 'ambiguous' if judgment == 'unclear' else judgment,
                       'task_boundary_clear': None,
                       'reason': reason.strip(),
                       'reviewer_id': reviewer_id.strip() or 'reviewer-not-named',
                       'reviewed_at_utc': now})
    return result


class ReviewHandler(BaseHTTPRequestHandler):
    rows: list[dict] = []

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: dict) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def do_GET(self) -> None:
        if self.path in ('/', '/index.html'):
            self._send(200, HTML_PATH.read_bytes(), 'text/html; charset=utf-8')
        elif self.path == '/cases':
            self._json(200, {'packet_sha256': EXPECTED_PACKET_SHA256, 'cases': self.rows})
        elif self.path == '/health':
            self._json(200, {'status': 'ready', 'cases': len(self.rows), 'answer_free': True})
        elif self.path == '/favicon.ico':
            self._send(204, b'', 'image/x-icon')
        else:
            self._json(404, {'error': 'not found'})

    def do_POST(self) -> None:
        if self.path != '/submit':
            self._json(404, {'error': 'not found'})
            return
        origin = self.headers.get('Origin')
        allowed_origins = {f'http://127.0.0.1:{self.server.server_port}',
                           f'http://localhost:{self.server.server_port}'}
        if origin is not None and origin not in allowed_origins:
            self._json(403, {'error': 'submission must come from this local page'})
            return
        try:
            size = int(self.headers.get('Content-Length', '-1'))
            if size < 0 or size > 128_000 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('invalid submission size or content type')
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError('submission must be an object')
            result = validate_submission(payload, [row['review_key'] for row in self.rows])
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json(400, {'error': str(error)})
            return
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        filename = f'human-review-submission-{timestamp}-{secrets.token_hex(3)}.jsonl'
        path = REVIEW_DIRECTORY / filename
        contents = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in result)
        try:
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as file:
                file.write(contents)
                file.flush()
                os.fsync(file.fileno())
        except OSError:
            self._json(500, {'error': 'could not save the local review'})
            return
        self._json(200, {'saved': True, 'count': len(result), 'filename': filename})

    def log_message(self, format: str, *args: object) -> None:
        # No document text or submitted judgments are logged.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    ReviewHandler.rows = load_packet()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), ReviewHandler)
    print(f'http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
