document.querySelector('#base').textContent=location.origin+'/v1';
document.querySelector('#mcp').textContent=location.origin+'/mcp';
for(const button of document.querySelectorAll('.example button'))button.onclick=async()=>{try{await navigator.clipboard.writeText(button.parentElement.querySelector('code').textContent);document.querySelector('#copy-status').textContent='Example copied. Replace placeholders before using it.';}catch{document.querySelector('#copy-status').textContent='Select the example and copy it manually.';}};
