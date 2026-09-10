// Read-only live Cloudflare plan plus a deliberately invalid confirmation.
// Does not authorize or deploy the service plan.
import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
const state=process.argv[2];if(!state)throw new Error('Pass the existing isolated setup state directory.');
const owner=(await readFile(resolve(state,'test-owner'),'utf8')).trim();
const server=spawn('python3',['-m','hermesaki.setup','--state',state,'--port','19206'],{env:{...process.env,PYTHONPATH:'src'},stdio:['ignore','pipe','pipe']});
let browser;
try{
 await new Promise((r,j)=>{server.stdout.once('data',r);server.once('exit',c=>j(new Error('setup exited '+c)));});
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1400,height:1100}});
 await page.goto('http://127.0.0.1:19206');await page.locator('#credential').fill(owner);await page.locator('#connect').click();
 await page.locator('#service-review').waitFor({state:'visible'});

 // Simulate a stale/tampered confirmation. The server must reject before any write.
 await page.evaluate(()=>{servicePlan={...servicePlan,id:'deliberately-unapproved-plan'};});
 await page.locator('#service-confirm').check();await page.locator('#service-apply-button').click();
 await page.locator('#feedback').filter({hasText:'exact plan confirmation required'}).waitFor();
 assert.match(await page.locator('#feedback').textContent(),/exact plan confirmation required/);
 await page.locator('#services').screenshot({path:'.runtime/evidence/live-service-plan-browser.png'});
 console.log('PASS live Cloudflare plan shown through forms; unapproved service confirmation refused by the real HTTP endpoint. No service deployment attempted.');
}finally{await browser?.close();server.kill();}
