import {connectFrame} from '../packages/demo-walkthrough/transport';
(window as any).rpc=(type:string,key:string)=>connectFrame({frame:document.querySelector('iframe')!,origin:location.origin,nonce:'local-author'},type,key,{sample:'hermesaki-local'});
