"""Instance brand from the environment. The default leaves the original site untouched."""
import json
import os
import re

DEFAULT = 'Le Bus des Toutous'
# Adine-Sophie's own photos and films, never served by another brand.
PRIVATE_ASSETS = ('assets/photos/', 'assets/films/')


def current():
    env = lambda name: os.environ.get(name, '').strip()
    return {'name': env('DC_BRAND_NAME') or DEFAULT, 'tagline': env('DC_BRAND_TAGLINE'),
            'owner': env('DC_BRAND_OWNER'), 'instagram': env('DC_BRAND_INSTAGRAM').lstrip('@'),
            'mark': env('DC_BRAND_MARK')}


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
            '.nav-item.active{box-shadow:inset 0 -3px 0 %s}.welcome-dialog a,.first-contact a{color:%s}@media(max-width:650px){.welcome-photo{box-shadow:5px 5px 0 %s}}</style>'
            % (c['secondary'], readable(c['secondary']), c['dark'], c['dark'], c['secondary'], c['secondary'], readable(c['secondary']), c['secondary']))


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
    text = text.replace(DEFAULT, name).replace('<head>', '<head>\n    <script>window.DOGCARE_BRAND=' + script + ';</script>', 1)
    # A long instance name wraps instead of running under the header buttons.
    style = '<style>.welcome-brand{white-space:normal;overflow-wrap:anywhere}.welcome-brand>span{flex:none}</style>'
    return text.replace('</head>', style + palette_style() + '</head>', 1).encode('utf-8')


def subject():
    return 'Votre accès · ' + current()['name'] + ' by Plus de Fun'


def signature():
    return current()['name'] + ' · by Plus de Fun'
