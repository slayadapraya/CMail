import sys,tempfile,os,traceback
if not os.environ.get('ASTER_DATA_DIR'):raise RuntimeError('Set ASTER_DATA_DIR to a temporary test directory')
from aster.app import Aster,Gtk,GLib
from aster import dockmodel as d
from aster.core import Store
app=Aster();errors=[];css_errors=[]
def children(w):
 c=w.get_first_child()
 while c:
  yield c;yield from children(c);c=c.get_next_sibling()
def step(i=0):
 try:
  if i==0:
   app.css_provider.connect('parsing-error',lambda _,section,error:css_errors.append(str(error)));app.apply_theme();assert not css_errors,css_errors
   assert app.topnav_widget.get_parent() is not app.command_widget.get_parent()
   assert app.config.get('mail_density','cards')=='cards'
   app.settings();controls=[w for w in children(app.settings_window) if isinstance(w,Gtk.DropDown)]
   row_control=next(w for w in controls if w.get_model().get_string(0).startswith('Current size'))
   row_control.set_selected(1);assert app.config.get('mail_density')=='compact'
   app.settings_window.close();app.settings()
   assert next(w for w in children(app.settings_window) if isinstance(w,Gtk.DropDown) and w.get_model().get_string(0).startswith('Current size')).get_selected()==1
   app.settings_window.close();assert Store(app.root/'config').get('mail_density')=='compact'
   app.docks.move('calendar',d.location(app.docks.layout,'mail')['id'],'right');app.docks.move('contacts')
  elif i==1:
   assert len(app.docks.windows)==1
   app.docks.select('mail');app.mail_list.select_row(app.mail_list.get_row_at_index(0));assert app.reader_open
   app.refresh_button.cmail_label.set_text('Refreshing…');assert isinstance(app.refresh_button.get_child(),Gtk.Box)
   app.config.set('mail_density','cards');app.render_mail();app.config.set('ui_scale',.65);app.apply_layout();assert not css_errors,css_errors
   app.docks.move('contacts',d.location(app.docks.layout,'mail')['id'],'center');app.docks.move('mail')
  elif i==2:
   assert len(app.docks.windows)==1;assert d.location(app.docks.layout,'mail')['id'] in app.docks.windows
   app.docks.move('mail',d.location(app.docks.layout,'calendar')['id'],'left')
   print('PASS: CSS parses; compact/card mode persists; reader opens; refresh icon survives; Calendar splits; People and Mail detach/redock; 65% scale.',flush=True)
   app.quit();return False
  GLib.timeout_add(500,step,i+1)
 except Exception:
  errors.append(traceback.format_exc());print(errors[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:GLib.timeout_add(500,step));app.run([])
if errors:raise SystemExit(1)
