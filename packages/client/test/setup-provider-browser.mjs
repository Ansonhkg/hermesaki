// Upstream Cloudflare is an explicit in-memory fixture. Never production evidence.
import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomBytes} from 'node:crypto';
import assert from 'node:assert/strict';
const directory=await mkdtemp(join(tmpdir(),'hermesaki-provider-ui-'));
const program=`import sys
from hermesaki.setup import Setup, App, QuietHandler
from test_setup_apply import Fixture
from hermesaki.setup_cloudflare import CloudflareError
from wsgiref.simple_server import make_server
fixture=Fixture()
def provider(token):
 if token.startswith('invalid'): raise CloudflareError('cloudflare_permission_denied')
 return fixture
setup=Setup(sys.argv[1],provider)
server=make_server('127.0.0.1',19204,App(setup,19204),handler_class=QuietHandler)
print('ready',flush=True)
server.serve_forever()`;
const server=spawn('python3',['-c',program,directory],{env:{...process.env,PYTHONPATH:'src:tests'},stdio:['ignore','pipe','pipe']});
let browser;
try{
 await new Promise((res,rej)=>{server.stdout.once('data',res);server.once('exit',code=>rej(new Error('server exited '+code)));});
 browser=await chromium.launch({headless:true});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:19204');
 await page.locator('#credential').fill((await readFile(join(directory,'bootstrap-token'),'utf8')).trim());
 await page.locator('#new-owner').fill(randomBytes(32).toString('hex'));await page.locator('#connect').click();await page.locator('#configuration').waitFor({state:'visible'});
 for(const [name,value] of Object.entries({domain:'example.com',server_ip:'203.0.113.10',owner_email:'owner@example.com'}))await page.locator(`[name=${name}]`).fill(value);
 await page.getByRole('button',{name:'Save configuration'}).click();await page.locator('#cloudflare').waitFor({state:'visible'});
 await page.locator('#provider-token').fill('invalid-credential-123456789');await page.locator('#provider button').click();await page.locator('#feedback').filter({hasText:'cloudflare permission denied'}).waitFor();assert.equal(await page.locator('#provider-token').inputValue(),'');
 await page.locator('#provider-token').fill('fixture-credential-123456789');await page.locator('#provider button').click();await page.locator('#provider-review').waitFor({state:'visible'});
 assert.equal(await page.locator('#confirm-plan').isChecked(),false);
 await page.locator('#apply-plan button').click();assert.equal(await page.locator('#apply-state').textContent(),'');
 await page.locator('#confirm-plan').check();await page.locator('#apply-plan button').click();await page.locator('#apply-state').filter({hasText:'web resources applied'}).waitFor();
 await page.locator('#services').waitFor({state:'visible'});
 await page.locator('#access-team').fill('fixture-team');await page.locator('#first-mailbox').fill('hi@example.com');await page.locator('#acme-terms').check();
 await page.locator('#service-settings button').click();await page.locator('#service-review').waitFor({state:'visible'});
 assert.match(await page.locator('#service-plan-text').textContent(),/Only SMTP port 25 is public/);
 assert.equal(await page.locator('#service-confirm').isChecked(),false);
 await page.locator('#service-apply-button').click();assert.equal(await page.locator('#service-status').textContent(),'');
 await page.locator('#services').scrollIntoViewIfNeeded();await page.screenshot({path:'.runtime/evidence/setup-service-plan-fixture.png'});
 await page.locator('#provider-token').fill('replacement-credential-123456789');await page.locator('#provider button').click();await page.locator('#feedback').filter({hasText:'Cloudflare read checks passed'}).waitFor();
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);
 console.log('PASS provider UI with explicit upstream fixture: rejected token, plan, required confirmation, apply, full mail service plan, required service confirmation, credential replacement, no browser secret persistence');
}finally{await browser?.close();const exited=new Promise(r=>server.once('exit',r));server.kill();await exited;await rm(directory,{recursive:true,force:true});}
