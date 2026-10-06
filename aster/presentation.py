"""Mailbox presentation independent of GTK: timestamps, categories and conversations."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
LOCAL_ZONE=ZoneInfo('Pacific/Auckland')
def timestamp(message):
    try:
        dt=datetime.fromisoformat(message.get('receivedDateTime','').replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError,TypeError):return 0

def date_label(message,full=False,zone=None):
    if not timestamp(message):return 'Unknown date'
    dt=datetime.fromtimestamp(timestamp(message),ZoneInfo(zone) if zone else LOCAL_ZONE)
    return dt.strftime('%a %d %b %Y · %H:%M %Z' if full else '%d %b · %H:%M')

def category_matches(message,category):
    labels=message.get('labelIds',[])
    mapping={'Primary':'CATEGORY_PERSONAL','Promotions':'CATEGORY_PROMOTIONS','Social':'CATEGORY_SOCIAL','Updates':'CATEGORY_UPDATES','Forums':'CATEGORY_FORUMS'}
    if category=='All categories':return True
    if category=='Primary':return 'CATEGORY_PERSONAL' in labels or not any(x.startswith('CATEGORY_') for x in labels)
    return mapping.get(category) in labels

def conversations(messages,category='All categories',term='',mail_filter=0,newest=True):
    groups={}
    for msg in messages:
        if not category_matches(msg,category):continue
        key=msg.get('threadId') or msg.get('conversationId') or msg['id'];groups.setdefault(key,[]).append(msg)
    result=[]
    for key,members in groups.items():
        members.sort(key=lambda m:(timestamp(m),m['id']));latest=dict(members[-1]);latest['thread_key']=key;latest['members']=members;latest['count']=len(members)
        latest['flag']={'flagStatus':'flagged' if any(m.get('flag',{}).get('flagStatus')=='flagged' for m in members) else 'notFlagged'}
        latest['isRead']=all(m.get('isRead',False) for m in members);latest['hasAttachments']=any(m.get('hasAttachments') for m in members)
        if mail_filter==1 and latest['isRead']:continue
        if mail_filter==2 and not any(m.get('flag',{}).get('flagStatus')=='flagged' for m in members):continue
        if term and not any(term.casefold() in (' '.join([m.get('subject',''),m.get('bodyPreview',''),str(m.get('from',{}))])).casefold() for m in members):continue
        result.append(latest)
    return sorted(result,key=lambda m:(timestamp(m),m['id']),reverse=newest)
