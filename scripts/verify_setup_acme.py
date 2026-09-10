"""Explicit real ACME check on an isolated authorized subdomain. No email is sent."""
import argparse
import os
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hermesaki.setup_services import Services, private_write
from hermesaki.setup_runtime import Runtime
from hermesaki.setup_cloudflare import Cloudflare

parser=argparse.ArgumentParser()
parser.add_argument('--domain',required=True)
parser.add_argument('--email',required=True)
parser.add_argument('--state',required=True)
parser.add_argument('--confirm-isolated-domain',required=True)
parser.add_argument('--accept-acme-terms',action='store_true')
args=parser.parse_args()
if args.domain!=args.confirm_isolated_domain or not args.accept_acme_terms:
    parser.error('Confirm the isolated domain and ACME subscriber agreement first.')
if not re.fullmatch(r'[a-z0-9.-]+',args.domain) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',args.email):
    parser.error('Invalid domain or contact email.')
provider=Cloudflare(os.environ['HERMESAKI_SETUP'])
zone=None
labels=args.domain.split('.')
for index in range(len(labels)-1):
    rows=provider.all('/zones',{'name':'.'.join(labels[index:])})
    if rows:zone=rows[0];break
if not zone or zone['name']==args.domain or zone.get('status')!='active':
    parser.error('Use an isolated subdomain of an active authorized zone, not its apex.')
services=Services(args.state);runtime=Runtime(services);root=runtime.root
(root/'product/tls').mkdir(parents=True,exist_ok=True,mode=0o700)
(root/'acme').mkdir(exist_ok=True,mode=0o700)
private_write(root/'certbot-secret/cloudflare.ini','dns_cloudflare_api_token = '+provider.token+'\n')
print('Real DNS-01 issuance for mail.'+args.domain,flush=True)
runtime.certificate({'domain':args.domain,'owner_email':args.email})
print('PASS public certificate issued and saved privately.',flush=True)
runtime.run(['docker','run','--rm','-v',str(root/'acme')+':/etc/letsencrypt','-v',str(root/'certbot-secret')+':/run/hermesaki-certbot:ro',runtime.lock['certbot']['image'],
             'renew','--dry-run','--non-interactive','--no-random-sleep-on-renew'])
print('PASS renewal dry-run against staging authority. Production certificate retained.',flush=True)
