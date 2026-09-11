"""Operator-visible installation inventory and reviewed presentation settings."""
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit
from .store import Problem


def read(config):
    root = Path(config.state)
    link = config.webmail_url
    try:
        link = json.loads((root / 'operator-settings.json').read_text())['webmail_url']
    except FileNotFoundError:
        pass
    inventory = None
    try:
        inventory = json.loads((root / 'installation-inventory.json').read_text())
    except FileNotFoundError:
        pass
    try:
        current = json.loads((root / 'live-infrastructure-inventory.json').read_text())
        inventory = {**(inventory or {}), **current}
    except FileNotFoundError:
        pass
    return {'domain': config.domain, 'mode': config.mode,
            'operator_url': config.public_url, 'webmail_url': link,
            'mail_host': config.mail_host, 'imap_port': config.mail_port,
            'smtp_port': config.smtp_port, 'cloudflare_access_team': config.access_team,
            'cloudflare_identity_verification': bool(config.access_team and config.access_aud),
            'webhook_hosts': config.webhook_hosts, 'delivery_attempt_limit': config.max_attempts,
            'message_size_limit_bytes': config.max_message_bytes,
            'infrastructure': inventory,
            'infrastructure_edit_policy': 'Existing mail DNS, Tunnel origins and Access policy additions use reviewed Cloudflare plans. Domain replacement and resource deletion require a separate migration.'}


def plan(store, config, data):
    if set(data) != {'webmail_url'} or not isinstance(data['webmail_url'], str):
        raise Problem(400, 'invalid_configuration')
    url = urlsplit(data['webmail_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise Problem(400, 'https_webmail_url_required')
    current = read(config)['webmail_url']
    result = {'id': secrets.token_hex(16), 'before': current, 'after': data['webmail_url'],
              'expires': time.time() + 600, 'effect': 'Changes the Open webmail link. Does not move mail or change DNS.'}
    with store.db() as db:
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('operator_configuration_plan', json.dumps(result)))
    return result


def apply(store, config, data):
    with store.db() as db:
        row = db.execute('SELECT value FROM meta WHERE key=?', ('operator_configuration_plan',)).fetchone()
        if not row:
            raise Problem(409, 'plan_required')
        p = json.loads(row[0])
        if data.get('confirm_plan_id') != p['id'] or time.time() > p['expires']:
            raise Problem(409, 'plan_expired_or_mismatched')
        if read(config)['webmail_url'] != p['before']:
            raise Problem(409, 'configuration_changed_review_again')
        target = Path(config.state) / 'operator-settings.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'webmail_url': p['after']}))
        temporary.chmod(0o600)
        temporary.replace(target)
        db.execute('DELETE FROM meta WHERE key=?', ('operator_configuration_plan',))
    return {'applied': True, 'webmail_url': p['after']}
