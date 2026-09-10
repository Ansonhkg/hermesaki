"""Verify public MCP transport with a temporary mailbox-scoped identity."""
import json
import time
import urllib.request
import urllib.error
from .setup_cloudflare import web_hosts
from .setup_services import DeploymentError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def verify(runtime, settings, plan, credentials):
    if set(credentials) != {'client_id', 'client_secret'} or any(
        not isinstance(v, str) or not 10 <= len(v) <= 512 or not v.isascii()
        or any(c.isspace() for c in v) for v in credentials.values()
    ):
        raise ValueError('access_service_credentials_required')
    result = {'id':'authenticated_agent', 'state':'pending', 'plan_id':plan['id'],
              'checked_at':int(time.time()), 'detail':'Remote MCP verification did not pass.'}
    issued = None
    try:
        issued = json.loads(runtime.dc('exec','-T','api','python','-',stdin='''import json
from pathlib import Path
from hermesaki.http import create_app
s=create_app().s.store
with s.db() as db:account=db.execute('SELECT id FROM inboxes WHERE email=? AND active=1',(MAILBOX,)).fetchone()
if account is None:raise ValueError('first_mailbox_missing')
token=s.token(account['id'],['mail.read'],ttl=120)
print(json.dumps({'inbox_id':account['id'],'id':token['id'],'token':token['token']}))
'''.replace('MAILBOX',repr(plan['first_mailbox']))))
        url = 'https://' + web_hosts(settings)[0] + '/mcp'
        def call(token, method, params=None):
            body = {'jsonrpc':'2.0','id':1,'method':method}
            if params is not None: body['params'] = params
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
                'Content-Type':'application/json','User-Agent':'Hermesaki/0.1',
                'Authorization':'Bearer '+token,
                'CF-Access-Client-Id':credentials['client_id'],
                'CF-Access-Client-Secret':credentials['client_secret']})
            try:
                response = urllib.request.build_opener(NoRedirect()).open(req, timeout=15)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                raw = response.read(65536)
                try: value = json.loads(raw)
                except ValueError: value = {}
                return response.code, value
        code, value = call(issued['token'],'tools/call',{'name':'list_folders','arguments':{'inbox_id':issued['inbox_id']}})
        read = code == 200 and isinstance(value.get('result'),dict) and value['result'].get('isError') is False
        # Empty recipients prevent external delivery even if scope enforcement regresses.
        deny_code, denied = call(issued['token'],'tools/call',{'name':'send_message','arguments':{
            'inbox_id':issued['inbox_id'],'to':[],'subject':'Setup permission check','body_text':'',
            'idempotency_key':'setup-denial-'+issued['id']}})
        denied = deny_code == 200 and denied.get('error',{}).get('message') == 'scope_denied'
        invalid_code, _ = call('invalid-mailbox-token','tools/list')
        passed = read and denied and invalid_code == 401
        result.update(state='passed' if passed else 'pending', observed={
            'read_succeeded':read,'read_only_send_denied':denied,'invalid_token_denied':invalid_code == 401},
            detail='Remote MCP read, denied read-only send and invalid token checked.' if passed else
            'Check the Access service-token policy and mailbox connection; remote authorization checks did not all pass.')
    except (OSError, ValueError, KeyError, TypeError, DeploymentError):
        result['detail'] = 'Remote verification could not finish. Check services and the Access service-token policy, then retry.'
    finally:
        if issued:
            try:
                runtime.dc('exec','-T','api','python','-',stdin='''from hermesaki.http import create_app
s=create_app().s.store
with s.db() as db:db.execute('UPDATE tokens SET revoked=1 WHERE id=?',('''+repr(issued['id'])+''',))
''')
            except DeploymentError:
                result.update(state='pending',detail='Temporary mailbox credential cleanup failed. It expires after two minutes; retry after services recover.')
    return result
