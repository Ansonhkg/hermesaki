import {defineConfig} from 'vite';
import {readFileSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {installPage} from './install';
import {mockApi} from './mock';
const root=resolve(import.meta.dirname,'..');
export default defineConfig({esbuild:{jsx:'automatic'},root:resolve(root,'demo'),server:{hmr:false,watch:{ignored:['**/.runtime/**']},host:'127.0.0.1',port:19195,strictPort:true,fs:{allow:[root]}},plugins:[{name:'hermesaki-fixtures',configureServer(server){let api=mockApi();server.middlewares.use(async(req,res,next)=>{
 const path=new URL(req.url!,'http://localhost').pathname;
 if(path==='/healthz'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({status:'ok'}));return;}
 if(path.startsWith('/install/')){res.setHeader('Content-Type','text/html');res.end(installPage(path.split('/').pop()!));return;}
 if(path==='/reset-demo'&&req.method==='POST'){api=mockApi();res.end('{}');return;}
 if(path==='/v1/session'){const logged=req.headers.cookie?.includes('hermesaki_demo_session=1');const ok=req.method==='POST'?req.headers.authorization==='Bearer demo-owner':logged;res.statusCode=ok?200:401;if(ok&&req.method!=='GET')res.setHeader('Set-Cookie',`hermesaki_demo_session=${req.method==='POST'?'1':''}; Path=/; HttpOnly; SameSite=Strict`);res.setHeader('Content-Type','application/json');res.end(JSON.stringify(ok?{authenticated:req.method!=='DELETE'}:{error:'invalid_token'}));return;}
 if(path.startsWith('/v1/')||path==='/mcp'){let text='';for await(const chunk of req)text+=chunk;const [status,data]=api(path,req.method!,text?JSON.parse(text):{},req.headers.authorization||(req.headers.cookie?.includes('hermesaki_demo_session=1')?'Bearer demo-owner':''));res.statusCode=status;res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));return;}
 let file=path==='/welcome'?'landing/index.html':path==='/welcome/setup'?'landing/get-started.html':(['/','/operator','/login','/inboxes','/agents','/activity','/settings','/docs'].includes(path)||path.startsWith('/docs/')||path.startsWith('/settings/'))&&!(path==='/'&&new URL(req.url!,'http://localhost').searchParams.has('workflow'))?'src/hermesaki/operator.html':path==='/setup'?'src/hermesaki/setup.html':path==='/setup.js'||path==='/setup.css'?'src/hermesaki'+path:path.startsWith('/ui/')?'landing/'+path.slice(4)+(path.endsWith('/')?'index.html':''):path==='/recordings.json'?'.runtime/demo/recordings.json':null;
 if(path==='/setup-mascot.png')file='landing/assets/hermesaki-messenger.png';
 if(path==='/ui/client.js')file='packages/client/dist/index.js';
 if(file){const full=resolve(root,file);if(!full.startsWith(root+'/')||!existsSync(full)){res.statusCode=404;res.end('Not found');return;}
 let body=readFileSync(full);const ext=full.split('.').at(-1);res.setHeader('Content-Type',({html:'text/html',js:'text/javascript',css:'text/css',json:'application/json',png:'image/png'} as any)[ext!]||'application/octet-stream');
 if(ext==='html'){
  let html=body.toString();
  const banner='<div class="demo-environment-banner" role="note"><strong>Local walkthrough</strong><span>Fictional data. Mail, DNS and Cloudflare responses are simulated.</span></div>';
  const styles='<link rel="stylesheet" href="/environment-banner.css">';
  html=html.includes('</main>')?html.replace('</main>',banner+'</main>'):html.replace('<body>','<body>'+banner);
  html=styles+html;
  html=html.includes('</body>')?html.replace('</body>','<script type="module" src="/bridge.ts"></script></body>'):html+'<script type="module" src="/bridge.ts"></script>';
  body=Buffer.from(html);
 }

 res.end(body);return;
 }next();
 });}}]});
