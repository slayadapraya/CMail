"""Futuristic workspace styling using editable theme colours throughout."""
FUTURE_CSS='''
window {background-image:linear-gradient(135deg,alpha(@accent_bg_color,.06),transparent 40%);}
headerbar {min-height:56px;background-image:linear-gradient(100deg,@headerbar_bg_color,alpha(@accent_bg_color,.20));border-bottom:1px solid alpha(@accent_color,.24);}
.brand {font-size:21px;letter-spacing:4px;text-shadow:0px 0px 18px alpha(@accent_color,.55);}
.brand-mark {text-shadow:0px 0px 16px alpha(@accent_color,.6);}
.topnav {padding:0px 22px;background-image:linear-gradient(90deg,alpha(@accent_bg_color,.12),transparent);}
.topnav button {padding:14px 24px;letter-spacing:1px;}
.topnav button.active {background-image:linear-gradient(0deg,alpha(@accent_bg_color,.20),transparent);border-bottom:2px solid @accent_color;}
.commandbar {padding:14px 20px;background-image:linear-gradient(115deg,@view_bg_color,alpha(@accent_bg_color,.08));border-bottom:1px solid alpha(@accent_color,.20);}
.commandbar button {border:1px solid alpha(@window_fg_color,.11);border-radius:10px;padding:9px 14px;}
button.suggested-action {background-image:linear-gradient(125deg,@accent_bg_color,shade(@accent_bg_color,.70));border:1px solid alpha(@accent_color,.65);box-shadow:0px 0px 16px alpha(@accent_bg_color,.17);}
button.suggested-action:hover {box-shadow:0px 0px 24px alpha(@accent_bg_color,.38);}
.rail {padding:18px 7px;border-right:1px solid alpha(@accent_color,.15);background-image:linear-gradient(180deg,alpha(@accent_bg_color,.08),transparent);}
.rail button {border-radius:12px;min-height:28px;}
.rail button.active {border:1px solid alpha(@accent_color,.40);box-shadow:0px 0px 18px alpha(@accent_bg_color,.18);}
.sidebar {padding:22px 14px;background-image:linear-gradient(160deg,alpha(@accent_bg_color,.10),transparent 55%);}
.sidebar button {border-radius:9px;}
.sidebar button.active {border:1px solid alpha(@accent_color,.35);border-left:3px solid @accent_color;background-image:linear-gradient(90deg,alpha(@accent_bg_color,.25),alpha(@accent_bg_color,.05));box-shadow:0px 0px 20px alpha(@accent_bg_color,.08);}
.account-card {background:@card_bg_color;border:1px solid alpha(@accent_color,.20);border-radius:12px;padding:12px;}
.workspace-title {font-size:25px;font-weight:700;letter-spacing:1px;}
.workspace-subtitle {font-size:10px;letter-spacing:2px;color:@accent_color;}
.message-column {background-image:linear-gradient(165deg,alpha(@accent_bg_color,.05),transparent 50%);border-right:1px solid alpha(@accent_color,.22);}
.list-heading {padding:22px 18px 16px;}
.section-title {font-size:29px;letter-spacing:-.5px;}
.mail-row {margin:5px 10px;padding:15px 14px;border:1px solid alpha(@window_fg_color,.08);border-radius:12px;background:@card_bg_color;}
row:selected {background:transparent;}
row:selected .mail-row {padding-left:13px;border:1px solid alpha(@accent_color,.50);border-left:3px solid @accent_color;background-image:linear-gradient(110deg,alpha(@accent_bg_color,.22),alpha(@accent_bg_color,.05));box-shadow:0px 0px 20px alpha(@accent_bg_color,.12);}
row:hover {background:transparent;}
row:hover .mail-row {border-color:alpha(@accent_color,.35);}
.sender-avatar {font-size:12px;font-weight:700;color:@accent_color;background:alpha(@accent_bg_color,.16);border:1px solid alpha(@accent_color,.24);border-radius:10px;min-width:34px;min-height:34px;}
.reader-avatar {font-size:18px;min-width:54px;min-height:54px;border-radius:15px;box-shadow:0px 0px 16px alpha(@accent_bg_color,.12);}
.mail-subject {font-weight:600;}
.reader {padding:26px;background-image:linear-gradient(155deg,alpha(@accent_bg_color,.07),transparent 45%);}
.message-heading {padding:22px;background:@card_bg_color;border:1px solid alpha(@accent_color,.20);border-radius:15px;}
.reader-title {font-size:27px;letter-spacing:-.4px;}
.reader-actions {padding:4px 0px;}
.reader-actions button {border:1px solid alpha(@window_fg_color,.10);border-radius:9px;}
.reader .message-paper, .reader .message-paper text {background:@view_bg_color;}
.message-paper {border:1px solid alpha(@window_fg_color,.08);border-radius:14px;padding:20px;}
.demo-banner {padding:8px 20px;letter-spacing:.3px;border-bottom:1px solid alpha(@accent_color,.09);}
.status {background:@headerbar_bg_color;border-top:1px solid alpha(@accent_color,.17);padding:9px 18px;}
.calendar-day {border-radius:12px;background:@card_bg_color;}
.calendar-day.today {box-shadow:0px 0px 18px alpha(@accent_bg_color,.18);}
.card {border-radius:13px;}
.formatbar {border:1px solid alpha(@accent_color,.20);}
'''

