// Fictional examples only: this module never calls a mail or agent service.
const examples = {
  send: {
    prompt: 'Send an email to alex@example.net. Subject: “Weekly update”. Body: “The report is ready for your review.”',
    response: 'The mail server accepted your email for sending. Recipient delivery is not yet confirmed.',
    title: 'Email submitted', badge: 'Submitted to SMTP',
    fields: [['From', 'atlas@example.com'], ['To', 'alex@example.net'], ['Subject', 'Weekly update']],
    message: 'The report is ready for your review.',
    note: 'Submission confirms the server accepted the message. Confirm receipt separately.'
  },
  read: {
    prompt: 'Read the latest email from Alex and tell me what needs my attention.',
    response: 'Alex has reviewed your report and would like to meet on Thursday at 2 pm. They’re waiting for you to confirm.',
    title: 'Incoming message', badge: 'Read from inbox',
    fields: [['From', 'alex@example.net'], ['To', 'atlas@example.com'], ['Subject', 'Re: Weekly update']],
    message: 'Thanks for the report! Could we go through it together on Thursday at 2 pm?',
    note: 'Your agent summarizes the message. Read-only access is enough for this request.'
  },
  reply: {
    prompt: 'Reply to Alex’s email about the weekly update: “Thursday at 2 pm works for me. See you then!”',
    response: 'Your reply was submitted in the same email conversation. Recipient delivery is not yet confirmed.',
    title: 'Reply submitted', badge: 'Conversation preserved',
    fields: [['From', 'atlas@example.com'], ['To', 'alex@example.net'], ['Subject', 'Re: Weekly update']],
    message: 'Thursday at 2 pm works for me. See you then!',
    note: 'Replying requires read and sending permissions. The original message provides the reply headers.'
  }
};
const root = document.querySelector('.mail-examples');
if (root) {
  const find = selector => root.querySelector(selector);
  const copy = find('[data-copy-example]');
  let selected = 'send';
  let reset;
  function render() {
    const query = new URL(location.href).searchParams.get('example');
    selected = Object.hasOwn(examples, query) ? query : 'send';
    const item = examples[selected];
    clearTimeout(reset); copy.textContent = 'Copy prompt';
    for (const [selector, value] of Object.entries({prompt:item.prompt, response:item.response, 'result-title':item.title, badge:item.badge, message:item.message, note:item.note})) {
      find(`[data-example-${selector}]`).textContent = value;
    }
    const fields = find('[data-example-fields]'); fields.replaceChildren();
    for (const [label, value] of item.fields) {
      const row = document.createElement('div');
      const dt = document.createElement('dt'); dt.textContent = label;
      const dd = document.createElement('dd'); dd.textContent = value;
      row.append(dt, dd); fields.append(row);
    }
    root.querySelectorAll('[data-example]').forEach(link => {
      if (link.dataset.example === selected) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const target = new URL(link.href);
    if (target.origin !== location.origin || target.pathname !== '/welcome' || !Object.hasOwn(examples, target.searchParams.get('example'))) return;
    event.preventDefault();
    if (target.href !== location.href) history.pushState(null, '', target.href);
    render();
    if (!root.contains(link)) root.scrollIntoView({block:'start'});
  });
  copy.onclick = async () => {
    const current = selected;
    try {
      await navigator.clipboard.writeText(examples[current].prompt);
      if (selected !== current) return;
      copy.textContent = 'Copied ✓';
    } catch {
      if (selected !== current) return;
      copy.textContent = 'Select to copy';
      const selection = window.getSelection(); const range = document.createRange();
      range.selectNodeContents(find('[data-example-prompt]')); selection.removeAllRanges(); selection.addRange(range);
    }
    clearTimeout(reset); reset = setTimeout(() => { copy.textContent = 'Copy prompt'; }, 2200);
  };
  copy.setAttribute('aria-live', 'polite');
  window.addEventListener('popstate', render);
  render();
  if (Object.hasOwn(examples, new URL(location.href).searchParams.get('example'))) {
    requestAnimationFrame(() => root.scrollIntoView({block:'start'}));
  }
}
