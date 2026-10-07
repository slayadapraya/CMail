"""Google desktop OAuth and Gmail/Calendar/People adapters. No Microsoft credentials are reused."""
import base64
import hashlib
import html
import json
import mimetypes
from pathlib import Path
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone
from email.message import EmailMessage, Message
from email.utils import getaddresses
import requests
from .core import AppError, AuthRequired, ApiError, AmbiguousSend, SecretVault, email_recipients, plain_body, event_datetime, utc_iso

MAIL_SCOPE='https://www.googleapis.com/auth/gmail.modify'
CAL_SCOPE='https://www.googleapis.com/auth/calendar.events'
CONTACT_SCOPE='https://www.googleapis.com/auth/contacts'

def credentials_from_json(path):
    try: data=json.loads(Path(path).read_text())['installed']
    except (KeyError,ValueError,OSError) as exc:raise AppError('Select the downloaded Google OAuth JSON for a Desktop app.') from exc
    if not data.get('client_id','').endswith('.apps.googleusercontent.com') or not data.get('client_secret'):
        raise AppError('The selected file does not contain Google Desktop app credentials.')
    return {'client_id':data['client_id'],'client_secret':data['client_secret']}

class GoogleAuth:
    def __init__(self,client_id,client_secret,calendar=False,contacts=False,vault=None):
        if not client_id.endswith('.apps.googleusercontent.com'):raise AppError('Import Google Desktop app credentials in Settings first.')
        self.client_id=client_id;self.client_secret=client_secret;self.vault=vault or SecretVault('google:'+client_id)
        self.refresh_token=self.vault.load();self.tokens={};self.needs_login=False;self.lock=threading.RLock()
        self.calendar_enabled=calendar;self.contacts_enabled=contacts
        self.scopes=[MAIL_SCOPE]+([CAL_SCOPE] if calendar else [])+([CONTACT_SCOPE] if contacts else [])
    def token_request(self,data):
        try:response=requests.post('https://oauth2.googleapis.com/token',data=dict(client_id=self.client_id,client_secret=self.client_secret,**data),timeout=30)
        except requests.RequestException as exc:raise AppError('Google sign-in is unreachable. Your local drafts are preserved.') from exc
        value=response.json()
        if not response.ok:
            if value.get('error') in ('invalid_grant','interaction_required'):
                self.needs_login=True;raise AuthRequired('Google requires a fresh sign-in. Reconnect your Google account.')
            raise AppError(value.get('error_description',value.get('error','Google sign-in failed.')))
        # Honour granted scopes; optional services must not be treated as granted when declined.
        if value.get('scope'):
            granted=set(value['scope'].split())
            if MAIL_SCOPE not in granted:raise AppError('Gmail access was not granted. Sign in again and grant mail permission.')
            self.calendar_enabled=CAL_SCOPE in granted;self.contacts_enabled=CONTACT_SCOPE in granted
        if value.get('refresh_token'):
            self.vault.save(value['refresh_token']);self.refresh_token=value['refresh_token']
        self.tokens=dict(value,expires_at=time.time()+value.get('expires_in',3600));self.needs_login=False
        return value['access_token']
    def access_token(self):
        with self.lock:
            if self.needs_login:raise AuthRequired('Reconnect Google to resume synchronisation.')
            if self.tokens.get('expires_at',0)>time.time()+90:return self.tokens['access_token']
            if not self.refresh_token:self.needs_login=True;raise AuthRequired('Sign in with Google in Settings.')
            return self.token_request({'grant_type':'refresh_token','refresh_token':self.refresh_token})
    def sign_in(self):
        verifier=secrets.token_urlsafe(64);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        state=secrets.token_urlsafe(32);received={}
        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                query=urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
                if not secrets.compare_digest(query.get('state',[''])[0],state):
                    handler.send_response(400);handler.end_headers();handler.wfile.write(b'Invalid sign-in state.');return
                received.update({key:val[0] for key,val in query.items()})
                handler.send_response(200);handler.send_header('Content-Type','text/html; charset=utf-8');handler.end_headers();handler.wfile.write(b'<h2>Return to CMail to check your Google sign-in.</h2>')
            def log_message(self,*_):pass
        with HTTPServer(('127.0.0.1',0),Handler) as server:
            redirect=f'http://127.0.0.1:{server.server_port}/'
            params=dict(client_id=self.client_id,response_type='code',redirect_uri=redirect,scope=' '.join(self.scopes),state=state,code_challenge=challenge,code_challenge_method='S256',access_type='offline',prompt='consent select_account')
            if not webbrowser.open('https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(params)):raise AppError('Could not open your browser for Google sign-in.')
            server.timeout=1;deadline=time.monotonic()+180
            while not received and time.monotonic()<deadline:server.handle_request()
        if not received:raise AppError('Google sign-in timed out. Try again.')
        if received.get('error'):raise AppError('Google sign-in: '+received['error'])
        with self.lock:return self.token_request(dict(grant_type='authorization_code',code=received['code'],redirect_uri=redirect,code_verifier=verifier))


def decode64(value):return base64.urlsafe_b64decode(value+'='*((-len(value))%4))
def walk_parts(part):
    yield part
    for child in part.get('parts',[]):yield from walk_parts(child)

def decode_part(part):
    header=Message();header['Content-Type']=next((h['value'] for h in part.get('headers',[]) if h['name'].lower()=='content-type'),part.get('mimeType','text/plain'))
    blob=decode64(part.get('body',{}).get('data',''))
    try:return blob.decode(header.get_content_charset() or 'utf-8',errors='replace')
    except LookupError:return blob.decode('utf-8',errors='replace')

def normalize_message(value):
    payload=value.get('payload',{});headers={h['name'].lower():h['value'] for h in payload.get('headers',[])}
    sender=getaddresses([headers.get('from','')]);labels=value.get('labelIds',[])
    bodies=[p for p in walk_parts(payload) if not p.get('filename') and p.get('mimeType') in ('text/plain','text/html') and p.get('body',{}).get('data')]
    best=next((p for p in bodies if p['mimeType']=='text/plain'),bodies[0] if bodies else {})
    text=decode_part(best)
    html_part=next((p for p in bodies if p['mimeType']=='text/html'),None)
    html_body=decode_part(html_part) if html_part else ''
    files=[]
    for part in walk_parts(payload):
        ph={h['name'].lower():h['value'] for h in part.get('headers',[])};cid=ph.get('content-id','').strip('<>')
        if part.get('filename') or cid:
            files.append({'id':part.get('body',{}).get('attachmentId') or 'part:'+part.get('partId',''),'name':part.get('filename') or 'Inline image','size':part.get('body',{}).get('size',0),'mimeType':part.get('mimeType','application/octet-stream'),'contentId':cid,'isInline':bool(cid) or ph.get('content-disposition','').lower().startswith('inline'),'inline_data':part.get('body',{}).get('data'),'@odata.type':'#microsoft.graph.fileAttachment'})
    def recipients(name):return [{'emailAddress':{'name':n,'address':a}} for n,a in getaddresses([headers.get(name,'')]) if a]
    return dict(htmlBody=html_body,files=files,id=value['id'],subject=headers.get('subject',''),from_='unused',**{'from':{'emailAddress':{'name':sender[0][0] if sender else '', 'address':sender[0][1] if sender else ''}}},toRecipients=recipients('to'),ccRecipients=recipients('cc'),receivedDateTime=datetime.fromtimestamp(int(value.get('internalDate',0))/1000,timezone.utc).isoformat(),isRead='UNREAD' not in labels,hasAttachments=any(not f['isInline'] for f in files),bodyPreview=html.unescape(value.get('snippet','')),body={'contentType':'HTML' if best.get('mimeType')=='text/html' else 'Text','content':text},flag={'flagStatus':'flagged' if 'STARRED' in labels else 'notFlagged'},threadId=value.get('threadId'),message_id=headers.get('message-id'),labelIds=labels)

class Gmail:
    provider='google';name='Google';attachment_limit=20_000_000
    def __init__(self,auth):self.auth=auth;self.backoff_until=0;self.service_backoffs={};self.rate_lock=threading.Lock();self.next_request=0;self.quota_failures=0;self.cancel_event=threading.Event()
    def api(self,method,path,data=None,service='gmail',send=False):
        if self.cancel_event.is_set():raise AppError('Mail loading stopped. Saved messages will resume next launch.')
        bases={'gmail':'https://gmail.googleapis.com/gmail/v1/users/me/','calendar':'https://www.googleapis.com/calendar/v3/','people':'https://people.googleapis.com/v1/'}
        if service not in bases or path.startswith(('http:','https:','//')):raise AppError('Refused an unexpected Google API URL.')
        if time.time()<(self.backoff_until if service=='gmail' else self.service_backoffs.get(service,0)):raise AppError('Google requested a pause for '+service+'. Synchronisation will retry later.')
        if service=='gmail':
            cost=100 if send else 40 if path.startswith('threads/') and method=='GET' else 20 if path.startswith('messages/') and method=='GET' else 5
            with self.rate_lock:
                delay=max(0,self.next_request-time.monotonic())
                if delay:time.sleep(delay)
                self.next_request=time.monotonic()+cost/70.0
        if self.cancel_event.is_set():raise AppError('Mail loading stopped. Saved messages will resume next launch.')
        if time.time()<(self.backoff_until if service=='gmail' else self.service_backoffs.get(service,0)):raise AppError('Google requested a pause for '+service+'. Synchronisation will retry later.')
        try:response=requests.request(method,bases[service]+path,json=data,headers={'Authorization':'Bearer '+self.auth.access_token()},timeout=(10,45))
        except requests.RequestException as exc:
            if send:raise AmbiguousSend('Google’s send result is unknown. Check Gmail Sent before sending again.') from exc
            raise AppError('Google is unreachable. Cached mail and local drafts remain available.') from exc
        if response.status_code==401:
            self.auth.needs_login=True;self.auth.tokens={};raise AuthRequired('Google requires sign-in. Use Reconnect.')
        if not response.ok:
            try:error=response.json()['error'];message=error.get('message','Google API error');reasons=[x.get('reason') for x in error.get('errors',[])]
            except Exception:message='Google returned HTTP '+str(response.status_code);reasons=[]
            if response.status_code==429 or any(r in ('rateLimitExceeded','userRateLimitExceeded','quotaExceeded') for r in reasons) or 'quota exceeded' in message.lower():
                try:delay=max(30,min(3600,int(response.headers.get('Retry-After',str(min(900,60*2**self.quota_failures))))))
                except ValueError:delay=60
                self.quota_failures=min(self.quota_failures+1,4)
                if service=='gmail':self.backoff_until=time.time()+delay
                else:self.service_backoffs[service]=time.time()+delay
                message=f'Google quota pause · retrying automatically in {delay} seconds. Cached mail is available.'
            if send and response.status_code>=500:raise AmbiguousSend('Google’s send result is unknown. Check Sent before sending again.')
            raise ApiError(message,response.status_code)
        self.quota_failures=0
        return response.json() if response.content else {}
    def pages(self,path,key,service='gmail'):
        values=[];token=None
        while True:
            result=self.api('GET',path+('&' if '?' in path else '?')+urllib.parse.urlencode({'pageToken':token}) if token else path,service=service)
            values.extend(result.get(key,[]));token=result.get('nextPageToken')
            if not token:return values
    def profile(self):
        profile=self.api('GET','profile');address=profile['emailAddress'];return {'id':address.lower(),'mail':address,'displayName':address.split('@')[0]}
    def folders(self):
        rows=[{'id':a,'displayName':b} for a,b in [('inbox','Inbox'),('STARRED','Starred'),('sentitems','Sent'),('drafts','Gmail drafts'),('archive','Archive'),('SPAM','Spam'),('deleteditems','Trash')]]
        rows.extend({'id':x['id'],'displayName':x['name']} for x in self.api('GET','labels').get('labels',[]) if x['type']=='user');return rows
    def create_folder(self,name):
        value=self.api('POST','labels',{'name':name,'labelListVisibility':'labelShow','messageListVisibility':'show'})
        return {'id':value['id'],'displayName':value.get('name',name)}
    def label(self,folder):return {'inbox':'INBOX','sentitems':'SENT','drafts':'DRAFT','deleteditems':'TRASH'}.get(folder,folder)
    def matches(self,msg,folder):
        labels=msg.get('labelIds',[])
        if folder=='archive':return not any(x in labels for x in ('INBOX','SENT','DRAFT','TRASH','SPAM'))
        return self.label(folder) in labels
    def message(self,mid):return normalize_message(self.api('GET','messages/'+urllib.parse.quote(mid,safe='')+'?format=full'))
    def sync_mail(self,store,folder,progress=None,batch_limit=None):
        cursor=store.get('delta:'+folder);changes=[];checkpoint=store.get('import:'+folder);baseline=checkpoint['baseline'] if checkpoint and not cursor else self.api('GET','profile')['historyId']
        if cursor:
            try:history=self.pages('history?'+urllib.parse.urlencode({'startHistoryId':cursor,'maxResults':500}),'history')
            except ApiError as exc:
                if exc.status==404:cursor=None
                else:raise
            if cursor:
                ids={m['id'] for item in history for key in ('messagesAdded','messagesDeleted','labelsAdded','labelsRemoved') for entry in item.get(key,[]) for m in [entry['message']]}
                for mid in ids:
                    try:msg=self.message(mid)
                    except ApiError as exc:
                        if exc.status==404:changes.append({'id':mid,'@removed':{}});continue
                        raise
                    changes.append(msg if self.matches(msg,folder) else {'id':mid,'@removed':{}})
        if not cursor:
            # A bounded desktop refresh checks the newest page before importing older mail.
            # Preserve the import's original history baseline until the snapshot completes.
            if batch_limit:
                latest_query={'maxResults':25,'includeSpamTrash':'true'}
                if folder=='archive':latest_query['q']='-in:inbox -in:sent -in:drafts -in:trash -in:spam'
                else:latest_query['labelIds']=self.label(folder)
                latest=self.api('GET','messages?'+urllib.parse.urlencode(latest_query)).get('messages',[])
                cached={m['id'] for m in store.items('mail',folder)};recent=[]
                for ref in latest:
                    if ref['id'] in cached:continue
                    try:recent.append(self.message(ref['id']))
                    except ApiError as exc:
                        if exc.status!=404:raise
                if recent:store.delta(folder,recent,'',reset=False)
            query={'maxResults':500,'includeSpamTrash':'true'}
            if folder=='archive':query['q']='-in:inbox -in:sent -in:drafts -in:trash -in:spam'
            else:query['labelIds']=self.label(folder)
            refs=checkpoint['refs'] if checkpoint else self.pages('messages?'+urllib.parse.urlencode(query),'messages')
            offset=checkpoint['offset'] if checkpoint else 0;loaded=offset;first=offset==0 and not batch_limit;batches=0
            cached={m['id'] for m in store.items('mail',folder)} if batch_limit else set()
            if not checkpoint:store.set('import:'+folder,{'baseline':baseline,'refs':refs,'offset':0})
            for index,ref in enumerate(refs[offset:],offset+1):
                try:
                    if ref['id'] not in cached:changes.append(self.message(ref['id']))
                except ApiError as exc:
                    if exc.status!=404:raise
                if index%25==0 or index==len(refs):
                    loaded=index;store.delta(folder,changes,'',reset=first);first=False;changes=[];store.set('import:'+folder,{'baseline':baseline,'refs':refs,'offset':index})
                    if progress:progress(loaded,len(refs))
                    batches+=1
                    if batch_limit and batches>=batch_limit and index<len(refs):return
            if not refs:store.delta(folder,[],'',reset=not batch_limit)
            # Only mark history complete after every page was fetched successfully.
            store.delta(folder,[],baseline);store.set('import:'+folder,None);return
        store.delta(folder,changes,baseline,reset=False)
    def set_read(self,mid,value):return self.api('POST','messages/'+mid+'/modify',{'removeLabelIds':['UNREAD']} if value else {'addLabelIds':['UNREAD']})
    def flag(self,mid,value):return self.api('POST','messages/'+mid+'/modify',{'addLabelIds':['STARRED']} if value else {'removeLabelIds':['STARRED']})
    def move(self,mid,target):
        if target=='deleteditems':return self.api('POST','messages/'+mid+'/trash',{})
        return self.api('POST','messages/'+mid+'/modify',{'removeLabelIds':['INBOX'],'addLabelIds':[] if target=='archive' else [self.label(target)]})
    def thread(self,tid):
        raw=self.api('GET','threads/'+urllib.parse.quote(tid,safe='')+'?format=full')
        return [normalize_message(m) for m in raw.get('messages',[])]
    def attachments(self,mid):return self.message(mid).get('files',[])
    def attachment(self,mid,file):
        if file.get('inline_data'):return decode64(file['inline_data'])
        return decode64(self.api('GET','messages/'+mid+'/attachments/'+urllib.parse.quote(file['id'],safe=''))['data'])
    def contacts(self):
        if not self.auth.contacts_enabled:return []
        values=self.pages('people/me/connections?personFields=names,emailAddresses,photos&pageSize=1000','connections',service='people')
        return [{'photoUrl':next((photo['url'] for photo in p.get('photos',[]) if not photo.get('default')),None),'id':p['resourceName'],'displayName':p.get('names',[{}])[0].get('displayName',''),'emailAddresses':[{'address':e['value']} for e in p.get('emailAddresses',[])]} for p in values]
    def people(self,term):
        if not self.auth.contacts_enabled:return []
        self.api('GET','people:searchContacts?query=&readMask=names,emailAddresses',service='people')
        rows=self.api('GET','people:searchContacts?'+urllib.parse.urlencode({'query':term,'readMask':'names,emailAddresses','pageSize':10}),service='people').get('results',[])
        return [(r['person'].get('names',[{}])[0].get('displayName',e['value']),e['value']) for r in rows for e in r['person'].get('emailAddresses',[])]
    def create_contact(self,data):
        if not self.auth.contacts_enabled:raise AppError('Enable Google Contacts in Settings and sign in again to grant access.')
        return self.api('POST','people:createContact',{'names':[{'givenName':data['displayName']}],'emailAddresses':[{'value':e['address']} for e in data['emailAddresses']]},service='people')
    def calendar(self,start,end):
        if not self.auth.calendar_enabled:raise AppError('Enable Google Calendar in Settings and sign in again to grant access.')
        rows=self.pages('calendars/primary/events?'+urllib.parse.urlencode({'timeMin':start,'timeMax':end,'singleEvents':'true','orderBy':'startTime','maxResults':2500}),'items',service='calendar')
        values=[]
        for e in rows:
            if e.get('status')=='cancelled':continue
            def stamp(v):return {'dateTime':v['dateTime']} if 'dateTime' in v else {'dateTime':datetime.fromisoformat(v['date']).astimezone().isoformat()}
            values.append({'id':e['id'],'subject':e.get('summary','(Untitled)'), 'start':stamp(e['start']),'end':stamp(e['end']),'isAllDay':'date' in e['start'],'location':{'displayName':e.get('location','')},'body':{'contentType':'HTML','content':e.get('description','')},'recurringEventId':e.get('recurringEventId')})
        return values
    def create_event(self,data):
        if not self.auth.calendar_enabled:raise AppError('Enable Google Calendar in Settings and sign in again to grant access.')
        start={'date':data['start']['dateTime'][:10]} if data.get('isAllDay') else {'dateTime':data['start']['dateTime']}
        end={'date':data['end']['dateTime'][:10]} if data.get('isAllDay') else {'dateTime':data['end']['dateTime']}
        return self.api('POST','calendars/primary/events',{'summary':data['subject'],'start':start,'end':end,'location':data['location']['displayName']},service='calendar')
    def update_event(self,eid,data):
        if not self.auth.calendar_enabled:raise AppError('Enable Google Calendar access and sign in again.')
        start={'date':data['start']['dateTime'][:10]} if data.get('isAllDay') else {'dateTime':data['start']['dateTime']}
        end={'date':data['end']['dateTime'][:10]} if data.get('isAllDay') else {'dateTime':data['end']['dateTime']}
        return self.api('PATCH','calendars/primary/events/'+urllib.parse.quote(eid,safe=''),{'summary':data['subject'],'start':start,'end':end,'location':data['location']['displayName']},service='calendar')
    def delete_event(self,eid):
        if not self.auth.calendar_enabled:raise AppError('Enable Google Calendar access and sign in again.')
        return self.api('DELETE','calendars/primary/events/'+urllib.parse.quote(eid,safe=''),service='calendar')
    def send(self,store,draft):
        prior=next((x for x in store.drafts() if x['id']==draft['id']),{})
        if prior.get('state') in ('sending','uncertain','accepted'):raise AppError('This send must not be retried. Check Gmail Sent first.')
        message=EmailMessage()
        for key,header in [('to','To'),('cc','Cc'),('bcc','Bcc')]:
            if draft.get(key,'').strip():email_recipients(draft[key]);message[header]=draft[key].replace(';',',')
        message['Subject']=draft['subject'];message.set_content(draft.get('body',''))
        if draft.get('html'):message.add_alternative(draft['html'],subtype='html')
        if draft.get('reply_id'):
            original=self.message(draft['reply_id'])
            if original.get('message_id'):message['In-Reply-To']=original['message_id'];message['References']=original['message_id']
            draft['thread_id']=original.get('threadId')
        files=[(Path(p),Path(p).read_bytes()) for p in draft.get('attachments',[])]
        if sum(len(b) for _,b in files)>self.attachment_limit:raise AppError('Gmail attachments exceed this version’s 20 MB limit.')
        for path,blob in files:
            mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream';major,minor=mime.split('/',1);message.add_attachment(blob,maintype=major,subtype=minor,filename=path.name)
        payload={'message':{'raw':base64.urlsafe_b64encode(message.as_bytes()).decode()}}
        if draft.get('thread_id'):payload['message']['threadId']=draft['thread_id']
        if draft.get('remote_id'):
            payload['id']=draft['remote_id'];remote=self.api('PUT','drafts/'+draft['remote_id'],payload)
        else:remote=self.api('POST','drafts',payload)
        draft['remote_id']=remote['id'];store.draft(draft,'sending')
        try:sent=self.api('POST','drafts/send',{'id':remote['id']},send=True)
        except AmbiguousSend:store.draft(draft,'uncertain');raise
        except Exception:store.draft(draft);raise
        store.draft(draft,'accepted')
        # A confirmed send already supplies the real Gmail identity; no extra API read is needed.
        if sent.get('id'):
            sender=draft.get('sender',{})
            value={'id':sent['id'],'threadId':sent.get('threadId') or draft.get('thread_id'),'labelIds':['SENT'],'subject':draft['subject'],'from':{'emailAddress':sender},'toRecipients':[{'emailAddress':{'name':name,'address':address}} for name,address in getaddresses([draft['to'].replace(';',',')])],'receivedDateTime':datetime.now(timezone.utc).isoformat(),'bodyPreview':draft.get('body','')[:240],'body':{'contentType':'HTML' if draft.get('html') else 'Text','content':draft.get('html') or draft.get('body','')},'htmlBody':draft.get('html',''),'isRead':True,'hasAttachments':bool(files),'files':[],'localConfirmed':True}
            try:
                store.delta('sentitems',[value],store.get('delta:sentitems',''))
                tid=value.get('threadId')
                if tid:
                    previous=store.items('thread',tid)
                    if not previous:previous=[m for m in store.items('mail','inbox') if m.get('threadId')==tid]
                    store.replace('thread',tid,[m for m in previous if m['id']!=value['id']]+[value])
                draft['sent_message_id']=value['id'];store.draft(draft,'accepted')
            except Exception:
                # Never turn an accepted send into a retryable failure because caching failed.
                draft['cache_warning']=True
        return draft
