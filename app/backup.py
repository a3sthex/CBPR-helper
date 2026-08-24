#!/usr/bin/env python3
"""NC//NET online SQLite backups and portable campaign bundles.

Only Python's standard library is required. Bundles contain an online SQLite
snapshot, attached uploads, and a checksummed manifest. Restoring is deliberately
not automatic while the web service is running; verify a bundle first, stop cbpr,
and use a reviewed restore workflow.
"""
import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BASE = Path(__file__).resolve().parent
DEFAULT_DB = Path(os.environ.get('CBPR_DB_PATH') or BASE / 'data' / 'cbpr.db').expanduser().resolve()
DEFAULT_UPLOADS = Path(os.environ.get('CBPR_UPLOAD_DIR') or BASE / 'data' / 'uploads').expanduser().resolve()
DEFAULT_BACKUPS = Path(os.environ.get('CBPR_BACKUP_DIR') or BASE / 'data' / 'backups').expanduser().resolve()
DEFAULT_CATALOG = BASE / 'data' / 'items.json'
BUNDLE_FORMAT = 'ncnet-campaign-bundle'
BUNDLE_VERSION = 1
BUNDLE_NAME_RX = re.compile(r'^ncnet-backup-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}\.tar\.gz$')
MAX_VERIFY_BYTES = 2_000_000_000
COUNT_TABLES = (
    'users', 'characters', 'personas', 'storylines', 'contracts', 'contract_signups',
    'feed_posts', 'feed_comments', 'npc_templates', 'nc_sessions', 'media',
)


class BackupError(Exception):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_stream(handle):
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: handle.read(1024 * 1024), b''):
        size += len(chunk)
        if size > MAX_VERIFY_BYTES:
            raise BackupError('Bundle member exceeds verification size limit')
        digest.update(chunk)
    return digest.hexdigest(), size


def sqlite_integrity(path):
    conn = sqlite3.connect(str(path), timeout=20)
    try:
        rows = [row[0] for row in conn.execute('PRAGMA integrity_check').fetchall()]
        return rows
    finally:
        conn.close()


