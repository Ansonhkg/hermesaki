# Hermesaki shared UI

Adapted from Codex-Linus commit 55aefefa3621d9f3d74f022ed1eaf997a323f2b3, with the owner's authorization.

Copied sources: `src/manager/ui-kit.js`, `ui-icons.js`, `styles/components.css`, and `styles/theme.css`.

This is Basecoat 1.0.2 (Vega) with Tailwind 4.3.3 and Lucide icon markup, not the React shadcn package. The shared renderers expose `window.ui`. No Codex-Linus server, authentication or product API is included.

Change Hermesaki colors in `theme.css`. Keep layout adaptations in `operator.css`. Build the stylesheet with `npm run build:ui`. The generated stylesheet is included so existing Python/Docker serving works without a Node runtime.

Open `/ui/design-system/showcase.html` for representative components in the Hermesaki theme. The operator dashboard now uses server-side sessions with a Secure/HttpOnly cookie in HTTPS deployments, expiry, revocation checks and same-origin protection for cookie-authenticated writes. API docs are embedded under /docs.
