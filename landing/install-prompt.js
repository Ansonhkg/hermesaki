const panel = document.querySelector('[data-install-prompt]');
if (panel) {
  const button = panel.querySelector('button');
  const preview = panel.querySelector('textarea');
  const status = panel.querySelector('[role="status"]');
  let reset;
  try {
    const response = await fetch('/ui/install-prompt.txt');
    if (!response.ok) throw new Error('Prompt unavailable');
    const prompt = await response.text();
    preview.value = prompt;
    button.disabled = false;
    status.textContent = '';
    button.addEventListener('click', async () => {
      clearTimeout(reset);
      try {
        await navigator.clipboard.writeText(prompt);
        button.textContent = 'Copied';
        status.textContent = 'Paste into your agent to get started.';
        reset = setTimeout(() => { button.textContent = 'Copy setup prompt'; status.textContent = ''; }, 4000);
      } catch {
        panel.querySelector('details').open = true;
        preview.focus();
        preview.select();
        status.textContent = 'Press ⌘C or Ctrl+C to copy the selected prompt.';
      }
    });
  } catch {
    panel.querySelector('details').open = true;
    status.textContent = 'Could not load the prompt. Open the text version below.';
  }
}
