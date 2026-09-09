// Read-only provider verification. Requires a privately injected Cloudflare credential.
import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm,mkdir,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomBytes} from 'node:crypto';
import assert from 'node:assert/strict';
const input=process.argv[2];if(!input)throw new Error('Provide private saved live-plan.json');
const {settings}=JSON.parse(await readFile(input,'utf8'));
const provider=process.env.HERMESAKI_SETUP;if(!provider)throw new Error('Inject HERMESAKI_SETUP privately');
const directory=await mkdtemp(join(tmpdir(),'hermesaki-live-state-'));const port=19206,base='http://127.0.0.1:'+port;let server,browser;
const owner=randomBytes(32).toString('hex');
async function request(path,method='GET',body,credential=owner){const r=await fetch(base+path,{method,headers:{'Content-Type':'application/json',Authorization:'Bearer '+credential},body:body?JSON.stringify(body):undefined});return {status:r.status,body:await r.json()};}
try{
 const env={...process.env,PYTHONPATH:'src'};delete env.HERMESAKI_SETUP;
 server=spawn('python3',['-m','hermesaki.setup','--state',directory,'--port',String(port)],{env,stdio:['ignore','pipe','pipe']});
 await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('exit',()=>reject(new Error('Setup exited')));});
 const bootstrap=await readFile(join(directory,'bootstrap-token'),'utf8');
 assert.equal((await request('/v1/setup/claim','POST',{owner_token:owner},bootstrap)).status,200);
 const incomplete=await request('/v1/setup');assert.equal(incomplete.body.next_action,'configure');
 const invalid=await request('/v1/setup/configuration','PUT',{...settings,domain:'bad domain'});assert.equal(invalid.status,400);
 assert.equal((await request('/v1/setup/configuration','PUT',settings)).status,200);
 const missing=await request('/v1/setup');assert.equal(missing.body.next_action,'connect_cloudflare');
 assert.equal((await request('/v1/setup/cloudflare','PUT',{token:provider})).status,200);
 const ready=await request('/v1/setup');assert.equal(ready.body.state,'plan_ready');assert.equal(ready.body.complete,false);assert.equal(ready.body.next_action,'review_and_apply_plan');
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1500,height:1200}});await page.goto(base);
 await page.getByText('This installation has an owner.',{exact:false}).waitFor();
 await page.locator('#credential').fill(owner);await page.getByRole('button',{name:'Connect',exact:true}).click();await page.locator('#provider-review').waitFor();
 assert.equal(await page.locator('#credential').inputValue(),'');
 await mkdir('.runtime/evidence',{recursive:true});await page.screenshot({path:'.runtime/evidence/setup-live-state-ui.png',fullPage:true});
 const samples=[{request:'GET /v1/setup before configuration',...incomplete},{request:'PUT /v1/setup/configuration invalid domain',...invalid},{request:'GET /v1/setup without provider',...missing},{request:'GET /v1/setup after real Cloudflare validation',...ready}];
 for(const sample of samples){delete sample.body.plan;delete sample.body.limitations;delete sample.body.cloudflare_plan;delete sample.body.settings;delete sample.body.host_preflight;}
 const report={time:new Date().toISOString(),source:'Actual HTTP responses from fresh setup service; real Cloudflare read checks; no apply performed. Ready means plan ready, not completed deployment.',samples};
 await writeFile('.runtime/evidence/setup-live-state.json',JSON.stringify(report,null,2));
 const statePage=await browser.newPage({viewport:{width:1700,height:1400}});await statePage.setContent('<h1>Hermesaki: actual setup API states</h1><p></p><div></div>');
 await statePage.locator('p').evaluate((el,r)=>el.textContent=r.time+' | '+r.source,report);
 await statePage.locator('div').evaluate((el,samples)=>{for(const s of samples){const section=document.createElement('section'),h=document.createElement('h2'),pre=document.createElement('pre');h.textContent=s.request+' → HTTP '+s.status;pre.textContent=JSON.stringify(s.body,null,2);section.append(h,pre);el.append(section);}},samples);
 await statePage.addStyleTag({content:'body{font:16px system-ui;padding:20px;color:#203428}div{display:grid;grid-template-columns:1fr 1fr;gap:20px}section{background:#f6f7f6;padding:16px}pre{font:15px/1.35 monospace;white-space:pre-wrap;overflow-wrap:anywhere}h2{font-size:18px}'});
 await statePage.screenshot({path:'.runtime/evidence/setup-live-state-api.png',fullPage:true});
 console.log('PASS actual incomplete, invalid, missing-provider and live plan-ready states; UI screenshot captured without credentials.');
}finally{await browser?.close();if(server){const stopped=new Promise(r=>server.once('exit',r));server.kill();await stopped;}await rm(directory,{recursive:true,force:true});}
