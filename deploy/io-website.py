#!/usr/bin/env python3
"""IO Website installer/updater for the existing RailSoftware Ubuntu mail/Apache host.
Never runs RailSoftware setup.sh. No database, DNS, firewall or TLS replacements.
"""
import argparse
import fcntl
import getpass
import grp
import imaplib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import smtplib
import socket
import ssl
from email.message import EmailMessage
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from contextlib import contextmanager

VERSION = '0.1.1'
REPO = 'https://github.com/omueller369/WebSite-IO-Goerlitz.eu.git'
HOST = 'ctl-software.io-goerlitz.eu'
DOMAIN = 'io-goerlitz.eu'
ADDRESS = 'info@' + DOMAIN
IP = '212.227.86.251'
ETC = Path('/etc/io-website')
STATE = Path('/var/lib/io-website')
WEB = Path('/var/www/rail-website')
SERVICE = Path('/opt/io-website-contact')
VHOST = Path('/etc/apache2/sites-available/ctlsoftware-test.conf')
MARKER = '# IO-WEBSITE managed include v1'
PAGES = ('leistungen', 'unternehmen', 'entwicklung', 'ki-musik', 'kontakt', 'impressum',
         'datenschutz', 'entwicklung/rail-software', 'entwicklung/rail-software/demo-download')
PROTECTED = ('/tf', '/admin', '/api/v1/me/months/2026/1/summary', '/health', '/webmailer', '/phpmyadmin')

class Stop(RuntimeError):
    pass


def run(args, *, secret=False, input=None):
    result = subprocess.run([str(a) for a in args], input=input, text=True,
                            capture_output=True, timeout=180)
    if result.returncode:
        # Neither commands nor process output are printed for operations containing secrets.
        detail = '' if secret else '\n' + result.stderr[-1500:]
        raise Stop('Befehl fehlgeschlagen: ' + str(args[0]) + detail)
    return result.stdout.strip()


def safe_path(path):
    path = Path(path)
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise Stop('Symlink als Verwaltungsziel abgelehnt: ' + str(parent))
    return path


