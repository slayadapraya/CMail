"""Native productivity controls: scale, themes, rail settings and calendar agenda."""
import os,traceback,ctypes,ctypes.util
from PIL import Image
from pathlib import Path
from gi.repository import GLib
from aster.app import Aster,Gtk
def capture(path):
    lib=ctypes.CDLL(ctypes.util.find_library('X11'))
    lib.XOpenDisplay.argtypes=[ctypes.c_char_p];lib.XOpenDisplay.restype=ctypes.c_void_p
    display=lib.XOpenDisplay(None)
    if not display:raise RuntimeError('No virtual display')
    lib.XDefaultScreen.argtypes=[ctypes.c_void_p];screen=lib.XDefaultScreen(display)
    for name in ('XDisplayWidth','XDisplayHeight'):
        getattr(lib,name).argtypes=[ctypes.c_void_p,ctypes.c_int]
    width=lib.XDisplayWidth(display,screen);height=lib.XDisplayHeight(display,screen)
    lib.XRootWindow.argtypes=[ctypes.c_void_p,ctypes.c_int];lib.XRootWindow.restype=ctypes.c_ulong
    root=lib.XRootWindow(display,screen)
    class XImage(ctypes.Structure):
        _fields_=[('width',ctypes.c_int),('height',ctypes.c_int),('xoffset',ctypes.c_int),('format',ctypes.c_int),('data',ctypes.c_void_p),('byte_order',ctypes.c_int),('bitmap_unit',ctypes.c_int),('bitmap_bit_order',ctypes.c_int),('bitmap_pad',ctypes.c_int),('depth',ctypes.c_int),('bytes_per_line',ctypes.c_int),('bits_per_pixel',ctypes.c_int),('red_mask',ctypes.c_ulong),('green_mask',ctypes.c_ulong),('blue_mask',ctypes.c_ulong)]
    lib.XGetImage.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_int,ctypes.c_uint,ctypes.c_uint,ctypes.c_ulong,ctypes.c_int];lib.XGetImage.restype=ctypes.POINTER(XImage)
    image=lib.XGetImage(display,root,0,0,width,height,ctypes.c_ulong(-1).value,2)
    raw=ctypes.string_at(image.contents.data,image.contents.bytes_per_line*height)
    Image.frombytes('RGB',(width,height),raw,'raw','BGRX',image.contents.bytes_per_line).save(path)
    lib.XDestroyImage.argtypes=[ctypes.POINTER(XImage)];lib.XDestroyImage(image)
    lib.XCloseDisplay.argtypes=[ctypes.c_void_p];lib.XCloseDisplay(display)

def descendants(widget):
    child=widget.get_first_child()
    while child:
        yield child;yield from descendants(child);child=child.get_next_sibling()

