import {chromium} from 'playwright';
import {readFile} from 'node:fs/promises';
const report=JSON.parse(await readFile('.runtime/evidence/setup-live-state.json','utf8'));
const screenshot=(await readFile('.runtime/evidence/setup-live-state-ui.png')).toString('base64');
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:2300,height:1900}});
 await page.setContent('<h1>Hermesaki setup: actual UI and API state</h1><p></p><main><aside><h2>Actual wizard after Cloudflare read checks</h2><img></aside><article></article></main>');
 await page.locator('p').evaluate((el,r)=>el.textContent=r.time+' | '+r.source,report);
 await page.locator('img').evaluate((el,b64)=>el.src='data:image/png;base64,'+b64,screenshot);
 await page.locator('article').evaluate((el,samples)=>{for(const s of samples){const section=document.createElement('section'),h=document.createElement('h2'),pre=document.createElement('pre');h.textContent=s.request+' → HTTP '+s.status;pre.textContent=JSON.stringify(s.body,null,2);section.append(h,pre);el.append(section);}},report.samples);
 await page.addStyleTag({content:'body{font:17px system-ui;padding:20px;color:#203428}main{display:grid;grid-template-columns:750px 1fr;gap:24px}img{width:750px}article{display:grid;grid-template-columns:1fr 1fr;gap:16px}section{background:#f6f7f6;padding:14px;align-self:start}pre{font:16px/1.4 monospace;white-space:pre-wrap;overflow-wrap:anywhere}h2{font-size:19px}'});
 await page.locator('img').evaluate(img=>img.decode());
 await page.screenshot({path:'.runtime/evidence/setup-state-combined.png',fullPage:true});
}finally{await browser.close();}
