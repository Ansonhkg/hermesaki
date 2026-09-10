"""Installation-bound external delivery check using a received original and reply.

The owner supplies the original downloaded from the receiving provider. Its
Authentication-Results are that provider's report, not independent attestation.
Raw message contents are not persisted by setup.
"""
import email.policy
import email.parser
import email.utils
import json
import re
import time


def validate_recipient(plan, recipient):
    if not isinstance(recipient,str) or not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+',recipient):
        raise ValueError('external_recipient_required')
    if recipient.rsplit('@',1)[1].lower()==plan['first_mailbox'].rsplit('@',1)[1].lower():
        raise ValueError('use_a_mailbox_on_an_external_domain')


def start(runtime, plan, recipient, key):
    validate_recipient(plan, recipient)
    script='''import json
from hermesaki.http import create_app
app=create_app();s=app.s.store
with s.db() as db:inbox=db.execute('SELECT id FROM inboxes WHERE email=? AND active=1',(ADDRESS,)).fetchone()['id']
t=s.token(inbox,['mail.write'],ttl=120)
try:
 job=app.s.send(s.auth(t['token']),inbox,{'to':[RECIPIENT],'subject':SUBJECT,'body_text':'Reply to this message to verify incoming mail. Then download the original of this message from your external inbox and upload it in Hermesaki setup.'},KEY)
 print(json.dumps(job))
finally:
 with s.db() as db:db.execute('UPDATE tokens SET revoked=1 WHERE id=?',(t['id'],))
'''
    subject='Hermesaki setup verification '+key
    values={'ADDRESS':plan['first_mailbox'],'RECIPIENT':recipient,'SUBJECT':subject,'KEY':'setup-mail-'+key}
    script=re.sub(r'\b(ADDRESS|RECIPIENT|SUBJECT|KEY)\b',lambda m:repr(values[m[0]]),script)
    job=json.loads(runtime.dc('exec','-T','api','python','-',stdin=script))
    return {'plan_id':plan['id'],'recipient':recipient,'sender':plan['first_mailbox'],
            'subject':subject,'message_id':job['message_id'],'job_id':job['id'],'started_at':int(time.time())}


def receipt_results(session, original):
    if not isinstance(original,str) or len(original.encode())>12000:
        raise ValueError('original_message_must_be_under_12_kb')
    msg=email.parser.Parser(policy=email.policy.default).parsestr(original)
    if str(msg.get('Message-ID','')).strip()!=session['message_id']:
        raise ValueError('original_does_not_match_test_message')
    if email.utils.parseaddr(msg.get('From',''))[1].lower()!=session['sender'].lower():
        raise ValueError('original_sender_mismatch')
    if session['recipient'].lower() not in {a.lower() for _,a in email.utils.getaddresses(msg.get_all('To',[]))}:
        raise ValueError('original_recipient_mismatch')
    if str(msg.get('Subject',''))!=session['subject']:
        raise ValueError('original_subject_mismatch')
    reports=msg.get_all('Authentication-Results',[])
    # One provider report must contain all three outcomes. Never combine partial
    # results from unrelated hops, ARC text, or the message body.
    passed=any(all(re.search(r'(?:^|;)\s*'+name+r'=pass(?:\s|;|$)',str(report),re.I) for name in ('spf','dkim','dmarc')) for report in reports)
    return {'provider_report_passed':passed}


def verify(runtime, session, original):
    if not 0<=time.time()-session['started_at']<86400:
        raise ValueError('external_mail_test_expired')
    observed=receipt_results(session,original)
    script='''import json,email.utils
from hermesaki.http import create_app
app=create_app();s=app.s.store
with s.db() as db:
 inbox=db.execute('SELECT id FROM inboxes WHERE email=? AND active=1',(ADDRESS,)).fetchone()['id']
 job=db.execute('SELECT state FROM jobs WHERE id=?',(JOB,)).fetchone()
found=False
for summary in app.s.mail.messages(s.inbox(inbox),query=SUBJECT,limit=50):
 if email.utils.parseaddr(summary['from'])[1].lower()!=RECIPIENT.lower():continue
 message=app.s.mail.message(s.inbox(inbox),summary['uid'])
 if MESSAGE_ID in message.get('references','').split():found=True;break
print(json.dumps({'reply_received':found,'outbound_submitted':bool(job and job['state']=='submitted')}))
'''
    values={'ADDRESS':session['sender'],'JOB':session['job_id'],'SUBJECT':session['subject'],'RECIPIENT':session['recipient'],'MESSAGE_ID':session['message_id']}
    script=re.sub(r'\b(ADDRESS|JOB|SUBJECT|RECIPIENT|MESSAGE_ID)\b',lambda m:repr(values[m[0]]),script)
    observed.update(json.loads(runtime.dc('exec','-T','api','python','-',stdin=script)))
    good=all(observed.get(k) is True for k in ('provider_report_passed','reply_received','outbound_submitted'))
    return {'id':'external_mail','state':'passed' if good else 'pending','plan_id':session['plan_id'],
            'checked_at':int(time.time()),'observed':observed,
            'detail':'External original reports SPF/DKIM/DMARC pass; submitted test and matching reply verified.' if good else
            'Awaiting a matching reply, submitted delivery and an external original reporting SPF, DKIM and DMARC pass.'}
