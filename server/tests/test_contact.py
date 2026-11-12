import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contact

class ContactTests(unittest.TestCase):
    def setUp(self):
        contact._BUCKETS.clear()
        self.config = patch.dict(os.environ, {'SMTP_HOST':'smtp.example.org', 'SMTP_FROM':'web@example.org', 'SMTP_SECURITY':'starttls'})
        self.config.start()
        self.addCleanup(self.config.stop)
        self.payload = {'name':'Test Person', 'email':'test@example.org', 'topic':'Software', 'message':'Dies ist eine Testanfrage.', 'website':''}
    def request(self, payload=None, **changes):
        raw=json.dumps(self.payload if payload is None else payload).encode()
        env={'REQUEST_METHOD':'POST', 'PATH_INFO':'/website-contact', 'HTTP_ORIGIN':contact.ORIGIN, 'CONTENT_TYPE':'application/json', 'CONTENT_LENGTH':str(len(raw)), 'wsgi.input':io.BytesIO(raw), 'REMOTE_ADDR':'127.0.0.1'}
        env.update(changes)
        result=[]
        body=b''.join(contact.application(env, lambda code,headers:result.append(code)))
        return int(result[0].split()[0]),json.loads(body)
    @patch('contact.send')
    def test_success_only_after_mail_handoff(self, send):
        self.assertEqual(self.request()[0],200)
        send.assert_called_once_with(self.payload)
    @patch('contact.send', side_effect=OSError('private SMTP failure'))
    def test_smtp_failure_is_not_success(self, send):
        code,body=self.request()
        self.assertEqual(code,503)
        self.assertNotIn('private SMTP',str(body))
    @patch('contact.send')
    def test_origin_injection_and_honeypot_rejected(self, send):
        self.assertEqual(self.request(HTTP_ORIGIN='https://other.example')[0],403)
        self.assertEqual(self.request({**self.payload,'email':'test@example.org\r\nBcc: victim@example.org'})[0],400)
        self.assertEqual(self.request({**self.payload,'website':'spam'})[0],400)
        self.assertEqual(self.request([])[0],400)
        send.assert_not_called()
    @patch('contact.send')
    def test_rate_limit_and_body_limit(self, send):
        for _ in range(5):self.assertEqual(self.request()[0],200)
        self.assertEqual(self.request()[0],429)
        self.assertEqual(self.request(CONTENT_LENGTH='40000')[0],413)
        self.assertEqual(send.call_count,5)
    @patch('contact.send')
    def test_unconfigured_is_unavailable(self, send):
        with patch.dict(os.environ, {'SMTP_HOST':''}):
            self.assertFalse(self.request(REQUEST_METHOD='GET')[1]['available'])
            self.assertEqual(self.request()[0],503)
        send.assert_not_called()

if __name__=='__main__':unittest.main()
