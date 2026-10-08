"""Recover private SQLite WAL records and audio without touching an existing store."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts import private_backup as backup


class PrivateBackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data'
        (self.data / 'blobs' / '1').mkdir(parents=True)
        (self.data / 'blobs' / '1' / 'voice.webm').write_bytes(b'synthetic audio')
        (self.data / '.dev-outbox').mkdir()
        (self.data / '.dev-outbox' / 'secret.json').write_text('synthetic token excluded')
        self.db = sqlite3.connect(self.data / 'dogcare.db')
        self.addCleanup(self.db.close)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE document (id INTEGER, content BLOB)')
        self.db.execute('INSERT INTO document VALUES (1, ?)', (b'synthetic document',))
        self.db.commit()
        self.backups = self.root / 'backups'

    def test_online_wal_and_audio_restore_without_outbox_or_live_store_mutation(self):
        self.assertTrue((self.data / 'dogcare.db-wal').is_file())
        snapshot = backup.backup(self.data, self.backups)
        self.assertEqual(set(backup.verify(snapshot)), {'dogcare.db', 'blobs/1/voice.webm'})
        # A later write must not leak into the snapshot.
        self.db.execute('INSERT INTO document VALUES (2, ?)', (b'later record',))
        self.db.commit()
        restored = backup.restore(snapshot, self.root / 'restored')
        with sqlite3.connect(restored / 'dogcare.db') as connection:
            self.assertEqual(connection.execute('SELECT * FROM document').fetchall(), [(1, b'synthetic document')])
        self.assertEqual((restored / 'blobs/1/voice.webm').read_bytes(), b'synthetic audio')
        self.assertFalse((restored / '.dev-outbox').exists())
        with self.assertRaises(FileExistsError):
            backup.restore(snapshot, self.data)
        self.assertEqual(self.db.execute('SELECT count(*) FROM document').fetchone()[0], 2)
        self.assertEqual((restored / 'dogcare.db').stat().st_mode & 0o777, 0o600)

    def test_corruption_and_symlinks_refused_before_creating_restore(self):
        snapshot = backup.backup(self.data, self.backups)
        (snapshot / 'blobs/1/voice.webm').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            backup.restore(snapshot, self.root / 'bad-restore')
        self.assertFalse((self.root / 'bad-restore').exists())
        (self.data / 'blobs' / 'external').symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, 'symbolic'):
            backup.backup(self.data, self.backups)

    def test_retention_keeps_only_bounded_verified_snapshots_and_preserves_unknown(self):
        unknown = self.backups / 'dogcare-unrecognized'
        unknown.mkdir(parents=True)
        (unknown / 'operator-note').write_text('retain')
        first = backup.backup(self.data, self.backups, keep=2)
        second = backup.backup(self.data, self.backups, keep=2)
        third = backup.backup(self.data, self.backups, keep=2)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists() and third.exists() and unknown.exists())
        for destination in (self.data, self.data / 'blobs' / 'backups', self.root):
            with self.assertRaises(ValueError):
                backup.backup(self.data, destination)
        with self.assertRaises(ValueError):
            backup.restore(third, backup.ROOT / 'runtime')
