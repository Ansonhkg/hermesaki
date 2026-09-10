# Demo Walkthrough integration

The standalone demo-walkthrough repository owns this versioned module. Apps and ReleaseFast copy it; no runtime link to that repository or npm package is required. Requires React 19, React DOM, TypeScript and a CSS-capable bundler.

```sh
node src/demo-walkthrough/sync.mjs /path/to/app/packages/demo-walkthrough
node src/demo-walkthrough/sync.mjs /path/to/app/packages/demo-walkthrough --check
```

```tsx
import {DemoWalkthrough} from './packages/demo-walkthrough';
import {adapter} from './my-product/demo-adapter';
export function Demonstrations() { return <DemoWalkthrough adapter={adapter}/>; }
```

Keep the adapter object stable. The framework owns the controller, UI, playback, journey selection and DAG navigation, cursor geometry, click pulses, transport correlation/cancellation, recording lifecycle, target resolution, capture mechanics and sanitized replay. `StudioController` is the internal presentation port; hosts do not implement its state/setters.

## Adapter contract

`StudioAdapter` in adapter.ts supplies:

- `workflows`: versioned nodes with explicit actors, edges, traversal route, optional chapters/branches and perspective titles.
- `actors` and `surfaces`: names, initial routes, URL resolvers and exact permitted origins. Include each provider origin explicitly.
- `guide`: product captions and actions. Target recipes use stable target IDs or selectors with scoped text and context interpolation.
- `store.list/save`: host-owned recording persistence and authorization. Enforce validation and ownership on the server; client config does not grant access.
- `plan`: domain preparation and planned steps. Shared runWalkthrough handles waiting, cancellation, capture, action execution, progress persistence and failure evidence. Domain callbacks implement dynamic URLs, fixtures, manual steps and outcome checks.
- `prepareSnapshot`: call prepareReplaySnapshot with explicitly allowed asset origins and optional legacy target resolver.
- Optional navigation, subtitle preferences and development details. Details are explicit opt-in display values, never automatically inferred passwords.

Mount outside product navigation. Standalone Studio does not require an operator console, backend framework, account shape or fixed number of surfaces. browserNavigation and browserPreferences are optional conveniences. Use another implementation when embedding or rendering in a different routing environment.

## Instrument participating pages

Call `installDemoBridge` on each approved live app/provider page. Supply an exact parent origin, an asynchronous enabled policy, registered recipes and an action authorization callback. The bridge verifies parent source, origin, protocol and nonce. Use its returned disposer for teardown. Never make production authorization depend on a synthetic name alone.

```tsx
const target = useDemoTarget('document.submit');
return <button ref={target}>Submit for review</button>;
```

A recipe `{target:'document.submit', caption:'Submit the document', action:'click'}` works without matching product text/classes. Legacy selectors remain supported. Multi-input actions declare `fields` explicitly. Context interpolation is generic; no email or password fields are assumed by the framework.

The bridge captures DOM/CSS, strips executable content and input values, preserves the exact marked target, and only retains values/context expressly approved by the adapter. Host policies must strip secrets from text and attributes too; this is not a universal PII detector. Replay has no script execution, form submission or navigable links. External fonts/images need explicit approved asset origins. Cross-origin stylesheets, canvas/video state and inaccessible shadow content require host capture extensions; the DOM recorder does not promise pixel-perfect recording of every browser primitive.

## Recording compatibility

New recordings freeze a schema version, workflow definition, captions and confirmed click cues. Replay uses captured target markers. Legacy captures can use a host resolver/current guide fallback and are not retroactively verified. Coverage without an explicit passed outcome is labelled unverified. Original timestamps remain evidence; the paced review clock is separate.

A DAG defines dependencies/choices; `route` defines the selected traversal. Chapters define playback grouping. Domain fixture lifecycle and branch prerequisites belong in the execution plan; the engine does not invent paths or claim every possible branch ran.

## Updating

Change canonical source, bump version.json, regenerate the manifest, run checks, then sync consumers. Sync rejects local edits, symlinks, unmanaged files, stale files during check, and mismatched manifests. Removed managed files are deleted only when unchanged from the previous manifest. No cross-repository dependency is introduced.

## Agent preparation

Read [AGENT-BRIEF.md](AGENT-BRIEF.md) to inventory actors and journeys and prepare reviewed replay evidence. The viewer has no recording controls or saved-recordings library. Recording and storage APIs remain available to authoring tools.
