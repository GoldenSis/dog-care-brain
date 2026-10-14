"""Private, unreviewed experience notes; independent of saved care snapshots."""
import json
from urllib.parse import urlsplit

import daily


def empty():
    return {'version': 1, 'experiences': []}


def load(connection, business_id):
    row = connection.execute('SELECT snapshot FROM business_knowledge WHERE business_id=?',
                             (business_id,)).fetchone()
    return json.loads(row[0]) if row else empty()


def validate(value):
    daily.fields(value, 'version experiences')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('unsupported knowledge format')
    records = value['experiences']
    daily.collection(records)
    if len(records) > 1000:
        raise ValueError('too many experiences')
    for item in records:
        daily.fields(item, 'id title body category author url status')
        daily.text(item['title'], 'title')
        daily.text(item['author'], 'author', optional=True)
        body = item['body']
        if (not isinstance(body, str) or not body.strip() or len(body) > 4000 or
                any((ord(c) < 32 and c not in '\n\r\t') or ord(c) == 127 for c in body)):
            raise ValueError('invalid experience text')
        if item['category'] not in ('traditional', 'colleague') or item['status'] != 'draft':
            raise ValueError('experiences must remain unreviewed drafts')
        link = daily.text(item['url'], 'link', 2000, optional=True)
        if link:
            try:
                parsed = urlsplit(link)
                valid = (parsed.scheme in ('http', 'https') and parsed.hostname and
                         not parsed.username and not parsed.password and
                         not any(c.isspace() for c in link) and '\\' not in link)
                parsed.port  # Reject malformed ports as well as unsafe schemes.
            except ValueError:
                valid = False
            if not valid:
                raise ValueError('invalid source link')
    return value


def save(connection, business_id, value):
    connection.execute('INSERT INTO business_knowledge(business_id,snapshot) VALUES(?,?) '
                       'ON CONFLICT(business_id) DO UPDATE SET snapshot=excluded.snapshot',
                       (business_id, json.dumps(value, ensure_ascii=False)))
