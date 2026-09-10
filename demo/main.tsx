import React from 'react';
import {createRoot} from 'react-dom/client';
import {DemoWalkthrough} from '../packages/demo-walkthrough';
import {prepareReplaySnapshot} from '../packages/demo-walkthrough/snapshot';
import {browserNavigation,browserPreferences,type StudioAdapter} from '../packages/demo-walkthrough/adapter';
import {withPayloads} from './payloads';
import {workflows,guides} from './journeys';
const adapter:StudioAdapter={id:'hermesaki-local',displayAddress:raw=>{const path=new URL(raw).pathname;if(path.startsWith('/install/'))return 'VPS terminal · installation';if(path==='/setup')return '127.0.0.1:19200/setup';if(path.startsWith('/ui/onboarding'))return 'hermesaki.anson.sh/onboarding';if(path.startsWith('/ui/api'))return 'hermesaki.anson.sh/ui/api/';return 'hermesaki.anson.sh/';},actors:[{id:'owner',label:'Owner / operator'},{id:'agent',label:'Agent'}],workflows,surfaces:[{id:'app',label:'Hermesaki · simulated services',initialPath:'/ui/onboarding/live.html',url:p=>new URL(p,location.origin).href,origins:[location.origin]}],guide:(w,s)=>guides[w+'/'+s],navigation:browserNavigation(),preferences:browserPreferences('hermesaki-demo'),store:{list:async()=>{const r=await fetch('/recordings.json');return r.ok?(await r.json()).map(withPayloads):[];},save:async()=>{throw Error('Prepare captures using npm run demo:prepare.');}},plan:w=>({prepare:async()=>({sample:'hermesaki-local'}),steps:()=>w.nodes.map(step=>({step,guide:guides[w.id+'/'+step.id]}))}),prepareSnapshot:c=>prepareReplaySnapshot(c.html,{assetOrigins:[location.origin]})};
createRoot(document.getElementById('root')!).render(<DemoWalkthrough adapter={adapter}/>);
