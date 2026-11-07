"""Durable one-use approval of exact sandbox actions; never rerun a model."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid


class ReviewConflict(ValueError):
    pass


class ReviewStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        os.chmod(self.path, 0o600)
        with sqlite3.connect(self.path) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS reviews '
                               '(id TEXT PRIMARY KEY, owner TEXT NOT NULL, snapshot TEXT NOT NULL, '
                               'snapshot_hash TEXT NOT NULL, digest TEXT NOT NULL, expires REAL NOT NULL, '
                               'status TEXT NOT NULL, result TEXT)')

    def create(self, snapshot, *, owner, ttl_seconds=900, now=None):
        if not isinstance(owner, str) or not owner or not 1 <= ttl_seconds <= 86400:
            raise ValueError('invalid review owner or lifetime')
        review_id = uuid.uuid4().hex
        raw = json.dumps(snapshot, sort_keys=True, separators=(',', ':'))
        digest = snapshot['action_digest']
        expires = (time.time() if now is None else now) + ttl_seconds
        with sqlite3.connect(self.path) as connection:
            connection.execute('INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                               (review_id, owner, raw, hashlib.sha256(raw.encode()).hexdigest(), digest, expires, 'pending', None))
        return {'review_id': review_id, 'action_digest': digest, 'expires_at': expires,
                'recipient': snapshot['intent']['recipient'], 'subject': snapshot['intent']['subject'],
                'body': snapshot['artifact']['body']}

    def resolve(self, review_id, *, owner, action_digest, approve, now=None):
        if type(approve) is not bool:
            raise ValueError('approval must be a boolean')
        from smaip.agents.task_progression import execute_checkpoint
        with sqlite3.connect(self.path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT snapshot,snapshot_hash,digest,expires,status FROM reviews '
                                     'WHERE id=? AND owner=?', (review_id, owner)).fetchone()
            if row is None:
                raise LookupError('review not found')
            raw, expected, digest, expires, status = row
            if status != 'pending':
                raise ReviewConflict('review already resolved')
            if (time.time() if now is None else now) >= expires:
                connection.execute('UPDATE reviews SET status=? WHERE id=?', ('expired', review_id))
                connection.commit()
                raise ReviewConflict('review expired')
            if not isinstance(action_digest, str) or not hmac.compare_digest(digest, action_digest):
                raise ReviewConflict('action digest differs')
            if not hmac.compare_digest(hashlib.sha256(raw.encode()).hexdigest(), expected):
                raise ReviewConflict('stored checkpoint differs')
            snapshot = json.loads(raw)
            if approve:
                result = execute_checkpoint(snapshot)
                result['events'].append({'type': 'review_approved', 'review_id': review_id, 'action_digest': digest})
                status = 'approved'
            else:
                result = snapshot['report']
                result.update(status='declined', pending_action=None)
                result['events'].append({'type': 'review_declined', 'review_id': review_id})
                status = 'declined'
            connection.execute('UPDATE reviews SET status=?,result=? WHERE id=?',
                               (status, json.dumps(result), review_id))
            return result
