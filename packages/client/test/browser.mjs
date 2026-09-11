import {chromium} from 'playwright';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {administratorSession} from './admin-session.mjs';
const b=await chromium.launch({headless:true});
try{
 const p=await b.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 const baseUrl=process.env.HERMESAKI_URL||'http://localhost:19100';const {credentials}=await administratorSession(baseUrl);
 await p.goto(baseUrl+'/login');
 await p.locator('#username').fill(credentials.username);await p.locator('#password').fill('incorrect-password');await p.locator('#connect').click();await p.locator('#error').filter({hasText:'Incorrect'}).waitFor();
 await p.locator('#password').fill(credentials.password);await p.locator('#connect').click();await p.locator('#sidebar').waitFor({state:'visible'});await p.getByRole('button',{name:'Inboxes',exact:true}).click();await p.locator('#create').waitFor({state:'visible'});
 const local='browser-'+Date.now();await p.locator('#local-name').fill(local);
 await p.route('**/v1/inboxes',r=>r.request().method()==='POST'?r.fulfill({status:502,contentType:'application/json',body:'{"error":"service_unavailable"}'}):r.continue());await p.locator('#create-form button').click();await p.locator('#status.error').waitFor();await p.unroute('**/v1/inboxes');
 await p.locator('#create-form button').click();await p.locator('#issued').waitFor({state:'visible'});await p.locator('#check').click();await p.locator('#checked').waitFor({state:'visible'});await p.locator('#send-test').click();await p.waitForFunction(()=>document.querySelector('#status').textContent.includes('arrived'),{},{timeout:45000});
 await p.locator('#messages button').first().click();await p.locator('#message-body').waitFor({state:'visible'});assert((await p.locator('#message-body').textContent()).includes('real local inbox'));
 await p.setViewportSize({width:390,height:844});assert(!await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
 await p.locator('summary').click();const email=await p.locator('#inbox-email').textContent();await p.locator('#delete-email').fill(email);await p.locator('#delete').click();await p.locator('#create').waitFor({state:'visible'});
 assert.equal(await p.evaluate(()=>localStorage.length+sessionStorage.length),0);assert.deepEqual(errors,[]);
 console.log('PASS browser: auth failure, retry, real inbox/token, MCP check, SMTP arrival/read, mobile, deletion and no persisted secrets');
}finally{await b.close();}
