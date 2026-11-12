from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import re
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[1]/'dist'
pages=list(root.rglob('*.html'))
assert len(pages)==10, len(pages)
class Check(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.ids=set(); self.h1=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        if tag=='h1':self.h1+=1
        for k in ('href','src','action'):
            if k in a:self.links.append(a[k])
for page in pages:
    parser=Check(); parser.feed(page.read_text())
    assert parser.h1==1,(page,parser.h1)
    for link in parser.links:
        u=urlsplit(link)
        if u.scheme or u.netloc:continue
        if not u.path:
            assert not u.fragment or u.fragment in parser.ids,(page,link)
            continue
        assert not re.match(r'^/(tf|admin|api)(/|$)',u.path),(page,link)
        if u.path=='/website-contact':continue
        target=root/unquote(u.path).lstrip('/')
        assert target.is_file() or (target/'index.html').is_file(),(page,link)
for svg in root.rglob('*.svg'):ET.parse(svg)
# Unknown software paths must not match the static Apache route allowlist.
conf=(root.parent/'docs/apache-website.conf.example').read_text()
patterns=re.findall(r'^ProxyPassMatch "([^"]+)" "!"',conf,re.M)
for path in ['/','/index.html','/leistungen','/leistungen/','/entwicklung/rail-software/demo-download/']:
    assert any(re.search(pattern,path) for pattern in patterns),path
for path in ['/tf','/admin','/api/v1/me','/auth-session.js','/entwicklung/unknown','/kontakt-extra']:
    assert not any(re.search(pattern,path) for pattern in patterns),path
print(f'{len(pages)} pages: links, single H1, SVGs, protected-link exclusion and Apache route boundaries passed.')
