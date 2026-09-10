import {installDemoBridge} from '../packages/demo-walkthrough/bridge';
import {guides} from './journeys';
installDemoBridge({parentOrigin:location.origin,enabled:async()=>['localhost','127.0.0.1'].includes(location.hostname),guides,authorize:(_,context)=>context.sample==='hermesaki-local'});
