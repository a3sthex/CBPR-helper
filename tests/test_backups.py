import importlib.util
import io
import json
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('backup_tools', ROOT / 'app/backup.py')
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


class CampaignBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / 'campaign.db'
        self.uploads = root / 'uploads'
        self.backups = root / 'backups'
        self.catalog = root / 'items.json'
        self.uploads.mkdir()
        self.catalog.write_text('{"version":1}', encoding='utf-8')
        self.conn = sqlite3.connect(self.db)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.executescript('''
          CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT);
          CREATE TABLE characters(id INTEGER PRIMARY KEY, owner_id INTEGER, data TEXT);
          CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT,applied REAL);
          INSERT INTO users VALUES(1,'operator');
          INSERT INTO characters VALUES(1,1,'{"handle":"V","notes":"private"}');
          INSERT INTO schema_migrations VALUES(1,'foundation',1);
        ''')
        self.conn.commit()
        (self.uploads / 'portrait.webp').write_bytes(b'RIFF-private-portrait')

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_online_bundle_contains_verified_database_uploads_and_manifest(self):
        result = backup.create_bundle(
            self.db, self.uploads, self.backups, self.catalog,
            retention=14, reason='unit test')
        path = Path(result['path'])
        self.assertTrue(path.is_file())
        self.assertRegex(path.name, backup.BUNDLE_NAME_RX)
        manifest = backup.read_manifest(path)
        self.assertEqual(manifest['format'], backup.BUNDLE_FORMAT)
        self.assertEqual(manifest['bundle_version'], 1)
        self.assertEqual(manifest['reason'], 'unit test')
        self.assertEqual(manifest['counts']['users'], 1)
        self.assertEqual(manifest['counts']['characters'], 1)
        self.assertEqual(manifest['database']['integrity_check'], 'ok')
        self.assertEqual([item['path'] for item in manifest['uploads']],
                         ['uploads/portrait.webp'])

        verified = backup.verify_bundle(path)
        self.assertTrue(verified['valid'])
        self.assertEqual(len(verified['sha256']), 64)
        listed = backup.list_bundles(self.backups)
        self.assertEqual(len(listed), 1)
        self.assertTrue(listed[0]['readable'])
        self.assertEqual(listed[0]['uploads'], 1)

        with tarfile.open(path, 'r:gz') as archive, tempfile.TemporaryDirectory() as directory:
            db_file = Path(directory) / 'restored.db'
            db_file.write_bytes(archive.extractfile('campaign.db').read())
            restored = sqlite3.connect(db_file)
            try:
                self.assertEqual(restored.execute('SELECT username FROM users').fetchone()[0],
                                 'operator')
                self.assertIn('private', restored.execute(
                    'SELECT data FROM characters').fetchone()[0])
            finally:
                restored.close()

    def test_retention_keeps_newest_bundles(self):
        created = [backup.create_bundle(
            self.db, self.uploads, self.backups, self.catalog,
            retention=2, reason=f'run-{index}') for index in range(3)]
        bundles = backup.list_bundles(self.backups)
        self.assertEqual(len(bundles), 2)
        self.assertFalse((self.backups / created[0]['name']).exists())
        self.assertTrue((self.backups / created[-1]['name']).exists())

    def test_verification_rejects_corruption_and_unsafe_members(self):
        result = backup.create_bundle(
            self.db, self.uploads, self.backups, self.catalog,
            retention=14, reason='corruption test')
        path = Path(result['path'])
        broken = self.backups / path.name.replace('.tar.gz', '-broken.tar.gz')
        broken.write_bytes(path.read_bytes()[:100])
        with self.assertRaises(backup.BackupError):
            backup.verify_bundle(broken)

        unsafe = self.backups / 'ncnet-backup-20260101T000000Z-deadbeef.tar.gz'
        manifest = json.dumps({
            'format': backup.BUNDLE_FORMAT, 'bundle_version': 1,
            'database': {}, 'uploads': [],
        }).encode()
        with tarfile.open(unsafe, 'w:gz') as archive:
            info = tarfile.TarInfo('manifest.json'); info.size = len(manifest)
            archive.addfile(info, io.BytesIO(manifest))
            payload = b'escape'
            info = tarfile.TarInfo('../outside'); info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        with self.assertRaises(backup.BackupError):
            backup.read_manifest(unsafe)

    def test_bundle_path_rejects_traversal_and_unknown_files(self):
        self.backups.mkdir()
        with self.assertRaises(backup.BackupError):
            backup.bundle_path(self.backups, '../../etc/passwd')
        with self.assertRaises(backup.BackupError):
            backup.bundle_path(self.backups, 'not-a-backup.tar.gz')


if __name__ == '__main__':
    unittest.main()
