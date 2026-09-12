import {mountDocs} from './reader.js';
const root=document.querySelector('#api-page');
const banner=root.querySelector('.demo-environment-banner');if(banner)document.body.append(banner);
try {
 const response=await fetch('/ui/api/');
 if(!response.ok)throw Error();
 const source=new DOMParser().parseFromString(await response.text(),'text/html');
 source.querySelectorAll('.demo-environment-banner').forEach(n=>n.remove());
 root.replaceChildren(...source.querySelector('main').childNodes);
 root.querySelector('#base').textContent=location.origin+'/v1';
 root.querySelector('#mcp').textContent=location.origin+'/mcp';
 const reader=mountDocs(root,'/welcome/api');reader.showRoute();
 root.addEventListener('click',event=>{
  const link=event.target.closest('a[href]');
  if(!link||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  const url=new URL(link.href);
  if(url.origin!==location.origin||!url.pathname.startsWith('/welcome/api/'))return;
  event.preventDefault();history.pushState({},'',url.pathname+url.search);reader.showRoute();
 });
 addEventListener('popstate',()=>reader.showRoute());
} catch {root.textContent='Could not load documentation. Reload to try again.';}
