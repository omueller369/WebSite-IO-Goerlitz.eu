"""Server-only customer download area, independent of RailSoftware and mail accounts."""
import hashlib
import hmac
from html import escape as e
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import parse_qs, urlsplit
import urllib.request

ADMIN = 'omueller369@gmail.com'
ORIGIN = 'https://ctl-software.io-goerlitz.eu'
DEFAULT_URL = 'https://github.com/omueller369/RailSoftware/releases/download/android-test-22/LokZeitleiste-TF-Portal.apk'
DEFAULT_LABEL = 'TF Portal Android 0.26.52 Test 22 (Testversion)'
COOKIE = '__Host-io-downloads'
LOGIN_COOKIE = '__Host-io-download-login'
LOCK = threading.Lock()
RELEASE_LOCK = threading.Lock()
READY = False
DB = None


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1, maxmem=64*1024*1024).hex()
    return 'scrypt$' + salt + '$' + digest


def password_ok(password, encoded):
    try:
        scheme, salt, expected = encoded.split('$')
        if scheme != 'scrypt' or len(salt) != 32 or len(expected) != 128:
            return False
        actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1, maxmem=64*1024*1024).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def valid_password(value):
    return 12 <= len(value) <= 256 and not any(c in value for c in '\x00\r\n')


def email(value):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', value):
        raise ValueError('Bitte eine gültige E-Mail-Adresse eingeben.')
    return value


def connection():
    global READY, DB
    location = os.environ.get('PORTAL_DB') or str(Path(os.environ.get('STATE_DIRECTORY', '/var/lib/io-website-downloads'))/'downloads.sqlite3')
    with LOCK:
        if not READY or DB != location:
            Path(location).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with sqlite3.connect(location, timeout=20) as db:
                db.executescript('''
                CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                  password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','customer')), active INTEGER NOT NULL DEFAULT 1,
                  must_change INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, last_login INTEGER);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, csrf TEXT NOT NULL, expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (key TEXT NOT NULL, at INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS attempts_time ON attempts(at);
                ''')
                credential = Path(os.environ['PORTAL_ADMIN_FILE']).read_text()
                admin = json.loads(credential)
                if admin['email'] != ADMIN or not re.fullmatch(r'scrypt\$[a-f0-9]{32}\$[a-f0-9]{128}', admin['password']):
                    raise ValueError('Ungültige Admin-Konfiguration.')
                row = db.execute('SELECT id,password,role FROM users WHERE email=?', (ADMIN,)).fetchone()
                if row:
                    if row[2] != 'admin':
                        raise ValueError('Admin-Identität ist nicht eindeutig.')
                    if row[1] != admin['password']:
                        db.execute('UPDATE users SET password=?,active=1,must_change=0 WHERE id=?', (admin['password'],row[0]))
                        db.execute('DELETE FROM sessions WHERE user_id=?',(row[0],))
                else:
                    db.execute('INSERT INTO users(email,name,password,role,created) VALUES(?,?,?,?,?)', (ADMIN,'Oliver Müller',admin['password'],'admin',int(time.time())))
                for key, value in [('apk_url', DEFAULT_URL), ('apk_label', DEFAULT_LABEL), ('apk_mode','auto'), ('apk_checked','0'), ('apk_refresh_error','0'), ('rate_secret', secrets.token_hex(32))]:
                    db.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(key,value))
                db.execute('PRAGMA user_version=1')
            os.chmod(location,0o600)
            DB, READY = location, True
    db = sqlite3.connect(location,timeout=20)
    db.row_factory = sqlite3.Row
    return db


def cookies(env):
    parsed = SimpleCookie()
    try: parsed.load(env.get('HTTP_COOKIE',''))
    except Exception: return {}
    return {k:v.value for k,v in parsed.items()}