def database_metadata(path):
    conn = sqlite3.connect(str(path), timeout=20)
    conn.row_factory = sqlite3.Row
    try:
        tables = {row['name'] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        counts = {}
        for table in COUNT_TABLES:
            if table in tables:
                counts[table] = conn.execute(f'SELECT COUNT(*) n FROM {table}').fetchone()['n']
        migrations = []
        if 'schema_migrations' in tables:
            migrations = [dict(row) for row in conn.execute(
                'SELECT version,name,applied FROM schema_migrations ORDER BY version').fetchall()]
        return {'counts': counts, 'schema_migrations': migrations}
    finally:
        conn.close()


def online_sqlite_snapshot(source_path, destination_path):
    if not source_path.is_file():
        raise BackupError(f'Database not found: {source_path}')
    source = sqlite3.connect(str(source_path), timeout=20)
    target = sqlite3.connect(str(destination_path), timeout=20)
    try:
        source.execute('PRAGMA busy_timeout=15000')
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()
    integrity = sqlite_integrity(destination_path)
    if integrity != ['ok']:
        raise BackupError('SQLite integrity check failed: ' + '; '.join(integrity[:10]))


def iter_uploads(upload_dir):
    if not upload_dir.exists():
        return []
    rows = []
    for path in sorted(upload_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.is_symlink():
            continue
        rows.append({
            'path': f'uploads/{path.name}',
            'source': path,
            'size': path.stat().st_size,
            'sha256': sha256_file(path),
        })
    return rows


def add_file_to_tar(archive, source, arcname):
    info = archive.gettarinfo(str(source), arcname=arcname)
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    with open(source, 'rb') as handle:
        archive.addfile(info, handle)


def prune_backups(backup_dir, retention):
    retention = max(1, int(retention))

    def created_key(path):
        try:
            manifest = read_manifest(path)
            if manifest.get('created_at_ns') is not None:
                return int(manifest['created_at_ns'])
            if manifest.get('created_at') is not None:
                return int(float(manifest['created_at']) * 1_000_000_000)
        except (BackupError, OSError, TypeError, ValueError):
            pass
        return path.stat().st_mtime_ns

    bundles = sorted(
        (path for path in backup_dir.iterdir() if path.is_file() and BUNDLE_NAME_RX.fullmatch(path.name)),
        key=lambda path: (created_key(path), path.name),
        reverse=True,
    )
    removed = []
    for stale in bundles[retention:]:
        stale.unlink()
        removed.append(stale.name)
    return removed


def create_bundle(db_path=DEFAULT_DB, uploads_dir=DEFAULT_UPLOADS,
                  backup_dir=DEFAULT_BACKUPS, catalog_path=DEFAULT_CATALOG,
                  retention=14, reason='manual'):
    db_path = Path(db_path).expanduser().resolve()
    uploads_dir = Path(uploads_dir).expanduser().resolve()
    backup_dir = Path(backup_dir).expanduser().resolve()
    catalog_path = Path(catalog_path).expanduser().resolve() if catalog_path else None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    suffix = os.urandom(4).hex()
    filename = f'ncnet-backup-{stamp}-{suffix}.tar.gz'
    final_path = backup_dir / filename
    temp_archive = backup_dir / f'.{filename}.tmp'

    try:
        with tempfile.TemporaryDirectory(prefix='.ncnet-snapshot-', dir=str(backup_dir)) as directory:
            snapshot = Path(directory) / 'campaign.db'
            online_sqlite_snapshot(db_path, snapshot)
            uploads = iter_uploads(uploads_dir)
            metadata = database_metadata(snapshot)
            created_at_ns = time.time_ns()
            manifest = {
                'format': BUNDLE_FORMAT,
                'bundle_version': BUNDLE_VERSION,
                'created_at': created_at_ns / 1_000_000_000,
                'created_at_ns': created_at_ns,
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'reason': str(reason or 'manual')[:120],
                'database': {
                    'path': 'campaign.db',
                    'size': snapshot.stat().st_size,
                    'sha256': sha256_file(snapshot),
                    'integrity_check': 'ok',
                },
                'uploads': [
                    {'path': row['path'], 'size': row['size'], 'sha256': row['sha256']}
                    for row in uploads
                ],
                'catalog': {
                    'sha256': sha256_file(catalog_path) if catalog_path and catalog_path.is_file() else None,
                    'path': str(catalog_path.name) if catalog_path else None,
                },
                **metadata,
            }
            encoded_manifest = json.dumps(
                manifest, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8')
            with tarfile.open(temp_archive, 'w:gz') as archive:
                info = tarfile.TarInfo('manifest.json')
                info.size = len(encoded_manifest)
                info.mtime = int(time.time())
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(encoded_manifest))
                add_file_to_tar(archive, snapshot, 'campaign.db')
                for row in uploads:
                    add_file_to_tar(archive, row['source'], row['path'])
        os.replace(temp_archive, final_path)
        removed = prune_backups(backup_dir, retention)
        return {
            'name': filename,
            'path': str(final_path),
            'size': final_path.stat().st_size,
            'created_at': manifest['created_at'],
            'manifest': manifest,
            'removed': removed,
        }
    except Exception:
        try:
            temp_archive.unlink()
        except FileNotFoundError:
            pass
        raise


def safe_member(member):
    path = PurePosixPath(member.name)
    if member.islnk() or member.issym() or member.isdev():
        return False
    if path.is_absolute() or '..' in path.parts:
        return False
    return (member.name in ('manifest.json', 'campaign.db') or
            (len(path.parts) == 2 and path.parts[0] == 'uploads' and path.parts[1]))


def read_manifest(bundle_path):
    bundle_path = Path(bundle_path).expanduser().resolve()
    try:
        with tarfile.open(bundle_path, 'r:gz') as archive:
            members = archive.getmembers()
            if any(not safe_member(member) for member in members):
                raise BackupError('Bundle contains an unsafe or unsupported member')
            member = archive.getmember('manifest.json')
            handle = archive.extractfile(member)
            if not handle:
                raise BackupError('Bundle manifest is unreadable')
            manifest = json.load(handle)
    except (tarfile.TarError, EOFError, KeyError, OSError, json.JSONDecodeError) as error:
        raise BackupError(f'Cannot read backup bundle: {error}') from error
    if manifest.get('format') != BUNDLE_FORMAT or manifest.get('bundle_version') != BUNDLE_VERSION:
        raise BackupError('Unsupported campaign bundle format or version')
    return manifest


def verify_bundle(bundle_path):
    bundle_path = Path(bundle_path).expanduser().resolve()
    manifest = read_manifest(bundle_path)
    expected_uploads = {row['path']: row for row in manifest.get('uploads') or []}
    try:
        with tarfile.open(bundle_path, 'r:gz') as archive, tempfile.TemporaryDirectory() as directory:
            members = {member.name: member for member in archive.getmembers()}
            database_info = manifest.get('database') or {}
            database_member = members.get(database_info.get('path') or 'campaign.db')
            if not database_member or not database_member.isfile():
                raise BackupError('Database snapshot is missing')
            source = archive.extractfile(database_member)
            if not source:
                raise BackupError('Database snapshot is unreadable')
            database_path = Path(directory) / 'campaign.db'
            digest = hashlib.sha256()
            size = 0
            with open(database_path, 'wb') as destination:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    size += len(chunk)
                    if size > MAX_VERIFY_BYTES:
                        raise BackupError('Database snapshot exceeds verification size limit')
                    digest.update(chunk)
                    destination.write(chunk)
            if digest.hexdigest() != database_info.get('sha256') or size != database_info.get('size'):
                raise BackupError('Database checksum or size mismatch')
            integrity = sqlite_integrity(database_path)
            if integrity != ['ok']:
                raise BackupError('SQLite integrity check failed: ' + '; '.join(integrity[:10]))

            actual_upload_names = {name for name in members if name.startswith('uploads/')}
            if actual_upload_names != set(expected_uploads):
                raise BackupError('Upload list does not match manifest')
            for name, expected in expected_uploads.items():
                member = members[name]
                if not member.isfile():
                    raise BackupError(f'Upload is not a regular file: {name}')
                handle = archive.extractfile(member)
                if not handle:
                    raise BackupError(f'Upload is unreadable: {name}')
                upload_hash, upload_size = sha256_stream(handle)
                if upload_hash != expected.get('sha256') or upload_size != expected.get('size'):
                    raise BackupError(f'Upload checksum or size mismatch: {name}')
    except (tarfile.TarError, OSError, sqlite3.DatabaseError) as error:
        if isinstance(error, BackupError):
            raise
        raise BackupError(f'Backup verification failed: {error}') from error
    return {
        'valid': True,
        'name': bundle_path.name,
        'size': bundle_path.stat().st_size,
        'sha256': sha256_file(bundle_path),
        'manifest': manifest,
    }


def bundle_path(backup_dir, name):
    if not BUNDLE_NAME_RX.fullmatch(str(name or '')):
        raise BackupError('Invalid backup filename')
    backup_dir = Path(backup_dir).expanduser().resolve()
    path = (backup_dir / name).resolve()
    if path.parent != backup_dir or not path.is_file():
        raise BackupError('Backup bundle not found')
    return path


def list_bundles(backup_dir=DEFAULT_BACKUPS):
    backup_dir = Path(backup_dir).expanduser().resolve()
    if not backup_dir.exists():
        return []
    rows = []
    for path in sorted(backup_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file() or not BUNDLE_NAME_RX.fullmatch(path.name):
            continue
        try:
            manifest = read_manifest(path)
            rows.append({
                'name': path.name, 'size': path.stat().st_size,
                'created_at': manifest.get('created_at') or path.stat().st_mtime,
                'reason': manifest.get('reason') or '',
                'counts': manifest.get('counts') or {},
                'uploads': len(manifest.get('uploads') or []),
                'readable': True,
            })
        except BackupError as error:
            rows.append({
                'name': path.name, 'size': path.stat().st_size,
                'created_at': path.stat().st_mtime, 'readable': False,
                'error': str(error),
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description='NC//NET campaign backup utility')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--uploads', default=str(DEFAULT_UPLOADS))
    parser.add_argument('--backup-dir', default=str(DEFAULT_BACKUPS))
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--retention', type=int, default=int(os.environ.get('CBPR_BACKUP_RETENTION', '14')))
    create.add_argument('--reason', default='scheduled')
    sub.add_parser('list')
    verify = sub.add_parser('verify')
    verify.add_argument('name')
    args = parser.parse_args()
    try:
        if args.command == 'create':
            result = create_bundle(args.db, args.uploads, args.backup_dir,
                                   DEFAULT_CATALOG, args.retention, args.reason)
        elif args.command == 'list':
            result = {'backups': list_bundles(args.backup_dir)}
        else:
            result = verify_bundle(bundle_path(args.backup_dir, args.name))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (BackupError, OSError, sqlite3.DatabaseError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
