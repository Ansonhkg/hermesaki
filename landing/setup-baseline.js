const button = document.querySelector('[data-baseline-copy]');
const status = document.querySelector('[data-baseline-status]');
button.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(document.querySelector('#baseline-prompt').value);
    status.textContent = 'Copied';
  } catch {
    document.querySelector('.baseline-prompt').open = true;
    document.querySelector('#baseline-prompt').select();
    status.textContent = 'Select and copy the prompt below';
  }
});
if (new URLSearchParams(location.search).get('view') === 'improve') {
  document.querySelector('[data-improvement-section]').scrollIntoView();
}
