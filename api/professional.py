"""Explicit, read-only sharing with one invited professional in one business.

Notes are shared as the version the owner selected. Files are immutable source
references; every read checks both the selected record and its current dog grant.
No family, booking, accounting, raw audio or business knowledge is projected.
"""
import hashlib
import json
import time

import daily


def clear(c, uid):
    c.execute('DELETE FROM professional_record WHERE user_id=?', (uid,))
    c.execute('DELETE FROM professional_dog WHERE user_id=?', (uid,))


def prune(c, bid, previous, current):
    """Removing/reassigning a dog ends its grants, including after ID reuse."""
    after = {d['id']: d['clientId'] for d in current['dogs']}
    for dog in previous['dogs']:
        if dog['id'] not in after or after[dog['id']] != dog['clientId']:
            c.execute('DELETE FROM professional_record WHERE business_id=? AND dog_id=?', (bid, dog['id']))
            c.execute('DELETE FROM professional_dog WHERE business_id=? AND dog_id=?', (bid, dog['id']))


def dogs(c, user):
    current = {d['id']: d for d in daily.load(c, user['business_id'])['dogs']}
    return {r['dog_id']: current[r['dog_id']] for r in c.execute(
        'SELECT dog_id,client_id FROM professional_dog WHERE user_id=? AND business_id=?',
        (user['id'], user['business_id'])) if r['dog_id'] in current and
        current[r['dog_id']]['clientId'] == r['client_id']}


def records(c, user):
    allowed = dogs(c, user)
    return [json.loads(r['snapshot']) for r in c.execute(
        'SELECT dog_id,snapshot FROM professional_record WHERE user_id=? AND business_id=? ORDER BY rowid',
        (user['id'], user['business_id'])) if r['dog_id'] in allowed]


def permits(c, user, kind, ident):
    return user['role'] == 'professional' and any(
        r['key'] == kind + ':' + ident for r in records(c, user))


def catalog(c, bid):
    current = daily.load(c, bid)
    allowed = {d['id'] for d in current['dogs']}
    out = []
    for row in c.execute('SELECT o.*,d.slug FROM observation o JOIN dog d ON d.id=o.dog_id '
                         'WHERE o.business_id=? ORDER BY o.id', (bid,)):
        if row['slug'] in allowed:
            ident = row['client_id'] if row['client_id'] is not None else row['id']
            record = {'kind': 'note', 'dogId': row['slug'], 'label': row['title'] or '',
                      'text': row['text'], 'date': row['date'] or ''}
            version = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
            out.append({'key': f"note:{row['slug']}:{ident}:{version}", **record})
    for doc in current['documents']:
        if doc['dogId'] in allowed:
            out.append({'key': 'document:' + doc['id'], 'kind': 'document', 'dogId': doc['dogId'],
                        'label': doc['label'], 'href': '/api/documents/' + doc['id'], 'mime': doc['type']})
    for row in c.execute('SELECT id,dog_id,client_id,label,mime FROM client_document WHERE business_id=?', (bid,)):
        dog = next((d for d in current['dogs'] if d['id'] == row['dog_id']), None)
        if dog and dog['clientId'] == row['client_id']:
            out.append({'key': 'client-document:' + row['id'], 'kind': 'document', 'dogId': row['dog_id'],
                        'label': row['label'], 'href': '/api/client-documents/' + row['id'], 'mime': row['mime']})
    for row in c.execute("SELECT id,dog_id,client_id,name,mime FROM media_asset WHERE business_id=? AND purpose='dog'", (bid,)):
        dog = next((d for d in current['dogs'] if d['id'] == row['dog_id']), None)
        if dog and dog['clientId'] == row['client_id']:
            out.append({'key': 'media:' + row['id'], 'kind': 'media', 'dogId': row['dog_id'],
                        'label': row['name'], 'href': '/api/media/content/' + row['id'], 'mime': row['mime']})
    return out


def members(c, bid):
    out = []
    for row in c.execute("SELECT id,email,role,business_id FROM user WHERE business_id=? AND role='professional' ORDER BY email", (bid,)):
        user = dict(row)
        shared = records(c, user)
        out.append({'id': user['id'], 'email': user['email'], 'dogIds': list(dogs(c, user)),
                    'recordKeys': [r['key'] for r in shared], 'sharedRecords': shared})
    return out


def grant(c, user, payload):
    if user['role'] != 'owner':
        raise PermissionError('owner access required')
    daily.fields(payload, 'email dogIds recordKeys')
    email = payload['email'].strip().lower() if isinstance(payload['email'], str) else ''
    selected = payload['dogIds']
    keys = payload['recordKeys']
    if (not email or len(email) > 255 or not isinstance(selected, list) or not 1 <= len(selected) <= 100 or
            not all(isinstance(x, str) for x in selected) or len(set(selected)) != len(selected) or
            not isinstance(keys, list) or len(keys) > 500 or not all(isinstance(x, str) for x in keys) or
            len(set(keys)) != len(keys)):
        raise ValueError('invalid professional selection')
    bid = user['business_id']
    current = {d['id']: d for d in daily.load(c, bid)['dogs']}
    if not set(selected) <= current.keys():
        raise ValueError('unknown dog')
    available = {r['key']: r for r in catalog(c, bid)}
    if not set(keys) <= available.keys() or any(available[k]['dogId'] not in selected for k in keys):
        raise ValueError('record outside selected dogs')
    existing = c.execute('SELECT id,role,business_id FROM user WHERE email=?', (email,)).fetchone()
    if existing and (existing['business_id'] != bid or existing['role'] not in ('professional', 'revoked')):
        raise ValueError('this account cannot be reassigned')
    if existing:
        uid = existing['id']
        c.execute("UPDATE user SET role='professional' WHERE id=?", (uid,))
    else:
        uid = c.execute("INSERT INTO user(email,role,business_id,created) VALUES(?,'professional',?,?)",
                        (email, bid, int(time.time()))).lastrowid
        c.execute("INSERT INTO pref(user_id,language) VALUES(?,'fr')", (uid,))
    clear(c, uid)
    c.execute('DELETE FROM client_access WHERE user_id=?', (uid,))
    c.execute('DELETE FROM session WHERE user_id=?', (uid,))
    c.execute('DELETE FROM magic WHERE email=?', (email,))
    for dog_id in selected:
        c.execute('INSERT INTO professional_dog(user_id,business_id,dog_id,client_id) VALUES(?,?,?,?)',
                  (uid, bid, dog_id, current[dog_id]['clientId']))
    for key in keys:
        r = available[key]
        c.execute('INSERT INTO professional_record(user_id,business_id,dog_id,record_key,snapshot) VALUES(?,?,?,?,?)',
                  (uid, bid, r['dogId'], key, json.dumps(r, ensure_ascii=False)))


def project(c, user, state):
    selected = dogs(c, user)
    shared = records(c, user)
    state.update(imported=True, dogs=[{'id': d['id'], 'slug': d['id'], 'name': d['name']} for d in selected.values()],
                 observations={}, invites=[], knowledge=None, finance=None,
                 daily={**daily.empty(), 'dogs': [{'id': d['id'], 'name': d['name'], 'clientId': None} for d in selected.values()]},
                 portal={'updates': [], 'requests': [], 'documents': [], 'members': [], 'quotes': {},
                         'extras': [], 'bookingClients': {}, 'sharedRecords': shared})
    return state
