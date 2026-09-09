import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm,mkdir,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomBytes} from 'node:crypto';
import assert from 'node:assert/strict';
const dir=await mkdtemp(join(tmpdir(),'hermesaki-security-'));
const port=19202,base='http://127.0.0.1:'+port,rows=[];
let server,browser;
async function start(){server=spawn('python3',['-m','hermesaki.setup','--state',dir,'--port',String(port)],{env:{...process.env,PYTHONPATH:'src'},stdio:['ignore','pipe','pipe']});await new Promise((res,rej)=>{server.stdout.once('data',res);server.once('exit',c=>rej(new Error('Server exited '+c)));});}
async function stop(){const exited=new Promise(r=>server.once('exit',r));server.kill();await exited;server=null;}
async function check(label,method,path,token,body,expected){const r=await fetch(base+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:body?JSON.stringify(body):undefined});const value=await r.json();assert.equal(r.status,expected,label);rows.push({label,request:method+' '+path,status:r.status,result:JSON.stringify(value)});return value;}
try{
 await start();const bootstrap=(await readFile(join(dir,'bootstrap-token'),'utf8')).trim();const owner=randomBytes(32).toString('hex');
 await check('Anonymous enrollment denied','POST','/v1/setup/claim',null,{owner_token:owner},401);
 await check('Incorrect bootstrap denied','POST','/v1/setup/claim','wrong',{owner_token:owner},401);
 await check('Private bootstrap claims owner','POST','/v1/setup/claim',bootstrap,{owner_token:owner},200);
 await assert.rejects(readFile(join(dir,'bootstrap-token')));rows.push({label:'Bootstrap credential file removed',result:'ENOENT after successful claim'});
 await check('Consumed bootstrap cannot claim again','POST','/v1/setup/claim',bootstrap,{owner_token:randomBytes(32).toString('hex')},409);
 await check('Second owner cannot take over','POST','/v1/setup/claim',owner,{owner_token:randomBytes(32).toString('hex')},409);
 await check('Consumed bootstrap cannot read owner state','GET','/v1/setup',bootstrap,null,401);
 await stop();await start();
 await check('Claim remains closed after restart','POST','/v1/setup/claim',bootstrap,{owner_token:randomBytes(32).toString('hex')},409);
 const state=await check('Original owner reconnects after restart','GET','/v1/setup',owner,null,200);
 assert.equal(state.state,'configuration_required');
 // Do not reproduce the lengthy configuration result or any credential in the screenshot.
 rows.at(-1).result=JSON.stringify({state:state.state,complete:state.complete});
 const raw=await readFile(join(dir,'setup.sqlite'));assert(!raw.includes(owner));rows.push({label:'Owner credential absent from SQLite plaintext',result:'Verified against live database bytes'});
 await mkdir('.runtime/evidence',{recursive:true});const report={time:new Date().toISOString(),transport:'Actual HTTP to isolated local setup service; new private state directory; server restarted during test',rows};
 await writeFile('.runtime/evidence/setup-security.json',JSON.stringify(report,null,2));
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1450,height:1100}});
 await page.setContent('<h1>Hermesaki owner-bootstrap verification</h1><p></p><table><thead><tr><th>Real test</th><th>Request</th><th>HTTP</th><th>Observed result</th></tr></thead><tbody></tbody></table>');
 await page.locator('p').evaluate((el,report)=>el.textContent=report.time+' | '+report.transport,report);
 await page.locator('tbody').evaluate((el,rows)=>{for(const row of rows){const tr=document.createElement('tr');for(const v of [row.label,row.request||'',row.status||'',row.result]){const td=document.createElement('td');td.textContent=v;tr.append(td);}el.append(tr);}},rows);
 await page.addStyleTag({content:'body{font:17px/1.5 system-ui;padding:28px;color:#24352a}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:14px;border-bottom:1px solid #ddd}td:last-child{font-family:monospace}h1{font-size:30px}'});
 await page.screenshot({path:'.runtime/evidence/setup-security.png',fullPage:true});console.log('PASS all owner bootstrap HTTP security checks, restart and plaintext checks');
}finally{await browser?.close();if(server)await stop();await rm(dir,{recursive:true,force:true});}
