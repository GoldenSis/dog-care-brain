"""Service quotes and optional extras, separate from issued accounting records.

Money reuses daily's integer hundredths/currency contract. A request captures
its rate once; editing the price list never rewrites a previously quoted rate.
"""
import secrets

import daily


def units(item):
    count = (daily.calendar(item['end']) - daily.calendar(item['start'])).days + (item['service'] != 'night')
    if item['service'] not in ('day', 'night', 'walk') or not 1 <= count <= 366:
        raise ValueError('invalid service dates')
    return count


def estimate(current, item):
    count = units(item)
    amount = current['rates'][item['service']]
    return {'unitMinor': amount, 'currency': current['rates']['currency'], 'units': count,
            'baseMinor': None if amount is None else amount * count,
            'totalMinor': None if amount is None else amount * count, 'extras': []}


def capture(c, bid, request_id, current, item):
    quote = estimate(current, item)
    c.execute('INSERT INTO request_quote(business_id,id,unit_minor,currency) VALUES(?,?,?,?)',
              (bid, request_id, quote['unitMinor'], quote['currency']))


def quote(c, bid, item, booking=False):
    # Saved bookings are authoritative, including explicit unknown amounts.
    saved = c.execute('SELECT unit_minor,currency FROM request_quote WHERE business_id=? AND id=?', (bid, item['id'])).fetchone()
    amount = item['unitMinor'] if booking else saved['unit_minor'] if saved else None
    currency = item['currency'] if booking else saved['currency'] if saved else daily.load(c, bid)['rates']['currency']
    count = units(item)
    extras = [dict(row) for row in c.execute(
        'SELECT id,label,unit_minor AS unitMinor,quantity,currency FROM booking_extra WHERE business_id=? AND target_id=? ORDER BY rowid',
        (bid, item['id']))]
    for extra in extras:
        extra['totalMinor'] = extra['unitMinor'] * extra['quantity']
    base = None if amount is None else amount * count
    total = None if base is None else base + sum(e['totalMinor'] for e in extras)
    if any(e['currency'] != currency for e in extras):
        total = None  # Never sum unlike currencies after an explicit booking edit.
    return {'id': item['id'], 'unitMinor': amount, 'currency': currency, 'units': count,
            'baseMinor': base, 'extras': extras, 'totalMinor': total}


def target(c, bid, current, ident):
    daily.identifier(ident)
    item = next((b for b in current['bookings'] if b['id'] == ident), None)
    if item:
        if item.get('status') == 'cancelled':
            raise ValueError('cancelled booking history must be retained')
        return item, True
    row = c.execute("SELECT id,dog_id AS dogId,service,start,end FROM booking_request WHERE business_id=? AND id=? AND status='requested'", (bid, ident)).fetchone()
    if not row or row['dogId'] not in {d['id'] for d in current['dogs']}:
        raise ValueError('request or booking unavailable')
    return dict(row), False


def templates(c, bid):
    return [dict(row) for row in c.execute('SELECT id,label,unit_minor AS unitMinor,currency FROM extra_template WHERE business_id=? ORDER BY label', (bid,))]


def mutate(c, bid, current, route, payload):
    if route == 'extra-remove':
        daily.fields(payload, 'targetId id')
        target(c, bid, current, payload['targetId'])
        if not c.execute('DELETE FROM booking_extra WHERE business_id=? AND target_id=? AND id=?', (bid, payload['targetId'], payload['id'])).rowcount:
            raise ValueError('unknown extra')
        return
    if route == 'quote':
        daily.fields(payload, 'targetId unitMinor currency')
        item, booking = target(c, bid, current, payload['targetId'])
        previous = quote(c, bid, item, booking)
        daily.amount(payload['unitMinor'])
        daily.currency(payload['currency'])
        if payload['unitMinor'] is None or previous['unitMinor'] is not None:
            raise ValueError('only an unknown base price can be completed')
        if previous['extras'] and any(e['currency'] != payload['currency'] for e in previous['extras']):
            raise ValueError('extras must share the quote currency')
        if booking:
            item.update(unitMinor=payload['unitMinor'], currency=payload['currency'])
            daily.validate(current, daily.load(c, bid))
            daily.save(c, bid, current)
        else:
            c.execute('INSERT INTO request_quote(business_id,id,unit_minor,currency) VALUES(?,?,?,?) ON CONFLICT(business_id,id) DO UPDATE SET unit_minor=excluded.unit_minor,currency=excluded.currency',
                      (bid, item['id'], payload['unitMinor'], payload['currency']))
        return
    daily.fields(payload, 'targetId id label unitMinor currency quantity reusable')
    item, booking = target(c, bid, current, payload['targetId'])
    prior = quote(c, bid, item, booking)
    daily.text(payload['label'], 'extra label', 160)
    daily.amount(payload['unitMinor'])
    daily.currency(payload['currency'])
    if (payload['unitMinor'] is None or
            type(payload['quantity']) is not int or not 1 <= payload['quantity'] <= 10000 or type(payload['reusable']) is not bool):
        raise ValueError('invalid extra price, currency or quantity')
    if payload['currency'] != prior['currency']:
        if prior['unitMinor'] is not None or prior['extras']:
            raise ValueError('extras must share the quote currency')
        if booking:
            item['currency'] = payload['currency']
            daily.validate(current, daily.load(c,bid))
            daily.save(c,bid,current)
        else:
            c.execute('INSERT INTO request_quote(business_id,id,unit_minor,currency) VALUES(?,?,NULL,?) ON CONFLICT(business_id,id) DO UPDATE SET currency=excluded.currency',
                      (bid,item['id'],payload['currency']))
    ident = payload['id']
    if ident:
        daily.identifier(ident)
        if not any(e['id'] == ident for e in prior['extras']):
            raise ValueError('unknown extra')
    else:
        if len(prior['extras']) >= 100:
            raise ValueError('too many extras')
        ident = secrets.token_hex(16)
    total = (prior['baseMinor'] or 0) + sum(e['totalMinor'] for e in prior['extras'] if e['id'] != ident) + payload['unitMinor'] * payload['quantity']
    if total > 1000000000000:
        raise ValueError('quote exceeds supported amount')
    c.execute('INSERT INTO booking_extra(business_id,target_id,id,label,unit_minor,currency,quantity) VALUES(?,?,?,?,?,?,?) '
              'ON CONFLICT(business_id,id) DO UPDATE SET label=excluded.label,unit_minor=excluded.unit_minor,currency=excluded.currency,quantity=excluded.quantity',
              (bid, item['id'], ident, payload['label'].strip(), payload['unitMinor'], payload['currency'], payload['quantity']))
    if payload['reusable']:
        if len(templates(c, bid)) >= 500:
            raise ValueError('too many reusable extras')
        c.execute('INSERT INTO extra_template(business_id,id,label,unit_minor,currency) VALUES(?,?,?,?,?) '
                  'ON CONFLICT(business_id,label,currency) DO UPDATE SET unit_minor=excluded.unit_minor',
                  (bid, secrets.token_hex(16), payload['label'].strip(), payload['unitMinor'], payload['currency']))
