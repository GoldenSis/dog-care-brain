"""Business-private walk tracks (Balades) with spots; mirrors balades-model.js validation."""
import json
import math

import daily
import finance

TYPES = ('pause', 'danger', 'interdit', 'laisse', 'tolere')
TRACKS, POINTS, TOTAL_POINTS, SPOTS, DOGS, WALK_REFS, NAME, NOTE = 500, 20000, 600000, 200, 50, 50, 120, 500


def empty():
    return {'version': 1, 'tracks': []}


def load(c, business_id):
    """Snapshot and its own revision; Balades writes never touch the care revision."""
    row = c.execute('SELECT snapshot, revision FROM business_balades WHERE business_id=?', (business_id,)).fetchone()
    return (json.loads(row[0]), row[1]) if row else (empty(), 0)


def require(ok):
    if not ok:
        raise ValueError('invalid walk track')


def number(value, low, high):
    require(type(value) in (int, float) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high)


def validate(value):
    daily.fields(value, 'version tracks')
    require(type(value['version']) is int and value['version'] == 1 and isinstance(value['tracks'], list) and len(value['tracks']) <= TRACKS)
    ids, walks, total = set(), set(), 0
    for t in value['tracks']:
        daily.fields(t, 'id name date dogs points durationSec source walkRefs spots')
        require(isinstance(t['id'], str) and daily.ID.fullmatch(t['id']) and t['id'] not in ids)
        ids.add(t['id'])
        finance.text(t['name'], NAME, True)
        finance.calendar(t['date'])
        require(t['source'] in ('record', 'import'))
        require(t['durationSec'] is None or (type(t['durationSec']) is int and 0 <= t['durationSec'] <= 604800))
        require(isinstance(t['dogs'], list) and len(t['dogs']) <= DOGS and len(set(map(str, t['dogs']))) == len(t['dogs']) and
                all(isinstance(d, str) and daily.ID.fullmatch(d) for d in t['dogs']))
        require(isinstance(t['points'], list) and 2 <= len(t['points']) <= POINTS)
        for p in t['points']:
            require(isinstance(p, list) and len(p) == 3)
            number(p[0], -90, 90)
            number(p[1], -180, 180)
            require(p[2] is None or (type(p[2]) is int and 0 <= p[2] <= 4102444800))
        total += len(t['points'])
        require(total <= TOTAL_POINTS)
        require(isinstance(t['walkRefs'], list) and len(t['walkRefs']) <= WALK_REFS)
        for r in t['walkRefs']:
            daily.fields(r, 'date dogId')
            finance.calendar(r['date'])
            require(isinstance(r['dogId'], str) and daily.ID.fullmatch(r['dogId']) and r['dogId'] in t['dogs'])
            require((r['date'], r['dogId']) not in walks)
            walks.add((r['date'], r['dogId']))
        require(isinstance(t['spots'], list) and len(t['spots']) <= SPOTS)
        spot_ids = set()
        for s in t['spots']:
            daily.fields(s, 'id type lat lon note rule noted')
            require(isinstance(s['id'], str) and daily.ID.fullmatch(s['id']) and s['id'] not in spot_ids)
            spot_ids.add(s['id'])
            require(s['type'] in TYPES)
            number(s['lat'], -90, 90)
            number(s['lon'], -180, 180)
            finance.text(s['note'], NOTE)
            finance.text(s['rule'], NOTE)
            require(s['type'] == 'tolere' or s['rule'] == '')
            finance.calendar(s['noted'])
    return value


def save(c, business_id, value):
    revision = load(c, business_id)[1] + 1
    c.execute('INSERT INTO business_balades(business_id,snapshot,revision) VALUES(?,?,?) ON CONFLICT(business_id) DO UPDATE SET '
              'snapshot=excluded.snapshot, revision=excluded.revision', (business_id, json.dumps(value, ensure_ascii=False), revision))
    return revision
