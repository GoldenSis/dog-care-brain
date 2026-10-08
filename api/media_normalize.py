"""Bounded local normalization of phone photos and clips."""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

PHOTO_TYPES = {'image/heic', 'image/heif'}
VIDEO_TYPES = {'video/quicktime', 'video/mp4', 'video/webm'}
SECONDS_LIMIT = 60
TIMEOUT = 120
TEMP_LIMIT = 200 * 1024 * 1024
_SLOTS = threading.BoundedSemaphore(1)
INVALID = 'Conversion impossible : fichier incomplet ou format non pris en charge.'
FF_INPUT = ['-protocol_whitelist', 'file', '-enable_drefs', '0', '-use_absolute_path', '0', '-f', 'mov']
WEBM_INPUT = ['-protocol_whitelist', 'file', '-f', 'matroska']


def tool(name):
    found = shutil.which(name)
    if not found:
        label = 'HEIC/HEIF' if name == 'heif-convert' else 'vidéo/photo'
        raise ValueError(f'Conversion {label} indisponible sur le serveur. Réessayez après activation du décodeur.')
    return found


def run(arguments, directory, deadline):
    output = directory / 'process-output'
    def budget():
        files = list(directory.iterdir())
        if (time.monotonic() >= deadline or len(files) > 8 or
                sum(p.stat().st_size for p in files) > TEMP_LIMIT or output.stat().st_size > 256 * 1024):
            raise ValueError('Conversion trop longue ou trop volumineuse. Choisissez un fichier plus court ou plus petit.')
    with output.open('w+b') as stdout:
        with subprocess.Popen([sys.executable, '-I', str(Path(__file__).with_name('media_process.py')), *arguments],
                              cwd=directory, stdin=subprocess.DEVNULL, stdout=stdout, stderr=subprocess.DEVNULL,
                              env={'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C', 'TMPDIR': str(directory)},
                              start_new_session=True) as process:
            try:
                while process.poll() is None:
                    budget()
                    time.sleep(0.04)
                budget()
                if process.returncode:
                    raise ValueError(INVALID)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        if output.stat().st_size > 256 * 1024:
            raise ValueError(INVALID)
        stdout.seek(0)
        return stdout.read()


def probe(path, directory, deadline, webm=False):
    args = [tool('ffprobe'), '-v', 'error', '-threads', '2']
    args += WEBM_INPUT if webm else FF_INPUT
    args += ['-show_entries', 'stream=codec_type,codec_name,width,height,pix_fmt,duration:format=duration', '-of', 'json', str(path)]
    try:
        return json.loads(run(args, directory, deadline))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError(INVALID) from None


def video_info(value, normalized=False, webm=False):
    videos = [s for s in value.get('streams', []) if s.get('codec_type') == 'video']
    audio = [s for s in value.get('streams', []) if s.get('codec_type') == 'audio']
    codecs = ('vp8', 'vp9') if webm else ('h264',) if normalized else ('h264', 'hevc')
    if len(videos) != 1 or videos[0].get('codec_name') not in codecs:
        raise ValueError('Choisissez une vidéo MP4/MOV H.264 ou HEVC.')
    video = videos[0]
    if (not 0 < video.get('width', 0) <= 4096 or not 0 < video.get('height', 0) <= 4096 or
            video['width'] * video['height'] > 4096 * 2160):
        raise ValueError('Vidéo trop grande : 4K maximum avant conversion.')
    try:
        durations = [s['duration'] for s in [*videos, *audio, value.get('format', {})] if s.get('duration') not in (None, 'N/A')]
        duration = max(map(float, durations), default=None)
    except (TypeError, ValueError):
        raise ValueError('Durée vidéo illisible.') from None
    if not (webm and duration is None) and (duration is None or not math.isfinite(duration) or not 0 < duration <= SECONDS_LIMIT + 0.05):
        raise ValueError('Vidéo trop longue ou durée illisible : 60 secondes maximum.')
    if normalized and (video.get('pix_fmt') != 'yuv420p' or any(s.get('codec_name') != 'aac' for s in audio)):
        raise ValueError(INVALID)


def heif_header(stream, size):
    stream.seek(0)
    header = stream.read(min(size, 4096))
    if len(header) < 16 or header[4:8] != b'ftyp':
        raise ValueError(INVALID)
    length = int.from_bytes(header[:4], 'big')
    if not 16 <= length <= len(header) or length % 4:
        raise ValueError(INVALID)
    brands = {header[8:12], *[header[n:n + 4] for n in range(16, length, 4)]}
    if not brands.intersection({b'heic', b'heix', b'hevc', b'hevx'}):
        raise ValueError('Choisissez une photo HEIC/HEIF contenant une image HEVC.')


