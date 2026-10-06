from __future__ import annotations
import base64
import calendar
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
import urllib.parse
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone
import requests

GRAPH = 'https://graph.microsoft.com/v1.0'
SCOPES = 'openid profile offline_access User.Read Mail.ReadWrite Mail.Send Contacts.ReadWrite Calendars.ReadWrite People.Read'

class AppError(Exception):
    pass

class AuthRequired(AppError):
    pass

class ApiError(AppError):
    def __init__(self, message, status):
        super().__init__(message); self.status = status

class AmbiguousSend(AppError):
    pass

class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('br', 'p', 'div', 'li', 'tr') and not self.hidden: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden: self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)

def plain_body(body):
    if body.get('contentType', '').lower() != 'html': return body.get('content', '')
    parser = TextHTML(); parser.feed(body.get('content', '')); return ''.join(parser.parts).strip()

def utc_iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

def event_datetime(value):
    raw = value['dateTime']; raw = raw.replace('Z', '+00:00')
    dt = datetime.fromisoformat(raw)
    # All calendar reads request UTC from Graph.
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()

def month_bounds(year, month):
    start = datetime(year, month, 1).astimezone()
    end = datetime(year + (month == 12), month % 12 + 1, 1).astimezone()
    return utc_iso(start), utc_iso(end)

def email_recipients(text):
    from email.utils import getaddresses
    values = getaddresses([text.replace(';', ',')])
    if not values or any(not address or '@' not in address or any(c.isspace() for c in address) for _, address in values):
        raise AppError('Enter valid recipient addresses, separated by commas.')
    return [{'emailAddress': {'name': name, 'address': address}} for name, address in values]

