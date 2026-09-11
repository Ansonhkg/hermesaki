# Hermesaki shared UI

Adapted from Codex-Linus commit 55aefefa3621d9f3d74f022ed1eaf997a323f2b3, with the owner's authorization.

Copied sources: `src/manager/ui-kit.js`, `ui-icons.js`, `styles/components.css`, and `styles/theme.css`.

This is Basecoat 1.0.2 (Vega) with Tailwind 4.3.3 and Lucide icon markup, not the React shadcn package. The shared renderers expose `window.ui`. No Codex-Linus server, authentication or product API is included.

Change Hermesaki colors in `theme.css`. Keep layout adaptations in `operator.css`. Build the stylesheet with `npm run build:ui`. The generated stylesheet is included so existing Python/Docker serving works without a Node runtime.

Open `/ui/design-system/showcase.html` for representative components in the Hermesaki theme. The operator dashboard now uses server-side sessions with a Secure/HttpOnly cookie in HTTPS deployments, expiry, revocation checks and same-origin protection for cookie-authenticated writes. API docs are embedded under /docs.

### Shared forms
`forms.css` owns label spacing (8px), field spacing (20px), action spacing (12px), 40px controls and select chevrons (12px inset with 40px text clearance). Load it after page styles. Do not add page-specific label/control spacing overrides. Use `.form-actions` for action rows and `secretField()` for sensitive inputs; its inline feedback must not change layout. Wrapped and `for`-associated labels both follow this contract.

## Dashboard integration contract

All authenticated routes render `src/hermesaki/operator.html`. Never replace a route with a separate preview document or duplicate its sidebar. The local Vite server serves the same shell and modules as production; only `/v1` responses are simulated. `/` is the dashboard; `/?workflow=…` explicitly opens the walkthrough.

`operator.css` owns sidebar width, page gutters, card spacing and responsive breakpoints. `forms.css` owns label gaps, control height, select chevrons and action spacing. `secret-field.js` owns reveal/copy behavior and inline feedback. `settings.css` owns setting cards and the shared tab treatment. Settings mutations use the server plan/apply endpoints, never localStorage.

Before reporting a dashboard change complete, inspect Overview, Inboxes, Agent access, Activity, Settings and Docs in the browser. Check route refresh, a single sidebar selection, card gaps, no horizontal page overflow, fixed environment banner, and an edit → review → apply → refresh flow. Do not equate mock verification with production provider verification.

`tables.css` owns dashboard table sizing: headers and values stay on one line without truncation. Tables use intrinsic column widths inside horizontal scroll containers; never force narrow columns or wrap identifiers.

Internal dashboard links are handled by the shell's client-side route dispatcher. It intercepts ordinary same-origin navigation only; modified clicks, downloads and external links retain native browser behavior. Back/Forward renders the current route without reloading. Documentation keeps its mounted reader and search state between chapters and dashboard sections. Do not add `location.reload()` or native navigation for internal page changes.
