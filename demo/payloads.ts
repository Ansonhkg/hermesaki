import type {Recording} from '../packages/demo-walkthrough/contracts';
// Explicit fictional examples only. Never derive payload previews from live traffic.
export function withPayloads(run:Recording):Recording {
 return {...run,captures:run.captures.map(c=>{
  if(c.check!=='server')return c;
  let payload;
  if(['credentials','get-token'].includes(c.stepId))payload={title:'Downloaded mailbox credentials',note:'Save this file. operator_token signs you into the dashboard; password signs you into webmail.',data:{email:'hi@example.test',operator_token:'demo-owner',password:'fictional-only'}};
  if(run.workflow==='inbox'&&c.stepId==='empty')payload={title:'Create an agent inbox',note:'The email address is sent to the API. The response identifies the new inbox.',data:{request:{method:'POST',path:'/v1/inboxes',body:{email:'atlas@example.test'}},response:{id:'atlas',email:'atlas@example.test',active:1}}};
  if(run.workflow==='inbox'&&c.stepId==='issued')payload={title:'Your agent’s mailbox token',note:'This fictional token grants mail.read only. Save the token when issued, then use it to connect the agent.',data:{id:'demo-token',token:'fictional-mail-token',scopes:['mail.read']}};
  return payload?{...c,payload}:c;
 })};
}
