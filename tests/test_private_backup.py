"""Recover private SQLite WAL records and audio without touching an existing store."""
from pathlib import Path
from contextlib import closing
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import private_backup as backup


class PrivateBackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data'
        self.voice = hashlib.sha256(b'synthetic audio').hexdigest()[:32] + '.webm'
        (self.data / 'blobs' / '1').mkdir(parents=True)
        (self.data / 'blobs' / '1' / self.voice).write_bytes(b'synthetic audio')
        (self.data / '.dev-outbox').mkdir()
        (self.data / '.dev-outbox' / 'secret.json').write_text('synthetic token excluded')
        self.db = sqlite3.connect(self.data / 'dogcare.db')
        self.addCleanup(self.db.close)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE document (id INTEGER, content BLOB)')
        self.db.execute('INSERT INTO document VALUES (1, ?)', (b'synthetic document',))
        self.db.execute('CREATE TABLE observation (business_id INTEGER, voice_blob_ref TEXT, audio_json TEXT)')
        self.db.execute('INSERT INTO observation VALUES (1, ?, ?)',
                        (self.voice, json.dumps({'url': '/api/blobs/' + self.voice})))
        self.db.commit()
        self.backups = self.root / 'backups'

    def test_online_wal_and_audio_restore_without_outbox_or_live_store_mutation(self):
        self.assertTrue((self.data / 'dogcare.db-wal').is_file())
        snapshot = backup.backup(self.data, self.backups)
        self.assertEqual(set(backup.verify(snapshot)), {'dogcare.db', 'blobs/1/' + self.voice})
        # A later write must not leak into the snapshot.
        self.db.execute('INSERT INTO document VALUES (2, ?)', (b'later record',))
        self.db.commit()
        restored = backup.restore(snapshot, self.root / 'restored')
        with closing(sqlite3.connect(restored / 'dogcare.db')) as connection:
            self.assertEqual(connection.execute('SELECT * FROM document').fetchall(), [(1, b'synthetic document')])
        self.assertEqual((restored / 'blobs/1' / self.voice).read_bytes(), b'synthetic audio')
        self.assertFalse((restored / '.dev-outbox').exists())
        with self.assertRaises(FileExistsError):
            backup.restore(snapshot, self.data)
        self.assertEqual(self.db.execute('SELECT count(*) FROM document').fetchone()[0], 2)
        self.assertEqual((restored / 'dogcare.db').stat().st_mode & 0o777, 0o600)

    def test_corruption_and_symlinks_refused_before_creating_restore(self):
        snapshot = backup.backup(self.data, self.backups)
        (snapshot / 'blobs/1' / self.voice).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            backup.restore(snapshot, self.root / 'bad-restore')
        self.assertFalse((self.root / 'bad-restore').exists())
        (self.data / 'blobs' / '1' / self.voice).unlink()
        (self.data / 'blobs' / '1' / self.voice).symlink_to(self.root)
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

    def test_missing_referenced_audio_never_publishes_or_prunes_intact_snapshot(self):
        complete = backup.backup(self.data, self.backups, keep=1)
        (self.data / 'blobs' / '1' / self.voice).unlink()
        with self.assertRaisesRegex(ValueError, 'recording'):
            backup.backup(self.data, self.backups, keep=1)
        self.assertEqual([path.resolve() for path in self.backups.iterdir()], [complete])
        backup.verify(complete)

    def test_corrupt_source_audio_never_publishes_or_prunes_intact_snapshot(self):
        complete = backup.backup(self.data, self.backups, keep=1)
        (self.data / 'blobs' / '1' / self.voice).write_bytes(b'corrupted before backup')
        with self.assertRaisesRegex(ValueError, 'recording checksum'):
            backup.backup(self.data, self.backups, keep=1)
        self.assertEqual([path.resolve() for path in self.backups.iterdir()], [complete])
        restored = backup.restore(complete, self.root / 'restored-intact')
        self.assertEqual((restored / 'blobs/1' / self.voice).read_bytes(), b'synthetic audio')

    def test_fresh_manifest_cannot_hide_corrupt_recording(self):
        snapshot = backup.backup(self.data, self.backups)
        relative = 'blobs/1/' + self.voice
        (snapshot / relative).write_bytes(b'corrupted before manifest')
        manifest = json.loads((snapshot / 'manifest.json').read_text())
        manifest['files'][relative] = backup.digest(snapshot / relative)
        (snapshot / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'recording checksum'):
            backup.verify(snapshot)
        with self.assertRaises(ValueError):
            backup.restore(snapshot, self.root / 'corrupt-restore')
        self.assertFalse((self.root / 'corrupt-restore').exists())

    def test_manifest_cannot_hide_a_missing_database_recording(self):
        snapshot = backup.backup(self.data, self.backups)
        relative = 'blobs/1/' + self.voice
        (snapshot / relative).unlink()
        manifest = json.loads((snapshot / 'manifest.json').read_text())
        del manifest['files'][relative]
        (snapshot / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'recording'):
            backup.verify(snapshot)
        with self.assertRaises(ValueError):
            backup.restore(snapshot, self.root / 'incomplete-restore')
        self.assertFalse((self.root / 'incomplete-restore').exists())

    def test_upload_staging_and_unreferenced_recordings_are_not_copied(self):
        staged = self.data / 'blobs' / '1' / 'tmp-upload'
        staged.write_bytes(b'incomplete upload')
        (self.data / 'blobs' / '1' / ('b' * 32 + '.webm')).write_bytes(b'not in snapshot')
        original_copy = backup.shutil.copyfile

        def copy(source, destination):
            if Path(source).resolve() == staged.resolve():
                staged.unlink()
            return original_copy(source, destination)

        with patch.object(backup.shutil, 'copyfile', side_effect=copy):
            snapshot = backup.backup(self.data, self.backups)
        self.assertEqual(set(backup.verify(snapshot)), {'dogcare.db', 'blobs/1/' + self.voice})

    def test_audio_json_reference_is_checked_when_legacy_column_is_empty(self):
        self.db.execute('UPDATE observation SET voice_blob_ref=NULL')
        self.db.commit()
        (self.data / 'blobs' / '1' / self.voice).unlink()
        with self.assertRaisesRegex(ValueError, 'recording'):
            backup.backup(self.data, self.backups)

    def add_media(self, purpose='dog'):
        from tests.test_media_api import png_fixture
        self.db.executescript((backup.ROOT / 'api/schema.sql').read_text())
        self.db.execute("INSERT INTO business(id,name,slug,created) VALUES(1,'Synthetic','synthetic',0)")
        content, ident = png_fixture(), 'c' * 32
        self.db.execute('INSERT INTO media_asset(id,business_id,dog_id,client_id,purpose,mime,name,size,sha256,contents,created) VALUES(?,?,?,?,?,?,?,?,?,?,0)',
                        (ident, 1, 'nino' if purpose == 'dog' else None, 'one' if purpose == 'dog' else None,
                         purpose, 'image/png', 'synthetic.png', len(content), hashlib.sha256(content).hexdigest(), content))
        if purpose == 'dog':
            self.db.execute("INSERT INTO dog_cover VALUES(1,'nino',?)", (ident,))
        else:
            self.db.execute('INSERT INTO business_branding VALUES(1,?)',
                            (json.dumps({'hero': {'mediaId': ident, 'fit': 'contain', 'position': 50}, 'services': {}}),))
        self.db.commit()
        return ident, content

    def test_corrupt_media_bytes_never_publish_or_prune_good_backup(self):
        ident, content = self.add_media()
        complete = backup.backup(self.data, self.backups, keep=1)
        for damaged in (b'', b'x' * len(content)):
            with self.subTest(size=len(damaged)):
                self.db.execute('UPDATE media_asset SET contents=? WHERE id=?', (damaged, ident))
                self.db.commit()
                with self.assertRaisesRegex(ValueError, 'media (size|checksum) mismatch'):
                    backup.backup(self.data, self.backups, keep=1)
                self.assertEqual([path.resolve() for path in self.backups.iterdir()], [complete])
        result = subprocess.run([sys.executable, str(backup.ROOT / 'scripts/private_backup.py'), 'verify', str(complete)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_cover_media_prevents_backup_publication(self):
        ident, _ = self.add_media()
        complete = backup.backup(self.data, self.backups, keep=1)
        self.db.execute('DELETE FROM media_asset WHERE id=?', (ident,))
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'cover'):
            backup.backup(self.data, self.backups, keep=1)
        self.assertTrue(complete.exists())

    def test_missing_published_branding_prevents_backup_publication(self):
        ident, _ = self.add_media('branding')
        complete = backup.backup(self.data, self.backups, keep=1)
        self.db.execute('DELETE FROM media_asset WHERE id=?', (ident,))
        self.db.commit()
        with self.assertRaises(ValueError):
            backup.backup(self.data, self.backups, keep=1)
        self.assertTrue(complete.exists())
