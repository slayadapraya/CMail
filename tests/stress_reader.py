"""Regression: sync allocations must not finalize detached WebKit views off-main."""
import gc, os, threading, traceback, weakref
from pathlib import Path
from gi.repository import GLib
from aster.app import Aster,Gtk
from aster.mailhtml import viewer
app=Aster();main_thread=threading.get_ident();finalized=[];failed=[];stop=threading.Event()
class Detached:
    def __init__(self):
        self.cycle=self;self.box=Gtk.Box();self.box.append(viewer('<p>Grey reader regression</p>'))
        weakref.finalize(self,lambda:finalized.append(threading.get_ident()))
def allocate():
    while not stop.is_set():
        for _ in range(3000):
            cycle=[];cycle.append(cycle)
        stop.wait(.01)
def step(index=0):
    try:
        assert not gc.isenabled()
        if index==0:app.pool.submit(allocate)
        if index<12:
            Detached()
            app.collect_ui_cycles()
            assert finalized and set(finalized)=={main_thread}
            GLib.timeout_add(100,step,index+1)
        else:
            stop.set();app.collect_ui_cycles()
            assert len(finalized)==12 and set(finalized)=={main_thread}
            print('PASS: 12 detached HTML readers finalized on UI thread while sync worker allocates cycles',flush=True)
            app.quit()
    except Exception:
        failed.append(traceback.format_exc());print(failed[-1],flush=True);stop.set();app.quit()
    return False
app.connect('activate',lambda *_:GLib.timeout_add(500,step));app.run([])
if failed:raise SystemExit(1)
