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

app=Aster();results=[];failed=[];out=Path(os.environ['ASTER_SCREENSHOT_DIR']);out.mkdir(parents=True,exist_ok=True)
def step(index=0):
    try:
        if index==0:
            assert app.mode=='demo';assert len(app.store.items('mail','inbox'))==5
            app.mail_list.select_row(app.mail_list.get_row_at_index(0))
        elif index==1:
            capture(out/'inbox.png');app.show_section('calendar')
        elif index==2:
            assert len(app.events)==3;capture(out/'calendar.png');app.change_month(1);app.change_month(-1);app.new_event()
            dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='New appointment')
            fields=[w for w in descendants(dialog) if isinstance(w,Gtk.Entry)]
            fields[0].set_text('Smoke test appointment')
            next(w for w in descendants(dialog) if isinstance(w,Gtk.Button) and w.get_label()=='Create appointment').emit('clicked')
            assert any(e.get('subject')=='Smoke test appointment' for e in app.store.items('events',__import__('datetime').datetime.now().strftime('%Y-%m')))
            app.show_section('contacts')
        elif index==3:
            assert len(app.store.items('contacts'))==5;app.add_contact()
            dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='Add contact')
            fields=[w for w in descendants(dialog) if isinstance(w,Gtk.Entry)]
            fields[0].set_text('Smoke Person');fields[1].set_text('smoke@example.com')
            next(w for w in descendants(dialog) if isinstance(w,Gtk.Button) and w.get_label()=='Save contact').emit('clicked')
            assert len(app.store.items('contacts'))==6
            app.compose(to='maya@example.com')
        elif index==4:
            win=next(iter(app.compose_windows));capture(out/'composer.png');fields=[w for w in descendants(win) if isinstance(w,Gtk.Entry)]
            win.recipient_fields['to'].set_text('alex@example.com');win.recipient_fields['subject'].set_text('A draft worth keeping')
            text=next(w for w in descendants(win) if isinstance(w,Gtk.TextView));text.get_buffer().set_text('Recover this local draft.');win.close()
            assert any(d.get('body')=='Recover this local draft.' for d in app.store.drafts())
            app.compose(draft=app.store.drafts()[0])
        elif index==5:
            win=next(iter(app.compose_windows))
            next(w for w in descendants(win) if isinstance(w,Gtk.Button) and w.get_label()=='Simulate send').emit('clicked')
            assert app.store.drafts()[0]['state']=='accepted';app.show_section('drafts');app.settings()
        elif index==6:
            settings=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='Settings · CMail')
            switch=next(w for w in descendants(settings) if isinstance(w,Gtk.Switch));switch.set_active(False);switch.set_active(True)
            assert app.config.get('dark')
            ai_toggle=next(w for w in descendants(settings) if isinstance(w,Gtk.CheckButton) and w.get_label()=='Show AI features')
            ai_toggle.set_active(False);assert not app.assistant_button.get_visible() and not app.chatgpt_button.get_visible();assert app.config.get('show_ai') is False
            app.assistant();assert app.assistant_window is None
            ai_toggle.set_active(True);assert app.assistant_button.get_visible() and app.chatgpt_button.get_visible()
            assert app.settings_window is settings
            app.settings_button.emit('clicked');assert app.settings_window is None
            app.settings_button.emit('clicked');assert app.settings_window is not None
            assert sum(w.get_title()=='Settings · CMail' and w.get_visible() for w in Gtk.Window.get_toplevels())==1
            settings=app.settings_window
            exits=[w for w in descendants(settings) if isinstance(w,Gtk.Button) and 'Close' in (w.get_label() or '')]
            assert len(exits)==1;exits[0].emit('clicked');assert app.settings_window is None
            app.config.set('color_accent','#55ffcc');app.apply_theme();app.config.set('color_accent',None);app.apply_theme()
            app.config.set('show_sidebar',False);app.apply_layout();assert not app.sidebar_widget.get_visible()
            app.config.set('show_sidebar',True);app.apply_layout()
            app.config.set('pane_bottom',True);app.build_mail();app.config.set('pane_bottom',False);app.build_mail()
            from aster.richtext import RichEditor
            editor=RichEditor(text='<hello>');editor.buffer.select_range(editor.buffer.get_start_iter(),editor.buffer.get_end_iter());editor.format('bold')
            text,state,html=editor.snapshot();assert '&lt;hello&gt;' in html and 'font-weight:bold' in html
            restored=RichEditor(state,text);assert restored.snapshot()[2]==html
            editor.list_lines();assert editor.snapshot()[0].startswith('• ')
            try:editor.link('javascript:alert(1)');raise AssertionError('Unsafe link accepted')
            except ValueError:pass
            app.assistant();assistant=app.assistant_window;app.assistant();assert app.assistant_window is assistant;assistant.close();assert app.assistant_window is None
            for _ in range(5):
                app.settings();assert app.settings_window is not None
                app.settings();assert app.settings_window is None
            assert app.nav_buttons['drafts'].has_css_class('active')
            app.show_section('mail');assert app.nav_buttons['mail'].has_css_class('active')
        elif index==7:
            app.mail_list.select_row(app.mail_list.get_row_at_index(0));capture(out/'inbox-dark.png')
            app.move_message(app.mail_list.get_row_at_index(0).message,'archive')
            assert len(app.store.items('mail','inbox'))==4;assert len(app.store.items('mail','archive'))==1
            from aster.core import AuthRequired
            from types import SimpleNamespace
            app.mode='live';app.auth=SimpleNamespace(needs_login=True)
            app.job(lambda: (_ for _ in ()).throw(AuthRequired('School requires 2FA.')))
        elif index==8:
            assert app.reconnect_button.get_visible();assert 'SIGN-IN NEEDED' in app.banner.get_text()
            assert app.store.drafts()[0]['state']=='accepted'
            app.tick()
            assert not app.syncing
            print('PASS: native inbox, reading, calendar navigation/create, contacts/create, draft recovery, simulated send, settings theme/single-window toggle/one top-left close button, rich formatting, custom colours/layout and singleton assistant, active top navigation, archive, school 2FA reconnect banner and polling pause',flush=True)
            app.settings()
        elif index==9:
            capture(out/'settings.png');assert app.settings_window is not None
            app.settings_window.close();assert app.settings_window is None
            app.mode='demo';app.graph=None;app.auth=None;app.show_section('mail');app.mail_list.select_row(app.mail_list.get_row_at_index(0))
            import aster.app as ui
            from types import SimpleNamespace
            ui.SecretVault=lambda *_:SimpleNamespace(load=lambda:None)
            class FakeAssistant:
                def __init__(self,*_):pass
                def ask(self,prompt,context,history):
                    assert 'Selected email' in context
                    return {'answer':'Here is a draft and an appointment proposal. Review both before saving.', 'email':{'to':'person@example.com','cc':'copy@example.com','bcc':'','subject':'Assistant draft','body':'Hello, can we meet tomorrow?'},'event':{'title':'Assistant appointment','start':__import__('datetime').datetime.now().astimezone().isoformat(),'duration':30,'location':'Studio'}}
            ui.Assistant=FakeAssistant;app.assistant();assistant=app.assistant_window
            next(w for w in descendants(assistant) if isinstance(w,Gtk.CheckButton)).set_active(True)
            views=[w for w in descendants(assistant) if isinstance(w,Gtk.TextView)];views[-1].get_buffer().set_text('Draft an email and appointment')
            next(w for w in descendants(assistant) if isinstance(w,Gtk.Button) and w.get_label()=='Ask assistant').emit('clicked')
        elif index==10:
            assistant=app.assistant_window;capture(out/'assistant.png')
            next(w for w in descendants(assistant) if isinstance(w,Gtk.Button) and w.get_label()=='Review email draft').emit('clicked')
            win=next(iter(app.compose_windows));assert win.recipient_fields['subject'].get_text()=='Assistant draft';assert win.recipient_fields['cc'].get_text()=='copy@example.com';win.close()
            next(w for w in descendants(assistant) if isinstance(w,Gtk.Button) and w.get_label()=='Review appointment').emit('clicked')
            dialog=next(w for w in Gtk.Window.get_toplevels() if w.get_title()=='New appointment')
            fields=[w for w in descendants(dialog) if isinstance(w,Gtk.Entry)];assert fields[0].get_text()=='Assistant appointment';assert fields[3].get_text()=='30';dialog.close();assistant.close()
            assert any(d.get('subject')=='Assistant draft' for d in app.store.drafts())
            print('PASS: assistant selected-mail context, email review draft, CC preservation and calendar proposal review (mocked API)',flush=True)
            app.quit();return False
        results.append(index)
        GLib.timeout_add(500,step,index+1)
    except Exception:
        failed.append(traceback.format_exc());print(failed[-1],flush=True);app.quit()
    return False
app.connect('activate',lambda *_:GLib.timeout_add(600,step))
app.run([])
if failed:raise SystemExit(1)