PRESETS={
    'CMail Blue':dict(background='#0b1726',surface='#0e1c2e',cards='#15273b',mail='#242831',text='#e6edf8',accent='#69bafa',buttons='#247bb5'),
    'Crimson Orbit':dict(background='#0b1222',surface='#101a2e',cards='#152139',mail='#242831',text='#e6edf8',accent='#ff7187',buttons='#c63d56'),
    'Cyber Mint':dict(background='#071b1c',surface='#10292b',cards='#183639',mail='#223234',text='#e1fff8',accent='#62efc8',buttons='#166b5d'),
    'Violet Circuit':dict(background='#130e24',surface='#211735',cards='#2d2145',mail='#2a2534',text='#f0eaff',accent='#c193ff',buttons='#7351ad'),
    'Deep Space':dict(background='#080e19',surface='#101d30',cards='#172b44',mail='#222c37',text='#e7f1ff',accent='#68b9ff',buttons='#235e96'),
    'Graphite':dict(background='#141619',surface='#202328',cards='#2b2f35',mail='#292d32',text='#edf0f3',accent='#c3cad4',buttons='#505967'),
}

def scaled_css(css,scale):
    """Scale app dimensions and typography without changing desktop display settings."""
    import re
    scale=max(.65,min(1.2,float(scale)))
    return re.sub(r'(-?(?:\d+(?:\.\d*)?|\.\d+))px',lambda m:f'{float(m[1])*scale:.2f}px',css)


COLOR_KEYS=tuple(PRESETS['Crimson Orbit'])
def save_custom_theme(config):
    value={'colors':{key:config.get('color_'+key) for key in COLOR_KEYS},'dark':config.get('dark',True)}
    config.set('custom_theme',value)
    return value

def select_theme(config,name):
    if name!='Custom' and name not in PRESETS:raise ValueError('Unknown theme preset')
    if config.get('theme_preset','Custom')=='Custom':save_custom_theme(config)
    if name=='Custom':
        value=config.get('custom_theme') or save_custom_theme(config)
        colors=value['colors'];dark=value.get('dark',True)
    else:colors=PRESETS[name];dark=True
    for key in COLOR_KEYS:config.set('color_'+key,colors.get(key))
    config.set('dark',dark);config.set('theme_preset',name)

def customize_color(config,key,value):
    if key not in COLOR_KEYS:raise ValueError('Unknown theme colour')
    config.set('color_'+key,value);config.set('theme_preset','Custom');save_custom_theme(config)

