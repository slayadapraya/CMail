"""Native GTK integration smoke test, run with a temporary display and data directory."""
import ctypes
import ctypes.util
import os
from pathlib import Path
import traceback
from PIL import Image
from gi.repository import GLib
from aster.app import Aster, Gtk

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


import base64
from datetime import datetime,timezone
from aster.google import normalize_message,Gmail
from aster import mailhtml
app=Aster();failed=[];out=Path(os.environ['ASTER_SCREENSHOT_DIR']);out.mkdir(parents=True,exist_ok=True)
html='<h2>Meeting confirmation</h2><p>Hi Taylor, <b>your appointment is confirmed.</b></p><table style="border:1px solid #ddd"><tr><td style="padding:12px">Tuesday</td><td style="padding:12px">15:58 NZDT</td></tr></table><p><img src="cid:logo" alt="Test logo"></p><a href="https://example.com">View appointment</a><div class="gmail_quote">Earlier email text, collapsed separately.</div>'
def message(mid,tid,when,sender='Ann Example',address='ann@example.com',category='CATEGORY_PERSONAL'):
    return normalize_message({'id':mid,'threadId':tid,'internalDate':str(int(datetime.fromisoformat(when).timestamp()*1000)),'labelIds':['INBOX',category],'snippet':'Your appointment is confirmed.','payload':{'headers':[{'name':'From','value':sender+' <'+address+'>'},{'name':'To','value':'recipient@example.com'},{'name':'Subject','value':'Appointment conversation'}],'parts':[{'mimeType':'text/html','body':{'data':base64.urlsafe_b64encode(html.encode()).decode()}},{'partId':'p','filename':'logo.png','mimeType':'image/png','headers':[{'name':'Content-ID','value':'<logo>'}],'body':{'attachmentId':'logo','size':200}},{'partId':'q','filename':'Appointment.pdf','mimeType':'application/pdf','body':{'attachmentId':'pdf','size':123456}}]}})
fixture=[message('a','thread','2026-10-06T02:49:33+00:00'),message('b','thread','2026-10-06T02:58:00+00:00'),message('c','other','2026-10-05T23:00:00+00:00'),message('d','promotion','2026-10-06T03:00:00+00:00',category='CATEGORY_PROMOTIONS')]
reply=message('sent','thread','2026-10-06T02:56:00+00:00','Taylor Example','recipient@example.com');reply['labelIds']=['SENT']
from io import BytesIO
photo=Image.new('RGB',(64,64),'#ff7187');stream=BytesIO();photo.save(stream,format='PNG');data=base64.b64encode(stream.getvalue()).decode()
def step(index=0):
    try:
        if index==0:
            app.win.set_default_size(1600,1050);app.graph=Gmail(None);app.store.replace('mail','inbox',fixture);app.store.replace('thread','thread',[fixture[0],reply,fixture[1]])
            app.store.replace('inline','b',[{'id':'logo','contentId':'logo','url':'data:image/png;base64,'+data}]);app.store.replace('photos','',[{'id':'ann@example.com','data':data}]);app.build_mail()
            assert app.mail_list.get_row_at_index(0).message['id']=='d'
            app.mail_category.set_selected(1);assert app.mail_list.get_row_at_index(0).message['id']=='b'
            assert app.mail_list.get_row_at_index(0).message['count']==3
            app.mail_list.select_row(app.mail_list.get_row_at_index(0))
        elif index==1:
            capture(out/'threads-html.png')
            expanders=[w for w in descendants(app.reader) if isinstance(w,Gtk.Expander)];assert len(expanders)==3, (len(expanders),app.selected,app.mail_list.selection.get_selected(),app.mail_list.get_row_at_index(0).message["id"],app.reader_key);assert [e.get_expanded() for e in expanders]==[False,False,True]
            from gi.repository import Adw
            assert any(isinstance(w,Adw.Avatar) and w.get_custom_image() is not None for w in descendants(app.reader))
            assert any(isinstance(w,Gtk.Label) and '15:58 NZDT' in w.get_text() for w in descendants(app.reader))
            assert any(isinstance(w,Gtk.Label) and 'Appointment.pdf' in w.get_text() and '123 KB' in w.get_text() for w in descendants(app.reader))
            next(w for w in descendants(app.reader) if isinstance(w,Gtk.Button) and w.get_label()=='Collapse all').emit('clicked');assert not any(e.get_expanded() for e in expanders)
            next(w for w in descendants(app.reader) if isinstance(w,Gtk.Button) and w.get_label()=='Expand all').emit('clicked');assert all(e.get_expanded() for e in expanders)
            from gi.repository import WebKit
            views=[w for w in descendants(app.reader) if isinstance(w,WebKit.WebView)];assert len(views)==3
            assert all(not v.get_settings().get_enable_javascript_markup() for v in views)
            app.config.set('split_right',480);app.config.set('gmail_category',1);app.build_mail();assert app.mail_category.get_selected()==1
            print('PASS: native Gmail grouping/category, sent reply, local NZ time, collapsed thread controls, profile photo, WebKit HTML/CID and attachment card',flush=True);app.quit();return False
        GLib.timeout_add(1800,step,index+1)
    except Exception:
        failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
    return False
app.connect('activate',lambda *_:GLib.timeout_add(600,step));app.run([])
if failed:raise SystemExit(1)
