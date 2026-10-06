"""GTK docking with persistent view widgets and shared application state."""
from gi.repository import Gtk,Adw,Gdk,GLib
from . import dockmodel as model

class DockWorkspace:
    def __init__(self,app,host):
        self.app=app;self.host=host;self.layout=model.normalize(app.config.get('dock_layout'));self.panels={p:Gtk.Box(orientation=Gtk.Orientation.VERTICAL,hexpand=True,vexpand=True) for p in model.PANELS};self.groups={};self.windows={};self.dragging=None;self.save_source=0;self.closing=False;self.restoring=False;self.pending_move=None;self.tree_widgets={}
    def start(self):
        self.rebuild();self.select(self.layout['active'],present=False)
    def save(self):
        if self.closing:return
        if self.save_source:GLib.source_remove(self.save_source)
        self.save_source=GLib.timeout_add(250,self.flush)
    def flush(self):
        self.save_source=0
        if self.dragging is not None:self.save_source=GLib.timeout_add(250,self.flush);return False
        if not self.closing:self.app.config.set('dock_layout',self.layout)
        return False
    def focus(self,panel):
        self.app.section=panel;self.layout['active']=panel;self.app.update_navigation()
        for w in self.app.message_commands:w.set_sensitive(panel=='mail' and bool(getattr(self.app,'selected_message',None)))
        self.save()
    def select(self,panel,present=True):
        leaf=model.location(self.layout,panel);leaf['selected']=panel
        group=self.groups[leaf['id']];group.show(panel);self.focus(panel)
        window=self.windows.get(leaf['id'])
        if window and present:window.present()
    def move(self,panel,target=None,edge='center',index=None):
        if self.closing:return False
        if model.move(self.layout,panel,target,edge,index):self.rebuild();self.select(panel);self.save()
        return False
    def schedule_move(self,*args):
        # GDK still owns the source tab until drag-end. Reparenting it in drop
        # can tear down the native drag surface while it is processing a drop.
        if self.dragging is not None:self.pending_move=args
        else:GLib.idle_add(self.move,*args)
    def finish_drag(self):
        self.dragging=None
        for group in self.groups.values():group.hide_preview()
        pending=self.pending_move;self.pending_move=None
        if pending is not None:GLib.idle_add(self.move,*pending)
        if getattr(self.app,'mail_render_pending',False):
            self.app.mail_render_pending=False;GLib.idle_add(lambda:(self.app.render_mail() or False))
    @staticmethod
    def detach(widget):
        parent=widget.get_parent()
        if isinstance(parent,Gtk.Paned):
            if parent.get_start_child() is widget:parent.set_start_child(None)
            else:parent.set_end_child(None)
        elif isinstance(parent,Gtk.Box):parent.remove(widget)
    def pop_out(self,panel):self.schedule_move(panel)
    def reset(self):
        self.layout=model.default();self.rebuild();self.select('mail');self.save()
    def close_float(self,gid):
        if self.closing:return False
        floating=next((f for f in self.layout['floating'] if f['group']['id']==gid),None)
        if floating:
            target=next(model.leaves(self.layout['tree']))['id']
            for panel in list(floating['group']['tabs']):model.move(self.layout,panel,target)
            GLib.idle_add(lambda:(self.rebuild(),self.save(),False)[-1])
        return False
    def shutdown(self):
        if self.closing:return
        for floating in self.layout['floating']:
            window=self.windows.get(floating['group']['id'])
            if window and window.get_width()>1:floating.update(width=window.get_width(),height=window.get_height())
        self.flush();self.closing=True
        for window in list(self.windows.values()):window.destroy()
    def rebuild(self):
        self.restoring=True
        # Keep every untouched panel mounted. Previously ALL views, including
        # WebKit readers, were unmapped/re-realized for every tab movement.
        destinations={p:g['id'] for g in model.groups(self.layout) for p in g['tabs']}
        for gid,group in self.groups.items():
            for p,child in self.panels.items():
                if child.get_parent() is group.stack and destinations.get(p)!=gid:group.stack.remove(child)
        wanted={g['id'] for g in model.groups(self.layout)}
        for gid in list(self.groups):
            if gid not in wanted:self.detach(self.groups[gid].root);del self.groups[gid]
        floating_ids={f['group']['id'] for f in self.layout['floating']}
        for gid in list(self.windows):
            if gid not in floating_ids:self.windows.pop(gid).destroy()
        for leaf in model.groups(self.layout):
            group=self.groups.setdefault(leaf['id'],DockGroup(self,leaf)) if leaf['id'] not in self.groups else self.groups[leaf['id']]
            group.leaf=leaf;group.populate()
        def build(node):
            if node['kind']=='group':return self.groups[node['id']].root
            first=build(node['first']);second=build(node['second'])
            cached=self.tree_widgets.get(id(node))
            if cached and cached[0] is node:
                pane=cached[1]
                if pane.get_start_child() is not first:self.detach(first);pane.set_start_child(first)
                if pane.get_end_child() is not second:self.detach(second);pane.set_end_child(second)
                return pane
            pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL if node['orientation']=='horizontal' else Gtk.Orientation.VERTICAL,hexpand=True,vexpand=True)
            self.tree_widgets[id(node)]=(node,pane)
            self.detach(first);self.detach(second)
            pane.set_start_child(first);pane.set_end_child(second);pane.set_shrink_start_child(True);pane.set_shrink_end_child(True);pane.set_resize_start_child(True);pane.set_resize_end_child(True)
            initial={'ready':False,'tries':0}
            def allocation(widget,clock):
                extent=widget.get_width() if node['orientation']=='horizontal' else widget.get_height();initial['tries']+=1
                if extent>1:widget.set_position(round(extent*node['ratio']));initial['ready']=True;return False
                return initial['tries']<60
            pane.add_tick_callback(allocation)
            def position(w,_):
                extent=w.get_width() if node['orientation']=='horizontal' else w.get_height()
                if initial['ready'] and extent and not self.restoring:node['ratio']=max(.15,min(.85,w.get_position()/extent));self.save()
            pane.connect('notify::position',position);return pane
        root=build(self.layout['tree'])
        old=self.host.get_first_child()
        if old is not root:
            self.detach(root)
            if old:self.host.remove(old)
            self.host.append(root)
        live_nodes=set()
        def remember_nodes(node):
            if node['kind']=='split':live_nodes.add(id(node));remember_nodes(node['first']);remember_nodes(node['second'])
        remember_nodes(self.layout['tree'])
        self.tree_widgets={key:value for key,value in self.tree_widgets.items() if key in live_nodes}
        for floating in self.layout['floating']:
            gid=floating['group']['id'];window=self.windows.get(gid)
            if not window:
                window=Adw.ApplicationWindow(application=self.app,title='CMail · Panels',default_width=floating['width'],default_height=floating['height']);self.windows[gid]=window
                window.connect('close-request',lambda _,key=gid:self.close_float(key))
                def size(w,_,record=floating):
                    if not self.restoring and not self.closing and w.get_width()>1:record.update(width=w.get_width(),height=w.get_height());self.save()
                window.connect('notify::default-width',size);window.connect('notify::default-height',size)
            group_root=self.groups[gid].root
            if group_root.get_root() is not window:
                self.detach(group_root)
                outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);header=Adw.HeaderBar();header.set_title_widget(Gtk.Label(label='CMail'));outer.append(header);outer.append(group_root);window.set_content(outer)
            window.present()
        self.restoring=False
    def parent(self,panel):
        return self.windows.get(model.location(self.layout,panel)['id'],self.app.win)