# Flat surfaces and inexpensive colour-only hover feedback, shared by all panes.
CMAIL_CSS = """
window, headerbar, .topnav, .commandbar, .rail, .sidebar, .reader, .message-column {background-image:none;}
headerbar {min-height:40px;background:@headerbar_bg_color;border-bottom:1px solid alpha(@accent_color,.18);}
.brand {font-size:19px;letter-spacing:1px;text-shadow:none;}
.topnav {padding:0px 6px;border:0;background:transparent;}
.topnav button {padding:7px 12px;letter-spacing:0px;border-radius:0px;}
.topnav button.active {background-image:none;background:transparent;border-bottom:2px solid @accent_color;}
.commandbar {padding:5px 12px;background:@headerbar_bg_color;}
.commandbar button {background:transparent;background-image:none;border:1px solid transparent;border-radius:6px;box-shadow:none;min-height:24px;padding:4px 8px;transition:background-color 120ms ease,color 120ms ease;}
.commandbar button:hover {background:alpha(@accent_color,.16);color:@accent_color;border-color:transparent;box-shadow:none;}
.commandbar button:disabled {opacity:.4;}
.commandbar .suggested-action {background:@accent_bg_color;color:@accent_fg_color;border:1px solid alpha(@accent_color,.5);background-image:none;box-shadow:none;}
.commandbar .suggested-action:hover {background:shade(@accent_bg_color,1.12);color:@accent_fg_color;box-shadow:none;}
.commandbar separator {margin:5px 6px;background:alpha(@accent_color,.20);}
.commandbar searchentry {background:alpha(@window_fg_color,.035);border:1px solid alpha(@accent_color,.18);border-radius:6px;}
.rail {padding:10px 5px;background:@headerbar_bg_color;}
.rail button {border-radius:6px;background-image:none;box-shadow:none;}
.rail button.active {background:alpha(@accent_color,.12);border-color:transparent;box-shadow:none;}
.sidebar {padding:12px 9px;background:@headerbar_bg_color;}
.workspace-title {font-size:21px;letter-spacing:0px;}
.account-card {padding:7px;border-radius:5px;background:alpha(@window_fg_color,.035);border-color:alpha(@window_fg_color,.08);}
.sidebar button {border-radius:4px;box-shadow:none;transition:background-color 120ms ease;}
.sidebar button.active {background-image:none;background:alpha(@accent_color,.16);border:1px solid transparent;border-left:3px solid @accent_color;box-shadow:none;}
.sidebar button:hover {background:alpha(@accent_color,.10);}
.folder-group-title {font-size:16px;font-weight:700;}
.folder-row label {font-size:14px;}
.message-column {background:@window_bg_color;}
.list-heading {padding:12px 16px;}
.section-title {font-size:24px;}
.mail-row {border-radius:5px;background-image:none;box-shadow:none;}
row:selected .mail-row {background-image:none;background:alpha(@accent_color,.14);box-shadow:none;}
row:hover .mail-row {background:alpha(@accent_color,.08);}
.mail-row.compact-row {margin:0px;padding:9px 14px;border:0;border-bottom:1px solid alpha(@window_fg_color,.07);border-radius:0px;background:transparent;}
row:selected .compact-row {padding-left:11px;border:0;border-left:3px solid @accent_color;border-bottom:1px solid alpha(@window_fg_color,.07);background:alpha(@accent_color,.14);}
.compact-row .sender-avatar {min-width:22px;min-height:22px;font-size:10px;}
.reader {padding:18px;}
.message-heading {padding:16px;border-radius:6px;box-shadow:none;}
.reader-title {font-size:24px;}
.message-paper, .card, .calendar-day, .attachment-chip {border-radius:6px;box-shadow:none;}
.reader-actions button {background-image:none;box-shadow:none;border-radius:5px;}
.calendar-day.today {box-shadow:none;border:1px solid @accent_color;}
.calendar-day:hover, .reader-actions button:hover {background:alpha(@accent_color,.12);}
.dock-tabs {padding:4px 8px;}
.dock-tabs button {background-image:none;border-radius:4px;box-shadow:none;}
.dock-tabs button.active {background:alpha(@accent_color,.12);color:@accent_color;}
.status {padding:4px 12px;}
.demo-banner {padding:4px 12px;font-size:11px;background:@view_bg_color;color:alpha(@window_fg_color,.65);}
"""
