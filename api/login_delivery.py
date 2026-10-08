"""Explicit login transport. No production debug-outbox fallback."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse


class DeliveryUnavailable(RuntimeError):
    pass


def configuration():
    mode = os.environ.get('DC_AUTH_MODE', 'disabled')
    if mode == 'development':
        if os.environ.get('DC_HOST', '127.0.0.1') not in ('127.0.0.1', 'localhost', '::1'):
            raise DeliveryUnavailable('development authentication requires loopback')
        return {'mode': mode}
    if mode != 'smtp':
        raise DeliveryUnavailable('login delivery is not configured')
    origin = os.environ.get('DC_PUBLIC_ORIGIN', '').rstrip('/')
    parsed = urlparse(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or
            parsed.path or parsed.query or parsed.fragment or os.environ.get('DC_INSECURE_COOKIE') != '0'):
        raise DeliveryUnavailable('HTTPS public origin and secure cookies are required')
    keys = {name: os.environ.get('DC_SMTP_'+name.upper(), '') for name in ('host','user','password','from')}
    tls = os.environ.get('DC_SMTP_TLS', 'ssl')
    if tls not in ('ssl','starttls') or any(not value or '\r' in value or '\n' in value for value in keys.values()):
        raise DeliveryUnavailable('SMTP configuration is incomplete')
    try:
        port = int(os.environ.get('DC_SMTP_PORT', '465' if tls=='ssl' else '587'))
        if not 1 <= port <= 65535:raise ValueError()
    except ValueError:
        raise DeliveryUnavailable('invalid SMTP port') from None
    return {**keys,'mode':mode,'origin':origin,'tls':tls,'port':port}


def demo_signup_enabled():
    return (os.environ.get('DC_AUTH_MODE') == 'development' and
            os.environ.get('DC_HOST','127.0.0.1') in ('127.0.0.1','localhost','::1') and
            os.environ.get('DC_ALLOW_DEMO_SIGNUP') == '1')


def send(config, email, link):
    if config['mode'] != 'smtp':
        raise DeliveryUnavailable('SMTP is not selected')
    message = EmailMessage()
    message['From'] = config['from']
    message['To'] = email
    message['Subject'] = 'Votre accès · Le Bus des Toutous by Plus de Fun'
    message.set_content('Votre lien personnel (valable 15 minutes, une seule utilisation) :\n\n'+link+
                        '\n\nSi vous n’avez pas demandé ce lien, ignorez ce message.\n\nLe Bus des Toutous · by Plus de Fun\n')
    context = ssl.create_default_context()
    try:
        if config['tls'] == 'ssl':
            with smtplib.SMTP_SSL(config['host'], config['port'], timeout=15, context=context) as smtp:
                smtp.login(config['user'], config['password'])
                if smtp.send_message(message):raise DeliveryUnavailable('recipient rejected')
        else:
            with smtplib.SMTP(config['host'], config['port'], timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(config['user'], config['password'])
                if smtp.send_message(message):raise DeliveryUnavailable('recipient rejected')
    except (OSError, smtplib.SMTPException) as error:
        # Never surface SMTP credentials, response text or usable links to clients.
        raise DeliveryUnavailable('login delivery failed') from error
