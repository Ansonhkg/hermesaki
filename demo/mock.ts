// Local-only, fictional provider and mailbox responses. Never imported by production.
export function mockApi() {
 let state:any={checks:[]}, inbox:any=null, issued=false, read=false, revoked=false;
 let mcpGate:any=null, pending:any=null;
 const inventory:any={dns:[{id:'demo-a',type:'A',name:'mail.example.test',content:'203.0.113.10',ttl:300}],routes:[{tunnel_id:'demo-tunnel',hostname:'inbox.example.test',service:'http://127.0.0.1:18940'}],policies:[{app_id:'demo-app',id:'demo-policy',hostname:'hermesaki.example.test',name:'Owner only',include:[{email:{email:'owner@example.test'}}]}]};
 const configuration:any={domain:'example.test',mode:'development',operator_url:'https://hermesaki.example.test',webmail_url:'https://inbox.example.test',mail_host:'mail.example.test',imap_port:993,smtp_port:465,cloudflare_identity_verification:true,message_size_limit_bytes:5242880,delivery_attempt_limit:5,infrastructure:inventory};
 const plan={id:'fictional-plan',apply_available:true,conflicts:[],actions:[{operation:'create',kind:'Tunnel',hostname:'inbox.example.test'},{operation:'create',kind:'Access',hostname:'hermesaki.example.test'}]};
 return (path:string,method:string,data:any,authorization:string):[number,any]=>{
 if(path==='/v1/setup/status')return [200,{claimed:false}];
 if(path==='/v1/setup/claim')return [200,{}];
 if(path==='/v1/setup/services/credentials')return [200,{email:'hi@example.test',operator_token:'demo-owner',password:'fictional-only'}];
 if(path.startsWith('/v1/setup')){
  if(path.endsWith('/configuration'))state.settings=data;
  if(path.endsWith('/cloudflare')){state.cloudflare_plan=plan;return [200,{plan}];}
  if(path==='/v1/setup/apply')state.provisioning={state:'web_resources_applied'};
  if(path.endsWith('/services/plan'))state.service_plan={...plan,options:data,first_mailbox:data.first_mailbox,actions:[],services:{mail:{published_ports:[25]},webmail:{published_ports:[],application_auth:'Mailbox login'}},certificate:{hostname:'mail.example.test'},webmail_hostname:'inbox.example.test',operator_hostname:'hermesaki.example.test'};
  if(path.endsWith('/services/apply'))state.service_progress={state:'services_running',stage:'Simulated deployment'};
  if(path.endsWith('/dkim/plan'))state.dkim_plan={id:'fictional-dkim',record:'DKIM public key (simulated)'};
  if(path.endsWith('/dkim/apply'))state.dkim_progress={state:'Simulated signing records published'};
  if(path.endsWith('/services/verify'))state.service_verification={ready:true,checks:['DNS','TLS','SMTP','SPF / DKIM / DMARC','Agent permissions'].map(id=>({id,state:'passed',detail:'SIMULATED in local walkthrough; no provider contacted'}))};
  if(path.endsWith('/complete'))return [200,{complete:true,operator_url:'/',webmail_url:'/ui/onboarding/live.html',authentication:'Demo only. Continue with the fictional operator token demo-owner.'}];
  return [200,state];
 }
 if(!authorization||authorization==='Bearer invalid')return [401,{error:'invalid_token'}];
 if(path==='/v1/operator/mcp-connection')return [200,{url:'https://hermesaki.example.test/mcp',cloudflare_required:true,configured:!!mcpGate}];
 if(path==='/v1/operator/mcp-connection/save'){mcpGate={client_id:'fictional-client-id',client_secret:'fictional-client-secret'};return [200,{saved:true,verified:false}];}
 if(path==='/v1/operator/mcp-connection/reveal')return mcpGate?[200,mcpGate]:[409,{error:'service_credentials_not_configured'}];
 if(path==='/v1/operator/configuration')return [200,configuration];
 if(path==='/v1/operator/configuration/plan'){if(!/^https:\/\//.test(data.webmail_url))return [400,{error:'https_webmail_url_required'}];pending={id:'demo-setting-plan',before:configuration.webmail_url,after:data.webmail_url};return [200,pending];}
 if(path==='/v1/operator/configuration/apply'){if(!pending||data.confirm_plan_id!==pending.id)return [409,{error:'plan_required'}];configuration.webmail_url=pending.after;pending=null;return [200,{applied:true}];}
 if(path==='/v1/operator/infrastructure'||path==='/v1/operator/infrastructure/connect')return [200,{...inventory,checked_at:Date.now()/1000}];
 if(path==='/v1/operator/infrastructure/plan'){const key=data.kind==='dns'?'dns':data.kind==='route'?'routes':'policies';const r=inventory[key].find((r:any)=>(data.kind==='dns'?r.id:data.kind==='route'?r.tunnel_id+'|'+r.hostname:r.app_id+'|'+r.id)===data.id);if(!r)return [404,{error:'resource_not_found'}];pending={id:'demo-infra-plan',before:{...r},after:{...r,...data.change},key,resource:r};return [200,{id:pending.id,before:pending.before,after:pending.after}];}
 if(path==='/v1/operator/infrastructure/apply'){if(!pending||data.confirm_plan_id!==pending.id)return [409,{error:'plan_required'}];Object.assign(pending.resource,pending.after);pending=null;return [200,{applied:true}];}
 if(path.endsWith('/webmail-credentials'))return authorization==='Bearer demo-owner'?[200,{email:inbox?.email,password:'fictional-webmail-password',webmail_url:'https://inbox.example.test'}]:[403,{error:'scope_denied'}];
 if(path==='/v1/settings')return [200,{webmail_url:'https://inbox.example.test',domain:'example.test',mode:'development',public_url:'http://127.0.0.1:19195'}];
 if(path==='/v1/inboxes'&&method==='POST'){inbox={id:'atlas',email:data.email,active:1};return [200,inbox];}
 if(path==='/v1/inboxes'||path==='/v1/operator/inboxes')return [200,{items:inbox?[inbox]:[],has_more:false}];
 if(path==='/v1/tokens'&&method==='POST'){issued=true;revoked=false;return [200,{id:'demo-token',token:'fictional-mail-token',scopes:['mail.read']}];}
 if(path==='/v1/operator/tokens')return [200,{items:issued?[{id:'demo-token',inbox:'atlas',scopes:'mail.read',expires:4102444800,revoked}]:[],has_more:false}];
 if(path.startsWith('/v1/tokens/')&&method==='DELETE'){revoked=true;return [200,{revoked:true}];}
 if(path==='/mcp'){if(revoked)return [401,{error:'invalid_token'}];return [200,{jsonrpc:'2.0',id:1,result:data.method==='tools/call'&&data.params.name==='read_message'?{content:[{type:'text',text:JSON.stringify({body_text:'Hi Atlas, can you summarise the project notes? Fictional local message.'})}]}:{tools:[{name:'list_folders'}]}}];}
 if(path.endsWith('/test-message')){read=true;return [200,{id:'mock-job',state:'queued'}];}
 if(path.endsWith('/messages'))return [200,read?[{uid:'1',subject:'Hello from Hermesaki',from:'sam@example.test'}]:[]];
 if(method==='DELETE'){inbox=null;return [200,{deleted:true}];}
 if(path.startsWith('/v1/operator/'))return [200,{items:[path.endsWith('/jobs')?{id:'job-demo',state:'submitted',note:'SMTP accepted; delivery not confirmed'}:path.endsWith('/deliveries')?{id:'delivery-demo',state:'dead',attempts:3,last_error:'Simulated webhook timeout; replay via API'}:path.endsWith('/drafts')?{id:'draft-demo',state:'pending',inbox:'atlas@example.test'}:path.endsWith('/audit')?{actor:'owner',action:'create_inbox',result:'ok'}:{id:'atlas',email:'atlas@example.test'}],has_more:false}];
 return [404,{error:'not_found'}];
 };
}
