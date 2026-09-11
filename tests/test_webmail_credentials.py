import io,json
from tests.test_sessions import SessionTests
class WebmailCredentialsTests(SessionTests):
 def test_only_operator_can_reveal_and_audit_has_no_password(self):
  password='test-mailbox-password'
  with self.store.db() as db:
   db.execute('INSERT INTO inboxes VALUES(?,?,?,1)',('box','agent@example.test',self.store.seal(password,'box')))
  def request(token):
   env={'REQUEST_METHOD':'GET','PATH_INFO':'/v1/inboxes/box/webmail-credentials','wsgi.input':io.BytesIO(b''),'HTTP_AUTHORIZATION':'Bearer '+token}
   response=[];data=b''.join(self.app(env,lambda s,h:response.append((s,dict(h)))))
   return response[0],json.loads(data)
  for scopes in (['mail.read'],['mail.read','mail.write']):
   response,data=request(self.store.token('box',scopes)['token']);self.assertTrue(response[0].startswith('403'));self.assertNotIn(password,json.dumps(data))
  response,data=request(self.token['token']);self.assertEqual(response[0],'200 OK');self.assertEqual(data['password'],password);self.assertEqual(response[1]['Cache-Control'],'no-store')
  with self.store.db() as db:
   records=str([dict(r) for r in db.execute('SELECT * FROM audit')]);self.assertIn('webmail.credentials.read',records);self.assertNotIn(password,records)
