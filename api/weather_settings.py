"""Business location and an owner-selected air-temperature warning threshold."""
import json
import math

import daily

DEFAULT_HEAT_THRESHOLD = 25
MIN_HEAT_THRESHOLD = 0
MAX_HEAT_THRESHOLD = 50


def empty():
    return {'location': None, 'heatThreshold': DEFAULT_HEAT_THRESHOLD}


def load(connection, business_id):
    row = connection.execute('SELECT snapshot FROM business_weather_settings WHERE business_id=?',
                             (business_id,)).fetchone()
    return json.loads(row[0]) if row else empty()


def number(value, name, minimum, maximum):
    if (type(value) not in (int, float) or not minimum <= value <= maximum or
            not math.isfinite(value)):
        raise ValueError('invalid ' + name)


def validate(value):
    daily.fields(value, 'location heatThreshold')
    number(value['heatThreshold'], 'heat threshold', MIN_HEAT_THRESHOLD, MAX_HEAT_THRESHOLD)
    location = value['location']
    if location is not None:
        daily.fields(location, 'name latitude longitude')
        daily.text(location['name'], 'location name')
        number(location['latitude'], 'latitude', -90, 90)
        number(location['longitude'], 'longitude', -180, 180)
    return value


def save(connection, business_id, value):
    connection.execute('INSERT INTO business_weather_settings(business_id,snapshot) VALUES(?,?) '
                       'ON CONFLICT(business_id) DO UPDATE SET snapshot=excluded.snapshot',
                       (business_id, json.dumps(value, ensure_ascii=False)))
