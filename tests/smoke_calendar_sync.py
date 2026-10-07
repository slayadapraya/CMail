"""Calendar loads independently of a paused or failing Gmail import."""
import os,time,traceback
if not os.environ.get('ASTER_DATA_DIR'):raise RuntimeError('Use a temporary ASTER_DATA_DIR')
from aster.app import Aster,GLib
from aster.google import Gmail
from aster.core import AppError
from unittest.mock import Mock
app=Aster();failures=[];calls=[]
fixture={'id':'calendar-fixture','subject':'Synthetic appointment','start':{'dateTime':'2026-10-07T10:00:00+13:00'},'end':{'dateTime':'2026-10-07T11:00:00+13:00'}}
def calendar(*_):calls.append('calendar');return [fixture]
def broken_mail(*_,**kwargs):calls.append('mail');raise AppError('Synthetic inbox failure')
def step(i=0):
 try:
  if i==0:
   app.graph=Gmail(Mock());app.graph.calendar=calendar;app.graph.sync_mail=broken_mail;app.mode='live';app.graph.backoff_until=time.time()+600
   app.show_section('calendar')
  elif i==1:
   assert calls==['calendar'],calls
   assert app.store.items('events',app.current_month.strftime('%Y-%m'))[0]['id']=='calendar-fixture'
   app.graph.backoff_until=0;app.refresh(section='mail');app.refresh(section='calendar')
  elif i==2:
   assert calls==['calendar','mail','calendar'],calls
   assert not app.syncing and not app.pending_sections
   assert app.status.get_text().startswith('Calendar updated'),app.status.get_text()
   print('PASS: Calendar loads while Gmail is paused, bypasses mail sync, and survives a queued inbox failure.',flush=True);app.quit();return False
  GLib.timeout_add(700,step,i+1)
 except Exception:
  failures.append(traceback.format_exc());print(failures[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:GLib.timeout_add(500,step));app.run([])
if failures:raise SystemExit(1)
