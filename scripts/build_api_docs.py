"""Build the in-app reference from the repository's canonical Markdown docs."""
from pathlib import Path
import html, re
ROOT = Path(__file__).resolve().parents[1]
def inline(s):
    s = html.escape(s)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
def render(text):
    out=[]; code=None; table=False
    for line in text.splitlines()+['']:
        if line.startswith('```'):
            if code is None: code=[]
            else:
                out.append('<div class="example"><button type="button">Copy</button><pre><code>'+html.escape('\n'.join(code))+'</code></pre></div>');code=None
            continue
        if code is not None: code.append(line);continue
        if table and not line.startswith('|'):out.append('</tbody></table></div>');table=False
        if line.startswith('|'):
            if re.match(r'^\|[\s:|\-]+$',line):continue
            cells=line.strip('|').split('|')
            if not table:
                out.append('<div class="table"><table><thead><tr>'+''.join('<th>'+inline(c.strip())+'</th>' for c in cells)+'</tr></thead><tbody>');table=True
            else:out.append('<tr>'+''.join('<td>'+inline(c.strip())+'</td>' for c in cells)+'</tr>')
        elif line == '<!-- cloudflare-credentials-guide -->':out.append((ROOT/'landing/api/cloudflare-credentials.html').read_text())
        elif line == '<!-- mcp-client-guide -->':out.append('<div data-mcp-guide></div>')
        elif line.startswith('#'):
            level=min(len(line)-len(line.lstrip('#'))+1,4);out.append(f'<h{level}>'+inline(line.lstrip('# ').strip())+f'</h{level}>')
        elif line:out.append('<p>'+inline(line)+'</p>')
    return '\n'.join(out)
body=''.join('<section id="'+ident+'">'+render((ROOT/'docs'/file).read_text())+'</section>' for ident,file in [('reference','api.md'),('clients','typescript.md')])
page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>API documentation · Hermesaki</title><link rel="stylesheet" href="/ui/api/style.css"><script src="/ui/api/docs.js" defer></script></head><body><header><a href="/">Hermesaki</a><nav><a href="/ui/onboarding/live.html">Agent inboxes</a><a href="#reference">API reference</a><a href="#clients">SDK & CLI</a></nav></header><main><h1>Build with your inbox.</h1><p>Read messages, connect an agent, and send with explicit permissions.</p><p>API base: <code id="base">Your installation origin</code> · MCP: <code id="mcp">/mcp</code></p><p>These examples do not execute requests. Replace placeholder inbox IDs and load credentials from your secret manager.</p>'''+body+'''<p id="copy-status" role="status" aria-live="polite"></p></main></body></html>'''
(ROOT/'landing/api/index.html').write_text(page)
