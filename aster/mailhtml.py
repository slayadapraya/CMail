"""Render mail HTML without scripts, forms, frames or external resources by default."""
from html.parser import HTMLParser
import html,re,weakref
from urllib.parse import urlparse
import webbrowser
_session=None
ALLOWED=set('div p span br hr b strong i em u s strike font a img table tbody thead tfoot tr td th ul ol li blockquote pre code h1 h2 h3 h4 h5 h6 center details summary'.split())
VOID={'br','hr','img'}
DROP={'script','style','iframe','object','embed','svg','math','form','input','button','textarea','select','link','meta','base','audio','video'}
def safe_url(url):return urlparse(url.strip()).scheme.lower() in ('http','https','mailto','tel')
class Sanitizer(HTMLParser):
    def __init__(self,assets=None,remote=False):super().__init__(convert_charrefs=True);self.out=[];self.skip=0;self.assets=assets or {};self.remote=remote;self.blocked=False;self.stack=[]
    def handle_starttag(self,tag,attrs):
        if tag in DROP:
            if tag not in ('input','link','meta','base','embed'):self.skip+=1
            return
        if self.skip or tag not in ALLOWED:return
        attrs=dict(attrs);values=[]
        if tag=='img':
            src=attrs.get('src','').strip();mime=''
            if src.lower().startswith('cid:'):src=self.assets.get(src[4:].strip('<>'),'')
            allowed=bool(re.match(r'^data:image/(png|jpeg|gif|webp);base64,[a-zA-Z0-9+/=]+$',src))
            if not allowed and self.remote and urlparse(src).scheme in ('https','http'):allowed=True
            if not allowed:self.blocked=True;self.out.append('<span class="image-placeholder">'+html.escape(attrs.get('alt') or '[Image]')+'</span>');return
            values.append(('src',src))
        if tag=='a' and safe_url(attrs.get('href','')):values.append(('href',attrs['href']))
        for key in ('alt','title','width','height','colspan','rowspan','align','valign','bgcolor','color','face','size'):
            if key in attrs:values.append((key,attrs[key]))
        style=attrs.get('style','')
        if style and not re.search(r'url\s*\(|expression|@import|behavior|javascript|position\s*:',style,re.I):values.append(('style',style))
        quote=tag in ('div','blockquote') and ('gmail_quote' in attrs.get('class','') or tag=='blockquote')
        actual='details' if quote else tag
        self.out.append('<'+actual+''.join(' '+k+'="'+html.escape(v,quote=True)+'"' for k,v in values)+'>')
        if quote:self.out.append('<summary>Show quoted text</summary>')
        if tag not in VOID:self.stack.append((tag,actual))
    def handle_endtag(self,tag):
        if tag in DROP:
            if self.skip:self.skip-=1
            return
        if self.skip:return
        if self.stack and self.stack[-1][0]==tag:self.out.append('</'+self.stack.pop()[1]+'>')
    def handle_data(self,data):
        if not self.skip:self.out.append(html.escape(data))
    def result(self):return ''.join(self.out)+''.join('</'+actual+'>' for _,actual in reversed(self.stack))
def document(content,assets=None,remote=False,is_html=True,background='#242831',foreground='#e6edf8'):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',background):background='#242831'
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',foreground):foreground='#e6edf8'
    parser=Sanitizer(assets,remote);parser.feed(content if is_html else '<div style="white-space:pre-wrap">'+html.escape(content)+'</div>')
    policy="default-src 'none'; img-src data:"+(' https: http:' if remote else '')+"; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    text='<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+policy+'"><style>html{overflow:hidden}body{font:15px sans-serif;background:'+background+'!important;color:'+foreground+'!important;margin:20px;overflow-wrap:anywhere}body *{background-color:transparent!important;background-image:none!important;color:'+foreground+'!important}img{max-width:100%;height:auto}table{max-width:100%}a,a *{color:#91bfff!important}pre{white-space:pre-wrap}details{margin:12px 0;border-left:2px solid #d0d5df;padding-left:12px}summary{color:#667085;cursor:pointer}.image-placeholder{color:#667085;font-size:12px}</style></head><body>'+parser.result()+'</body></html>'
    return text,parser.blocked

def viewer(content,assets=None,remote=False,is_html=True,background='#242831',foreground='#e6edf8',low_power=False):
    import gi
    gi.require_version('WebKit','6.0')
    from gi.repository import WebKit, GLib
    global _session
    if _session is None:_session=WebKit.NetworkSession.new_ephemeral()
    view=WebKit.WebView(network_session=_session);settings=view.get_settings()
    if low_power:
        settings.set_hardware_acceleration_policy(WebKit.HardwareAccelerationPolicy.NEVER);settings.set_enable_webgl(False)
    settings.set_enable_javascript(True);settings.set_enable_javascript_markup(False);settings.set_enable_html5_local_storage(False)
    def policy(_,decision,kind):
        if kind in (WebKit.PolicyDecisionType.NAVIGATION_ACTION,WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            action=decision.get_navigation_action();url=action.get_request().get_uri()
            if action.get_navigation_type()==WebKit.NavigationType.LINK_CLICKED:
                decision.ignore()
                if safe_url(url):webbrowser.open(url)
                return True
            if url not in ('about:blank',):decision.ignore();return True
        return False
    signals=[view.connect('decide-policy',policy),view.connect('permission-request',lambda _,request:(request.deny() or True))];view.set_size_request(-1,80)
    manager=view.get_user_content_manager();manager.register_script_message_handler('mailHeight','cmailLayout')
    height_state={'source':0,'height':80}
    def apply_height():
        height_state['source']=0
        height=height_state['height']
        if abs(view.get_size_request()[1]-height)>2:view.set_size_request(-1,height)
        return False
    def resize(_,value):
        try:
            height=max(60,min(900 if low_power else 500000,int(value.to_double()*view.get_zoom_level()+2)))
            height_state['height']=height
            if not height_state['source']:height_state['source']=GLib.timeout_add(80,apply_height)
        except (TypeError,ValueError,OverflowError):pass
    resize_signal=manager.connect('script-message-received::mailHeight',resize)
    # Trusted isolated-world code measures only layout. Mail scripts remain stripped and CSP-blocked.
    script="""(() => {
        const update = () => window.webkit.messageHandlers.mailHeight.postMessage(Math.ceil(document.body.getBoundingClientRect().height + 40));
        new ResizeObserver(update).observe(document.body);
        document.addEventListener('toggle', update, true);
        document.addEventListener('load', update, true);
        update();
    })();"""
    def loaded(_,event):
        if event==WebKit.LoadEvent.FINISHED:view.evaluate_javascript(script,-1,'cmailLayout',None,None,None,None)
    signals.append(view.connect('load-changed',loaded))
    reference=weakref.ref(view)
    def dispose():
        target=reference()
        if target is None:return
        target.stop_loading()
        if height_state['source']:GLib.source_remove(height_state['source']);height_state['source']=0
        for signal in signals:
            if target.handler_is_connected(signal):target.disconnect(signal)
        if manager.handler_is_connected(resize_signal):manager.disconnect(resize_signal)
        manager.unregister_script_message_handler('mailHeight','cmailLayout');target.cmail_dispose=None
    view.cmail_dispose=dispose
    page=document(content,assets,remote,is_html,background,foreground)[0]
    if low_power:page=page.replace('html{overflow:hidden}','html{overflow:auto}')
    view.load_html(page,None);return view
