import type {Workflow} from '../packages/demo-walkthrough/contracts';
const rows=[
 ['setup','Install and set up your server',[
 ['clone','Get Hermesaki','#install-step','Clone the repository. This terminal is an illustration, not an executed installation.'],
 ['vps','Clone on your VPS','#install-step','Connect over SSH and clone directly on the server.'],
 ['upload','Or upload your checkout','#install-step','Alternative to cloning on the VPS. Exclude runtime data and credentials.'],
 ['boot','Start setup','#install-step','Run make setup on the VPS.'],
 ['tunnel','Open private setup','#install-step','Forward the private port from your computer and open the wizard.'],
 ['bootstrap','Read bootstrap credential','#install-step','Read the bootstrap-token file privately, then enter it into the next screen.'],

 ['claim','Claim the installation','#claim','Enter fictional bootstrap and owner credentials.'],
 ['domain','Connect your domain','#configuration','Save example.test and a documentation-only IP address.'],
 ['cloudflare','Prepare web protection','#cloudflare','Review the simulated Cloudflare plan before applying.'],
 ['review','Review protection changes','#provider-review','Confirm the exact plan. No real DNS records are changed.'],
 ['services','Plan mail services','#services','Choose the first mailbox and prepare private services.'],
 ['deploy','Review and deploy','#service-review','The local adapter simulates service deployment.'],
 ['credentials','Download your credentials','#download-mailbox','Click Download mailbox credentials. Save this JSON file: it contains the operator token needed at sign-in.'],
 ['signing','Prepare signing records','#dkim','Prepare fictional DKIM records.'],
 ['publish','Review signing records','#dkim-review','Confirm the simulated signing record plan.'],
 ['verify','Verify installation','#runtime-verification','Provider and delivery checks are simulated here. Production requires real checks.'],
 ['ready','Review checks','#runtime-checks','These results are illustrative, not evidence of public delivery.'],
 ['finish','Finish setup','#complete-setup','Finish the simulated setup and hand over to daily operation.'],
 ['complete','Ready for daily use','main','The first-run flow hands over to the mailbox operator.'],
 ]],
 ['inbox','Create an agent inbox',[
 ['get-token','Download operator credentials','#download-mailbox','During setup, click Download mailbox credentials. This downloads the JSON file containing your operator token. Keep it private.'],
 ['login','Sign in','#login','Use the saved operator credential. Cloudflare login alone does not authorize mailbox management.'],
 ['invalid','Find your saved credentials','#token-file','Choose the hermesaki-mailbox-credentials.json file downloaded during setup using this file picker.'],
 ['file','Credentials file selected','#login-form','The operator token is loaded from the selected file. Click Connect to sign in.'],
 ['empty','Create an agent email','#create','No inboxes yet. Create Atlas using fictional data.'],
 ['issued','Save scoped access','#issued','A read-only mailbox token is issued. Save it before leaving.'],
 ['connected','Check MCP','#checked','The mock MCP endpoint responds. Real connections use the same permission boundary.'],
 ['message','Read incoming mail','#messages','A fictional message arrives locally. Nothing is sent externally.'],
 ['read','Agent reads message','#message-body','Read the fictional message through the mocked MCP interface.'],
 ['revoke','Revoke access','#tokens','Revoke the token when this agent should no longer access mail.'],
 ['revoked','Access retired','#tokens','The revoked token is inactive and the connection controls are cleared.'],
 ['delete','Remove inbox','details','Deletion requires the exact mailbox address.'],
 ['deleted','Inbox removed','#create','The fictional inbox has been removed.'],
 ]],
 ['operator','Manage mail operations',[
 ['op-login','Sign in as operator','#connect','Enter the operator token saved during setup.'],
 ['op-inboxes','Review inboxes','#results','Inspect fictional mailbox metadata.'],
 ['op-jobs','Review jobs','#results','Submitted means SMTP accepted the message, not final recipient delivery.'],
 ['op-deliveries','Inspect failed delivery','#results','A failed webhook is shown. This UI is read-only; replay is an API operation.'],
 ['op-drafts','Review drafts','#results','Inspect draft metadata. Sending approval uses the API.'],
 ['op-tokens','Inspect tokens','#results','View scoped token metadata. Manage tokens through agent inbox setup.'],
 ['op-audit','Read audit history','#results','Review fictional operator activity without message bodies.']
 ]]
] as const;
export const workflows:Workflow[]=rows.map(([id,title,steps])=>({id,title,version:'1',description:'Local demonstration using the real forms and fictional service responses. No production operations.',defaultActor:'owner',nodes:steps.map(([id,label,selector,expected])=>({id,label,expected,surface:'app',actor:['connected','read'].includes(id)?'agent':'owner',path:''})),edges:[...steps.slice(1).map((s,i)=>[steps[i][0],s[0]] as [string,string]),...(id==='inbox'?[['login','empty'],['read','delete']] as [string,string][]:[])],route:steps.map(s=>s[0])}));
export const guides=Object.fromEntries(rows.flatMap(([w,,steps])=>steps.map(([id,,selector,caption])=>[w+'/'+id,{selector,caption,action:'inspect' as const}])));
