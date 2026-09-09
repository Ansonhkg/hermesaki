// Render recorded verification results. This does not execute or invent checks.
import {chromium} from 'playwright';
import {readFile} from 'node:fs/promises';
const [input,output]=process.argv.slice(2);
if(!input||!output)throw new Error('Usage: setup-evidence-report.mjs report.json screenshot.png');
const report=JSON.parse(await readFile(input,'utf8'));
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1450,height:1000}});
 await page.setContent('<h1>Hermesaki live infrastructure verification</h1><p id="source"></p><table><thead><tr><th>Check</th><th>Observed result</th></tr></thead><tbody></tbody></table><p id="hash"></p>');
 await page.locator('#source').evaluate((el,r)=>el.textContent=r.time+' | '+r.source,report);
 await page.locator('tbody').evaluate((el,rows)=>{for(const row of rows){const tr=document.createElement('tr');for(const v of [row.test,row.result]){const td=document.createElement('td');td.textContent=v;tr.append(td);}el.append(tr);}},report.rows);
 await page.locator('#hash').evaluate((el,r)=>el.textContent='Existing DNS before: '+r.before_fingerprint+'\nExisting DNS after: '+r.after_fingerprint,report);
 await page.addStyleTag({content:'body{font:18px/1.5 system-ui;padding:30px;color:#24352a;background:white}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:18px;border-bottom:1px solid #ddd}td:first-child{width:28%;font-weight:600}h1{font-size:30px}#hash{white-space:pre-wrap;font:14px/1.7 monospace}'});
 if(report.raw){
  await page.evaluate(r=>{
   document.querySelector('table').remove();
   const heading=t=>{const h=document.createElement('h2');h.textContent=t;document.body.append(h);};
   const pre=v=>{const p=document.createElement('pre');p.textContent=JSON.stringify(v,null,2);document.body.append(p);};
   heading('Actual planner output after provisioning');pre(r.raw.refreshed_plan.actions.map(a=>a.operation+' '+a.kind+' '+(a.hostname||a.name)));
   heading('Actual conflict and refused apply output');pre({conflicts:r.raw.conflict_plan.conflicts,apply_available:r.raw.conflict_plan.apply_available,...r.raw.apply_error,record_after_refused_apply:r.raw.conflict_record_after_refused_apply});
   heading('Existing DNS records: before and after');
   const table=document.createElement('table');
   for(let i=0;i<r.before_records.length;i++){const tr=document.createElement('tr');for(const value of [r.before_records[i],r.after_records[i]]){const td=document.createElement('td');td.textContent=JSON.stringify(value);tr.append(td);}table.append(tr);}
   table.className='raw';document.body.append(table);
  },report);
  await page.addStyleTag({content:'pre{font:15px/1.3 monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f7f6;padding:12px}.raw{table-layout:fixed}.raw td{width:50%;font:14px/1.3 monospace;white-space:pre-wrap;overflow-wrap:anywhere;vertical-align:top}'});
 }
 await page.screenshot({path:output,fullPage:true});
}finally{await browser.close();}
