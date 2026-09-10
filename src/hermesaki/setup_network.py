"""External SMTP probe with a short-lived, installation-bound challenge.

The owner runs the probe on another host. It records observed values, not a
caller-selected pass flag. Its result must be signed with the one-use probe key.
"""
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def issue(settings, plan_id):
    return {'id':secrets.token_hex(16),'key':secrets.token_hex(32),
            'server_ip':settings['server_ip'],'mail_hostname':'mail.'+settings['domain'],
            'plan_id':plan_id,'expires_at':int(time.time())+900}


def probe(challenge):
    target=challenge['server_ip']
    if not ipaddress.ip_address(target).is_global:
        raise ValueError('probe_requires_public_target')
    observed={'challenge_id':challenge['id'],'plan_id':challenge['plan_id'],
              'server_ip':target,'checked_at':int(time.time()),'source_ip':None,
              'smtp_banner':False,'ptr_matches':False,'forward_matches':False}
    try:
        with socket.create_connection((target,25),timeout=8) as connection:
            observed['source_ip']=connection.getsockname()[0]
            observed['smtp_banner']=connection.recv(1024).startswith(b'220 ')
            connection.sendall(b'QUIT\r\n')
        hostname=challenge['mail_hostname'].rstrip('.').lower()
        observed['ptr_matches']=socket.gethostbyaddr(target)[0].rstrip('.').lower()==hostname
        observed['forward_matches']=target in {r[4][0] for r in socket.getaddrinfo(hostname,25,type=socket.SOCK_STREAM)}
    except OSError:
        pass
    return {'observed':observed,'signature':hmac.new(bytes.fromhex(challenge['key']),canonical(observed),hashlib.sha256).hexdigest()}


def accept(challenge, receipt, plan_id, now=None):
    now=int(time.time()) if now is None else now
    if now>challenge['expires_at'] or challenge['plan_id']!=plan_id:
        raise ValueError('probe_expired_or_plan_changed')
    observed=receipt.get('observed',{})
    signature=hmac.new(bytes.fromhex(challenge['key']),canonical(observed),hashlib.sha256).hexdigest()
    if not isinstance(receipt.get('signature'),str) or not hmac.compare_digest(signature,receipt['signature']):
        raise ValueError('invalid_probe_signature')
    if (observed.get('challenge_id')!=challenge['id'] or observed.get('plan_id')!=plan_id
            or observed.get('server_ip')!=challenge['server_ip']):
        raise ValueError('probe_does_not_match_installation')
    stamp=observed.get('checked_at',0)
    if not isinstance(stamp,int) or not 0<=now-stamp<=900:
        raise ValueError('probe_observation_expired')
    try:
        source=ipaddress.ip_address(observed.get('source_ip',''))
        independent=source.is_global and str(source)!=challenge['server_ip']
    except ValueError:independent=False
    passed=independent and all(observed.get(k) is True for k in ('smtp_banner','ptr_matches','forward_matches'))
    return {'id':'provider_network','state':'passed' if passed else 'pending','checked_at':stamp,
            'plan_id':plan_id,'detail':'External SMTP banner, independent source address and forward/reverse DNS checked.',
            'observed':{k:observed.get(k) for k in ('source_ip','smtp_banner','ptr_matches','forward_matches')},
            'remedy':None if passed else 'Run the probe on a separate publicly addressed host and check SMTP firewall, PTR and forward DNS.'}


def main():
    import sys
    challenge=json.load(sys.stdin)
    print(json.dumps(probe(challenge)))


if __name__=='__main__':main()
