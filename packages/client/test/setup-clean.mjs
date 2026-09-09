// Browser requests are relayed into the isolated container's private listener.
// The app response is rendered unchanged; the separate report shows real command output.
import {chromium} from 'playwright';
import {execFileSync} from 'node:child_process';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const run=(...a)=>execFileSync('docker',a,{encoding:'utf8'}).trim();
const name='hermesaki-setup-proof-'+Date.now();
const transcript=[];
const command=(...a)=>{const output=run(...a);transcript.push('$ docker '+a.join(' ')+'\n'+output);return output;};
let browser;
try{
 const id=command('create','--name',name,'--network','none','hermesaki-setup-test:local');
 const config=JSON.parse(run('inspect',name))[0];
 assert.equal(config.Mounts.length,0);assert.deepEqual(config.Config.Cmd,['make','setup']);
 transcript.push('Fresh disposable Linux container. No mounted state. Network disabled. Command: make setup.');
 command('start',name);
 const python=`import json,sys,urllib.request,urllib.error,base64
x=json.loads(sys.stdin.read())
r=urllib.request.Request('http://127.0.0.1:19200'+x['path'],method=x['method'],headers=x['headers'],data=base64.b64decode(x['body']) if x['body'] else None)
try: response=urllib.request.urlopen(r,timeout=10)
except urllib.error.HTTPError as e: response=e
print(json.dumps({'status':response.status,'headers':dict(response.headers),'body':base64.b64encode(response.read()).decode()}))`;
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1200,height:950}});
 await page.route('http://127.0.0.1:19200/**',async route=>{
 const req=route.request();
 const result=JSON.parse(execFileSync('docker',['exec','-i',name,'python3','-c',python],{encoding:'utf8',input:JSON.stringify({path:new URL(req.url()).pathname,method:req.method(),headers:req.headers(),body:req.postDataBuffer()?.toString('base64')||''})}));
 await route.fulfill({status:result.status,headers:result.headers,body:Buffer.from(result.body,'base64')});
 });
 await page.goto('http://127.0.0.1:19200/');
 await page.waitForFunction(()=>document.querySelector('#access-help').textContent.includes('bootstrap-token'));
 command('logs',name);
 command('exec',name,'python3','-c',"import pathlib,platform; print(platform.platform()); print('Product mail configuration exists:', pathlib.Path('/app/.runtime/product').exists()); print('First-run state exists:', pathlib.Path('/app/.runtime/setup/setup.sqlite').exists())");
 transcript.push('Browser rendered the actual container HTTP responses. Owner is unclaimed. No configuration files were edited or repairs performed after startup.');
 await mkdir('.runtime/evidence',{recursive:true});
 await page.screenshot({path:'.runtime/evidence/setup-clean-screen.png',fullPage:true});
 await writeFile('.runtime/evidence/setup-clean-transcript.txt',transcript.join('\n\n'));
 // An actual browser-rendered test report. Kept separate from the application screenshot.
 const report=await browser.newPage({viewport:{width:1400,height:1100}});
 await report.setContent('<h1>Hermesaki clean Linux startup test</h1><p>Actual command transcript from this run. Container HTTP responses rendered unchanged in Chromium.</p><pre></pre>');
 await report.locator('pre').evaluate((e,t)=>{e.textContent=t;e.style.cssText='white-space:pre-wrap;font:18px/1.6 monospace';},transcript.join('\n\n'));
 const screenshot=await readFile('.runtime/evidence/setup-clean-screen.png');
 await report.evaluate(data=>{const img=document.createElement('img');img.src=data;img.style.cssText='width:900px;max-width:100%';document.body.append(img);},'data:image/png;base64,'+screenshot.toString('base64'));
 await report.screenshot({path:'.runtime/evidence/setup-clean-startup.png',fullPage:true});
 console.log('PASS fresh Linux container: make setup, zero mounted state, no network, real browser first-run page, no post-start repair');
}finally{await browser?.close();run('rm','-f',name);}