def atomic(path, content, mode=0o644, gid=0):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.io-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.chown(tmp, 0, gid)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def locked(path):
    with open(path, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def read(path):
    return Path(path).read_text()


def merge_map(text, key, value, replace=False):
    lines = text.splitlines()
    matches = [i for i, line in enumerate(lines) if line.split()[:1] == [key]]
    if len(matches) > 1:
        raise Stop('Mehrdeutiger Tabelleneintrag: ' + key)
    if matches:
        i = matches[0]
        if lines[i].split(None, 1)[1] == value:
            return text
        if not replace:
            raise Stop('Bestehender Eintrag wird nicht überschrieben: ' + key)
        lines[i] = key + ' ' + value
    else:
        lines.append(key + ' ' + value)
    return '\n'.join(lines) + '\n'


def merge_user(text, hashed, uid, gid, reset=False):
    prefix = ADDRESS + ':'
    lines = text.splitlines()
    found = [x for x in lines if x.startswith(prefix)]
    if len(found) > 1 or (found and not reset):
        raise Stop('Postfach existiert bereits; keine automatische Passwortänderung.')
    lines = [x for x in lines if not x.startswith(prefix)]
    lines.append(f'{ADDRESS}:{{SHA512-CRYPT}}{hashed}:{uid}:{gid}::/var/vmail/{DOMAIN}/info::')
    return '\n'.join(lines) + '\n'


def insert_include(text):
    # Modify only the one existing TLS vhost for the exact host, before proxy rules.
    blocks = list(re.finditer(r'<VirtualHost\s+[^>]+>.*?</VirtualHost>', text, re.S | re.I))
    matches = [m for m in blocks if re.search(r'<VirtualHost\s+[^>]*:443\s*>', m[0], re.I)
               and re.search(r'^\s*ServerName\s+' + re.escape(HOST) + r'\s*$', m[0], re.M)]
    if len(matches) != 1:
        raise Stop('Genau ein passender HTTPS-VirtualHost erwartet. --vhost prüfen.')
    m = matches[0]
    include = 'Include /etc/io-website/apache.conf'
    if include in m[0]:
        return text
    if MARKER in text or include in text:
        raise Stop('Vorhandene Website-Einbindung ist mehrdeutig.')
    pos = m.start() + m[0].index('>') + 1
    return text[:pos] + '\n' + MARKER + '\n' + include + '\n' + text[pos:]


def check_sieve(text):
    # Accept the repository's explicit envelope-recipient forwarding only.
    pattern = (r'\s*require\s+\["envelope"\];\s*if\s+envelope\s+:is\s+"to"\s*'
               r'\[(?P<recipients>[^\]]+)\]\s*\{\s*redirect\s+"[^"\n]+";\s*\}\s*keep;\s*')
    match = re.fullmatch(pattern, text)
    if not match:
        raise Stop('Unbekannte globale Sieve-Regel. Weiterleitung vorab prüfen; keine Änderung.')
    addresses = re.findall(r'"([^"\n]+)"', match['recipients'])
    if not addresses or any('*' in x or '?' in x for x in addresses) or ADDRESS in addresses:
        raise Stop('Die Sieve-Regel könnte das neue Postfach weiterleiten. Vorab korrigieren.')


def preflight(vhost):
    if os.geteuid() != 0:
        raise Stop('Bitte mit sudo/root auf dem Zielserver ausführen.')
    for command in ('git', 'curl', 'apache2ctl', 'systemctl', 'postconf', 'postmap', 'postfix',
                    'doveconf', 'dovecot', 'openssl', 'opendkim', 'opendkim-genkey', 'dig'):
        if not shutil.which(command):
            raise Stop('Benötigter vorhandener Serverdienst/Befehl fehlt: ' + command)
    if not run(['dovecot', '--version']).startswith('2.4.'):
        raise Stop('Dieses Script erwartet Dovecot 2.4 aus dem RailSoftware-Serverstand.')
    for path in (vhost, '/etc/dovecot/ctl-users', '/etc/postfix/ctl-domains',
                 '/etc/postfix/ctl-mailboxes', '/etc/opendkim/ctl-keys', '/etc/opendkim/ctl-signing'):
        if not safe_path(path).is_file():
            raise Stop('Erwartete Serverdatei fehlt: ' + str(path))
    if not re.search(r'passwd_file_path\s*=\s*/etc/dovecot/ctl-users', read('/etc/dovecot/dovecot.conf')):
        raise Stop('Unerwartete Dovecot-Kontoverwaltung.')
    check_sieve(read('/etc/dovecot/sieve/ctl-forward.sieve'))
    for key, source in [('virtual_mailbox_domains','ctl-domains'), ('virtual_mailbox_maps','ctl-mailboxes')]:
        current = run(['postconf','-h',key])
        allowed = {'hash:/etc/postfix/' + source, 'hash:/etc/postfix/io-website-' + source[4:]}
        parts = set(filter(None, re.split(r'[\s,]+',current)))
        if not parts or not parts <= allowed or 'hash:/etc/postfix/' + source not in parts:
            raise Stop('Unerwartete Postfix-Tabelle: ' + key)
    for setting in ('always_bcc','sender_bcc_maps','recipient_bcc_maps'):
        if run(['postconf','-h',setting]):
            raise Stop('Globale Mailkopie/BCC-Konfiguration erkannt: '+setting+'; vorab prüfen.')
    if run(['postconf','-h','virtual_transport']) != 'lmtp:unix:private/dovecot-lmtp':
        raise Stop('Unerwarteter virtueller Mailtransport.')
    for service in ('apache2','postfix','dovecot','opendkim','postsrsd'):
        if run(['systemctl','is-active',service]) != 'active':
            raise Stop('Vorhandener Dienst nicht aktiv: ' + service)
    insert_include(read(vhost))
    pwd.getpwnam('ctlvmail')
    run(['apache2ctl','configtest'])
    run(['postfix','check'])
    run(['doveconf','-n'])


def password_prompt():
    if not sys.stdin.isatty():
        raise Stop('Für die verdeckte Passwortabfrage ein Terminal verwenden (kein Pipe-Aufruf).')
    first = getpass.getpass('Neues Passwort für ' + ADDRESS + ' (mindestens 12 Zeichen): ')
    second = getpass.getpass('Passwort wiederholen: ')
    if first != second or len(first) < 12 or any(c in first for c in '\r\n\x00'):
        raise Stop('Passwörter stimmen nicht überein oder erfüllen die Vorgabe nicht.')
    return first


def dkim_key():
    directory = safe_path('/etc/opendkim/keys/' + DOMAIN)
    private = directory/'io.private'
    if not private.exists():
        directory.mkdir(parents=True, exist_ok=True)
        run(['opendkim-genkey','-D',directory,'-d',DOMAIN,'-s','io','-b','2048'])
    account = pwd.getpwnam('opendkim')
    os.chown(directory,account.pw_uid,account.pw_gid);directory.chmod(0o750)
    for f in directory.iterdir():
        safe_path(f);os.chown(f,account.pw_uid,account.pw_gid);f.chmod(0o600)
    public = ''.join(re.findall(r'"([^"]*)"',read(directory/'io.txt')))
    if not re.search(r'p=[A-Za-z0-9+/=]+',public):
        raise Stop('DKIM-Schlüssel kann nicht gelesen werden.')
    return public


def dns_records(public, ip):
    return (f'MX @ 10 {HOST}.\n'
            f'TXT @ v=spf1 ip4:{ip} -all\n'
            f'TXT io._domainkey {public}\n'
            f'TXT _dmarc v=DMARC1; p=none; rua=mailto:{ADDRESS}\n'
            f'Vorhandener Mailhost: A {HOST} -> {ip}; PTR {ip} -> {HOST}\n'
            'Bestehende SPF-/DMARC-Regeln zusammenführen, nicht blind ersetzen.\n'
            'STRATO-Nameserver behalten. Keine Änderung an der CTL-Subdomain/MX.\n')


def dns_check(public, ip):
    import shlex
    expected_p = re.search(r'p=([A-Za-z0-9+/=]+)', public)[1]
    errors=[]
    for resolver in ('1.1.1.1','8.8.8.8'):
        def query(name,kind):
            raw = run(['dig','@'+resolver,'+short','+time=5','+tries=1',name,kind])
            return raw.splitlines()
        if query(HOST,'AAAA'):
            errors.append(resolver+': AAAA am Mailhost erkannt; die dokumentierte Mailkonfiguration ist IPv4-only.')
        if ip not in query(HOST,'A'):
            errors.append(resolver+': A des bestehenden Mailhosts passt nicht.')
        mx=query(DOMAIN,'MX')
        if not mx or any(line.split()[-1].lower() != HOST+'.' for line in mx):
            errors.append(resolver+': MX der Hauptdomain fehlt oder zeigt auf einen anderen Anbieter.')
        def txt(name):
            return [''.join(shlex.split(line)) for line in query(name,'TXT')]
        spf=[x for x in txt(DOMAIN) if x.startswith('v=spf1')]
        if len(spf)!=1 or 'ip4:'+ip not in spf[0].split() or spf[0].split()[-1] not in ('-all','~all'):
            errors.append(resolver+': Genau ein SPF mit expliziter Server-IP erwartet.')
        dkim=[x for x in txt('io._domainkey.'+DOMAIN) if 'p=' in x]
        if not any(re.search(r'p=([A-Za-z0-9+/=]+)',x) and re.search(r'p=([A-Za-z0-9+/=]+)',x)[1]==expected_p for x in dkim):
            errors.append(resolver+': DKIM-Wert io._domainkey fehlt oder passt nicht.')
        dmarc=[x for x in txt('_dmarc.'+DOMAIN) if x.startswith('v=DMARC1;')]
        if len(dmarc)!=1 or not re.search(r'(?:;|^)\s*p=(none|quarantine|reject)(?:;|$)',dmarc[0]):
            errors.append(resolver+': DMARC fehlt oder ist mehrdeutig.')
        reverse=run(['dig','@'+resolver,'+short','+time=5','+tries=1','-x',ip]).splitlines()
        if HOST+'.' not in reverse:errors.append(resolver+': PTR passt nicht.')
    if errors:
        raise Stop('\n'.join(errors)+'\nDNS bei STRATO ergänzen, danach denselben install-Aufruf wiederholen.\nWerte: /etc/io-website/dns-required.txt')


class Transaction:
    """Rollback config bytes and ownership, not mailbox messages or generated keys."""
    def __init__(self):
        self.saved={}
        self.id=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
    def save(self,path):
        path=Path(path);safe_path(path)
        if path not in self.saved:
            stat=path.stat() if path.exists() else None
            self.saved[path]=(path.read_bytes() if stat else None,stat)
            if stat:
                target=STATE/'backups'/self.id/path.relative_to('/')
                target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                target.write_bytes(path.read_bytes());target.chmod(0o600)
    def write(self,path,text,mode=0o644,gid=0):
        path=Path(path)
        if path.exists() and path.read_text()==text and (path.stat().st_mode & 0o777)==mode and path.stat().st_gid==gid:
            return
        self.save(path);atomic(path,text,mode,gid)
    def restore(self):
        for path,(data,stat) in reversed(list(self.saved.items())):
            if data is None:
                path.unlink(missing_ok=True)
            else:
                atomic(path,data.decode(),stat.st_mode & 0o777,stat.st_gid)
                os.chown(path,stat.st_uid,stat.st_gid)


def map_paths():
    return [('virtual_mailbox_domains','domains'),('virtual_mailbox_maps','mailboxes')]


def sync_mail(tx):
    # Separate Postfix maps survive the CTL employee provisioner's table rewrites.
    for key,suffix in map_paths():
        current=run(['postconf','-h',key])
        table='hash:/etc/postfix/io-website-'+suffix
        if table not in re.split(r'[\s,]+',current):
            tx.save('/etc/postfix/main.cf')
            run(['postconf','-e',key+' = '+current+', '+table])
    original=read('/etc/opendkim.conf')
    for keyword,base in [('KeyTable','keys'),('SigningTable','signing')]:
        source='/etc/opendkim/ctl-'+base
        target='/etc/opendkim/io-website-'+base
        pattern=r'^\s*'+keyword+r'\s+([^\n]+)$'
        match=re.search(pattern,original,re.M)
        if not match or match[1].strip() not in ('refile:'+source,'refile:'+target):
            raise Stop('Unbekannte OpenDKIM-'+keyword+'; keine Ersetzung.')
        original=re.sub(pattern,keyword+' refile:'+target,original,flags=re.M)
        value=read(source)
        if base=='keys':
            value=merge_map(value,'io._domainkey.'+DOMAIN,DOMAIN+':io:/etc/opendkim/keys/'+DOMAIN+'/io.private')
        else:
            # Earlier wildcard rules could otherwise sign the new domain with a different key.
            value='*@'+DOMAIN+' io._domainkey.'+DOMAIN+'\n'+value
        tx.write(target,value,0o640,grp.getgrnam('opendkim').gr_gid)
    tx.write('/etc/opendkim.conf',original)
    # Exclude the added local domain from SRS rewriting; retain the existing SRS domain and secret.
    srs=read('/etc/postsrsd.conf')
    match=re.search(r'(?m)^\s*domains\s*=\s*\{([^}]*)\}',srs)
    if not match:raise Stop('Unbekannte PostSRSd-Domainkonfiguration.')
    values=re.findall(r'"([^"]+)"',match[1])
    if HOST not in values:
        raise Stop('Dokumentierte bestehende lokale SRS-Domain fehlt.')
    if DOMAIN not in values:
        values.append(DOMAIN)
        srs=srs[:match.start()]+'domains = { '+', '.join(json.dumps(x) for x in values)+' }'+srs[match.end():]
        tx.write('/etc/postsrsd.conf',srs)


def reload_mail():
    for suffix in ('domains','mailboxes'):
        run(['postmap','/etc/postfix/io-website-'+suffix])
    run(['postfix','check']);run(['doveconf','-n']);run(['opendkim','-n','-x','/etc/opendkim.conf'])
    run(['systemctl','reload','dovecot','postfix','opendkim'])
    # This service has no ExecReload in the documented CTL installation.
    run(['systemctl','restart','postsrsd'])


def mailbox_test(secret, deliver=False):
    try:
        with smtplib.SMTP(HOST,587,timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context());smtp.ehlo();smtp.login(ADDRESS,secret)
            token='IO-Website-Test-'+secrets.token_hex(12)
            if deliver:
                msg=EmailMessage();msg['From']=ADDRESS;msg['To']=ADDRESS;msg['Subject']=token
                msg.set_content('Lokaler Zustelltest der IO-Website-Installation. Keine Weiterleitung eingerichtet.')
                if smtp.send_message(msg):raise Stop('Lokaler Test wurde nicht angenommen.')
        with imaplib.IMAP4_SSL(HOST,993,ssl_context=ssl.create_default_context(),timeout=15) as imap:
            imap.login(ADDRESS,secret)
            if deliver:
                imap.select('INBOX')
                for _ in range(20):
                    code,found=imap.search(None,'HEADER','Subject',token)
                    if code=='OK' and found[0]:break
                    time.sleep(1);imap.noop()
                else:raise Stop('Testnachricht nicht im lokalen Postfach angekommen.')
                code,headers=imap.fetch(found[0].split()[-1], '(BODY.PEEK[HEADER.FIELDS (DKIM-Signature)])')
                value=b' '.join(x[1] for x in headers if isinstance(x,tuple))
                if code!='OK' or b'd='+DOMAIN.encode() not in value:
                    raise Stop('Lokale Testnachricht ohne erwartete DKIM-Domainsignatur.')
            imap.logout()
    except Stop:
        raise
    except Exception:
        raise Stop('Verschlüsselte SMTP-/IMAP-Prüfung fehlgeschlagen; keine Zugangsdaten ausgegeben.') from None


def create_mailbox(tx, reset=False):
    secret_file=ETC/'contact-password'
    users=read('/etc/dovecot/ctl-users')
    exists=any(x.startswith(ADDRESS+':') for x in users.splitlines())
    if exists and secret_file.exists() and not reset:
        mailbox_test(read(secret_file).rstrip('\n'))
        return
    if exists and not reset:
        raise Stop('Nicht vom Website-Script verwaltetes Postfach existiert. Keine Übernahme.')
    secret=password_prompt()
    hashed=run(['openssl','passwd','-6','-stdin'],input=secret+'\n',secret=True)
    if not hashed.startswith('$6$'):raise Stop('Passwort-Hash konnte nicht erzeugt werden.')
    identity=pwd.getpwnam('ctlvmail')
    for path in (Path('/var/vmail')/DOMAIN,Path('/var/vmail')/DOMAIN/'info',
                 Path('/var/vmail')/DOMAIN/'info/Maildir',
                 *[Path('/var/vmail')/DOMAIN/'info/Maildir'/x for x in ('cur','new','tmp')]):
        safe_path(path);path.mkdir(exist_ok=True);os.chown(path,identity.pw_uid,identity.pw_gid);path.chmod(0o700)
    tx.write('/etc/dovecot/ctl-users',merge_user(users,hashed,identity.pw_uid,identity.pw_gid,reset),0o640,grp.getgrnam('dovecot').gr_gid)
    tx.write(secret_file,secret+'\n',0o600)


def provision_mail():
    tx=Transaction()
    # Same lock as the existing RailSoftware provisioner: no lost user entries.
    with locked('/run/lock/ctl-mailboxes.lock'):
        try:
            if any(x.split()[:1]==[ADDRESS] for x in read('/etc/postfix/ctl-mailboxes').splitlines()):
                raise Stop('Postfach bereits in der CTL-Tabelle; keine doppelte Übernahme.')
            aliases=read('/etc/postfix/ctl-aliases')
            if any(x.split()[:1] in ([ADDRESS],['@'+DOMAIN]) for x in aliases.splitlines()):
                raise Stop('Bestehender Alias für '+ADDRESS+' erkannt.')
            if any(x.split()[:1]==[DOMAIN] for x in read('/etc/postfix/ctl-domains').splitlines()):
                raise Stop('Hauptdomain bereits durch CTL verwaltet. Keine zweite Domainverwaltung.')
            tx.write('/etc/postfix/io-website-domains',DOMAIN+' OK\n')
            tx.write('/etc/postfix/io-website-mailboxes',ADDRESS+' 1\n')
            sync_mail(tx)
            create_mailbox(tx)
            reload_mail()
            mailbox_test(read(ETC/'contact-password').rstrip('\n'), deliver=not (ETC/'mail-tested').exists())
            tx.write(ETC/'mail-tested','Lokale SMTP/IMAP-Zustellung mit DKIM geprüft.\n',0o600)
        except BaseException:
            tx.restore()
            for suffix in ('domains','mailboxes'):
                if Path('/etc/postfix/io-website-'+suffix).exists():run(['postmap','/etc/postfix/io-website-'+suffix])
                else:Path('/etc/postfix/io-website-'+suffix+'.db').unlink(missing_ok=True)
            subprocess.run(['systemctl','reload','dovecot','postfix','opendkim'],capture_output=True)
            subprocess.run(['systemctl','restart','postsrsd'],capture_output=True)
            raise
    # The CTL service regenerates its own DKIM tables. Merge them after each completed run.
    dropin=Path('/etc/systemd/system/ctl-mailboxes.service.d/io-website.conf')
    if Path('/etc/systemd/system/ctl-mailboxes.service').exists():
        atomic(dropin,'[Service]\nExecStartPost=/usr/local/sbin/io-website sync-mail\n')
        run(['systemctl','daemon-reload'])


def fetch_source(ref):
    if ref=='latest':
        request=urllib.request.Request('https://api.github.com/repos/omueller369/WebSite-IO-Goerlitz.eu/releases/latest',headers={'User-Agent':'IO-Website-Installer/'+VERSION})
        with urllib.request.urlopen(request,timeout=20) as response:ref=json.load(response)['tag_name']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/\-]{0,119}',ref) or '..' in ref:
        raise Stop('Ungültiger Git-Ref.')
    source=Path(tempfile.mkdtemp(prefix='io-source-',dir=STATE))
    try:
        run(['git','init',source]);run(['git','-C',source,'remote','add','origin',REPO])
        run(['git','-C',source,'fetch','--depth','1','origin',ref])
        run(['git','-C',source,'-c','core.hooksPath=/dev/null','checkout','--detach','FETCH_HEAD'])
        sha=run(['git','-C',source,'rev-parse','HEAD'])
        if not re.fullmatch('[a-f0-9]{40}',sha):raise Stop('Ungültiger Commit.')
        return source,sha
    except Exception:
        shutil.rmtree(source);raise


