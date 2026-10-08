"""Private binary albums and explicitly published business artwork."""
import hashlib
import json
import mmap
import re
import secrets
import struct
import time
import zlib

import daily
import portal
import professional
from media_normalize import normalize as normalize_upload

IMAGE_LIMIT = 12 * 1024 * 1024
VIDEO_LIMIT = 80 * 1024 * 1024
BUSINESS_LIMIT = 2 * 1024 * 1024 * 1024
ITEM_LIMIT = 1000
PIXEL_LIMIT = 40_000_000
FACES = ('terrier', 'dalmatian', 'pug')
TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'video/mp4', 'video/quicktime', 'video/webm'}
ID = re.compile(r'[a-f0-9]{32}')
META = 'rowid,id,business_id,dog_id,client_id,purpose,mime,name,size,sha256,created'
INVALID = 'Fichier incomplet ou format non pris en charge. Choisissez JPEG, PNG, WebP, HEIC/HEIF, MP4/MOV H.264 ou HEVC, ou WebM VP8/VP9.'


def dimensions(width, height):
    if not width or not height or width * height > PIXEL_LIMIT:
        raise ValueError('Image trop grande : 40 millions de pixels maximum.')


def png(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(INVALID)
    offset, compressed, header, ended = 8, bytearray(), None, False
    while offset + 12 <= len(data):
        size = int.from_bytes(data[offset:offset + 4], 'big')
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(data) or zlib.crc32(data[offset + 4:end - 4]) != int.from_bytes(data[end - 4:end], 'big'):
            raise ValueError(INVALID)
        value = data[offset + 8:end - 4]
        if kind == b'IHDR':
            if offset != 8 or size != 13:
                raise ValueError(INVALID)
            width, height, bits, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', value)
            dimensions(width, height)
            if bits != 8 or color not in (0, 2, 3, 4, 6) or compression or filtering or interlace:
                raise ValueError('PNG non pris en charge : utilisez un PNG 8 bits non entrelacé ou JPEG.')
            header = (width, height, {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color])
        elif kind == b'IDAT':
            compressed.extend(value)
        elif kind == b'IEND':
            ended = size == 0 and end == len(data)
            break
        offset = end
    if not header or not ended or not compressed:
        raise ValueError(INVALID)
    width, height, channels = header
    expected = (width * channels + 1) * height
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data or any(raw[n] > 4 for n in range(0, expected, width * channels + 1)):
        raise ValueError(INVALID)


def jpeg(data):
    if data[:2] != b'\xff\xd8' or data[-2:] != b'\xff\xd9':
        raise ValueError(INVALID)
    pos, sized, scanned, quantized, huffman = 2, False, False, False, False
    while pos < len(data) - 2:
        if data[pos] != 255:
            raise ValueError(INVALID)
        while pos < len(data) and data[pos] == 255:
            pos += 1
        marker = data[pos]
        pos += 1
        size = int.from_bytes(data[pos:pos + 2], 'big')
        if size < 2 or pos + size > len(data) - 2:
            raise ValueError(INVALID)
        if marker in (0xc0, 0xc1, 0xc2):
            if size < 8 or data[pos + 2] != 8 or data[pos + 7] not in (1, 3, 4) or size != 8 + 3 * data[pos + 7]:
                raise ValueError(INVALID)
            dimensions(int.from_bytes(data[pos + 5:pos + 7], 'big'), int.from_bytes(data[pos + 3:pos + 5], 'big'))
            sized = True
        if marker == 0xdb:
            quantized = size >= 67
        if marker == 0xc4:
            huffman = size >= 20
        if marker == 0xda and (size < 8 or not 1 <= data[pos + 2] <= 4 or size != 6 + 2 * data[pos + 2]):
            raise ValueError(INVALID)
        pos += size
        if marker == 0xda:
            scanned = pos < len(data) - 3
            break
    if not sized or not scanned or not quantized or not huffman:
        raise ValueError(INVALID)


def webp(data):
    if data[:4] != b'RIFF' or data[8:12] != b'WEBP' or int.from_bytes(data[4:8], 'little') + 8 != len(data):
        raise ValueError(INVALID)
    offset, sized = 12, False
    while offset + 8 <= len(data):
        kind = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], 'little')
        start, end = offset + 8, offset + 8 + size
        if end > len(data):
            raise ValueError(INVALID)
        if kind == b'VP8 ' and size >= 10 and data[start + 3:start + 6] == b'\x9d\x01\x2a':
            tag = int.from_bytes(data[start:start + 3], 'little')
            if tag & 1 or not tag & 16 or not 0 < tag >> 5 < size - 10:
                raise ValueError(INVALID)
            dimensions(int.from_bytes(data[start + 6:start + 8], 'little') & 0x3fff, int.from_bytes(data[start + 8:start + 10], 'little') & 0x3fff)
            sized = True
        if kind == b'VP8L' and size > 5 and data[start] == 0x2f:
            bits = int.from_bytes(data[start + 1:start + 5], 'little')
            if bits >> 29:
                raise ValueError(INVALID)
            dimensions((bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1)
            sized = True
        offset = end + size % 2
    if offset != len(data) or not sized:
        raise ValueError(INVALID)


def boxes(data, start, end):
    count = 0
    while start < end:
        if start + 8 > end or count > 10000:
            raise ValueError(INVALID)
        size, kind = struct.unpack('>I4s', data[start:start + 8])
        head = 8
        if size == 1:
            if start + 16 > end:
                raise ValueError(INVALID)
            size, head = int.from_bytes(data[start + 8:start + 16], 'big'), 16
        if size == 0:
            size = end - start
        if size < head or start + size > end:
            raise ValueError(INVALID)
        yield kind, start + head, start + size
        start += size
        count += 1


def mp4(data):
    top = list(boxes(data, 0, len(data)))
    if not top or top[0][0] != b'ftyp' or not any(k == b'mdat' and e > s for k, s, e in top):
        raise ValueError(INVALID)
    found = False
    def walk(start, end, depth=0):
        nonlocal found
        if depth > 8:
            raise ValueError(INVALID)
        for kind, first, last in boxes(data, start, end):
            if kind in (b'moov', b'trak', b'mdia', b'minf', b'stbl'):
                walk(first, last, depth + 1)
            elif kind == b'stsd':
                if last - first < 8:
                    raise ValueError(INVALID)
                entries = list(boxes(data, first + 8, last))
                if len(entries) != int.from_bytes(data[first + 4:first + 8], 'big'):
                    raise ValueError(INVALID)
                for codec, sample, stop in entries:
                    if codec in (b'hvc1', b'hev1', b'av01'):
                        raise ValueError(INVALID)
                    if codec in (b'avc1', b'avc3'):
                        if stop - sample < 78:
                            raise ValueError(INVALID)
                        dimensions(*struct.unpack('>HH', data[sample + 24:sample + 28]))
                        found = any(k == b'avcC' and e - s >= 7 for k, s, e in boxes(data, sample + 78, stop))
    walk(0, len(data))
    if not found:
        raise ValueError(INVALID)


def vint(data, pos, ident=False):
    if pos >= len(data) or not data[pos]:
        raise ValueError(INVALID)
    width = 1
    while not data[pos] & (1 << (8 - width)):
        width += 1
    if width > (4 if ident else 8) or pos + width > len(data):
        raise ValueError(INVALID)
    value = int.from_bytes(data[pos:pos + width], 'big')
    if not ident:
        value &= (1 << (7 * width)) - 1
        if value == (1 << (7 * width)) - 1:
            value = None
    return value, pos + width


def webm(data):
    if data[:4] != b'\x1a\x45\xdf\xa3':
        raise ValueError(INVALID)
    codecs, video, cluster, doc = [], False, False, False
    def walk(start, end, depth=0):
        nonlocal video, cluster, doc
        count = 0
        while start < end:
            count += 1
            if depth > 8 or count > 100000:
                raise ValueError(INVALID)
            kind, pos = vint(data, start, True)
            size, pos = vint(data, pos)
            if size is None and kind not in (0x18538067, 0x1f43b675):
                raise ValueError(INVALID)
            stop = end if size is None else pos + size
            if stop > end:
                raise ValueError(INVALID)
            if kind in (0x1a45dfa3, 0x18538067, 0x1654ae6b, 0xae, 0xe0):
                walk(pos, stop, depth + 1)
            elif kind == 0x4282:
                doc = data[pos:stop] == b'webm'
            elif kind == 0x86:
                codecs.append(data[pos:stop])
            elif kind == 0x83 and data[pos:stop] == b'\x01':
                video = True
            elif kind == 0x1f43b675:
                cluster = stop > pos
            start = stop
    walk(0, len(data))
    if not doc or not video or not cluster or not any(x in (b'V_VP8', b'V_VP9') for x in codecs) or any(x.startswith(b'V_') and x not in (b'V_VP8', b'V_VP9') for x in codecs):
        raise ValueError(INVALID)


def validate_file(stream, mime, size):
    if mime not in TYPES - {'image/heic', 'image/heif'} or not size:
        raise ValueError(INVALID)
    if size > (IMAGE_LIMIT if mime.startswith('image/') else VIDEO_LIMIT):
        raise ValueError('Fichier trop volumineux : photo 12 Mio, vidéo 80 Mio maximum.')
    stream.flush()
    with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        try:
            {'image/png': png, 'image/jpeg': jpeg, 'image/webp': webp,
             'video/mp4': mp4, 'video/quicktime': mp4, 'video/webm': webm}[mime](data)
        except (IndexError, struct.error, zlib.error):
            raise ValueError(INVALID) from None


def upload_scope(c, user, dog_id, purpose):
    if purpose == 'branding':
        if user['role'] != 'owner' or dog_id:
            raise PermissionError('Accès réservé à la propriétaire.')
        return None
    if purpose != 'dog' or user['role'] not in ('owner', 'client'):
        raise PermissionError('Accès à cet album refusé.')
    dogs = daily.load(c, user['business_id'])['dogs']
    dog = next((d for d in dogs if d['id'] == dog_id), None)
    if not dog and user['role'] == 'owner' and isinstance(dog_id, str):
        legacy = c.execute('SELECT 1 FROM dog WHERE business_id=? AND slug=?', (user['business_id'], dog_id)).fetchone()
        if legacy:
            return None
    if not dog or (user['role'] == 'client' and (not dog['clientId'] or dog['clientId'] != portal.client_id(c, user))):
        raise PermissionError('Accès à cet album refusé.')
    return dog['clientId']


def permitted(c, user, row):
    if not row or row['business_id'] != user['business_id']:
        return False
    if user['role'] == 'owner':
        return True
    if user['role'] == 'professional':
        return row['purpose'] == 'dog' and professional.permits(c, user, 'media', row['id'])
    return (user['role'] == 'client' and row['purpose'] == 'dog' and row['client_id'] is not None and
            row['client_id'] == portal.client_id(c, user) and row['dog_id'] in portal.allowed_dogs(c, user))


def asset(c, user, ident):
    if not isinstance(ident, str) or not ID.fullmatch(ident):
        return None
    row = c.execute('SELECT ' + META + ' FROM media_asset WHERE id=? AND business_id=?', (ident, user['business_id'])).fetchone()
    return row if permitted(c, user, row) else None


def branding(c, bid):
    row = c.execute('SELECT snapshot FROM business_branding WHERE business_id=?', (bid,)).fetchone()
    return json.loads(row[0]) if row else {'hero': None, 'services': {}}


def snapshot(c, user):
    cid = portal.client_id(c, user) if user['role'] == 'client' else None
    dogs = portal.allowed_dogs(c, user) if cid is not None else set()
    shared = {r['key'] for r in professional.records(c, user)} if user['role'] == 'professional' else set()
    rows = [r for r in c.execute('SELECT ' + META + ' FROM media_asset WHERE business_id=? ORDER BY created,rowid', (user['business_id'],))
            if user['role'] == 'owner' or (cid is not None and r['purpose'] == 'dog' and r['client_id'] == cid and r['dog_id'] in dogs) or
            (user['role'] == 'professional' and r['purpose'] == 'dog' and 'media:' + r['id'] in shared)]
    visible = {r['id'] for r in rows}
    items = [{'id': r['id'], 'dogId': r['dog_id'], 'purpose': r['purpose'], 'mime': r['mime'], 'name': r['name'],
              'size': r['size'], 'url': '/api/media/content/' + r['id']} for r in rows]
    covers = {r['dog_id']: r['media_id'] for r in c.execute('SELECT dog_id,media_id FROM dog_cover WHERE business_id=?', (user['business_id'],)) if r['media_id'] in visible}
    return {'items': items, 'covers': covers, 'branding': branding(c, user['business_id']) if user['role'] == 'owner' else {'hero': None, 'services': {}}}


def validate_name(name):
    if not isinstance(name, str) or not name.strip() or len(name) > 180 or any(ord(ch) < 32 or ord(ch) == 127 or 0xd800 <= ord(ch) <= 0xdfff for ch in name):
        raise ValueError('Nom de fichier invalide.')


def store(c, user, stream, mime, size, name, dog_id, purpose):
    cid = upload_scope(c, user, dog_id, purpose)
    if purpose == 'branding' and not mime.startswith('image/'):
        raise ValueError('Choisissez une photo pour la page d’accueil ou les services.')
    total, count = c.execute('SELECT coalesce(sum(size),0),count(*) FROM media_asset WHERE business_id=?', (user['business_id'],)).fetchone()
    if total + size > BUSINESS_LIMIT or count >= ITEM_LIMIT:
        raise ValueError('Espace médias plein : 2 Gio ou 1 000 fichiers maximum. Retirez des fichiers avant de réessayer.')
    validate_name(name)
    ident = secrets.token_hex(16)
    stream.seek(0)
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    cursor = c.execute('INSERT INTO media_asset(id,business_id,dog_id,client_id,purpose,mime,name,size,sha256,contents,created) VALUES(?,?,?,?,?,?,?,?,?,zeroblob(?),?)',
                       (ident, user['business_id'], dog_id or None, cid, purpose, mime, name, size, digest, size, int(time.time())))
    stream.seek(0)
    with c.blobopen('media_asset', 'contents', cursor.lastrowid) as target:
        while chunk := stream.read(64 * 1024):
            target.write(chunk)
    c.execute('UPDATE business SET imported=1 WHERE id=?', (user['business_id'],))
    return ident


def valid_branding(c, bid, value):
    daily.fields(value, 'hero services')
    def image(ident):
        if not isinstance(ident, str):
            raise ValueError('Photo introuvable.')
        row = c.execute("SELECT id FROM media_asset WHERE id=? AND business_id=? AND purpose='branding' AND mime LIKE 'image/%'", (ident, bid)).fetchone()
        if not row:
            raise ValueError('Choisissez une photo ajoutée pour la page publique.')
    if value['hero'] is not None:
        hero = value['hero']
        daily.fields(hero, 'mediaId fit position')
        image(hero['mediaId'])
        if hero['fit'] not in ('contain', 'cover') or type(hero['position']) is not int or not 0 <= hero['position'] <= 100:
            raise ValueError('Cadrage invalide.')
    if not isinstance(value['services'], dict) or set(value['services']) - {'day', 'night', 'walk'}:
        raise ValueError('Service inconnu.')
    for item in value['services'].values():
        if not isinstance(item, dict):
            raise ValueError('Illustration invalide.')
        if set(item) == {'face'} and item['face'] in FACES:
            continue
        daily.fields(item, 'mediaId')
        image(item['mediaId'])


def mutate(c, user, action, value):
    bid = user['business_id']
    if action == 'branding':
        if user['role'] != 'owner':
            raise PermissionError('Accès réservé à la propriétaire.')
        valid_branding(c, bid, value)
        c.execute('INSERT INTO business_branding(business_id,snapshot) VALUES(?,?) ON CONFLICT(business_id) DO UPDATE SET snapshot=excluded.snapshot', (bid, json.dumps(value)))
    elif action == 'cover':
        daily.fields(value, 'dogId mediaId')
        upload_scope(c, user, value['dogId'], 'dog')
        if value['mediaId'] is None:
            c.execute('DELETE FROM dog_cover WHERE business_id=? AND dog_id=?', (bid, value['dogId']))
            return
        row = asset(c, user, value['mediaId'])
        if not row or row['dog_id'] != value['dogId'] or not row['mime'].startswith('image/'):
            raise LookupError('Photo introuvable dans cet album.')
        c.execute('INSERT INTO dog_cover(business_id,dog_id,media_id) VALUES(?,?,?) ON CONFLICT(business_id,dog_id) DO UPDATE SET media_id=excluded.media_id', (bid, value['dogId'], row['id']))
    elif action == 'delete':
        daily.fields(value, 'id')
        row = asset(c, user, value['id'])
        if not row:
            raise LookupError('Média introuvable.')
        current = branding(c, bid)
        if current['hero'] and current['hero']['mediaId'] == row['id']:
            current['hero'] = None
        current['services'] = {k: v for k, v in current['services'].items() if v.get('mediaId') != row['id']}
        c.execute('UPDATE business_branding SET snapshot=? WHERE business_id=?', (json.dumps(current), bid))
        c.execute('DELETE FROM dog_cover WHERE business_id=? AND media_id=?', (bid, row['id']))
        c.execute('DELETE FROM media_asset WHERE business_id=? AND id=?', (bid, row['id']))
    else:
        raise LookupError('Action inconnue.')


def public_branding(c, bid):
    value = branding(c, bid)
    def project(item):
        if 'mediaId' not in item:
            return item
        return {**{k: v for k, v in item.items() if k != 'mediaId'}, 'url': '/api/public/media/' + item['mediaId']}
    return {'hero': project(value['hero']) if value['hero'] else None,
            'services': {k: project(v) for k, v in value['services'].items()}}


def public_asset(c, bid, ident):
    current = branding(c, bid)
    selected = {v.get('mediaId') for v in current['services'].values()}
    if current['hero']:
        selected.add(current['hero']['mediaId'])
    if ident not in selected:
        return None
    return c.execute("SELECT " + META + " FROM media_asset WHERE business_id=? AND id=? AND purpose='branding' AND mime LIKE 'image/%'", (bid, ident)).fetchone()


def verify_database(c):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='media_asset'").fetchone():
        return
    for rowid, size, checksum, actual in c.execute('SELECT rowid,size,sha256,length(contents) FROM media_asset'):
        if size != actual:
            raise ValueError('media size mismatch')
        digest = hashlib.sha256()
        with c.blobopen('media_asset', 'contents', rowid, readonly=True) as stream:
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != checksum:
            raise ValueError('media checksum mismatch')
    if c.execute("SELECT 1 FROM dog_cover d LEFT JOIN media_asset m ON d.media_id=m.id AND d.business_id=m.business_id AND d.dog_id=m.dog_id WHERE m.id IS NULL OR m.mime NOT LIKE 'image/%'").fetchone():
        raise ValueError('missing cover image')
    for bid, value in c.execute('SELECT business_id,snapshot FROM business_branding'):
        valid_branding(c, bid, json.loads(value))
