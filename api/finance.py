"""Business-scoped accounting drafts, immutable invoice details and original documents."""
import base64
import hashlib
import json
import re
from datetime import date

import daily


def empty():
    return {'version': 1, 'profile': {'name': '', 'address': '', 'taxId': ''}, 'entries': [], 'documents': []}


def load(c, business_id):
    row = c.execute('SELECT snapshot FROM business_finance WHERE business_id=?', (business_id,)).fetchone()
    return json.loads(row[0]) if row else empty()


def require(ok):
    if not ok:
        raise ValueError('invalid accounting record')


def text(value, limit, required=False):
    require(isinstance(value, str) and len(value) <= limit and (not required or value.strip()) and
            not any((ord(x) < 32 and x not in '\r\n\t') or ord(x) == 127 or 0xd800 <= ord(x) <= 0xdfff for x in value))


def calendar(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value))
    try:
        require(date.fromisoformat(value).isoformat() == value)
    except ValueError:
        raise ValueError('invalid date') from None


def minor(value):
    require(type(value) is int and 0 <= value <= 100000000)


def total(entry):
    if not entry['lines'] or any(x['unitMinor'] is None for x in entry['lines']):
        return None
    value = sum(x['quantity'] * x['unitMinor'] for x in entry['lines'])
    require(value <= 1000000000000)
    return value


def validate(value, previous):
    daily.fields(value, 'version profile entries documents')
    require(type(value['version']) is int and value['version'] == 1)
    daily.fields(value['profile'], 'name address taxId')
    for key, limit in [('name', 160), ('address', 1000), ('taxId', 120)]:
        text(value['profile'][key], limit)
    docids = daily.collection(value['documents'])
    daily.collection(value['entries'])
    hashes, numbers, regions = set(), set(), set()
    for d in value['documents']:
        daily.fields(d, 'id name type size sha256')
        require(isinstance(d['sha256'], str) and re.fullmatch('[a-f0-9]{64}', d['sha256']) and
                d['id'] == d['sha256'] and d['sha256'] not in hashes)
        hashes.add(d['sha256'])
        text(d['name'], 180, True)
        require(d['type'] in ('image/jpeg', 'image/png', 'application/pdf') and
                type(d['size']) is int and 0 < d['size'] <= 5 * 1024 * 1024)
    for e in value['entries']:
        daily.fields(e, 'id kind status number date due party address issuer issuerAddress taxId currency category lines vatMinor note sourceId region raw payments cancelReason')
        require(e['kind'] in ('sale', 'purchase', 'expense', 'extra') and e['status'] in ('draft', 'confirmed', 'cancelled') and
                e['category'] in ('service', 'supplies', 'food', 'transport', 'health', 'equipment', 'insurance', 'other'))
        for key in ('number', 'party', 'issuer', 'taxId'):
            text(e[key], 160)
        for key in ('address', 'issuerAddress', 'note', 'cancelReason'):
            text(e[key], 1000)
        text(e['raw'], 20000)
        require(isinstance(e['currency'], str) and (e['currency'] == '' or re.fullmatch('[A-Z]{3}', e['currency'])))
        for key in ('date', 'due'):
            if e[key] != '':
                calendar(e[key])
        require(not e['due'] or not e['date'] or e['due'] >= e['date'])
        require(isinstance(e['sourceId'], str) and (e['sourceId'] == '' or e['sourceId'] in docids))
        r = e['region']
        if r is not None:
            daily.fields(r, 'page x y width height')
            require(e['sourceId'] and type(r['page']) is int and 1 <= r['page'] <= 100)
            for key in ('x', 'y', 'width', 'height'):
                require(type(r[key]) in (float, int) and 0 <= r[key] <= 1)
            require(r['width'] > 0 and r['height'] > 0 and r['x'] + r['width'] <= 1.000001 and r['y'] + r['height'] <= 1.000001)
        require(isinstance(e['lines'], list) and 1 <= len(e['lines']) <= 100)
        for line in e['lines']:
            daily.fields(line, 'description quantity unitMinor bookingId')
            text(line['description'], 500)
            require(type(line['quantity']) is int and 1 <= line['quantity'] <= 10000)
            if line['unitMinor'] is not None:
                minor(line['unitMinor'])
            require(isinstance(line['bookingId'], str) and (line['bookingId'] == '' or daily.ID.fullmatch(line['bookingId'])))
        amount = total(e)
        if e['vatMinor'] is not None:
            minor(e['vatMinor'])
            require(amount is None or e['vatMinor'] <= amount)
        daily.collection(e['payments'])
        require(len(e['payments']) <= 100)
        for p in e['payments']:
            daily.fields(p, 'id date amountMinor note')
            calendar(p['date'])
            minor(p['amountMinor'])
            require(p['amountMinor'] > 0)
            text(p['note'], 500)
        require(not e['payments'] or (e['status'] == 'confirmed' and amount is not None and sum(p['amountMinor'] for p in e['payments']) <= amount))
        if e['status'] == 'confirmed':
            calendar(e['date'])
            require(e['party'].strip() and e['currency'] and amount is not None and all(l['description'].strip() for l in e['lines']))
            if e['kind'] == 'sale':
                require(all(e[k].strip() for k in ('number', 'address', 'issuer', 'issuerAddress')))
        if e['status'] == 'cancelled':
            require(e['cancelReason'].strip() and not e['payments'])
        if e['kind'] == 'sale' and e['status'] != 'draft' and e['number'].strip():
            require(e['number'].strip() not in numbers)
            numbers.add(e['number'].strip())
        if e['sourceId'] and r is not None and e['status'] != 'cancelled':
            key = (e['sourceId'], r['page'], r['x'], r['y'], r['width'], r['height'])
            require(key not in regions)
            regions.add(key)
    for d in previous['documents']:
        require(d in value['documents'])
    current = {x['id']: x for x in value['entries']}
    for old in previous['entries']:
        require(old['id'] in current)
        e = current[old['id']]
        if old['payments']:
            require(e['currency'] == old['currency'] and
                    (e['kind'] in ('sale', 'extra')) == (old['kind'] in ('sale', 'extra')))
        if old['kind'] == 'sale' and old['status'] != 'draft':
            require(all(e[k] == v for k, v in old.items() if k not in ('payments', 'status', 'cancelReason')))
            require(e['status'] == old['status'] or (old['status'] == 'confirmed' and e['status'] == 'cancelled'))
            if old['status'] == 'cancelled':
                require(e['cancelReason'] == old['cancelReason'])
        require(all(p in e['payments'] for p in old['payments']))
    return value


