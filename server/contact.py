"""Separate WSGI contact endpoint. No RailSoftware imports or database."""
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

ORIGIN = 'https://ctl-software.io-goerlitz.eu'
TOPICS = {'Software', 'Rail Software', 'KI-Musik'}
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+\Z")
_SECRET = secrets.token_bytes(32)
_BUCKETS = {}
_LOCK = threading.Lock()


def ready():
    return (all(os.environ.get(k) for k in ('SMTP_HOST', 'SMTP_FROM'))
            and os.environ.get('SMTP_SECURITY') in ('ssl', 'starttls')
            and bool(EMAIL.fullmatch(os.environ.get('SMTP_FROM', ''))))


def allowed(ip):
    now = time.monotonic()
    key = hmac.new(_SECRET, ip.encode(), hashlib.sha256).hexdigest()
    with _LOCK:
        for k in list(_BUCKETS):
            _BUCKETS[k] = [t for t in _BUCKETS[k] if now - t < 3600]
            if not _BUCKETS[k]:
                del _BUCKETS[k]
        if len(_BUCKETS) >= 10000 or len(_BUCKETS.get(key, [])) >= 5:
            return False
        if sum(map(len, _BUCKETS.values())) >= 100:
            return False
        _BUCKETS.setdefault(key, []).append(now)
        return True


def send(data):
    msg = EmailMessage()
    msg['From'] = os.environ['SMTP_FROM']
    msg['To'] = 'omueller369@gmail.com'
    msg['Reply-To'] = data['email']
    msg['Subject'] = 'Website-Anfrage: ' + data['topic']
    msg.set_content('Name: ' + data['name'] + '\nE-Mail: ' + data['email']
                    + '\nThema: ' + data['topic'] + '\n\n' + data['message'])
    security = os.environ['SMTP_SECURITY']
    port = int(os.environ.get('SMTP_PORT', '465' if security == 'ssl' else '587'))
    context = ssl.create_default_context()
    cls = smtplib.SMTP_SSL if security == 'ssl' else smtplib.SMTP
    kwargs = {'context': context} if security == 'ssl' else {}
    with cls(os.environ['SMTP_HOST'], port, timeout=10, **kwargs) as smtp:
        if security == 'starttls':
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        if os.environ.get('SMTP_USERNAME'):
            smtp.login(os.environ['SMTP_USERNAME'], os.environ.get('SMTP_PASSWORD', ''))
        refused = smtp.send_message(msg)
        if refused:
            raise smtplib.SMTPException('Recipient refused')


def application(env, start_response):
    def reply(code, message, **extra):
        body = json.dumps({'message': message, **extra}, ensure_ascii=False).encode()
        labels = {200:'OK', 400:'Bad Request', 403:'Forbidden', 404:'Not Found',
                  405:'Method Not Allowed', 413:'Content Too Large',
                  415:'Unsupported Media Type', 429:'Too Many Requests', 503:'Service Unavailable'}
        headers = [('Content-Type', 'application/json; charset=utf-8'),
                   ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'),
                   ('X-Content-Type-Options', 'nosniff')]
        if code == 429:
            headers.append(('Retry-After', '3600'))
        if code == 405:
            headers.append(('Allow', 'GET, POST'))
        start_response(str(code) + ' ' + labels[code], headers)
        return [body]
    if env.get('PATH_INFO') != '/website-contact':
        return reply(404, 'Nicht gefunden.')
    method = env.get('REQUEST_METHOD', '')
    if method == 'GET':
        return reply(200, 'Formularstatus', available=bool(ready()))
    if method != 'POST':
        return reply(405, 'Methode nicht erlaubt.')
    if env.get('HTTP_ORIGIN') != ORIGIN:
        return reply(403, 'Diese Anfrage ist nicht erlaubt.')
    if not ready():
        return reply(503, 'Der Formularversand ist noch nicht eingerichtet. Bitte kontaktieren Sie mich per E-Mail.')
    if env.get('CONTENT_TYPE', '').split(';')[0].strip() != 'application/json':
        return reply(415, 'JSON erforderlich.')
    try:
        length = int(env.get('CONTENT_LENGTH', '0'))
    except ValueError:
        return reply(400, 'Ungültige Anfrage.')
    if length <= 0 or length > 32768:
        return reply(413, 'Nachricht zu groß oder leer.')
    # Apache overwrites this header using the real connection IP. Never trust a client-provided forwarded header.
    ip = env.get('HTTP_X_WEBSITE_IP', env.get('REMOTE_ADDR', 'unknown'))
    if not allowed(ip):
        return reply(429, 'Zu viele Anfragen. Bitte versuchen Sie es in einer Stunde erneut oder nutzen Sie E-Mail.')
    try:
        data = json.loads(env['wsgi.input'].read(length))
        if not isinstance(data, dict) or any(not isinstance(v, str) for v in data.values()):
            raise ValueError()
        data = {k:v.strip() for k,v in data.items()}
        if data.get('website'):
            raise ValueError()
        if not 1 <= len(data.get('name', '')) <= 120 or any(c in data['name'] for c in '\r\n\x00'):
            raise ValueError()
        if not 3 <= len(data.get('email', '')) <= 254 or not EMAIL.fullmatch(data['email']):
            raise ValueError()
        if data.get('topic') not in TOPICS or not 10 <= len(data.get('message', '')) <= 5000:
            raise ValueError()
        if '\x00' in data['message']:
            raise ValueError()
    except (ValueError, KeyError, UnicodeDecodeError):
        return reply(400, 'Bitte prüfen Sie Name, E-Mail, Thema und Nachricht (10 bis 5000 Zeichen).')
    try:
        send(data)
    except Exception:
        # No request data, credentials or SMTP exception details in responses/logs.
        return reply(503, 'Keine Versandbestätigung erhalten. Bitte versuchen Sie es später oder nutzen Sie E-Mail.')
    return reply(200, 'Ihre Anfrage wurde an den E-Mail-Dienst übergeben. Vielen Dank!')