def validate_source(source):
    # No code from GitHub is executed as root. Static export is a verified file copy.
    required=['src/index.html','server/contact.py','server/io-website-contact.service',
              'docs/apache-website.conf.example','docs/apache-contact.conf.example','deploy/io-website.py','VERSION']
    for name in required:
        if not safe_path(source/name).is_file():raise Stop('Quelldatei fehlt: '+name)
    for folder in ('src','server','deploy'):
        for path in (source/folder).rglob('*'):
            safe_path(path)
            if path.is_file() and path.stat().st_size>5_000_000:raise Stop('Quelldatei unerwartet groß.')
            if folder=='src' and path.is_file() and path.suffix.lower() not in ('.html','.css','.js','.svg','.png','.jpg','.jpeg','.webp','.ico','.woff2','.json','.txt'):
                raise Stop('Nichtstatische Datei im Website-Export: '+path.name)
    version=read(source/'VERSION').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise Stop('Ungültige Website-Version.')
    for path in ('index.html', *[x+'/index.html' for x in PAGES]):
        text=read(source/'src'/path)
        if re.search(r'(?:href|src)=[\'"]/(?:tf|admin)(?:[/?\'\"])',text):
            raise Stop('Öffentlicher Portal-Link gefunden.')
    return version


def probe(path):
    # Curl preserves first-response redirect details and does not authenticate or mutate software data.
    raw=run(['curl','--silent','--show-error','--max-time','20','--resolve',HOST+':443:127.0.0.1','--noproxy',HOST,
             '--output','/dev/null','--write-out','%{http_code}|%{content_type}|%{redirect_url}',
             'https://'+HOST+path])
    if raw.startswith(('000|','502|','503|','504|')):raise Stop('Lokale HTTPS-Prüfung nicht erreichbar: '+path)
    return raw


