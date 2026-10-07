from __future__ import annotations
import calendar
import gc
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.parse
import uuid
import gi
gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1');gi.require_version('GdkPixbuf','2.0')
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, GdkPixbuf
from .core import Store, Auth, Graph, AppError, AuthRequired, plain_body, email_recipients, month_bounds, event_datetime, utc_iso
from . import demo
from .google import GoogleAuth, Gmail, credentials_from_json
from .imap_google import AppPasswordAuth, GmailIMAP
from .core import SecretVault
from .richtext import RichEditor
from .assistant import Assistant
from .theme import FUTURE_CSS, CMAIL_CSS, PRESETS, scaled_css, select_theme, save_custom_theme, customize_color
import webbrowser
import re
import base64
import requests
from .presentation import conversations, date_label, timestamp
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .mailhtml import viewer
from .docking import DockWorkspace
from .maillist import MailList

NAVY_PALETTE = """
@define-color window_bg_color #0b1222;
@define-color window_fg_color #e6edf8;
@define-color view_bg_color #101a2e;
@define-color view_fg_color #e6edf8;
@define-color headerbar_bg_color #101a2e;
@define-color headerbar_fg_color #e6edf8;
@define-color headerbar_backdrop_color #101a2e;
@define-color card_bg_color #152139;
@define-color dialog_bg_color #101a2e;
@define-color dialog_fg_color #e6edf8;
@define-color popover_bg_color #17243b;
@define-color popover_fg_color #e6edf8;
@define-color accent_bg_color #247bb5;
@define-color accent_fg_color #ffffff;
@define-color accent_color #69bafa;
"""
CSS = """
headerbar { background-image: linear-gradient(115deg, @headerbar_bg_color, alpha(@accent_bg_color,.18)); }
.brand { text-shadow: 0px 0px 12px alpha(@accent_color,.45); }
.topnav { background-image: linear-gradient(90deg, alpha(@accent_bg_color,.09), transparent); }
.message-column { border-right: 1px solid alpha(@accent_color,.18); }
.card, .attachment-chip { border: 1px solid alpha(@accent_color,.17); }
.attachment-chip {padding:8px;border-radius:8px;}
.formatbar {padding:8px;background:@card_bg_color;border-radius:10px;}
.calendar-day.today {border-color:@accent_color;}

window { background: @window_bg_color; color: @window_fg_color; }
button.suggested-action { background: @accent_bg_color; color: @accent_fg_color; border-color: alpha(@accent_color,.5); }
button.suggested-action:hover { background: shade(@accent_bg_color,1.12); }
headerbar { background: @headerbar_bg_color; box-shadow: none; border-bottom: 1px solid alpha(@window_fg_color, .08); }
.topnav { background: @headerbar_bg_color; border-bottom: 1px solid alpha(@window_fg_color,.10); padding: 0 14px; }
.topnav button { background: transparent; box-shadow: none; border: none; border-radius: 0; padding: 11px 18px; color: alpha(@window_fg_color,.65); }
.topnav button.active { color: @accent_color; border-bottom: 2px solid @accent_color; font-weight: 700; }
.topnav button:hover { background: alpha(@accent_bg_color,.08); }
.commandbar { padding: 10px 16px; border-bottom: 1px solid alpha(@window_fg_color,.10); background: alpha(@view_bg_color,.7); }
.brand { font-size: 19px; font-weight: 800; letter-spacing: 2px; }
.brand-mark { color: @accent_color; font-size: 27px; }
.rail { background: @headerbar_bg_color; border-right: 1px solid alpha(@window_fg_color,.09); padding: 12px 6px; }
.rail button { padding: 11px 6px; background: transparent; box-shadow: none; border: none; }
.rail button.active { background: alpha(@accent_bg_color,.17); color: @accent_color; }
.sidebar { background: @headerbar_bg_color; padding: 18px 12px; border-right: 1px solid alpha(@window_fg_color,.1); }
.sidebar button { background: transparent; box-shadow: none; border: none; padding: 10px 12px; }
.sidebar button:hover { background: alpha(@accent_bg_color,.08); }
.sidebar button.active { background: alpha(@accent_bg_color,.13); border-left: 3px solid @accent_color; font-weight: 700; }
.sidebar-heading { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; color: alpha(@window_fg_color,.55); }
.section-title { font-size: 24px; font-weight: 750; }
.message-column { background: @view_bg_color; }
.list-heading { padding: 18px 16px 12px; border-bottom: 1px solid alpha(@window_fg_color,.09); }
.mail-row { padding: 16px 16px; border-bottom: 1px solid alpha(@window_fg_color,.075); }
list { background: transparent; }
row:selected { background: alpha(@accent_bg_color,.12); }
row:selected .mail-row { border-left: 3px solid @accent_color; padding-left: 13px; }
row:hover { background: alpha(@window_fg_color,.035); }
.sender { font-weight: 650; }
.unread { color: @accent_color; font-weight: 750; }
.preview { color: alpha(@window_fg_color,.53); font-size: 12px; }
.reader { padding: 28px; background: @window_bg_color; }
.reader textview, .reader textview text { background: transparent; color: @window_fg_color; font-size: 15px; }
.reader-title { font-size: 25px; font-weight: 700; }
.reader-actions { padding: 8px 0; }
.demo-banner { background: alpha(@accent_bg_color,.06); color: alpha(@window_fg_color,.62); padding: 6px 18px; font-size: 11px; }
.status { font-size: 11px; color: alpha(@window_fg_color,.6); padding: 7px 16px; border-top: 1px solid alpha(@window_fg_color,.08); }
.calendar-day { min-height: 74px; padding: 7px; border: 1px solid alpha(@window_fg_color,.08); border-radius: 6px; }
.today { background: alpha(@accent_bg_color,.13); }
.event-chip { color: @accent_color; font-size: 11px; }
.card { padding: 16px; border-radius: 8px; background: @card_bg_color; }
.settings-footer { padding: 12px 20px; border-top: 1px solid alpha(@window_fg_color,.1); }
"""

def label(text='', css=None, wrap=False):
    w = Gtk.Label(label=text, xalign=0); w.set_wrap(wrap)
    if css: w.add_css_class(css)
    return w

def button(text, callback, css=None):
    w = Gtk.Button(label=text); w.connect('clicked', callback)
    if css: w.add_css_class(css)
    return w

def command_button(text,icon,callback,primary=False,icon_only=False):
    w=Gtk.Button();w.connect('clicked',callback);w.set_tooltip_text(text);w.update_property([Gtk.AccessibleProperty.LABEL],[text])
    contents=Gtk.Box(spacing=7);contents.set_halign(Gtk.Align.CENTER);contents.append(Gtk.Image.new_from_icon_name(icon))
    w.cmail_label=Gtk.Label(label=text)
    if not icon_only:contents.append(w.cmail_label)
    w.set_child(contents)
    if primary:w.add_css_class('suggested-action')
    return w

def clear(box):
    def release(widget):
        dispose=getattr(widget,'cmail_dispose',None)
        if dispose:dispose();return
        child=widget.get_first_child()
        while child:release(child);child=child.get_next_sibling()
    while box.get_first_child():
        child=box.get_first_child();release(child);box.remove(child)

def scroll(child):
    view = Gtk.ScrolledWindow(); view.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); view.set_child(child); view.set_vexpand(True); view.set_hexpand(True); return view

def entry(placeholder='', text=''):
    w = Gtk.Entry(placeholder_text=placeholder); w.set_text(text); w.set_hexpand(True); return w

def logo(size=28):
    source=Path(__file__).resolve().parent.parent/'assets/cmail-icon.svg'
    image=Gtk.Image.new_from_file(str(source)) if source.exists() else Gtk.Image.new_from_icon_name('org.aster.Mail')
    image.set_pixel_size(size);image.add_css_class('cmail-logo');return image

