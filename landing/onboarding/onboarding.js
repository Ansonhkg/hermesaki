const $ = s => document.querySelector(s);
let timer, edited = false;
const names = ['ready','empty','invalid','creating','taken','create-error','connect','connecting','connect-error','connected','waiting','timeout','received','complete'];
function fill() { $('#name').value = 'Atlas'; $('#address').value = 'atlas'; }
function render(state, updateUrl = true) {
  clearTimeout(timer);
  if (!names.includes(state)) state = 'ready';
  const stage = names.indexOf(state) < 6 ? 1 : names.indexOf(state) < 9 ? 2 : 3;
  for (let n = 1; n <= 3; n++) $('#step'+n).hidden = stage !== n;
  document.querySelectorAll('.progress li').forEach((el,i) => {el.removeAttribute('aria-current');if (i===stage-1) el.setAttribute('aria-current','step');});
  $('#preview-state').value = state;
  if (updateUrl) history.replaceState(null,'','?state='+state);
  const name = $('#name').value.trim() || 'Atlas';
  const email = ($('#address').value || 'atlas')+'@agents.example.com';
  $('#created-email').textContent = $('#test-email').textContent = email;
  $('#agent-name').textContent = name;
  $('#permission').textContent = $('input[name=access]:checked').value === 'read' ? 'Read only' : 'Read and send';
  $('#config').value = JSON.stringify({url:'https://mail.example.com/mcp',headers:{Authorization:'Bearer DEMO_ONLY_NOT_A_REAL_TOKEN'}},null,2);
  $('#copy-status').textContent = 'Mock credentials. No live account is connected.';
  const busy = ['creating','connecting','waiting'].includes(state);
  $('.wizard').setAttribute('aria-busy',String(busy));
  document.querySelectorAll('#inbox-form input, #inbox-form button').forEach(el=>el.disabled=state==='creating');
  $('#inbox-form button').textContent = state==='creating' ? 'Creating inbox…' : 'Create inbox →';
  $('#next').disabled = state==='connecting';
  $('#next').textContent = state==='connecting' ? 'Checking connection…' : state==='connect-error' ? 'Retry connection →' : 'Check connection →';
  $('#simulate').hidden = ['received','complete'].includes(state);
  $('#simulate').disabled = state==='waiting';
  $('#simulate').textContent = state==='waiting' ? 'Waiting for your message…' : state==='timeout' ? 'Try again →' : 'Send sample message →';
  $('#success').hidden = !['received','complete'].includes(state);
  $('#agent-reply').hidden = state!=='complete';
  $('#agent-reply span').textContent = name+' · just now';
  $('#agent-reply p').textContent = `I found your message: “Hello, ${name}!” You asked what’s in your inbox.`;
  $('#read-message').hidden = state==='complete';
  const messages = {invalid:'Use a name and an address like atlas. Letters, numbers, dots and hyphens only.',creating:'Setting up your inbox and mailbox permissions…',taken:'That address is already in use. Try atlas-assistant.', 'create-error':'We couldn’t create the inbox. Your details are saved. Try again.', connecting:'Checking the endpoint and mailbox token…','connect-error':'Couldn’t connect. Check the endpoint, token and Cloudflare Access settings.',connected:'Connected. Atlas can read this mailbox.',waiting:'Sample sent. Waiting for it to arrive…',timeout:'Nothing yet. The message may be delayed. Try again.',received:'Message received. Ready for your agent.',complete:'All set. Your agent read its first message.'};
  const feedback=$('#feedback');feedback.hidden=!messages[state];feedback.textContent=messages[state]||'';
  feedback.className=['invalid','taken','create-error','connect-error','timeout'].includes(state)?'error':busy?'loading':'ok';
  $('#address').setAttribute('aria-invalid',String(['invalid','taken'].includes(state)));
}
function play(start,end) { render(start); timer=setTimeout(()=>render(end),1800); }
$('#preview-state').onchange=e=>{if(e.target.value==='empty'){$('#inbox-form').reset();$('#name').value='';$('#address').value='';}else if(!$('#name').value) fill(); render(e.target.value);};
$('#address').oninput=()=>edited=true;
$('#name').oninput=()=>{if(!edited)$('#address').value=$('#name').value.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');};
$('#inbox-form').noValidate=true;
$('#inbox-form').onsubmit=e=>{e.preventDefault();if(!$('#name').value.trim()||!$('#address').validity.valid){render('invalid');return;}play('creating','connect');};
$('#next').onclick=()=>play('connecting','connected');
$('#simulate').onclick=()=>play('waiting','received');
$('#read-message').onclick=()=>render('complete');
$('#restart').onclick=()=>{$('#inbox-form').reset();fill();edited=false;render('ready');};
document.querySelectorAll('[data-back]').forEach(b=>b.onclick=()=>render(b.dataset.back==='1'?'ready':'connect'));
$('#copy').onclick=async()=>{try{await navigator.clipboard.writeText($('#config').value);$('#copy-status').textContent='Copied. Demo credentials only.';}catch{$('#config').select();$('#copy-status').textContent='Select and copy the example above.';}};
const initial=new URLSearchParams(location.search).get('state')||'ready';
if(initial==='empty'){$('#name').value='';$('#address').value='';}
render(initial,false);
