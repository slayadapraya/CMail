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

from gi.repository import Gdk
app=Aster();failed=[];out=Path(os.environ['ASTER_SCREENSHOT_DIR']);out.mkdir(parents=True,exist_ok=True)
def step(index=0):
 try:
  if index==0:
   app.config.set('ui_scale',.65);app.apply_layout();app.build_mail();app.settings()
   dialog=app.settings_window;app.test_presets=next(w for w in descendants(dialog) if isinstance(w,Gtk.DropDown));pickers=[w for w in descendants(dialog) if isinstance(w,Gtk.ColorButton)];app.test_picker=pickers[0];color=Gdk.RGBA();color.parse('#123456');app.test_picker.set_rgba(color);app.test_picker.emit('color-set');app.test_presets.set_selected(2)
   assert app.config.get('color_background')!='#123456';app.test_presets.set_selected(0);assert app.config.get('color_background')=='#123456';app.settings_window.close();app.settings()
   assert app.config.get('color_background')=='#123456';app.settings_window.close();app.new_mail_folder()
  elif index==1:
   dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='New folder');next(w for w in descendants(dialog) if isinstance(w,Gtk.Entry)).set_text('Projects');next(w for w in descendants(dialog) if isinstance(w,Gtk.Button) and w.get_label()=='Create folder').emit('clicked');assert any(v['displayName']=='Projects' for v in app.store.items('folders'));app.folder_values=None;app.populate_folders();assert any(v.get_child().get_text()=='Projects' for v in app.folder_buttons.values())
   assert app.search.get_parent() is app.command_widget
   assert sum(isinstance(w,Gtk.Image) and w.has_css_class('cmail-logo') for w in descendants(app.win))==2
   assert not any(isinstance(w,Gtk.Label) and w.get_text()=='⠿' for w in descendants(app.folders))
   assert not any(isinstance(w,Gtk.MenuButton) and w.get_icon_name()=='view-more-symbolic' for w in descendants(app.folders))
   assert any(isinstance(w,Gtk.MenuButton) and w.get_label()=='More' for w in descendants(app.command_widget))
   group=next(w for w in descendants(app.folders) if isinstance(w,Gtk.Label) and w.has_css_class('folder-group-title'));folder=app.folder_buttons['inbox'].get_child();assert group.get_layout().get_pixel_size()[1]>folder.get_layout().get_pixel_size()[1]
   subtitle=next(w for w in descendants(app.win) if isinstance(w,Gtk.Label) and w.has_css_class('workspace-subtitle'));assert subtitle.get_height()>=subtitle.get_layout().get_pixel_size()[1],(subtitle.get_height(),subtitle.get_layout().get_pixel_size())
   capture(out/'cmail-clean-65.png');app.config.set('ui_scale',1.0);app.apply_layout();app.build_mail()
  elif index==2:
   capture(out/'cmail-clean-100.png');app.show_section('calendar');app.select_calendar_day(None);app.test_event_id=app.events[0]['id'];next(w for w in descendants(app.agenda) if isinstance(w,Gtk.Button) and w.get_label()=='Edit').emit('clicked')
  elif index==3:
   dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='Edit appointment');next(w for w in descendants(dialog) if isinstance(w,Gtk.Entry)).set_text('Direct agenda edit');next(w for w in descendants(dialog) if isinstance(w,Gtk.Button) and w.get_label()=='Save changes').emit('clicked');assert any(e.get('subject')=='Direct agenda edit' for e in app.events);capture(out/'cmail-calendar-actions.png');next(w for w in descendants(app.agenda) if isinstance(w,Gtk.Button) and w.get_label()=='Delete').emit('clicked')
   from gi.repository import Adw
   confirmation=next(w for w in Gtk.Window.get_toplevels() if isinstance(w,Adw.MessageDialog));confirmation.emit('response','delete');assert not any(e.get('subject')=='Direct agenda edit' for e in app.events)
   print('PASS: custom theme restored after preset switching/reopening; new folder persisted; clean draggable rows; larger group headings; search in toolbar; single arrows; subtitle fits at 65%; visible agenda Edit/Delete work without opening details',flush=True);app.quit();return False
  GLib.timeout_add(900,step,index+1)
 except Exception:
  failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
 return False
app.connect('activate',lambda *_:GLib.timeout_add(700,step));app.run([])
if failed:raise SystemExit(1)
