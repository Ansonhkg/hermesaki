# Map this app for journey review

Use Demo Walkthrough to let the owner review the entire product from each person's perspective. The studio is a presentation and review surface. Do not add recording controls, a saved-recordings library, or app-specific studio chrome.

## Discover before building

1. Inspect the app's routes, screens, permissions, domain actions and existing tests. Identify every actor, including visitors, signed-in users, administrators and operators where applicable. Do not assume those roles exist in every app.
2. Inventory each actor's goals and all reachable journeys across landing pages, app panels, administration, operator tools and external-provider screens. Include onboarding, everyday use, settings, recovery, approvals, cancellation and failures where supported.
3. Produce a coverage table: actor, goal, entry point, screens, actions, branches, expected result, evidence and status. Label unimplemented, inaccessible and unverified paths explicitly. Never imply exhaustive coverage without reconciling this table against the app.

## Build the adapter

- Keep the shared studio unchanged. Supply actors, surfaces, workflows, stable target bindings, captions and app-specific authorization through the adapter.
- Build a DAG of meaningful actions, not just pages. Include every applicable fork, nested branch and join. Show permission failures, empty states and alternate outcomes. Represent a retry as a bounded attempt or a separate journey, not a graph cycle.
- Associate every step with its actor. Include cross-role handoffs and all relevant subdomains. Let the perspective selector filter journeys. Playback must run continuously across actors; show the actor responsible for each step in the frame header. Never block review with a handoff confirmation screen.
- Bind highlights and cursor positions to actual DOM elements using the bridge and target hooks. Scroll the correct container to the target. Capture inputs, actions and resulting states separately.
- Write short subtitles explaining what the person is trying to achieve and the observable result.

## Prepare the presentation

Use the framework runner and capture APIs during agent preparation, with authorized synthetic fixtures and isolated credentials. Supply a reviewed replay through the adapter store for each journey; the studio loads the latest available replay automatically. Keep intermediate or failed evidence outside the viewer's curated store. Do not require the owner to record anything, and never execute mutations automatically when they open the viewer.

Existing capture/runner APIs are authoring infrastructure, not user-facing recording controls. If evidence is unavailable, keep the map reviewable and label the preview honestly. Do not manufacture a successful result or replace real behavior with a scripted success screen.

## Verify and hand off

Check each journey against its expected outcomes, actor permissions and real UI. Verify target alignment, scrolling, subtitles, playback ordering and DAG navigation. Keep testing evidence separate from demonstration captures: a capture alone is not proof that a business operation passed. Report remaining coverage gaps and point the owner to the studio to review the product journey.