class Aster(Adw.Application):
    def __init__(self):
        super().__init__(application_id='org.aster.Mail', flags=Gio.ApplicationFlags.NON_UNIQUE)
        # CPython can collect GTK/WebKit reference cycles on any allocating thread.
        # Their native destructors must run on the UI thread, including during sync.
        gc.disable()
        self.ui_thread=threading.get_ident()
        self.gc_source=GLib.timeout_add_seconds(30,lambda:self.collect_ui_cycles(full=False))
        self.panel_built=set();self.pending_sections=[];self.reader_save_source=0
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='aster')
        self.root = Path(os.environ.get('ASTER_DATA_DIR', str(Path.home() / '.local/share/aster-mail')))
        self.config = Store(self.root / 'config'); self.mode = 'demo'; self.graph = None; self.auth = None
        previous=self.config.get('last_account')
        cached=Path(previous.get('path','')) if isinstance(previous,dict) else None
        if self.config.get('mode')=='live' and cached and cached.is_relative_to(self.root/'accounts') and (cached/'mail.sqlite3').is_file():
            self.mode='live';self.store=Store(cached)
        else:
            self.store = Store(self.root / 'demo'); demo.seed(self.store)
        self.folder = 'inbox'; self.section = 'mail'; self.selected = None; self.syncing = False; self.refresh_pending=False; self.connecting = False; self.generation = 0
        self.current_month = datetime.now().replace(day=1);self.calendar_selected=datetime.now().date();self.calendar_days={}; self.events = []; self.compose_windows = set(); self.settings_window = None; self.assistant_window = None;self.photo_inflight={};self.photo_misses=set(); self.folder_buttons = {}; self.nav_buttons = {}; self.rail_buttons = {}
        self.connect('activate', self.activate); self.connect('shutdown',self.shutdown_jobs)
    def collect_ui_cycles(self,full=True):
        if threading.get_ident()!=self.ui_thread:raise RuntimeError('UI cleanup must run on the GTK thread')
        if hasattr(self,'docks') and self.docks.dragging is not None and not full:return True
        self.gc_round=getattr(self,"gc_round",0)+1
        gc.collect(2 if full or self.gc_round % 4==0 else 1)
        return True
    def shutdown_jobs(self,*_):
        if hasattr(self,"docks"):self.docks.shutdown()
        if self.reader_save_source:GLib.source_remove(self.reader_save_source);self.reader_save_source=0;self.save_reader_fraction()
        if self.gc_source:GLib.source_remove(self.gc_source);self.gc_source=None
        self.collect_ui_cycles()
        if self.graph and hasattr(self.graph,'cancel_event'):self.graph.cancel_event.set()
        self.pool.shutdown(wait=False,cancel_futures=True)
    def display_date(self,message,full=False):return date_label(message,full,self.config.get('display_timezone','Pacific/Auckland'))
    def job(self, fn, done=None, failed=None):
        future = self.pool.submit(fn)
        def complete(f):
            try: value = f.result()
            except Exception as exc:
                def failure(error=str(exc), exc_saved=exc):
                    if isinstance(exc_saved, AuthRequired): self.require_reconnect()
                    if failed: failed(error)
                    else: self.error(error)
                    return False
                GLib.idle_add(failure)
            else:
                def success():
                    if done: done(value)
                    return False
                GLib.idle_add(success)
        future.add_done_callback(complete)
    def error(self, message):
        self.status.set_text(message[:400]); self.toast.add_toast(Adw.Toast.new(message[:220]))
    def activate(self, *_):
        if hasattr(self, 'win'): self.win.present(); return
        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.apply_theme()
        self.win = Adw.ApplicationWindow(application=self, title='CMail', default_width=1440, default_height=900)
        self.toast = Adw.ToastOverlay(); self.win.set_content(self.toast)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); self.toast.set_child(outer)
        header = Adw.HeaderBar()
        brand = Gtk.Box(spacing=10);self.header_logo=logo();brand.append(self.header_logo);brand.append(label('CMAIL', 'brand'));header.pack_start(brand)
        self.search = Gtk.SearchEntry(placeholder_text='Search this folder'); self.search.set_size_request(390, -1)
        self.search.connect('search-changed', self.search_changed);header.set_title_widget(Gtk.Box())
        self.assistant_button=button('Assistant',lambda *_:self.assistant());header.pack_end(self.assistant_button);self.chatgpt_button=button('ChatGPT ↗',lambda *_:webbrowser.open('https://chatgpt.com/'));header.pack_end(self.chatgpt_button)
        self.reconnect_button = button('Reconnect', lambda *_: self.connect_account())
        self.reconnect_button.set_visible(False); header.pack_end(self.reconnect_button)
        self.header_widget=header;outer.append(header)
        nav = Gtk.Box(spacing=4); nav.add_css_class('topnav')
        for key, title in [('mail','Mail'), ('calendar','Calendar'), ('contacts','People'), ('drafts','Local drafts')]:
            item = button(title, lambda _, section=key: self.show_section(section)); self.nav_buttons[key] = item; nav.append(item)
        spacer = Gtk.Box(); spacer.set_hexpand(True); nav.append(spacer); self.topnav_widget=nav;nav.remove(spacer);header.pack_start(nav)
        command = Gtk.Box(spacing=5); command.add_css_class('commandbar')
        command.append(command_button('New message','list-add-symbolic',lambda *_:self.compose(),primary=True))
        self.refresh_button=command_button('Refresh','view-refresh-symbolic',lambda *_:self.refresh());self.refresh_button.set_tooltip_text('Check for new mail now (F5)');command.append(self.refresh_button)
        command.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        keys=Gtk.EventControllerKey()
        def refresh_key(_,keyval,*args):
            if keyval==Gdk.KEY_F5:self.refresh();return True
            if keyval==Gdk.KEY_Escape and self.section=='mail':self.close_reader();return True
            return False
        keys.connect('key-pressed',refresh_key);self.win.add_controller(keys)
        self.message_commands=[]
        for name,action in [('Reply',lambda m:self.compose(reply=m)),('Forward',lambda m:self.compose(forward=m)),('Archive',lambda m:self.move_message(m,'archive')),('Delete',lambda m:self.move_message(m,'deleteditems'))]:
            icons={'Reply':'mail-reply-sender-symbolic','Forward':'mail-forward-symbolic','Archive':'mail-archive-symbolic','Delete':'user-trash-symbolic'}
            if name=='Archive':command.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
            item=command_button(name,icons[name],lambda _,fn=action:self.selected_action(fn),icon_only=name in ('Archive','Delete'));item.set_sensitive(False);self.message_commands.append(item);command.append(item)
        menu=Gtk.MenuButton(icon_name='view-more-symbolic');menu.set_tooltip_text('More mail actions');menu.set_always_show_arrow(False);popover=Gtk.Popover();options=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);popover.set_child(options);menu.set_popover(popover)
        for name,action in [('Reply all',lambda m:self.compose(reply=m,reply_all=True)),('Mark unread',self.mark_unread),('Star / unstar',self.flag_message)]:
            item=button(name,lambda _,fn=action:(popover.popdown(),self.selected_action(fn)));item.set_sensitive(False);self.message_commands.append(item);options.append(item)
        options.append(button('Reading pane ↔ / ↕',lambda *_:(popover.popdown(),self.toggle_pane())));command.append(menu)
        spacer=Gtk.Box();spacer.set_hexpand(True);command.append(spacer);self.search.set_valign(Gtk.Align.CENTER);command.append(self.search);
        self.command_widget=command;outer.append(command)
        self.banner = label('DEMO MODE  ·  Fictional mail and contacts. Nothing is sent.', 'demo-banner')
        outer.append(self.banner)
        horizontal = Gtk.Box(); horizontal.set_vexpand(True); outer.append(horizontal)
        rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); rail.add_css_class('rail'); rail.set_size_request(54, -1); self.rail_widget=rail;horizontal.append(rail)
        for key, icon, name in [('mail','mail-unread-symbolic','Mail'), ('calendar','x-office-calendar-symbolic','Calendar'), ('contacts','system-users-symbolic','People')]:
            item = Gtk.Button(icon_name=icon); item.set_tooltip_text(name); item.connect('clicked', lambda _, section=key: self.show_section(section)); self.rail_buttons[key]=item; rail.append(item)
        rail_spacer=Gtk.Box();rail_spacer.set_vexpand(True);rail.append(rail_spacer)
        self.settings_button=Gtk.Button(icon_name='emblem-system-symbolic');self.settings_button.set_tooltip_text('Settings');self.settings_button.connect('clicked',lambda *_:self.settings());rail.append(self.settings_button)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); side.add_css_class('sidebar'); side.set_size_request(220, -1); side.set_hexpand(False)
        self.sidebar_widget=side;horizontal.append(side)
        sidebar_brand=Gtk.Box(spacing=7);self.sidebar_logo=logo();sidebar_brand.append(self.sidebar_logo);sidebar_brand.append(label('CMAIL','workspace-title'));side.append(sidebar_brand);side.append(label('MAIL / CALENDAR / PEOPLE','workspace-subtitle'));side.append(Gtk.Separator());
        self.account_label = label('Demo workspace', 'preview', True); self.account_label.set_margin_bottom(14);self.account_label.add_css_class('account-card');side.append(self.account_label)
        side.append(label('FOLDERS', 'sidebar-heading'))
        self.folders = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3); folder_scroll=scroll(self.folders); folder_scroll.set_hexpand(False); side.append(folder_scroll)
        self.populate_folders()
        side.append(Gtk.Separator()); side.append(button('Local drafts', lambda *_: self.show_section('drafts')))
        side.append(label('CMAIL  /  0.8.2', 'preview'))
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); self.content.set_hexpand(True); horizontal.append(self.content)
        self.status = label('Ready · Explore the demo or connect an account in Settings.', 'status'); outer.append(self.status)
        if self.mode=='live':
            profile=self.config.get('last_account',{}).get('profile',{});address=profile.get('mail') or profile.get('displayName','Cached account')
            self.account_label.set_text(address);self.banner.set_text('CACHED MAIL  ·  '+address+' · Connecting…');self.status.set_text('Saved mailbox · Connecting in the background…')
        self.docks=DockWorkspace(self,self.content);self.docks.start()
        self.win.connect('close-request',lambda *_:(self.docks.shutdown() or False))
        self.apply_layout(); self.win.present()
        GLib.timeout_add_seconds(10, self.tick)
        if self.config.get('mode') == 'live':
            self.connect_account(interactive=False)
    def toggle_pane(self):
        self.config.set('pane_bottom',not self.config.get('pane_bottom',False))
        self.build_mail();self.show_section('mail')
    def apply_theme(self):
        dark=self.config.get('dark',True)
        palette=NAVY_PALETTE if dark else ''
        names={'background':['window_bg_color'],'surface':['view_bg_color','headerbar_bg_color','headerbar_backdrop_color','dialog_bg_color','popover_bg_color'],'cards':['card_bg_color'],'text':['window_fg_color','view_fg_color','headerbar_fg_color','dialog_fg_color','popover_fg_color'],'accent':['accent_color'],'buttons':['accent_bg_color']}
        for key,colors in names.items():
            value=self.config.get('color_'+key)
            if value and re.fullmatch(r'#[0-9a-fA-F]{6}',value):
                palette+=''.join('@define-color '+name+' '+value+';\n' for name in colors)
        extra=''
        if self.config.get('compact',True):extra+='.mail-row {padding-top:7px;padding-bottom:7px;} .sidebar button {padding-top:6px;padding-bottom:6px;}'
        extra+=' .formatbar {padding:3px;border-radius:6px;} .formatbar button {padding:3px 6px;min-height:20px;min-width:16px;} .calendar-day {padding:6px;min-height:66px;} .calendar-day.selected {border:2px solid @accent_color;background:alpha(@accent_bg_color,.15);}'
        extra+=' .dock-tabs {padding:3px 6px;background:@headerbar_bg_color;border-bottom:1px solid alpha(@window_fg_color,.12);} .dock-tabs button {padding:4px 9px;min-height:22px;} .dock-tabs button.active {color:@accent_color;background:alpha(@accent_bg_color,.14);} .dock-preview {background:alpha(@accent_color,.22);border:2px solid @accent_color;} .mail-row {margin-top:3px;margin-bottom:3px;} .commandbar searchentry {padding:2px 6px;min-height:20px;} .commandbar {padding:3px 10px;} .commandbar button {padding:3px 8px;min-height:20px;} .folder-group {padding:3px;} .folder-row button {padding:5px 7px;} .folder-group-title {font-size:17px;font-weight:700;} .folder-row label {font-size:14px;}'
        if self.config.get('low_power',True):extra+=' * {text-shadow:none;box-shadow:none;} headerbar,.topnav,.commandbar {background-image:none;}'
        scale=self.ui_scale();extra+=' window {font-size:'+str(14)+'px;}'
        self.css_provider.load_from_string(palette+scaled_css(CSS+'''
headerbar {background-image:linear-gradient(110deg,@headerbar_bg_color,alpha(@accent_bg_color,.10));}
.topnav {background-image:linear-gradient(90deg,alpha(@accent_bg_color,.07),transparent);}
textview, textview text {background:@card_bg_color;color:@window_fg_color;}
.compose-body, .compose-body text {background:@view_bg_color;color:@window_fg_color;}
.format-red {color:#69bafa;} .format-blue {color:#7ab8ff;} .format-green {color:#73d9bd;} .format-white {color:#ffffff;}
'''+FUTURE_CSS+extra+CMAIL_CSS,scale)+'.workspace-subtitle {font-size:'+str(max(9,round(11*scale)))+'px;letter-spacing:.5px;padding-top:3px;padding-bottom:3px;min-height:14px;} .topnav button label {padding-top:2px;padding-bottom:2px;}')
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.DEFAULT)
    def ui_scale(self):return max(.65,min(1.2,float(self.config.get('ui_scale',.85))))
    def apply_layout(self):
        for key,widget in [('sidebar',self.sidebar_widget),('rail',self.rail_widget),('topnav',self.topnav_widget),('commands',self.command_widget),('banner',self.banner)]:widget.set_visible(self.config.get('show_'+key,True))
        for widget in (self.assistant_button,self.chatgpt_button):widget.set_visible(self.config.get('show_ai',True))
        self.sidebar_widget.set_size_request(round(self.config.get('sidebar_width',220)*self.ui_scale()),-1)
        self.rail_widget.set_size_request(round(54*self.ui_scale()),-1);self.search.set_size_request(round(290*self.ui_scale()),-1)
        for image in (self.header_logo,self.sidebar_logo):image.set_pixel_size(max(20,round(28*self.ui_scale())))
        self.settings_button.set_visible(True)
        self.rail_widget.set_visible(True)
        self.apply_theme()
    def search_changed(self, *_):
        if self.section != 'mail': self.show_section('mail')
        else: self.render_mail()
    def update_navigation(self):
        for widgets in (self.nav_buttons, self.rail_buttons):
            for key, widget in widgets.items():
                if key == self.section: widget.add_css_class('active')
                else: widget.remove_css_class('active')
        for key, widget in self.folder_buttons.items():
            if key == self.folder and self.section == 'mail': widget.add_css_class('active')
            else: widget.remove_css_class('active')
    def require_reconnect(self):
        if self.mode != 'live': return
        self.reconnect_button.set_visible(True)
        self.banner.set_text('SIGN-IN NEEDED  ·  Cached mail and drafts are available. Reconnect to resume live updates.')
        self.status.set_text('Sign-in is required. Synchronisation is paused.')
    def tick(self):
        if self.mode == 'live' and not (self.auth and self.auth.needs_login):
            if self.graph: self.refresh(automatic=True)
            elif not self.connecting: self.connect_account(interactive=False)
        return True
    def folder_preferences_key(self):
        account=(self.config.get('last_account') or {}).get('profile',{}).get('mail','demo') if self.mode=='live' else 'demo'
        return 'folder_layout:'+account.casefold()
    def folder_layout(self):return self.config.get(self.folder_preferences_key(),{})
    def save_folder_layout(self,layout):
        self.config.set(self.folder_preferences_key(),layout);self.populate_folders(self.folder_values)
    def reorder_folder(self,source,target):
        if source==target:return False
        layout=self.folder_layout();order=[x for x in layout.get('order',[]) if x in {v['id'] for v in self.folder_values}]
        order += [v['id'] for v in self.folder_values if v['id'] not in order]
        if source not in order or target not in order:return False
        order.remove(source);order.insert(order.index(target),source);groups=layout.get('groups',{});groups[source]=self.folder_group(next(v for v in self.folder_values if v['id']==target),layout);layout.update(order=order,groups=groups);self.save_folder_layout(layout);return True
    def folder_group(self,item,layout):
        if item['id'] in layout.get('groups',{}):return layout['groups'][item['id']]
        return 'Mailbox' if item['id'].lower() in ('inbox','sentitems','drafts','archive','deleteditems','starred','spam','important','snoozed') else 'Labels'
    def populate_folders(self, values=None):
        clear(self.folders); self.folder_buttons = {}
        self.folder_values=values or getattr(self,'folder_values',None) or self.store.items('folders') or [{'id': k, 'displayName': v} for k,v in [('inbox','Inbox'),('sentitems','Sent'),('drafts','Provider drafts'),('archive','Archive'),('deleteditems','Trash')]]
        layout=self.folder_layout();order=layout.get('order',[]);hidden=set(layout.get('hidden',[]));groups=['Mailbox','Labels']+layout.get('custom_groups',[])
        items=sorted(self.folder_values,key=lambda v:order.index(v['id']) if v['id'] in order else len(order)+self.folder_values.index(v))
        menu=Gtk.MenuButton(label='Organise folders');pop=Gtk.Popover();box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);pop.set_child(box);menu.set_popover(pop)
        box.append(button('Show / hide folders',lambda *_:(pop.popdown(),self.manage_folders())))
        box.append(button('New folder',lambda *_:(pop.popdown(),self.new_mail_folder())))
        box.append(button('New folder group',lambda *_:(pop.popdown(),self.new_folder_group())))
        box.append(button('Reset arrangement',lambda *_:(pop.popdown(),self.save_folder_layout({}))))
        self.folders.append(menu)
        for group in groups:
            members=[v for v in items if self.folder_group(v,layout)==group and v['id'] not in hidden]
            if not members and group not in layout.get('custom_groups',[]):continue
            expander=Gtk.Expander(label=group);heading=label(group,'folder-group-title');expander.set_label_widget(heading);expander.add_css_class('folder-group');expander.set_expanded(group not in layout.get('collapsed',[]));contents=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2);expander.set_child(contents);self.folders.append(expander)
            def fold(widget,_,name=group):
                prefs=self.folder_layout();collapsed=set(prefs.get('collapsed',[]))
                if widget.get_expanded():collapsed.discard(name)
                else:collapsed.add(name)
                prefs['collapsed']=sorted(collapsed);self.config.set(self.folder_preferences_key(),prefs)
            expander.connect('notify::expanded',fold)
            drop_group=Gtk.DropTarget.new(str,Gdk.DragAction.MOVE)
            def group_drop(_,value,x,y,name=group):
                if value not in {v['id'] for v in self.folder_values}:return False
                prefs=self.folder_layout();mapping=prefs.get('groups',{});mapping[value]=name;prefs['groups']=mapping;self.save_folder_layout(prefs);return True
            drop_group.connect('drop',group_drop);expander.add_controller(drop_group)
            for item in members:
                fid=item['id'];row=Gtk.Box(spacing=2);row.add_css_class('folder-row');contents.append(row)
                row.set_tooltip_text('Drag to reorder · Right-click for folder options')
                folder_button = button(item['displayName'], lambda _, f=fid: self.select_folder(f));folder_button.set_hexpand(True)
                folder_label=folder_button.get_child()
                if isinstance(folder_label,Gtk.Label):folder_label.set_xalign(0);folder_label.set_ellipsize(3)
                self.folder_buttons[fid]=folder_button;row.append(folder_button)
                drag=Gtk.DragSource(actions=Gdk.DragAction.MOVE);drag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                drag.connect('prepare',lambda _,x,y,f=fid:Gdk.ContentProvider.new_for_value(f));row.add_controller(drag)
                target=Gtk.DropTarget.new(str,Gdk.DragAction.MOVE);target.connect('drop',lambda _,value,x,y,f=fid:self.reorder_folder(value,f));row.add_controller(target)
                popover=Gtk.Popover();choices=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3);popover.set_child(choices);popover.set_parent(row)
                context=Gtk.GestureClick();context.set_button(3);context.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                def open_menu(_,count,x,y,popover=popover):
                    rect=Gdk.Rectangle();rect.x=int(x);rect.y=int(y);rect.width=1;rect.height=1;popover.set_pointing_to(rect);popover.popup()
                context.connect('pressed',open_menu);row.add_controller(context)
                def hide(_,f=fid,popover=popover):
                    popover.popdown();prefs=self.folder_layout();prefs['hidden']=list(set(prefs.get('hidden',[]))|{f});self.save_folder_layout(prefs)
                choices.append(button('Hide folder',hide))
                for group_name in groups:
                    def move(_,f=fid,g=group_name,popover=popover):
                        popover.popdown();prefs=self.folder_layout();mapping=prefs.get('groups',{});mapping[f]=g;prefs['groups']=mapping;self.save_folder_layout(prefs)
                    choices.append(button('Move to '+group_name,move))
        self.update_navigation()
    def manage_folders(self):
        win=Adw.Window(title='Show / hide folders',transient_for=self.win,default_width=380,default_height=460);outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);win.set_content(outer);outer.append(button('Close',lambda *_:win.close()));box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);outer.append(scroll(box))
        for item in self.folder_values:
            check=Gtk.CheckButton(label=item['displayName'],active=item['id'] not in self.folder_layout().get('hidden',[]));box.append(check)
            def toggle(widget,fid=item['id']):
                prefs=self.folder_layout();hidden=set(prefs.get('hidden',[]))
                if widget.get_active():hidden.discard(fid)
                else:hidden.add(fid)
                prefs['hidden']=list(hidden);self.save_folder_layout(prefs)
            check.connect('toggled',toggle)
        win.present()
    def new_folder_group(self):
        win=Adw.Window(title='New folder group',transient_for=self.win,default_width=350);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);win.set_content(box);name=entry('Group name');box.append(name);box.append(label('Groups organise this sidebar locally. Drag folders onto a group or use their menu.','preview',True))
        def create(*_):
            value=name.get_text().strip();prefs=self.folder_layout();groups=prefs.get('custom_groups',[])
            if not value or value in ['Mailbox','Labels']+groups:return
            prefs['custom_groups']=groups+[value];self.save_folder_layout(prefs);win.close()
        box.append(button('Create group',create));box.append(button('Cancel',lambda *_:win.close()));win.present()
    def new_mail_folder(self):
        win=Adw.Window(title='New folder',transient_for=self.win,default_width=390);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_top(18);box.set_margin_bottom(18);box.set_margin_start(18);box.set_margin_end(18);win.set_content(box)
        name=entry('Folder name');box.append(name);groups=['Mailbox','Labels']+self.folder_layout().get('custom_groups',[]);destination=Gtk.DropDown.new_from_strings(groups);destination.set_selected(1);box.append(label('Sidebar group'));box.append(destination)
        info=label('Creates a Gmail label or an Outlook mail folder in your account.' if self.mode=='live' else 'Creates a folder in this demo mailbox.','preview',True);box.append(info)
        graph,store=self.graph,self.store
        def create(*_):
            value=name.get_text().strip()
            if not value or len(value)>255 or any(c in value for c in ('\n','\r','\x00')):info.set_text('Enter a folder name of 1–255 characters.');return
            if any(v['displayName'].casefold()==value.casefold() for v in self.folder_values):info.set_text('A folder with that name already exists.');return
            create_button.set_sensitive(False);group=groups[destination.get_selected()]
            def success(item):
                if store is not self.store:win.close();return
                values=[v for v in self.folder_values if v['id']!=item['id']]+[item];store.replace('folders','',values);prefs=self.folder_layout();mapping=prefs.get('groups',{});mapping[item['id']]=group;prefs['groups']=mapping;self.config.set(self.folder_preferences_key(),prefs);self.populate_folders(values);win.close();self.error('Folder created.')
            def failed(message):create_button.set_sensitive(True);info.set_text(message)
            if self.mode=='demo':success({'id':'demo-folder:'+str(uuid.uuid4()),'displayName':value})
            elif graph:self.job(lambda:graph.create_folder(value),success,failed)
            else:failed('Reconnect your account before creating a folder.')
        create_button=button('Create folder',create,'suggested-action');box.append(create_button);box.append(button('Cancel',lambda *_:win.close()));win.present()
    def select_folder(self, folder):
        self.folder = folder; self.selected = None; self.reader_key=None;self.close_reader();self.show_section('mail');self.render_mail()
        if self.mode=='live':self.refresh(section='mail')
    def ensure_panel(self,section):
        if section not in self.panel_built:
            getattr(self,'build_'+section)()
            if self.mode=='live' and self.graph and section in ('calendar','contacts'):GLib.idle_add(lambda:(self.refresh(section=section) or False))
    def panel_content(self,section):
        self.panel_built.add(section)
        return self.docks.panels[section]
    def rebuild_panels(self):
        for section in list(self.panel_built):getattr(self,'build_'+section)()
    def show_section(self, section):
        self.docks.select(section)
    def save_reader_fraction(self):
        self.reader_save_source=0
        value=getattr(self,'reader_fraction_pending',None)
        if value:self.config.set(*value)
        return False
    def build_mail(self):
        content=self.panel_content('mail');clear(content)
        if getattr(self,'pane_animation',0):GLib.source_remove(self.pane_animation);self.pane_animation=0
        self.reader_open=False;self.selected_message=None
        panes = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL if self.config.get('pane_bottom',False) else Gtk.Orientation.HORIZONTAL);panes.set_vexpand(True);panes.set_shrink_start_child(True);panes.set_shrink_end_child(True);self.mail_panes=panes;content.append(panes)
        def remember(widget,_):
            if not self.reader_open or getattr(self,'pane_animation',0):return
            extent=widget.get_height() if self.config.get('pane_bottom',False) else widget.get_width()
            if extent:
                self.reader_fraction_pending=('reader_fraction_bottom' if self.config.get('pane_bottom',False) else 'reader_fraction',max(.15,min(.65,widget.get_position()/extent)))
                if self.reader_save_source:GLib.source_remove(self.reader_save_source)
                self.reader_save_source=GLib.timeout_add(350,self.save_reader_fraction)
        panes.connect('notify::position',remember)
        listing = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); listing.set_size_request(round(300*self.ui_scale()),-1); listing.add_css_class('message-column')
        title = Gtk.Box(spacing=10); title.add_css_class('list-heading')
        self.mail_title = label('Your inbox' if self.folder == 'inbox' else 'Messages', 'section-title'); self.mail_title.set_hexpand(True);self.mail_title.set_ellipsize(3); title.append(self.mail_title); title.append(label('LATEST', 'preview')); listing.append(title)
        filters=Gtk.Box(spacing=8);filters.set_margin_start(16);filters.set_margin_end(16)
        self.mail_filter=Gtk.DropDown.new_from_strings(['All messages','Unread','Flagged']);self.mail_filter.connect('notify::selected',lambda *_:self.render_mail());filters.append(self.mail_filter)
        self.mail_sort=Gtk.DropDown.new_from_strings(['Newest first','Oldest first']);self.mail_sort.connect('notify::selected',lambda *_:self.render_mail());filters.append(self.mail_sort);listing.append(filters)
        self.mail_category=Gtk.DropDown.new_from_strings(['All categories','Primary','Promotions','Social','Updates','Forums']);self.mail_category.set_selected(self.config.get('gmail_category',0));self.mail_category.set_margin_start(16);self.mail_category.set_margin_end(16);self.mail_category.set_visible(isinstance(self.graph,Gmail))
        self.mail_category.connect('notify::selected',lambda w,_:(self.config.set('gmail_category',w.get_selected()),self.render_mail()));listing.append(self.mail_category)
        self.mail_list = MailList(self.mail_row,self.read_row)
        self.mail_empty=label('No cached messages here. Refresh to sync.','dim-label',True);listing.append(self.mail_empty)
        listing.append(scroll(self.mail_list)); panes.set_start_child(listing)
        self.reader_key=None;self.reader = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); self.reader.add_css_class('reader')
        self.reader_revealer=Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,transition_duration=240);self.reader_revealer.set_child(scroll(self.reader));panes.set_end_child(self.reader_revealer)
        self.empty_reader(); self.render_mail()
    def selected_action(self,action):
        if self.section=='mail' and getattr(self,'selected_message',None):action(self.selected_message)
    def set_reader_open(self,opened):
        if self.reader_open==opened:return
        self.reader_open=opened;panes=self.mail_panes;revealer=self.reader_revealer
        if getattr(self,'pane_animation',0):GLib.source_remove(self.pane_animation);self.pane_animation=0
        extent=panes.get_height() if self.config.get('pane_bottom',False) else panes.get_width()
        if not extent:GLib.idle_add(lambda:(self.animate_reader(opened) or False));return
        self.animate_reader(opened)
    def animate_reader(self,opened):
        if self.config.get('low_power',True):
            self.reader_revealer.set_transition_type(Gtk.RevealerTransitionType.NONE);self.reader_revealer.set_reveal_child(opened)
            extent=self.mail_panes.get_height() if self.config.get('pane_bottom',False) else self.mail_panes.get_width()
            fraction=self.config.get('reader_fraction_bottom',.35) if self.config.get('pane_bottom',False) else self.config.get('reader_fraction',.25)
            self.mail_panes.set_position(round(extent*fraction) if opened else extent);return
        self.reader_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        panes=self.mail_panes;revealer=self.reader_revealer;bottom=self.config.get('pane_bottom',False)
        extent=panes.get_height() if bottom else panes.get_width()
        start=panes.get_position() if revealer.get_reveal_child() else extent
        fraction=self.config.get('reader_fraction_bottom',.35) if bottom else self.config.get('reader_fraction',.25)
        target=round(extent*max(.15,min(.65,fraction))) if opened else extent
        revealer.set_reveal_child(opened);began=GLib.get_monotonic_time()
        def frame():
            if panes is not self.mail_panes:self.pane_animation=0;return False
            elapsed=min(1,(GLib.get_monotonic_time()-began)/240000);eased=1-(1-elapsed)**3
            panes.set_position(round(start+(target-start)*eased))
            if elapsed>=1:self.pane_animation=0;return False
            return True
        self.pane_animation=GLib.timeout_add(16,frame)
    def close_reader(self):
        self.selected=None;self.selected_message=None;self.reader_key=None;self.mail_list.unselect_all();self.empty_reader()
    def empty_reader(self):
        clear(self.reader);self.set_reader_open(False)
        for item in self.message_commands:item.set_sensitive(False)
    def prepare_mail(self,store,folder,category,term,mail_filter,newest):
        rows=conversations(store.items('mail',folder),category,term,mail_filter,newest)
        threads=store.items_by_bucket('thread')
        for msg in rows:
            saved=threads.get(msg.get('threadId'))
            if saved:
                combined={m['id']:m for m in saved+msg['members']};msg.update(conversations(list(combined.values()))[0])
        rows.sort(key=lambda m:(timestamp(m),m['id']),reverse=newest)
        photos={p['id']:p for p in store.items('photos')}
        contacts={e['address'].casefold():p['photoUrl'] for p in store.items('contacts') if p.get('photoUrl') for e in p.get('emailAddresses',[]) if e.get('address')}
        return rows,photos,contacts
    def mail_context(self):
        category=['All categories','Primary','Promotions','Social','Updates','Forums'][self.mail_category.get_selected()] if isinstance(self.graph,Gmail) else 'All categories'
        return self.store,self.folder,category,self.search.get_text().casefold(),self.mail_filter.get_selected(),self.mail_sort.get_selected()==0,self.generation
    def render_mail(self):
        if hasattr(self,'docks') and self.docks.dragging is not None:self.mail_render_pending=True;return
        if 'mail' not in self.panel_built:return
        if getattr(self,'mail_build_running',False):self.mail_build_pending=True;return
        context=self.mail_context()
        def apply(result):
            if context!=self.mail_context():return
            if self.docks.dragging is not None:self.mail_render_pending=True;return
            rows,self.photo_index,self.contact_photo_index=result
            shown=self.mail_list.set_rows(rows,self.selected,style_key=(self.config.get('display_timezone','Pacific/Auckland'),self.ui_scale(),self.config.get('mail_density','cards')))
            self.mail_title.set_text(('Inbox' if self.folder == 'inbox' else 'Messages') + f' · {shown}');self.mail_empty.set_visible(not shown)
        if self.store.item_count('mail',self.folder)<=300:apply(self.prepare_mail(*context[:-1]));return
        self.mail_build_running=True
        def complete(result):
            self.mail_build_running=False;apply(result)
            if getattr(self,'mail_build_pending',False):self.mail_build_pending=False;GLib.idle_add(lambda:(self.render_mail() or False))
        def failed(message):self.mail_build_running=False;self.mail_build_pending=False;self.error(message)
        self.job(lambda:self.prepare_mail(*context[:-1]),complete,failed)
    def mail_row(self,msg):
        if self.config.get('mail_density','cards')=='compact':return self.compact_mail_row(msg)
        sender=msg.get('from',{}).get('emailAddress',{})
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); box.add_css_class('mail-row')
        top = Gtk.Box(spacing=8);avatar=self.avatar(sender);top.append(avatar);who = label(sender.get('name') or sender.get('address') or '(No sender)', 'sender' if msg.get('isRead') else 'unread')
        who.set_ellipsize(3); who.set_hexpand(True); top.append(who)
        stamp=self.display_date(msg)
        top.append(label(stamp,'preview')); box.append(top)
        subject = label(('★ ' if msg.get('flag',{}).get('flagStatus')=='flagged' else '')+('⌁ ' if msg.get('hasAttachments') else '')+(msg.get('subject') or '(No subject)')+(f'  ·  {msg["count"]} messages' if msg['count']>1 else '')); subject.set_ellipsize(3);subject.add_css_class('mail-subject');box.append(subject)
        preview = label(msg.get('bodyPreview','').replace('\n',' '), 'preview'); preview.set_ellipsize(3); box.append(preview)
        return box
    def compact_mail_row(self,msg):
        sender=msg.get('from',{}).get('emailAddress',{})
        row=Gtk.Box(spacing=10);row.add_css_class('mail-row');row.add_css_class('compact-row')
        avatar=self.avatar(sender);avatar.set_size_request(-1,-1);avatar.set_size(round(24*self.ui_scale()));row.append(avatar)
        who=label(sender.get('name') or sender.get('address') or '(No sender)','sender' if msg.get('isRead') else 'unread');who.set_ellipsize(3);who.set_width_chars(14);who.set_max_width_chars(14);row.append(who)
        subject=label((msg.get('subject') or '(No subject)')+(f' · {msg["count"]}' if msg['count']>1 else ''),'mail-subject');subject.set_ellipsize(3);subject.set_hexpand(True);row.append(subject)
        preview=label(msg.get('bodyPreview','').replace('\n',' '),'preview');preview.set_ellipsize(3);preview.set_hexpand(True);preview.set_max_width_chars(65);row.append(preview)
        if msg.get('hasAttachments'):image=Gtk.Image.new_from_icon_name('mail-attachment-symbolic');image.set_tooltip_text('Has attachments');row.append(image)
        if msg.get('flag',{}).get('flagStatus')=='flagged':image=Gtk.Image.new_from_icon_name('starred-symbolic');image.set_tooltip_text('Starred');row.append(image)
        row.append(label(self.display_date(msg),'preview'));row.set_tooltip_text(msg.get('bodyPreview',''))
        return row
    def avatar(self,sender,large=False):
        size=round((54 if large else 34)*self.ui_scale());box=Adw.Avatar.new(size,sender.get('name') or sender.get('address') or '?',True);box.set_halign(Gtk.Align.CENTER);box.set_valign(Gtk.Align.CENTER);box.set_hexpand(False);box.set_vexpand(False);box.add_css_class('sender-avatar')
        address=sender.get('address','').casefold();store=self.store
        cached=getattr(self,'photo_index',{}).get(address)
        def display(value):
            if not value:return
            try:
                textures=getattr(self,'avatar_textures',None)
                if textures is None:self.avatar_textures={};textures=self.avatar_textures
                texture_key=(str(store.root),address,hash(value['data']))
                texture=textures.get(texture_key)
                if texture is None:
                    stream=Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(base64.b64decode(value['data'])))
                    pixels=GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream,96,96,True,None);texture=Gdk.Texture.new_for_pixbuf(pixels)
                    if len(textures)>=256:textures.pop(next(iter(textures)))
                    textures[texture_key]=texture
                box.set_custom_image(texture)
            except Exception:pass
        if cached:display(cached)
        elif address in self.photo_inflight:self.photo_inflight[address].append(display)
        elif address not in self.photo_misses:
            photo=getattr(self,'contact_photo_index',{}).get(address)
            host=urllib.parse.urlparse(photo or '').hostname or ''
            if photo and urllib.parse.urlparse(photo).scheme=='https' and (host=='googleusercontent.com' or host.endswith('.googleusercontent.com')):
                def fetch():
                    with requests.get(photo,timeout=(5,10),stream=True,allow_redirects=False) as response:
                        if not response.ok:return None
                        blob=b''
                        for chunk in response.iter_content(65536):
                            blob+=chunk
                            if len(blob)>2_000_000:return None
                    value={'id':address,'data':base64.b64encode(blob).decode()}
                    with store.lock,store.db:store.db.execute('INSERT OR REPLACE INTO items VALUES (?,?,?,?)',('photos','',address,json.dumps(value)))
                    return value
                self.photo_inflight[address]=[display]
                def complete(value):
                    callbacks=self.photo_inflight.pop(address,[])
                    if value and store is self.store:getattr(self,'photo_index',{})[address]=value
                    if not value:self.photo_misses.add(address)
                    for callback in callbacks:callback(value)
                self.job(fetch,complete,lambda _:complete(None))
        return box
    def read_row(self,_,row):
        if not row or not hasattr(row,'message'):return
        msg=row.message;self.selected_message=msg;self.set_reader_open(True)
        for item in self.message_commands:item.set_sensitive(self.section=='mail')
        key=(msg.get('thread_key',msg['id']),msg.get('count',1),self.generation)
        if self.reader_key==key:return
        self.reader_key=key;self.selected=msg['id'];clear(self.reader)
        self.reader.append(button('← Inbox',lambda *_:self.close_reader()))
        self.reader.append(label(msg.get('subject') or '(No subject)','reader-title',True))
        self.reader.append(label('Conversation · Click a sender to expand or collapse their message','preview',True))
        threadbox=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
        controls=Gtk.Box(spacing=8)
        def fold(expanded):
            child=threadbox.get_first_child()
            while child:
                if isinstance(child,Gtk.Expander):child.set_expanded(expanded)
                child=child.get_next_sibling()
        controls.append(button('Collapse all',lambda *_:fold(False)));controls.append(button('Expand all',lambda *_:fold(True)));self.reader.append(controls);self.reader.append(threadbox)
        graph,store=self.graph,self.store
        cached=store.items('thread',msg.get('threadId','')) if msg.get('threadId') else []
        def show(messages):
            if self.reader_key!=key or 'mail' not in self.panel_built or store is not self.store:return
            clear(threadbox);messages=sorted(messages,key=timestamp)
            for index,message in enumerate(messages):
                self.thread_message(threadbox,message,index==len(messages)-1)
        show(cached or msg.get('members',[msg]))
        if self.mode=='live' and graph and (not cached or any(m.get('localConfirmed') for m in cached) or max(timestamp(m) for m in cached)<timestamp(msg)):
            def fetch():
                messages=graph.thread(msg['threadId']) if isinstance(graph,Gmail) and msg.get('threadId') else [graph.message(msg['id'])]
                if msg.get('threadId'):
                    ids={m['id'] for m in messages};messages += [m for m in store.items('thread',msg['threadId']) if m.get('localConfirmed') and m['id'] not in ids];store.replace('thread',msg['threadId'],messages)
                for message in messages:
                    if not isinstance(graph,Gmail):
                        message['files']=graph.attachments(message['id'])
                        for file in message['files']:file['mimeType']=file.get('mimeType') or file.get('contentType','application/octet-stream')
                    if not message.get('isRead'):graph.set_read(message['id'],True)
                return messages
            self.job(fetch,show)
    def thread_message(self,parent,msg,expanded=False):
        sender=msg.get('from',{}).get('emailAddress',{});expander=Gtk.Expander();expander.set_expanded(expanded);expander.add_css_class('message-heading');parent.append(expander)
        # FlowBox wraps the complete action group below the sender on narrow panes.
        # The same persistent Expander still owns folding and body cleanup.
        header=Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,homogeneous=False,min_children_per_line=1,max_children_per_line=2,column_spacing=16,row_spacing=6);header.set_hexpand(True);header.add_css_class('message-header');header.set_activate_on_single_click(False);header.set_focusable(False)
        sender_box=Gtk.Box(spacing=10);sender_box.set_hexpand(True);sender_box.append(self.avatar(sender))
        identity=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3);identity.set_hexpand(True)
        who=label(sender.get('name') or sender.get('address',''),'sender');who.set_ellipsize(3);who.set_max_width_chars(38);identity.append(who)
        address=label(sender.get('address',''),'preview');address.set_ellipsize(3);address.set_max_width_chars(38);address.set_tooltip_text(sender.get('address',''));identity.append(address)
        preview=label(msg.get('bodyPreview','').replace('\n',' '),'preview');preview.set_ellipsize(3);preview.set_single_line_mode(True);preview.set_max_width_chars(38);preview.set_visible(not expanded);identity.append(preview);sender_box.append(identity);header.insert(sender_box,-1)
        expander.connect('notify::expanded',lambda widget,_:preview.set_visible(not widget.get_expanded()))
        tools=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);tools.set_halign(Gtk.Align.END)
        stamp=label(self.display_date(msg),'preview');stamp.set_halign(Gtk.Align.END);stamp.set_tooltip_text(self.display_date(msg,True));tools.append(stamp)
        actions=Gtk.Box(spacing=3);actions.add_css_class('message-actions');actions.set_halign(Gtk.Align.END)
        flagged=msg.get('flag',{}).get('flagStatus')=='flagged'
        definitions=[('Reply','mail-reply-sender-symbolic',lambda:self.compose(reply=msg)),('Reply all','mail-reply-all-symbolic',lambda:self.compose(reply=msg,reply_all=True)),('Forward','mail-forward-symbolic',lambda:self.compose(forward=msg)),('Archive','mail-archive-symbolic',lambda:self.move_message(msg,'archive')),('Move to trash','user-trash-symbolic',lambda:self.move_message(msg,'deleteditems')),('Mark unread','mail-unread-symbolic',lambda:self.mark_unread(msg)),('Unstar message' if flagged else 'Star message','starred-symbolic' if flagged else 'non-starred-symbolic',lambda:self.flag_message(msg))]
        for index,(name,icon,fn) in enumerate(definitions):
            if index in (3,6):actions.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
            item=command_button(name,icon,lambda _,f=fn:f(),icon_only=True)
            if index==6 and flagged:item.add_css_class('starred')
            actions.append(item)
        tools.append(actions);header.insert(tools,-1)
        for child in (header.get_child_at_index(0),header.get_child_at_index(1)):child.set_focusable(False)
        expander.set_label_widget(header)
        content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);expander.set_child(content)
        recipients=[r.get('emailAddress',{}).get('address','') for r in msg.get('toRecipients',[])];content.append(label('To: '+', '.join(recipients),'preview',True));content.append(Gtk.Separator())
        bodybox=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);content.append(bodybox)
        state={'loaded':False};graph,store=self.graph,self.store
        def render(assets,remote=None):
            if remote is None:remote=self.config.get('load_remote_images',True)
            clear(bodybox);html=msg.get('htmlBody') or (msg.get('body',{}).get('content') if msg.get('body',{}).get('contentType','').lower()=='html' else '')
            text=html or plain_body(msg.get('body',{})) or msg.get('bodyPreview','')
            try:
                if not html:
                    if len(text)>12000 and self.config.get('low_power',True):
                        native=Gtk.TextView(editable=False,cursor_visible=False,wrap_mode=Gtk.WrapMode.WORD_CHAR);native.get_buffer().set_text(text)
                        viewport=scroll(native);viewport.set_size_request(-1,600);viewport.set_vexpand(False);bodybox.append(viewport)
                    else:
                        native=Gtk.Label(label=text,wrap=True,selectable=True,xalign=0);native.set_wrap_mode(2);bodybox.append(native)
                else:
                    html_view=viewer(text,assets,remote,True,self.config.get('color_mail') or '#242831',self.config.get('color_text') or '#e6edf8',low_power=self.config.get('low_power',True));html_view.set_zoom_level(self.ui_scale());bodybox.append(html_view)
            except (ValueError,ImportError):
                fallback=Gtk.Label(label=plain_body(msg.get('body',{})) or msg.get('bodyPreview',''),wrap=True,selectable=True,xalign=0);fallback.set_wrap_mode(2);bodybox.append(fallback);bodybox.append(label('Install the updated package to enable HTML viewing.','preview',True))
            if html and not remote:bodybox.append(button('Load remote images for this message',lambda *_:render(assets,True)))
            files=msg.get('files',[])
            for file in files:
                if file.get('isInline'):continue
                size=file.get('size',0);size_text=f'{size/1_000_000:.1f} MB' if size>=1_000_000 else f'{size/1000:.0f} KB'
                card=Gtk.Box(spacing=10);card.add_css_class('attachment-chip');caption=label('📎 '+file.get('name','Attachment')+' · '+size_text,wrap=True);caption.set_hexpand(True);card.append(caption);save=button('Save',lambda _,f=file:self.save_attachment(msg['id'],f));save.set_sensitive(graph is not None);card.append(save);bodybox.append(card)
        def load(*_):
            if not expander.get_expanded():
                if state['loaded']:clear(bodybox);state['loaded']=False
                return
            if state['loaded']:return
            state['loaded']=True
            cached={x['contentId']:x['url'] for x in store.items('inline',msg['id'])};render(cached)
            missing=[f for f in msg.get('files',[]) if f.get('isInline') and f.get('contentId') and f.get('mimeType') in ('image/png','image/jpeg','image/gif','image/webp') and f.get('size',0)<=8_000_000 and f['contentId'] not in cached][:20]
            if graph and self.mode=='live' and missing:
                def fetch():
                    assets=dict(cached);used=0
                    for file in missing:
                        blob=graph.attachment(msg['id'],file);used+=len(blob)
                        if used>20_000_000:break
                        assets[file['contentId']]='data:'+file['mimeType']+';base64,'+base64.b64encode(blob).decode()
                    store.replace('inline',msg['id'],[{'id':cid,'contentId':cid,'url':url} for cid,url in assets.items()]);return assets
                def failed(error):
                    bodybox.append(label(error,'preview',True))
                    def retry():state['loaded']=False;load()
                    bodybox.append(button('Retry inline images',lambda *_:retry()))
                self.job(fetch,lambda assets:render(assets) if state['loaded'] and expander.get_expanded() and store is self.store else None,failed)
        expander.connect('notify::expanded',load);load()
    def flag_message(self,msg):
        value=msg.get('flag',{}).get('flagStatus')!='flagged'
        if self.mode=='demo':
            rows=self.store.items('mail',self.folder)
            for row in rows:
                if row['id']==msg['id']:row['flag']={'flagStatus':'flagged' if value else 'notFlagged'}
            self.store.replace('mail',self.folder,rows);self.render_mail();return
        graph=self.graph
        if not graph:self.error('Reconnect before flagging mail.');return
        self.job(lambda:graph.flag(msg['id'],value),lambda _:self.refresh(section='mail'))
    def mark_unread(self,msg):
        if self.mode == 'demo':
            rows=self.store.items('mail',self.folder)
            for x in rows:
                if x['id']==msg['id']: x['isRead']=False
            self.store.replace('mail',self.folder,rows); self.render_mail(); return
        graph=self.graph
        if not graph:self.error('Reconnect your account before changing mailbox messages.');return
        self.job(lambda: graph.set_read(msg['id'],False),lambda _:self.refresh(section='mail'))
    def move_message(self, msg, target):
        if self.mode == 'demo':
            rows=self.store.items('mail',self.folder); self.store.replace('mail',self.folder,[x for x in rows if x['id']!=msg['id']])
            dest=self.store.items('mail',target); self.store.replace('mail',target,dest+[msg]); self.selected=None; self.empty_reader(); self.render_mail(); return
        graph=self.graph
        if not graph:self.error('Reconnect your account before changing mailbox messages.');return
        self.job(lambda: graph.move(msg['id'],target),lambda _:self.refresh(section='mail'))
    def save_attachment(self,mid,file):
        chooser=Gtk.FileChooserNative(title='Save attachment',transient_for=self.win,action=Gtk.FileChooserAction.SAVE,accept_label='Save',cancel_label='Cancel')
        chooser.set_current_name(Path(file.get('name','attachment')).name)
        graph=self.graph
        def chosen(dialog,response):
            if response==Gtk.ResponseType.ACCEPT:
                destination=dialog.get_file().get_path()
                self.job(lambda: Path(destination).write_bytes(graph.attachment(mid,file)), lambda _:self.error('Attachment saved.'))
            dialog.destroy()
        chooser.connect('response',chosen); chooser.show()
    def refresh(self,automatic=False,section=None):
        section=section or self.section
        if self.mode == 'demo':
            if not automatic: self.status.set_text('Demo mode · Sample data only. Connect Google or Microsoft in Settings for live mail.')
            return
        if self.syncing:
            if not automatic:
                self.refresh_pending=True
                if section not in self.pending_sections:self.pending_sections.append(section)
                self.status.set_text('Refresh queued · Checking again as soon as this batch finishes')
            return
        if not self.graph:
            if not automatic:self.status.set_text('Reconnect your account to refresh live mail.')
            return
        retry_at=getattr(self.graph,'backoff_until',0) if automatic or section=='mail' else getattr(self.graph,'service_backoffs',{}).get('calendar' if section=='calendar' else 'people',0)
        if retry_at>time.time():
            remaining=max(1,int(retry_at-time.time()));self.refresh_button.cmail_label.set_text('Refresh (paused)')
            self.status.set_text(f'Google quota pause · Retry in {remaining // 60}m {remaining % 60:02d}s · Cached mail is available')
            return
        self.syncing=True; graph,store,section,folder,generation=self.graph,self.store,section,self.folder,self.generation
        month=self.current_month; self.refresh_button.cmail_label.set_text('Refreshing…');self.status.set_text('Loading calendar…' if section=='calendar' and not automatic else 'Loading contacts…' if section=='contacts' and not automatic else 'Checking for new mail…')
        def sync():
            new_mail=[]
            if automatic or section not in ('calendar','contacts'):
                had_cursor=bool(store.get('delta:inbox'));old_ids={x['id'] for x in store.items('mail','inbox')}
                def progress(loaded,total):
                    def update():
                        if generation==self.generation:
                            self.status.set_text(f'Loading Gmail · {loaded} of {total} messages · You can read loaded mail')
                            if 'mail' in self.panel_built and self.folder=='inbox':self.render_mail()
                        return False
                    GLib.idle_add(update)
                if isinstance(graph,Gmail):graph.sync_mail(store,'inbox',progress=progress,batch_limit=1)
                else:graph.sync_mail(store,'inbox')
                new_mail=[x for x in store.items('mail','inbox') if had_cursor and x['id'] not in old_ids and not x.get('isRead')]
            if section=='mail' and folder!='inbox' and not automatic:
                if isinstance(graph,Gmail):graph.sync_mail(store,folder,batch_limit=1)
                else:graph.sync_mail(store,folder)
            elif section=='contacts' and not automatic: store.replace('contacts','',graph.contacts())
            elif section=='calendar' and not automatic:
                start,end=month_bounds(month.year,month.month)
                rows=graph.calendar(start,end)
                store.replace('events',month.strftime('%Y-%m'),rows)
            return datetime.now().strftime('%H:%M:%S'),new_mail
        def success(result):
            stamp,new_mail=result
            self.syncing=False;self.refresh_button.cmail_label.set_text('Refresh')
            if generation != self.generation: return
            if new_mail and self.config.get('notifications',True):
                notification=Gio.Notification.new('New mail' if len(new_mail)==1 else str(len(new_mail))+' new messages')
                notification.set_body(new_mail[0].get('subject') or '(No subject)');self.send_notification('new-mail',notification)
            store.set('last_sync:'+section,stamp)
            if section=='mail' or automatic:store.set('last_sync',stamp)
            importing=store.get('import:inbox')
            self.status.set_text(('New mail checked · '+stamp+' · Importing older mail: '+str(importing['offset'])+' / '+str(len(importing['refs']))) if importing else 'Up to date · '+stamp+' · Checks every 10 seconds while open')
            if section=='calendar' and not automatic:self.status.set_text('Calendar updated · '+stamp)
            elif section=='contacts' and not automatic:self.status.set_text('Contacts updated · '+stamp)
            if folder==self.folder:self.render_mail()
            if section=='contacts':self.render_contacts()
            elif section=='calendar' and month==self.current_month:self.render_calendar()
            if self.refresh_pending:
                self.refresh_pending=False
                target=self.pending_sections.pop(0) if self.pending_sections else self.section
                self.refresh_pending=bool(self.pending_sections)
                GLib.idle_add(lambda:(self.refresh(section=target) or False))
        def failure(message):
            self.syncing=False;self.refresh_pending=False;self.refresh_button.cmail_label.set_text('Refresh')
            if generation==self.generation:
                self.error(('Calendar sync failed · ' if section=='calendar' else 'Sync paused · ')+message)
                if self.pending_sections:
                    target=self.pending_sections.pop(0);self.refresh_pending=bool(self.pending_sections)
                    GLib.idle_add(lambda:(self.refresh(section=target) or False))
        self.job(sync,success,failure)
    def build_contacts(self):
        content=self.panel_content('contacts');clear(content); box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16)
        box.set_margin_top(24);box.set_margin_start(24);box.set_margin_end(24);content.append(box)
        top=Gtk.Box(spacing=12);top.append(label('Your people','section-title'));top.append(button('Add contact',lambda *_:self.add_contact()));box.append(top)
        box.append(label('Saved contacts and addresses from your cached mail. Online suggestions depend on the connected account.', 'dim-label',True))
        self.contact_search=Gtk.SearchEntry(placeholder_text='Find a saved contact');self.contact_search.connect('search-changed',lambda *_:self.render_contacts());box.append(self.contact_search)
        self.contact_list=Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE);content.append(scroll(self.contact_list));self.render_contacts()
    def render_contacts(self):
        if 'contacts' not in self.panel_built:return
        clear(self.contact_list);term=self.contact_search.get_text().casefold()
        for person in sorted(self.store.items('contacts'),key=lambda x:x.get('displayName','').casefold()):
            addresses=[x['address'] for x in person.get('emailAddresses',[]) if x.get('address')]
            name=person.get('displayName') or '(Unnamed)'
            if term not in (name+' '+' '.join(addresses)).casefold():continue
            row=Adw.ActionRow(title=name,subtitle=' · '.join(addresses))
            if addresses:row.add_suffix(button('Write',lambda _,a=addresses[0]:self.compose(to=a)))
            self.contact_list.append(row)
    def add_contact(self):
        dialog=Gtk.Window(title='Add contact',transient_for=self.docks.parent('contacts'),modal=True,default_width=420)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_top(24);box.set_margin_bottom(24);box.set_margin_start(24);box.set_margin_end(24);dialog.set_child(box)
        name=entry('Name');address=entry('Email address');box.append(name);box.append(address)
        def save(*_):
            try: recipients=email_recipients(address.get_text())
            except AppError as exc:self.error(str(exc));return
            data={'displayName':name.get_text(),'emailAddresses':[recipients[0]['emailAddress']]}
            if self.mode=='demo':
                data['id']=str(uuid.uuid4());self.store.replace('contacts','',self.store.items('contacts')+[data]);dialog.close();self.render_contacts()
            else:
                graph=self.graph
                if not graph:self.error('Reconnect your account before saving a contact.');return
                self.job(lambda:graph.create_contact(data),lambda _:(dialog.close(),self.refresh(section='contacts')))
        box.append(button('Save contact',save,'suggested-action'));dialog.present()
    def build_calendar(self):
        content=self.panel_content('calendar');clear(content)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16);box.set_margin_start(24);box.set_margin_end(24);box.set_margin_top(24)
        content.append(scroll(box));top=Gtk.Box(spacing=12);box.append(top)
        self.month_label=label('','section-title');self.month_label.set_hexpand(True);top.append(self.month_label)
        top.append(button('‹',lambda *_:self.change_month(-1)));top.append(button('Today',lambda *_:self.calendar_today()));top.append(button('›',lambda *_:self.change_month(1)))
        top.append(command_button('Refresh calendar','view-refresh-symbolic',lambda *_:self.refresh(section='calendar')))
        top.append(button('＋ Appointment',lambda *_:self.new_event(),'suggested-action'))
        self.calendar_grid=Gtk.Grid(column_homogeneous=True,row_spacing=6,column_spacing=6);box.append(self.calendar_grid)
        agenda_header=Gtk.Box(spacing=8);self.agenda_title=label('','title-2');self.agenda_title.set_hexpand(True);agenda_header.append(self.agenda_title);agenda_header.append(button('Whole month',lambda *_:self.select_calendar_day(None)));box.append(agenda_header);self.agenda=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);box.append(self.agenda)
        self.render_calendar()
    def change_month(self,delta):
        n=self.current_month.year*12+self.current_month.month-1+delta
        self.current_month=self.current_month.replace(year=n//12,month=n%12+1);self.calendar_selected=self.current_month.date();self.render_calendar();self.refresh(section='calendar')
    def calendar_today(self):
        self.current_month=datetime.now().replace(day=1);self.calendar_selected=datetime.now().date();self.render_calendar();self.refresh(section='calendar')
    def render_calendar(self):
        if 'calendar' not in self.panel_built:return
        clear(self.calendar_grid);clear(self.agenda);self.calendar_days={};month=self.current_month
        self.month_label.set_text(month.strftime('%B %Y'))
        bucket=month.strftime('%Y-%m');rows=self.store.items('events',bucket)
        if self.mode=='demo':
            removed=set(self.store.get('deleted_events:'+bucket,[]));combined={e['id']:e for e in demo.events(month.year,month.month) if e['id'] not in removed};combined.update({e['id']:e for e in rows});rows=list(combined.values())
        self.events=rows;by_day={}
        for item in rows:
            try:
                start=event_datetime(item['start'])
                if start.year==month.year and start.month==month.month:by_day.setdefault(start.day,[]).append(item)
            except (KeyError,ValueError):continue
        for col,name in enumerate(['Mon','Tue','Wed','Thu','Fri','Sat','Sun']):self.calendar_grid.attach(label(name,'dim-label'),col,0,1,1)
        today=datetime.now()
        for row,week in enumerate(calendar.monthcalendar(month.year,month.month),1):
            for col,day in enumerate(week):
                cell=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
                if day:
                    chosen=month.replace(day=day).date();day_button=Gtk.Button();day_button.add_css_class('calendar-day');day_button.set_child(cell);day_button.set_hexpand(True)
                    self.calendar_days[day]=day_button
                    day_button.set_tooltip_text(chosen.strftime('%A %d %B')+f' · {len(by_day.get(day,[]))} appointments')
                    day_button.connect('clicked',lambda _,value=chosen:self.select_calendar_day(value))
                    if chosen==today.date():day_button.add_css_class('today')
                    if chosen==self.calendar_selected:day_button.add_css_class('selected')
                    cell.append(label(str(day),'sender'))
                    for item in by_day.get(day,[])[:2]:
                        chip=label(item['subject'],'event-chip');chip.set_ellipsize(3);cell.append(chip)
                    if len(by_day.get(day,[]))>2:cell.append(label(f'+{len(by_day[day])-2} more','preview'))
                    self.calendar_grid.attach(day_button,col,row,1,1)
                else:self.calendar_grid.attach(cell,col,row,1,1)
        self.agenda_title.set_text(self.calendar_selected.strftime('%A %d %B') if self.calendar_selected else 'This month')
        displayed=[]
        for item in rows:
            try:start=event_datetime(item['start'])
            except Exception:continue
            if self.calendar_selected:
                try:end=event_datetime(item['end'])
                except Exception:end=start
                # All-day provider end dates are exclusive; timed overnight events span days.
                last=(end-timedelta(microseconds=1)).date() if end>start else start.date()
                if not start.date()<=self.calendar_selected<=last:continue
            displayed.append((start,item))
        for start,item in sorted(displayed,key=lambda pair:pair[0]):
            card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);card.append(label(item.get('subject','Appointment'),'sender'))
            detail=('All day' if item.get('isAllDay') else start.strftime('%H:%M'))+' · '+start.strftime('%a %d %b')
            card.append(label(detail+' · '+item.get('location',{}).get('displayName',''),'dim-label'))
            appointment=Gtk.Button();appointment.add_css_class('flat');appointment.set_child(card);appointment.set_hexpand(True);appointment.set_tooltip_text('Open appointment details');appointment.connect('clicked',lambda _,event=item:self.event_details(event))
            row=Gtk.Box(spacing=8);row.add_css_class('card');row.append(appointment)
            edit=button('Edit',lambda _,event=item:self.new_event(event=event));edit.set_valign(Gtk.Align.CENTER);row.append(edit)
            delete=button('Delete',lambda _,event=item:self.delete_calendar_event(event));delete.set_valign(Gtk.Align.CENTER);row.append(delete);self.agenda.append(row)
        if not displayed:self.agenda.append(label('No appointments on this day.' if self.calendar_selected else 'No cached events this month. Refresh to load your calendar.','dim-label'))
    def select_calendar_day(self,value):
        self.calendar_selected=value;self.render_calendar()
    def event_details(self,event):
        dialog=Adw.Window(title='Appointment details',transient_for=self.docks.parent('calendar'),default_width=470,default_height=350)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_top(20);box.set_margin_bottom(20);box.set_margin_start(20);box.set_margin_end(20);dialog.set_content(box)
        box.append(label(event.get('subject','Appointment'),'title-2',True))
        for name in ('start','end'):
            try:stamp=event_datetime(event[name]);box.append(label(name.title()+': '+stamp.strftime('%a %d %b %Y · %H:%M %Z'),'dim-label',True))
            except Exception:pass
        if event.get('isAllDay'):box.append(label('All-day appointment','sender'))
        location=event.get('location',{}).get('displayName','')
        if location:box.append(label('Location: '+location,'dim-label',True))
        description=plain_body(event.get('body',{})) or event.get('bodyPreview','')
        if description:box.append(scroll(label(description,'',True)))
        controls=Gtk.Box(spacing=8);box.append(controls)
        controls.append(button('Edit appointment',lambda *_:(dialog.close(),self.new_event(event=event))))
        controls.append(button('Delete appointment',lambda *_:self.delete_calendar_event(event,dialog),'destructive-action'))
        controls.append(button('Close',lambda *_:dialog.close()));dialog.present()
    def remove_cached_event(self,event):
        bucket=event_datetime(event['start']).strftime('%Y-%m')
        self.store.replace('events',bucket,[e for e in self.store.items('events',bucket) if e['id']!=event['id']])
        if self.mode=='demo':self.store.set('deleted_events:'+bucket,list(set(self.store.get('deleted_events:'+bucket,[]))|{event['id']}))
    def delete_calendar_event(self,event,parent=None):
        dialog=Adw.MessageDialog(transient_for=parent or self.docks.parent('calendar'),heading='Delete appointment?',body=event.get('subject','Appointment')+(' · This occurrence only.' if event.get('recurringEventId') or event.get('type')=='occurrence' else ''))
        dialog.add_response('cancel','Keep');dialog.add_response('delete','Delete');dialog.set_response_appearance('delete',Adw.ResponseAppearance.DESTRUCTIVE);dialog.set_default_response('cancel')
        def remove(_,response):
            if response!='delete':return
            graph,store=self.graph,self.store
            def success(_=None):
                if self.store is not store:return
                self.remove_cached_event(event)
                if parent:parent.close()
                self.render_calendar();self.error('Appointment deleted.')
            if self.mode=='demo':success()
            elif graph:self.job(lambda:graph.delete_event(event['id']),success)
            else:self.error('Reconnect your account before deleting an appointment.')
        dialog.connect('response',remove);dialog.present()
    def new_event(self,proposal=None,event=None):
        dialog=Gtk.Window(title='Edit appointment' if event else 'New appointment',transient_for=self.docks.parent('calendar'),modal=True,default_width=440)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_top(24);box.set_margin_bottom(24);box.set_margin_start(24);box.set_margin_end(24);dialog.set_child(box)
        title=entry('Appointment title');date=entry('YYYY-MM-DD',(self.calendar_selected if self.calendar_selected else datetime.now().date()).isoformat());clock=entry('HH:MM','10:00');duration=entry('Duration in minutes','60');location=entry('Location (optional)')
        if proposal:
            title.set_text(proposal.get('title',''));location.set_text(proposal.get('location',''));duration.set_text(str(proposal.get('duration',60)))
            try:
                start=datetime.fromisoformat(proposal['start'].replace('Z','+00:00')).astimezone();date.set_text(start.strftime('%Y-%m-%d'));clock.set_text(start.strftime('%H:%M'))
            except (ValueError,KeyError):pass
        all_day=Gtk.CheckButton(label='All-day appointment',active=bool(event and event.get('isAllDay')))
        if event:
            title.set_text(event.get('subject',''));location.set_text(event.get('location',{}).get('displayName',''))
            start=event_datetime(event['start']);end=event_datetime(event['end']);date.set_text(start.strftime('%Y-%m-%d'));clock.set_text(start.strftime('%H:%M'));duration.set_text(str(max(1,round((end-start).total_seconds()/60))))
        all_day.connect('toggled',lambda w:clock.set_sensitive(not w.get_active()));clock.set_sensitive(not all_day.get_active())
        for text,w in [('Title',title),('Date',date),('Time · your system timezone',clock),('Duration',duration),('Location',location)]:box.append(label(text));box.append(w)
        box.append(all_day)
        info=label('Saves an appointment in your primary calendar. Meeting invitations and recurrence editing are not included yet.','dim-label',True);box.append(info)
        def save(*_):
            try:
                if not title.get_text().strip():raise ValueError()
                start=datetime.fromisoformat(date.get_text()+'T'+('00:00' if all_day.get_active() else clock.get_text())).astimezone();minutes=int(duration.get_text())
                if all_day.get_active():minutes=max(1440,round(minutes/1440)*1440)
                if not 1<=minutes<=10080:raise ValueError()
            except ValueError:self.error('Enter a title, valid date/time and duration of 1–10080 minutes.');return
            data={'subject':title.get_text(),'start':{'dateTime':utc_iso(start),'timeZone':'UTC'},'end':{'dateTime':utc_iso(start+timedelta(minutes=minutes)),'timeZone':'UTC'},'location':{'displayName':location.get_text()},'isAllDay':all_day.get_active()}
            if all_day.get_active():data['start']['dateTime']=start.isoformat();data['end']['dateTime']=(start+timedelta(minutes=minutes)).isoformat();data['start']['timeZone']=str(start.tzinfo);data['end']['timeZone']=str(start.tzinfo)
            if self.mode=='demo':
                data['id']=event['id'] if event else str(uuid.uuid4());bucket=start.strftime('%Y-%m');
                if event:self.remove_cached_event(event)
                self.store.replace('events',bucket,self.store.items('events',bucket)+[data]);dialog.close();self.render_calendar()
            else:
                graph=self.graph
                if not graph:self.error('Reconnect your account before saving an appointment.');return
                save_button.set_sensitive(False)
                def saved(_):
                    if event:self.remove_cached_event(event)
                    dialog.close();self.refresh(section='calendar')
                def failed(message):save_button.set_sensitive(True);self.error(message)
                self.job(lambda:graph.update_event(event['id'],data) if event else graph.create_event(data),saved,failed)
        save_button=button('Save changes' if event else 'Create appointment',save,'suggested-action');box.append(save_button);box.append(button('Cancel',lambda *_:dialog.close()));dialog.present()
    def build_drafts(self):
        content=self.panel_content('drafts');clear(content);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_top(24);box.set_margin_start(24);box.set_margin_end(24);content.append(scroll(box))
        box.append(label('Local drafts','section-title'));box.append(label('Saved on this computer. Provider drafts appear in the mail folder list.','dim-label',True))
        rows=self.store.drafts()
        for draft in rows:
            card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);card.add_css_class('card');box.append(card)
            card.append(label(draft.get('subject') or '(No subject)','sender'));card.append(label(draft.get('to') or '(No recipient)','dim-label'))
            state=draft['state'];card.append(label({'draft':'Ready to edit','sending':'Send in progress','uncertain':'Send result unknown — check your mailbox Sent folder','accepted':'The provider accepted this send request; delivery is not confirmed.'}[state],'dim-label',True))
            if state=='draft':card.append(button('Continue writing',lambda _,d=draft:self.compose(draft=d)))
            if state in ('uncertain','accepted'):
                card.append(label('Keep this record until you have checked the mailbox. It is not automatically resent.','dim-label',True))
            if state!='sending':card.append(button('Remove local record',lambda _,d=draft:self.discard_draft(d)))
        if not rows:box.append(label('Nothing waiting. Drafts save automatically as you write.','dim-label'))
    def discard_draft(self,draft):
        dialog=Adw.MessageDialog(transient_for=self.win,heading='Remove local draft?',body='This removes the copy on this computer. Any provider draft remains in your mailbox.')
        dialog.add_response('cancel','Keep');dialog.add_response('remove','Remove');dialog.set_response_appearance('remove',Adw.ResponseAppearance.DESTRUCTIVE)
        def respond(_,response):
            if response=='remove':self.store.delete_draft(draft['id']);self.build_drafts()
        dialog.connect('response',respond);dialog.present()
    def compose(self,to='',reply=None,draft=None,reply_all=False,forward=None):
        store=self.store;graph=self.graph;mode=self.mode
        if draft and draft.get('state','draft')!='draft':self.error('This draft has a pending or uncertain send result. Check Sent Items.');return
        draft=dict(draft or {'id':str(uuid.uuid4()),'to':to,'subject':'','body':'','attachments':[]})
        if reply:
            sender=reply.get('from',{}).get('emailAddress',{})
            draft.update(to=sender.get('address',''),subject=('' if reply.get('subject','').lower().startswith('re:') else 'Re: ')+reply.get('subject',''),reply_id=reply['id'])
        if reply_all and reply:
            own=(self.config.get('last_account') or {}).get('profile',{}).get('mail','').casefold()
            others=[c.get('emailAddress',{}).get('address','') for c in reply.get('toRecipients',[])+reply.get('ccRecipients',[]) if c.get('emailAddress',{}).get('address','').casefold()!=own]
            draft['cc']=', '.join(dict.fromkeys(a for a in others if a and a.casefold()!=draft['to'].casefold()));draft['reply_all']=True
        if forward:
            original=next((m for m in store.items('body') if m['id']==forward['id']),forward)
            sender=forward.get('from',{}).get('emailAddress',{}).get('address','')
            draft.update(subject='Fwd: '+forward.get('subject',''),body='\n\n— Forwarded message —\nFrom: '+sender+'\nSubject: '+forward.get('subject','')+'\n\n'+(plain_body(original.get('body',{})) or forward.get('bodyPreview','')),forwarded=True)
        if any(getattr(w,'draft_id',None)==draft['id'] for w in self.compose_windows):
            next(w for w in self.compose_windows if w.draft_id==draft['id']).present();return
        win=Adw.Window(title='New message · CMail',transient_for=self.docks.parent('mail'),default_width=900,default_height=740)
        win.draft_id=draft['id'];self.compose_windows.add(win)
        outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);win.set_content(outer)
        header=Adw.HeaderBar();header.set_title_widget(label('New message','sender'));outer.append(header)
        send_button=button('Send' if mode=='live' else 'Simulate send',lambda *_:send(),'suggested-action');header.pack_end(send_button)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_top(18);box.set_margin_bottom(18);box.set_margin_start(24);box.set_margin_end(24);box.set_vexpand(True);outer.append(box)
        if mode=='demo':box.append(label('Demo mode · Nothing leaves this computer.','demo-banner',True))
        recipient=entry('Email addresses, separated by commas',draft.get('to',''));subject=entry('Subject',draft.get('subject',''))
        cc=entry('CC addresses',draft.get('cc',''));bcc=entry('BCC addresses',draft.get('bcc',''))
        win.recipient_fields={'to':recipient,'cc':cc,'bcc':bcc,'subject':subject}
        recipients=Gtk.Grid(column_spacing=12,row_spacing=8);recipients.attach(label('To','dim-label'),0,0,1,1);recipients.attach(recipient,1,0,1,1)
        copy_toggle=Gtk.ToggleButton(label='CC / BCC',active=bool(draft.get('cc') or draft.get('bcc')));recipients.attach(copy_toggle,2,0,1,1)
        cc_label=label('Cc','dim-label');bcc_label=label('Bcc','dim-label');recipients.attach(cc_label,0,1,1,1);recipients.attach(cc,1,1,2,1);recipients.attach(bcc_label,0,2,1,1);recipients.attach(bcc,1,2,2,1)
        def copies(*_):
            for widget in (cc,cc_label,bcc,bcc_label):widget.set_visible(copy_toggle.get_active())
        copy_toggle.connect('toggled',copies);copies();box.append(recipients)
        suggestions=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);box.append(suggestions)
        subjectrow=Gtk.Box(spacing=12);subjectrow.append(label('Subject','dim-label'));subjectrow.append(subject);box.append(subjectrow)
        editor=RichEditor(draft.get('formatting'),draft.get('body',''));body=editor.view;win.editor=editor
        def insert_link():
            dialog=Gtk.Window(title='Insert link',transient_for=win,modal=True,default_width=450)
            form=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);form.set_margin_start(20);form.set_margin_end(20);form.set_margin_top(20);form.set_margin_bottom(20);dialog.set_child(form)
            url=entry('https://example.com');caption=entry('Link text (optional)');form.append(url);form.append(caption)
            def apply(*_):
                try:editor.link(url.get_text().strip(),caption.get_text() or None);dialog.close()
                except ValueError as exc:self.error(str(exc))
            form.append(button('Insert link',apply,'suggested-action'));dialog.present()
        win.format_toolbar=editor.toolbar(insert_link);outer.insert_child_after(win.format_toolbar,header);box.append(scroll(body))
        if draft.get('forwarded'):box.append(label('Forwarded text is included. Attach original files manually if needed.','dim-label',True))
        files_box=Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,column_spacing=8,row_spacing=8,min_children_per_line=1,max_children_per_line=4);box.append(files_box)
        bottom=Gtk.Box(spacing=12);box.append(bottom)
        attach=button('＋ Attach files',lambda *_:choose_attachment());bottom.append(attach)
        limit=graph.attachment_limit if graph else 20_000_000;limit_label=label(f'{limit/1_000_000:g} MB limit','preview');bottom.append(limit_label)
        state_label=label('Draft saved locally','dim-label');state_label.set_hexpand(True);bottom.append(state_label)
        pending={'save':0,'suggest':0,'serial':0,'sending':False,'closed':False}
        def snapshot():
            text,formatting,html=editor.snapshot();draft.update(to=recipient.get_text(),cc=cc.get_text(),bcc=bcc.get_text(),subject=subject.get_text(),body=text,formatting=formatting,html=html);return draft
        def save_now():
            pending['save']=0
            if pending['sending'] or pending['closed']:return False
            store.draft(snapshot());state_label.set_text('Draft saved locally');return False
        def changed(*_):
            if pending['sending']:return
            if pending['save']:GLib.source_remove(pending['save'])
            pending['save']=GLib.timeout_add(450,save_now)
        editor.on_change=changed
        def show_files():
            clear(files_box)
            for file in draft.get('attachments',[]):
                row=Gtk.Box(spacing=8);row.add_css_class('attachment-chip')
                try:size=Path(file).stat().st_size;size_text=f'{size/1000:.0f} KB' if size<1_000_000 else f'{size/1_000_000:.1f} MB'
                except OSError:size_text='Missing file'
                row.append(label(Path(file).name+' · '+size_text));row.append(button('×',lambda _,f=file:remove_file(f)));files_box.insert(row,-1)
        def remove_file(file):draft['attachments'].remove(file);show_files();save_now()
        def add_files(paths):
            try:
                unique=list(dict.fromkeys(draft.get('attachments',[])+paths))
                if sum(Path(x).stat().st_size for x in unique)>limit:raise AppError(f'Attachments exceed the {limit/1_000_000:g} MB limit for this connection.')
                draft['attachments']=unique;show_files();save_now()
            except Exception as exc:self.error(str(exc))
        def choose_attachment():
            chooser=Gtk.FileChooserNative(title='Attach files',transient_for=win,action=Gtk.FileChooserAction.OPEN,accept_label='Attach',cancel_label='Cancel');chooser.set_select_multiple(True)
            def chosen(dialog,response):
                if response==Gtk.ResponseType.ACCEPT:
                    files=dialog.get_files();add_files([files.get_item(i).get_path() for i in range(files.get_n_items())])
                dialog.destroy()
            chooser.connect('response',chosen);chooser.show()
        drop=Gtk.DropTarget.new(Gdk.FileList,Gdk.DragAction.COPY)
        def dropped(_,value,x,y):
            if pending['sending']:return False
            add_files([file.get_path() for file in value.get_files() if file.get_path()]);return True
        drop.connect('drop',dropped);body.add_controller(drop)
        def add_suggestion(name,address,target):
            def select(*_):
                existing=target.get_text().replace(';',',').split(',');existing[-1]=address;target.set_text(', '.join(x.strip() for x in existing));clear(suggestions)
            suggestions.append(button(name+'  ·  '+address,select))
        def suggest(target,*_):
            pending['serial']+=1;serial=pending['serial'];clear(suggestions)
            if pending['suggest']:GLib.source_remove(pending['suggest'])
            term=target.get_text().replace(';',',').split(',')[-1].strip()
            if len(term)<2:return
            matches=[]
            local_people=store.items('contacts')
            for message in store.items('mail','inbox'):
                for contact in [message.get('from',{})]+message.get('toRecipients',[])+message.get('ccRecipients',[]):
                    e=contact.get('emailAddress',{})
                    if e.get('address'):local_people.append({'displayName':e.get('name') or e['address'],'emailAddresses':[e]})
            for person in local_people:
                for email in person.get('emailAddresses',[]):
                    address=email.get('address','');name=person.get('displayName',address)
                    if address and term.casefold() in (name+' '+address).casefold():matches.append((name,address))
            seen=set()
            for name,address in matches[:5]:add_suggestion(name,address,target);seen.add(address.casefold())
            if mode=='live' and graph:
                def search_people():
                    pending['suggest']=0
                    def complete(values):
                        if pending['closed'] or pending['serial']!=serial:return
                        for name,address in values[:5]:
                            if address.casefold() not in seen:add_suggestion(name,address,target);seen.add(address.casefold())
                    def failure(message):
                        if pending['closed'] or pending['serial']!=serial:return
                        suggestions.append(label('Online contact search unavailable. Local suggestions still work.','dim-label',True))
                    self.job(lambda:graph.people(term),complete,failure);return False
                pending['suggest']=GLib.timeout_add(600,search_people)
        recipient.connect('changed',changed);recipient.connect('changed',suggest);cc.connect('changed',changed);cc.connect('changed',suggest);bcc.connect('changed',changed);bcc.connect('changed',suggest);subject.connect('changed',changed);body.get_buffer().connect('changed',changed)
        def lock(value):
            for widget in (recipient,cc,bcc,subject,body,attach,files_box,copy_toggle):widget.set_sensitive(not value)
            send_button.set_sensitive(not value)
        def send():
            if pending['sending']:return
            snapshot()
            try:
                if mode=='live' and not graph:raise AppError('Reconnect your account before sending. Your local draft is saved.')
                email_recipients(draft['to'])
                if not draft['subject'].strip():raise AppError('Add a subject before sending.')
                for field in ('cc','bcc'):
                    if draft.get(field,'').strip():email_recipients(draft[field])
                if sum(Path(x).stat().st_size for x in draft.get('attachments',[]))>limit:raise AppError('Attachments exceed this connection’s limit.')
            except Exception as exc:state_label.set_text(str(exc));return
            profile=(self.config.get('last_account') or {}).get('profile',{});draft['sender']={'name':profile.get('displayName','Me'),'address':profile.get('mail') or profile.get('userPrincipalName','')}
            save_now();pending['sending']=True;lock(True);state_label.set_text('Submitting message…')
            def success(_):
                pending['sending']=False;pending['closed']=True;win.close()
                self.error('Demo send simulated. No email was sent.' if mode=='demo' else 'The send request was accepted. Check your Sent folder for the saved copy.')
                if 'drafts' in self.panel_built:self.build_drafts()
                if 'mail' in self.panel_built and store is self.store and draft.get('sent_message_id'):
                    self.reader_key=None;self.render_mail()
                self.refresh()
            def failure(message):
                pending['sending']=False
                record=next((x for x in store.drafts() if x['id']==draft['id']),{})
                if record.get('state')=='uncertain':
                    lock(True);state_label.set_text('Send result unknown. Check your mailbox Sent folder. This record is kept in Local drafts.');return
                lock(False);state_label.set_text(message[:250])
            if mode=='demo':store.draft(draft,'accepted');success(None)
            else:self.job(lambda:graph.send(store,draft),success,failure)
        def close(*_):
            if pending['sending']:state_label.set_text('Wait for the send result before closing this window.');return True
            if not pending['closed']:
                record=next((x for x in store.drafts() if x['id']==draft['id']),{})
                if record.get('state') not in ('uncertain','accepted'):store.draft(snapshot())
            pending['closed']=True
            for key in ('save','suggest'):
                if pending[key]:GLib.source_remove(pending[key]);pending[key]=0
            self.compose_windows.discard(win);return False
        win.connect('close-request',close);show_files();save_now();win.present()
    def settings(self):
        if self.settings_window is not None:
            self.settings_window.close(); return
        win=Adw.Window(title='Settings · CMail',transient_for=self.win,default_width=610,default_height=720)
        self.settings_window=win
        def settings_closed(*_):
            if self.settings_window is win:self.settings_window=None
            self.settings_button.remove_css_class('suggested-action')
            return False
        win.connect('close-request',settings_closed)
        escape=Gtk.EventControllerKey()
        def settings_key(_,keyval,*args):
            if keyval==Gdk.KEY_Escape:win.close();return True
            return False
        escape.connect('key-pressed',settings_key);win.add_controller(escape)
        self.settings_button.add_css_class('suggested-action')
        layout=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);win.set_content(layout)
        settings_header=Adw.HeaderBar();settings_header.set_show_start_title_buttons(False);settings_header.set_show_end_title_buttons(False);settings_header.set_title_widget(label('Settings','sender'));settings_header.pack_start(button('✕ Close',lambda *_:win.close()));layout.append(settings_header)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18);box.set_margin_top(24);box.set_margin_bottom(24);box.set_margin_start(24);box.set_margin_end(24);layout.append(scroll(box))
        box.append(label('Make it yours','section-title'))
        theme_updates={'busy':False}
        row=Gtk.Box(spacing=12);theme=Gtk.Switch(active=bool(self.config.get('dark',True)));row.append(label('Navy night theme'));row.append(theme);box.append(row)
        def theme_change(s,_):
            self.config.set('dark',s.get_active())
            if not theme_updates['busy'] and self.config.get('theme_preset','Custom')=='Custom':save_custom_theme(self.config)
            self.apply_theme()
        theme.connect('notify::active',theme_change)
        notification_row=Gtk.Box(spacing=12);notification_switch=Gtk.Switch(active=self.config.get('notifications',True));notification_row.append(label('Desktop mail notifications'));notification_row.append(notification_switch);box.append(notification_row)
        notification_switch.connect('notify::active',lambda switch,_:self.config.set('notifications',switch.get_active()))
        performance=Gtk.CheckButton(label='Low-power rendering (recommended)',active=self.config.get('low_power',True));box.append(performance)
        box.append(label('Reduces effects and browser compositing. Long HTML emails scroll inside a bounded body area; their full content remains available.','dim-label',True))
        def performance_changed(w):
            self.config.set('low_power',w.get_active());self.apply_layout()
            if 'mail' in self.panel_built:self.reader_key=None;self.render_mail()
        performance.connect('toggled',performance_changed)
        box.append(label('Inbox row style','title-2'))
        row_styles=Gtk.DropDown.new_from_strings(['Current size · message cards','Compact · single-line messages'])
        row_styles.set_selected(1 if self.config.get('mail_density','cards')=='compact' else 0);box.append(row_styles)
        box.append(label('Keep the current larger email rows, or use the compact list from concept C. This is independent of interface scale.','dim-label',True))
        def rows_changed(widget,_):
            self.config.set('mail_density','compact' if widget.get_selected() else 'cards');self.apply_theme()
            if 'mail' in self.panel_built:self.render_mail()
        row_styles.connect('notify::selected',rows_changed)
        box.append(label('Interface scale','title-2'))
        scale_label=label(f'{round(self.ui_scale()*100)}% · Smaller controls, text and email content','dim-label');box.append(scale_label)
        scale_control=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,65,120,5);scale_control.set_value(self.ui_scale()*100);scale_control.set_draw_value(False);box.append(scale_control)
        def scale_changed(w):
            self.config.set('ui_scale',round(w.get_value())/100);scale_label.set_text(f'{round(w.get_value())}% · Smaller controls, text and email content');self.apply_layout()
            if self.section=='mail':self.build_mail()
            elif self.section=='calendar':self.render_calendar()
        scale_control.connect('value-changed',scale_changed)
        box.append(label('Theme presets','title-2'));preset_names=['Custom']+list(PRESETS);presets=Gtk.DropDown.new_from_strings(preset_names);presets.set_selected(preset_names.index(self.config.get('theme_preset','Custom')) if self.config.get('theme_preset','Custom') in preset_names else 0);box.append(presets);pickers={}
        def choose_preset(w,_):
            if theme_updates['busy']:return
            name=preset_names[w.get_selected()];theme_updates['busy']=True
            try:
                select_theme(self.config,name);theme.set_active(self.config.get('dark',True))
                for key,picker in pickers.items():
                    rgba=Gdk.RGBA();rgba.parse(self.config.get('color_'+key) or PRESETS['Crimson Orbit'][key]);picker.set_rgba(rgba)
            finally:theme_updates['busy']=False
            self.apply_layout()
            if 'mail' in self.panel_built:self.reader_key=None;self.render_mail()
        presets.connect('notify::selected',choose_preset)
        box.append(label('Email timezone','title-2'));tz=entry('IANA timezone, e.g. Pacific/Auckland',self.config.get('display_timezone','Pacific/Auckland'));box.append(tz)
        def save_timezone():
            value=tz.get_text().strip()
            try:ZoneInfo(value)
            except (ZoneInfoNotFoundError,ValueError):self.error('Enter a valid timezone such as Pacific/Auckland.');return
            self.config.set('display_timezone',value)
            if 'mail' in self.panel_built:self.reader_key=None;self.render_mail()
        box.append(button('Save timezone',lambda *_:save_timezone()))
        box.append(label('Custom colours','title-2'))
        for key,name,default in [('background','Background','#0b1222'),('surface','Panels & navigation','#101a2e'),('cards','Cards','#152139'),('mail','Email HTML background','#242831'),('text','Text','#e6edf8'),('accent','Highlight','#ff7187'),('buttons','Buttons','#c63d56')]:
            row=Gtk.Box(spacing=12);caption=label(name);caption.set_hexpand(True);row.append(caption)
            rgba=Gdk.RGBA();rgba.parse(self.config.get('color_'+key) or default);picker=Gtk.ColorButton();picker.set_rgba(rgba);picker.set_use_alpha(False);row.append(picker);box.append(row);pickers[key]=picker
            def color_changed(w,k=key):
                c=w.get_rgba();customize_color(self.config,k,'#%02x%02x%02x'%tuple(round(v*255) for v in (c.red,c.green,c.blue)))
                theme_updates['busy']=True;presets.set_selected(0);theme_updates['busy']=False;self.apply_theme()
                if k in ('mail','text') and 'mail' in self.panel_built:self.reader_key=None;self.render_mail()
            picker.connect('color-set',color_changed)
        def reset_colors():
            self.config.set('theme_preset','Custom')
            for key in ('background','surface','cards','mail','text','accent','buttons'):self.config.set('color_'+key,None)
            save_custom_theme(self.config);self.apply_theme();win.close();self.settings()
        box.append(button('Reset colours',lambda *_:reset_colors()))
        box.append(label('Workspace layout','title-2'))
        for key,name in [('sidebar','Folder sidebar'),('topnav','Top navigation'),('commands','Mail command bar'),('banner','Connection banner'),('reader','Reading pane')]:
            toggle=Gtk.CheckButton(label=name,active=self.config.get('show_'+key,True));box.append(toggle)
            def visibility(w,k=key):
                self.config.set('show_'+k,w.get_active());self.apply_layout()
                if self.section=='mail':self.build_mail()
            toggle.connect('toggled',visibility)
        images=Gtk.CheckButton(label='Load email images automatically',active=self.config.get('load_remote_images',True));box.append(images)
        def image_preference(w):
            self.config.set('load_remote_images',w.get_active())
            if 'mail' in self.panel_built:self.reader_key=None;self.render_mail()
        images.connect('toggled',image_preference)
        compact=Gtk.CheckButton(label='Compact spacing',active=self.config.get('compact',True));compact.connect('toggled',lambda w:(self.config.set('compact',w.get_active()),self.apply_theme()));box.append(compact)
        bottom=Gtk.CheckButton(label='Reading pane below messages',active=self.config.get('pane_bottom',False));bottom.connect('toggled',lambda w:(self.config.set('pane_bottom',w.get_active()),self.build_mail()));box.append(bottom)
        box.append(label('Folder sidebar width · drag the mail divider to resize columns','dim-label',True))
        width=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,150,350,10);width.set_value(self.config.get('sidebar_width',220));width.connect('value-changed',lambda w:(self.config.set('sidebar_width',int(w.get_value())),self.apply_layout()));box.append(width)
        box.append(Gtk.Separator());box.append(label('Assistant','title-2'))
        ai_toggle=Gtk.CheckButton(label='Show AI features',active=self.config.get('show_ai',True));box.append(ai_toggle)
        ai_options=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.append(ai_options);ai_options.set_visible(self.config.get('show_ai',True))
        def ai_visibility(w):
            enabled=w.get_active();self.config.set('show_ai',enabled);ai_options.set_visible(enabled);self.apply_layout()
            if not enabled and self.assistant_window:self.assistant_window.close()
        ai_toggle.connect('toggled',ai_visibility)
        ai_options.append(label('ChatGPT ↗ opens your browser session. The in-app assistant uses your own OpenAI API key and separate API billing. It only drafts mail and proposes appointments for you to review.','dim-label',True))
        key_entry=Gtk.PasswordEntry(show_peek_icon=True,placeholder_text='OpenAI API key');ai_options.append(key_entry)
        model=entry('API model',self.config.get('assistant_model','gpt-5-mini'));ai_options.append(model)
        def save_key():
            key=key_entry.get_text().strip();key_entry.set_text('')
            if not key:self.error('Enter an API key to save.');return
            self.config.set('assistant_model',model.get_text().strip() or 'gpt-5-mini');self.job(lambda:SecretVault('openai-api').save(key),lambda _:self.error('Assistant key saved in your desktop keyring.'))
        ai_options.append(button('Save assistant key',lambda *_:save_key()));ai_options.append(button('Remove assistant key',lambda *_:self.job(lambda:SecretVault('openai-api').clear(),lambda _:self.error('Assistant key removed.'))))
        ai_options.append(Gtk.LinkButton(uri='https://platform.openai.com/api-keys',label='OpenAI API keys'))
        box.append(Gtk.Separator());box.append(label('Google / Gmail','title-2'))
        box.append(label('Choose Google browser sign-in, or use a Gmail app password with two-step verification enabled. A Google API key alone cannot open your inbox.','dim-label',True))
        google_info=label('Desktop OAuth credentials imported' if self.config.get('google_client_id') else 'No Google OAuth credentials imported yet.','dim-label',True);box.append(google_info)
        def import_google():
            chooser=Gtk.FileChooserNative(title='Import Google Desktop OAuth JSON',transient_for=win,action=Gtk.FileChooserAction.OPEN,accept_label='Import',cancel_label='Cancel')
            def selected(dialog,response):
                if response==Gtk.ResponseType.ACCEPT:
                    path=dialog.get_file().get_path()
                    def load():
                        credentials=credentials_from_json(path);SecretVault('google-config:'+credentials['client_id']).save(json.dumps(credentials));return credentials['client_id']
                    def imported(client_id):self.config.set('google_client_id',client_id);google_info.set_text('Google desktop credentials imported. Ready to sign in.')
                    self.job(load,imported,lambda msg:google_info.set_text(msg))
                dialog.destroy()
            chooser.connect('response',selected);chooser.show()
        box.append(button('Import Google OAuth JSON',lambda *_:import_google()))
        options=Gtk.Box(spacing=12);cal=Gtk.CheckButton(label='Google Calendar',active=self.config.get('google_calendar',False));people=Gtk.CheckButton(label='Google Contacts',active=self.config.get('google_contacts',False));options.append(cal);options.append(people);box.append(options)
        def google_signin():
            self.config.set('google_calendar',cal.get_active());self.config.set('google_contacts',people.get_active())
            google_info.set_text('Complete Google sign-in in your browser.');self.connect_account(provider='google',done=lambda:google_info.set_text('Google connected.'),failed=lambda msg:google_info.set_text(msg))
        box.append(button('Sign in with Google',lambda *_:google_signin(),'suggested-action'))
        password_expander=Gtk.Expander(label='Connect using a Gmail app password');password_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);password_expander.set_child(password_box);box.append(password_expander)
        gmail_address=entry('Your Gmail address',self.config.get('gmail_address',''));password_box.append(gmail_address)
        gmail_password=Gtk.PasswordEntry(show_peek_icon=True,placeholder_text='16-letter Google app password');password_box.append(gmail_password)
        password_box.append(Gtk.LinkButton(uri='https://myaccount.google.com/apppasswords',label='Create an app password named CMail'))
        password_box.append(label('Keep 2FA enabled. Use an app password, not your normal password. This route connects mail; Calendar and Contacts require Google OAuth.','dim-label',True))
        def password_connect():
            address=gmail_address.get_text().strip();password=gmail_password.get_text();gmail_password.set_text('')
            self.config.set('gmail_address',address);google_info.set_text('Connecting to Gmail over encrypted IMAP/SMTP…')
            self.connect_account(provider='gmail_password',password=password,done=lambda:google_info.set_text('Gmail connected.'),failed=lambda msg:google_info.set_text(msg))
        password_box.append(button('Connect Gmail',lambda *_:password_connect(),'suggested-action'))
        box.append(Gtk.LinkButton(uri='https://console.cloud.google.com/auth/clients',label='Google OAuth setup · Desktop app'))
        box.append(Gtk.Separator());box.append(label('Microsoft account','title-2'))
        box.append(label('Register a Mobile and desktop application in Microsoft Entra with the redirect URI http://localhost. Use the Application (client) ID below. No client secret is needed.','dim-label',True))
        client=entry('Application (client) ID',self.config.get('client_id',''));box.append(client)
        help_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        help_box.append(label('Open Microsoft Entra → Entra ID → App registrations. Open an existing app or choose New registration. Copy Application (client) ID from its Overview page. Your school may need to create or approve the registration.','dim-label',True))
        help_box.append(Gtk.LinkButton(uri='https://entra.microsoft.com/',label='Open Microsoft Entra'))
        help_expander=Gtk.Expander(label='Where do I get my client ID?');help_expander.set_child(help_box);box.append(help_expander)
        tenant=entry('Directory (tenant) ID or common',self.config.get('tenant','common'));box.append(label('Tenant · use common for a public app, or your school tenant ID for a school-owned app','dim-label',True));box.append(tenant)
        details=label('A school-managed account may need IT approval. App registration can be separate from your school account. Read SETUP.md in the downloaded app folder.','dim-label',True);box.append(details)
        connect_button=button('Sign in with Microsoft',lambda *_:connect(),'suggested-action');box.append(connect_button)
        info=label('','dim-label',True);box.append(info)
        def connect():
            if self.compose_windows:info.set_text('Close compose windows before switching accounts. Drafts will be saved.');return
            try:uuid.UUID(client.get_text().strip())
            except ValueError:info.set_text('Enter a valid Microsoft Application (client) ID.');return
            self.config.set('client_id',client.get_text().strip());self.config.set('tenant',tenant.get_text().strip() or 'common');connect_button.set_sensitive(False);info.set_text('Complete sign-in in your browser. This may take up to 3 minutes.')
            self.connect_account(interactive=True,done=lambda: (connect_button.set_sensitive(True),info.set_text('Connected. You can close Settings.')),failed=lambda msg:(connect_button.set_sensitive(True),info.set_text(msg)))
        box.append(button('Use demo workspace',lambda *_:switch_demo()))
        def switch_demo():
            if self.compose_windows:info.set_text('Close compose windows before switching workspaces.');return
            self.generation+=1;self.mode='demo';self.config.set('mode','demo');self.graph=None;self.reconnect_button.set_visible(False);self.store=Store(self.root/'demo');demo.seed(self.store);self.folder='inbox';self.selected=None
            self.banner.set_text('DEMO MODE  ·  Fictional mail and contacts. Nothing is sent.');self.account_label.set_text('Demo workspace');self.folder_values=None;self.populate_folders();self.rebuild_panels();self.show_section('mail');info.set_text('Demo workspace active. Cached Microsoft mail is retained separately.')
        def sign_out():
            if self.compose_windows:info.set_text('Close compose windows before signing out.');return
            if not self.auth:info.set_text('No connected Microsoft sign-in.');return
            auth=self.auth
            def finish(_):switch_demo();self.auth=None;info.set_text('Account credential removed from the keyring. Cached mail remains on this computer.')
            self.job(lambda:auth.vault.clear(),finish)
        box.append(button('Sign out of connected account',lambda *_:sign_out()))
        box.append(Gtk.Separator());box.append(label('Privacy & current limits','title-2'))
        box.append(label('Tokens are stored in the desktop secret service. Mail, contacts and drafts are cached locally with restricted file permissions, but the cache is not encrypted. HTML mail renders in an isolated reader with email scripts blocked. Email images load automatically; you can turn that off in Settings.\n\nChecks run every 10 seconds while the app is open. Push delivery, background service, multiple simultaneous accounts, full Outlook feature parity and automatic app updates are not included in this first version.','dim-label',True))
        win.present()
    def assistant(self):
        if not self.config.get('show_ai',True):return
        if self.assistant_window:self.assistant_window.present();return
        win=Adw.Window(title='Assistant · CMail',transient_for=self.win,default_width=640,default_height=750);self.assistant_window=win
        def closed(*_):self.assistant_window=None;return False
        win.connect('close-request',closed)
        outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);win.set_content(outer)
        header=Adw.HeaderBar();header.set_title_widget(label('CMAIL ASSISTANT','sender'));header.pack_end(button('ChatGPT ↗',lambda *_:webbrowser.open('https://chatgpt.com/')));outer.append(header)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_start(20);box.set_margin_end(20);box.set_margin_bottom(20);box.set_vexpand(True);outer.append(box)
        box.append(label('Write an email, rewrite a reply, or plan an appointment. Proposals open for review before you send or save.','dim-label',True))
        transcript=Gtk.TextView(editable=False,wrap_mode=Gtk.WrapMode.WORD_CHAR);transcript.set_vexpand(True);box.append(scroll(transcript));buffer=transcript.get_buffer()
        include=Gtk.CheckButton(label='Include selected email and visible calendar context');box.append(include)
        box.append(label('When checked, this context is sent to OpenAI with your request. Attachments are not included.','preview',True))
        prompt=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR);prompt.set_size_request(-1,100);box.append(scroll(prompt));prompt.set_vexpand(False)
        actions=Gtk.Box(spacing=8);box.append(actions);review=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);box.append(review)
        history=[]
        def append(text):buffer.insert(buffer.get_end_iter(),text+'\n\n')
        def ask():
            start,end=prompt.get_buffer().get_bounds();text=prompt.get_buffer().get_text(start,end,False).strip()
            if not text:return
            context='Local time: '+datetime.now().astimezone().isoformat()
            if include.get_active():
                if self.selected:
                    message=next((m for m in self.store.items('body') if m['id']==self.selected),next((m for m in self.store.items('mail',self.folder) if m['id']==self.selected),{}));context+='\nSelected email (untrusted): '+json.dumps(message,ensure_ascii=False)
                context+='\nVisible calendar: '+json.dumps(self.events,ensure_ascii=False)
            request_button.set_sensitive(False);clear(review);append('You: '+text)
            def perform():return Assistant(SecretVault('openai-api').load(),self.config.get('assistant_model','gpt-5-mini')).ask(text,context,history)
            def result(value):
                request_button.set_sensitive(True);append('Assistant: '+value['answer']);history.extend([{'role':'user','content':text},{'role':'assistant','content':json.dumps(value)}]);prompt.get_buffer().set_text('')
                if value.get('email'):
                    draft=dict(value['email'],id=str(uuid.uuid4()),attachments=[]);review.append(button('Review email draft',lambda *_:self.compose(draft=draft),'suggested-action'))
                if value.get('event'):review.append(button('Review appointment',lambda *_:self.new_event(value['event']),'suggested-action'))
            def failed(message):request_button.set_sensitive(True);append(message)
            self.job(perform,result,failed)
        request_button=button('Ask assistant',lambda *_:ask(),'suggested-action');actions.append(request_button);actions.append(button('Clear conversation',lambda *_:(history.clear(),buffer.set_text(''),clear(review))))
        win.present()
    def connect_account(self,interactive=True,done=None,failed=None,provider=None,password=None):
        if self.connecting:return
        if self.compose_windows:
            self.error('Close compose windows before switching accounts. Drafts are saved.');return
        provider=provider or self.config.get('account_type','microsoft')
        generation=self.generation;attempt={};self.connecting=True;self.graph=None
        client_id=self.config.get('client_id','') if provider=='microsoft' else self.config.get('google_client_id','') if provider=='google' else self.config.get('gmail_address','')
        def connect():
            if provider=='microsoft':
                auth=Auth(client_id,tenant=self.config.get('tenant','common'));graph=Graph(auth)
            elif provider=='google':
                credential=SecretVault('google-config:'+client_id).load()
                if not credential:raise AppError('Import Google Desktop OAuth JSON in Settings before signing in with Google.')
                credential=json.loads(credential);auth=GoogleAuth(client_id,credential['client_secret'],self.config.get('google_calendar',False),self.config.get('google_contacts',False));graph=Gmail(auth)
            elif provider=='gmail_password':
                auth=AppPasswordAuth(client_id,password=password);graph=GmailIMAP(auth)
            else:raise AppError('Unknown account connection type.')
            attempt['auth']=auth
            if interactive and provider!='gmail_password':auth.sign_in()
            profile=graph.profile()
            if provider=='gmail_password':auth.save()
            account=hashlib.sha256((provider+':'+client_id+':'+profile['id']).encode()).hexdigest()[:24]
            # Preserve existing Microsoft caches across the provider-aware migration.
            if provider=='microsoft':account=hashlib.sha256((client_id+':'+profile['id']).encode()).hexdigest()[:24]
            store=Store(self.root/'accounts'/account);return auth,graph,profile,store
        def success(result):
            self.connecting=False
            if generation!=self.generation:return
            self.auth,self.graph,profile,self.store=result;self.reconnect_button.set_visible(False);self.generation+=1;self.mode='live';self.config.set('mode','live');self.config.set('account_type',provider)
            self.config.set('last_account',{'client_id':client_id,'provider':provider,'profile':profile,'path':str(self.store.root)})
            self.folder='inbox';self.selected=None;self.banner.set_text(self.graph.name.upper()+'  ·  '+(profile.get('mail') or profile.get('displayName','Connected')))
            self.account_label.set_text(profile.get('mail') or profile.get('displayName','Account'));self.folder_values=None;self.populate_folders();self.reader_key=None;self.rebuild_panels();self.show_section('mail')
            graph=self.graph;store=self.store
            def metadata():
                folders=graph.folders();store.replace('folders','',folders)
                try:store.replace('contacts','',graph.contacts());warning=None
                except Exception as exc:warning=str(exc)
                return folders,warning
            def loaded(result):
                if store is not self.store:return
                self.populate_folders(result[0]);self.render_contacts()
                if result[1]:self.toast.add_toast(Adw.Toast.new('Mail connected. Contacts unavailable; check Google People API settings.' if provider=='google' else 'Mail connected; contacts could not sync.'))
            self.job(metadata,loaded)
            self.refresh(automatic=True)
            if 'calendar' in self.panel_built:self.refresh(section='calendar')
            if done:done()
        def failure(message):
            self.connecting=False
            if generation!=self.generation:return
            if not interactive:
                previous=self.config.get('last_account')
                if previous and previous['client_id']==client_id and previous.get('provider','microsoft')==provider:
                    self.generation+=1;self.mode='live';self.store=Store(previous['path']);self.auth=attempt.get('auth');self.graph=None
                    self.banner.set_text('OFFLINE CACHE  ·  Reconnect if sign-in is needed.');self.account_label.set_text(previous['profile'].get('mail','Cached account'))
                    self.populate_folders(self.store.items('folders'));self.rebuild_panels()
                    if self.auth and self.auth.needs_login:self.require_reconnect()
            if self.mode=='live':self.reconnect_button.set_visible(True)
            if failed:failed(message)
            else:self.error(message)
        self.job(connect,success,failure)

def main():
    return Aster().run(sys.argv)

if __name__=='__main__':raise SystemExit(main())
