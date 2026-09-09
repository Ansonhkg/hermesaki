import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,stat,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {Hermesaki} from '../dist/index.js';
const baseUrl=process.env.HERMESAKI_URL||'http://localhost:19100';
const adminFile=process.env.HERMESAKI_ADMIN_FILE||'.runtime/product/operator-token';
const admin=new Hermesaki({baseUrl,token:(await readFile(adminFile,'utf8')).trim()});
const config=await admin.settings();assert.equal(config.mode,'development','Live suite only runs on local captured mail');
const tmp=await mkdtemp(join(tmpdir(),'hermesaki-client-'));const suffix=Date.now();const boxes=[];
const cli=(args,file=adminFile)=>JSON.parse(execFileSync(process.execPath,['packages/client/dist/cli.js',...args],{env:{...process.env,HERMESAKI_URL:baseUrl,HERMESAKI_TOKEN_FILE:file},encoding:'utf8'}));
async function wait(fn){for(let n=0;n<45;n++){const r=await fn();if(r)return r;await new Promise(r=>setTimeout(r,1000));}throw Error('Mail did not arrive within 45 seconds');}
try{
 const a=await admin.createInbox(`sdk-${suffix}@${config.domain}`);boxes.push(a);const b=cli(['create','--email',`cli-${suffix}@${config.domain}`]);boxes.push(b);
 assert.equal((await admin.createInbox(a.email)).id,a.id);
 const ta=await admin.createToken(a.id,['mail.read','mail.write']);const ca=new Hermesaki({baseUrl,token:ta.token});
 const tbfile=join(tmp,'token');const tb=cli(['token','--inbox',b.id,'--scopes','mail.read,mail.write','--out',tbfile]);assert.equal((await stat(tbfile)).mode&0o777,0o600);assert(!JSON.stringify(tb).includes('token\":'));
 const cb=new Hermesaki({baseUrl,token:(await readFile(tbfile,'utf8')).trim()});
 const ro=await admin.createToken(a.id,['mail.read']);const cr=new Hermesaki({baseUrl,token:ro.token});
 await assert.rejects(cr.send(a.id,{to:[b.email],subject:'denied',body_text:'no'},'denied'),e=>e.status===403);
 await assert.rejects(ca.listFolders(b.id),e=>e.code==='mailbox_denied');
 const short=await admin.createToken(a.id,['mail.read'],1);await new Promise(r=>setTimeout(r,1100));await assert.rejects(new Hermesaki({baseUrl,token:short.token}).listFolders(a.id),e=>e.status===401);
 await admin.revokeToken(ro.id);await assert.rejects(cr.listFolders(a.id),e=>e.status===401);
 const body={to:[b.email],subject:`SDK hello ${suffix}`,body_text:'Fictional acceptance message',attachments:[{filename:'hello.txt',data:Buffer.from('fixture bytes').toString('base64')}]};
 const jobs=await Promise.all([ca.send(a.id,body,'stable'),ca.send(a.id,body,'stable')]);assert.equal(jobs[0].id,jobs[1].id);
 await assert.rejects(ca.send(a.id,{...body,body_text:'changed'},'stable'),e=>e.code==='idempotency_conflict');
 const msg=await wait(async()=> (await cb.listMessages(b.id)).find(m=>m.subject===body.subject));
 const fromCli=cli(['read','--inbox',b.id,'--uid',msg.uid],tbfile);assert.equal(fromCli.attachments[0].data,body.attachments[0].data);
 const tools=await cb.mcp('tools/list');assert(tools.tools.some(t=>t.name==='read_message'));
 const read=await cb.mcp('tools/call',{name:'read_message',arguments:{inbox_id:b.id,uid:msg.uid}});assert(JSON.parse(read.content[0].text).body_text.includes('Fictional'));
 await writeFile(join(tmp,'reply.json'),JSON.stringify({body_text:'A reply from the CLI inbox'}));
 cli(['reply','--inbox',b.id,'--uid',msg.uid,'--file',join(tmp,'reply.json'),'--key','reply-1'],tbfile);
 const reply=await wait(async()=> (await ca.listMessages(a.id)).find(m=>m.subject==='Re: '+body.subject));assert((await ca.readMessage(a.id,reply.uid)).references.includes(msg.message_id));
 const sample=await admin.localTest(a.id,'sample-'+suffix);assert(sample.id);await wait(async()=> (await ca.listMessages(a.id)).find(m=>m.subject==='Hello from Hermesaki'));
 await ca.send(a.id,{to:['outside@example.org'],subject:`capture-${suffix}`,body_text:'Must stay in Mailpit'},'capture');
 await wait(async()=>{const r=await fetch((process.env.HERMESAKI_CAPTURE_URL||'http://localhost:19125')+'/api/v1/search?query='+encodeURIComponent(`subject:capture-${suffix}`));const d=await r.json();return d.messages?.length;});
 console.log('PASS SDK/CLI/MCP real send, attachment, reply, local sample, external capture, idempotency, scope/isolation, expiry and revocation');
}finally{for(const i of boxes)await admin.deleteInbox(i.id,i.email);await rm(tmp,{recursive:true,force:true});}
