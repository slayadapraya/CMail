import os,traceback
from pathlib import Path
from aster.core import Store
from aster.app import Aster
from aster import dockmodel as d
from gi.repository import GLib
config=Store(Path(os.environ['ASTER_DATA_DIR'])/'config');layout=d.default();d.move(layout,'calendar',layout['tree']['id'],'right');d.move(layout,'contacts');config.set('dock_layout',layout)
app=Aster();failed=[]
def check():
 try:
  assert len(app.docks.windows)==1;assert app.docks.panels['calendar'].get_mapped();assert app.docks.panels['mail'].get_mapped();assert app.section=='contacts';assert len(list(d.groups(app.docks.layout)))==3
  app.select_folder('sentitems');assert app.folder=='sentitems';assert app.section=='mail';assert 'Messages' in app.mail_title.get_text()
  print('PASS: saved split and detached panels restored at startup; folder selection updates persistent Mail view',flush=True)
 except Exception:failed.append(traceback.format_exc());print(failed[-1],flush=True)
 app.quit();return False
app.connect('activate',lambda *_:GLib.timeout_add(700,check));app.run([])
if failed:raise SystemExit(1)
