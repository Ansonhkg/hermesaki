from tests.test_sessions import SessionTests
from hermesaki.mcp_connection import handle,KEY
from hermesaki.store import Problem
class McpConnectionTests(SessionTests):
 def test_gate_credentials_are_operator_only_encrypted_and_redacted(self):
  actor={'id':'owner','scopes':['admin']};data={'client_id':'fictional-id','client_secret':'fictional-secret'}
  for scopes in (['mail.read'],['mail.read','mail.write']):
   for method,action in [('GET',''),('POST','save'),('POST','reveal')]:
    with self.assertRaises(Problem):handle(self.store,self.config,{'id':'agent','scopes':scopes},method,action,data)
  handle(self.store,self.config,actor,'POST','save',data)
  self.assertNotIn('client_secret',handle(self.store,self.config,actor,'GET','',{}))
  self.assertEqual(handle(self.store,self.config,actor,'POST','reveal',{}),data)
  with self.store.db() as db:
   self.assertNotIn('fictional-secret',db.execute('SELECT value FROM meta WHERE key=?',(KEY,)).fetchone()[0])
   self.assertNotIn('fictional-secret',str([dict(r) for r in db.execute('SELECT * FROM audit')]))
