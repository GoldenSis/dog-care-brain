"""Instance brand from the environment. The default leaves the original site untouched."""
import json
import os
import re
import sys

DEFAULT = 'Le Bus des Toutous'
# Adine-Sophie's own photos and films, never served by another brand.
PRIVATE_ASSETS = ('assets/photos/', 'assets/films/')


def current():
    env = lambda name: os.environ.get(name, '').strip()
    brand = {'name': env('DC_BRAND_NAME') or DEFAULT, 'tagline': env('DC_BRAND_TAGLINE'),
             'owner': env('DC_BRAND_OWNER'), 'instagram': env('DC_BRAND_INSTAGRAM').lstrip('@'),
             'mark': env('DC_BRAND_MARK')}
    if brand['name'] != DEFAULT:
        brand |= {'short': env('DC_BRAND_SHORT'), 'logo': LOGO_PATH if logo() else '', 'content': content()}
    return brand


# DC_BRAND_LOGO: the instance's own logo file, outside the release; served at LOGO_PATH.
LOGO_PATH = '/brand/logo'
LOGO_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}


def logo():
    """(path, mime) of a readable custom-brand logo, else None."""
    path = os.environ.get('DC_BRAND_LOGO', '').strip()
    mime = LOGO_TYPES.get(os.path.splitext(path)[1].lower())
    return (path, mime) if path and mime and os.path.isfile(path) else None


# DC_BRAND_CONTENT: a JSON file with the instance's own public copy. Everything is optional and literal
# in every language; anything malformed is dropped so the default interface copy shows instead.
SERVICE_KEYS = ('day', 'night', 'walk')
FACES = ('terrier', 'pug', 'dalmatian')


def _text(value, limit):
    return value.strip() if isinstance(value, str) and value.strip() and len(value) <= limit and not re.search(r'[\x00-\x1f\x7f]', value) else ''


def _texts(value, limit, count):
    items = [_text(v, limit) for v in value[:count]] if isinstance(value, list) else []
    return items if all(items) else []


def _service(item):
    if not isinstance(item, dict):
        return None
    service = {'id': _text(item.get('id'), 24), 'label': _text(item.get('label'), 80), 'detail': _text(item.get('detail'), 400),
               'request': item.get('request'), 'face': item.get('face') if item.get('face') in FACES else 'terrier'}
    ok = re.fullmatch(r'[a-z][a-z0-9-]*', service['id']) and service['label'] and service['request'] in SERVICE_KEYS
    return service if ok else None


def _section(value, fields):
    value = value if isinstance(value, dict) else {}
    return {key: check(value.get(key)) for key, check in fields.items() if check(value.get(key))}


def content():
    path = os.environ.get('DC_BRAND_CONTENT', '').strip()
    if not path:
        return {}
    try:
        with open(path, encoding='utf-8') as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            raise ValueError('not an object')
    except (OSError, ValueError) as error:
        print('DC_BRAND_CONTENT ignored: %s' % error, file=sys.stderr, flush=True)
        return {}
    services = [_service(item) for item in raw.get('services', [])[:6]] if isinstance(raw.get('services'), list) else []
    ids = [s['id'] for s in services if s]
    contact = raw.get('contact') if isinstance(raw.get('contact'), dict) else {}
    phone, reviews, email = (str(contact.get(key) or '') for key in ('phone', 'reviews', 'email'))
    result = {
        'hero': _section(raw.get('hero'), {'heading': lambda v: _text(v, 120), 'text': lambda v: _text(v, 300)}),
        'services': services if services and all(services) and len(set(ids)) == len(ids) else [],
        'price': _text(raw.get('price'), 60),
        'about': _section(raw.get('about'), {'kicker': lambda v: _text(v, 60), 'heading': lambda v: _text(v, 120),
                                             'paragraphs': lambda v: _texts(v, 600, 4), 'steps': lambda v: _texts(v, 120, 4)}),
        'contact': {k: v for k, v in (('phone', phone if re.fullmatch(r'\+?[0-9 .]{6,20}', phone) else ''),
                                      ('email', email if re.fullmatch(r'[^\s@"<>]{1,64}@[^\s@"<>]{1,190}\.[a-z]{2,24}', email) else ''),
                                      ('reviews', _text(reviews, 300) if re.fullmatch(r'https://[^\s"<>]+', reviews) else '')) if v},
        'shop': _section(raw.get('shop'), {'label': lambda v: _text(v, 60), 'text': lambda v: _text(v, 300)}),
        'gallery': _section(raw.get('gallery'), {'empty': lambda v: _text(v, 300)}),
    }
    return {k: v for k, v in result.items() if v}


