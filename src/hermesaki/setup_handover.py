"""Fail-closed handover of a verified installation to its normal operator UI."""
import time
from .setup_cloudflare import web_hosts

REQUIRED = frozenset(('mailbox', 'webmail', 'tls', 'anonymous_access', 'origin_ports',
                      'dkim', 'renewal', 'public_mail_dns', 'external_mail',
                      'authenticated_agent', 'provider_network'))


def handover(verification, settings, plan_id, now=None):
    now = int(time.time()) if now is None else now
    if not isinstance(verification, dict):
        raise ValueError('verification_required')
    checks = verification.get('checks', [])
    ids = [c.get('id') for c in checks]
    if len(ids) != len(set(ids)) or set(ids) != REQUIRED:
        raise ValueError('complete_verification_required')
    if any(c.get('state') != 'passed' for c in checks):
        raise ValueError('resolve_failed_or_pending_checks')
    age = now - verification.get('checked_at', 0)
    if age < 0 or age > 300:
        raise ValueError('verification_expired_run_checks_again')
    operator, inbox = web_hosts(settings)
    return {'state': 'complete', 'complete': True, 'completed_at': now,
            'plan_id': plan_id, 'operator_url': 'https://' + operator,
            'webmail_url': 'https://' + inbox, 'mcp_url': 'https://' + operator + '/mcp',
            'next_action': 'open_operator', 'setup_mutations_retired': True,
            'authentication': 'Sign in through Cloudflare Access as the configured owner. Agents use scoped mailbox keys.'}
