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

app=Aster();failed=[];out=Path(os.environ['ASTER_SCREENSHOT_DIR']);out.mkdir(parents=True,exist_ok=True)
def step(index=0):
    try:
        if index==0:
            assert app.settings_button.get_parent() is app.rail_widget
            assert app.settings_button.get_icon_name()=='emblem-system-symbolic'
            assert not any(w.has_css_class('formatbar') for w in descendants(app.win))
            app.config.set('ui_scale',1.0);app.apply_layout();app.build_mail()
        elif index==1:
            app.baseline_height=app.mail_list.get_row_at_index(0).get_height();app.settings()
            controls=[w for w in descendants(app.settings_window) if isinstance(w,Gtk.Scale)]
            controls[0].set_value(65);assert app.config.get('ui_scale')==.65
            from aster.theme import PRESETS
            dropdown=next(w for w in descendants(app.settings_window) if isinstance(w,Gtk.DropDown))
            dropdown.set_selected(2);assert app.config.get('theme_preset')=='Cyber Mint';assert app.config.get('color_accent')==PRESETS['Cyber Mint']['accent']
            app.settings_window.close()
        elif index==2:
            assert app.mail_list.get_row_at_index(0).get_height()<app.baseline_height
            app.config.set('ui_scale',.8);app.apply_layout();app.build_mail();capture(out/'compact-mint.png')
            app.show_section('calendar');event=app.events[0];from aster.core import event_datetime
            app.test_date=event_datetime(event['start']).date();app.calendar_days[app.test_date.day].emit('clicked')
            assert app.calendar_selected==app.test_date
            assert app.test_date.strftime('%A %d %B')==app.agenda_title.get_text()
            next(w for w in descendants(app.agenda) if isinstance(w,Gtk.Button)).emit('clicked')
        elif index==3:
            dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='Appointment details');assert dialog.get_visible();dialog.close();capture(out/'calendar-day.png')
            app.new_event();dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='New appointment')
            fields=[w for w in descendants(dialog) if isinstance(w,Gtk.Entry)];assert fields[1].get_text()==app.test_date.isoformat();dialog.close()
            app.show_section('mail');app.compose()
        elif index==4:
            win=next(iter(app.compose_windows));assert win.format_toolbar.get_parent() is win.get_content()
            assert win.format_toolbar.get_prev_sibling().__class__.__name__=='HeaderBar'
            win.editor.buffer.set_text('Compact formatted message');win.editor.buffer.select_range(win.editor.buffer.get_start_iter(),win.editor.buffer.get_end_iter());win.editor.format('bold');assert 'font-weight:bold' in win.editor.snapshot()[2]
            capture(out/'compact-composer.png');win.close();assert not any(w.has_css_class('formatbar') for w in descendants(app.win))
            app.settings();assert app.config.get('ui_scale')==.8 and app.config.get('theme_preset')=='Cyber Mint';app.settings_window.close()
            print('PASS: measured scale reduction, saved theme/scale, bottom rail gear, clickable day agenda/details and prefilled date, compact contextual composer toolbar',flush=True);app.quit();return False
        GLib.timeout_add(700,step,index+1)
    except Exception:
        failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
    return False
app.connect('activate',lambda *_:GLib.timeout_add(600,step));app.run([])
if failed:raise SystemExit(1)
