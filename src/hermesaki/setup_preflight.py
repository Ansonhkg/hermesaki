"""Read-only checks on the installation host. Never infer external reachability."""
import ipaddress
import platform
import shutil
import socket
import subprocess


def host_checks(settings):
    checks=[]
    def add(name,state,detail,remedy=None):
        checks.append({'id':name,'state':state,'detail':detail,**({'remedy':remedy} if remedy else {})})
    add('supported_host','passed' if platform.system()=='Linux' else 'blocked',platform.system(),'Production deployment requires a Linux Docker host.')
    try:
        result=subprocess.run(['docker','info','--format','{{.ServerVersion}}'],capture_output=True,timeout=10,check=True)
        add('docker','passed','Docker daemon is reachable.')
        subprocess.run(['docker','compose','version'],capture_output=True,timeout=10,check=True)
        add('compose','passed','Docker Compose is available.')
    except (OSError,subprocess.SubprocessError):
        add('docker','blocked','Docker or Compose is unavailable.','Install Docker with Compose and give the setup process access to its daemon.')
    address=ipaddress.ip_address(settings['server_ip'])
    add('public_ip','passed' if address.is_global else 'blocked','Configured address is globally routable.' if address.is_global else 'Configured address is not globally routable.','Use the public IP assigned to this server.')
    family=socket.AF_INET6 if address.version==6 else socket.AF_INET
    try:
        with socket.socket(family,socket.SOCK_STREAM) as listener:
            listener.bind((str(address),25))
        add('smtp_bind','passed','Configured IP and SMTP port 25 are available on this host.')
    except OSError:
        add('smtp_bind','blocked','Cannot bind SMTP port 25 on the configured IP.','Check IP assignment, permissions and existing mail services. Do not stop an existing inbox to proceed.')
    try:
        with socket.create_connection(('gmail-smtp-in.l.google.com',25),timeout=5):
            pass
        add('smtp_outbound','passed','TCP connection to an external MX on port 25 succeeded. No email was sent.')
    except OSError:
        add('smtp_outbound','blocked','External SMTP connection failed.','Check provider port-25 restrictions, routing and outbound firewall rules.')
    expected='mail.'+settings['domain']
    if shutil.which('dig'):
        try:
            result=subprocess.run(['dig','+short','+time=3','+tries=1','-x',str(address)],capture_output=True,text=True,timeout=5,check=True)
            names=[n.strip().rstrip('.').lower() for n in result.stdout.splitlines()]
            add('reverse_dns','passed' if expected in names else 'blocked','PTR matches the planned mail hostname.' if expected in names else 'PTR does not match the planned mail hostname.','Set reverse DNS to '+expected+' with your server provider.')
        except (OSError,subprocess.SubprocessError):
            add('reverse_dns','pending','Reverse DNS lookup unavailable.','Retry after restoring DNS resolution.')
    else:
        add('reverse_dns','pending','DNS lookup utility is missing.','Install dig to verify the provider PTR record.')
    add('smtp_inbound','pending','External inbound SMTP has not been checked.','After deployment, connect from a separate host to verify public SMTP and firewall reachability.')
    return {'checks':checks,'ready':all(c['state']=='passed' for c in checks),'complete':False}
