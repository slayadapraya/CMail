"""Inline icon actions preserve message targets, folding and narrow windows."""
import os,traceback
if not os.environ.get('ASTER_DATA_DIR'):raise RuntimeError('Use a temporary ASTER_DATA_DIR')
from aster.app import Aster,Gtk,GLib
from aster import dockmodel as d
app=Aster();errors=[];calls=[];css_errors=[]
def children(w):
 c=w.get_first_child()
 while c:
  yield c;yield from children(c);c=c.get_next_sibling()
def capture(path,widget):
 paint=Gtk.WidgetPaintable.new(widget);snap=Gtk.Snapshot.new();paint.snapshot(snap,widget.get_width(),widget.get_height());node=snap.to_node()
 if node:app.win.get_renderer().render_texture(node,None).save_to_png(path)
def step(i=0):
 try:
  if i==0:
   app.css_provider.connect('parsing-error',lambda _,section,error:css_errors.append(str(error)));app.apply_theme();assert not css_errors,css_errors
   app.compose=lambda **kw:calls.append(('compose',kw));app.move_message=lambda m,target:calls.append(('move',m['id'],target));app.mark_unread=lambda m:calls.append(('unread',m['id']));app.flag_message=lambda m:calls.append(('flag',m['id']))
   app.mail_list.select_row(app.mail_list.get_row_at_index(0))
  elif i==1:
   expander=next(w for w in children(app.reader) if isinstance(w,Gtk.Expander));app.test_expander=expander
   actions=next(w for w in children(expander) if w.has_css_class('message-actions'));buttons=[w for w in children(actions) if isinstance(w,Gtk.Button)]
   assert len(buttons)==7,len(buttons);assert expander.get_expanded()
   for w in buttons:
    assert w.get_tooltip_text();assert not w.get_label();w.emit('clicked');assert expander.get_expanded()
   mid=app.selected_message['id'];assert calls[0][1]['reply']['id']==mid;assert calls[1][1]['reply_all'];assert calls[2][1]['forward']['id']==mid
   assert calls[3:]==[('move',mid,'archive'),('move',mid,'deleteditems'),('unread',mid),('flag',mid)],calls
   expander.set_expanded(False);expander.set_expanded(True)
   app.docks.move('mail');app.test_window=app.docks.windows[d.location(app.docks.layout,'mail')['id']];app.test_window.set_default_size(520,700)
  elif i==2:
   app.mail_panes.set_position(100)
  elif i==3:
   header=app.test_expander.get_label_widget();assert header.get_width()>0
   left=header.get_child_at_index(0);right=header.get_child_at_index(1)
   ok,bounds=right.compute_bounds(header);assert ok
   assert bounds.get_x()>=-1 and bounds.get_x()+bounds.get_width()<=header.get_width()+1,(header.get_width(),bounds.get_x(),bounds.get_width())
   assert not css_errors,css_errors
   capture('/tmp/cmail-inline-message-header.png',app.test_window.get_content())
   app.docks.move('mail',d.location(app.docks.layout,'calendar')['id'],'center');print('PASS: all seven icon actions target the selected message; folding works; native CSS parses; header fits a narrow standalone window and re-docks.',flush=True)
   app.quit();return False
  GLib.timeout_add(600,step,i+1)
 except Exception:
  errors.append(traceback.format_exc());print(errors[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:GLib.timeout_add(500,step));app.run([])
if errors:raise SystemExit(1)