def save(c, business_id, value, uploads):
    previous = load(c, business_id)
    validate(value, previous)
    require(isinstance(uploads, list) and len(uploads) <= 10)
    oldids = {d['id'] for d in previous['documents']}
    additions = {d['id']: d for d in value['documents'] if d['id'] not in oldids}
    require(len(uploads) == len(additions))
    seen, size = set(), 0
    for item in uploads:
        daily.fields(item, 'id data')
        require(isinstance(item['id'], str) and item['id'] in additions and item['id'] not in seen)
        seen.add(item['id'])
        d = additions[item['id']]
        require(isinstance(item['data'], str) and len(item['data']) <= 6990508)
        try:
            blob = base64.b64decode(item['data'], validate=True)
        except ValueError:
            raise ValueError('invalid document encoding') from None
        signature = {'application/pdf': b'%PDF-', 'image/jpeg': b'\xff\xd8\xff', 'image/png': b'\x89PNG\r\n\x1a\n'}[d['type']]
        require(len(blob) == d['size'] and blob.startswith(signature) and hashlib.sha256(blob).hexdigest() == d['sha256'])
        size += len(blob)
        require(size <= 20 * 1024 * 1024)
        c.execute('INSERT INTO finance_document(business_id,id,mime,contents) VALUES(?,?,?,?)', (business_id, d['id'], d['type'], blob))
    c.execute('INSERT INTO business_finance(business_id,snapshot) VALUES(?,?) ON CONFLICT(business_id) DO UPDATE SET snapshot=excluded.snapshot', (business_id, json.dumps(value, ensure_ascii=False)))
