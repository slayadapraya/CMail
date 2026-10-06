import subprocess,time,traceback,os
from gi.repository import GLib
from aster.app import Aster,Gtk
from aster import dockmodel as d
app=Aster();failed=[];latencies=[];previous=[time.monotonic()]
def heartbeat():
 now=time.monotonic();latencies.append(now-previous[0]);previous[0]=now;return True
def drag(start,end):
 subprocess.run(['xdotool','mousemove',str(start[0]),str(start[1]),'mousedown','1'],check=True)
 for i in range(1,21):
  x=round(start[0]+(end[0]-start[0])*i/20);y=round(start[1]+(end[1]-start[1])*i/20)
  subprocess.run(['xdotool','mousemove',str(x),str(y)],check=True);time.sleep(.04)
 subprocess.run(['xdotool','mouseup','1'],check=True)
def point(widget,x=.5,y=.5,root=None):
 ok,b=widget.compute_bounds(root or app.win);assert ok;return (round(b.get_x()+b.get_width()*x),round(b.get_y()+b.get_height()*y))
def step(i=0):
 try:
  group=app.docks.groups[d.location(app.docks.layout,'mail')['id']]
  if i==0:app.pool.submit(drag,point(group.buttons['calendar']),point(group.root,.95,.55))
  elif i==1:
   assert app.docks.layout['tree']['kind']=='split',app.docks.layout
   assert app.docks.panels['calendar'].get_mapped();app.show_section('mail');app.mail_list.select_row(app.mail_list.get_row_at_index(0));app.saved_reader=app.reader
   app.pool.submit(drag,point(group.buttons['contacts']), (1600,1100))
  elif i==2:
   assert len(app.docks.windows)==1,app.docks.layout
   for n in range(12):app.win.set_default_size(1100+n*15,760+n*8)
   app.win.maximize()
  elif i==3:
   app.win.unmaximize();assert app.reader is app.saved_reader
   assert max(latencies)<1.5,max(latencies)
   float_group=app.docks.groups[d.location(app.docks.layout,'contacts')['id']];window=app.docks.parent('contacts');calendar_group=app.docks.groups[d.location(app.docks.layout,'calendar')['id']]
   app.pool.submit(drag,point(float_group.buttons['contacts'],root=window),point(calendar_group.root,.55,.55))
  elif i==4:
   assert not app.docks.windows,app.docks.layout
   assert d.location(app.docks.layout,'contacts') is d.location(app.docks.layout,'calendar')
   app.docks.flush();print('PASS: real mouse edge docking; outside pop-out; dragging back groups tabs; resize/maximize preserve reader; largest UI heartbeat gap %.3fs'%max(latencies),flush=True)
   app.quit();return False
  GLib.timeout_add(1600,step,i+1)
 except Exception:
  failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:(GLib.timeout_add(50,heartbeat),GLib.timeout_add(600,step)));app.run([])
if failed:raise SystemExit(1)
