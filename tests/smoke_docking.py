import traceback,os
from pathlib import Path
from ui_capture import capture
from gi.repository import GLib
from aster.app import Aster,Gtk
from aster import dockmodel as d
app=Aster();failed=[]
def step(i=0):
 try:
  if i==0:
   app.mail_list.select_row(app.mail_list.get_row_at_index(0));app.saved_reader=app.reader;app.saved_id=app.selected;app.show_section('calendar');app.saved_calendar=app.calendar_grid
   app.docks.move('calendar',d.location(app.docks.layout,'mail')['id'],'right')
   assert app.section=='calendar';assert app.reader is app.saved_reader;assert app.selected==app.saved_id;assert app.calendar_grid is app.saved_calendar
  elif i==1:
   assert app.docks.panels['mail'].get_mapped();assert app.docks.panels['calendar'].get_mapped()
   if os.environ.get('ASTER_SCREENSHOT_DIR'):capture(Path(os.environ['ASTER_SCREENSHOT_DIR'])/'cmail-docked-panels.png')
   app.docks.move('calendar');assert len(app.docks.windows)==1;assert app.calendar_grid is app.saved_calendar
  elif i==2:
   window=next(iter(app.docks.windows.values()));assert window.get_visible();window.close()
  elif i==3:
   assert not app.docks.windows;assert app.reader is app.saved_reader
   app.docks.move('contacts',d.location(app.docks.layout,'mail')['id'],'bottom');app.docks.move('drafts');app.docks.flush()
   assert len(list(d.groups(app.docks.layout)))==3
   app.win.maximize()
  elif i==4:
   app.win.unmaximize();app.docks.reset();assert app.docks.layout['tree']['tabs']==list(d.PANELS);assert not app.docks.windows
   print('PASS: split panels mapped together; persistent reader/calendar; pop-out and return; layout saved; maximize/restore; reset',flush=True);app.quit();return False
  GLib.timeout_add(500,step,i+1)
 except Exception:
  failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:GLib.timeout_add(700,step));app.run([])
if failed:raise SystemExit(1)
