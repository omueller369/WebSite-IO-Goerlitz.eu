import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('deploy',Path(__file__).resolve().parents[1]/'io-website.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)

VHOST='''<VirtualHost *:80>
ServerName ctl-software.io-goerlitz.eu
RewriteRule ^ https://ctl-software.io-goerlitz.eu%{REQUEST_URI} [R=301,L]
</VirtualHost>
<VirtualHost *:443>
ServerName ctl-software.io-goerlitz.eu
SSLEngine On
ProxyPass /tf http://127.0.0.1:18080/tf
ProxyPass / http://127.0.0.1:18080/
ProxyPassReverse / http://127.0.0.1:18080/
</VirtualHost>
<VirtualHost *:443>
ServerName other.example
ProxyPass / http://other.example/
</VirtualHost>
'''

class DeploymentTests(unittest.TestCase):
    def test_include_before_proxy_only_in_correct_tls_host(self):
        value=d.insert_include(VHOST)
        self.assertLess(value.index('Include /etc/io-website/apache.conf'),value.index('ProxyPass /tf'))
        self.assertEqual(value.count(d.MARKER),1)
        self.assertEqual(d.insert_include(value),value)
        self.assertIn('ProxyPass /tf http://127.0.0.1:18080/tf',value)
        self.assertTrue(value.endswith('<VirtualHost *:443>\nServerName other.example\nProxyPass / http://other.example/\n</VirtualHost>\n'))
    def test_missing_or_duplicate_target_rejected(self):
        with self.assertRaises(d.Stop):d.insert_include(VHOST.replace(d.HOST,'unknown.example'))
        with self.assertRaises(d.Stop):d.insert_include(VHOST+VHOST)
    def test_sieve_known_existing_forward_does_not_include_new_mailbox(self):
        d.check_sieve('require ["envelope"];\nif envelope :is "to" ["info@ctl-software.io-goerlitz.eu"] {\n redirect "existing@example.org";\n}\nkeep;\n')
        for text in ('redirect "external@example.org"; keep;', 'require ["envelope"];if envelope :is "to" ["info@io-goerlitz.eu"] {redirect "external@example.org";}keep;'):
            with self.assertRaises(d.Stop):d.check_sieve(text)
    def test_existing_mailbox_hashes_preserved(self):
        original='old@example.org:{SHA512-CRYPT}$6$existing:100:100::/var/vmail/old::\n'
        result=d.merge_user(original,'$6$new',500,500)
        self.assertTrue(result.startswith(original))
        self.assertIn('info@io-goerlitz.eu:{SHA512-CRYPT}$6$new:500:500:',result)
        with self.assertRaises(d.Stop):d.merge_user(result,'$6$overwrite',500,500)
        reset=d.merge_user(result,'$6$reset',500,500,reset=True)
        self.assertIn(original,reset);self.assertNotIn('$6$new',reset)
    def test_map_preserves_other_domains_and_refuses_conflicts(self):
        old='other.example OK\n'
        self.assertEqual(d.merge_map(old,'io-goerlitz.eu','OK'),old+'io-goerlitz.eu OK\n')
        with self.assertRaises(d.Stop):d.merge_map('io-goerlitz.eu OTHER\n','io-goerlitz.eu','OK')
    def test_symlink_management_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'real').mkdir();(root/'link').symlink_to(root/'real')
            with self.assertRaises(d.Stop):d.safe_path(root/'link/file')
    @patch.object(d.os,'chown')
    def test_transaction_restores_bytes_permissions_and_removes_new_file(self,chown):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'old';new=root/'new';old.write_text('original');old.chmod(0o640)
            with patch.object(d,'STATE',root/'state'):
                tx=d.Transaction();tx.write(old,'changed',0o600);tx.write(new,'created',0o600);tx.restore()
            self.assertEqual(old.read_text(),'original');self.assertEqual(old.stat().st_mode & 0o777,0o640)
            self.assertFalse(new.exists())
    def test_password_hidden_prompt_and_mismatch_rejected(self):
        with patch.object(d.sys.stdin,'isatty',return_value=True),patch.object(d.getpass,'getpass',side_effect=['Long-test-password','different-password']):
            with self.assertRaises(d.Stop):d.password_prompt()
        with patch.object(d.sys.stdin,'isatty',return_value=False):
            with self.assertRaises(d.Stop):d.password_prompt()
    def test_mail_sync_uses_independent_maps_and_composites(self):
        files={'/etc/opendkim.conf':'KeyTable refile:/etc/opendkim/ctl-keys\nSigningTable refile:/etc/opendkim/ctl-signing\nMode sv\n',
               '/etc/opendkim/ctl-keys':'ctl._domainkey.old.example old.example:ctl:/old/private\n',
               '/etc/opendkim/ctl-signing':'*@old.example ctl._domainkey.old.example\n',
               '/etc/postsrsd.conf':'domains = { "ctl-software.io-goerlitz.eu" }\nsrs-domain = "ctl-software.io-goerlitz.eu"\n'}
        class Tx:
            def __init__(self):self.values={}
            def save(self,p):pass
            def write(self,p,value,*args):self.values[str(p)]=value
        tx=Tx();calls=[]
        def command(args,**kwargs):
            calls.append(args)
            if args[:2]==['postconf','-h']:
                return 'hash:/etc/postfix/ctl-'+('domains' if args[2]=='virtual_mailbox_domains' else 'mailboxes')
            return ''
        with patch.object(d,'read',side_effect=lambda p:files[str(p)]),patch.object(d,'run',side_effect=command),patch.object(d.grp,'getgrnam',return_value=type('G',(),{'gr_gid':123})()):
            d.sync_mail(tx)
        self.assertNotIn('/etc/opendkim/ctl-keys',tx.values)
        self.assertNotIn('/etc/opendkim/ctl-signing',tx.values)
        self.assertIn('old.example',tx.values['/etc/opendkim/io-website-keys'])
        self.assertIn('io-goerlitz.eu',tx.values['/etc/opendkim/io-website-keys'])
        self.assertIn('srs-domain = "ctl-software.io-goerlitz.eu"',tx.values['/etc/postsrsd.conf'])
        self.assertTrue(any('io-website-domains' in str(c) for c in calls))
    def test_tls_vhost_existing_log_preserved_with_filter(self):
        value=VHOST.replace('SSLEngine On','SSLEngine On\nCustomLog /var/log/apache2/existing.log combined')
        result,extra=d.website_logging(value)
        self.assertIn('CustomLog /var/log/apache2/existing.log combined env=!io_website',result)
        self.assertEqual(extra,'')
    def test_plan_has_no_system_mutations(self):
        with patch.object(d.sys,'argv',['io-website','plan']),patch.object(d,'run') as run,patch.object(d,'atomic') as atomic,patch('sys.stdout',io.StringIO()):
            d.main()
        run.assert_not_called();atomic.assert_not_called()

if __name__=='__main__':unittest.main()
