import unittest,base64,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from aster.presentation import timestamp,date_label,conversations
from aster.mailhtml import document
from aster.google import Gmail,normalize_message
from aster.core import ApiError,AppError,Store
class PresentationTests(unittest.TestCase):
    def test_actual_user_time_and_dst(self):
        msg={'receivedDateTime':'2026-10-06T02:49:33+00:00'}
        self.assertIn('15:49',date_label(msg));self.assertIn('NZDT',date_label(msg,True));self.assertIn('02:49',date_label(msg,zone='UTC'))
        self.assertIn('14:49',date_label({'receivedDateTime':'2026-07-06T02:49:33Z'}))
    def test_numeric_sort_and_grouping_not_subject(self):
        rows=[{'id':'1','threadId':'a','receivedDateTime':'2026-10-06T15:49:33+13:00','subject':'Same','isRead':False},{'id':'2','threadId':'a','receivedDateTime':'2026-10-06T02:58:00Z','isRead':True},{'id':'3','threadId':'b','receivedDateTime':'2026-10-06T03:00:00Z','subject':'Same','isRead':True}]
        groups=conversations(rows);self.assertEqual([g['thread_key'] for g in groups],['b','a']);self.assertEqual(groups[1]['count'],2);self.assertFalse(groups[1]['isRead'])
    def test_primary_filter_matches_gmail_category_labels(self):
        rows=[{'id':'p','labelIds':['INBOX','CATEGORY_PROMOTIONS']},{'id':'x','labelIds':['INBOX','CATEGORY_PERSONAL']},{'id':'s','labelIds':['INBOX','CATEGORY_SOCIAL']}]
        self.assertEqual([m['id'] for m in conversations(rows,'Primary')],['x']);self.assertEqual([m['id'] for m in conversations(rows,'Promotions')],['p'])
    def test_html_format_cid_quote_and_external_image_block(self):
        cid='data:image/png;base64,YWJj'
        text='<table><tr><td><b>Signature</b><img src="cid:logo"></td></tr></table><div class="gmail_quote">Older reply</div><img src="https://tracker.invalid/x">'
        result,blocked=document(text,{'logo':cid});self.assertIn('<table>',result);self.assertIn(cid,result);self.assertIn('<details',result);self.assertTrue(blocked);self.assertNotIn('tracker.invalid',result)
    def test_reader_is_grey_and_overrides_white_sender_backgrounds(self):
        result,_=document('<div style="background-color:white;color:black">Readable</div>')
        self.assertIn('background:#242831!important',result);self.assertIn('background-color:transparent!important',result);self.assertIn('color:#e6edf8!important',result)
        custom,_=document('Text',is_html=False,background='#000000');self.assertIn('background:#000000!important',custom)
    def test_mail_html_removes_active_content_and_dangerous_links(self):
        result,_=document('<script>attack()</script><iframe src="file:///etc/passwd"></iframe><a href="javascript:attack()" onclick="attack()">Text</a><img src="file:///etc/passwd"><span style="background:url(https://track.invalid)">Hello</span>')
        for bad in ('attack()','file:///etc/passwd','onclick','https://track.invalid'):self.assertNotIn(bad,result)
        self.assertIn("default-src 'none'",result)
    def test_mime_html_inline_metadata_and_character_encoding(self):
        body=base64.urlsafe_b64encode('<b>Café</b>'.encode('iso-8859-1')).decode()
        msg=normalize_message({'id':'x','payload':{'parts':[{'mimeType':'text/html','headers':[{'name':'Content-Type','value':'text/html; charset=iso-8859-1'}],'body':{'data':body}},{'partId':'p','filename':'logo.png','mimeType':'image/png','headers':[{'name':'Content-ID','value':'<logo>'}],'body':{'attachmentId':'asset','size':99}}]}})
        self.assertEqual(msg['htmlBody'],'<b>Café</b>');self.assertTrue(msg['files'][0]['isInline']);self.assertEqual(msg['files'][0]['contentId'],'logo');self.assertFalse(msg['hasAttachments'])
    def test_quota_backoff_matches_new_total_query_cost_error(self):
        gmail=Gmail(SimpleNamespace(access_token=lambda:'token'));response=SimpleNamespace(status_code=403,ok=False,headers={},json=lambda:{'error':{'message':"Quota exceeded for quota metric 'Total Query Cost'",'errors':[{'reason':'quotaExceeded'}]}})
        with patch('aster.google.requests.request',return_value=response) as request:
            with self.assertRaises(ApiError):gmail.api('GET','profile')
            self.assertGreater(gmail.backoff_until,0)
            with self.assertRaises(AppError):gmail.api('GET','profile')
            self.assertEqual(request.call_count,1)
    def test_shared_request_pacing(self):
        gmail=Gmail(SimpleNamespace(access_token=lambda:'token'));response=SimpleNamespace(status_code=200,ok=True,content=b'{}',json=lambda:{})
        with patch('aster.google.time.monotonic',return_value=100),patch('aster.google.time.sleep') as sleep,patch('aster.google.requests.request',return_value=response):
            gmail.api('GET','messages/a?format=full');gmail.api('GET','messages/b?format=full')
            self.assertAlmostEqual(sleep.call_args.args[0],20/70)
    def test_resume_does_not_redownload_completed_batches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp));gmail=Gmail(None);gmail.api=Mock(return_value={'historyId':'1'});gmail.pages=Mock(return_value=[{'id':str(i)} for i in range(30)])
            calls=[]
            def message(mid):
                calls.append(mid)
                if mid=='26':raise AppError('quota')
                return {'id':mid}
            gmail.message=message
            with self.assertRaises(AppError):gmail.sync_mail(store,'inbox')
            calls.clear();gmail.message=lambda mid:(calls.append(mid) or {'id':mid});gmail.sync_mail(store,'inbox')
            self.assertEqual(calls,['25','26','27','28','29']);self.assertEqual(len(store.items('mail','inbox')),30);self.assertIsNone(store.get('import:inbox'))

    def test_bounded_import_checks_new_arrivals_before_old_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp));gmail=Gmail(None)
            refs=[{'id':str(i)} for i in range(60)]
            store.set('import:inbox',{'baseline':'100','refs':refs,'offset':25})
            store.delta('inbox',[{'id':str(i)} for i in range(25)],'',reset=True)
            gmail.api=Mock(return_value={'messages':[{'id':'new'}]});calls=[]
            gmail.message=lambda mid:(calls.append(mid) or {'id':mid,'labelIds':['INBOX']})
            gmail.sync_mail(store,'inbox',batch_limit=1)
            self.assertEqual(calls[0],'new');self.assertEqual(len(calls),26)
            self.assertIn('new',{m['id'] for m in store.items('mail','inbox')})
            self.assertEqual(store.get('import:inbox')['offset'],50);self.assertFalse(store.get('delta:inbox'))
            calls.clear();gmail.sync_mail(store,'inbox',batch_limit=1)
            self.assertNotIn('new',calls);self.assertEqual(len(calls),10)
            self.assertEqual(store.get('delta:inbox'),'100');self.assertIsNone(store.get('import:inbox'))
    def test_recent_mail_survives_first_import_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp));gmail=Gmail(None)
            gmail.api=Mock(side_effect=[{'historyId':'100'},{'messages':[{'id':'new'}]}])
            gmail.pages=Mock(return_value=[{'id':str(i)} for i in range(30)])
            gmail.message=lambda mid:{'id':mid,'labelIds':['INBOX']}
            gmail.sync_mail(store,'inbox',batch_limit=1)
            self.assertIn('new',{m['id'] for m in store.items('mail','inbox')})
            self.assertEqual(store.get('import:inbox')['offset'],25)

    def test_css_scale_handles_fractional_dimensions(self):
        from aster.theme import scaled_css
        value=scaled_css('x {padding:10px;letter-spacing:-.5px;border:1px}',.8)
        self.assertIn('padding:8.00px',value);self.assertIn('letter-spacing:-0.40px',value)
        self.assertIn('border:0.80px',value);self.assertNotIn('-.0.',value)
