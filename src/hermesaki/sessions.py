"""Revocable browser sessions. Only an opaque identifier leaves the server."""
import hashlib
import json
import secrets
import time
from http.cookies import SimpleCookie
from .store import Problem

COOKIE='hermesaki_session'
TTL=43200

def key(raw): return 'session:'+hashlib.sha256(raw.encode()).hexdigest()
def cookie_id(environ):
    c=SimpleCookie()
    try:c.load(environ.get('HTTP_COOKIE',''))
    except Exception:return ''
    return c[COOKIE].value if COOKIE in c else ''
def same_origin(config,environ):
    if environ.get('HTTP_ORIGIN')!=config.public_url.rstrip('/'):
        raise Problem(403,'same_origin_required')
def issue(store,token,old=''):
    actor=store.auth(token)
    if 'admin' not in actor['scopes']:raise Problem(403,'scope_denied')
    raw=secrets.token_urlsafe(32);k=key(raw);expires=time.time()+TTL
    value=json.dumps({'token':store.seal(token,k),'expires':expires})
    with store.db() as db:
        if old:db.execute('DELETE FROM meta WHERE key=?',(key(old),))
        db.execute('INSERT INTO meta VALUES(?,?)',(k,value))
        for row in db.execute("SELECT key,value FROM meta WHERE key LIKE 'session:%'").fetchall():
            if json.loads(row['value'])['expires']<time.time():db.execute('DELETE FROM meta WHERE key=?',(row['key'],))
    return raw,expires

def authenticate(store,raw):
    if not raw:raise Problem(401,'token_required')
    k=key(raw)
    with store.db() as db:r=db.execute('SELECT value FROM meta WHERE key=?',(k,)).fetchone()
    if not r:raise Problem(401,'invalid_token')
    value=json.loads(r[0])
    if value['expires']<=time.time():raise Problem(401,'invalid_token')
    return store.auth(store.open(value['token'],k))
def revoke(store,raw):
    with store.db() as db:db.execute('DELETE FROM meta WHERE key=?',(key(raw),))
def header(config,raw='',age=TTL):
    return ('Set-Cookie',f'{COOKIE}={raw}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}'+ ('; Secure' if config.public_url.startswith('https://') else ''))
