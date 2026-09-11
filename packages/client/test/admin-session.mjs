// Real local acceptance helper. Never overwrites an existing administrator account.
import {readFile,writeFile} from 'node:fs/promises';
import {randomBytes} from 'node:crypto';
import {dirname,join} from 'node:path';
export async function administratorSession(baseUrl){
 if(!['localhost','127.0.0.1'].includes(new URL(baseUrl).hostname))throw Error('Acceptance login is local-only');
 const state=process.env.HERMESAKI_STATE||dirname(process.env.HERMESAKI_ADMIN_FILE||'.runtime/product/administrator-setup-code');
 let credentials={username:process.env.HERMESAKI_ADMIN_USERNAME,password:process.env.HERMESAKI_ADMIN_PASSWORD};
 const auth=await (await fetch(baseUrl+'/v1/auth')).json();
 if(auth.mode!=='password')throw Error('Acceptance login requires local password mode');
 const file=join(state,'acceptance-administrator.json');
 if(!credentials.password){
  try{credentials=JSON.parse(await readFile(file,'utf8'));}catch{if(auth.configured)throw Error('Set HERMESAKI_ADMIN_USERNAME and HERMESAKI_ADMIN_PASSWORD for the existing local administrator');
   credentials={username:'acceptance',password:randomBytes(24).toString('hex')};await writeFile(file,JSON.stringify(credentials),{mode:0o600,flag:'wx'});}
 }
 const headers={'Content-Type':'application/json',Origin:new URL(baseUrl).origin};
 if(!auth.configured){const setup=await fetch(baseUrl+'/v1/auth/setup',{method:'POST',headers,body:JSON.stringify({...credentials,setup_code:(await readFile(join(state,'administrator-setup-code'),'utf8')).trim()})});if(!setup.ok)throw Error('Cannot create acceptance administrator');}
 const login=await fetch(baseUrl+'/v1/session',{method:'POST',headers,body:JSON.stringify(credentials)});
 if(!login.ok)throw Error('Cannot sign in to local acceptance server');
 const cookie=login.headers.get('set-cookie').split(';')[0];
 return {credentials,cookie,fetch:(url,init)=>fetch(url,{...init,headers:{...init?.headers,Cookie:cookie,Origin:new URL(baseUrl).origin}})};
}
