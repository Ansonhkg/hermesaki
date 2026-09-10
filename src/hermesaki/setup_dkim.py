"""Export only the public DNS portion of Stalwart's generated signing keys."""
import base64
import json
import re
from cryptography.hazmat.primitives import serialization
from .http import create_app


def public_records(api, domain):
    domains=[d for d in api.list('Domain') if d.get('name')==domain]
    if len(domains)!=1:raise ValueError('domain_not_found')
    rows=[]
    for key in api.list('DkimSignature'):
        if key.get('domainId')!=domains[0]['id'] or key.get('stage') not in ('active','retiring'):continue
        kind=key.get('@type')
        if kind not in ('Dkim1RsaSha256','Dkim1Ed25519Sha256'):continue
        selector=key['selector']
        if not re.fullmatch(r'[A-Za-z0-9_-]+',selector):raise ValueError('invalid_selector')
        value=key['publicKey']
        if value.startswith('-----BEGIN'):
            public=serialization.load_pem_public_key(value.encode())
            raw=public.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo) if kind=='Dkim1RsaSha256' else public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        else:
            # Pinned 0.16.19 returns DNS-ready base64 despite the reference's PEM label.
            raw=base64.b64decode(value,validate=True)
        algorithm='rsa' if kind=='Dkim1RsaSha256' else 'ed25519'
        if algorithm=='rsa':serialization.load_der_public_key(raw)
        elif len(raw)!=32:raise ValueError('invalid_ed25519_public_key')
        rows.append({'type':'TXT','name':selector+'._domainkey.'+domain,'content':'v=DKIM1; k='+algorithm+'; p='+base64.b64encode(raw).decode(),'ttl':300})
    if not rows:raise ValueError('no_active_dkim_keys')
    return sorted(rows,key=lambda r:r['name'])

if __name__=='__main__':
    app=create_app()
    print(json.dumps(public_records(app.s.provision,app.c.domain)))
