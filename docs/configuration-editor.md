# Server configuration

Sign in as the operator and select **Server configuration**. The page shows installed settings, the imported inventory timestamp, the Roundcube link, and a Cloudflare editor.

Connect a Cloudflare API credential, then refresh to read current mail DNS records, application Tunnel origins, and Access policies. The credential is encrypted in the existing state store. Read permission is checked during connection; write permission is checked on apply.

Select an existing resource, edit its values, and select **Review change**. Review the before/after values and explicitly confirm before applying. Plans expire after ten minutes and are rejected if the provider resource has changed. Applied resources are read back for verification. An interrupted write is reconciled without automatically repeating it; refresh restores its pending plan.

Supported edits:

- Existing mail DNS record content, TTL and MX priority.
- Existing application and webmail Tunnel origins, preserving other routes and origin settings.
- Allow policy names and additional email identities, preserving existing requirements and exclusions.
- The webmail link shown in the dashboard.

Domain replacement, resource creation/deletion and removal of Access identities are separate migrations. The editor does not claim to support these operations. A failed write whose outcome cannot be reconciled requires inspecting Cloudflare before further changes.

Validation: backend tests cover conflicts, exact confirmation, uncertain writes and preserved configuration. Browser checks use a simulated provider. Read-only production inventory is verified separately; these checks do not prove every production write permission.
