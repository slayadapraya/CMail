"""Gmail app-password connection over TLS IMAP and SMTP, independent of OAuth."""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from email.utils import getaddresses, parsedate_to_datetime, make_msgid
import imaplib
import json
import mimetypes
from pathlib import Path
import re
import smtplib
import ssl
import threading
from .core import AppError, AuthRequired, AmbiguousSend, SecretVault, email_recipients

class AppPasswordAuth:
    def __init__(self,address,password=None,vault=None):
        email_recipients(address)
        if not address.lower().endswith(('@gmail.com','@googlemail.com')):raise AppError('This connection is for a personal Gmail address.')
        self.address=address.lower().strip();self.client_id='gmail-imap:'+self.address;self.vault=vault or SecretVault(self.client_id)
        self.password=''.join(password.split()) if password else self.vault.load();self.needs_login=False
        if not self.password: self.needs_login=True;raise AuthRequired('Enter a Gmail app password in Settings.')
        if len(self.password)!=16 or not self.password.isalpha():raise AppError('Use the 16-letter Google app password, not your ordinary password or an API key.')
    def save(self):self.vault.save(self.password)


def encode_id(folder,validity,uid):return base64.urlsafe_b64encode(json.dumps([folder,validity,str(uid)]).encode()).decode().rstrip('=')
def decode_id(mid):return json.loads(base64.urlsafe_b64decode(mid+'='*((-len(mid))%4)))
def quoted(value):return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'

def decode_folder(name):
    def replace(match):
        if not match[1]:return '&'
        value=match[1].replace(',','/');return base64.b64decode(value+'='*((-len(value))%4)).decode('utf-16-be')
    try:return re.sub(r'&([^-]*)-',replace,name)
    except Exception:return name

def encode_folder(name):
    result=[];pending=[]
    def flush():
        if pending:result.append('&'+base64.b64encode(''.join(pending).encode('utf-16-be')).decode().rstrip('=').replace('/',',')+'-');pending.clear()
    for char in name:
        if 32<=ord(char)<=126:
            flush();result.append('&-' if char=='&' else char)
        else:pending.append(char)
    flush();return ''.join(result)