def cookie(name, value, max_age):
    return ('Set-Cookie',f'{name}={value}; Path=/; Max-Age={max_age}; Secure; HttpOnly; SameSite=Strict')


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def layout(title, body, user=None):
    links = '<a href="/download/">Downloads</a>'
    if user and user['role']=='admin': links += '<a href="/kundenverwaltung/">Kundenverwaltung</a>'
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      '<meta name="robots" content="noindex,nofollow"><title>'+e(title)+' · IO-Software-Görlitz</title>'
      '<link rel="stylesheet" href="/website-assets/site.css?v=0.2.2"></head><body class="portal-page"><header><a class="brand" href="/">IO-Software-Görlitz</a><nav>'+links+'</nav></header>'
      '<main id="inhalt"><section class="page-intro"><p class="eyebrow">GESCHÜTZTER KUNDENBEREICH</p><h1>'+e(title)+'</h1></section>'
      '<section class="section no-top portal-content">'+body+'</section></main><footer><a href="/">Startseite</a><a href="/datenschutz/">Datenschutz</a><a href="/kontakt/">Kontakt</a></footer></body></html>')


def csrf_valid(expected, actual):
    return bool(re.fullmatch('[a-f0-9]{64}',actual)) and hmac.compare_digest(expected,actual)


def hidden(csrf):
    return '<input type="hidden" name="csrf" value="'+e(csrf,quote=True)+'">'


def field(name, label, typ='text', value='', required=True, autocomplete='off'):
    limits = {'password':256,'confirm':256,'old':256,'email':254,'name':120,'url':2048,'label':180}
    return ('<label>'+e(label)+'<input name="'+name+'" type="'+typ+'" value="'+e(value,quote=True)+'" maxlength="'+str(limits.get(name,256))+'"'
      +(' required' if required else '')+' autocomplete="'+autocomplete+'"'+(' minlength="12"' if typ=='password' and name!='old' else '')+'></label>')


def form(action, csrf, content, label):
    return '<form class="contact-form portal-form" method="post" action="'+action+'">'+hidden(csrf)+content+'<button class="button" type="submit">'+e(label)+'</button></form>'


def logout(csrf):
    return form('/download/abmelden',csrf,'','Abmelden')


def settings(db):
    return dict(db.execute('SELECT key,value FROM settings'))


def android_release(db):
    config=settings(db)
    if config.get('apk_mode')!='auto':return config
    with RELEASE_LOCK:
        config=settings(db)
        if config.get('apk_mode')!='auto':return config
        if int(config.get('apk_checked','0'))>int(time.time())-3600:return config
        try:
            request=urllib.request.Request('https://api.github.com/repos/omueller369/RailSoftware/releases?per_page=20',headers={'User-Agent':'IO-Website-Downloads/0.2.0','Accept':'application/vnd.github+json'})
            with urllib.request.urlopen(request,timeout=5) as response:releases=json.loads(response.read(2_000_000))
            candidates=[]
            for release in releases:
                if release.get('draft') or not release.get('published_at'):continue
                assets=[a for a in release.get('assets',[]) if a.get('name','').lower().endswith('.apk') and a.get('browser_download_url','').startswith('https://github.com/omueller369/RailSoftware/releases/download/')]
                if assets:
                    assets.sort(key=lambda a:(a['name']!='LokZeitleiste-TF-Portal.apk',a['name']))
                    candidates.append((release,assets[0]))
            release,asset=max(candidates,key=lambda pair:pair[0]['published_at'])
            url=asset['browser_download_url']
            if not url.isascii() or any(c in url for c in '\r\n\x00') or len(url)>2048:raise ValueError()
            label=(release.get('name') or release['tag_name'])[:160]
            if release.get('prerelease') and 'test' not in label.lower():label+=' (Testversion)'
            db.execute('UPDATE settings SET value=? WHERE key=?',(url,'apk_url'))
            db.execute('UPDATE settings SET value=? WHERE key=?',(label,'apk_label'))
            db.execute("UPDATE settings SET value='0' WHERE key='apk_refresh_error'")
        except Exception:
            # Keep the last known link on upstream failure. No secrets or customer data sent.
            db.execute("UPDATE settings SET value='1' WHERE key='apk_refresh_error'")
        db.execute('UPDATE settings SET value=? WHERE key=?',(str(int(time.time())),'apk_checked'));db.commit()
        return settings(db)