class Store:
    def __init__(self, root):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.path = self.root / 'mail.sqlite3'
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        os.chmod(self.path, 0o600)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS items (kind TEXT, bucket TEXT, id TEXT, data TEXT, PRIMARY KEY(kind,bucket,id));
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, data TEXT, state TEXT);
        ''')
        self.db.execute("UPDATE drafts SET state='uncertain' WHERE state='sending'"); self.db.commit()
    def get(self, key, default=None):
        with self.lock:
            row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default
    def set(self, key, value):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value))); self.db.commit()
    def items(self, kind, bucket=''):
        with self.lock:
            return [json.loads(x[0]) for x in self.db.execute('SELECT data FROM items WHERE kind=? AND bucket=?', (kind, bucket))]
    def item_count(self,kind,bucket=''):
        with self.lock:return self.db.execute('SELECT count(*) FROM items WHERE kind=? AND bucket=?',(kind,bucket)).fetchone()[0]
    def items_by_bucket(self,kind):
        result={}
        with self.lock:
            for bucket,value in self.db.execute('SELECT bucket,data FROM items WHERE kind=?',(kind,)):result.setdefault(bucket,[]).append(json.loads(value))
        return result
    def replace(self, kind, bucket, values):
        with self.lock, self.db:
            self.db.execute('DELETE FROM items WHERE kind=? AND bucket=?', (kind, bucket))
            self.db.executemany('INSERT INTO items VALUES (?,?,?,?)', [(kind, bucket, x['id'], json.dumps(x)) for x in values])
    def delta(self, bucket, values, cursor, reset=False):
        # Commit changes and cursor together only after every page succeeds.
        with self.lock, self.db:
            if reset: self.db.execute("DELETE FROM items WHERE kind='mail' AND bucket=?", (bucket,))
            for value in values:
                if '@removed' in value:
                    self.db.execute("DELETE FROM items WHERE kind='mail' AND bucket=? AND id=?", (bucket, value['id']))
                else:
                    self.db.execute('INSERT OR REPLACE INTO items VALUES (?,?,?,?)', ('mail', bucket, value['id'], json.dumps(value)))
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', ('delta:' + bucket, json.dumps(cursor)))
    def draft(self, data, state='draft'):
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO drafts VALUES (?,?,?)', (data['id'], json.dumps(data), state))
    def drafts(self):
        with self.lock:
            return [dict(json.loads(row[0]), state=row[1]) for row in self.db.execute('SELECT data,state FROM drafts')]
    def delete_draft(self, draft_id):
        with self.lock, self.db: self.db.execute('DELETE FROM drafts WHERE id=?', (draft_id,))

class SecretVault:
    def __init__(self, client_id):
        import gi
        gi.require_version('Secret', '1')
        from gi.repository import Secret
        self.api = Secret
        self.schema = Secret.Schema.new('org.aster.Mail', Secret.SchemaFlags.NONE, {'client': Secret.SchemaAttributeType.STRING})
        self.attrs = {'client': client_id}
    def load(self):
        try: return self.api.password_lookup_sync(self.schema, self.attrs, None)
        except Exception: return None
    def save(self, token):
        try:
            ok = self.api.password_store_sync(self.schema, self.attrs, self.api.COLLECTION_DEFAULT, 'CMail sign-in', token, None)
            if not ok: raise AppError('The desktop keyring could not save this sign-in.')
        except Exception as exc:
            raise AppError('Unlock your desktop keyring to save the sign-in. Credentials are never saved in the mail database.') from exc
    def clear(self):
        self.api.password_clear_sync(self.schema, self.attrs, None)

class Auth:
    def __init__(self, client_id, vault=None, tenant='common'):
        try: uuid.UUID(client_id)
        except ValueError: raise AppError('Enter the Application (client) ID from your Microsoft app registration.')
        self.client_id = client_id; self.vault = vault or SecretVault(client_id); self.refresh_token = self.vault.load()
        self.tokens = {}; self.lock = threading.RLock(); self.needs_login = False
        if tenant not in ('common', 'organizations', 'consumers'):
            try: uuid.UUID(tenant)
            except ValueError: raise AppError('Enter a valid Directory (tenant) ID, or use common.')
        self.endpoint = 'https://login.microsoftonline.com/' + tenant + '/oauth2/v2.0/'
    def token_request(self, data):
        try: response = requests.post(self.endpoint + 'token', data=dict(client_id=self.client_id, **data), timeout=30)
        except requests.RequestException as exc: raise AppError('Microsoft sign-in is unreachable. Check your connection.') from exc
        result = response.json()
        if not response.ok:
            if result.get('error') in ('invalid_grant', 'interaction_required', 'login_required', 'consent_required'):
                self.needs_login = True
                raise AuthRequired('Microsoft requires a fresh sign-in. Reconnect and complete any school 2FA prompt.')
            raise AppError(result.get('error_description', 'Microsoft sign-in failed.'))
        self.needs_login = False
        refresh = result.get('refresh_token')
        if refresh:
            self.vault.save(refresh); self.refresh_token = refresh
        self.tokens = dict(result, expires_at=time.time() + result.get('expires_in', 3600))
        return result['access_token']
    def access_token(self):
        with self.lock:
            if self.needs_login: raise AuthRequired('Reconnect Microsoft to resume synchronisation.')
            if self.tokens.get('expires_at', 0) > time.time() + 90: return self.tokens['access_token']
            refresh = self.refresh_token
            if not refresh:
                self.needs_login = True
                raise AuthRequired('Sign in to Microsoft in Settings to connect your mailbox.')
            return self.token_request({'grant_type': 'refresh_token', 'refresh_token': refresh, 'scope': SCOPES})
    def sign_in(self):
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        state = secrets.token_urlsafe(32); received = {}
        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                query = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
                if not secrets.compare_digest(query.get('state', [''])[0], state):
                    handler.send_response(400); handler.end_headers(); handler.wfile.write(b'Invalid sign-in state.'); return
                received.update({key: val[0] for key, val in query.items()})
                handler.send_response(200); handler.send_header('Content-Type', 'text/html; charset=utf-8'); handler.end_headers()
                handler.wfile.write(b'<h2>You can return to CMail.</h2><p>Check the app for your sign-in result.</p>')
            def log_message(self, *args): pass
        with HTTPServer(('127.0.0.1', 0), Handler) as server:
            redirect = f'http://localhost:{server.server_port}/'
            params = dict(client_id=self.client_id, response_type='code', redirect_uri=redirect, scope=SCOPES,
                          state=state, code_challenge=challenge, code_challenge_method='S256', prompt='select_account')
            if not webbrowser.open(self.endpoint + 'authorize?' + urllib.parse.urlencode(params)):
                raise AppError('Could not open your browser for Microsoft sign-in.')
            deadline = time.monotonic() + 180; server.timeout = 1
            while not received and time.monotonic() < deadline: server.handle_request()
        if not received: raise AppError('Sign-in timed out. Try again from Settings.')
        if 'error' in received: raise AppError(received.get('error_description', received['error']))
        with self.lock:
            return self.token_request(dict(grant_type='authorization_code', code=received['code'], redirect_uri=redirect, code_verifier=verifier))

class Graph:
    def __init__(self, auth): self.auth = auth; self.backoff_until = 0
    def request(self, method, path, data=None, raw=False):
        url = path if path.startswith('https://') else GRAPH + path
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'graph.microsoft.com' or not parsed.path.startswith('/v1.0/'):
            raise AppError('Refused an unexpected Microsoft API URL.')
        if time.time() < self.backoff_until: raise AppError('Microsoft asked the app to pause. It will retry synchronisation later.')
        headers = {'Authorization': 'Bearer ' + self.auth.access_token(), 'Prefer': 'IdType="ImmutableId", outlook.timezone="UTC"'}
        try: response = requests.request(method, url, json=data, headers=headers, timeout=(10, 45))
        except requests.RequestException as exc:
            if method == 'POST' and path.endswith('/send'): raise AmbiguousSend('The send result is unknown. Check Sent Items in Outlook before sending again.') from exc
            raise AppError('Could not reach Microsoft. Your cached mail and local drafts are still available.') from exc
        if response.status_code == 429:
            try: delay = max(30, min(3600, int(response.headers.get('Retry-After', '60'))))
            except ValueError: delay = 60
            self.backoff_until = time.time() + delay
        if not response.ok:
            if response.status_code == 401:
                self.auth.tokens = {}; self.auth.needs_login = True
                raise AuthRequired('Microsoft requires a fresh sign-in. Use Reconnect to resume synchronisation.')
            if method == 'POST' and path.endswith('/send') and response.status_code >= 500:
                raise AmbiguousSend('Microsoft returned an uncertain send result. Check Sent Items before trying again.')
            try: message = response.json()['error']['message']
            except Exception: message = 'Microsoft returned HTTP ' + str(response.status_code)
            raise ApiError(message, response.status_code)
        if raw: return response.content
        return response.json() if response.content else {}
    def pages(self, path):
        values = []
        while path:
            result = self.request('GET', path); values.extend(result.get('value', [])); path = result.get('@odata.nextLink')
        return values
    def sync_mail(self, store, folder):
        cursor = store.get('delta:' + folder)
        path = cursor or '/me/mailFolders/' + urllib.parse.quote(folder, safe='') + '/messages/delta?$select=id,subject,from,toRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview'
        changes = []
        try:
            while path:
                result = self.request('GET', path); changes.extend(result.get('value', []))
                path = result.get('@odata.nextLink'); cursor = result.get('@odata.deltaLink', cursor)
        except AppError as exc:
            # Expired delta token needs a new full sync; retain existing cache until successful.
            if getattr(exc, 'status', None) == 410 or 'sync state' in str(exc).lower() or 'resync' in str(exc).lower():
                store.set('delta:' + folder, None)
            raise
        if not cursor: raise AppError('Microsoft did not provide a synchronisation cursor.')
        store.delta(folder, changes, cursor, reset=not store.get('delta:' + folder))
    def contacts(self):
        contacts = self.pages('/me/contacts?$select=id,displayName,emailAddresses')
        def folders(path):
            for folder in self.pages(path):
                fid = urllib.parse.quote(folder['id'], safe='')
                contacts.extend(self.pages('/me/contactFolders/' + fid + '/contacts?$select=id,displayName,emailAddresses'))
                folders('/me/contactFolders/' + fid + '/childFolders')
        folders('/me/contactFolders')
        return list({x['id']: x for x in contacts}.values())
    def people(self, term):
        result = self.request('POST', '/search/query', {'requests': [{'entityTypes': ['person'], 'query': {'queryString': term}, 'size': 10}]})
        people = []
        for item in result.get('value', []):
            for container in item.get('hitsContainers', []):
                for hit in container.get('hits', []):
                    resource = hit.get('resource', {}); address = resource.get('emailAddress') or resource.get('userPrincipalName')
                    if address: people.append((resource.get('displayName', address), address))
        return people
    def send(self, store, draft):
        # Persist the remote draft ID before requesting delivery. Never auto-retry sends.
        email_recipients(draft['to'])
        prior = next((x for x in store.drafts() if x['id'] == draft['id']), {})
        if prior.get('state') in ('sending', 'uncertain', 'accepted'):
            raise AppError('This send must not be retried. Check Sent Items first.')
        blobs = []
        for attachment in draft.get('attachments', []):
            file = Path(attachment); blobs.append((file.name, file.read_bytes()))
        if sum(len(blob) for _, blob in blobs) > 2_500_000:
            raise AppError('Attachments exceed this version’s 2.5 MB limit.')
        payload = {'subject': draft['subject'], 'body': {'contentType': 'HTML' if draft.get('html') else 'Text', 'content': draft.get('html') or draft['body']}, 'toRecipients': email_recipients(draft['to']), 'ccRecipients': email_recipients(draft['cc']) if draft.get('cc','').strip() else [], 'bccRecipients': email_recipients(draft['bcc']) if draft.get('bcc','').strip() else []}
        if draft.get('remote_id'):
            path = '/me/messages/' + urllib.parse.quote(draft['remote_id'], safe='')
            self.request('PATCH', path, payload)
            # Replace attachments from a previous preparation attempt.
            for old in self.pages(path + '/attachments'):
                self.request('DELETE', path + '/attachments/' + urllib.parse.quote(old['id'], safe=''))
        else:
            if draft.get('reply_id'):
                remote = self.request('POST', '/me/messages/' + urllib.parse.quote(draft['reply_id'], safe='') + ('/createReplyAll' if draft.get('reply_all') else '/createReply'), {})
            else:
                remote = self.request('POST', '/me/messages', payload)
            draft['remote_id'] = remote['id']; store.draft(draft)
            path = '/me/messages/' + urllib.parse.quote(remote['id'], safe='')
            if draft.get('reply_id'): self.request('PATCH', path, payload)
        for name, blob in blobs:
            self.request('POST', path + '/attachments', {'@odata.type': '#microsoft.graph.fileAttachment', 'name': name, 'contentBytes': base64.b64encode(blob).decode()})
        store.draft(draft, 'sending')
        try: self.request('POST', path + '/send', {})
        except AmbiguousSend:
            store.draft(draft, 'uncertain'); raise
        except Exception:
            store.draft(draft); raise
        store.draft(draft, 'accepted')
        return draft

# Provider-neutral operations used by the native UI.
def _graph_profile(self):return self.request('GET','/me?$select=id,displayName,mail,userPrincipalName')
def _graph_folders(self):
    rows=self.pages('/me/mailFolders?includeHiddenFolders=false');inbox=self.request('GET','/me/mailFolders/inbox?$select=id')['id']
    return [dict(row,id='inbox') if row['id']==inbox else row for row in rows]
def _graph_message(self,mid):return self.request('GET','/me/messages/'+urllib.parse.quote(mid,safe='')+'?$select=id,body')
def _graph_attachments(self,mid):return self.pages('/me/messages/'+urllib.parse.quote(mid,safe='')+'/attachments')
def _graph_read(self,mid,value):return self.request('PATCH','/me/messages/'+urllib.parse.quote(mid,safe=''),{'isRead':value})
def _graph_move(self,mid,target):return self.request('POST','/me/messages/'+urllib.parse.quote(mid,safe='')+'/move',{'destinationId':target})
def _graph_attachment(self,mid,file):return self.request('GET','/me/messages/'+urllib.parse.quote(mid,safe='')+'/attachments/'+urllib.parse.quote(file['id'],safe='')+'/$value',raw=True)
def _graph_calendar(self,start,end):return self.pages('/me/calendarView?'+urllib.parse.urlencode({'startDateTime':start,'endDateTime':end,'$orderby':'start/dateTime'}))
def _graph_flag(self,mid,value):return self.request('PATCH','/me/messages/'+urllib.parse.quote(mid,safe=''),{'flag':{'flagStatus':'flagged' if value else 'notFlagged'}})
Graph.provider='microsoft';Graph.name='Microsoft';Graph.attachment_limit=2_500_000
Graph.profile=_graph_profile;Graph.folders=_graph_folders;Graph.message=_graph_message;Graph.attachments=_graph_attachments
Graph.set_read=_graph_read;Graph.move=_graph_move;Graph.attachment=_graph_attachment;Graph.calendar=_graph_calendar;Graph.flag=_graph_flag
Graph.create_contact=lambda self,data:self.request('POST','/me/contacts',data)
def _graph_event_payload(data):
    result=dict(data)
    if data.get('isAllDay'):
        for field in ('start','end'):result[field]={'dateTime':data[field]['dateTime'][:10]+'T00:00:00','timeZone':'UTC'}
    return result
Graph.create_event=lambda self,data:self.request('POST','/me/events',_graph_event_payload(data))

Graph.update_event=lambda self,eid,data:self.request('PATCH','/me/events/'+urllib.parse.quote(eid,safe=''),_graph_event_payload(data))
Graph.delete_event=lambda self,eid:self.request('DELETE','/me/events/'+urllib.parse.quote(eid,safe=''))

Graph.create_folder=lambda self,name:self.request('POST','/me/mailFolders',{'displayName':name})
