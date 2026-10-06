import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from aster.core import Store, Graph, Auth, AppError, ApiError, AmbiguousSend, plain_body, email_recipients, month_bounds

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name)
        self.graph=Graph(Mock(access_token=Mock(return_value='test')))
    def tearDown(self):self.store.db.close();self.temp.cleanup()
    def test_html_does_not_render_scripts_or_remote_images(self):
        self.assertEqual(plain_body({'contentType':'HTML','content':'<p>Hello</p><script>secret()</script><img src="https://tracker">there'}),'Hellothere')
    def test_recipient_addresses(self):
        values=email_recipients('Maya <maya@example.com>; alex@example.com')
        self.assertEqual(values[0]['emailAddress']['address'],'maya@example.com')
        with self.assertRaises(AppError):email_recipients('bad address')
    def test_private_cache_permissions(self):
        self.assertEqual(self.store.root.stat().st_mode & 0o777,0o700)
        self.assertEqual(self.store.path.stat().st_mode & 0o777,0o600)
    def test_delta_atomic_pagination_and_deletions(self):
        self.store.delta('inbox',[{'id':'old','subject':'old'}],'old-cursor')
        self.graph.request=Mock(side_effect=[{'value':[{'id':'new'}],'@odata.nextLink':'next'},AppError('offline')])
        with self.assertRaises(AppError):self.graph.sync_mail(self.store,'inbox')
        self.assertEqual(self.store.get('delta:inbox'),'old-cursor')
        self.assertEqual([x['id'] for x in self.store.items('mail','inbox')],['old'])
        self.graph.request=Mock(side_effect=[{'value':[{'id':'new'}],'@odata.nextLink':'next'},{'value':[{'id':'old','@removed':{}}],'@odata.deltaLink':'new-cursor'}])
        self.graph.sync_mail(self.store,'inbox')
        self.assertEqual([x['id'] for x in self.store.items('mail','inbox')],['new'])
    def test_expired_delta_retains_cache_until_replacement(self):
        self.store.delta('inbox',[{'id':'old'}],'expired')
        self.graph.request=Mock(side_effect=ApiError('Gone',410))
        with self.assertRaises(ApiError):self.graph.sync_mail(self.store,'inbox')
        self.assertIsNone(self.store.get('delta:inbox'))
        self.assertEqual(self.store.items('mail','inbox'),[{'id':'old'}])
        self.graph.request=Mock(return_value={'value':[{'id':'replacement'}],'@odata.deltaLink':'valid'})
        self.graph.sync_mail(self.store,'inbox')
        self.assertEqual(self.store.items('mail','inbox'),[{'id':'replacement'}])
    def test_restart_preserves_uncertain_send(self):
        self.store.draft({'id':'one','body':'keep me'},'sending')
        reopened=Store(self.temp.name)
        self.assertEqual(reopened.drafts()[0]['state'],'uncertain');reopened.db.close()
    def test_ambiguous_send_is_never_retried(self):
        draft={'id':'d','to':'alex@example.com','subject':'hello','body':'test','attachments':[]}
        self.store.draft(draft)
        self.graph.request=Mock(side_effect=[{'id':'remote'},AmbiguousSend('uncertain')])
        with self.assertRaises(AmbiguousSend):self.graph.send(self.store,draft)
        self.assertEqual(self.store.drafts()[0]['state'],'uncertain')
        with self.assertRaises(AppError):self.graph.send(self.store,draft)
        self.assertEqual(self.graph.request.call_count,2)
    def test_accepted_send_is_journalled(self):
        draft={'id':'d','to':'alex@example.com','subject':'hello','body':'test','attachments':[]}
        self.graph.request=Mock(side_effect=[{'id':'remote'},{}])
        self.graph.send(self.store,draft)
        self.assertEqual(self.store.drafts()[0]['state'],'accepted')
    def test_failed_preparation_reuses_remote_draft(self):
        draft={'id':'d','to':'alex@example.com','subject':'hello','body':'test','attachments':[], 'remote_id':'existing'}
        self.store.draft(draft)
        self.graph.request=Mock(return_value={});self.graph.pages=Mock(return_value=[])
        self.graph.send(self.store,draft)
        self.assertEqual(self.graph.request.call_args_list[0].args[0],'PATCH')
        self.assertEqual(self.graph.request.call_args_list[1].args[1],'/me/messages/existing/send')
    def test_graph_rejects_untrusted_pagination_urls(self):
        with self.assertRaises(AppError):self.graph.request('GET','https://evil.example/steal')
        with self.assertRaises(AppError):self.graph.request('GET','https://graph.microsoft.com.evil.example/v1.0/me')
    @patch('aster.core.requests.request')
    def test_network_send_ambiguity_and_no_automatic_retry(self, request):
        import requests
        request.side_effect=requests.Timeout()
        with self.assertRaises(AmbiguousSend):self.graph.request('POST','/me/messages/id/send',{})
        request.assert_called_once()
    @patch('aster.core.requests.request')
    def test_throttle_respects_retry_after(self,request):
        response=Mock(status_code=429,ok=False,headers={'Retry-After':'120'})
        response.json.return_value={'error':{'message':'slow down'}};request.return_value=response
        with self.assertRaises(ApiError):self.graph.request('GET','/me')
        with self.assertRaises(AppError):self.graph.request('GET','/me')
        request.assert_called_once()
    def test_month_bounds_december_rollover(self):
        start,end=month_bounds(2026,12)
        self.assertTrue(start.startswith('2026-'));self.assertTrue(end.startswith(('2026-12-31','2027-01-01')))


class AuthTests(unittest.TestCase):
    @patch('aster.core.requests.post')
    def test_school_reauthentication_pauses_silent_refresh(self,post):
        from aster.core import AuthRequired
        vault=Mock();vault.load.return_value='fake-refresh'
        auth=Auth('00000000-0000-0000-0000-000000000001',vault=vault)
        response=Mock(ok=False);response.json.return_value={'error':'invalid_grant','error_description':'AADSTS70043 Sign-in frequency expired'};post.return_value=response
        with self.assertRaises(AuthRequired):auth.access_token()
        self.assertTrue(auth.needs_login)
        with self.assertRaises(AuthRequired):auth.access_token()
        post.assert_called_once()
        auth.tokens={'access_token':'fresh','expires_at':__import__('time').time()+3600};auth.needs_login=False
        self.assertEqual(auth.access_token(),'fresh')
    @patch('aster.core.requests.post')
    def test_silent_refresh_rotates_keyring_token(self,post):
        vault=Mock();vault.load.return_value='previous'
        auth=Auth('00000000-0000-0000-0000-000000000001',vault=vault)
        response=Mock(ok=True);response.json.return_value={'access_token':'access','refresh_token':'rotated','expires_in':3600};post.return_value=response
        self.assertEqual(auth.access_token(),'access');vault.save.assert_called_once_with('rotated')
        self.assertEqual(auth.access_token(),'access');post.assert_called_once()

if __name__=='__main__':unittest.main()
