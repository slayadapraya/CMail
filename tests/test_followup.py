"""Confirmed send caching and calendar mutations, using fake provider responses."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from aster.google import Gmail
from aster.core import Store,Graph,AppError,AmbiguousSend
class FollowupTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name));self.gmail=Gmail(SimpleNamespace(calendar_enabled=True))
 def tearDown(self):self.temp.cleanup()
 def draft(self):return {'id':'d','to':'Ann <ann@example.com>','subject':'Re: Hello','body':'Immediate reply','html':'<p>Immediate reply</p>','reply_id':'old','sender':{'name':'Me','address':'me@example.com'}}
 def test_confirmed_reply_cached_immediately_and_reconciles_by_real_id(self):
  original={'id':'old','threadId':'thread','message_id':'<old@example.com>','receivedDateTime':'2026-10-06T01:00:00Z'};self.store.replace('thread','thread',[original]);self.gmail.message=Mock(return_value=original)
  self.gmail.api=Mock(side_effect=[{'id':'remote-draft'},{'id':'sent-real','threadId':'thread'}]);draft=self.gmail.send(self.store,self.draft())
  self.assertEqual(draft['sent_message_id'],'sent-real');messages=self.store.items('thread','thread');self.assertEqual([m['id'] for m in messages],['old','sent-real']);self.assertEqual(messages[-1]['body']['content'],'<p>Immediate reply</p>');self.assertEqual(self.store.drafts()[0]['state'],'accepted');self.assertEqual(self.gmail.api.call_count,2)
  self.store.delta('sentitems',[dict(messages[-1],localConfirmed=False)],'new');self.assertEqual(len(self.store.items('mail','sentitems')),1)
 def test_ambiguous_reply_never_shown_as_sent(self):
  self.gmail.message=Mock(return_value={'id':'old','threadId':'thread'});self.gmail.api=Mock(side_effect=[{'id':'remote'},AmbiguousSend('unknown')])
  with self.assertRaises(AmbiguousSend):self.gmail.send(self.store,self.draft())
  self.assertEqual(self.store.items('thread','thread'),[]);self.assertEqual(self.store.items('mail','sentitems'),[])
 def test_cache_failure_does_not_allow_resend(self):
  self.gmail.message=Mock(return_value={'id':'old','threadId':'thread'});self.gmail.api=Mock(side_effect=[{'id':'remote'},{'id':'sent','threadId':'thread'}]);self.store.delta=Mock(side_effect=OSError('disk full'));draft=self.gmail.send(self.store,self.draft());self.assertTrue(draft['cache_warning']);self.assertEqual(self.store.drafts()[0]['state'],'accepted')
  with self.assertRaises(AppError):self.gmail.send(self.store,draft)
 def event(self):return {'subject':'Edited','start':{'dateTime':'2026-10-07T00:00:00+13:00','timeZone':'NZDT'},'end':{'dateTime':'2026-10-08T00:00:00+13:00','timeZone':'NZDT'},'location':{'displayName':'Home'},'isAllDay':True}
 def test_google_all_day_create_edit_and_delete(self):
  self.gmail.api=Mock();data=self.event();self.gmail.create_event(data);self.assertEqual(self.gmail.api.call_args.args[2]['start'],{'date':'2026-10-07'});self.gmail.update_event('a/b',data);call=self.gmail.api.call_args;self.assertEqual(call.args[:2],('PATCH','calendars/primary/events/a%2Fb'));self.assertEqual(call.args[2]['end'],{'date':'2026-10-08'});self.gmail.delete_event('a/b');self.assertEqual(self.gmail.api.call_args.args,('DELETE','calendars/primary/events/a%2Fb'))
 def test_graph_all_day_uses_valid_midnight_timezone(self):
  graph=Graph.__new__(Graph);graph.request=Mock();graph.update_event('event',self.event());payload=graph.request.call_args.args[2];self.assertEqual(payload['start'],{'dateTime':'2026-10-07T00:00:00','timeZone':'UTC'});self.assertTrue(payload['isAllDay']);graph.delete_event('event');self.assertEqual(graph.request.call_args.args,('DELETE','/me/events/event'))