def current_user(db,env):
    token=cookies(env).get(COOKIE,'')
    if not re.fullmatch('[a-f0-9]{64}',token):return None
    return db.execute('SELECT u.*,s.csrf,s.token FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1', (token_hash(token),int(time.time()))).fetchone()


def rate_allowed(db,env,address):
    now=int(time.time());secret=settings(db)['rate_secret'].encode()
    ip=env.get('HTTP_X_WEBSITE_IP',env.get('REMOTE_ADDR','unknown'))
    keys=[('ip:'+ip,20),('email:'+address,8),('global',200)]
    db.execute('BEGIN IMMEDIATE')
    db.execute('DELETE FROM attempts WHERE at<?',(now-900,))
    hashed=[(hmac.new(secret,k.encode(),hashlib.sha256).hexdigest(),limit) for k,limit in keys]
    allowed=all(db.execute('SELECT COUNT(*) FROM attempts WHERE key=?',(k,)).fetchone()[0]<limit for k,limit in hashed)
    if allowed:
        db.executemany('INSERT INTO attempts(key,at) VALUES(?,?)',[(k,now) for k,_ in hashed])
    db.commit()
    return allowed


def trusted_form_origin(env):
    # Never derive the allowed origin from attacker-controlled Host/Forwarded headers.
    def matches(value, referer=False):
        try:
            candidate=urlsplit(value)
            expected=urlsplit(ORIGIN)
            return (candidate.scheme==expected.scheme and candidate.hostname==expected.hostname
                    and (candidate.port or 443)==(expected.port or 443)
                    and not candidate.username and not candidate.password
                    and (referer or not (candidate.path or candidate.query or candidate.fragment)))
        except (ValueError,TypeError):
            return False
    if env.get('HTTP_SEC_FETCH_SITE') in ('cross-site','same-site'):return False
    origin=env.get('HTTP_ORIGIN')
    if origin:return matches(origin)  # Explicit null or foreign origins never fall back.
    referer=env.get('HTTP_REFERER')
    if referer:return matches(referer,referer=True)
    # Browser-controlled Fetch Metadata is a fallback; CSRF tokens are still mandatory.
    return env.get('HTTP_SEC_FETCH_SITE')=='same-origin'


