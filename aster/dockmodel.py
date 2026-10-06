"""Small, serializable docking tree; every panel has exactly one home."""
import uuid
PANELS={'mail':'Mail','calendar':'Calendar','contacts':'People','drafts':'Drafts'}
def group(tabs=None):
    tabs=list(tabs or [])
    return dict(kind='group',id=uuid.uuid4().hex[:8],tabs=tabs,selected=tabs[0] if tabs else None)
def default():return dict(version=1,tree=group(PANELS),floating=[],active='mail')
def leaves(node):
    if node['kind']=='group':yield node
    else:
        yield from leaves(node['first']);yield from leaves(node['second'])
def normalize(value):
    if not isinstance(value,dict):return default()
    seen=set();ids=set()
    def node(raw,depth=0):
        if not isinstance(raw,dict) or depth>8:return group()
        if raw.get('kind')=='split':
            a=node(raw.get('first'),depth+1);b=node(raw.get('second'),depth+1)
            if not any(g['tabs'] for g in leaves(a)):return b
            if not any(g['tabs'] for g in leaves(b)):return a
            try:ratio=max(.15,min(.85,float(raw.get('ratio',.5))))
            except (TypeError,ValueError):ratio=.5
            return dict(kind='split',orientation='vertical' if raw.get('orientation')=='vertical' else 'horizontal',ratio=ratio,first=a,second=b)
        tabs=[]
        for key in raw.get('tabs',[]) if isinstance(raw.get('tabs'),list) else []:
            if isinstance(key,str) and key in PANELS and key not in seen:tabs.append(key);seen.add(key)
        result=group(tabs);gid=raw.get('id')
        if isinstance(gid,str) and len(gid)<40 and gid not in ids:result['id']=gid
        ids.add(result['id']);result['selected']=raw.get('selected') if raw.get('selected') in tabs else (tabs[0] if tabs else None)
        return result
    tree=node(value.get('tree'));floating=[]
    for raw in value.get('floating',[])[:4] if isinstance(value.get('floating'),list) else []:
        if not isinstance(raw,dict):continue
        leaf=node(raw.get('group'))
        if leaf['kind']!='group' or not leaf['tabs']:continue
        size={}
        for key,initial in [('width',900),('height',700)]:
            try:size[key]=max(360,min(2200,int(raw.get(key,initial))))
            except (TypeError,ValueError):size[key]=initial
        floating.append(dict(group=leaf,**size))
    first=next(leaves(tree));first['tabs'] += [p for p in PANELS if p not in seen]
    if not first['selected'] and first['tabs']:first['selected']=first['tabs'][0]
    return dict(version=1,tree=tree,floating=floating,active=value.get('active') if isinstance(value.get('active'),str) and value.get('active') in PANELS else 'mail')
def groups(layout):
    yield from leaves(layout['tree'])
    for floating in layout['floating']:yield floating['group']
def location(layout,panel):return next(g for g in groups(layout) if panel in g['tabs'])
def prune(node):
    if node['kind']=='group':return node if node['tabs'] else None
    a=prune(node['first']);b=prune(node['second'])
    if a is None:return b
    if b is None:return a
    node.update(first=a,second=b);return node
def replace(node,gid,new):
    if node['kind']=='group':return new if node['id']==gid else node
    node['first']=replace(node['first'],gid,new);node['second']=replace(node['second'],gid,new);return node
def move(layout,panel,target_id=None,edge='center',index=None):
    source=location(layout,panel)
    target=next((g for g in groups(layout) if g['id']==target_id),None)
    if target is source and edge!='center' and len(source['tabs'])==1:return False
    source['tabs'].remove(panel)
    if source['selected']==panel:source['selected']=source['tabs'][0] if source['tabs'] else None
    if target is None:
        target=group([panel]);layout['floating'].append(dict(group=target,width=900,height=700))
    elif edge=='center':
        target['tabs'].insert(min(index if index is not None else len(target['tabs']),len(target['tabs'])),panel);target['selected']=panel
    else:
        # Edge splits apply to the main window. Floating groups accept tabs or pop out.
        if any(f['group'] is target for f in layout['floating']):
            target['tabs'].append(panel);target['selected']=panel
        else:
            new=group([panel]);split=dict(kind='split',orientation='horizontal' if edge in ('left','right') else 'vertical',ratio=.5,first=new if edge in ('left','top') else target,second=target if edge in ('left','top') else new)
            layout['tree']=replace(layout['tree'],target['id'],split)
    layout['tree']=prune(layout['tree']) or group()
    layout['floating']=[f for f in layout['floating'] if f['group']['tabs']]
    layout['active']=panel
    return True
