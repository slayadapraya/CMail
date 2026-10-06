import base64
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock
import requests
from aster.core import Store, AppError, AmbiguousSend, ApiError, AuthRequired
from aster.google import Gmail, GoogleAuth, MAIL_SCOPE, CAL_SCOPE, normalize_message, credentials_from_json
from aster.imap_google import GmailIMAP,AppPasswordAuth,encode_id,decode_id
from aster.assistant import Assistant
class Vault:
    def __init__(self,value=None):self.value=value
    def load(self):return self.value
    def save(self,value):self.value=value
class ProviderTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'cache')
    def tearDown(self):self.temp.cleanup()
    def test_google_refresh_and_optional_declined_scope(self):
        vault=Vault('refresh');auth=GoogleAuth('test.apps.googleusercontent.com','secret',calendar=True,vault=vault)
        response=SimpleNamespace(ok=True,json=lambda:{'access_token':'access','refresh_token':'rotated','scope':MAIL_SCOPE,'expires_in':3600})
        with patch('aster.google.requests.post',return_value=response):self.assertEqual(auth.access_token(),'access')
        self.assertFalse(auth.calendar_enabled);self.assertEqual(vault.value,'rotated')
    def test_google_history_atomic_failure(self):
        gmail=Gmail(None);self.store.delta('inbox',[{'id':'old'}],'100',reset=True)
        gmail.api=Mock(return_value={'historyId':'120'});gmail.pages=Mock(return_value=[{'messagesAdded':[{'message':{'id':'new'}}]}]);gmail.message=Mock(side_effect=AppError('offline'))
        with self.assertRaises(AppError):gmail.sync_mail(self.store,'inbox')
        self.assertEqual(self.store.get('delta:inbox'),'100');self.assertEqual(self.store.items('mail','inbox')[0]['id'],'old')
    def test_initial_sync_exposes_partial_mail_without_advancing_history(self):
        gmail=Gmail(None);gmail.api=Mock(return_value={'historyId':'120'});gmail.pages=Mock(return_value=[{'id':str(i)} for i in range(30)])
        def message(mid):
            if mid=='26':raise AppError('network failed')
            return {'id':mid,'labelIds':['INBOX']}
        gmail.message=message;progress=[]
        with self.assertRaises(AppError):gmail.sync_mail(self.store,'inbox',lambda loaded,total:progress.append((loaded,total)))
        self.assertEqual(len(self.store.items('mail','inbox')),25);self.assertFalse(self.store.get('delta:inbox'));self.assertEqual(progress,[(25,30)])
        gmail.message=lambda mid:{'id':mid,'labelIds':['INBOX']};gmail.sync_mail(self.store,'inbox')
        self.assertEqual(len(self.store.items('mail','inbox')),30);self.assertEqual(self.store.get('delta:inbox'),'120')
    def test_google_history_delete_and_label_change(self):
        gmail=Gmail(None);self.store.delta('inbox',[{'id':'gone'},{'id':'moved'}],'100',reset=True)
        gmail.api=Mock(return_value={'historyId':'120'});gmail.pages=Mock(return_value=[{'messagesDeleted':[{'message':{'id':'gone'}}],'labelsRemoved':[{'message':{'id':'moved'}}]}])
        gmail.message=lambda mid: (_ for _ in ()).throw(ApiError('gone',404)) if mid=='gone' else {'id':mid,'labelIds':[]}
        gmail.sync_mail(self.store,'inbox');self.assertEqual(self.store.items('mail','inbox'),[]);self.assertEqual(self.store.get('delta:inbox'),'120')
    def test_google_ambiguous_send_no_retry(self):
        gmail=Gmail(None);calls=[]
        def api(method,path,data=None,**kwargs):
            calls.append(path)
            if path=='drafts/send':raise AmbiguousSend('unknown')
            return {'id':'remote'}
        gmail.api=api;draft={'id':'test','to':'person@example.com','cc':'copy@example.com','bcc':'hidden@example.com','subject':'Hello','body':'Text','html':'<b>Text</b>'}
        with self.assertRaises(AmbiguousSend):gmail.send(self.store,draft)
        self.assertEqual(self.store.drafts()[0]['state'],'uncertain')
        with self.assertRaises(AppError):gmail.send(self.store,draft)
        self.assertEqual(calls.count('drafts/send'),1)
    def test_normalize_multipart_attachment_and_autocomplete_fields(self):
        value={'id':'x','labelIds':['INBOX','UNREAD','STARRED'],'payload':{'headers':[{'name':'From','value':'Person <person@example.com>'},{'name':'To','value':'me@example.com'}],'parts':[{'mimeType':'text/plain','body':{'data':base64.urlsafe_b64encode(b'Hello').decode()}},{'filename':'file.txt','body':{'attachmentId':'a'}}]}}
        result=normalize_message(value);self.assertEqual(result['body']['content'],'Hello');self.assertTrue(result['hasAttachments']);self.assertFalse(result['isRead']);self.assertEqual(result['toRecipients'][0]['emailAddress']['address'],'me@example.com')
    def test_app_password_requires_correct_credential(self):
        auth=AppPasswordAuth('cmail.test.fixture@gmail.com','abcd efgh ijkl mnop',vault=Vault());self.assertEqual(auth.password,'abcdefghijklmnop')
        with self.assertRaises(AppError):AppPasswordAuth('cmail.test.fixture@gmail.com','api-key',vault=Vault())
        with self.assertRaises(AuthRequired):AppPasswordAuth('cmail.test.fixture@gmail.com',vault=Vault())
    def test_imap_batch_flags_and_uid_identity(self):
        auth=AppPasswordAuth('cmail.test.fixture@gmail.com','abcdefghijklmnop',vault=Vault());gmail=GmailIMAP(auth)
        client=Mock();client.select.return_value=('OK',[]);client.response.return_value=('UIDVALIDITY',[b'77'])
        def uid(command,*args):
            if command=='SEARCH':return 'OK',[b'1 2']
            return 'OK',[(b'1 (UID 1 FLAGS (\\Seen) BODY[HEADER] {20}',b'From: A <a@example.com>\r\nSubject: First\r\n\r\n'),(b'2 (UID 2 FLAGS (\\Flagged) BODY[HEADER] {20}',b'From: B <b@example.com>\r\nSubject: Second\r\n\r\n')]
        client.uid.side_effect=uid
        @contextmanager
        def connection():yield client
        gmail.connection=connection;gmail.sync_mail(self.store,'inbox');rows=self.store.items('mail','inbox');self.assertEqual(len(rows),2);self.assertEqual(client.uid.call_count,2)
        self.assertEqual(decode_id(rows[0]['id'])[1],'77');self.assertTrue(any(x['isRead'] for x in rows));self.assertTrue(any(x['flag']['flagStatus']=='flagged' for x in rows))
    def test_smtp_bcc_hidden_and_ambiguous_send(self):
        auth=AppPasswordAuth('cmail.test.fixture@gmail.com','abcdefghijklmnop',vault=Vault());gmail=GmailIMAP(auth);smtp=Mock();smtp.send_message.side_effect=OSError('disconnect')
        draft={'id':'d','to':'person@example.com','bcc':'hidden@example.com','subject':'Subject','body':'Text'}
        with patch('aster.imap_google.smtplib.SMTP_SSL',return_value=smtp) as constructor:
            with self.assertRaises(AmbiguousSend):gmail.send(self.store,draft)
            self.assertEqual(constructor.call_args.args[:2],('smtp.gmail.com',465));self.assertEqual(constructor.call_args.kwargs['context'].verify_mode,2)
        message=smtp.send_message.call_args.args[0];self.assertIsNone(message.get('Bcc'));self.assertIn('hidden@example.com',smtp.send_message.call_args.kwargs['to_addrs']);self.assertEqual(self.store.drafts()[0]['state'],'uncertain')
    def test_assistant_structured_proposals_no_actions(self):
        value={'answer':'Review this','email':{'to':'a@example.com','cc':'','bcc':'','subject':'Hello','body':'Hi'},'event':None}
        session=Mock();session.post.return_value=SimpleNamespace(status_code=200,ok=True,json=lambda:{'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(value)}]}]})
        self.assertEqual(Assistant('key',session=session).ask('Draft mail')['email']['subject'],'Hello')
        payload=session.post.call_args.kwargs['json'];self.assertFalse(payload['store']);self.assertTrue(payload['text']['format']['strict']);self.assertEqual(session.post.call_count,1)
    def test_assistant_errors_dont_expose_key(self):
        session=Mock();session.post.side_effect=requests.ConnectionError('secret-key')
        with self.assertRaises(AppError) as caught:Assistant('secret-key',session=session).ask('hello')
        self.assertNotIn('secret-key',str(caught.exception))
        session.post.side_effect=None;session.post.return_value=SimpleNamespace(status_code=401,ok=False)
        with self.assertRaises(AppError):Assistant('key',session=session).ask('hello')
