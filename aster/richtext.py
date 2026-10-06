"""Native rich text with safe, generated HTML and restorable draft formatting."""
import html
import re
from urllib.parse import urlparse
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk, Pango, GLib

STYLES={'bold':{'weight':Pango.Weight.BOLD},'italic':{'style':Pango.Style.ITALIC},'underline':{'underline':Pango.Underline.SINGLE},'strike':{'strikethrough':True},'small':{'size_points':11.0},'normal':{'size_points':14.0},'large':{'size_points':20.0},'red':{'foreground':'#ff7187'},'blue':{'foreground':'#7ab8ff'},'green':{'foreground':'#73d9bd'},'white':{'foreground':'#ffffff'},'left':{'justification':Gtk.Justification.LEFT},'center':{'justification':Gtk.Justification.CENTER},'right':{'justification':Gtk.Justification.RIGHT}}
HTML_STYLES={'bold':'font-weight:bold','italic':'font-style:italic','underline':'text-decoration:underline','strike':'text-decoration:line-through','small':'font-size:11pt','normal':'font-size:14pt','large':'font-size:20pt','red':'color:#ff7187','blue':'color:#7ab8ff','green':'color:#73d9bd','white':'color:#ffffff'}

class RichEditor:
    def __init__(self,state=None,text=''):
        self.view=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR);self.view.add_css_class('compose-body');self.view.set_top_margin(16);self.view.set_bottom_margin(16);self.view.set_left_margin(16);self.view.set_right_margin(16)
        self.buffer=self.view.get_buffer();self.buffer.set_enable_undo(True);self.links={};self.typing=set();self.on_change=lambda:None
        for name,props in STYLES.items():self.buffer.create_tag(name,**props)
        self.buffer.set_text(text)
        if state:
            self.links=state.get('links',{})
            for name,url in list(self.links.items()):
                if not self.valid_link(url):self.links.pop(name);continue
                self.buffer.create_tag(name,foreground='#7ab8ff',underline=Pango.Underline.SINGLE)
            length=self.buffer.get_char_count()
            for span in state.get('runs',[]):
                if self.buffer.get_tag_table().lookup(span['name']):self.buffer.apply_tag_by_name(span['name'],self.buffer.get_iter_at_offset(max(0,min(length,span['start']))),self.buffer.get_iter_at_offset(max(0,min(length,span['end']))))
        self.buffer.connect_after('insert-text',self.inserted)
    def inserted(self,buffer,location,text,length):
        # The after-handler receives the iterator after insertion.
        if self.typing:
            end=location.copy();start=end.copy();start.backward_chars(len(text))
            for name in self.typing:buffer.apply_tag_by_name(name,start,end)
    def bounds(self,paragraph=False):
        bounds=self.buffer.get_selection_bounds()
        if bounds:start,end=bounds
        else:start=self.buffer.get_iter_at_mark(self.buffer.get_insert());end=start.copy()
        if paragraph:
            start.set_line_offset(0)
            if not end.ends_line():end.forward_to_line_end()
        return start,end
    def format(self,name):
        start,end=self.bounds(paragraph=name in ('left','center','right'))
        if start.equal(end):
            if name in self.typing:self.typing.remove(name)
            else:self.typing.add(name)
        else:
            if name in ('left','center','right','small','normal','large','red','blue','green'):
                group=('left','center','right') if name in ('left','center','right') else ('small','normal','large') if name in ('small','normal','large') else ('red','blue','green')
                for tag in group:self.buffer.remove_tag_by_name(tag,start,end)
                self.buffer.apply_tag_by_name(name,start,end)
            elif start.has_tag(self.buffer.get_tag_table().lookup(name)):self.buffer.remove_tag_by_name(name,start,end)
            else:self.buffer.apply_tag_by_name(name,start,end)
        self.on_change();self.view.grab_focus()
    def clear_format(self):
        start,end=self.bounds();self.buffer.remove_all_tags(start,end);self.typing.clear();self.on_change()
    def undo(self):
        if self.buffer.get_can_undo():self.buffer.undo()
    def redo(self):
        if self.buffer.get_can_redo():self.buffer.redo()
    def list_lines(self,numbered=False):
        start,end=self.bounds(paragraph=True);first=start.get_line();last=end.get_line();self.buffer.begin_user_action()
        for line in range(last,first-1,-1):
            iterator=self.buffer.get_iter_at_line(line)[1];self.buffer.insert(iterator,str(line-first+1)+'. ' if numbered else '• ')
        self.buffer.end_user_action();self.on_change()
    @staticmethod
    def valid_link(url):return urlparse(url).scheme.lower() in ('https','http','mailto') and not any(c in url for c in ('\n','\r'))
    def link(self,url,text=None):
        if not self.valid_link(url):raise ValueError('Use an https://, http:// or mailto: link.')
        start,end=self.bounds()
        if start.equal(end):
            offset=start.get_offset();self.buffer.insert(start,text or url);start=self.buffer.get_iter_at_offset(offset);end=self.buffer.get_iter_at_offset(offset+len(text or url))
        name='link-'+str(len(self.links)+1);self.links[name]=url;self.buffer.create_tag(name,foreground='#7ab8ff',underline=Pango.Underline.SINGLE);self.buffer.apply_tag_by_name(name,start,end);self.on_change()
    def snapshot(self):
        text=self.buffer.get_text(self.buffer.get_start_iter(),self.buffer.get_end_iter(),True);runs=[]
        for name in list(STYLES)+list(self.links):
            tag=self.buffer.get_tag_table().lookup(name);begin=None
            for offset in range(len(text)+1):
                active=offset<len(text) and self.buffer.get_iter_at_offset(offset).has_tag(tag)
                if active and begin is None:begin=offset
                if not active and begin is not None:runs.append({'name':name,'start':begin,'end':offset});begin=None
        state={'runs':runs,'links':dict(self.links)};return text,state,self.to_html(text,state)
    @staticmethod
    def to_html(text,state):
        output=[];offset=0
        for line in text.split('\n'):
            align=next((r['name'] for r in state['runs'] if r['name'] in ('left','center','right') and r['start']<=offset<r['end']),'left')
            output.append('<div style="text-align:'+align+';white-space:pre-wrap">')
            boundaries={0,len(line)}
            for r in state['runs']:
                for point in (r['start']-offset,r['end']-offset):
                    if 0<point<len(line):boundaries.add(point)
            points=sorted(boundaries)
            for start,end in zip(points,points[1:]):
                active=[r['name'] for r in state['runs'] if r['start']<=offset+start<r['end']];styles=[HTML_STYLES[n] for n in active if n in HTML_STYLES]
                content=html.escape(line[start:end])
                link=next((state['links'][n] for n in active if n in state['links'] and RichEditor.valid_link(state['links'][n])),None)
                if styles:content='<span style="'+ ';'.join(styles)+'">'+content+'</span>'
                if link:content='<a href="'+html.escape(link,quote=True)+'">'+content+'</a>'
                output.append(content)
            if not line:output.append('<br>')
            output.append('</div>');offset+=len(line)+1
        return ''.join(output)
    def toolbar(self,link_callback):
        box=Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,column_spacing=3,row_spacing=2,min_children_per_line=12,max_children_per_line=20);box.add_css_class('formatbar')
        actions=[('↶','Undo',self.undo),('↷','Redo',self.redo),('B','Bold',lambda:self.format('bold')),('I','Italic',lambda:self.format('italic')),('U','Underline',lambda:self.format('underline')),('S̶','Strikethrough',lambda:self.format('strike')),('A−','Small text',lambda:self.format('small')),('A','Normal text',lambda:self.format('normal')),('A+','Large text',lambda:self.format('large')),('●','Red text',lambda:self.format('red')),('●','Blue text',lambda:self.format('blue')),('●','Green text',lambda:self.format('green')),('●','White text',lambda:self.format('white')),('≡','Align left',lambda:self.format('left')),('≣','Align centre',lambda:self.format('center')),('≡','Align right',lambda:self.format('right')),('•','Bulleted list',lambda:self.list_lines()),('1.','Numbered list',lambda:self.list_lines(True)),('↗','Insert link',link_callback),('Tx','Clear formatting',self.clear_format)]
        for title,tooltip,fn in actions:
            widget=Gtk.Button(label=title);widget.set_tooltip_text(tooltip)
            if tooltip in ('Red text','Blue text','Green text','White text'):widget.add_css_class('format-'+tooltip.split()[0].lower())
            widget.connect('clicked',lambda _,action=fn:action());box.insert(widget,-1)
        return box
