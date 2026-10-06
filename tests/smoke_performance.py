"""Large mailbox + scrolling + unchanged refresh + bounded HTML surfaces."""
import time,traceback
from gi.repository import GLib
from aster.app import Aster,Gtk
from aster.mailhtml import viewer
import gi
gi.require_version('WebKit','6.0')
from gi.repository import WebKit
app=Aster();failed=[];gaps=[];previous=[time.monotonic()];started=[0]
def heartbeat():
 now=time.monotonic();gaps.append(now-previous[0]);previous[0]=now;return True
def step(i=0):
 try:
  if i==0:
   rows=[dict(id=str(n),subject='Synthetic mail '+str(n),receivedDateTime='2026-10-07T01:00:00Z',isRead=True,bodyPreview='Preview',**{'from':{'emailAddress':{'name':'Example sender','address':'fixture@example.invalid'}}}) for n in range(10000)]
   app.pool.submit(lambda:app.store.replace('mail','inbox',rows));GLib.timeout_add(500,step,1);return False
  elif i==1:
   started[0]=time.monotonic();app.render_mail()
  elif i==2:
   assert app.mail_list.items.get_n_items()==10000,app.mail_list.items.get_n_items();assert app.mail_list.created<500,app.mail_list.created
   assert not app.mail_build_running
   app.test_initial=time.monotonic()-started[0]
   parent=app.mail_list.get_parent()
   while not isinstance(parent,Gtk.ScrolledWindow):parent=parent.get_parent()
   app.test_adjustment=parent.get_vadjustment();app.test_n=0
   def scroll():
    app.test_n+=1;maximum=app.test_adjustment.get_upper()-app.test_adjustment.get_page_size();app.test_adjustment.set_value(maximum*app.test_n/30)
    if app.test_n>=30:return False
    return True
   GLib.timeout_add(30,scroll)
  elif i==3:
   app.test_bound=app.mail_list.bound;app.test_created=app.mail_list.created;app.test_changes=[];app.mail_list.items.connect('items-changed',lambda _,pos,removed,added:app.test_changes.append((pos,removed,added)));app.render_mail()
  elif i==4:
   assert not app.test_changes,app.test_changes
   assert app.mail_list.created<500,app.mail_list.created
   app.show_section('mail');app.mail_list.select_row(app.mail_list.get_row_at_index(0))
   def browser_count(root):
    count=int(isinstance(root,WebKit.WebView));child=root.get_first_child()
    while child:count+=browser_count(child);child=child.get_next_sibling()
    return count
   assert browser_count(app.reader)==0  # Native plain-text body.
   app.test_html=viewer('<p>Long message</p>'+''.join('<p>Paragraph '+str(n)+'</p>' for n in range(1000)),low_power=True)
   app.reader.append(app.test_html);app.set_reader_open(True)
  elif i==5:
   assert app.test_html.get_size_request()[1]<=900,app.test_html.get_size_request()
   assert app.test_html.get_settings().get_hardware_acceleration_policy()==WebKit.HardwareAccelerationPolicy.NEVER
   assert max(gaps)<1.5,max(gaps)
   app.test_html.evaluate_javascript("window.scrollTo(0,document.body.scrollHeight);window.webkit.messageHandlers.mailHeight.postMessage(document.body.scrollHeight)",-1,'cmailLayout',None,None,None,None)
   print('PASS: 10,000 cached conversations; %d recycled row shells; unchanged refresh mutates no model items; long HTML capped at 900px with hardware compositing off; largest UI gap %.3fs'%(app.mail_list.created,max(gaps)),flush=True)
   app.quit();return False
  GLib.timeout_add(1400,step,i+1)
 except Exception:
  failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:(GLib.timeout_add(50,heartbeat),GLib.timeout_add(500,step)));app.run([])
if failed:raise SystemExit(1)
