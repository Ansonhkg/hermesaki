export type Scope = 'admin' | 'mail.read' | 'mail.write' | 'mail.delete';
export interface Inbox { id: string; email: string; active?: number }
export interface Page<T> { items: T[]; has_more: boolean; offset: number }
export interface Token { id: string; token: string; scopes: Scope[] }
export interface Attachment { filename: string; data: string; id?: string; content_type?: string; size?: number }
export interface MessageSummary { uid: string; folder: string; subject: string; from: string; to: string; date?: string; message_id: string }
export interface Message extends MessageSummary { body_text: string; references: string; attachments: Attachment[] }
export interface Send { to: string[]; subject: string; body_text: string; attachments?: Attachment[] }
export interface Job { id: string; state: 'queued'|'sending'|'submitted'|'failed'|'uncertain'; message_id: string }
export interface Options { baseUrl: string; token: string; access?: {clientId: string; clientSecret: string}; timeoutMs?: number; fetch?: typeof fetch }
export class HermesakiError extends Error {
  constructor(public status: number, public code: string) { super(`Hermesaki: ${code} (${status})`); this.name='HermesakiError'; }
}
const segment = encodeURIComponent;
export class Hermesaki {
  private readonly options: Options;
  constructor(options: Options) {
    const url = new URL(options.baseUrl);
    if (url.username || url.password || url.search || url.hash || (url.protocol !== 'https:' && !(url.protocol==='http:' && ['localhost','127.0.0.1','[::1]'].includes(url.hostname)))) throw new Error('Use HTTPS, or HTTP on loopback for local development');
    this.options={...options,baseUrl:options.baseUrl.replace(/\/$/,'')};
  }
  private async request<T>(path: string, method='GET', body?: unknown, key?: string): Promise<T> {
    const headers: Record<string,string>={...(this.options.token?{Authorization:`Bearer ${this.options.token}`} : {}),Accept:'application/json','User-Agent':'Hermesaki/0.1'};
    if(body!==undefined) headers['Content-Type']='application/json';
    if(key) headers['Idempotency-Key']=key;
    if(this.options.access) { headers['CF-Access-Client-Id']=this.options.access.clientId; headers['CF-Access-Client-Secret']=this.options.access.clientSecret; }
    let response: Response;
    try {response=await (this.options.fetch??fetch)(this.options.baseUrl+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),redirect:'error',signal:AbortSignal.timeout(this.options.timeoutMs??20000)});}
    catch {throw new HermesakiError(0,'connection_failed');}
    let data: any;
    try {data=await response.json();} catch {throw new HermesakiError(response.status,'invalid_response');}
    if(!response.ok) throw new HermesakiError(response.status,typeof data.error==='string' && /^[a-z_]+$/.test(data.error)?data.error:'request_failed');
    return data as T;
  }
  settings() {return this.request<{domain:string;mode:string;public_url:string}>('/v1/settings');}
  listInboxes(offset=0) {return this.request<Page<Inbox>>(`/v1/inboxes?offset=${offset}`);}
  createInbox(email:string) {return this.request<Inbox>('/v1/inboxes','POST',{email});}
  deleteInbox(id:string,confirmEmail:string) {return this.request<{deleted:boolean}>(`/v1/inboxes/${segment(id)}`,'DELETE',{confirm_email:confirmEmail});}
  createToken(inboxId:string,scopes:Scope[]=['mail.read'],ttl=2592000) {return this.request<Token>('/v1/tokens','POST',{inbox_id:inboxId,scopes,ttl});}
  revokeToken(id:string) {return this.request<{revoked:boolean}>(`/v1/tokens/${segment(id)}`,'DELETE');}
  listFolders(id:string) {return this.request<string[]>(`/v1/inboxes/${segment(id)}/folders`);}
  listMessages(id:string,options:{folder?:string;query?:string;limit?:number}={}) {return this.request<MessageSummary[]>(`/v1/inboxes/${segment(id)}/messages?${new URLSearchParams(Object.entries(options).filter(([,v])=>v!==undefined).map(([k,v])=>[k,String(v)]))}`);}
  readMessage(id:string,uid:string,folder='INBOX') {return this.request<Message>(`/v1/inboxes/${segment(id)}/messages/${segment(uid)}?folder=${segment(folder)}`);}
  send(id:string,message:Send,idempotencyKey:string) {if(!idempotencyKey)throw new Error('idempotencyKey is required');return this.request<Job>(`/v1/inboxes/${segment(id)}/messages`,'POST',message,idempotencyKey);}
  reply(id:string,uid:string,bodyText:string,idempotencyKey:string,folder='INBOX') {if(!idempotencyKey)throw new Error('idempotencyKey is required');return this.request<Job>(`/v1/inboxes/${segment(id)}/messages/${segment(uid)}/reply?folder=${segment(folder)}`,'POST',{body_text:bodyText},idempotencyKey);}
  overview<T=Record<string,unknown>>(table:string,offset=0) {return this.request<Page<T>>(`/v1/operator/${segment(table)}?offset=${offset}`);}
  async mcp<T=unknown>(method:string,params:unknown={}):Promise<T> {const r=await this.request<{result:T;error?:{message:string}}>('/mcp','POST',{jsonrpc:'2.0',id:1,method,params});if(r.error)throw new HermesakiError(200,r.error.message);return r.result;}
  localTest(id:string,key:string) {return this.request<Job>(`/v1/inboxes/${segment(id)}/test-message`,'POST',{},key);}
}
