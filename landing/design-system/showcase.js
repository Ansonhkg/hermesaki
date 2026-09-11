const u=window.ui;
document.querySelector('#components').innerHTML=[
 u.card({title:'Actions',description:'Consistent sizes, icons, states and focus treatment.',body:'<div class="examples">'+u.button({label:'Save changes',variant:'primary',icon:'check'})+u.button({label:'Cancel',variant:'outline'})+u.button({label:'Saving…',disabled:true})+'</div>'}),
 u.card({title:'Domain',description:'The domain used by your mail server.',body:'<div class="field"><label for="sample-domain">Email domain</label>'+u.input({value:'example.test',attrs:{id:'sample-domain'}})+'</div>',footer:u.button({label:'Review change',variant:'primary'})}),
 u.card({title:'Connection status',description:'Status colors remain distinct from the brand accent.',body:'<div class="examples">'+u.badge({label:'Connected',variant:'success'})+u.badge({label:'Needs verification',variant:'warning'})+u.badge({label:'Not connected',variant:'outline'})+'</div>'}),
 u.card({title:'Confirmation',description:'A shared dialog with keyboard support.',body:u.button({label:'Open example dialog',attrs:{id:'dialog-example'}})})
].join('');
document.querySelector('#dialog-example').onclick=()=>u.confirm({title:'Apply configuration?',description:'This is a component preview. No configuration will be changed.'});
