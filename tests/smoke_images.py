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

import threading
from http.server import HTTPServer,BaseHTTPRequestHandler
from io import BytesIO
stream=BytesIO();Image.new('RGB',(30,30),'#7aa2f7').save(stream,format='PNG');png=stream.getvalue();requests_seen=[]
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  requests_seen.append(self.path);self.send_response(200);self.send_header('Content-Type','image/png');self.end_headers();self.wfile.write(png)
 def log_message(self,*args):pass
server=HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
app=Aster();failed=[]
def step(index=0):
 try:
  if index==0:
   html='<p>Image loads automatically.</p><img width="30" height="30" src="http://127.0.0.1:'+str(server.server_port)+'/test.png">'
   msg={'id':'image','subject':'Automatic images','receivedDateTime':'2026-10-06T01:00:00Z','from':{'emailAddress':{'name':'Example','address':'example@example.com'}},'isRead':True,'htmlBody':html,'body':{'contentType':'HTML','content':html}}
   app.store.replace('mail','inbox',[msg]);app.render_mail();app.mail_list.select_row(app.mail_list.get_row_at_index(0))
  elif index==1:
   assert '/test.png' in requests_seen;assert not any(isinstance(w,Gtk.Button) and w.get_label()=='Load remote images for this message' for w in descendants(app.reader));app.image_count=len(requests_seen)
   app.settings();check=next(w for w in descendants(app.settings_window) if isinstance(w,Gtk.CheckButton) and w.get_label()=='Load email images automatically');check.set_active(False);app.settings_window.close()
  elif index==2:
   assert len(requests_seen)==app.image_count;assert any(isinstance(w,Gtk.Button) and w.get_label()=='Load remote images for this message' for w in descendants(app.reader));assert app.config.get('load_remote_images') is False
   print('PASS: remote image fetched automatically from local fixture server; no manual button by default; saved Settings opt-out blocks further requests',flush=True);app.quit();return False
  GLib.timeout_add(1300,step,index+1)
 except Exception:
  failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:GLib.timeout_add(600,step));app.run([]);server.shutdown()
if failed:raise SystemExit(1)
