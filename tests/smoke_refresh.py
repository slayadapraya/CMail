"""Refresh queue, bounded import dispatch and quota pause with no network calls."""
import time,threading,traceback
from unittest.mock import Mock
from gi.repository import GLib
from aster.app import Aster
from aster.google import Gmail
app=Aster();failed=[];release=threading.Event();calls=[]
def sync(store,folder,progress=None,batch_limit=None):
    calls.append((folder,batch_limit))
    if len(calls)==1:assert release.wait(4)
    store.delta('inbox',[{'id':'fresh','subject':'New mail fixture','receivedDateTime':'2026-10-06T03:00:00Z','isRead':True}],'100')
def step(index=0):
    try:
        if index==0:
            app.graph=Gmail(None);app.graph.sync_mail=sync;app.mode='live';app.config.set('notifications',False)
            app.refresh_button.emit('clicked');assert app.syncing
            app.refresh_button.emit('clicked');assert app.refresh_pending
            release.set()
        elif index==1:
            assert calls==[('inbox',1),('inbox',1)];assert not app.syncing
            assert 'every 10 seconds' in app.status.get_text();assert app.refresh_button.get_label()=='↻  Refresh'
            app.graph.backoff_until=time.time()+65
            app.refresh_button.emit('clicked');assert not app.syncing and len(calls)==2
            assert 'Google quota pause' in app.status.get_text()
            app.tick();assert len(calls)==2
            print('PASS: Refresh button queues a second check; bounded Gmail import; ten-second polling status; quota countdown prevents further calls',flush=True)
            app.graph=None;app.mode='demo';app.quit();return False
        GLib.timeout_add(800,step,index+1)
    except Exception:
        failed.append(traceback.format_exc());print(failed[-1],flush=True);release.set();app.quit()
    return False
app.connect('activate',lambda *_:GLib.timeout_add(500,step));app.run([])
if failed:raise SystemExit(1)
