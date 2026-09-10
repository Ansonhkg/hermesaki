"""Public DNS observations for the planned mail records, using the host resolver."""
import json
import shlex
import subprocess
from .setup_services import records_for


def lookup(name, record_type):
    result = subprocess.run(['dig', '+short', '+time=3', '+tries=1', name, record_type],
                            capture_output=True, text=True, timeout=5, check=True)
    values = []
    for line in result.stdout.splitlines():
        if not line.strip():continue
        if record_type == 'TXT':
            values.append(''.join(shlex.split(line)))
        else:values.append(line.strip().rstrip('.').lower())
    return values


def public_dns(settings):
    observations = []
    try:
        for record in records_for(settings):
            observed = lookup(record['name'], record['type'])
            expected = record['content']
            if record['type'] == 'MX':expected = str(record['priority']) + ' ' + expected.rstrip('.').lower()
            observations.append({'type':record['type'], 'name':record['name'],
                                 'passed':expected in observed})
    except (OSError, subprocess.SubprocessError, ValueError):
        return {'id':'public_mail_dns','state':'pending','detail':'Public DNS lookup failed. Install dig or restore DNS resolution, then retry.'}
    return {'id':'public_mail_dns','state':'passed' if all(x['passed'] for x in observations) else 'pending',
            'detail':'Planned A/AAAA, MX, SPF and DMARC records checked through the host DNS resolver.',
            'observations':observations}
