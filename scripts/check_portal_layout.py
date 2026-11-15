"""Optional Chromium layout regression. No webserver or production accounts used.
Requires playwright and Chromium; browser executable can be set with CHROMIUM_PATH.
"""
from pathlib import Path
import argparse
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
        assert client.request('/kundenverwaltung/')==200
        admin=client.body
        return {'download':download,'customers':admin}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--screenshots',type=Path);args=parser.parse_args()
    if args.screenshots:args.screenshots.mkdir(parents=True,exist_ok=True)
    css=(ROOT/'src/website-assets/site.css').read_text()
    with tempfile.TemporaryDirectory() as tmp:
        pages=rendered_pages(Path(tmp))
        pages['services']=(ROOT/'src/leistungen/index.html').read_text()
        with sync_playwright() as playwright:
            executable=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
            browser=playwright.chromium.launch(headless=True,executable_path=executable,args=['--no-sandbox'])
            try:
                for name,html in pages.items():
                    page=browser.new_page()
                    def resource(route, request, html=html):
                        path=urlsplit(route.request.url).path
                        stylesheet=path.endswith('.css')
                        body=css if stylesheet else ('' if path.endswith('.js') else html)
                        route.fulfill(body=body,content_type='text/css' if stylesheet else ('application/javascript' if path.endswith('.js') else 'text/html'))
                    page.route('**/*',resource)
                    for width in (320,375,768,1440,1920,2560,3840):
                        page.set_viewport_size({'width':width,'height':1000})
                        page.goto('https://layout.test/'+name+'/')
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
                        if width>=1440 and name!='services':
                            assert dimensions['title']<80,(name,width,dimensions)
                            if name=='download':assert dimensions['card']>=700,(name,width,dimensions)
                        if name=='services' and width>=1600:assert dimensions['titleWidth']>=1000,(name,width,dimensions)
                        if args.screenshots and width in (375,2560):page.screenshot(path=str(args.screenshots/f'{name}-{width}.png'),full_page=True)
                        print(name,width,dimensions)
                    page.close()
            finally:browser.close()

if __name__=='__main__':main()
