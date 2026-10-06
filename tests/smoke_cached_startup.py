import os,traceback,time
from pathlib import Path
from aster.core import Store
from aster.app import Aster
from gi.repository import GLib
root=Path(os.environ['ASTER_DATA_DIR']);cached=Store(root/'accounts'/'fixture');cached.replace('mail','inbox',[dict(id='cached-one',subject='Immediately available cached mail',receivedDateTime='2026-10-07T00:00:00Z',isRead=True)])
config=Store(root/'config');config.set('mode','live');config.set('last_account',dict(path=str(cached.root),client_id='fixture',provider='google',profile=dict(mail='fixture@example.invalid')))
app=Aster();app.connect_account=lambda **kwargs:None;failed=[]
def check():
 try:
  assert app.mode=='live';assert app.store.root==cached.root
  assert app.mail_list.get_row_at_index(0).message['id']=='cached-one';assert 'DEMO' not in app.banner.get_text();assert app.account_label.get_text()=='fixture@example.invalid'
  print('PASS: cached account and emails visible before any connection attempt completes',flush=True)
 except Exception:failed.append(traceback.format_exc());print(failed[-1],flush=True)
 app.quit();return False
app.connect('activate',lambda *_:GLib.timeout_add(100,check));app.run([])
if failed:raise SystemExit(1)
