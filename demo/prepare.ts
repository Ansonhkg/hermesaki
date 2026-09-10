import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import {runWalkthrough} from '../packages/demo-walkthrough/runner';
import {workflows,guides} from './journeys';
const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1460,height:1000}});
const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
await page.request.post('http://127.0.0.1:19195/reset-demo');
await page.goto('http://127.0.0.1:19195/author.html');await page.waitForFunction(()=>typeof (window as any).rpc==='function');
const frame=()=>page.frames().find(f=>f!==page.mainFrame())!;
const fill=async(s:string,v:string)=>frame().locator(s).fill(v);const click=async(s:string)=>frame().locator(s).click();
const steps:Record<string,()=>Promise<any>>={
 claim:async()=>{await fill('#credential','demo-bootstrap');await fill('#new-owner','demo-owner');await click('#connect');},
 domain:async()=>{await fill('[name=domain]','example.test');await fill('[name=server_ip]','192.0.2.10');await fill('[name=owner_email]','owner@example.test');await click('#settings button');},
 cloudflare:async()=>{await fill('#provider-token','fictional-provider-token');await click('#provider button');},
 review:async()=>{await frame().locator('#confirm-plan').check();await click('#apply-plan button');},
 services:async()=>{await fill('#access-team','demo');await fill('#first-mailbox','hi@example.test');await frame().locator('#acme-terms').check();await click('#service-settings button');},
 deploy:async()=>{await frame().locator('#service-confirm').check();await click('#service-apply button');},
 signing:async()=>click('#dkim-plan button'),publish:async()=>{await frame().locator('#dkim-confirm').check();await click('#dkim-apply button');},
 verify:async()=>click('#verify-runtime button'),finish:async()=>click('#complete-setup button'),
 login:async()=>{await fill('#owner-token','invalid');await click('#login-form button');},
 invalid:async()=>{await fill('#owner-token','demo-owner');await click('#login-form button');},
 empty:async()=>{await fill('#local-name','atlas');await click('#create-form button');},
 issued:async()=>click('#check'),connected:async()=>{await click('#send-test');await frame().locator('#messages button').waitFor();},
 message:async()=>click('#messages button'),revoke:async()=>click('#tokens button'),
 revoked:async()=>click('summary'),delete:async()=>{await fill('#delete-email','atlas@example.test');await click('#delete');}
};
const recordings:any[]=[];await mkdir('.runtime/demo',{recursive:true});
try{for(const workflow of workflows){await page.locator('iframe').evaluate((el:any,path)=>{el.src=path;},workflow.id==='setup'?'/setup':'/ui/onboarding/live.html');await page.frameLocator('iframe').locator(workflow.id==='setup'?'#claim':'#login').waitFor();
 const run=await runWalkthrough({workflow,signal:new AbortController().signal,timing:{settle:200,after:250,poll:100},select:(id)=>console.log(workflow.id,id),prepare:()=>{},rpc:async(_s,type,key)=>page.evaluate(({type,key})=>(window as any).rpc(type,key),{type,key}),save:async()=>{},plan:{prepare:async()=>({sample:'hermesaki-local'}),steps:()=>workflow.nodes.map(step=>({step,key:workflow.id+'/'+step.id,guide:guides[workflow.id+'/'+step.id],manual:steps[step.id],afterCapture:steps[step.id]?'server' as const:undefined}))}});
 if(run.outcome!=='passed')throw Error(run.error);recordings.push(run);
 }await writeFile('.runtime/demo/recordings.json',JSON.stringify(recordings));if(errors.length)throw Error(errors.join('\n'));console.log('Prepared '+recordings.reduce((n,r)=>n+r.captures.length,0)+' actual UI captures with simulated services.');
}catch(e){await page.screenshot({path:'.runtime/demo/failure.png'});console.log(await frame().locator('body').innerText());throw e;}finally{await browser.close();}