def switch_link(target):
    WEB.mkdir(parents=True,exist_ok=True)
    current=WEB/'current';nextlink=WEB/'current.next'
    if current.exists() and not current.is_symlink():raise Stop('current ist kein Symlink.')
    nextlink.unlink(missing_ok=True)
    nextlink.symlink_to(target)
    os.replace(nextlink,current)


def service_config(source):
    # Runtime code is unprivileged. Password passed through systemd credentials, not env or argv.
    text=read(source/'server/io-website-contact.service')
    if 'LoadCredential=' not in text:raise Stop('Kontakt-Unit ohne Credential-Schutz abgelehnt.')
    return text


def website_logging(text):
    pattern=r'<VirtualHost\s+[^>]+>.*?</VirtualHost>'
    matches=[m for m in re.finditer(pattern,text,re.S|re.I)
             if re.search(r'<VirtualHost\s+[^>]*:443\s*>',m[0],re.I)
             and re.search(r'^\s*ServerName\s+'+re.escape(HOST)+r'\s*$',m[0],re.M)]
    if len(matches)!=1:raise Stop('Mehrdeutiger TLS-VirtualHost.')
    match=matches[0];block=match[0]
    logs=re.findall(r'(?m)^\s*CustomLog\s+([^\n]+)',block)
    if logs:
        for line in logs:
            if not re.fullmatch(r'\S+\s+\S+(?:\s+env=!io_website)?',line.strip()):
                raise Stop('Individuelle Apache-Logbedingungen zuerst manuell abstimmen.')
        block=re.sub(r'(?m)^(\s*CustomLog\s+\S+\s+\S+)(?:\s+env=!io_website)?\s*$',r'\1 env=!io_website',block)
        return text[:match.start()]+block+text[match.end():],''
    # Adding CustomLog disables inherited main-server logs. Preserve the known Ubuntu logger.
    global_logs=[]
    for path in [Path('/etc/apache2/apache2.conf'),*Path('/etc/apache2/conf-enabled').glob('*.conf')]:
        global_logs+=re.findall(r'(?m)^\s*CustomLog\s+([^\n]+)',path.read_text())
    expected='${APACHE_LOG_DIR}/other_vhosts_access.log vhost_combined'
    if global_logs != [expected]:
        raise Stop('Abweichende geerbte Apache-Logkonfiguration; vor Installation abstimmen.')
    return text,'\nCustomLog '+expected+' env=!io_website\n'


