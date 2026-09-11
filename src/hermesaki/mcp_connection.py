"""Operator-only storage for the Access gate credentials used by MCP clients."""
import json
from .store import Problem
KEY = 'mcp_access_service_credentials'

def handle(store, config, actor, method, action, data):
    if 'admin' not in actor['scopes']:
        raise Problem(403, 'scope_denied')
    with store.db() as db:
        row = db.execute('SELECT value FROM meta WHERE key=?', (KEY,)).fetchone()
    if method == 'GET' and not action:
        return {'url': config.public_url.rstrip('/') + '/mcp', 'cloudflare_required': config.mode == 'production', 'configured': bool(row)}
    if method == 'POST' and action == 'save':
        values = {k: data.get(k) for k in ('client_id', 'client_secret')}
        if any(not isinstance(v,str) or not v.strip() or len(v)>4096 or '\n' in v or '\r' in v for v in values.values()):
            raise Problem(400, 'service_credentials_required')
        with store.db() as db:
            db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (KEY, store.seal(json.dumps(values), KEY)))
        store.audit(actor['id'], 'mcp.access_credentials.saved', 'mcp')
        return {'saved': True, 'verified': False}
    if method == 'POST' and action == 'reveal':
        if not row:
            raise Problem(409, 'service_credentials_not_configured')
        store.audit(actor['id'], 'mcp.access_credentials.read', 'mcp')
        return json.loads(store.open(row[0], KEY))
    raise Problem(404, 'not_found')
