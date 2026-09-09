#!/usr/bin/env node
import {readFile,writeFile} from 'node:fs/promises';
import {parseArgs} from 'node:util';
import {Hermesaki, Scope} from './index.js';
const usage=`hermesaki <command> [options]
  inboxes [--offset N]            List inboxes (50 per page)
  create --email EMAIL            Create/retrieve inbox
  token --inbox ID --out FILE      Issue token to a NEW private file
        [--scopes mail.read,mail.write] [--ttl SECONDS]
  revoke --id TOKEN_ID             Revoke token
  delete --inbox ID --email EMAIL  Delete with exact email confirmation
  folders --inbox ID               Check mailbox connection
  messages --inbox ID [--query TEXT]
  read --inbox ID --uid UID
  send --inbox ID --file JSON --key UNIQUE_KEY
  reply --inbox ID --uid UID --file JSON --key UNIQUE_KEY
  test-message --inbox ID --key UNIQUE_KEY  Local captured-mail only
  tools                           List MCP tools
Use HERMESAKI_URL and HERMESAKI_TOKEN_FILE (or HERMESAKI_TOKEN).
Optional CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET. No tokens in arguments.`;
async function main(){
 const {positionals,values:v}=parseArgs({allowPositionals:true,options:Object.fromEntries(['email','inbox','out','scopes','ttl','id','uid','query','file','key','offset','folder'].map(x=>[x,{type:'string' as const}]))});
 const command=positionals[0];if(!command||command==='help'){console.log(usage);return;}
 const token=process.env.HERMESAKI_TOKEN_FILE?(await readFile(process.env.HERMESAKI_TOKEN_FILE,'utf8')).trim():process.env.HERMESAKI_TOKEN;
 if(!token)throw Error('Set HERMESAKI_TOKEN_FILE or HERMESAKI_TOKEN');
 const c=new Hermesaki({baseUrl:process.env.HERMESAKI_URL??'http://localhost:19100',token,access:process.env.CF_ACCESS_CLIENT_ID?{clientId:process.env.CF_ACCESS_CLIENT_ID,clientSecret:process.env.CF_ACCESS_CLIENT_SECRET??''}:undefined});
 const need=(k:string)=>{if(!v[k])throw Error(`Missing --${k}`);return v[k]!;};
 let r:unknown;
 switch(command){
 case 'inboxes':r=await c.listInboxes(Number(v.offset??0));break;
 case 'create':r=await c.createInbox(need('email'));break;
 case 'token':{const out=need('out');const t=await c.createToken(need('inbox'),(v.scopes??'mail.read').split(',') as Scope[],Number(v.ttl??2592000));try{await writeFile(out,t.token+'\n',{mode:0o600,flag:'wx'});}catch{await c.revokeToken(t.id);throw Error('Cannot save token to a new file; issued token revoked');}r={id:t.id,scopes:t.scopes,saved:true};break;}
 case 'revoke':r=await c.revokeToken(need('id'));break;
 case 'delete':r=await c.deleteInbox(need('inbox'),need('email'));break;
 case 'folders':r=await c.listFolders(need('inbox'));break;
 case 'messages':r=await c.listMessages(need('inbox'),{query:v.query,folder:v.folder});break;
 case 'read':r=await c.readMessage(need('inbox'),need('uid'),v.folder);break;
 case 'send':r=await c.send(need('inbox'),JSON.parse(await readFile(need('file'),'utf8')),need('key'));break;
 case 'reply':r=await c.reply(need('inbox'),need('uid'),JSON.parse(await readFile(need('file'),'utf8')).body_text,need('key'),v.folder);break;
 case 'test-message':r=await c.localTest(need('inbox'),need('key'));break;
 case 'tools':r=await c.mcp('tools/list');break;
 default:throw Error('Unknown command. Run hermesaki help');
 }
 console.log(JSON.stringify(r,null,2));
}
main().catch(e=>{console.error(e instanceof Error && (e.name==='HermesakiError'||/^(Missing|Set |Unknown|Cannot|Use HTTPS)/.test(e.message))?e.message:'Command failed. Check arguments, credentials and connection.');process.exitCode=1;});
