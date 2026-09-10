import React from 'react';
import {createRoot} from 'react-dom/client';
import {DemoWalkthrough} from '../packages/demo-walkthrough';
import {prepareReplaySnapshot} from '../packages/demo-walkthrough/snapshot';
import {browserNavigation,browserPreferences,type StudioAdapter} from '../packages/demo-walkthrough/adapter';
import {workflows,guides} from './journeys';
const adapter:StudioAdapter={id:'hermesaki-local',actors:[{id:'owner',label:'Owner / operator'},{id:'agent',label:'Agent'}],workflows,surfaces:[{id:'app',label:'Hermesaki · simulated services',initialPath:'/ui/onboarding/live.html',url:p=>new URL(p,location.origin).href,origins:[location.origin]}],guide:(w,s)=>guides[w+'/'+s],navigation:browserNavigation(),preferences:browserPreferences('hermesaki-demo'),store:{list:async()=>{const r=await fetch('/recordings.json');return r.ok?r.json():[];},save:async()=>{throw Error('Prepare captures using npm run demo:prepare.');}},plan:w=>({prepare:async()=>({sample:'hermesaki-local'}),steps:()=>w.nodes.map(step=>({step,guide:guides[w.id+'/'+step.id]}))}),prepareSnapshot:c=>prepareReplaySnapshot(c.html)};
createRoot(document.getElementById('root')!).render(<DemoWalkthrough adapter={adapter}/>);
