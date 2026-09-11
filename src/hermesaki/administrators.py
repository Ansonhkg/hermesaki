"""Local administrator credentials and explicit Cloudflare identity authorization."""
import argparse
import getpass
import hashlib
import hmac
import json
import re
import secrets
import time
from pathlib import Path
from .store import Store, Problem

KEY = 'administrator'

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def credentials(username, password):
    if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{3,128}',username):
        raise Problem(400,'invalid_username')
    if not isinstance(password,str) or not 12 <= len(password) <= 256:
        raise Problem(400,'password_requires_12_to_256_characters')
    salt=secrets.token_hex(16)
    return {'username':username,'salt':salt,'hash':password_hash(password,salt),'revision':secrets.token_hex(16)}

def saved(store):
    with store.db() as db:
        row=db.execute('SELECT value FROM meta WHERE key=?',(KEY,)).fetchone()
    return json.loads(row[0]) if row else None

def install(store, record):
    with store.db() as db:
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(KEY,json.dumps(record)))
        db.execute("DELETE FROM meta WHERE key LIKE 'session:%'")

def login(store, username, password):
    # Persist an installation-wide limit so restart and guessed usernames cannot bypass it.
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT value FROM meta WHERE key='login-attempts'").fetchone()
        attempts=json.loads(row[0]) if row else []
        attempts=[t for t in attempts if t>time.time()-300]
        if len(attempts)>=10:raise Problem(429,'try_again_in_five_minutes')
        attempts.append(time.time())
        db.execute("INSERT OR REPLACE INTO meta VALUES('login-attempts',?)",(json.dumps(attempts),))
    record=saved(store)
    if not isinstance(password,str) or len(password)>256:raise Problem(401,'invalid_credentials')
    expected=record or {'username':'','salt':'00'*16,'hash':'00'*64}
    valid=hmac.compare_digest(password_hash(password,expected['salt']),expected['hash'])
    if not record or not valid or username!=record['username']:raise Problem(401,'invalid_credentials')
    with store.db() as db:db.execute("DELETE FROM meta WHERE key='login-attempts'")
    return {'id':'administrator:'+record['username'],'scopes':['admin'],'revision':record['revision'],'provider':'password'}

def cloudflare(config, claims):
    email=claims.get('email','')
    allowed=[v.casefold() for v in config.admin_emails]
    if not isinstance(email,str) or not email or email.casefold() not in allowed or not claims.get('sub'):
        raise Problem(403,'administrator_identity_required')
    return {'id':'cloudflare:'+claims['sub'],'email':email.casefold(),'scopes':['admin'],'provider':'cloudflare'}

def main():
    parser=argparse.ArgumentParser(description='Create/reset the local administrator; invalidates browser sessions.')
    parser.add_argument('--state',required=True)
    parser.add_argument('--username',required=True)
    parser.add_argument('--setup',action='store_true',help='Reset the private installation wizard account instead of the dashboard account')
    args=parser.parse_args()
    password=getpass.getpass('New administrator password (at least 12 characters): ')
    if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match')
    record=credentials(args.username,password)
    if args.setup:
        from .setup import Setup
        setup=Setup(args.state)
        with setup.connect() as db:
            db.execute('INSERT OR REPLACE INTO administrator VALUES(1,?,NULL,0)',(json.dumps(record),))
            db.execute("UPDATE state SET owner='password',bootstrap='' WHERE id=1")
            db.execute('DELETE FROM login_attempts')
        (Path(args.state)/'bootstrap-token').unlink(missing_ok=True)
    else:
        install(Store(args.state),record)
    print('Administrator saved. Previous browser sessions are signed out.')


def prepare_setup(store, state):
    if saved(store):return
    path=Path(state)/'administrator-setup-code'
    try:
        with path.open('x') as f:
            path.chmod(0o600)
            f.write(secrets.token_urlsafe(32))
    except FileExistsError:pass

def setup(store,state,data):
    record=credentials(data.get('username'),data.get('password'))
    path=Path(state)/'administrator-setup-code'
    code=data.get('setup_code','')
    if not isinstance(code,str) or not path.exists() or not hmac.compare_digest(path.read_text().strip(),code):
        raise Problem(401,'invalid_setup_code')
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM meta WHERE key=?',(KEY,)).fetchone():raise Problem(409,'administrator_already_configured')
        db.execute('INSERT INTO meta VALUES(?,?)',(KEY,json.dumps(record)))
    path.unlink(missing_ok=True)


if __name__=='__main__':main()