def custom():
    return current()['name'] != DEFAULT


# The approved orange family, by role. A custom palette replaces each literal in served CSS/HTML/JS.
PRIMARY = ('#f2851e', '#ff982f', '#ffad48')
DARK = ('#954407', '#9b4b0d', '#a6430b', '#b84600', '#99451d', '#884007', '#a94908', '#a34b09',
        '#9b4c00', '#8a3e00', '#c4580b', '#b86d21', '#af641d')
HEX = re.compile(r'#[0-9a-fA-F]{6}')


def _luminance(colour):
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def readable(colour):
    """Darken until text in this colour reaches WCAG AA (4.5:1) on white."""
    while 1.05 / (_luminance(colour) + 0.05) < 4.5:
        colour = '#' + ''.join('%02x' % int(int(colour[i:i + 2], 16) * .92) for i in (1, 3, 5))
    return colour


def palette():
    """{primary, dark, secondary} from DC_BRAND_PRIMARY/DARK/SECONDARY, or None for the default orange."""
    if not custom():
        return None
    values = {k: os.environ.get('DC_BRAND_' + k.upper(), '').strip().lower() for k in ('primary', 'dark', 'secondary')}
    if not HEX.fullmatch(values['primary']) or not HEX.fullmatch(values['dark']):
        return None
    values['secondary'] = values['secondary'] if HEX.fullmatch(values['secondary']) else values['dark']
    return values


def recolour(data):
    colours = palette()
    if not colours:
        return data
    table = {old: colours['primary'] for old in PRIMARY} | {old: colours['dark'] for old in DARK}
    text = re.sub(r'#[0-9a-fA-F]{6}', lambda m: table.get(m.group().lower(), m.group()), data.decode('utf-8'))
    text = re.sub(r'%23([0-9a-fA-F]{6})', lambda m: table.get('#' + m.group(1).lower(), '#' + m.group(1)).replace('#', '%23'), text)
    return text.encode('utf-8')


def palette_style():
    """Contrast fixes on top of the recoloured tokens: dark text on the primary, secondary for decoration only."""
    c = palette()
    if not c:
        return ''
    return ('<style>:root{--brand-secondary:%s;--brand-link:%s}.primary,#public-welcome .primary,.workspace-mark,'
            '.welcome-brand>span{color:%s}.utility-by b{color:%s}.welcome-photo{box-shadow:12px 10px 0 %s}'
            '.nav-item.active{box-shadow:inset 0 -3px 0 %s}.welcome-dialog a,.first-contact a{color:%s}.welcome-choices button[aria-pressed=true]{border-color:%s}@media(max-width:650px){.welcome-photo{box-shadow:5px 5px 0 %s}}</style>'
            % (c['secondary'], readable(c['secondary']), c['dark'], c['dark'], c['secondary'], c['secondary'], readable(c['secondary']), c['dark'], c['secondary']))


def page(data):
    """Rebrand a served HTML shell; default-brand bytes are returned unchanged."""
    brand = current()
    if brand['name'] == DEFAULT:
        return data
    name = brand['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    script = json.dumps(brand).replace('<', '\\u003c').replace('&', '\\u0026')
    text = data.decode('utf-8')
    text = re.sub(r'<noscript>.*?</noscript>', lambda _: '<noscript>' + name + '</noscript>', text, flags=re.S)
    text = text.replace('%2245%22>B</text>', '%2245%22>' + (re.sub(r'[^A-Za-z0-9]', '', name)[:1].upper() or 'D') + '</text>')
    # The workspace header shows the short name (DC_BRAND_SHORT) so it fits a phone; titles keep the full name.
    short = (brand.get('short') or brand['name']).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('</svg></span>' + DEFAULT + '</a>', '</svg></span>' + short + '</a>')
    text = text.replace(DEFAULT, name).replace('<head>', '<head>\n    <script>window.DOGCARE_BRAND=' + script + ';</script>', 1)
    # A long instance name wraps instead of running under the header buttons.
    style = '<style>.welcome-brand{white-space:normal;overflow-wrap:anywhere}.welcome-brand>span{flex:none}</style>'
    return text.replace('</head>', style + palette_style() + '</head>', 1).encode('utf-8')


def subject():
    return 'Votre accès · ' + current()['name'] + ' by Plus de Fun'


def signature():
    return current()['name'] + ' · by Plus de Fun'