class DockGroup:
    def __init__(self,workspace,leaf):
        self.workspace=workspace;self.leaf=leaf;self.buttons={}
        self.root=Gtk.Overlay(hexpand=True,vexpand=True);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);self.root.set_child(box)
        self.header=Gtk.Box(spacing=3);self.header.add_css_class('dock-tabs');box.append(self.header)
        self.stack=Gtk.Stack(hexpand=True,vexpand=True);box.append(self.stack)
        self.preview_edge=None
        self.preview=Gtk.DrawingArea(hexpand=True,vexpand=True);self.preview.set_can_target(False);self.preview.set_visible(False);self.preview.set_draw_func(self.draw_preview);self.root.add_overlay(self.preview);self.root.set_measure_overlay(self.preview,False)
        click=Gtk.GestureClick();click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE);click.connect('pressed',lambda *_:self.workspace.focus(self.leaf['selected']) if self.leaf['selected'] else None);self.root.add_controller(click)
        drop=Gtk.DropTarget.new(str,Gdk.DragAction.MOVE)
        drop.connect('accept',lambda *_:workspace.dragging in model.PANELS)
        drop.connect('motion',self.motion);drop.connect('leave',lambda *_:self.hide_preview());drop.connect('drop',self.drop);self.root.add_controller(drop)
    def zone(self,x,y):
        w=max(1,self.root.get_width());h=max(1,self.root.get_height())
        if x<w*.22:return 'left'
        if x>w*.78:return 'right'
        if y<h*.22:return 'top'
        if y>h*.78:return 'bottom'
        return 'center'
    def draw_preview(self,area,cr,w,h):
        edge=self.preview_edge;x=y=0;width=w;height=h
        if edge in ('left','right'):width=w/2;x=w/2 if edge=='right' else 0
        elif edge in ('top','bottom'):height=h/2;y=h/2 if edge=='bottom' else 0
        cr.set_source_rgba(.3,.65,1,.18);cr.rectangle(x+2,y+2,width-4,height-4);cr.fill_preserve();cr.set_source_rgba(.3,.65,1,.8);cr.set_line_width(2);cr.stroke()
    def hide_preview(self):
        self.preview_edge=None;self.preview.set_visible(False)
    def motion(self,_,x,y):
        edge=self.zone(x,y)
        if edge!=self.preview_edge:self.preview_edge=edge;self.preview.queue_draw()
        self.preview.set_visible(True);return Gdk.DragAction.MOVE
    def drop(self,_,panel,x,y):
        self.hide_preview()
        if panel not in model.PANELS:return False
        self.workspace.schedule_move(panel,self.leaf['id'],self.zone(x,y));return True
    def populate(self):
        signature=tuple(self.leaf['tabs'])
        if getattr(self,'tab_signature',None)==signature:
            if self.leaf['selected']:self.show(self.leaf['selected'])
            return
        self.tab_signature=signature
        while self.header.get_first_child():self.header.remove(self.header.get_first_child())
        self.buttons={}
        empty=self.stack.get_child_by_name('empty')
        if empty:self.stack.remove(empty)
        for index,panel in enumerate(self.leaf['tabs']):
            root=self.workspace.panels[panel]
            if root.get_parent() is not self.stack:self.stack.add_named(root,panel)
            tab=Gtk.Button(label=model.PANELS[panel]);tab.add_css_class('flat');tab.set_tooltip_text('Drag to a panel edge to split, onto a tab to group, or outside to pop out');tab.connect('clicked',lambda _,p=panel:self.workspace.select(p));self.header.append(tab);self.buttons[panel]=tab
            source=Gtk.DragSource();source.set_actions(Gdk.DragAction.MOVE)
            source.connect('prepare',lambda _,x,y,p=panel:Gdk.ContentProvider.new_for_value(p))
            def begin(_,drag,p=panel):
                self.workspace.dragging=p
                Gtk.DragIcon.get_for_drag(drag).set_child(Gtk.Label(label=model.PANELS[p]))
            source.connect('drag-begin',begin)
            def cancelled(_,drag,reason,p=panel):
                if reason==Gdk.DragCancelReason.NO_TARGET:self.workspace.schedule_move(p);return True
                return False
            source.connect('drag-cancel',cancelled)
            source.connect('drag-end',lambda *_:self.workspace.finish_drag());tab.add_controller(source)
            target=Gtk.DropTarget.new(str,Gdk.DragAction.MOVE);target.connect('accept',lambda *_:self.workspace.dragging in model.PANELS)
            def dropped(_,p,x,y,i=index):
                if p not in model.PANELS:return False
                self.workspace.schedule_move(p,self.leaf['id'],'center',i);return True
            target.connect('drop',dropped);tab.add_controller(target)
        spacer=Gtk.Box(hexpand=True);self.header.append(spacer)
        detach=Gtk.Button(icon_name='window-new-symbolic');detach.set_tooltip_text('Pop out selected tab into a standalone window');detach.connect('clicked',lambda *_:self.workspace.pop_out(self.leaf['selected']) if self.leaf['selected'] else None);self.header.append(detach)
        menu=Gtk.MenuButton(label='Layout');popover=Gtk.Popover();options=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);popover.set_child(options);menu.set_popover(popover);self.header.append(menu)
        actions=[('Pop out',None,None),('Dock left','left','main'),('Dock right','right','main'),('Dock above','top','main'),('Dock below','bottom','main'),('Return as tab','center','main')]
        for title,edge,target in actions:
            btn=Gtk.Button(label=title)
            def action(_,e=edge,t=target):
                popover.popdown();p=self.leaf['selected']
                if p:self.workspace.schedule_move(p,next(model.leaves(self.workspace.layout['tree']))['id'] if t else None,e or 'center')
            btn.connect('clicked',action);options.append(btn)
        reset=Gtk.Button(label='Reset layout');reset.connect('clicked',lambda *_:(popover.popdown(),GLib.idle_add(lambda:(self.workspace.reset() or False))));options.append(reset)
        if self.leaf['selected']:self.show(self.leaf['selected'])
        else:self.stack.add_named(Gtk.Label(label='Drag a panel here'),'empty')
    def show(self,panel):
        self.workspace.app.ensure_panel(panel);self.stack.set_visible_child_name(panel)
        for p,b in self.buttons.items():
            if p==panel:b.add_css_class('active')
            else:b.remove_css_class('active')