def publish(source,sha,vhost):
    version=validate_source(source)
    stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+sha[:12]
    release=WEB/'releases'/stamp
    safe_path(release);release.parent.mkdir(parents=True,exist_ok=True)
    WEB.chmod(0o755);release.parent.chmod(0o755)
    shutil.copytree(source/'src',release)
    for path in [release,*release.rglob('*')]:path.chmod(0o755 if path.is_dir() else 0o644)
    atomic(release/'release.json',json.dumps({'version':version,'commit':sha})+'\n')
    tx=Transaction()
    current=WEB/'current'
    old=os.readlink(current) if current.is_symlink() else None
    if current.exists() and old is None:raise Stop('Website-current ist ein Verzeichnis. Keine Ersetzung.')
    old_contact=subprocess.run(['systemctl','is-active','io-website-contact'],capture_output=True,text=True).stdout.strip()
    before={path:probe(path) for path in PROTECTED}
    if not (ETC/'state.json').exists():
        for path in PAGES:
            status=probe('/'+path).split('|')[0]
            if status not in ('404','307','308'):
                raise Stop('Mögliche bestehende Route /'+path+' ('+status+'). Vor Zuordnung prüfen.')
            if status in ('307','308') and not probe('/'+path+'/').startswith('404|'):
                raise Stop('Mögliche bestehende Route /'+path+'/ erkannt.')
    try:
        SERVICE.mkdir(parents=True,exist_ok=True);SERVICE.chmod(0o755)
        tx.write(SERVICE/'contact.py',read(source/'server/contact.py'))
        tx.write('/etc/systemd/system/io-website-contact.service',service_config(source))
        tx.write(ETC/'contact.env','SMTP_HOST='+HOST+'\nSMTP_PORT=587\nSMTP_SECURITY=starttls\nSMTP_FROM='+ADDRESS+'\nSMTP_USERNAME='+ADDRESS+'\n',0o600)
        # Dedicated log: 7 days, no query, referrer, user agent or form body.
        apache=read(source/'docs/apache-website.conf.example')+'\n'+read(source/'docs/apache-contact.conf.example')
        apache+='\nSetEnvIf Request_URI "^/(?:$|index\\.html$|website-assets/|website-contact$|'+ '|'.join(re.escape(x)+r'(?:/index\.html|/)?$' for x in PAGES)+')" io_website\n'
        apache+='CustomLog /var/log/apache2/io-website-access.log "%a %t %m %U %>s" env=io_website\n'
        patched,backend_log=website_logging(insert_include(read(vhost)))
        apache+=backend_log
        tx.write(ETC/'apache.conf',apache)
        tx.write(vhost,patched)
        tx.write('/etc/logrotate.d/io-website','/var/log/apache2/io-website-access.log {\n daily\n rotate 7\n maxage 7\n missingok\n notifempty\n compress\n delaycompress\n sharedscripts\n postrotate\n  /usr/sbin/apache2ctl graceful > /dev/null\n endscript\n}\n')
        run(['a2enmod','proxy','proxy_http','headers','setenvif'])
        run(['systemctl','daemon-reload']);run(['systemctl','enable','io-website-contact'])
        switch_link('releases/'+stamp)
        run(['apache2ctl','configtest'])
        run(['systemctl','restart','io-website-contact']);run(['systemctl','reload','apache2'])
        for _ in range(15):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8091/website-contact',timeout=2) as response:
                    if json.load(response).get('available'):break
            except Exception:pass
            time.sleep(1)
        else:raise Stop('Kontakt-Maildienst nicht bereit.')
        for path,expected in before.items():
            if probe(path)!=expected:raise Stop('Bestehende Software-Route verändert: '+path)
        for path in ('/', '/website-assets/site.css', '/kontakt/', '/impressum/', '/datenschutz/'):
            if not probe(path).startswith('200|'):raise Stop('Website-Pfad nicht erreichbar: '+path)
        with urllib.request.urlopen('http://127.0.0.1:8091/website-contact',timeout=3) as response:
            if not json.load(response).get('available'):raise Stop('Formular nicht bereit.')
        state={'version':version,'commit':sha,'current':'releases/'+stamp,'previous':old,'vhost':str(vhost)}
        # Keep runtime with each release for complete website/contact rollback.
        bundle=STATE/'release-runtime'/stamp;bundle.mkdir(parents=True)
        shutil.copy2(source/'server/contact.py',bundle/'contact.py')
        shutil.copy2(source/'server/io-website-contact.service',bundle/'service')
        shutil.copy2(ETC/'apache.conf',bundle/'apache.conf')
        atomic(ETC/'state.json',json.dumps(state,indent=2)+'\n',0o600)
        atomic('/usr/local/sbin/io-website',read(source/'deploy/io-website.py'),0o755)
    except BaseException:
        tx.restore()
        if old is not None:switch_link(old)
        else:current.unlink(missing_ok=True)
        subprocess.run(['systemctl','daemon-reload'],capture_output=True)
        if old_contact=='active':subprocess.run(['systemctl','restart','io-website-contact'],capture_output=True)
        else:subprocess.run(['systemctl','disable','--now','io-website-contact'],capture_output=True)
        subprocess.run(['apache2ctl','configtest'],capture_output=True)
        subprocess.run(['systemctl','reload','apache2'],capture_output=True)
        raise
    print('Online: https://'+HOST+'/ — Version '+version+' ('+sha[:12]+')')