from aster.google import Gmail
import gi
gi.require_version('WebKit','6.0')
from gi.repository import WebKit,Adw,Gdk
app=Aster();failed=[];out=Path(os.environ['ASTER_SCREENSHOT_DIR']);out.mkdir(parents=True,exist_ok=True)
def buttons(widget,text):return next(w for w in descendants(widget) if isinstance(w,Gtk.Button) and w.get_label()==text)
def step(index=0):
    try:
        if index==0:
            app.config.set('low_power',False)  # Exercise the optional full-height reader.
            assert app.win.get_title()=='CMail'
            assert not app.reader_revealer.get_reveal_child()
            assert app.mail_panes.get_start_child().get_width()>=app.mail_panes.get_width()-15
            assert app.command_widget.get_height()<45
            app.graph=Gmail(None)
            long='<p>Long email starts here.</p>'+''.join('<p>Paragraph '+str(i)+' — enough text to make this email much longer than a fixed reader box.</p>' for i in range(65))+'<details><summary>Quoted text</summary>'+''.join('<p>Quote paragraph</p>' for _ in range(30))+'</details>'
            message={'id':'long','threadId':'thread','subject':'Dynamic message height','from':{'emailAddress':{'name':'Ann Example','address':'ann@example.com'}},'receivedDateTime':'2026-10-06T01:00:00Z','body':{'contentType':'HTML','content':long},'htmlBody':long,'bodyPreview':'Long email starts here.','isRead':True,'labelIds':['INBOX']}
            app.store.replace('mail','inbox',[message]);app.store.replace('thread','thread',[message]);app.render_mail();app.mail_list.select_row(app.mail_list.get_row_at_index(0))
        elif index==1:
            ratio=app.mail_panes.get_position()/app.mail_panes.get_width();assert .22<ratio<.30,ratio
            view=next(w for w in descendants(app.reader) if isinstance(w,WebKit.WebView));app.test_view=view
            app.test_height=view.get_size_request()[1];assert app.test_height>1400,app.test_height
            view.evaluate_javascript("document.querySelector('details').open=true",-1,'cmailLayout',None,None,None,None)
        elif index==2:
            assert app.test_view.get_size_request()[1]>app.test_height+200
            capture(out/'cmail-thread.png');buttons(app.reader,'← Inbox').emit('clicked')
        elif index==3:
            assert not app.reader_revealer.get_reveal_child();assert app.mail_panes.get_start_child().get_width()>=app.mail_panes.get_width()-15
            app.populate_folders([{'id':'inbox','displayName':'Inbox'},{'id':'sentitems','displayName':'Sent'},{'id':'work','displayName':'Work'},{'id':'travel','displayName':'Travel'}]);app.reorder_folder('travel','work');assert app.folder_layout()['order'].index('travel')<app.folder_layout()['order'].index('work')
            app.new_folder_group();dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='New folder group');next(w for w in descendants(dialog) if isinstance(w,Gtk.Entry)).set_text('Projects');buttons(dialog,'Create group').emit('clicked');assert 'Projects' in app.folder_layout()['custom_groups']
            expander=next(w for w in descendants(app.folders) if isinstance(w,Gtk.Expander) and w.get_label()=='Projects');controllers=expander.observe_controllers();drop=next(controllers.get_item(i) for i in range(controllers.get_n_items()) if isinstance(controllers.get_item(i),Gtk.DropTarget));assert drop.emit('drop','work',0.,0.)
            app.manage_folders();dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='Show / hide folders');check=next(w for w in descendants(dialog) if isinstance(w,Gtk.CheckButton) and w.get_label()=='Travel');check.set_active(False);assert 'travel' not in app.folder_buttons;check.set_active(True);assert 'travel' in app.folder_buttons;dialog.close()
            app.populate_folders(app.folder_values);assert app.folder_layout()['groups']['work']=='Projects';capture(out/'cmail-inbox.png')
            app.graph=None;app.show_section('calendar');app.test_event=app.events[0];app.new_event(event=app.test_event)
        elif index==4:
            dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='Edit appointment');fields=[w for w in descendants(dialog) if isinstance(w,Gtk.Entry)];fields[0].set_text('Edited appointment');buttons(dialog,'Save changes').emit('clicked');assert any(e['subject']=='Edited appointment' and e['id']==app.test_event['id'] for e in app.events)
            updated=next(e for e in app.events if e['id']==app.test_event['id']);app.delete_calendar_event(updated)
            dialog=next(w for w in Gtk.Window.get_toplevels() if isinstance(w,Adw.MessageDialog));dialog.emit('response','delete');assert not any(e['id']==updated['id'] for e in app.events);app.render_calendar();assert not any(e['id']==updated['id'] for e in app.events)
            app.show_section('mail');app.compose();win=next(iter(app.compose_windows));win.editor.buffer.set_text('White text');win.editor.buffer.select_range(win.editor.buffer.get_start_iter(),win.editor.buffer.get_end_iter());win.editor.format('white');assert 'color:#ffffff' in win.editor.snapshot()[2];win.close()
            app.mode='live';app.graph=Gmail(None);app.graph.backoff_until=9999999999
            from unittest.mock import Mock
            app.graph.api=Mock(side_effect=[{'id':'draft'},{'id':'real-sent','threadId':'thread'}]);original=app.store.items('thread','thread')[0];app.graph.message=Mock(return_value=original);app.graph.thread=Mock(return_value=[original]);app.render_mail();app.mail_list.select_row(app.mail_list.get_row_at_index(0));app.compose(reply=original);win=next(iter(app.compose_windows));win.editor.buffer.set_text('Confirmed reply appears immediately');buttons(win,'Send').emit('clicked')
        elif index==5:
            assert app.mail_list.get_row_at_index(0).message['count']==2
            assert app.mail_list.get_row_at_index(0).message['id']=='real-sent'
            expanders=[w for w in descendants(app.reader) if isinstance(w,Gtk.Expander)];assert len(expanders)==2 and expanders[-1].get_expanded()
            assert not app.compose_windows
            print('PASS: immediate confirmed reply before inbox refresh, CMail branding, full inbox, animated quarter reader, compact commands, long adaptive HTML + expanding quotes, folder group/drop/order/hide persistence, calendar edit/delete persistence and white text',flush=True);app.quit();return False
        GLib.timeout_add(1500,step,index+1)
    except Exception:
        failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
    return False
app.connect('activate',lambda *_:GLib.timeout_add(800,step));app.run([])
if failed:raise SystemExit(1)
