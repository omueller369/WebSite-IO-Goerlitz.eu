"""Optional Chromium layout regression. No webserver or production accounts used.
Requires playwright and Chromium; browser executable can be set with CHROMIUM_PATH.
"""
from pathlib import Path
import argparse
import mimetypes
import json
import os
import shutil
import sys
import tempfile
from unittest.mock import patch
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server/tests'))
from test_downloads import Client, ADMIN_PASSWORD
import downloads


def rendered_pages(directory):
    credential=directory/'admin.json'
    credential.write_text(json.dumps({'email':downloads.ADMIN,'password':downloads.password_hash(ADMIN_PASSWORD)}))
    with patch.dict(os.environ,{'PORTAL_DB':str(directory/'test.sqlite3'),'PORTAL_ADMIN_FILE':str(credential)}):
        downloads.READY=False
        with downloads.connection() as db:db.execute("UPDATE settings SET value='manual' WHERE key='apk_mode'")
        client=Client()
        assert client.login(downloads.ADMIN,ADMIN_PASSWORD)==303
        assert client.request('/download/')==200
        download=client.body
        download_headers={key:value for key,value in client.headers.items() if key in ('Content-Security-Policy','Referrer-Policy','X-Frame-Options')}
        assert client.request('/kundenverwaltung/')==200
        admin=client.body
        admin_headers={key:value for key,value in client.headers.items() if key in ('Content-Security-Policy','Referrer-Policy','X-Frame-Options')}
        return {'download':(download,download_headers),'customers':(admin,admin_headers)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--screenshots',type=Path);args=parser.parse_args()
    if args.screenshots:args.screenshots.mkdir(parents=True,exist_ok=True)
    css=(ROOT/'src/website-assets/site.css').read_text()
    with tempfile.TemporaryDirectory() as tmp:
        pages=rendered_pages(Path(tmp))
        pages['services']=((ROOT/'src/leistungen/index.html').read_text(),{})
        pages['home']=((ROOT/'src/index.html').read_text(),{})
        pages['company']=((ROOT/'src/unternehmen/index.html').read_text(),{})
        with sync_playwright() as playwright:
            executable=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
            browser=playwright.chromium.launch(headless=True,executable_path=executable,args=['--no-sandbox'])
            try:
                for name,(html,security_headers) in pages.items():
                    page=browser.new_page()
                    def resource(route, request, html=html,security_headers=security_headers):
                        path=urlsplit(route.request.url).path
                        stylesheet=path.endswith('.css')
                        if path.startswith('/website-assets/') and (ROOT/'src'/path.lstrip('/')).is_file():
                            file=ROOT/'src'/path.lstrip('/')
                            route.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
                        else:
                            route.fulfill(body='' if path.endswith('.js') else html,content_type='application/javascript' if path.endswith('.js') else 'text/html',headers={} if path.endswith('.js') else security_headers)
                    page.route('**/*',resource)
                    for width in (320,375,768,1440,1920,2560,3840):
                        page.set_viewport_size({'width':width,'height':1000})
                        page.goto('https://layout.test/'+name+'/')
                        page.locator('img[loading=lazy]').evaluate_all("images => images.forEach(image => image.removeAttribute('loading'))")
                        page.wait_for_function("[...document.images].every(image => image.complete && image.naturalWidth > 0)")
                        dimensions=page.evaluate('''() => ({
                          overflow:document.documentElement.scrollWidth>innerWidth,
                          main:document.querySelector('main').getBoundingClientRect().width,
                          content:(document.querySelector('.portal-content')||document.querySelector('.section')).getBoundingClientRect().width,
                          title:document.querySelector('h1').getBoundingClientRect().height,
                          titleWidth:document.querySelector('h1').getBoundingClientRect().width,
                          card:document.querySelector('.boxed')?.getBoundingClientRect().width,
                          button:document.querySelector('.button').getBoundingClientRect().width
                        })''')
                        assert not dimensions['overflow'],(name,width,dimensions)
                        assert dimensions['content']>=min(272,width-48),(name,width,dimensions)
                        assert dimensions['button']>=150,(name,width,dimensions)
                        if width>=1440 and name in ('download','customers'):
                            assert dimensions['title']<80,(name,width,dimensions)
                            if name=='download':assert dimensions['card']>=700,(name,width,dimensions)
                        if name in ('services','company') and width>=1600:assert dimensions['titleWidth']>=1000,(name,width,dimensions)
                        if args.screenshots and width in (375,2560):page.screenshot(path=str(args.screenshots/f'{name}-{width}.png'),full_page=True)
                        print(name,width,dimensions)
                    page.close()
            finally:browser.close()

if __name__=='__main__':main()
