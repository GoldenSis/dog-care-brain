#!/usr/bin/env python3
"""Decode synthetic phone media with the installed production converters."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'api'))
import media


def check(directory):
    for name in ('ffmpeg', 'ffprobe', 'heif-convert'):
        if not shutil.which(name):
            raise ValueError(f'Missing required media decoder: {name}')
    with tempfile.TemporaryDirectory(prefix='media-runtime-', dir=directory) as temporary:
        work = Path(temporary)
        heic = work / 'synthetic.heic'
        shutil.copyfile(ROOT / 'tests/fixtures/synthetic-phone.heic', heic)
        movie = work / 'synthetic.mov'
        shutil.copyfile(ROOT / 'tests/fixtures/synthetic-phone.mov', movie)
        for source, mime, expected in ((heic, 'image/heic', 'image/jpeg'), (movie, 'video/quicktime', 'video/mp4')):
            with source.open('r+b') as stream, media.normalize_upload(stream, mime, source.stat().st_size, source.name, work) as normalized:
                content, result_mime, size, name = normalized
                if result_mime != expected or size <= 0:
                    raise ValueError('Unexpected normalization result')
                media.validate_file(content, result_mime, size)
                print(f'PASS {source.suffix}: {result_mime}, {size} bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True, help='Existing private writable directory for self-cleaning synthetic files')
    args = parser.parse_args()
    try:
        check(args.directory)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Media runtime check failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
