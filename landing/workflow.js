// Illustrative progress only. This preview never runs setup or contacts providers.
const steps = [
  {name:'Tell your agent', title:'An email address. A few details.', description:'Paste the setup prompt into your agent. It asks for your domain, the address you want and access to your server. It reuses anything you have already shared.', screen:'Your agent checks what is ready', tasks:[['Domain and email address','Needs your input'],['Server and account access','Checking'],['Existing websites and mail','Next']], request:'Choose your address and share access.', help:'For example: “Create atlas@example.com.” Open Cloudflare and your server provider in the connected browser, sign in, and share the tabs with your agent.'},
  {name:'Let it set up', title:'Your agent does the setup.', description:'Your agent installs the mail services, connects the domain and configures protection. Follow its progress while it handles the technical steps.', screen:'Your agent is configuring email', tasks:[['Server requirements checked','Done'],['Email and protection','In progress'],['Mailbox and agent connection','Next']], request:'Step in when a decision needs you.', help:'Your agent asks if it needs sign-in verification, approval for a purchase or permission to change existing mail routing. Routine configuration stays with the agent.'},
  {name:'Start using email', title:'A working inbox, ready for you.', description:'Your agent tests webmail and its own connection, checks delivery in both directions, and gives you the links and securely saved credentials.', screen:'Your agent verifies the result', tasks:[['Webmail and agent connection','Checked'],['Sending and receiving','Awaiting confirmation'],['Access details and backup instructions','Next']], request:'Confirm the test email and reply.', help:'Open your existing inbox and check Spam or Junk too. You can reply yourself, or authorize your agent to use a shared email tab. Setup finishes after the checks pass.'}
];
const root = document.querySelector('#workflow-demo');
let current = 0;
const $ = selector => root.querySelector(selector);
for (const [index, step] of steps.entries()) {
  const button = document.createElement('button');
  button.type = 'button'; button.textContent = step.name;
  button.onclick = () => { current = index; render(); };
  $('.workflow-steps').append(button);
}
function render() {
  const step = steps[current];
  $('[data-workflow-title]').textContent = step.title;
  $('[data-workflow-description]').textContent = step.description;
  $('[data-workflow-screen-title]').textContent = step.screen;
  $('[data-workflow-request]').textContent = step.request;
  $('[data-workflow-help]').textContent = step.help;
  const screen = $('[data-workflow-screen]'); screen.replaceChildren();
  for (const [label, state] of step.tasks) {
    const row = document.createElement('div'); row.className = 'agent-progress-row';
    const name = document.createElement('span'); name.textContent = label;
    const badge = document.createElement('span'); badge.className = 'agent-progress-state'; badge.textContent = state;
    if (['Done','Checked'].includes(state)) badge.classList.add('complete');
    row.append(name, badge); screen.append(row);
  }
  $('[data-workflow-progress]').textContent = `Preview ${current + 1} of ${steps.length}`;
  $('[data-workflow-prev]').disabled = current === 0;
  $('[data-workflow-next]').disabled = current === steps.length - 1;
  [...$('.workflow-steps').children].forEach((button,index) => button.setAttribute('aria-current', index === current ? 'step' : 'false'));
}
$('[data-workflow-prev]').onclick = () => { if (current > 0) { current--; render(); } };
$('[data-workflow-next]').onclick = () => { if (current < steps.length - 1) { current++; render(); } };
render();