@contextmanager
def normalize(stream, mime, size, name, directory):
    import media
    media.validate_name(name)
    if not _SLOTS.acquire(blocking=False):
        raise ValueError('Une conversion est déjà en cours. Réessayez dans un instant.')
    try:
        if mime not in PHOTO_TYPES | VIDEO_TYPES:
            media.validate_file(stream, mime, size)
            yield stream, mime, size, name
            return
        if size > (media.IMAGE_LIMIT if mime in PHOTO_TYPES else media.VIDEO_LIMIT):
            raise ValueError('Fichier trop volumineux : photo 12 Mio, vidéo 80 Mio maximum.')
        if mime in PHOTO_TYPES:
            heif_header(stream, size)
        elif mime == 'video/webm':
            media.validate_file(stream, mime, size)
        else:
            stream.seek(0)
            if stream.read(8)[4:8] != b'ftyp':
                raise ValueError(INVALID)
        with tempfile.TemporaryDirectory(prefix='media-convert-', dir=directory) as temporary:
            work = Path(temporary)
            deadline = time.monotonic() + TIMEOUT
            source = work / ('input.heic' if mime in PHOTO_TYPES else 'input.webm' if mime == 'video/webm' else 'input.mov')
            stream.seek(0)
            with source.open('wb') as target:
                shutil.copyfileobj(stream, target, 64 * 1024)
            photo_decoder = tool('heif-convert') if mime in PHOTO_TYPES else None
            ffmpeg = tool('ffmpeg')
            base = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-xerror', '-threads', '2', '-filter_threads', '2']
            if mime in PHOTO_TYPES:
                decoded = work / 'decoded.jpg'
                run([photo_decoder, '--quiet', '--strict', '-q', '95', str(source), str(decoded)], work, deadline)
                if not decoded.is_file():
                    raise ValueError('Choisissez une seule photo HEIC, sans séquence d’images.')
                with decoded.open('r+b') as check:
                    media.validate_file(check, 'image/jpeg', decoded.stat().st_size)
                result = work / 'result.jpg'
                run(base + ['-protocol_whitelist', 'file', '-f', 'image2', '-pattern_type', 'none', '-noautorotate',
                            '-i', str(decoded), '-map', '0:v:0', '-map_metadata', '-1', '-frames:v', '1',
                            '-c:v', 'mjpeg', '-threads', '2', '-q:v', '2', '-update', '1', str(result)], work, deadline)
                out_mime = 'image/jpeg'
            elif mime == 'video/webm':
                video_info(probe(source, work, deadline, webm=True), webm=True)
                result, out_mime = source, mime
            else:
                video_info(probe(source, work, deadline))
                result = work / 'result.mp4'
                run(base + FF_INPUT + ['-err_detect', 'explode', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
                            '-map_metadata', '-1', '-map_chapters', '-1', '-t', str(SECONDS_LIMIT + 1),
                            '-vf', "scale=w='min(1920,iw)':h='min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
                            '-r', '30', '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-b:a', '128k', '-ac', '2', '-movflags', '+faststart', str(result)], work, deadline)
                video_info(probe(result, work, deadline), normalized=True)
                out_mime = 'video/mp4'
            out_size = result.stat().st_size
            with result.open('r+b') as normalized:
                media.validate_file(normalized, out_mime, out_size)
                input_options = WEBM_INPUT if out_mime == 'video/webm' else FF_INPUT if out_mime == 'video/mp4' else ['-protocol_whitelist', 'file', '-f', 'image2', '-pattern_type', 'none']
                progress = run(base + input_options + ['-err_detect', 'explode', '-i', str(result), '-map', '0:v:0', '-map', '0:a:0?',
                               '-t', str(SECONDS_LIMIT + 1), '-progress', 'pipe:1', '-f', 'null', '-'], work, deadline)
                if out_mime.startswith('video/'):
                    durations = [int(line.partition(b'=')[2]) / 1_000_000 for line in progress.splitlines() if line.startswith(b'out_time_us=') and line.partition(b'=')[2] != b'N/A']
                    if not durations or not 0 < max(durations) <= SECONDS_LIMIT + 0.05:
                        raise ValueError('Vidéo trop longue ou durée illisible : 60 secondes maximum.')
                stem = Path(name).stem[:170] or 'media'
                yield normalized, out_mime, out_size, name if mime == 'video/webm' else stem + result.suffix
    finally:
        _SLOTS.release()
