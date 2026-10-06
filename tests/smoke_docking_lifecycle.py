"""Drag lifecycle and untouched-view mounting regression, with demo data."""
import traceback
from gi.repository import GLib
from aster.app import Aster,Gtk
from aster import dockmodel as d
app=Aster();failed=[];unmaps=[]
def step(i=0):
 try:
  if i==0:
   app.docks.move('calendar',d.location(app.docks.layout,'mail')['id'],'right')
   app.docks.panels['calendar'].connect('unmap',lambda *_:unmaps.append('calendar'))
   app.docks.dragging='contacts';snapshot=repr(app.docks.layout)
   app.docks.schedule_move('contacts');assert repr(app.docks.layout)==snapshot
   app.render_mail();assert app.mail_render_pending
   app.docks.finish_drag()
  elif i==1:
   assert len(app.docks.windows)==1;assert not unmaps,unmaps;assert not app.mail_render_pending
   source=d.location(app.docks.layout,'contacts')['id'];window=app.docks.windows[source]
   app.docks.move('drafts',d.location(app.docks.layout,'mail')['id'],'center',0)
   assert not unmaps,unmaps;assert app.docks.windows[source] is window
   app.docks.select('mail');group=app.docks.groups[d.location(app.docks.layout,'mail')['id']]
   child=group.header.get_first_child()
   while child and not (isinstance(child,Gtk.Button) and child.get_icon_name()=='window-new-symbolic'):child=child.get_next_sibling()
   assert child;child.emit('clicked')
  elif i==2:
   assert len(app.docks.windows)==2;assert not unmaps,unmaps
   print('PASS: move waits for drag-end; background mail redraw deferred; untouched Calendar remains mounted; existing float retained; visible pop-out button opens standalone Mail',flush=True)
   app.quit();return False
  GLib.timeout_add(500,step,i+1)
 except Exception:
  failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:GLib.timeout_add(500,step));app.run([])
if failed:raise SystemExit(1)
