import base64,io,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hermesaki.config import Config
from hermesaki.store import Store,Problem
from hermesaki.http import App
from hermesaki import sessions,administrators
class SessionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  Path(self.tmp.name,'key').write_text(base64.b64encode(os.urandom(32)).decode())
  self.store=Store(self.tmp.name);self.token=self.store.token(None,['admin'])
  self.config=Config(state=self.tmp.name,public_url='https://mail.example.test')
  def permit(a,scope):
   if scope not in a['scopes']:raise Problem(403,'scope_denied')
  administrators.install(self.store,administrators.credentials('admin','test-password-long'))
  self.app=App(SimpleNamespace(store=self.store,config=self.config,permit=permit))
 def call(self,method='GET',cookie='',bearer='',origin=None,data=None):
  e={'REQUEST_METHOD':method,'PATH_INFO':'/v1/session','wsgi.input':io.BytesIO(b''),'HTTP_COOKIE':cookie}
  if data is not None:
   body=json.dumps(data).encode();e['wsgi.input']=io.BytesIO(body);e['CONTENT_LENGTH']=str(len(body))
  if bearer:e['HTTP_AUTHORIZATION']='Bearer '+bearer
  if origin:e['HTTP_ORIGIN']=origin
  out=[];body=b''.join(self.app(e,lambda s,h:out.append((s,h))))
  return out[0][0],dict(out[0][1]),json.loads(body)
 def login(self):
  status,h,d=self.call('POST',data={'username':'admin','password':'test-password-long'},origin=self.config.public_url)
  self.assertEqual(status,'200 OK');self.assertNotIn(self.token['token'],json.dumps(d))
  for value in ('HttpOnly','Secure','SameSite=Strict'):self.assertIn(value,h['Set-Cookie'])
  return h['Set-Cookie'].split(';')[0]
 def test_refresh_reconstruction_logout(self):
  c=self.login();self.assertEqual(self.call(cookie=c)[0],'200 OK')
  self.app.s.store=Store(self.tmp.name)
  self.assertEqual(self.call(cookie=c)[0],'200 OK')
  self.assertEqual(self.call('DELETE',cookie=c,origin=self.config.public_url)[0],'200 OK')
  self.assertEqual(self.call(cookie=c)[0],'401 Unauthorized')
 def test_csrf_and_expiry(self):
  self.assertEqual(self.call('POST',bearer=self.token['token'],origin='https://evil.test')[0],'403 Forbidden')
  c=self.login()
  self.assertEqual(self.call('DELETE',cookie=c,origin='https://evil.test')[0],'403 Forbidden')
  self.assertEqual(self.call('DELETE',cookie=c)[0],'403 Forbidden')
  with patch('hermesaki.sessions.time.time',return_value=10**12):self.assertEqual(self.call(cookie=c)[0],'401 Unauthorized')
 def test_password_reset_revokes_sessions(self):
  c=self.login()
  with self.store.db() as db:
   rows=db.execute("SELECT value FROM meta WHERE key LIKE 'session:%'").fetchall()
   self.assertNotIn(self.token['token'],str([r[0] for r in rows]))
  administrators.install(self.store,administrators.credentials('admin','replacement-password'))
  self.assertEqual(self.call(cookie=c)[0],'401 Unauthorized')
 def test_mailbox_token_cannot_create_operator_session(self):
  with patch.object(self.store,'auth',return_value={'scopes':['mail.read']}):
   with self.assertRaises(Problem):sessions.issue(self.store,'mail-token')

 def test_dashboard_deep_routes_serve_shell(self):
  for path in ['/docs/connect-with-mcp','/docs/api-reference','/settings/dns','/settings/network']:
   with self.subTest(path=path):
    out=[]
    body=b''.join(self.app({'REQUEST_METHOD':'GET','PATH_INFO':path,'wsgi.input':io.BytesIO(b'')},lambda status,headers:out.append(status)))
    self.assertEqual(out[0],'200 OK')
    self.assertIn(b'id="sidebar"',body)

 def test_landing_and_setup_guide_routes(self):
  for path,title in [('/welcome',b'A real inbox.'),('/welcome/setup',b'Make room for'),('/welcome/api/connect-with-mcp',b'API documentation')]:
   with self.subTest(path=path):
    out=[]
    body=b''.join(self.app({'REQUEST_METHOD':'GET','PATH_INFO':path,'wsgi.input':io.BytesIO(b'')},lambda status,headers:out.append(status)))
    self.assertEqual(out[0],'200 OK')
    self.assertIn(title,body)
