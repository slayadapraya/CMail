"""Virtualized inbox: model messages are cheap; GTK rows exist only near view."""
import json,weakref
from gi.repository import Gtk,Gio,GObject

def signature(message):
    fields=('id','thread_key','count','receivedDateTime','isRead','flag','hasAttachments','from','subject','bodyPreview')
    return json.dumps([message.get(k) for k in fields],sort_keys=True,ensure_ascii=False)
class MailItem(GObject.Object):
    def __init__(self,message):
        super().__init__();self.message=message;self.signature=signature(message);self.widget=None;self.style_key=None
    def get_height(self):
        widget=self.widget() if self.widget else None
        return widget.get_height() if widget else 0
class MailList(Gtk.ListView):
    def __init__(self,build_row,selected):
        self.items=Gio.ListStore.new(MailItem);self.selection=Gtk.SingleSelection.new(self.items);self.selection.set_autoselect(False);self.selection.set_can_unselect(True)
        self.factory=Gtk.SignalListItemFactory();self.created=0;self.bound=0;self.updating=False;self.selected_callback=selected
        self.factory.connect('setup',self.setup);self.factory.connect('bind',lambda _,item:self.bind(item,build_row));self.factory.connect('unbind',self.unbind)
        super().__init__(model=self.selection,factory=self.factory,hexpand=True,vexpand=True)
        self.set_single_click_activate(True)
        self.connect('activate',lambda _,pos:self.selected_callback(self,self.items.get_item(pos)))
    def setup(self,_,item):
        self.created+=1;item.set_child(Gtk.Box(orientation=Gtk.Orientation.VERTICAL))
    def bind(self,item,build_row):
        self.bound+=1;box=item.get_child();child=box.get_first_child()
        if child:box.remove(child)
        value=item.get_item();box.append(build_row(value.message));value.widget=weakref.ref(box)
    def unbind(self,_,item):
        value=item.get_item()
        if value:value.widget=None
    def changed(self,*_):
        if not self.updating:self.selected_callback(self,self.selection.get_selected_item())
    def get_row_at_index(self,index):return self.items.get_item(index)
    def select_row(self,row):
        if row is None:self.unselect_all();return
        found,index=self.items.find(row)
        if found:
            self.selection.set_selected(index);self.selected_callback(self,row)
    def unselect_all(self):self.selection.set_selected(Gtk.INVALID_LIST_POSITION)
    def set_rows(self,rows,selected_id=None,style_key=None):
        old=[self.items.get_item(i) for i in range(self.items.get_n_items())];by_key={x.message.get('thread_key',x.message['id']):x for x in old};new=[]
        for message in rows:
            previous=by_key.get(message.get('thread_key',message['id']))
            if previous and previous.signature==signature(message) and previous.style_key==style_key:previous.message=message;new.append(previous)
            else:
                item=MailItem(message);item.style_key=style_key;new.append(item)
        first=0
        while first<min(len(old),len(new)) and old[first] is new[first]:first+=1
        tail=0
        while tail<min(len(old),len(new))-first and old[-1-tail] is new[-1-tail]:tail+=1
        self.updating=True
        if first!=len(old) or first!=len(new):self.items.splice(first,len(old)-first-tail,new[first:len(new)-tail if tail else len(new)])
        index=next((i for i,item in enumerate(new) if any(m['id']==selected_id for m in item.message['members'])),Gtk.INVALID_LIST_POSITION) if selected_id else Gtk.INVALID_LIST_POSITION
        self.selection.set_selected(index);self.updating=False
        selected=self.selection.get_selected_item()
        if selected:self.selected_callback(self,selected)
        return len(new)
