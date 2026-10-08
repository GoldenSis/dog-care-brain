#!/usr/bin/env python3
"""Back up SQLite and immutable audio; restore only into a NEW private directory.

Standard deployment layout only: DATA/dogcare.db and DATA/blobs. No credentials,
login outbox or application files are copied. Uses SQLite's online backup API.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'api'))
import media


def private_path(value):
    path = Path(value).expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('runtime storage must be outside the application root')
    return path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(root):
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('symbolic links are not supported in private backups')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path
        elif not path.is_dir():
            raise ValueError('unsupported private backup entry')
    return result


def integrity(database):
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)) as connection:
        if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('database integrity check failed')
        media.verify_database(connection)


def recording_paths(database):
    paths = set()
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='observation'").fetchone():
            return paths
        for business_id, reference, audio_json in connection.execute(
                'SELECT business_id, voice_blob_ref, audio_json FROM observation'):
            references = {reference} if reference else set()
            if audio_json:
                try:
                    audio = json.loads(audio_json)
                except (TypeError, ValueError):
                    raise ValueError('invalid recording metadata') from None
                url = audio.get('url') if isinstance(audio, dict) else None
                if isinstance(url, str) and url.startswith('/api/blobs/'):
                    references.add(url[len('/api/blobs/'):])
            for reference in references:
                if (not isinstance(business_id, int) or business_id < 1 or
                        not isinstance(reference, str) or
                        not re.fullmatch(r'[a-f0-9]{32}\.(webm|ogg|m4a|wav|mp3)', reference)):
                    raise ValueError('invalid recording reference')
                paths.add(f'blobs/{business_id}/{reference}')
    return paths


def recording_source(root, relative):
    path = root / relative
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root and root in parent.parents):
        raise ValueError('symbolic links are not supported in private backups')
    if not path.is_file():
        raise ValueError('referenced recording is missing')
    return path


def verify(snapshot):
    snapshot = private_path(snapshot)
    actual = files(snapshot)
    if 'manifest.json' not in actual:
        raise ValueError('backup manifest missing')
    manifest = json.loads(actual.pop('manifest.json').read_text())
    expected = manifest.get('files', {})
    if manifest.get('version') != 1 or set(actual) != set(expected) or 'dogcare.db' not in actual:
        raise ValueError('backup inventory mismatch')
    if any(name != 'dogcare.db' and not name.startswith('blobs/') for name in actual):
        raise ValueError('unexpected backup content')
    checksums = {name: digest(path) for name, path in actual.items()}
    if checksums != expected:
        raise ValueError('backup checksum mismatch')
    integrity(actual['dogcare.db'])
    recordings = recording_paths(actual['dogcare.db'])
    if not recordings.issubset(actual):
        raise ValueError('referenced recording is missing from backup')
    if any(not checksums[name].startswith(Path(name).stem) for name in recordings):
        raise ValueError('recording checksum mismatch')
    return actual


def backup(data, destination, keep=14):
    data, destination = private_path(data), private_path(destination)
    if keep < 1:
        raise ValueError('keep must be positive')
    database, blobs = data / 'dogcare.db', data / 'blobs'
    if not database.is_file() or database.is_symlink() or blobs.is_symlink():
        raise ValueError('standard private database/audio layout required')
    if destination == blobs or blobs in destination.parents or destination == data or destination in data.parents:
        raise ValueError('backup destination must not overlap source files')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = 'dogcare-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ-') + uuid.uuid4().hex[:8]
    staging = Path(tempfile.mkdtemp(prefix='.backup-', dir=destination))
    try:
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(staging / 'dogcare.db')) as target:
                source.backup(target)
        for relative in recording_paths(staging / 'dogcare.db'):
            source = recording_source(data, relative)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(source, target)
        inventory = files(staging)
        for path in inventory.values():
            path.chmod(0o600)
        manifest = {'version': 1, 'created': datetime.now(timezone.utc).isoformat(),
                    'files': {name: digest(path) for name, path in inventory.items()}}
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (staging / 'manifest.json').chmod(0o600)
        verify(staging)
        result = destination / name
        staging.rename(result)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    # Prune only this helper's verified complete snapshots. Unknown/corrupt
    # directories are retained for operator inspection, never silently deleted.
    completed = []
    for candidate in sorted(destination.glob('dogcare-*')):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        try:
            verify(candidate)
        except (ValueError, OSError, sqlite3.Error):
            continue
        completed.append(candidate)
    for candidate in completed[:-keep]:
        shutil.rmtree(candidate)
    return result


def restore(snapshot, destination):
    snapshot, destination = private_path(snapshot), private_path(destination)
    inventory = verify(snapshot)
    # mkdir without exist_ok is deliberate: never replace a live store or WAL.
    destination.mkdir(mode=0o700)
    try:
        for name, source in inventory.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(source, target)
            target.chmod(0o600)
            if digest(target) != digest(source):
                raise ValueError('restore checksum mismatch')
        (destination / 'blobs').mkdir(mode=0o700, exist_ok=True)
        integrity(destination / 'dogcare.db')
    except Exception:
        shutil.rmtree(destination)
        raise
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    save = commands.add_parser('backup')
    save.add_argument('--data-dir', required=True)
    save.add_argument('--backup-dir', required=True)
    save.add_argument('--keep', type=int, default=14)
    check = commands.add_parser('verify')
    check.add_argument('snapshot')
    recover = commands.add_parser('restore')
    recover.add_argument('snapshot')
    recover.add_argument('--into', required=True, help='new, nonexistent private directory')
    args = parser.parse_args()
    try:
        if args.command == 'backup':
            print(backup(args.data_dir, args.backup_dir, args.keep))
        elif args.command == 'restore':
            print(restore(args.snapshot, args.into))
        else:
            verify(args.snapshot)
            print('Backup verified')
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f'Backup operation refused: {error}\n')


if __name__ == '__main__':
    main()
