const $ = s => document.querySelector(s);
let token = '', claimed = false, providerPlan = null;
async function request(path, method='GET', data, credential=token) {
  const response = await fetch(path, {method, headers:{'Content-Type':'application/json', ...(credential ? {Authorization:'Bearer '+credential}: {})}, body:data ? JSON.stringify(data):undefined});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error.replaceAll('_',' '));
  return result;
}
function render(state) {
  $('#configuration').hidden=false;
  $('#cloudflare').hidden=!state.settings;
  renderProvider(state.cloudflare_plan);
  if(state.provisioning){$('#apply-state').textContent=state.provisioning.state.replaceAll('_',' ')+(state.provisioning.inflight?' · An operation may be incomplete. Review before retrying.':'');}
  if(state.settings) for(const [key,value] of Object.entries(state.settings)) $('#settings').elements[key].value=value;
  $('#review').hidden=!state.settings;
  $('#plan').replaceChildren();
  for (const [key,value] of Object.entries(state.plan || {}).filter(([key])=>['mail_hostname','webmail_hostname','operator_hostname'].includes(key))) {const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key.replaceAll('_',' ');dd.textContent=String(value);$('#plan').append(dt,dd);}
  renderHost(state.host_preflight);
  $('#checks').replaceChildren(...state.checks.map(check=>{const li=document.createElement('li');li.textContent=check.id.replaceAll('_',' ')+' · '+check.state+(check.detail?' ('+check.detail+')':'');return li;}));
}
async function busy(form, action) {const button=form.querySelector('[type=submit]');button.disabled=true;$('#feedback').textContent='';try{await action();}catch(error){$('#feedback').textContent=error.message;}finally{button.disabled=false;}}
$('#generate').onclick=()=>{const bytes=crypto.getRandomValues(new Uint8Array(32));const value=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');$('#new-owner').value=value;const url=URL.createObjectURL(new Blob([value],{type:'text/plain'}));const link=document.createElement('a');link.href=url;link.download='hermesaki-owner-token.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('#feedback').textContent='Keep the downloaded owner credential private. You will need it to reconnect.';};
$('#claim').onsubmit=event=>{event.preventDefault();busy(event.target,async()=>{const credential=$('#credential').value.trim();if(!claimed){const owner=$('#new-owner').value.trim();await request('/v1/setup/claim','POST',{owner_token:owner},credential);token=owner;claimed=true;}else token=credential;render(await request('/v1/setup'));$('#credential').value='';$('#new-owner').value='';$('#access').hidden=true;});};
$('#settings').onsubmit=event=>{event.preventDefault();busy(event.target,async()=>{render(await request('/v1/setup/configuration','PUT',Object.fromEntries(new FormData(event.target))));$('#feedback').textContent='Configuration saved. Verification and deployment remain pending.';});};
request('/v1/setup/status').then(state=>{claimed=state.claimed;$('#new-owner-label').hidden=claimed;$('#generate').hidden=claimed;$('#access-help').textContent=claimed?'This installation has an owner. Enter your saved owner credential.':'Read the bootstrap-token file on your server, then generate and save a new owner credential.';}).catch(error=>$('#feedback').textContent=error.message);

function renderProvider(plan) {
  providerPlan=plan;
  $('#provider-review').hidden=!plan;
  if(!plan)return;
  $('#apply-plan').hidden=!plan.apply_available;
  $('#confirm-plan').checked=false;
  $('#provider-state').textContent='Read access checked. Write access and deployment remain unverified.';
  const list=(selector,items)=>$(selector).replaceChildren(...items.map(text=>{const li=document.createElement('li');li.textContent=text;return li;}));
  list('#provider-conflicts',plan.conflicts);
  list('#provider-actions',plan.actions.map(a=>a.operation+' '+a.kind+': '+(a.hostname||a.name)));
}
$('#provider').onsubmit=event=>{event.preventDefault();busy(event.target,async()=>{try{const result=await request('/v1/setup/cloudflare','PUT',{token:$('#provider-token').value.trim()});renderProvider(result.plan);$('#feedback').textContent='Cloudflare read checks passed. Plan prepared; no infrastructure changed.';}finally{$('#provider-token').value='';}});};

$('#apply-plan').onsubmit=event=>{event.preventDefault();busy(event.target,async()=>{if(!providerPlan || !$('#confirm-plan').checked)throw new Error('Confirm the exact plan first.');const result=await request('/v1/setup/apply','POST',{confirm_plan_id:providerPlan.id});$('#apply-state').textContent='Web protection resources applied. Private service deployment and live verification are still required.';render(await request('/v1/setup'));});};

function renderHost(result){
 $('#host-checks').replaceChildren(...(result?.checks||[]).map(check=>{const li=document.createElement('li');li.textContent=check.id.replaceAll('_',' ')+' · '+check.state+': '+check.detail+(check.state!=='passed'&&check.remedy?' '+check.remedy:'');return li;}));
}
$('#preflight').onsubmit=event=>{event.preventDefault();busy(event.target,async()=>{renderHost(await request('/v1/setup/preflight','POST',{}));});};
