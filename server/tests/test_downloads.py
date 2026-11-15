import io
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unittest
from http.cookies import SimpleCookie
from urllib.parse import urlencode
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import downloads as app

ADMIN_PASSWORD='Admin-test-password-123'
CUSTOMER_PASSWORD='Customer-start-password-123'
NEW_PASSWORD='Customer-new-password-456'

class Client:
    def __init__(self):self.cookies={};self.set_cookies=[]
    def request(self,path='/download/',method='GET',data=None,origin=app.ORIGIN,referer=None,fetch_site=None):
        raw=urlencode(data or {}).encode()
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'HTTP_ORIGIN':origin,
             'HTTP_COOKIE':'; '.join(k+'='+v for k,v in self.cookies.items()),'REMOTE_ADDR':'127.0.0.1',
             'CONTENT_TYPE':'application/x-www-form-urlencoded','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
        if origin is None:env.pop('HTTP_ORIGIN',None)
        if referer is not None:env['HTTP_REFERER']=referer
        if fetch_site is not None:env['HTTP_SEC_FETCH_SITE']=fetch_site
        result=[]
        body=b''.join(app.application(env,lambda status,headers:result.append((status,headers)))).decode()
        for key,value in result[0][1]:
            if key.lower()=='set-cookie':
                self.set_cookies.append(value)
                parsed=SimpleCookie();parsed.load(value)
                for k,v in parsed.items():self.cookies[k]=v.value
        self.status=int(result[0][0].split()[0]);self.headers=dict(result[0][1]);self.body=body
        return self.status
    def csrf(self):return re.search(r'name="csrf" value="([a-f0-9]+)"',self.body)[1]
    def login(self,address,password):
        self.request();csrf=self.csrf()
        return self.request('/download/anmelden','POST',{'email':address,'password':password,'csrf':csrf})