class GmailIMAP:
    provider='gmail_password';name='Gmail';attachment_limit=20_000_000
    def __init__(self,auth):self.auth=auth;self.folder_map={'inbox':'INBOX'};self.raw_cache={};self.lock=threading.RLock()
    @contextmanager
    def connection(self):
        if self.auth.needs_login:raise AuthRequired('Reconnect Gmail in Settings.')
        client=None
        try:
            client=imaplib.IMAP4_SSL('imap.gmail.com',993,ssl_context=ssl.create_default_context(),timeout=30)
            client.login(self.auth.address,self.auth.password);yield client
        except imaplib.IMAP4.error as exc:
            if 'AUTHENTICATIONFAILED' in str(exc).upper() or 'AUTHENTICATION' in str(exc).upper():
                self.auth.needs_login=True;raise AuthRequired('Google rejected the app password. Check it in Settings or create a new one.') from exc
            raise AppError('Gmail IMAP could not complete this action. Check your connection and account settings.') from exc
        except (OSError,ssl.SSLError) as exc:raise AppError('Gmail is unreachable. Cached mail and drafts are preserved.') from exc
        finally:
            if client:
                try:client.logout()
                except Exception:pass
    def profile(self):
        with self.connection():pass
        return {'id':self.auth.address,'mail':self.auth.address,'displayName':self.auth.address.split('@')[0]}
    def folders(self):
        with self.connection() as client:
            status,lines=client.list()
            if status!='OK':raise AppError('Could not list Gmail folders.')
        values=[];known={r'\Inbox':'inbox',r'\Sent':'sentitems',r'\Drafts':'drafts',r'\Trash':'deleteditems',r'\Junk':'spam',r'\All':'archive',r'\Flagged':'starred'}
        for line in lines:
            if not isinstance(line,bytes):continue
            match=re.match(rb'\(([^)]*)\)\s+(?:"[^"]*"|NIL)\s+(.+)',line)
            if not match:continue
            flags=match[1].decode().split()
            if '\\Noselect' in flags:continue
            name=match[2].decode().strip('"').replace('\\"','"').replace('\\\\','\\')
            fid='inbox' if name.upper()=='INBOX' else next((known[f] for f in flags if f in known),name)
            self.folder_map[fid]=name
            display={'inbox':'Inbox','sentitems':'Sent','drafts':'Gmail drafts','deleteditems':'Trash','archive':'All mail','spam':'Spam','starred':'Starred'}.get(fid,decode_folder(name))
            values.append({'id':fid,'displayName':display})
        return values
    def create_folder(self,name):
        encoded=encode_folder(name)
        with self.connection() as client:
            status,_=client.create(quoted(encoded))
            if status!='OK':raise AppError('Gmail could not create this folder. Check whether it already exists.')
        self.folder_map[encoded]=encoded
        return {'id':encoded,'displayName':name}
    def select(self,client,folder,readonly=True):
        status,_=client.select(quoted(self.folder_map.get(folder,folder)),readonly=readonly)
        if status!='OK':raise AppError('Could not open this Gmail folder.')
        _,validity=client.response('UIDVALIDITY');return (validity or [b'0'])[0].decode()
    def fetch(self,client,uid,full=False):
        spec='(UID FLAGS BODY.PEEK[])' if full else '(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID CONTENT-TYPE)])'
        status,values=client.uid('FETCH',str(uid),spec)
        if status!='OK':raise AppError('Could not fetch a Gmail message.')
        for value in values:
            if isinstance(value,tuple):return value[0],value[1]
        return None,None
    def normalized(self,raw,flags,mid,full=False):
        message=BytesParser(policy=policy.default).parsebytes(raw)
        name,address=(getaddresses([str(message.get('From',''))])+[('','')])[0]
        try:date=parsedate_to_datetime(str(message.get('Date',''))).astimezone(timezone.utc).isoformat()
        except Exception:date=datetime.now(timezone.utc).isoformat()
        best=message.get_body(preferencelist=('plain','html')) if full else None
        try:content=best.get_content() if best else ''
        except Exception:content='Unable to decode this message body.'
        def recipients(header):return [{'emailAddress':{'name':n,'address':a}} for n,a in getaddresses([str(message.get(header,''))]) if a]
        return {'id':mid,'subject':str(message.get('Subject','')),'from':{'emailAddress':{'name':name,'address':address}},'toRecipients':recipients('To'),'ccRecipients':recipients('Cc'),'receivedDateTime':date,'isRead':b'\\Seen' in flags,'flag':{'flagStatus':'flagged' if b'\\Flagged' in flags else 'notFlagged'},'hasAttachments':any(p.get_filename() for p in message.walk()) if full else message.get_content_type()=='multipart/mixed','bodyPreview':content[:180] if full else '', 'body':{'contentType':'HTML' if best and best.get_content_type()=='text/html' else 'Text','content':content},'message_id':str(message.get('Message-ID',''))}
    def sync_mail(self,store,folder):
        with self.connection() as client:
            validity=self.select(client,folder);status,values=client.uid('SEARCH',None,'ALL')
            if status!='OK':raise AppError('Could not synchronise Gmail folder.')
            uids=values[0].decode().split() if values and values[0] else [];previous={x['id']:x for x in store.items('mail',folder)};rows=[]
            # Batch headers and flags to avoid a network round-trip for every email.
            spec='(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID CONTENT-TYPE)])'
            for offset in range(0,len(uids),100):
                status,values=client.uid('FETCH',','.join(uids[offset:offset+100]),spec)
                if status!='OK':raise AppError('Could not synchronise Gmail message headers.')
                for value in values:
                    if not isinstance(value,tuple):continue
                    flags,raw=value;match=re.search(rb'UID (\d+)',flags)
                    if not match:raise AppError('Gmail returned a message without its UID.')
                    mid=encode_id(self.folder_map.get(folder,folder),validity,match[1].decode());item=self.normalized(raw,flags,mid)
                    if mid in previous:item['bodyPreview']=previous[mid].get('bodyPreview','')
                    rows.append(item)
            changes=rows+[{'id':mid,'@removed':{}} for mid in previous if mid not in {x['id'] for x in rows}]
            store.delta(folder,changes,'imap:'+validity,reset=True)
    def raw_message(self,mid):
        with self.lock:
            if mid in self.raw_cache:return self.raw_cache[mid]
        folder,validity,uid=decode_id(mid)
        with self.connection() as client:
            current=self.select(client,folder)
            if current!=validity:raise AppError('This message’s folder changed. Refresh and select it again.')
            flags,raw=self.fetch(client,uid,True)
            if raw is None:raise AppError('This message is no longer in the folder. Refresh your mailbox.')
        with self.lock:
            if sum(len(x[1]) for x in self.raw_cache.values())+len(raw)>25_000_000:self.raw_cache.clear()
            self.raw_cache[mid]=(flags,raw)
        return flags,raw
    def message(self,mid):flags,raw=self.raw_message(mid);return self.normalized(raw,flags,mid,True)
    def attachments(self,mid):
        _,raw=self.raw_message(mid);message=BytesParser(policy=policy.default).parsebytes(raw)
        return [{'id':str(i),'name':part.get_filename() or 'Inline image','isInline':bool(part.get('Content-ID')) or part.get_content_disposition()=='inline','contentId':str(part.get('Content-ID','')).strip('<>'),'mimeType':part.get_content_type(),'size':len(part.get_payload(decode=True) or b''),'@odata.type':'#microsoft.graph.fileAttachment'} for i,part in enumerate(message.walk()) if part.get_filename() or part.get('Content-ID')]
    def attachment(self,mid,file):
        _,raw=self.raw_message(mid);message=BytesParser(policy=policy.default).parsebytes(raw);return list(message.walk())[int(file['id'])].get_payload(decode=True) or b''
    def action(self,mid,command,*args):
        folder,validity,uid=decode_id(mid)
        with self.connection() as client:
            if self.select(client,folder,readonly=False)!=validity:raise AppError('Folder changed; refresh your mailbox.')
            status,_=client.uid(command,uid,*args)
            if status!='OK':raise AppError('Gmail could not complete this action.')
        with self.lock:self.raw_cache.pop(mid,None)
    def set_read(self,mid,value):return self.action(mid,'STORE','+FLAGS.SILENT' if value else '-FLAGS.SILENT',r'(\Seen)')
    def flag(self,mid,value):return self.action(mid,'STORE','+FLAGS.SILENT' if value else '-FLAGS.SILENT',r'(\Flagged)')
    def move(self,mid,target):
        destination=self.folder_map.get(target)
        if not destination:raise AppError('Gmail folders are not loaded. Reconnect or refresh first.')
        return self.action(mid,'MOVE',quoted(destination))
    def contacts(self):return []
    def people(self,term):return []
    def create_contact(self,data):raise AppError('The app-password connection supports mail. Use Google OAuth with Contacts access to create Google contacts.')
    def calendar(self,*args):raise AppError('The app-password connection supports mail. Use Google OAuth with Calendar access for Google Calendar.')
    def create_event(self,data):return self.calendar()
    def update_event(self,eid,data):return self.calendar()
    def delete_event(self,eid):return self.calendar()
    def send(self,store,draft):
        prior=next((x for x in store.drafts() if x['id']==draft['id']),{})
        if prior.get('state') in ('sending','uncertain','accepted'):raise AppError('Do not retry this send. Check Gmail Sent first.')
        message=EmailMessage();recipients=[]
        message['From']=self.auth.address;message['Subject']=draft['subject'];message['Message-ID']=draft.setdefault('outgoing_message_id',make_msgid())
        for field,header in [('to','To'),('cc','Cc'),('bcc','Bcc')]:
            if draft.get(field,'').strip():
                recipients.extend(x['emailAddress']['address'] for x in email_recipients(draft[field]))
                if field!='bcc':message[header]=draft[field].replace(';',',')
        message.set_content(draft.get('body',''))
        if draft.get('html'):message.add_alternative(draft['html'],subtype='html')
        if draft.get('reply_id'):
            original=self.message(draft['reply_id'])
            if original.get('message_id'):message['In-Reply-To']=original['message_id'];message['References']=original['message_id']
        files=[(Path(p),Path(p).read_bytes()) for p in draft.get('attachments',[])]
        if sum(len(blob) for _,blob in files)>self.attachment_limit:raise AppError('Attachments exceed 20 MB.')
        for path,blob in files:
            major,minor=(mimetypes.guess_type(path.name)[0] or 'application/octet-stream').split('/',1);message.add_attachment(blob,maintype=major,subtype=minor,filename=path.name)
        client=None;submitted=False
        try:
            client=smtplib.SMTP_SSL('smtp.gmail.com',465,context=ssl.create_default_context(),timeout=45);client.login(self.auth.address,self.auth.password)
            store.draft(draft,'sending');submitted=True
            refused=client.send_message(message,from_addr=self.auth.address,to_addrs=recipients)
            if refused:
                store.draft(draft,'uncertain');raise AmbiguousSend('Some recipients may have received this message. Check Gmail Sent before resending.')
        except smtplib.SMTPAuthenticationError as exc:
            self.auth.needs_login=True;raise AuthRequired('Google rejected the app password. Reconnect Gmail.') from exc
        except (smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPDataError) as exc:
            store.draft(draft);raise AppError('Gmail rejected the message. It has been kept as a local draft.') from exc
        except AmbiguousSend:raise
        except (OSError,smtplib.SMTPException) as exc:
            if submitted:store.draft(draft,'uncertain');raise AmbiguousSend('The send result is unknown. Check Gmail Sent before resending.') from exc
            raise AppError('Could not connect to Gmail sending. Your local draft is preserved.') from exc
        finally:
            if client:
                try:client.quit()
                except Exception:pass
        store.draft(draft,'accepted');return draft