def application(env,start_response):
    def reply(status,body='',headers=(),title=None,user=None):
        if title:body=layout(title,body,user)
        encoded=body.encode()
        base=[('Content-Type','text/html; charset=utf-8'),('Content-Length',str(len(encoded))),('Cache-Control','no-store, private'),
          ('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin'),('X-Frame-Options','DENY'),('X-Robots-Tag','noindex, nofollow'),
          ('Content-Security-Policy',"default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")]
        start_response(status,base+list(headers));return [encoded]
    def redirect(path,headers=()):return reply('303 See Other',headers=[('Location',path),*headers])
    path=env.get('PATH_INFO','').rstrip('/') or '/'
    if path in ('/download/index.html','/kundenverwaltung/index.html'):return redirect(path.rsplit('/',1)[0]+'/')
    known={'/download','/download/anmelden','/download/abmelden','/download/passwort','/download/android','/download/health','/kundenverwaltung','/kundenverwaltung/kunde','/kundenverwaltung/status','/kundenverwaltung/passwort','/kundenverwaltung/android','/kundenverwaltung/aktualisieren'}
    if path not in known:return reply('404 Not Found','Nicht gefunden.')
    method=env.get('REQUEST_METHOD','GET')
    if method not in ('GET','POST'):return reply('405 Method Not Allowed','Methode nicht erlaubt.',[('Allow','GET, POST')])
    try:
        db=connection()
    except Exception:
        return reply('503 Service Unavailable','Der Downloadbereich wird eingerichtet. Bitte später erneut versuchen.')
    try:
        now=int(time.time())
        db.execute('DELETE FROM sessions WHERE expires<=?',(now,));db.commit()
        if path=='/download/health':return reply('200 OK','Bereit.')
        user=current_user(db,env)
        data={}
        if method=='POST':
            if not trusted_form_origin(env):return reply('403 Forbidden','Ungültiger Ursprung.')
            try:
                length=int(env.get('CONTENT_LENGTH','0'))
                if not 0<length<=16384:raise ValueError()
                if env.get('CONTENT_TYPE','').split(';')[0]!='application/x-www-form-urlencoded':raise ValueError()
                values=parse_qs(env['wsgi.input'].read(length).decode(),keep_blank_values=True,max_num_fields=20)
                if any(len(v)!=1 for v in values.values()):raise ValueError()
                data={k:v[0] for k,v in values.items()}
            except (ValueError,UnicodeError):return reply('400 Bad Request','Ungültiges Formular.')
        if path=='/download/anmelden' and method=='POST':
            challenge=cookies(env).get(LOGIN_COOKIE,'')
            if not re.fullmatch('[a-f0-9]{64}',challenge) or not csrf_valid(challenge,data.get('csrf','')):
                return reply('403 Forbidden','Formular abgelaufen. Bitte die Anmeldung neu öffnen.')
            address=data.get('email','').strip().lower()[:254]
            if not rate_allowed(db,env,address):return reply('429 Too Many Requests','Zu viele Anmeldeversuche. Bitte nach 15 Minuten erneut versuchen.',[('Retry-After','900')])
            found=db.execute('SELECT * FROM users WHERE email=?',(address,)).fetchone()
            encoded=found['password'] if found else 'scrypt$'+'0'*32+'$'+'0'*128
            good=password_ok(data.get('password','')[:256],encoded) and len(data.get('password',''))<=256
            if not good or not found or not found['active']:
                return reply('401 Unauthorized','<p>E-Mail-Adresse oder Passwort ungültig, oder Zugang nicht freigeschaltet.</p><a href="/download/">Zur Anmeldung</a>',title='Anmeldung nicht möglich')
            token=secrets.token_hex(32)
            # Rotate on login; the incoming session is never reused.
            prior=cookies(env).get(COOKIE,'')
            db.execute('DELETE FROM sessions WHERE token=?',(token_hash(prior),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token_hash(token),found['id'],secrets.token_hex(32),now+8*3600))
            db.execute('UPDATE users SET last_login=? WHERE id=?',(now,found['id']));db.commit()
            return redirect('/download/passwort' if found['must_change'] else '/download/',[cookie(COOKIE,token,8*3600),cookie(LOGIN_COOKIE,'',0)])
        if not user:
            if path!='/download' or method!='GET':return redirect('/download/')
            challenge=secrets.token_hex(32)
            content=('<p>Nur für persönlich freigeschaltete Kunden. Zugang erhalten Sie nach Anfrage bei IO-Software-Görlitz.</p>'
              +form('/download/anmelden',challenge,field('email','E-Mail','email',autocomplete='username')+field('password','Passwort','password',autocomplete='current-password'),'Anmelden')
              +'<p><a href="/kontakt/?thema=rail">Zugang anfragen</a></p>')
            return reply('200 OK',content,[cookie(LOGIN_COOKIE,challenge,900)],title='Download')
        if method=='POST' and not csrf_valid(user['csrf'],data.get('csrf','')):return reply('403 Forbidden','Ungültiges Formular.')
        if path=='/download/abmelden' and method=='POST':
            db.execute('DELETE FROM sessions WHERE token=?',(user['token'],));db.commit()
            return redirect('/download/',[cookie(COOKIE,'',0)])
        if user['must_change'] and path!='/download/passwort':return redirect('/download/passwort')
        if path.startswith('/kundenverwaltung') and (user['role']!='admin' or user['email']!=ADMIN):return reply('403 Forbidden','Dieser Bereich ist ausschließlich dem Administrator vorbehalten.')
        if path=='/download/passwort':
            if method=='POST':
                if not password_ok(data.get('old',''),user['password']):raise ValueError('Das aktuelle Passwort stimmt nicht.')
                new=data.get('password','')
                if not valid_password(new) or new!=data.get('confirm'):raise ValueError('Neue Passwörter müssen übereinstimmen und 12 bis 256 Zeichen lang sein.')
                if password_ok(new,user['password']):raise ValueError('Bitte ein anderes Passwort als das bisherige wählen.')
                if user['role']=='admin':raise ValueError('Das Admin-Passwort wird über sudo io-website admin-password geändert.')
                db.execute('UPDATE users SET password=?,must_change=0 WHERE id=?',(password_hash(new),user['id']))
                db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],));db.commit()
                return redirect('/download/',[cookie(COOKIE,'',0)])
            body='<p>Ändern Sie vor dem ersten Download Ihr Startpasswort. Danach melden Sie sich mit dem neuen Passwort an.</p>'+form('/download/passwort',user['csrf'],field('old','Aktuelles Passwort','password',autocomplete='current-password')+field('password','Neues Passwort','password',autocomplete='new-password')+field('confirm','Neues Passwort wiederholen','password',autocomplete='new-password'),'Passwort ändern')+logout(user['csrf'])
            return reply('200 OK',body,title='Passwort ändern',user=user)
        if path=='/download/android' and method=='GET':
            return redirect(android_release(db)['apk_url'])
        if path=='/download' and method=='GET':
            config=android_release(db)
            body='<p>Angemeldet als '+e(user['email'])+'</p><article class="boxed"><h2>Aktuelle Android-Version</h2><p>'+e(config['apk_label'])+'</p><a class="button" href="/download/android">Android-Datei herunterladen ↗</a><p>Die Installation muss auf dem Android-Gerät bestätigt werden. Testversionen sind entsprechend gekennzeichnet.</p></article>'
            if user['role']=='admin':body+='<p><a class="button" href="/kundenverwaltung/">Kunden freischalten und Download verwalten</a></p>'
            else:body+='<p><a href="/download/passwort">Eigenes Passwort ändern</a></p>'
            body+=logout(user['csrf'])
            return reply('200 OK',body,title='Download',user=user)
        if path.startswith('/kundenverwaltung') and method=='POST':
            if path=='/kundenverwaltung/kunde':
                address=email(data.get('email',''));name=data.get('name','').strip()
                if not 1<=len(name)<=120 or address==ADMIN:raise ValueError('Bitte einen Kundennamen und eine andere E-Mail-Adresse angeben.')
                password=data.get('password','')
                if not valid_password(password) or password!=data.get('confirm'):raise ValueError('Startpasswörter müssen übereinstimmen und mindestens zwölf Zeichen lang sein.')
                db.execute('INSERT INTO users(email,name,password,role,must_change,created) VALUES(?,?,?,?,1,?)',(address,name,password_hash(password),'customer',now))
            elif path in ('/kundenverwaltung/status','/kundenverwaltung/passwort'):
                target=db.execute("SELECT id FROM users WHERE id=? AND role='customer'",(data.get('id',''),)).fetchone()
                if not target:raise ValueError('Kundenkonto nicht gefunden.')
                if path.endswith('/status'):
                    if data.get('active') not in ('0','1'):raise ValueError('Ungültiger Status.')
                    db.execute('UPDATE users SET active=? WHERE id=?',(int(data['active']),target['id']))
                else:
                    password=data.get('password','')
                    if not valid_password(password) or password!=data.get('confirm'):raise ValueError('Startpasswörter müssen übereinstimmen und mindestens zwölf Zeichen lang sein.')
                    db.execute('UPDATE users SET password=?,must_change=1 WHERE id=?',(password_hash(password),target['id']))
                db.execute('DELETE FROM sessions WHERE user_id=?',(target['id'],))
            elif path=='/kundenverwaltung/android':
                url=data.get('url','').strip();label=data.get('label','').strip();parsed=urlsplit(url)
                if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or len(url)>2048 or not url.isascii() or any(c in url for c in '\r\n\x00') or not 1<=len(label)<=180:
                    raise ValueError('Bitte eine HTTPS-Downloadadresse und Versionsbezeichnung eingeben.')
                with RELEASE_LOCK:
                    db.execute('UPDATE settings SET value=? WHERE key=?',(url,'apk_url'));db.execute('UPDATE settings SET value=? WHERE key=?',(label,'apk_label'))
                    db.execute("UPDATE settings SET value='manual' WHERE key='apk_mode'");db.commit()
            elif path=='/kundenverwaltung/aktualisieren':
                with RELEASE_LOCK:
                    db.execute("UPDATE settings SET value='auto' WHERE key='apk_mode'")
                    db.execute("UPDATE settings SET value='0' WHERE key='apk_checked'");db.commit()
            else:return reply('404 Not Found','Nicht gefunden.')
            db.commit();return redirect('/kundenverwaltung/')
        if path=='/kundenverwaltung' and method=='GET':
            csrf=user['csrf'];config=android_release(db)
            body='<p>Administrator: '+e(ADMIN)+'. Kundenkonten sind unabhängig von TF-Konten und E-Mail-Postfächern.</p><h2>Neuen Kunden freischalten</h2>'
            body+=form('/kundenverwaltung/kunde',csrf,field('name','Kundenname')+field('email','E-Mail','email',autocomplete='off')+field('password','Startpasswort','password',autocomplete='new-password')+field('confirm','Startpasswort wiederholen','password',autocomplete='new-password'),'Konto anlegen und freischalten')
            body+='<p>Übermitteln Sie das Startpasswort persönlich über einen geeigneten getrennten Kanal. Es wird keine automatische E-Mail verschickt. Der Kunde muss es vor dem Download ändern.</p><h2>Freigaben verwalten</h2>'
            customers=db.execute("SELECT id,email,name,active,must_change FROM users WHERE role='customer' ORDER BY email").fetchall()
            if not customers:body+='<p>Noch keine Kunden angelegt.</p>'
            for customer in customers:
                identifier='<input type="hidden" name="id" value="'+str(customer['id'])+'">'
                body+='<article class="boxed portal-customer"><h3>'+e(customer['name'])+'</h3><p>'+e(customer['email'])+' · '+('Freigeschaltet' if customer['active'] else 'Gesperrt')+(' · Passwortwechsel ausstehend' if customer['must_change'] else '')+'</p>'
                body+=form('/kundenverwaltung/status',csrf,identifier+'<input type="hidden" name="active" value="'+('0' if customer['active'] else '1')+'">','Sperren' if customer['active'] else 'Freischalten')
                body+='<details><summary>Startpasswort zurücksetzen</summary>'+form('/kundenverwaltung/passwort',csrf,identifier+field('password','Neues Startpasswort','password',autocomplete='new-password')+field('confirm','Wiederholen','password',autocomplete='new-password'),'Passwort zurücksetzen')+'</details></article>'
            body+='<h2>Android-Version aktualisieren</h2><p>Modus: '+('Automatisch aus GitHub (stündliche Prüfung)' if config.get('apk_mode')=='auto' else 'Manuell festgelegt')+'</p>'+form('/kundenverwaltung/aktualisieren',csrf,'','Aktuellen Link aus GitHub übernehmen und Automatik aktivieren')+form('/kundenverwaltung/android',csrf,field('label','Versionsbezeichnung',value=config['apk_label'])+field('url','HTTPS-Downloadlink','url',config['apk_url']),'Download speichern')
            if config.get('apk_mode')=='auto' and config.get('apk_refresh_error')=='1':body+='<p>Die letzte GitHub-Prüfung war nicht erfolgreich. Der bisherige Link bleibt aktiv; Sie können die Prüfung oben erneut starten.</p>'
            body+='<p>Der Link wird erst nach Anmeldung angezeigt. Eine bereits öffentliche GitHub-Datei bleibt unabhängig davon öffentlich verfügbar.</p>'+logout(csrf)
            return reply('200 OK',body,title='Kundenverwaltung',user=user)
        return reply('405 Method Not Allowed','Methode nicht erlaubt.')
    except sqlite3.IntegrityError:
        db.rollback();return reply('400 Bad Request','<p>Diese E-Mail-Adresse ist bereits vergeben.</p><a href="/kundenverwaltung/">Zurück</a>',title='Eingabe prüfen')
    except ValueError as error:
        db.rollback();return reply('400 Bad Request','<p>'+e(str(error))+'</p><a href="/download/">Zum Downloadbereich</a>',title='Eingabe prüfen',user=user)
    except Exception:
        db.rollback();return reply('503 Service Unavailable','Der Bereich ist vorübergehend nicht erreichbar. Bitte später erneut versuchen.')
    finally:
        db.close()