class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);cred=self.root/'admin.json'
        cred.write_text(json.dumps({'email':app.ADMIN,'password':app.password_hash(ADMIN_PASSWORD)}))
        env=patch.dict(os.environ,{'PORTAL_DB':str(self.root/'portal.sqlite3'),'PORTAL_ADMIN_FILE':str(cred)})
        env.start();self.addCleanup(env.stop);app.READY=False
        self.admin=Client();self.client=Client()
        with app.connection() as db:db.execute("UPDATE settings SET value='manual' WHERE key='apk_mode'")
    def admin_login(self):
        self.assertEqual(self.admin.login(app.ADMIN,ADMIN_PASSWORD),303)
        self.assertEqual(self.admin.request('/kundenverwaltung/'),200)
    def add_customer(self):
        self.admin_login()
        self.assertEqual(self.admin.request('/kundenverwaltung/kunde','POST',{'csrf':self.admin.csrf(),'name':'Testkunde','email':'kunde@example.org','password':CUSTOMER_PASSWORD,'confirm':CUSTOMER_PASSWORD}),303)
        with app.connection() as db:return db.execute('SELECT id FROM users WHERE email=?',('kunde@example.org',)).fetchone()[0]
    def change_customer_password(self):
        self.assertEqual(self.client.login('kunde@example.org',CUSTOMER_PASSWORD),303)
        self.assertEqual(self.client.request('/download/passwort'),200)
        self.assertEqual(self.client.request('/download/passwort','POST',{'csrf':self.client.csrf(),'old':CUSTOMER_PASSWORD,'password':NEW_PASSWORD,'confirm':NEW_PASSWORD}),303)
        self.assertEqual(self.client.login('kunde@example.org',NEW_PASSWORD),303)
    def test_anonymous_has_no_download_or_customer_data(self):
        self.assertEqual(self.client.request(),200)
        self.assertNotIn(app.DEFAULT_URL,self.client.body)
        self.assertEqual(self.client.request('/download/android'),303)
        self.assertEqual(self.client.headers['Location'],'/download/')
        self.assertEqual(self.client.request('/kundenverwaltung/'),303)
    def test_admin_and_secure_session(self):
        self.admin_login()
        self.assertIn('Neuen Kunden freischalten',self.admin.body)
        session_cookie=next(c for c in self.admin.set_cookies if c.startswith(app.COOKIE+'='))
        for attr in ('Secure','HttpOnly','SameSite=Strict','Path=/'):self.assertIn(attr,session_cookie)
        token=self.admin.cookies[app.COOKIE]
        with app.connection() as db:
            row=db.execute('SELECT token FROM sessions').fetchone()
            self.assertNotEqual(row[0],token);self.assertEqual(row[0],app.token_hash(token))
        self.assertEqual(self.admin.headers['Cache-Control'],'no-store, private')
    def test_customer_first_change_then_download_but_no_admin(self):
        self.add_customer()
        self.assertEqual(self.client.login('kunde@example.org',CUSTOMER_PASSWORD),303)
        self.assertEqual(self.client.request('/download/android'),303)
        self.assertEqual(self.client.headers['Location'],'/download/passwort')
        self.client=Client();self.change_customer_password()
        self.assertEqual(self.client.request('/download/android'),303)
        self.assertEqual(self.client.headers['Location'],app.DEFAULT_URL)
        self.assertEqual(self.client.request('/kundenverwaltung/'),403)
        self.assertEqual(self.client.request('/download/'),200)
        csrf=self.client.csrf()
        self.assertEqual(self.client.request('/kundenverwaltung/android','POST',{'csrf':csrf,'url':'https://bad.example/a.apk','label':'Bad'}),403)
    def test_block_revokes_existing_sessions_and_can_reenable(self):
        uid=self.add_customer();self.change_customer_password()
        self.admin.request('/kundenverwaltung/');csrf=self.admin.csrf()
        self.assertEqual(self.admin.request('/kundenverwaltung/status','POST',{'csrf':csrf,'id':uid,'active':'0'}),303)
        self.assertEqual(self.client.request('/download/android'),303)
        self.assertEqual(self.client.headers['Location'],'/download/')
        self.assertEqual(self.client.login('kunde@example.org',NEW_PASSWORD),401)
        self.admin.request('/kundenverwaltung/')
        self.assertEqual(self.admin.request('/kundenverwaltung/status','POST',{'csrf':self.admin.csrf(),'id':uid,'active':'1'}),303)
        self.assertEqual(self.client.login('kunde@example.org',NEW_PASSWORD),303)
    def test_password_reset_invalidates_customer_session(self):
        uid=self.add_customer();self.change_customer_password();self.admin.request('/kundenverwaltung/')
        self.assertEqual(self.admin.request('/kundenverwaltung/passwort','POST',{'csrf':self.admin.csrf(),'id':uid,'password':CUSTOMER_PASSWORD,'confirm':CUSTOMER_PASSWORD}),303)
        self.assertEqual(self.client.request('/download/android'),303)
        self.assertEqual(self.client.login('kunde@example.org',NEW_PASSWORD),401)
        self.assertEqual(self.client.login('kunde@example.org',CUSTOMER_PASSWORD),303)
        self.assertEqual(self.client.headers['Location'],'/download/passwort')
    def test_admin_cannot_be_created_or_blocked_via_customer_forms(self):
        self.admin_login();csrf=self.admin.csrf()
        self.assertEqual(self.admin.request('/kundenverwaltung/kunde','POST',{'csrf':csrf,'email':app.ADMIN,'name':'Fake','password':CUSTOMER_PASSWORD,'confirm':CUSTOMER_PASSWORD}),400)
        with app.connection() as db:uid=db.execute("SELECT id FROM users WHERE role='admin'").fetchone()[0]
        self.assertEqual(self.admin.request('/kundenverwaltung/status','POST',{'csrf':csrf,'id':uid,'active':'0'}),400)
    def test_csrf_and_origin_are_required(self):
        self.client.request();csrf=self.client.csrf()
        self.assertEqual(self.client.request('/download/anmelden','POST',{'csrf':csrf,'email':app.ADMIN,'password':ADMIN_PASSWORD},origin='https://other.example'),403)
        self.admin_login()
        self.assertEqual(self.admin.request('/kundenverwaltung/android','POST',{'csrf':'bad','url':'https://example.org/a.apk','label':'New'}),403)
        self.assertEqual(self.admin.request('/kundenverwaltung/android','POST',{'csrf':'ä'*64,'url':'https://example.org/a.apk','label':'New'}),403)
    def test_android_link_update_admin_only_and_https(self):
        self.admin_login();csrf=self.admin.csrf()
        self.assertEqual(self.admin.request('/kundenverwaltung/android','POST',{'csrf':csrf,'url':'javascript:alert(1)','label':'Bad'}),400)
        self.assertEqual(self.admin.request('/kundenverwaltung/android','POST',{'csrf':csrf,'url':'https://example.org/new.apk','label':'Neue Testversion'}),303)
        self.assertEqual(self.admin.request('/download/android'),303)
        self.assertEqual(self.admin.headers['Location'],'https://example.org/new.apk')
    def test_session_persists_restart_but_new_bootstrap_password_revokes_admin(self):
        self.admin_login();app.READY=False
        self.assertEqual(self.admin.request('/kundenverwaltung/'),200)
        path=self.root/'admin.json';path.write_text(json.dumps({'email':app.ADMIN,'password':app.password_hash('New-admin-password-456')}));app.READY=False
        self.assertEqual(self.admin.request('/kundenverwaltung/'),303)
        self.assertEqual(self.admin.login(app.ADMIN,ADMIN_PASSWORD),401)
        self.assertEqual(self.admin.login(app.ADMIN,'New-admin-password-456'),303)
    def test_login_rate_limit_and_logout(self):
        self.client.request();csrf=self.client.csrf()
        for _ in range(8):self.assertEqual(self.client.request('/download/anmelden','POST',{'csrf':csrf,'email':'unknown@example.org','password':'wrong'}),401)
        self.assertEqual(self.client.request('/download/anmelden','POST',{'csrf':csrf,'email':'unknown@example.org','password':'wrong'}),429)
        self.admin_login();self.admin.request('/download/');csrf=self.admin.csrf()
        self.assertEqual(self.admin.request('/download/abmelden','POST',{'csrf':csrf}),303)
        self.assertEqual(self.admin.request('/kundenverwaltung/'),303)
    def test_automatic_latest_android_and_upstream_failure_keeps_cache(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return json.dumps([{'name':'New Android Test','published_at':'2026-11-16T10:00:00Z','draft':False,'prerelease':True,'assets':[{'name':'LokZeitleiste-TF-Portal.apk','browser_download_url':'https://github.com/omueller369/RailSoftware/releases/download/new/app.apk'}]}]).encode()
        with app.connection() as db:
            db.execute("UPDATE settings SET value='auto' WHERE key='apk_mode'");db.commit()
            with patch.object(app.urllib.request,'urlopen',return_value=Response()):config=app.android_release(db)
            self.assertTrue(config['apk_url'].endswith('/new/app.apk'))
            db.execute("UPDATE settings SET value='0' WHERE key='apk_checked'");db.commit()
            with patch.object(app.urllib.request,'urlopen',side_effect=OSError()):fallback=app.android_release(db)
            self.assertEqual(fallback['apk_url'],config['apk_url'])
            self.assertEqual(fallback['apk_refresh_error'],'1')
    def test_expired_session_cannot_download(self):
        self.admin_login()
        with app.connection() as db:db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.admin.request('/download/android'),303)
        self.assertEqual(self.admin.headers['Location'],'/download/')
    def test_referrer_policy_preserves_same_origin_form_posts(self):
        self.client.request()
        self.assertEqual(self.client.headers['Referrer-Policy'],'same-origin')
    def test_missing_origin_can_use_trusted_referer_with_csrf(self):
        self.client.request();csrf=self.client.csrf()
        data={'email':app.ADMIN,'password':ADMIN_PASSWORD,'csrf':csrf}
        self.assertEqual(self.client.request('/download/anmelden','POST',data,origin=None,referer=app.ORIGIN+'/download/'),303)
    def test_missing_origin_can_use_browser_same_origin_metadata_with_csrf(self):
        self.client.request();csrf=self.client.csrf()
        data={'email':app.ADMIN,'password':ADMIN_PASSWORD,'csrf':csrf}
        self.assertEqual(self.client.request('/download/anmelden','POST',data,origin=None,fetch_site='same-origin'),303)
    def test_null_foreign_and_unverifiable_origins_stay_blocked(self):
        self.client.request();data={'email':app.ADMIN,'password':ADMIN_PASSWORD,'csrf':self.client.csrf()}
        for headers in [dict(origin='null',fetch_site='same-origin'),dict(origin='https://other.example',referer=app.ORIGIN+'/download/',fetch_site='same-origin'),dict(origin=None),dict(origin=None,referer='https://ctl-software.io-goerlitz.eu.evil.example/download/'),dict(origin=None,fetch_site='same-site'),dict(origin=None,referer=app.ORIGIN+'/download/',fetch_site='cross-site')]:
            self.assertEqual(self.client.request('/download/anmelden','POST',data,**headers),403)
    def test_origin_fallback_still_requires_csrf(self):
        self.client.request()
        self.assertEqual(self.client.request('/download/anmelden','POST',{'email':app.ADMIN,'password':ADMIN_PASSWORD,'csrf':'bad'},origin=None,fetch_site='same-origin'),403)
    def test_customer_name_html_escaped(self):
        self.admin_login();csrf=self.admin.csrf()
        self.admin.request('/kundenverwaltung/kunde','POST',{'csrf':csrf,'email':'x@example.org','name':'<script>alert(1)</script>','password':CUSTOMER_PASSWORD,'confirm':CUSTOMER_PASSWORD})
        self.admin.request('/kundenverwaltung/')
        self.assertNotIn('<script>alert(1)</script>',self.admin.body)
        self.assertIn('&lt;script&gt;',self.admin.body)

if __name__=='__main__':unittest.main()