def rollback():
    state=json.loads(read(ETC/'state.json'))
    previous=state.get('previous')
    if not previous:raise Stop('Kein vorheriges Website-Release gespeichert.')
    if not re.fullmatch(r'releases/[A-Za-z0-9-]+',previous):raise Stop('Ungültiger Rückweg.')
    bundle=STATE/'release-runtime'/Path(previous).name
    metadata=json.loads(read(WEB/previous/'release.json'))
    if not bundle.is_dir():raise Stop('Gesicherte Kontakt-Konfiguration fehlt.')
    tx=Transaction();old=state['current']
    try:
        tx.write(SERVICE/'contact.py',read(bundle/'contact.py'))
        tx.write('/etc/systemd/system/io-website-contact.service',read(bundle/'service'))
        tx.write(ETC/'apache.conf',read(bundle/'apache.conf'))
        switch_link(previous);run(['apache2ctl','configtest'])
        run(['systemctl','daemon-reload']);run(['systemctl','restart','io-website-contact']);run(['systemctl','reload','apache2'])
        if not probe('/').startswith('200|'):raise Stop('Rollback-Prüfung fehlgeschlagen.')
    except BaseException:
        tx.restore();switch_link(old)
        subprocess.run(['systemctl','daemon-reload'],capture_output=True)
        subprocess.run(['systemctl','restart','io-website-contact'],capture_output=True)
        subprocess.run(['systemctl','reload','apache2'],capture_output=True)
        raise
    state.update({'current':previous,'previous':old,**metadata})
    atomic(ETC/'state.json',json.dumps(state,indent=2)+'\n',0o600)
    print('Website und Kontaktcode zurückgesetzt; Postfach und Nachrichten unverändert.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','install','update','status','rollback','sync-mail','mail-password'])
    parser.add_argument('--ref',default='latest',help='Git-Tag/Commit/Branch; Standard: neuestes GitHub-Release')
    parser.add_argument('--vhost',type=Path,default=VHOST)
    parser.add_argument('--ipv4',default=IP,help='IPv4 des vorhandenen CTL-Mailservers')
    args=parser.parse_args()
    try:
        if ipaddress.ip_address(args.ipv4).version!=4:raise ValueError()
    except ValueError:
        raise Stop('Gültige IPv4-Adresse erforderlich.') from None
    if args.action=='plan':
        print('Version '+VERSION+'; Ziel: '+HOST+'; Postfach: '+ADDRESS+'\nVHost: '+str(args.vhost))
        print('GitHub -> getrennte Website-Releases; additive Postfix-/DKIM-Tabellen; Dovecot-Konto unter gemeinsamer Sperre.\nKeine Änderungen an Datenbank, DNS, Firewall, TLS oder RailSoftware-Dateien.')
        return
    if os.geteuid()!=0:raise Stop('sudo/root erforderlich.')
    os.umask(0o077)
    safe_path(ETC);safe_path(STATE)
    ETC.mkdir(exist_ok=True,mode=0o700);STATE.mkdir(exist_ok=True,mode=0o700)
    ETC.chmod(0o700);STATE.chmod(0o700)
    if args.action=='status':
        print(read(ETC/'state.json') if (ETC/'state.json').exists() else 'Noch kein Website-Release aktiv.')
        print('Website: https://'+HOST+'/; IMAP/SMTP-Konto: '+ADDRESS)
        for name in ('apache2','postfix','dovecot','opendkim','io-website-contact'):
            result=subprocess.run(['systemctl','is-active',name],capture_output=True,text=True)
            print(name+': '+result.stdout.strip())
        return
    with locked('/run/lock/io-website.lock'):
        if args.action=='rollback':rollback();return
        if args.action=='sync-mail':
            with locked('/run/lock/ctl-mailboxes.lock'):
                tx=Transaction()
                try:
                    sync_mail(tx)
                    if tx.saved:reload_mail()
                except BaseException:
                    tx.restore()
                    subprocess.run(['systemctl','reload','dovecot','postfix','opendkim'],capture_output=True)
                    subprocess.run(['systemctl','restart','postsrsd'],capture_output=True)
                    raise
            return
        preflight(args.vhost)
        if args.action=='mail-password':
            if not (ETC/'state.json').exists() or not (ETC/'contact-password').exists():
                raise Stop('Zuerst die eigene Website-/Postfachinstallation abschließen.')
            with locked('/run/lock/ctl-mailboxes.lock'):
                tx=Transaction()
                try:
                    create_mailbox(tx,reset=True);reload_mail()
                    mailbox_test(read(ETC/'contact-password').rstrip('\n'))
                    run(['systemctl','restart','io-website-contact'])
                except Exception:
                    tx.restore();subprocess.run(['systemctl','reload','dovecot'],capture_output=True)
                    subprocess.run(['systemctl','restart','io-website-contact'],capture_output=True)
                    raise
            print('Postfachpasswort und Formularzugang aktualisiert.');return
        if args.action=='update' and not (ETC/'state.json').exists():raise Stop('Zuerst install ausführen.')
        if args.action=='install':
            public=dkim_key();records=dns_records(public,args.ipv4)
            atomic(ETC/'dns-required.txt',records,0o600);print(records)
            dns_check(public,args.ipv4)
        if not shutil.which('gunicorn'):
            print('Installiere separates Ubuntu-Paket python3-gunicorn.')
            run(['apt-get','update']);run(['apt-get','install','-y','python3-gunicorn'])
        if not shutil.which('curl'):raise Stop('curl wird für lokale HTTPS-Prüfungen benötigt.')
        source,sha=fetch_source(args.ref)
        try:
            validate_source(source)
            # Prevent binding over another service. Our existing service may keep its port.
            if not Path('/etc/systemd/system/io-website-contact.service').exists():
                with socket.socket() as sock:
                    try:sock.bind(('127.0.0.1',8091))
                    except OSError:raise Stop('Port 8091 bereits belegt. Keine Änderung.') from None
            # Install the exact checked source before adding the CTL ExecStartPost hook.
            atomic('/usr/local/sbin/io-website',read(source/'deploy/io-website.py'),0o755)
            provision_mail()
            publish(source,sha,args.vhost)
        finally:shutil.rmtree(source)

if __name__=='__main__':
    try:main()
    except (Stop, OSError, subprocess.TimeoutExpired, ValueError, KeyError, urllib.error.URLError) as exc:
        print('Abgebrochen: '+str(exc),file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nAbgebrochen. Bestehende Postfachdaten werden nicht gelöscht.',file=sys.stderr)
        sys.exit(130)
