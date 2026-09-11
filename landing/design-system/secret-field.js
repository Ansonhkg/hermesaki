// One shared control for sensitive inputs. Feedback never changes document flow.
export function secretField(input,{copy=true,load}={}){
 if(input.closest('.secret-field'))return;
 const wrap=document.createElement('div');wrap.className='secret-field';input.before(wrap);wrap.append(input);
 const actions=document.createElement('span');actions.className='secret-actions';wrap.append(actions);
 const eye='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>';
 const clipboard='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>';
 function button(label,icon){const b=document.createElement('button');b.type='button';b.className='secret-action';b.setAttribute('aria-label',label);b.title=label;b.innerHTML=icon;actions.append(b);return b;}
 const reveal=button('Show value',eye);reveal.setAttribute('aria-pressed','false');reveal.onclick=async()=>{if(load&&input.type==='password'){reveal.disabled=true;try{await load()}catch{reveal.title='Could not load value. Retry.';return}finally{reveal.disabled=false}}const show=input.type==='password';input.type=show?'text':'password';reveal.setAttribute('aria-pressed',String(show));reveal.setAttribute('aria-label',show?'Hide value':'Show value');reveal.title=show?'Hide value':'Show value';};
 if(copy){const b=button('Copy value',clipboard);const status=document.createElement('span');status.className='secret-feedback';status.setAttribute('role','status');status.setAttribute('aria-live','polite');wrap.append(status);let timer;b.onclick=async()=>{clearTimeout(timer);try{if(load)await load();if(!input.value){status.textContent='Empty';}else{await navigator.clipboard.writeText(input.value);status.textContent='Copied';}}catch{status.textContent='Copy failed';}timer=setTimeout(()=>{status.textContent=''},1800);};}
}
export function enhanceSecrets(root){root.querySelectorAll('input[type=password]').forEach(input=>secretField(input));}
