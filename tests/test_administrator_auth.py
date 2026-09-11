import io,json,time
from types import SimpleNamespace
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from tests.test_sessions import SessionTests
from hermesaki import administrators,sessions
from hermesaki.store import Problem

class AdministratorAuthTests(SessionTests):
 def test_invalid_password_and_throttle(self):
  for _ in range(10):
   self.assertEqual(self.call('POST',origin=self.config.public_url,data={'username':'admin','password':'wrong'})[0],'401 Unauthorized')
  self.assertEqual(self.call('POST',origin=self.config.public_url,data={'username':'admin','password':'test-password-long'})[0],'429 Too Many Requests')
 def test_old_operator_key_is_rejected(self):
  self.assertEqual(self.call(bearer=self.token['token'])[0],'401 Unauthorized')
  self.assertEqual(self.call('POST',bearer=self.token['token'],origin=self.config.public_url)[0],'400 Bad Request')
 def test_single_use_setup(self):
  with self.store.db() as db:db.execute("DELETE FROM meta WHERE key='administrator'")
  administrators.prepare_setup(self.store,self.tmp.name)
  from pathlib import Path
  code=Path(self.tmp.name,'administrator-setup-code').read_text()
  with self.assertRaises(Problem):administrators.setup(self.store,self.tmp.name,{'username':'owner','password':'a-long-password','setup_code':'wrong'})
  administrators.setup(self.store,self.tmp.name,{'username':'owner','password':'a-long-password','setup_code':code})
  self.assertFalse(Path(self.tmp.name,'administrator-setup-code').exists())
  with self.assertRaises(Problem):administrators.setup(self.store,self.tmp.name,{'username':'attacker','password':'a-long-password','setup_code':code})
  self.assertEqual(administrators.saved(self.store)['username'],'owner')
 def test_cloudflare_signed_identity_and_session_binding(self):
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  self.config.mode='production';self.config.access_team='team';self.config.access_aud='dashboard'
  self.config.admin_emails=['owner@example.test']
  self.app.jwks=SimpleNamespace(get_signing_key_from_jwt=lambda _:SimpleNamespace(key=key.public_key()))
  claims={'iss':'https://team.cloudflareaccess.com','aud':'dashboard','exp':time.time()+300,'sub':'owner-id','email':'owner@example.test'}
  def request(claims,cookie='',method='POST'):
   assertion=jwt.encode(claims,key,algorithm='RS256') if claims else ''
   e={'REQUEST_METHOD':method,'PATH_INFO':'/v1/session','HTTP_ORIGIN':self.config.public_url,'wsgi.input':io.BytesIO(b''),'HTTP_COOKIE':cookie,'HTTP_CF_ACCESS_JWT_ASSERTION':assertion}
   out=[];data=b''.join(self.app(e,lambda s,h:out.append((s,dict(h)))))
   return out[0],json.loads(data)
  for bad in [None,claims|{'exp':1},claims|{'aud':'another-app'},claims|{'iss':'https://evil.test'}, {k:v for k,v in claims.items() if k!='exp'}]:
   self.assertEqual(request(bad)[0][0],'401 Unauthorized')
  for bad in [claims|{'email':'stranger@example.test'},claims|{'email':''},claims|{'sub':''}]:
   self.assertEqual(request(bad)[0][0],'403 Forbidden')
  with patch.object(self.app.jwks,'get_signing_key_from_jwt',return_value=SimpleNamespace(key=rsa.generate_private_key(public_exponent=65537,key_size=2048).public_key())):
   self.assertEqual(request(claims)[0][0],'401 Unauthorized')
  response,data=request(claims);self.assertEqual(response[0],'200 OK')
  cookie=response[1]['Set-Cookie'].split(';')[0]
  self.assertEqual(request(claims,cookie,'GET')[0][0],'200 OK')
  self.assertEqual(request(claims|{'sub':'different-id'},cookie,'GET')[0][0],'401 Unauthorized')
  self.config.admin_emails=[]
  self.assertEqual(request(claims,cookie,'GET')[0][0],'403 Forbidden')

 def test_mailbox_bearer_still_works(self):
  token=self.store.token(None,['mail.read'])['token']
  environ={'REQUEST_METHOD':'GET','PATH_INFO':'/v1/example','wsgi.input':io.BytesIO(b''),'HTTP_AUTHORIZATION':'Bearer '+token}
  result=[]
  with patch.object(self.app,'route',side_effect=lambda actor,*_: {'scopes':actor['scopes']}):
   body=b''.join(self.app(environ,lambda s,h:result.append(s)))
  self.assertEqual(result,['200 OK']);self.assertEqual(json.loads(body)['scopes'],['mail.read'])
