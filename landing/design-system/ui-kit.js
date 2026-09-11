/**
 * Shared UI kit for the sandbox manager — the design system's component layer.
 *
 * Purpose: one markup function per control, all emitting Basecoat (shadcn/ui in
 * plain HTML) markup styled by /manager.css and the tokens in styles/theme.css.
 * Product views and the Design page (/#settings/design) call the same
 * renderers, so a change here updates every surface.
 *
 * Rules:
 *   - Icons come from ui-icons.js (Lucide) through ui.icon(). No glyphs, no
 *     inline paths.
 *   - Buttons are `.btn` with data-variant / data-size. Use ui.button() or
 *     ui.iconButton().
 *   - Overlays (dialogs, menus, toasts) go through ui.openDialog(), ui.confirm(),
 *     ui.openMenu() and ui.toast() so behaviour and styling stay uniform.
 *
 * Usage: served at /ui-kit.js after /ui-icons.js and before design-settings.js
 * and group-ui.js. Access everything on window.ui.
 */

/* ------------------------------------------------------------------------- */
/* Configuration                                                              */
/* ------------------------------------------------------------------------- */

/**
 * Icon set: Lucide markup generated into ui-icons.js by scripts/build-icons.ts.
 * Add icons there, never inline SVG paths or unicode glyphs in views.
 */
const UI_ICONS = window.UI_ICONS || {};
const UI_ICON_NAMES = Object.keys(UI_ICONS);
const UI_ICON_FALLBACK = 'file';

/** Button variants and sizes accepted by ui.button() (Basecoat data attributes). */
const UI_BUTTON_VARIANTS = ['primary', 'secondary', 'outline', 'ghost', 'link', 'destructive'];
const UI_BUTTON_SIZES = ['xs', 'sm', 'default', 'lg', 'icon', 'icon-xs', 'icon-sm', 'icon-lg'];
const UI_DEFAULT_BUTTON_VARIANT = 'secondary';

/** Badge variants (Basecoat data-variant). */
const UI_BADGE_VARIANTS = ['primary', 'secondary', 'outline', 'destructive', 'success', 'warning'];

/** Default emoji used when a sandbox has no avatar chosen. Avatars are content, not icons. */
const UI_DEFAULT_AVATAR = '🤖';

/** Toast lifetime in ms; errors stay longer. */
const UI_TOAST_DURATION = 3200;

/** How long a clipboard button shows its "copied" tick. */
const UI_COPY_FEEDBACK_MS = 1400;
const UI_TOAST_ERROR_DURATION = 6000;

/** Narrowest menu a settings dropdown opens; wider triggers widen it to match. */
const UI_DROPDOWN_MENU_MIN_WIDTH = 160;

/** Reasoning effort options shared by the agent settings dropdowns and the Design page. */
const UI_REASONING_OPTIONS = [{value: 'low', label: 'Light'}, {value: 'medium', label: 'Medium'}, {value: 'high', label: 'High'}, {value: 'xhigh', label: 'Extra high'}];

/** Colour tokens from :root, grouped as they are used. Values are read live so the swatches never drift. */
const UI_COLOR_TOKENS = [
  {group: 'Surfaces', names: ['background', 'sidebar', 'card', 'popover', 'secondary', 'muted', 'accent', 'elevated']},
  {group: 'Overlays (hover and selection on dark surfaces)', names: ['overlay-1', 'overlay-2', 'overlay-3', 'backdrop']},
  {group: 'Borders and focus', names: ['border', 'border-strong', 'input', 'ring']},
  {group: 'Text', names: ['foreground', 'muted-foreground', 'faint']},
  {group: 'Primary and brand', names: ['primary', 'primary-foreground', 'brand', 'brand-strong']},
  {group: 'Status', names: ['success', 'warning', 'danger', 'info', 'destructive']}
];

/** Type scale in use across the manager: size, line-height and where it appears. */
const UI_TYPE_SCALE = [
  {size: 18, line: 26, weight: 400, label: 'Page title', sample: 'Design'},
  {size: 14, line: 20, weight: 500, label: 'Section or component title', sample: 'Composer'},
  {size: 13, line: 18, weight: 400, label: 'Body, buttons, inputs', sample: 'Manage your local autonomous sandboxes.'},
  {size: 12, line: 18, weight: 400, label: 'Secondary text, chips, sidebar', sample: 'Sidebar and command-palette query field.'},
  {size: 11, line: 16, weight: 400, label: 'Captions, eyebrow labels, timestamps', sample: 'Queued tasks · 14:25'}
];

/** Spacing steps (px) used for padding and gaps. */
const UI_SPACING_SCALE = [4, 8, 12, 16, 24, 32];

/** Corner radii and the controls that use them. */
const UI_RADIUS_SCALE = [
  {value: 6, label: 'radius-sm · chips, small controls'},
  {value: 8, label: 'radius-md · buttons, inputs, rows'},
  {value: 10, label: 'radius-lg · menus, popovers'},
  {value: 14, label: 'radius-xl · cards, dialogs'},
  {value: 999, label: 'pill · avatars, badges'}
];

/** Elevation levels: surface colour plus shadow. */
const UI_ELEVATION_SCALE = [
  {label: 'Flat', detail: 'Page and grouped rows', style: 'background:var(--card)'},
  {label: 'Raised', detail: 'Cards and settings groups', style: 'background:var(--secondary)'},
  {label: 'Floating', detail: 'Menus and toasts', style: 'background:var(--popover);box-shadow:var(--shadow-floating)'},
  {label: 'Modal', detail: 'Dialogs', style: 'background:var(--popover);box-shadow:var(--shadow-modal)'}
];

/* ------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* ------------------------------------------------------------------------- */

function uiEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

/** Serialise an attribute map; `true` renders a bare attribute, false/null/undefined are skipped. */
function uiAttrs(attrs) {
  return Object.entries(attrs || {}).filter(([, v]) => v !== undefined && v !== false && v !== null)
    .map(([k, v]) => v === true ? k : `${k}="${uiEscape(v)}"`).join(' ');
}

/** Join class names, dropping empties. */
function uiClass(...names) {
  return names.filter(Boolean).join(' ');
}

let uiIdCounter = 0;
/** Unique DOM id with a readable prefix. */
function uiId(prefix = 'ui') {
  uiIdCounter += 1;
  return `${prefix}-${uiIdCounter}`;
}

/**
 * Read a CSS custom property from :root. Falls back to the raw var() so a
 * missing token is still visible on the Design page.
 * @param {string} name token name without the leading dashes
 */
function uiToken(name) {
  const value = typeof getComputedStyle === 'function'
    ? getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim()
    : '';
  return value || `var(--${name})`;
}

/* ------------------------------------------------------------------------- */
/* Icons                                                                      */
/* ------------------------------------------------------------------------- */

/**
 * Shared Lucide glyph. Every icon in the product renders through this.
 * @param {string} name semantic icon name from ui-icons.js
 * @param {{active?: boolean, className?: string}} [opts]
 */
function uiIcon(name = 'file', {active = false, className = ''} = {}) {
  const key = UI_ICONS[name] ? name : UI_ICON_FALLBACK;
  const cls = uiClass('icon', `icon-${key}`, active && 'is-active', className);
  return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${UI_ICONS[key] || ''}</svg>`;
}

/** Design catalogue tiles. Each tile is an icon button around uiIcon. */
function uiIcons() {
  const tiles = UI_ICON_NAMES.map((name) => `<div class="design-icon">${uiIconButton({name, label: `${name} inactive`, className: 'design-icon-box', attrs: {'data-icon': name, 'aria-pressed': 'false', onclick: 'designToggleIcon(this)'}})}<small>${uiEscape(name)}</small></div>`).join('');
  return `<div class="design-icon-panel"><div class="design-icon-toolbar" role="group" aria-label="Icon state">${uiButton({label: 'Inactive', variant: 'secondary', size: 'xs', attrs: {'data-icon-state': 'false', 'aria-pressed': 'true', onclick: 'designSetIcons(false)'}})}${uiButton({label: 'Active', variant: 'ghost', size: 'xs', attrs: {'data-icon-state': 'true', 'aria-pressed': 'false', onclick: 'designSetIcons(true)'}})}</div><div class="design-icons">${tiles}</div></div>`;
}

/* ------------------------------------------------------------------------- */
/* Foundations (Design page)                                                  */
/* ------------------------------------------------------------------------- */

/**
 * Wrap a preview in a labelled state so mutually exclusive states read as
 * separate examples.
 * @param {Array<{label: string, html: string}>} states
 */
function uiStates(states) {
  return states.map(({label, html}) => `<div class="design-state"><small>${uiEscape(label)}</small><div class="design-state-body">${html}</div></div>`).join('');
}

/** Colour swatches for every token, grouped by role. */
function uiColorTokens() {
  return UI_COLOR_TOKENS.map(({group, names}) => `<div class="design-token-group"><small>${uiEscape(group)}</small><div class="design-swatches">${names.map((name) =>
    `<div class="design-swatch"><span class="design-swatch-chip" style="background:var(--${name})"></span><code>--${uiEscape(name)}</code><small>${uiEscape(uiToken(name))}</small></div>`
  ).join('')}</div></div>`).join('');
}

/** Type scale with live samples at each size. */
function uiTypeScale() {
  const family = typeof getComputedStyle === 'function' ? getComputedStyle(document.body).fontFamily.split(',')[0].replace(/["']/g, '') : 'system-ui';
  const rows = UI_TYPE_SCALE.map((t) => `<div class="design-type-row"><span class="design-type-sample" style="font-size:${t.size}px;line-height:${t.line}px;font-weight:${t.weight}">${uiEscape(t.sample)}</span><span class="design-type-meta"><strong>${t.size}/${t.line}${t.weight !== 400 ? ` · ${t.weight}` : ''}</strong><small>${uiEscape(t.label)}</small></span></div>`).join('');
  return `<div class="design-type"><div class="design-type-family"><small>Family</small><code>${uiEscape(family)}</code></div>${rows}</div>`;
}

/** Spacing steps drawn to scale. */
function uiSpacingScale() {
  return `<div class="design-spacing">${UI_SPACING_SCALE.map((px) => `<div class="design-spacing-step"><span class="design-spacing-bar" style="width:${px}px;height:${px}px"></span><code>${px}</code></div>`).join('')}</div>`;
}

/** Corner radii drawn on identical boxes. */
function uiRadiusScale() {
  return `<div class="design-radii">${UI_RADIUS_SCALE.map((r) => `<div class="design-radius"><span class="design-radius-box" style="border-radius:${r.value}px"></span><code>${r.value === 999 ? 'pill' : r.value}</code><small>${uiEscape(r.label)}</small></div>`).join('')}</div>`;
}

/** Elevation levels: surface plus shadow. */
function uiElevationScale() {
  return `<div class="design-elevation">${UI_ELEVATION_SCALE.map((e) => `<div class="design-elevation-level"><span class="design-elevation-box" style="${e.style}"></span><strong>${uiEscape(e.label)}</strong><small>${uiEscape(e.detail)}</small></div>`).join('')}</div>`;
}

/** Motion tokens (styles/theme.css). Durations pair with --ease-out. */
const UI_MOTION_TOKENS = [
  {name: 'duration-fast', label: 'Reveal a control (toggle fades in)'},
  {name: 'duration-base', label: 'Move layout (panel slides, column resizes)'},
  {name: 'ease-out', label: 'Every transition: quick start, soft landing'}
];

/**
 * Two-column miniature of the conversation + inspector layout (rule animate-layout).
 * `live` wires the icon toggle and the panel close button so the panel slides out and in;
 * `hidden` renders the collapsed end state; `pop` renders the panel removed with display:none.
 * @param {{live?: boolean, hidden?: boolean, pop?: boolean}} [opts]
 */
function uiMotionDemo({live = false, hidden = false, pop = false} = {}) {
  const toggle = "this.closest('.design-motion-demo').classList.toggle('is-hidden')";
  const attrs = live ? {onclick: toggle} : {disabled: true};
  return `<div class="design-motion-demo${hidden ? ' is-hidden' : ''}${pop ? ' is-pop' : ''}" aria-label="Panel motion demo"><div class="design-motion-chat"><div class="design-motion-header">${uiIconButton({name: 'panelRight', label: 'Show panel', size: 'icon-xs', className: 'design-motion-toggle', attrs})}</div><span class="design-motion-composer"></span></div><aside class="design-motion-panel"><div class="design-motion-header">${uiIconButton({name: 'chevronsRight', label: 'Hide panel', size: 'icon-xs', attrs})}</div></aside></div>`;
}

/** Motion foundation: the three tokens plus a live panel that slides out and back in. */
function uiMotionScale() {
  const rows = UI_MOTION_TOKENS.map((t) => `<div class="design-motion-token"><code>--${uiEscape(t.name)}</code><strong>${uiEscape(uiToken(t.name))}</strong><small>${uiEscape(t.label)}</small></div>`).join('');
  return `<div class="design-motion">${rows}${uiMotionDemo({live: true})}<span class="design-rule-note">Close the panel with its own button; the toggle appears once it has left.</span></div>`;
}

/* ------------------------------------------------------------------------- */
/* Actions                                                                    */
/* ------------------------------------------------------------------------- */

/**
 * Basecoat button. Default variant is secondary (the manager's grey button).
 * @param {{label?: string, variant?: string, size?: string, icon?: string, iconEnd?: string, disabled?: boolean, type?: string, className?: string, attrs?: Record<string, unknown>}} [opts]
 */
function uiButton({label = 'Button', variant = UI_DEFAULT_BUTTON_VARIANT, size = 'sm', icon, iconEnd, disabled = false, danger = false, type = 'button', className = '', attrs = {}} = {}) {
  const v = UI_BUTTON_VARIANTS.includes(variant) ? variant : UI_DEFAULT_BUTTON_VARIANT;
  const s = UI_BUTTON_SIZES.includes(size) ? size : 'sm';
  const start = icon ? uiIcon(icon, {className: 'btn-icon'}) : '';
  const end = iconEnd ? uiIcon(iconEnd, {className: 'btn-icon'}) : '';
  return `<button class="${uiClass('btn', danger ? 'btn-danger' : '', className)}" type="${uiEscape(type)}" data-variant="${v}" data-size="${s}" ${disabled ? 'disabled' : ''} ${uiAttrs(attrs)}>${start}${uiEscape(label)}${end}</button>`;
}

/**
 * Glyph-only button. `className` keeps product hooks such as attach-button or send-button.
 * `round` adds `.btn-round` (fully circular, same width and height) for composer
 * and floating actions; leave it off for toolbars and rows, which use the
 * default rounded square.
 * @param {{name?: string, label?: string, variant?: string, size?: string, className?: string, type?: string, active?: boolean, danger?: boolean, round?: boolean, attrs?: Record<string, unknown>}} [opts]
 */
function uiIconButton({name = 'settings', label, variant = 'ghost', size = 'icon-sm', className = '', type = 'button', active = false, danger = false, round = false, attrs = {}} = {}) {
  const v = UI_BUTTON_VARIANTS.includes(variant) ? variant : 'ghost';
  const s = UI_BUTTON_SIZES.includes(size) ? size : 'icon-sm';
  return `<button class="${uiClass('btn', danger ? 'btn-danger' : '', round ? 'btn-round' : '', className)}" type="${uiEscape(type)}" data-variant="${v}" data-size="${s}" aria-label="${uiEscape(label || name)}" ${uiAttrs(attrs)}>${uiIcon(name, {active})}</button>`;
}

/**
 * Icon button that carries its own state (rule: one element, toggled state).
 * Swaps `name` for `activeName` and `label` for `activeLabel` while pressed.
 * Add `copy` to make it a clipboard button: after the click it shows the
 * active icon for UI_COPY_FEEDBACK_MS, then returns to rest.
 * Toggle programmatically with ui.setPressed(button, pressed). `round` passes through to uiIconButton.
 */
function uiToggleIconButton({name = 'copy', activeName = 'check', label = 'Copy', activeLabel = 'Copied', pressed = false, copy = false, variant = 'ghost', size = 'icon-sm', className = '', round = false, attrs = {}} = {}) {
  return uiIconButton({
    name: pressed ? activeName : name,
    label: pressed ? activeLabel : label,
    variant, size, className, round,
    attrs: {'data-toggle-icon': name, 'data-active-icon': activeName, 'data-label': label, 'data-active-label': activeLabel, 'aria-pressed': String(pressed), 'data-copy': copy ? 'true' : undefined, ...attrs}
  });
}

/**
 * Set a toggle icon button's pressed state, swapping icon and label in place.
 * @param {HTMLElement} button element rendered by uiToggleIconButton
 * @param {boolean} pressed
 */
function uiSetPressed(button, pressed) {
  if (!button?.dataset.toggleIcon) return;
  button.setAttribute('aria-pressed', String(pressed));
  button.setAttribute('aria-label', pressed ? button.dataset.activeLabel : button.dataset.label);
  button.innerHTML = uiIcon(pressed ? button.dataset.activeIcon : button.dataset.toggleIcon);
}

/** Clipboard buttons flash their active icon after the click handler has run. */
document.addEventListener('click', (e) => {
  const button = e.target.closest?.('[data-toggle-icon][data-copy]');
  if (!button) return;
  uiSetPressed(button, true);
  clearTimeout(button._copyTimer);
  button._copyTimer = setTimeout(() => uiSetPressed(button, false), UI_COPY_FEEDBACK_MS);
});

/* ------------------------------------------------------------------------- */
/* Inputs                                                                     */
/* ------------------------------------------------------------------------- */

function uiInput({value = '', placeholder = '', label = 'Input', type = 'text', readonly = false, className = '', attrs = {}} = {}) {
  return `<input class="${uiClass('input', className)}" type="${uiEscape(type)}" aria-label="${uiEscape(label)}" placeholder="${uiEscape(placeholder)}" value="${uiEscape(value)}" ${readonly ? 'readonly' : ''} ${uiAttrs(attrs)}>`;
}

function uiTextarea({value = '', placeholder = '', label = 'Message', rows = 2, className = '', attrs = {}} = {}) {
  return `<textarea class="${uiClass('textarea', className)}" rows="${rows}" aria-label="${uiEscape(label)}" placeholder="${uiEscape(placeholder)}" ${uiAttrs(attrs)}>${uiEscape(value)}</textarea>`;
}

/**
 * Native select styled by Basecoat. `options` accepts strings or {value,label}.
 */
function uiSelect({label = 'Select', options = [], value, className = '', attrs = {}} = {}) {
  const items = options.map((o) => typeof o === 'string' ? {value: o, label: o} : o);
  return `<select class="${uiClass('select', className)}" aria-label="${uiEscape(label)}" ${uiAttrs(attrs)}>${items.map((o) => `<option value="${uiEscape(o.value)}" ${o.value === value ? 'selected' : ''}>${uiEscape(o.label)}</option>`).join('')}</select>`;
}

/**
 * Normalise dropdown options: strings become {value, label}.
 * @param {Array<string|{value: string, label?: string, disabled?: boolean}>} options
 * @returns {Array<{value: string, label: string, disabled?: boolean}>}
 */
function uiDropdownOptions(options = []) {
  return options.map((o) => typeof o === 'string' ? {value: o, label: o} : {value: String(o.value), label: o.label ?? String(o.value), disabled: o.disabled});
}

/**
 * Compact settings dropdown (rule aligned-settings): a ghost, borderless
 * trigger showing the current value and a chevron. Clicking opens a kit menu
 * with the current option checked. Options are stored in data-options so
 * dynamically rendered dropdowns work through one delegated listener.
 *
 * Choosing an option updates data-value and the visible label, then
 * dispatches a bubbling `change` event on the button, so `onchange` attrs
 * (or `onChange`, which becomes the onchange attribute) and addEventListener
 * both work. Read the value with ui.dropdownValue(el); set it with
 * ui.setDropdownValue(el, value).
 * @param {{id?: string, label?: string, value?: string, options?: Array<string|{value: string, label?: string, disabled?: boolean}>, disabled?: boolean, align?: 'start'|'end', className?: string, attrs?: Record<string, unknown>, onChange?: string}} [opts]
 */
function uiDropdown({id, label = 'Option', value, options = [], disabled = false, align = 'end', className = '', attrs = {}, onChange} = {}) {
  const items = uiDropdownOptions(options);
  const current = items.find((o) => o.value === value) || items[0] || {value: '', label: ''};
  return `<button type="button" class="${uiClass('btn', 'dropdown', className)}" data-variant="ghost" data-size="sm" ${id ? `id="${uiEscape(id)}"` : ''} aria-haspopup="menu" aria-expanded="false" aria-label="${uiEscape(label)}" data-value="${uiEscape(current.value)}" data-align="${align === 'start' ? 'start' : 'end'}" data-options="${uiEscape(JSON.stringify(items))}" ${disabled ? 'disabled' : ''} ${uiAttrs({onchange: onChange, ...attrs})}><span class="dropdown-value">${uiEscape(current.label)}</span>${uiIcon('chevronDown', {className: 'dropdown-chevron'})}</button>`;
}

/**
 * Current value of a dropdown rendered by uiDropdown().
 * @param {HTMLElement|null} el
 * @returns {string}
 */
function uiDropdownValue(el) {
  return el?.dataset?.value ?? '';
}

/**
 * Visible label of a dropdown's current option.
 * @param {HTMLElement|null} el
 * @returns {string}
 */
function uiDropdownLabel(el) {
  return el?.querySelector?.('.dropdown-value')?.textContent ?? '';
}

/**
 * Set a dropdown's value in place. Unknown values are appended as an option
 * (label defaults to the value) so server-provided settings always show.
 * Does not dispatch `change`; pass {notify: true} to do so.
 * @param {HTMLElement|null} el element rendered by uiDropdown()
 * @param {string} value
 * @param {{label?: string, notify?: boolean}} [opts]
 */
function uiSetDropdownValue(el, value, {label, notify = false} = {}) {
  if (!el?.dataset?.options) return;
  const items = uiDropdownOptions(JSON.parse(el.dataset.options));
  let option = items.find((o) => o.value === String(value));
  if (!option) {
    option = {value: String(value), label: label ?? String(value)};
    items.push(option);
    el.dataset.options = JSON.stringify(items);
  }
  el.dataset.value = option.value;
  const span = el.querySelector('.dropdown-value');
  if (span) span.textContent = option.label;
  if (notify) el.dispatchEvent(new CustomEvent('change', {bubbles: true, detail: {value: option.value}}));
}

/**
 * Settings grid (rule aligned-settings): a fixed label column and one control
 * per row, so every control shares the same left edge and width.
 * @param {{rows?: Array<{label: string, control: string}>, className?: string, attrs?: Record<string, unknown>}} [opts]
 */
function uiSettingGrid({rows = [], className = '', attrs = {}} = {}) {
  return `<div class="${uiClass('setting-grid', className)}" ${uiAttrs(attrs)}>${rows.map((r) => `<span class="setting-grid-label">${uiEscape(r.label)}</span>${r.control}`).join('')}</div>`;
}

/** Dropdown triggers open a kit menu listing their options; picking one sets the value. */
document.addEventListener('click', (e) => {
  const trigger = e.target.closest?.('.dropdown[data-options]');
  if (!trigger || trigger.disabled) return;
  if (trigger.getAttribute('aria-expanded') === 'true') { uiCloseMenu(); return; }
  const items = uiDropdownOptions(JSON.parse(trigger.dataset.options));
  const current = trigger.dataset.value;
  const menu = uiOpenMenu(uiMenu({label: trigger.getAttribute('aria-label') || 'Options', items: items.map((o) => ({label: o.label, checked: o.value === current, disabled: o.disabled, attrs: {'data-option': o.value}}))}), {anchor: trigger, align: trigger.dataset.align === 'start' ? 'start' : 'end'});
  // Match the trigger's width, then re-align the (now wider) menu to the trigger edge.
  menu.style.minWidth = `${Math.max(trigger.offsetWidth, UI_DROPDOWN_MENU_MIN_WIDTH)}px`;
  const rect = trigger.getBoundingClientRect();
  const left = trigger.dataset.align === 'start' ? rect.left : rect.right - menu.offsetWidth;
  menu.style.left = `${Math.max(8, Math.min(left, innerWidth - menu.offsetWidth - 8))}px`;
  menu.addEventListener('click', (ev) => {
    const item = ev.target.closest('[data-option]');
    if (!item || item.disabled) return;
    if (item.dataset.option !== current) uiSetDropdownValue(trigger, item.dataset.option, {notify: true});
  });
});

function uiSearch({placeholder = 'Search', label = 'Search', className = '', attrs = {}} = {}) {
  return `<div class="${uiClass('sidebar-search', className)}">${uiIcon('search')}<input aria-label="${uiEscape(label)}" placeholder="${uiEscape(placeholder)}" ${uiAttrs(attrs)}></div>`;
}

/** Read-only value with a copy action. `copyAttrs` usually carries the onclick. */
function uiFieldCopy({value = '', label = 'Value', copyLabel = 'Copy', copyAttrs = {}, inputAttrs = {}} = {}) {
  return `<div class="field-copy">${uiInput({value, label, readonly: true, attrs: inputAttrs})}${uiToggleIconButton({name: 'copy', activeName: 'check', label: copyLabel, activeLabel: 'Copied', copy: true, variant: 'outline', size: 'icon-sm', attrs: copyAttrs})}</div>`;
}

function uiCheckbox({label = 'Option', checked = false, name, value, className = '', attrs = {}} = {}) {
  return `<label class="${uiClass('label', 'checkbox-row', className)}"><input type="checkbox" class="input" ${name ? `name="${uiEscape(name)}"` : ''} ${value !== undefined ? `value="${uiEscape(value)}"` : ''} ${checked ? 'checked' : ''} ${uiAttrs(attrs)}>${uiEscape(label)}</label>`;
}

function uiSwitch({label = 'Enabled', checked = false, className = '', attrs = {}} = {}) {
  return `<label class="${uiClass('label', className)}"><input type="checkbox" role="switch" class="input" ${checked ? 'checked' : ''} ${uiAttrs(attrs)}>${uiEscape(label)}</label>`;
}

/** Labelled field wrapper (Basecoat .field). */
function uiField({label, control = '', hint = '', id} = {}) {
  const fieldId = id || uiId('field');
  return `<div class="field">${label ? `<label for="${fieldId}">${uiEscape(label)}</label>` : ''}${control.replace(/^<(input|select|textarea)/, `<$1 id="${fieldId}"`)}${hint ? `<p>${uiEscape(hint)}</p>` : ''}</div>`;
}

/**
 * Recipient field (rule padded-fields): a short label and a text input in one
 * filled row, as in the New chat "To" line. The row owns the fill, radius and
 * horizontal padding; the input inside is flush and transparent with no
 * fill, border, ring or shadow in any state, so the caret never touches the
 * edge of the fill. The label is linked to the input through `id`.
 * @param {{label?: string, placeholder?: string, id?: string, inputLabel?: string, className?: string, attrs?: Record<string, unknown>}} [opts]
 *   `attrs` go on the input (e.g. autofocus, autocomplete); `className` goes on the row.
 */
function uiRecipientField({label = 'To', placeholder = '', id, inputLabel, className = '', attrs = {}} = {}) {
  const fieldId = id || uiId('recipient');
  return `<div class="${uiClass('recipient-field', className)}"><label for="${fieldId}">${uiEscape(label)}</label>${uiInput({label: inputLabel || placeholder || label, placeholder, attrs: {id: fieldId, ...attrs}})}</div>`;
}

/* ------------------------------------------------------------------------- */
/* Identity and feedback                                                      */
/* ------------------------------------------------------------------------- */

/**
 * Avatar. Emoji or initials are content; a Lucide icon name can be passed as
 * `icon` for non-person identities such as groups.
 * @param {{mark?: string, icon?: string, size?: 'sm'|'default'|'lg', className?: string}} [opts]
 */
function uiAvatar({mark = UI_DEFAULT_AVATAR, icon, size = 'default', className = ''} = {}) {
  const inner = icon ? uiIcon(icon) : `<span>${uiEscape(mark)}</span>`;
  return `<span class="${uiClass('avatar', className)}" ${size !== 'default' ? `data-size="${uiEscape(size)}"` : ''} aria-hidden="true">${inner}</span>`;
}

/** Running-only motion. Keep queued, waiting, disconnected and terminal states static. */
let uiShimmerId = 0;
function uiRunningText({label = 'Working', running = true, svg = false, x = 0, y = 0, className = ''} = {}) {
  const text = uiEscape(label);
  if (!svg) return `<span class="${uiEscape(className)}${running ? ' ui-running-text' : ''}">${text}</span>`;
  if (!running) return `<text x="${Number(x)}" y="${Number(y)}" class="${uiEscape(className)}">${text}</text>`;
  const id = 'ui-running-text-' + (++uiShimmerId);
  return `<defs><linearGradient id="${id}" x1="-100%" x2="0%"><stop offset="0" class="ui-shimmer-base"/><stop offset=".5" class="ui-shimmer-highlight"/><stop offset="1" class="ui-shimmer-base"/><animate attributeName="x1" values="-100%;100%" dur="2s" repeatCount="indefinite"/><animate attributeName="x2" values="0%;200%" dur="2s" repeatCount="indefinite"/></linearGradient></defs><text x="${Number(x)}" y="${Number(y)}" class="${uiEscape(className)} ui-running-svg-text" style="fill:url(#${id})">${text}</text>`;
}
function uiRunningArrow({path = ''} = {}) {
  return `<path class="ui-running-arrow" d="${uiEscape(path)}" pathLength="100" fill="none" pointer-events="none" aria-hidden="true"/>`;
}

function uiDot({running = false, label} = {}) {
  return `<span class="dot${running ? ' running' : ''}" ${label ? `title="${uiEscape(label)}"` : ''}></span>`;
}

/**
 * Compact last-message label for sidebar rows. Keep in step with
 * last-message-time.ts: clock time for today (`1:18AM`), otherwise `9/1`.
 * @param {string|number|Date|null|undefined} value
 * @param {Date} [now]
 */
function uiLastMessageTime(value, now = new Date()) {
  if (value == null || value === '') return '';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const sameDay = date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
  if (sameDay) {
    return date.toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', hour12: true}).replace(/[\s\u202f\u00a0]/g, '').toUpperCase();
  }
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

/** Right-hand last-message time for a sidebar row. Empty when there is no stamp. */
function uiNavTime(value) {
  const label = uiLastMessageTime(value);
  if (!label) return '';
  const instant = value instanceof Date ? value.toISOString() : (typeof value === 'string' && !Number.isNaN(new Date(value).getTime()) ? value : '');
  return `<time class="bot-time"${instant ? ` datetime="${uiEscape(instant)}"` : ''}>${uiEscape(label)}</time>`;
}

function uiBadge({label = 'Badge', variant = 'secondary', icon, className = '', attrs = {}} = {}) {
  const v = UI_BADGE_VARIANTS.includes(variant) ? variant : 'secondary';
  return `<span class="${uiClass('badge', className)}" data-variant="${v}" ${uiAttrs(attrs)}>${icon ? uiIcon(icon) : ''}${uiEscape(label)}</span>`;
}

function uiLeadBadge(name = 'the group') {
  return uiBadge({label: 'Lead', variant: 'outline', icon: 'crown', className: 'group-lead-badge', attrs: {title: `Lead for ${name}`}});
}

function uiMuted({text = 'Helper text'} = {}) {
  return `<span class="muted">${uiEscape(text)}</span>`;
}

function uiKbd(keys = 'Esc') {
  return `<kbd class="kbd">${uiEscape(keys)}</kbd>`;
}

/** Tooltip attributes to spread on any element: `<button ${ui.tooltip('Copy')}>`. */
function uiTooltip(text, {side = 'top', align = 'center'} = {}) {
  return `data-tooltip="${uiEscape(text)}" data-side="${uiEscape(side)}" data-align="${uiEscape(align)}"`;
}

/**
 * Empty / zero-data state (Basecoat .empty).
 */
function uiEmpty({icon = 'folder', title = 'Nothing here yet', description = '', action = ''} = {}) {
  return `<div class="empty"><header><figure>${uiIcon(icon)}</figure><h3>${uiEscape(title)}</h3>${description ? `<p>${uiEscape(description)}</p>` : ''}</header>${action ? `<footer>${action}</footer>` : ''}</div>`;
}

/** Inline alert (Basecoat .alert). */
function uiAlert({title = '', description = '', variant = 'default', icon = 'info'} = {}) {
  return `<div class="alert" ${variant !== 'default' ? `data-variant="${uiEscape(variant)}"` : ''} role="alert">${uiIcon(icon)}${title ? `<h2>${uiEscape(title)}</h2>` : ''}${description ? `<section>${uiEscape(description)}</section>` : ''}</div>`;
}

function uiSkeleton({width = '100%', height = '16px'} = {}) {
  return `<span class="skeleton" style="display:block;width:${uiEscape(width)};height:${uiEscape(height)}"></span>`;
}

/* ------------------------------------------------------------------------- */
/* Toasts                                                                     */
/* ------------------------------------------------------------------------- */

/**
 * Markup for the toaster mount. Rendered once in the app shell; ui.toast()
 * appends to it through Basecoat's runtime.
 */
function uiToaster() {
  return '<div id="toaster" class="toaster" aria-live="polite"></div>';
}

/**
 * Show a toast. `category` is info | success | warning | error.
 * Falls back to a plain toast element when Basecoat's runtime has not loaded.
 * @param {{title?: string, description?: string, category?: string, duration?: number}} opts
 */
function uiToast({title = '', description = '', category = 'info', duration} = {}) {
  const mount = document.getElementById('toaster');
  if (!mount) return;
  const ms = duration ?? (category === 'error' ? UI_TOAST_ERROR_DURATION : UI_TOAST_DURATION);
  if (typeof mount.toast === 'function') {
    mount.toast({category, title: uiEscape(title), description: uiEscape(description), duration: ms});
    return;
  }
  const el = document.createElement('div');
  el.className = 'toast';
  el.setAttribute('role', category === 'error' ? 'alert' : 'status');
  el.dataset.category = category;
  el.innerHTML = `<div class="toast-content">${uiIcon(category === 'error' ? 'alert' : category === 'success' ? 'check' : 'info')}<section>${title ? `<h2>${uiEscape(title)}</h2>` : ''}${description ? `<p>${uiEscape(description)}</p>` : ''}</section></div>`;
  mount.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

/** Static toast preview for the Design page. */
function uiToastPreview({title = 'Task completed', description = 'Report saved to the workspace.', category = 'success'} = {}) {
  const iconName = category === 'error' ? 'alert' : category === 'success' ? 'check' : category === 'warning' ? 'alert' : 'info';
  return `<div class="toaster design-toaster-preview"><div class="toast" role="status" data-category="${uiEscape(category)}"><div class="toast-content">${uiIcon(iconName)}<section>${title ? `<h2>${uiEscape(title)}</h2>` : ''}${description ? `<p>${uiEscape(description)}</p>` : ''}</section></div></div></div>`;
}

/* ------------------------------------------------------------------------- */
/* Navigation                                                                 */
/* ------------------------------------------------------------------------- */

/**
 * Sidebar list row for a sandbox or a group. The trailing slot is last-message
 * time, not a running/idle status dot.
 */
function uiNavItem({title = 'Papacito', meta = 'running', preview = 'Latest message preview', avatar = UI_DEFAULT_AVATAR, active = false, time = '', kind = 'sandbox', badge = '', attrs = {}} = {}) {
  const face = kind === 'group' ? uiAvatar({icon: 'group', size: 'sm', className: 'mini-avatar'}) : uiAvatar({mark: avatar, size: 'sm', className: 'mini-avatar'});
  return `<div class="bot-list-row"><button class="bot-list-item${active ? ' is-active' : ''}" type="button" ${uiAttrs(attrs)}>${face}<span class="bot-list-copy"><strong>${uiEscape(title)}${badge}</strong><small>${uiEscape(meta)}</small><span class="bot-preview">${uiEscape(preview)}</span></span>${uiNavTime(time)}</button></div>`;
}

/**
 * Workspace row: the sidebar footer. One button carrying the workspace mark,
 * name and meta; clicking it opens the workspace menu (Settings).
 */
function uiWorkspaceRow({name = 'Sandbox workspace', meta = 'Your local cloud workers', mark = 'S', attrs = {}} = {}) {
  return `<button type="button" class="workspace-row" aria-haspopup="menu" ${uiAttrs(attrs)}><span class="workspace-mark" aria-hidden="true">${uiEscape(mark)}</span><span class="workspace-copy"><strong>${uiEscape(name)}</strong><small>${uiEscape(meta)}</small></span></button>`;
}

/**
 * Nav link: one row in a stacked navigation list (settings sections, Design
 * pages, Design rail, sidebar footer). Ghost at rest, accent when selected.
 * `size: 'sm'` is the compact rail variant; `icon` is optional.
 */
function uiNavLink({label = 'General', icon, selected = false, size = 'md', className = '', attrs = {}} = {}) {
  return `<button type="button" class="${uiClass('nav-link', selected ? 'selected' : '', className)}" data-size="${size === 'sm' ? 'sm' : 'md'}" aria-current="${selected ? 'page' : 'false'}" ${uiAttrs(attrs)}>${icon ? uiIcon(icon) : ''}<span>${uiEscape(label)}</span></button>`;
}

/**
 * Basecoat line tabs. Each tab: {id, label, selected, attrs}.
 */
function uiTabs({tabs = [{id: 'chat', label: 'Chat', selected: true}, {id: 'flow', label: 'Flow', selected: false}], label = 'View', className = ''} = {}) {
  return `<nav class="${uiClass('tabs-line', className)}" role="tablist" aria-orientation="horizontal" aria-label="${uiEscape(label)}">${tabs.map((t) => `<button type="button" role="tab" data-tab="${uiEscape(t.id)}" aria-selected="${t.selected ? 'true' : 'false'}" tabindex="${t.selected ? '0' : '-1'}" ${uiAttrs(t.attrs)}>${t.icon ? uiIcon(t.icon) : ''}${uiEscape(t.label)}</button>`).join('')}</nav>`;
}

/** Removable chip (selected member, recipient). */
function uiChip({label = 'Papacito', removable = true, attrs = {}} = {}) {
  return `<button type="button" class="chip" ${uiAttrs(attrs)}>${uiEscape(label)}${removable ? uiIcon('close') : ''}</button>`;
}

/* ------------------------------------------------------------------------- */
/* Settings                                                                   */
/* ------------------------------------------------------------------------- */

function uiSettingItem({title = 'Setting', detail = '', control = ''} = {}) {
  return `<div class="setting-item"><div><strong>${uiEscape(title)}</strong>${detail ? `<p>${uiEscape(detail)}</p>` : ''}</div>${control}</div>`;
}

function uiSettingsGroup({label = '', items = []} = {}) {
  return `${label ? `<h2 class="setting-label">${uiEscape(label)}</h2>` : ''}<div class="settings-group">${items.join('')}</div>`;
}

/** Card (Basecoat .card): header, optional description, body, footer. */
function uiCard({title = '', description = '', body = '', footer = '', className = ''} = {}) {
  return `<div class="${uiClass('card', className)}">${title || description ? `<header>${title ? `<h3>${uiEscape(title)}</h3>` : ''}${description ? `<p>${uiEscape(description)}</p>` : ''}</header>` : ''}${body ? `<section>${body}</section>` : ''}${footer ? `<footer>${footer}</footer>` : ''}</div>`;
}

/* ------------------------------------------------------------------------- */
/* Chat                                                                       */
/* ------------------------------------------------------------------------- */

function uiMessage({text = 'The report is ready.', user = false, author = 'Papacito', time = '14:25', status = ''} = {}) {
  const meta = `<span class="muted">${uiEscape(time)}${status ? ` · ${uiEscape(status)}` : ''}</span>`;
  return `<article class="group-message${user ? ' from-user' : ''}"><div class="group-author">${user ? 'You' : uiEscape(author)} ${meta}</div><div class="message-bubble">${uiEscape(text)}</div></article>`;
}

function uiCurrentTask({text = 'Ready for your next task', live = false, stopAttrs = {}} = {}) {
  return `<div class="current-task">${uiIcon(live ? 'loader' : 'target')}<span class="current-task-copy">${uiEscape(text)}</span>${live ? uiButton({label: 'Stop request', variant: 'outline', size: 'xs', icon: 'stop', attrs: stopAttrs}) : ''}</div>`;
}

function uiQueueRow({prompt = 'Read BBC and write a report', action = 'Remove', number = 1, waiting = true, actionAttrs = {}} = {}) {
  return `<div class="queue-row">${number ? `<span class="queue-number">${uiEscape(number)}</span>` : ''}<span class="queue-prompt">${uiEscape(prompt)}</span>${waiting ? '<span class="muted">Waiting</span>' : ''}${action ? uiButton({label: action, variant: 'ghost', size: 'xs', icon: 'close', danger: true, attrs: actionAttrs}) : ''}</div>`;
}

function uiComposer({placeholder = 'Message…', attachAttrs = {}, voiceAttrs = {}, sendAttrs = {}, textareaAttrs = {}, formAttrs = {}, mention = false} = {}) {
  return `<form class="composer" ${uiAttrs({onsubmit: 'return false', ...formAttrs})}>${uiIconButton({name: 'attach', className: 'attach-button', label: 'Attach file', round: true, attrs: attachAttrs})}<textarea rows="1" aria-label="Message" placeholder="${uiEscape(placeholder)}" ${uiAttrs(textareaAttrs)}></textarea>${mention ? uiIconButton({name: 'target', className: 'mention-button', label: 'Choose recipients', round: true, attrs: mention === true ? {} : mention}) : ''}${uiIconButton({name: 'voice', className: 'voice-button', label: 'Dictate message', round: true, attrs: voiceAttrs})}${uiIconButton({name: 'send', className: 'send-button', variant: 'primary', type: 'submit', label: 'Send', round: true, attrs: sendAttrs})}</form>`;
}

/* ------------------------------------------------------------------------- */
/* Inspector                                                                  */
/* ------------------------------------------------------------------------- */

function uiFileRow({name = 'report.md', href = '#', title = '', detail = '', icon = 'file', attrs = {}} = {}) {
  return `<div class="file">${uiIcon(icon)}<div><a title="${uiEscape(title || name)}" href="${uiEscape(href)}" target="_blank" rel="noopener" ${uiAttrs(attrs)}>${uiEscape(name)}</a>${detail ? `<div class="muted">${uiEscape(detail)}</div>` : ''}</div></div>`;
}

function uiArtifact({name = 'bbc-fresh.png', href = '#', icon = 'file', attrs = {}} = {}) {
  return `<a class="group-artifact" href="${uiEscape(href)}" ${uiAttrs(attrs)}>${uiIcon(icon)}<span>${uiEscape(name)}</span></a>`;
}

/**
 * Group member row. `attrs` go on the section (data-group-member, aria-label);
 * `removeAttrs` may carry disabled/title when removal is blocked.
 */
function uiMemberRow({name = 'Papacito', status = 'Ready', avatar = UI_DEFAULT_AVATAR, lead = false, groupName = 'the group', attrs = {}, removeAttrs = {}, moreAttrs = {}} = {}) {
  return `<section class="group-member-row${lead ? ' group-member-lead' : ''}" tabindex="0" ${uiAttrs(attrs)}>${uiAvatar({mark: avatar, size: 'sm', className: 'group-member-avatar'})}<div class="group-member-copy"><strong>${uiEscape(name)}${lead ? uiLeadBadge(groupName) : ''}</strong><small>${uiEscape(status)}</small></div>${uiButton({label: 'Remove', variant: 'ghost', size: 'xs', danger: true, className: 'group-member-remove', attrs: removeAttrs})}${uiIconButton({name: 'more', label: `Options for ${name}`, className: 'group-member-more', attrs: {'aria-haspopup': 'menu', ...moreAttrs}})}</section>`;
}

function uiRecentItem({name = 'todays-news.md', by = 'Papacito', href = '#', ext = 'MD', attrs = {}} = {}) {
  return `<a class="recent-gallery-item" href="${uiEscape(href)}" ${uiAttrs(attrs)}><span class="recent-gallery-preview"><span class="recent-document">${uiIcon('file')}<small>${uiEscape(ext)}</small></span></span><span class="recent-gallery-caption"><strong>${uiEscape(name)}</strong><small>${uiEscape(by)}</small></span></a>`;
}

/* ------------------------------------------------------------------------- */
/* Overlays                                                                   */
/* ------------------------------------------------------------------------- */

/**
 * Basecoat dialog markup. Pass `body` (HTML) and optional `footer` (HTML, usually buttons).
 * `size` widens the panel: sm 400 · default 480 · lg 640 · xl 880.
 */
function uiDialog({id, title = '', description = '', body = '', footer = '', size = 'default', className = '', closeLabel = 'Close', open = false} = {}) {
  const dialogId = id || uiId('dialog');
  const labelled = title ? `aria-labelledby="${dialogId}-title"` : '';
  const described = description ? `aria-describedby="${dialogId}-description"` : '';
  return `<dialog id="${dialogId}" class="${uiClass('dialog', className)}" data-size="${uiEscape(size)}" ${labelled} ${described} ${open ? 'open' : ''} onclick="if(event.target===this)this.close()"><div>${title || description ? `<header>${title ? `<h2 id="${dialogId}-title">${uiEscape(title)}</h2>` : ''}${description ? `<p id="${dialogId}-description">${uiEscape(description)}</p>` : ''}</header>` : ''}<section>${body}</section>${footer ? `<footer>${footer}</footer>` : ''}${uiIconButton({name: 'close', label: closeLabel, className: 'dialog-close', attrs: {onclick: "this.closest('dialog').close()"}})}</div></dialog>`;
}

/**
 * Create a dialog from markup, show it and remove it on close.
 * @param {string} html markup from uiDialog()
 * @returns {HTMLDialogElement}
 */
function uiOpenDialog(html) {
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  const dialog = wrap.firstElementChild;
  document.body.appendChild(dialog);
  dialog.addEventListener('close', () => dialog.remove(), {once: true});
  dialog.showModal();
  return dialog;
}

/**
 * Alert dialog (confirm). Resolves true when confirmed.
 * @param {{title?: string, description?: string, confirmLabel?: string, cancelLabel?: string, destructive?: boolean}} opts
 * @returns {Promise<boolean>}
 */
function uiConfirm({title = 'Are you sure?', description = '', confirmLabel = 'Continue', cancelLabel = 'Cancel', destructive = false} = {}) {
  return new Promise((resolve) => {
    const id = uiId('alert');
    const wrap = document.createElement('div');
    wrap.innerHTML = `<dialog id="${id}" class="alert-dialog" aria-labelledby="${id}-title" ${description ? `aria-describedby="${id}-description"` : ''}><div><header><h2 id="${id}-title">${uiEscape(title)}</h2>${description ? `<p id="${id}-description">${uiEscape(description)}</p>` : ''}</header><footer>${uiButton({label: cancelLabel, variant: 'outline', size: 'sm', attrs: {'data-cancel': true}})}${uiButton({label: confirmLabel, variant: destructive ? 'destructive' : 'primary', size: 'sm', attrs: {'data-confirm': true}})}</footer></div></dialog>`;
    const dialog = wrap.firstElementChild;
    document.body.appendChild(dialog);
    let result = false;
    dialog.querySelector('[data-confirm]').addEventListener('click', () => { result = true; dialog.close(); });
    dialog.querySelector('[data-cancel]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { dialog.remove(); resolve(result); }, {once: true});
    dialog.showModal();
    dialog.querySelector('[data-confirm]').focus();
  });
}

/** Static alert-dialog preview for the Design page (not modal). */
function uiAlertDialogPreview({title = 'Remove Mamacita from the group?', description = 'The sandbox keeps running. Only its membership in Famalia ends.', confirmLabel = 'Remove', cancelLabel = 'Cancel', destructive = true} = {}) {
  return `<div class="alert-dialog design-dialog-preview"><div><header><h2>${uiEscape(title)}</h2><p>${uiEscape(description)}</p></header><footer>${uiButton({label: cancelLabel, variant: 'outline', size: 'sm'})}${uiButton({label: confirmLabel, variant: destructive ? 'destructive' : 'primary', size: 'sm'})}</footer></div></div>`;
}

/**
 * Menu items markup. Item: {label, icon, danger, disabled, checked, shortcut, attrs} or {separator:true} or {heading, sub}.
 */
function uiMenuItems(items = []) {
  return items.map((item) => {
    if (item.separator) return '<hr role="separator">';
    if (item.heading !== undefined) return `<div class="menu-heading" role="presentation">${uiEscape(item.heading)}${item.sub ? `<small>${uiEscape(item.sub)}</small>` : ''}</div>`;
    const cls = uiClass(item.danger && 'menu-danger', item.className);
    return `<button type="button" role="menuitem" class="${cls}" ${item.disabled ? 'disabled aria-disabled="true"' : ''} ${uiAttrs(item.attrs)}>${item.icon ? uiIcon(item.icon) : ''}<span>${uiEscape(item.label)}</span>${item.checked ? uiIcon('check', {className: 'menu-check'}) : ''}${item.shortcut ? uiKbd(item.shortcut) : ''}</button>`;
  }).join('');
}

/**
 * Context / dropdown menu panel. Position it with uiOpenMenu().
 */
function uiMenu({items = [], label = 'Menu', className = '', id} = {}) {
  return `<div class="${uiClass('menu', className)}" role="menu" aria-label="${uiEscape(label)}" ${id ? `id="${uiEscape(id)}"` : ''}>${uiMenuItems(items)}</div>`;
}

/** The single open menu, if any. */
let uiActiveMenu = null;

/**
 * Open a menu near a point or anchored to an element. Closes on outside click,
 * Escape, scroll or when another menu opens. Item clicks bubble to the caller's
 * handlers before the menu closes.
 * @param {string} html markup from uiMenu()
 * @param {{x?: number, y?: number, anchor?: HTMLElement, align?: 'start'|'end'}} where
 * @returns {HTMLElement}
 */
function uiOpenMenu(html, {x, y, anchor, align = 'end', placement = 'bottom'} = {}) {
  uiCloseMenu();
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  const menu = wrap.firstElementChild;
  menu.classList.add('menu-floating');
  document.body.appendChild(menu);
  const rect = anchor ? anchor.getBoundingClientRect() : null;
  let left = rect ? (align === 'end' ? rect.right - menu.offsetWidth : rect.left) : (x ?? 0);
  let top = rect ? (placement === 'top' ? rect.top - menu.offsetHeight - 6 : rect.bottom + 6) : (y ?? 0);
  // Flip above the anchor when there is no room below (e.g. the workspace row at the sidebar foot).
  if (rect && top + menu.offsetHeight + 8 > innerHeight && rect.top - menu.offsetHeight - 6 >= 8) top = rect.top - menu.offsetHeight - 6;
  left = Math.max(8, Math.min(left, innerWidth - menu.offsetWidth - 8));
  top = Math.max(8, Math.min(top, innerHeight - menu.offsetHeight - 8));
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
  if (anchor) anchor.setAttribute('aria-expanded', 'true');
  const close = () => uiCloseMenu();
  const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); close(); } };
  const onDown = (e) => { if (!menu.contains(e.target)) close(); };
  setTimeout(() => { document.addEventListener('pointerdown', onDown, true); document.addEventListener('keydown', onKey, true); window.addEventListener('scroll', close, {capture: true, once: true}); }, 0);
  uiActiveMenu = {menu, anchor, teardown: () => { document.removeEventListener('pointerdown', onDown, true); document.removeEventListener('keydown', onKey, true); window.removeEventListener('scroll', close, {capture: true}); }};
  menu.addEventListener('click', (e) => { if (e.target.closest('[role=menuitem]')) setTimeout(close, 0); });
  const first = menu.querySelector('[role=menuitem]:not([disabled])');
  if (first) first.focus();
  return menu;
}

/** Close the open menu, if any. */
function uiCloseMenu() {
  if (!uiActiveMenu) return;
  const {menu, anchor, teardown} = uiActiveMenu;
  teardown();
  menu.remove();
  if (anchor) anchor.setAttribute('aria-expanded', 'false');
  uiActiveMenu = null;
}

/** Static drawer (sheet) preview for the Design page. */
function uiDrawerPreview({title = 'Papacito’s computer', description = 'Live desktop, files and agent settings.', side = 'right'} = {}) {
  return `<div class="design-drawer-preview" data-side="${uiEscape(side)}"><div class="design-drawer-panel"><header><h2>${uiEscape(title)}</h2><p>${uiEscape(description)}</p>${uiIconButton({name: 'close', label: 'Close'})}</header><section>${uiSkeleton({height: '120px'})}<div class="design-drawer-rows">${uiSkeleton({width: '60%'})}${uiSkeleton({width: '80%'})}${uiSkeleton({width: '45%'})}</div></section></div></div>`;
}

/* ------------------------------------------------------------------------- */
/* Layouts (Design page miniatures)                                           */
/* ------------------------------------------------------------------------- */

/**
 * Labelled region inside a layout miniature.
 */
function uiRegion(label, className = '', body = '') {
  return `<div class="${uiClass('design-region', className)}"><small>${uiEscape(label)}</small>${body}</div>`;
}

/** App shell: sidebar · conversation · inspector. */
function uiLayoutAppShell() {
  return `<div class="design-frame design-frame-app">${uiRegion('Sidebar · 220–278px', 'design-region-sidebar', `<span class="design-line ln-60"></span><span class="design-line ln-80"></span><span class="design-line ln-70"></span>`)}${uiRegion('Conversation · flexible', 'design-region-main', `<span class="design-bubble right"></span><span class="design-bubble left"></span><span class="design-composer"></span>`)}${uiRegion('Inspector · 278–478px', 'design-region-aside', `<span class="design-block"></span><span class="design-line ln-70"></span><span class="design-line ln-50"></span>`)}</div>`;
}

/** Settings shell: 200px section rail plus left-aligned content column. */
function uiLayoutSettings() {
  return `<div class="design-frame design-frame-settings">${uiRegion('Sections · 200px', 'design-region-rail', `<span class="design-line ln-60 is-active"></span><span class="design-line ln-50"></span><span class="design-line ln-70"></span>`)}${uiRegion('Content · max 720px, left aligned', 'design-region-content', `<span class="design-line ln-30 is-title"></span><span class="design-block"></span><span class="design-block"></span>`)}<span class="design-close">${uiIcon('close')}</span></div>`;
}

/** Page: centred 960px column of panels (API, sign-in). */
function uiLayoutPage() {
  return `<div class="design-frame design-frame-page"><div class="design-region-page">${uiRegion('Page · max 960px centred', '', `<span class="design-line ln-30 is-title"></span><div class="design-grid-2"><span class="design-block tall"></span><span class="design-block tall"></span></div>`)}</div></div>`;
}

/** Inspector: stacked sections with a header row each. */
function uiLayoutInspector() {
  return `<div class="design-frame design-frame-inspector">${uiRegion('Header · title + actions', 'design-region-header', `<span class="design-line ln-40"></span><span class="design-actions"><i></i><i></i></span>`)}${uiRegion('Section', '', `<span class="design-line ln-40 is-title"></span><span class="design-block"></span>`)}${uiRegion('Section', '', `<span class="design-line ln-40 is-title"></span><span class="design-line ln-80"></span><span class="design-line ln-60"></span>`)}</div>`;
}

/* ------------------------------------------------------------------------- */
/* Catalogue                                                                  */
/* ------------------------------------------------------------------------- */

/**
 * Catalogue shown at /#settings/design. `layout: 'stack'` renders the preview
 * as a full-width column, matching how the control sits in the product.
 */
const UI_KIT = [
  {id: 'colors', section: 'Foundations', name: 'Colour', detail: 'shadcn/ui-compatible tokens from styles/theme.css. Every surface, border and text colour maps to one of these.', layout: 'stack', render: uiColorTokens},
  {id: 'type', section: 'Foundations', name: 'Typography', detail: 'Five sizes cover the whole manager. Titles are 500 weight; everything else is 400.', layout: 'stack', render: uiTypeScale},
  {id: 'spacing', section: 'Foundations', name: 'Spacing', detail: 'Padding and gap steps. Cards use 16, rows use 8 to 12, groups are separated by 24 to 32.', render: uiSpacingScale},
  {id: 'radius', section: 'Foundations', name: 'Radius', detail: '--radius is 10px; Basecoat derives sm/md/lg/xl from it.', render: uiRadiusScale},
  {id: 'elevation', section: 'Foundations', name: 'Elevation', detail: 'Surface colour steps up with each level; only floating layers cast a shadow.', render: uiElevationScale},
  {id: 'motion', section: 'Foundations', name: 'Motion', detail: 'Two durations and one curve. Layout moves (panels, columns) take --duration-base; reveals take --duration-fast. Reduced-motion users get the end state at once.', layout: 'stack', render: uiMotionScale},

  {id: 'layout-app', section: 'Layouts', name: 'App shell', detail: 'Three columns: sandbox sidebar, conversation, inspector. Sidebar and inspector are resizable; below 760px the inspector becomes a drawer.', layout: 'stack', render: uiLayoutAppShell},
  {id: 'layout-settings', section: 'Layouts', name: 'Settings shell', detail: 'Section rail on the left, content column left-aligned next to it, close in the top-right corner. The rail hosts sub-navigation when a section needs it.', layout: 'stack', render: uiLayoutSettings},
  {id: 'layout-page', section: 'Layouts', name: 'Page', detail: 'Centred 960px column of cards for standalone pages such as the Management API and sign-in.', layout: 'stack', render: uiLayoutPage},
  {id: 'layout-inspector', section: 'Layouts', name: 'Inspector', detail: 'Header with title and icon actions, then stacked sections separated by borders.', layout: 'stack', render: uiLayoutInspector},

  {id: 'icons', section: 'Icons', name: 'Icons', detail: `Lucide ${window.UI_ICON_SOURCE?.version || ''} via ui.icon(). Toggle Active or Inactive, or click a box. Add icons in scripts/build-icons.ts.`, render: uiIcons},

  {id: 'button', section: 'Actions', name: 'Button', detail: 'Basecoat .btn. Secondary is the default in this app; primary is reserved for the one main action on a surface.', render: () => uiStates([
    {label: 'Primary', html: uiButton({label: 'Save', variant: 'primary'})},
    {label: 'Secondary', html: uiButton({label: 'Open'})},
    {label: 'Outline', html: uiButton({label: 'View all', variant: 'outline'})},
    {label: 'Ghost', html: uiButton({label: 'Cancel', variant: 'ghost'})},
    {label: 'Destructive', html: uiButton({label: 'Remove', variant: 'destructive'})},
    {label: 'Link', html: uiButton({label: 'OpenAPI', variant: 'link', iconEnd: 'external'})},
    {label: 'With icon', html: uiButton({label: 'Publish report', icon: 'send'})},
    {label: 'Disabled', html: uiButton({label: 'Disabled', disabled: true})}
  ])},
  {id: 'button-size', section: 'Actions', name: 'Button sizes', detail: 'xs for dense rows, sm (default) for panels and dialogs, default for page-level actions.', render: () => uiStates([
    {label: 'xs', html: uiButton({label: 'Remove', size: 'xs'})},
    {label: 'sm', html: uiButton({label: 'View sandboxes', size: 'sm'})},
    {label: 'default', html: uiButton({label: 'Create sandbox', size: 'default', variant: 'primary'})}
  ])},
  {id: 'icon-button', section: 'Actions', name: 'Icon button', detail: 'Glyph-only .btn with data-size="icon-*" and an aria-label. Ghost by default. Rounded square in toolbars and rows; pass round:true (.btn-round, a true circle) only for composer and floating actions such as attach, dictate and send/stop.', render: () => uiStates([
    {label: 'New chat', html: uiIconButton({name: 'add', label: 'New chat'})},
    {label: 'Settings', html: uiIconButton({name: 'settings', label: 'Settings'})},
    {label: 'More', html: uiIconButton({name: 'more', label: 'Options'})},
    {label: 'Close', html: uiIconButton({name: 'close', label: 'Close'})},
    {label: 'Outline', html: uiIconButton({name: 'copy', label: 'Copy', variant: 'outline'})},
    {label: 'Primary · send', html: uiIconButton({name: 'send', label: 'Send', variant: 'primary', size: 'icon'})},
    {label: 'Round · composer', html: `${uiIconButton({name: 'attach', label: 'Attach file', variant: 'secondary', round: true})}${uiIconButton({name: 'voice', label: 'Dictate message', variant: 'secondary', round: true})}${uiIconButton({name: 'send', label: 'Send', variant: 'primary', size: 'icon', round: true})}`}
  ])},

  {id: 'toggle-icon-button', section: 'Actions', name: 'Toggle icon button', detail: 'One element, toggled state: swaps icon and label via aria-pressed. copy: true flashes the tick after copying.', render: () => uiStates([
    {label: 'Copy to tick', html: uiToggleIconButton({label: 'Copy', copy: true, variant: 'outline'})},
    {label: 'Play and stop', html: uiToggleIconButton({name: 'play', activeName: 'stop', label: 'Start', activeLabel: 'Stop', variant: 'outline', attrs: {onclick: "ui.setPressed(this, this.getAttribute('aria-pressed') !== 'true')"}})},
    {label: 'Pressed', html: uiToggleIconButton({name: 'list', activeName: 'grid', label: 'List view', activeLabel: 'Grid view', pressed: true, variant: 'outline'})}
  ])},
  {id: 'input', section: 'Inputs', name: 'Input', detail: 'Basecoat .input. Always carries a visible label or aria-label.', render: () => uiInput({value: 'Famalia', label: 'Name', placeholder: 'Name'})},
  {id: 'field', section: 'Inputs', name: 'Field', detail: 'Label, control and hint grouped with .field.', layout: 'stack', render: () => uiField({label: 'Sandbox name', control: uiInput({value: 'Famalia', label: 'Sandbox name'}), hint: 'Shown in the sidebar and group chats.'})},
  {id: 'textarea', section: 'Inputs', name: 'Textarea', detail: 'Basecoat .textarea for routines, notes and system prompts.', layout: 'stack', render: () => uiTextarea({value: 'Read BBC and CNN and share a report.', label: 'Instruction'})},
  {id: 'select', section: 'Inputs', name: 'Select', detail: 'Native select styled with .select. Only for long lists inside forms (create sandbox, routine triggers); settings blocks use the dropdown.', render: () => uiSelect({label: 'Reasoning', options: ['Light', 'Medium', 'High'], value: 'Medium'})},
  {id: 'dropdown', section: 'Inputs', name: 'Dropdown', detail: 'Ghost trigger with the current value and a chevron; opens a menu with the current item checked. Use for compact settings; the native select is only for long lists in forms.', layout: 'stack', render: () => uiStates([
    {label: 'Enabled', html: uiDropdown({label: 'Reasoning', value: 'medium', options: UI_REASONING_OPTIONS})},
    {label: 'Disabled', html: uiDropdown({label: 'Agent', value: 'codex-cua', options: [{value: 'codex-cua', label: 'Codex + Cua'}], disabled: true})}
  ]) + `<div class="design-rule-stack">${uiSettingGrid({rows: [
    {label: 'Agent', control: uiDropdown({label: 'Agent', value: 'codex-cua', options: [{value: 'codex-cua', label: 'Codex + Cua'}], disabled: true})},
    {label: 'Model', control: uiDropdown({label: 'Model', value: 'gpt-6-astra', options: [{value: 'gpt-6-astra', label: 'GPT-6 Astra'}]})},
    {label: 'Reasoning', control: uiDropdown({label: 'Reasoning', value: 'low', options: UI_REASONING_OPTIONS})}
  ]})}</div>`},
  {id: 'search', section: 'Inputs', name: 'Search', detail: 'Sidebar and command-palette query field with a leading search icon.', render: () => uiSearch()},
  {id: 'field-copy', section: 'Inputs', name: 'Copy field', detail: 'Read-only value with a copy action.', layout: 'stack', render: () => uiFieldCopy({value: 'http://localhost:4590/api', label: 'Base URL'})},
  {id: 'recipient-field', section: 'Inputs', name: 'Recipient field', detail: 'Label and borderless input in one filled row (New chat “To”). The row carries the padding; the input has none of its own fill, border or ring.', layout: 'stack', render: () => uiRecipientField({placeholder: 'Search or create a sandbox'})},
  {id: 'checkbox', section: 'Inputs', name: 'Checkbox and switch', detail: 'Member picks use checkboxes; on/off settings use the switch role.', render: () => uiStates([
    {label: 'Checked', html: uiCheckbox({label: 'Papacito', checked: true})},
    {label: 'Unchecked', html: uiCheckbox({label: 'Mamacita'})},
    {label: 'Switch', html: uiSwitch({label: 'Notifications', checked: true})}
  ])},

  {id: 'avatar', section: 'Identity', name: 'Avatar', detail: 'Emoji or initials are content; groups use the users icon. Sizes sm / default / lg.', render: () => uiStates([
    {label: 'Sandbox · sm', html: uiAvatar({size: 'sm'})},
    {label: 'Sandbox', html: uiAvatar()},
    {label: 'Group', html: uiAvatar({icon: 'group'})},
    {label: 'Workspace · lg', html: uiAvatar({mark: 'S', size: 'lg'})}
  ])},
  {id: 'running-state', section: 'Identity', name: 'Running shimmer', detail: 'A traveling highlight for active execution only. Use ui.runningText() for HTML or SVG labels and ui.runningArrow() over a diagram path. Waiting, disconnected and finished states stay static. Reduced motion uses a steady highlight.', render: () => uiStates([
    {label: 'Working', html: uiRunningText()},
    {label: 'Completed · static', html: uiRunningText({label: 'Completed', running: false})},
    {label: 'Active diagram', html: `<svg width="230" height="75" aria-label="Running state and arrow preview">${uiRunningText({svg:true,x:10,y:20})}<path d="M10 50 H210" fill="none" stroke="var(--brand)"/>${uiRunningArrow({path:'M10 50 H210'})}<path d="m205 45 5 5-5 5" fill="none" stroke="var(--brand)"/></svg>`}
  ])},
  {id: 'dot', section: 'Identity', name: 'Status dot', detail: 'Running versus idle sandbox marker.', render: () => uiStates([
    {label: 'Running', html: uiDot({running: true})},
    {label: 'Idle', html: uiDot({running: false})}
  ])},
  {id: 'badge', section: 'Identity', name: 'Badge', detail: 'Basecoat .badge. Outline for roles, secondary for states, success/warning/destructive for health.', render: () => uiStates([
    {label: 'Secondary', html: uiBadge({label: 'Ready'})},
    {label: 'Outline · lead', html: uiLeadBadge('Famalia')},
    {label: 'Success', html: uiBadge({label: 'Online', variant: 'success'})},
    {label: 'Warning', html: uiBadge({label: 'Paused', variant: 'warning'})},
    {label: 'Destructive', html: uiBadge({label: 'Error', variant: 'destructive'})}
  ])},
  {id: 'kbd', section: 'Identity', name: 'Keyboard key', detail: 'Shortcut hints in menus and the composer.', render: () => uiKbd('⌘K') + uiKbd('Esc')},

  {id: 'muted', section: 'Feedback', name: 'Muted text', detail: 'Secondary labels and helper copy.', render: () => uiMuted({text: 'No waiting tasks. Send a message to add one.'})},
  {id: 'empty', section: 'Feedback', name: 'Empty state', detail: 'Basecoat .empty: icon, title, one line of guidance and at most one action.', layout: 'stack', render: () => uiEmpty({icon: 'folder', title: 'No files yet', description: 'Files the agents publish will appear here.', action: uiButton({label: 'Upload a file', variant: 'outline', icon: 'attach'})})},
  {id: 'alert', section: 'Feedback', name: 'Alert', detail: 'Inline notice that stays on the page.', layout: 'stack', render: () => uiAlert({title: 'Capacity is reserved when created', description: 'Stopping a sandbox releases it.'}) + uiAlert({title: 'Agent sign-in required', description: 'Open the sandbox to finish the device code flow.', variant: 'destructive', icon: 'alert'})},
  {id: 'toast', section: 'Feedback', name: 'Toast', detail: 'Bottom-right, auto-dismiss. ui.toast({category, title, description}). Errors stay 6s.', layout: 'stack', render: () => uiStates([
    {label: 'Success', html: uiToastPreview()},
    {label: 'Error', html: uiToastPreview({title: 'Task failed', description: 'Sandbox unavailable. Try again once it is running.', category: 'error'})}
  ]) + uiButton({label: 'Show a live toast', variant: 'outline', size: 'sm', attrs: {onclick: "ui.toast({category:'success',title:'Task completed',description:'Report saved to the workspace.'})"}})},
  {id: 'skeleton', section: 'Feedback', name: 'Skeleton', detail: 'Loading placeholder for rows and tiles.', layout: 'stack', render: () => uiSkeleton({width: '40%'}) + uiSkeleton({width: '90%'}) + uiSkeleton({width: '70%'})},
  {id: 'tooltip', section: 'Feedback', name: 'Tooltip', detail: 'data-tooltip on any control. Hover or focus to show.', render: () => `<button class="btn" data-variant="outline" data-size="sm" ${uiTooltip('Copies the API key')}>Hover me</button>`},

  {id: 'nav-item', section: 'Navigation', name: 'List item', detail: 'Sandbox and group rows in the sidebar: 12px vertical padding, 34px avatar (30–36px), title, preview, and last-message time (clock today, date otherwise).', render: () => `<div class="bot-list design-nav-preview">${uiNavItem({active: true, time: new Date().toISOString()})}${uiNavItem({title: 'Famalia', meta: '2 members', preview: 'BBC and CNN news brief', kind: 'group', time: '2026-08-27T12:00:00'})}</div>`},
  {id: 'nav-link', section: 'Navigation', name: 'Nav link', detail: 'Stacked navigation rows: settings sections, Design pages and rail, sidebar footer. One gap (--gap-list) between rows; the selected row takes the accent fill.', render: () => `<div class="nav-list design-nav-preview">${uiNavLink({label: 'General', icon: 'settings'})}${uiNavLink({label: 'Design', icon: 'spark', selected: true})}${uiNavLink({label: 'Computer', icon: 'desktop'})}</div><div class="nav-list design-nav-preview">${uiNavLink({label: 'Buttons', size: 'sm', selected: true})}${uiNavLink({label: 'Inputs', size: 'sm'})}</div>`},
  {id: 'workspace-row', section: 'Navigation', name: 'Workspace row', detail: 'Sidebar footer. Clicking it opens the workspace menu, which is the route to Settings; there are no standalone sidebar links.', render: () => `<div class="design-nav-preview">${uiWorkspaceRow()}</div>`},
  {id: 'tabs', section: 'Navigation', name: 'Tabs', detail: 'Line tabs for switching views inside one surface (Chat / Flow, Overview / Examples).', render: () => uiTabs()},
  {id: 'chip', section: 'Navigation', name: 'Chip', detail: 'Selected members and recipients; the × removes.', render: () => `<div class="group-chips">${uiChip()}${uiChip({label: 'Everyone'})}</div>`},

  {id: 'setting-item', section: 'Settings', name: 'Setting row', detail: 'Grouped rows with a title, one line of detail and a single control.', layout: 'stack', render: () => uiSettingsGroup({items: [uiSettingItem({title: 'Sandbox Manager', detail: 'Manage your local autonomous sandboxes.', control: uiButton({label: 'Open'})}), uiSettingItem({title: 'Notifications', detail: 'Desktop alerts when a task completes.', control: uiSwitch({label: '', checked: true})})]})},
  {id: 'card', section: 'Settings', name: 'Card', detail: 'Basecoat .card with header, body and footer. Used on the API page.', layout: 'stack', render: () => uiCard({title: 'API endpoints', description: 'Management scope', body: uiMuted({text: 'GET /api/capacity · GET /api/sandboxes · POST /api/sandboxes'}), footer: uiButton({label: 'OpenAPI', variant: 'link', iconEnd: 'external'})})},

  {id: 'mention-picker', section: 'Chat', name: 'Mention picker', detail: 'Shared contract for individual and group chat: open above the composer; highlight the first match automatically; Up/Down moves selection; Tab or Enter inserts the selected reference without sending; Escape dismisses. Keep typing focus in the composer. The opaque menu must sit above messages, with readable names and truncated secondary descriptions. Use ui.openMenu with placement: top for floating composer suggestions.', layout: 'stack', render: () => `<div class="design-rule-stack">${uiMenu({label:'Mention suggestions',items:[{label:'Design',icon:'spark',attrs:{'data-highlighted':'true'}}]})}${uiInput({label:'Mention preview',value:'@des',placeholder:'Type @ to reference context'})}<span class="design-rule-note">${uiKbd('↑')} ${uiKbd('↓')} Select · ${uiKbd('Tab')} Insert · ${uiKbd('Esc')} Dismiss</span></div>`},
  {id: 'reference', section: 'Chat', name: 'Context reference', detail: 'Recognized mentions render with an icon and highlighted name. Hover or focus to inspect their type and description. Unknown references remain plain text.', render: () => ui.reference({label:'Design',kind:'Your System',detail:'Current components, tokens, styles and usage rules.',icon:'spark'})},
  {id: 'message', section: 'Chat', name: 'Message', detail: 'Attributed bubbles. Your messages sit right, agents sit left; status follows the time.', layout: 'stack', render: () => uiMessage({user: true, text: 'Can you both check BBC and CNN?'}) + uiMessage({status: 'completed'})},
  {id: 'current-task', section: 'Chat', name: 'Current task', detail: 'Live request bar above the conversation.', layout: 'stack', render: () => uiStates([
    {label: 'Idle', html: uiCurrentTask()},
    {label: 'Running', html: uiCurrentTask({text: 'Read BBC and CNN and share a report', live: true})}
  ])},
  {id: 'queue-row', section: 'Chat', name: 'Queue row', detail: 'Waiting task with a remove action.', layout: 'stack', render: () => `<section class="queue-panel"><h2>Queued tasks <span>(1)</span></h2>${uiQueueRow()}</section>`},
  {id: 'composer', section: 'Chat', name: 'Composer', detail: 'Attach, text, optional recipients, dictate and send. Send is the surface’s primary action.', layout: 'stack', render: () => uiComposer({placeholder: 'Message Papacito…', mention: true})},

  {id: 'file-row', section: 'Inspector', name: 'File row', detail: 'Workspace file in the inspector and files page.', layout: 'stack', render: () => uiFileRow({detail: '4 KB · Workspace'})},
  {id: 'artifact', section: 'Inspector', name: 'Artifact', detail: 'Published group file attachment.', layout: 'stack', render: () => uiArtifact()},
  {id: 'member-row', section: 'Inspector', name: 'Member row', detail: 'Group member with lead badge, remove and overflow menu.', layout: 'stack', render: () => uiMemberRow({lead: true, groupName: 'Famalia'}) + uiMemberRow({name: 'Mamacita'})},
  {id: 'recent-item', section: 'Inspector', name: 'Recent file', detail: 'Shared-file tile in the group inspector.', render: () => `<div class="recent-gallery-items grid">${uiRecentItem()}</div>`},

  {id: 'dialog', section: 'Overlays', name: 'Dialog', detail: 'Basecoat .dialog. ui.openDialog(ui.dialog({...})) shows it modally and removes it on close.', layout: 'stack', render: () => `<div class="design-dialog-preview">${uiDialog({title: 'New chat', description: 'Pick a sandbox or start a group.', body: uiSearch({placeholder: 'Search or create a sandbox'}) + `<div class="search-results">${uiButton({label: 'Create group chat', variant: 'ghost', icon: 'group', className: 'search-result'})}${uiButton({label: 'Create new sandbox', variant: 'ghost', icon: 'add', className: 'search-result'})}</div>`, open: true})}</div>` + uiButton({label: 'Open a live dialog', variant: 'outline', size: 'sm', attrs: {onclick: "ui.openDialog(ui.dialog({title:'Rename agent',description:'The new name shows everywhere this sandbox appears.',body:ui.field({label:'Name',control:ui.input({value:'Papacito',label:'Name'})}),footer:ui.button({label:'Cancel',variant:'outline',attrs:{onclick:\"this.closest('dialog').close()\"}})+ui.button({label:'Save',variant:'primary',attrs:{onclick:\"this.closest('dialog').close()\"}})}))"}})},
  {id: 'alert-dialog', section: 'Overlays', name: 'Alert dialog', detail: 'Confirmation before destructive or irreversible actions. ui.confirm() resolves to true or false.', layout: 'stack', render: () => uiAlertDialogPreview() + uiButton({label: 'Try ui.confirm()', variant: 'outline', size: 'sm', attrs: {onclick: "ui.confirm({title:'Stop this sandbox?',description:'Queued tasks stay queued and resume when it starts again.',confirmLabel:'Stop sandbox',destructive:true}).then(ok=>ui.toast({category:ok?'success':'info',title:ok?'Sandbox stopped':'Kept running'}))"}})},
  {id: 'menu', section: 'Overlays', name: 'Menu', detail: 'Context and overflow menus. ui.openMenu(ui.menu({items}), {anchor}) positions and dismisses.', render: () => uiMenu({items: [{heading: 'Papacito', sub: 'Role in Famalia'}, {label: 'Rename agent', icon: 'edit'}, {label: 'Make lead', icon: 'crown'}, {label: 'Notifications', icon: 'check', checked: true}, {separator: true}, {label: 'Remove from group', icon: 'remove', danger: true}], className: 'design-menu-preview'}) + uiButton({label: 'Open a live menu', variant: 'outline', size: 'sm', attrs: {onclick: "ui.openMenu(ui.menu({items:[{label:'Rename agent',icon:'edit'},{label:'Make lead',icon:'crown'},{separator:true},{label:'Remove from group',icon:'remove',danger:true}]}),{anchor:this})"}})},
  {id: 'drawer', section: 'Overlays', name: 'Drawer', detail: 'Side sheet for the inspector on narrow screens. Slides from the right; Escape or the backdrop closes it.', layout: 'stack', render: () => uiDrawerPreview()}
];

/* ------------------------------------------------------------------------- */
/* Rules                                                                      */
/* ------------------------------------------------------------------------- */

/**
 * Design rules shown on Settings → Design → Rules. Each rule renders a live
 * "do" and "don't" example from the same kit the product uses, and
 * test/design-system.test.ts enforces the mechanically checkable ones.
 * @type {Array<{id: string, title: string, rationale: string, check: string, good: () => string, bad: () => string}>}
 */
const UI_RULES = [
  {
    id: 'no-eyebrows',
    title: 'No eyebrows',
    rationale: 'Sections are introduced by a plain sentence-case heading. Small uppercase, letter-spaced labels add a second typographic voice and read as chrome rather than content.',
    check: 'No text-transform: uppercase or tracked small labels in product CSS.',
    good: () => `<div class="design-rule-stack"><h2 class="setting-label">Connections</h2>${uiSettingItem({title: 'Management API', detail: 'Fleet capacity and scoped access.', control: uiButton({label: 'Open API', size: 'sm'})})}</div>`,
    bad: () => `<div class="design-rule-stack"><small class="design-eyebrow">Connections</small>${uiSettingItem({title: 'Management API', detail: 'Fleet capacity and scoped access.', control: uiButton({label: 'Open API', size: 'sm'})})}</div>`
  },
  {
    id: 'no-outlines',
    title: 'No focus rings or outlines',
    rationale: 'Nothing glows. Text fields show focus with the caret alone; their border never changes. Buttons, tabs and menu items show keyboard focus (:focus-visible) as a 1px border or the accent background, and nothing for pointer focus. No rings, halos, offsets or browser outlines.',
    check: 'No outline: or focus ring declarations outside components.css.',
    good: () => `<div class="design-rule-stack">${uiInput({value: 'Read BBC and CNN and share a report.', label: 'Focused input, correct', readonly: true})}${uiButton({label: 'Save group', variant: 'outline', size: 'sm', className: 'design-focus-good'})}<span class="design-rule-note">Input focused: no change. Button: keyboard focus only.</span></div>`,
    bad: () => `<div class="design-rule-stack">${uiInput({value: 'Read BBC and CNN and share a report.', label: 'Focused input, wrong', className: 'design-focus-bad', readonly: true})}${uiButton({label: 'Save group', variant: 'outline', size: 'sm', className: 'design-focus-bad'})}</div>`
  },
  {
    id: 'icons-over-text',
    title: 'Icons over text for universal actions',
    rationale: 'Copy, download, refresh, close, add and more are icon buttons with an aria-label and tooltip. Text labels are for verbs without a universal icon, such as Save group.',
    check: 'No text button labelled Copy, Download, Refresh or Close.',
    good: () => `${uiToggleIconButton({label: 'Copy', copy: true})}${uiIconButton({name: 'download', label: 'Download'})}${uiIconButton({name: 'refresh', label: 'Refresh'})}${uiIconButton({name: 'close', label: 'Close'})}${uiButton({label: 'Save group', variant: 'primary', size: 'sm'})}`,
    bad: () => `${uiButton({label: 'Copy', size: 'sm'})}${uiButton({label: 'Download', size: 'sm'})}${uiButton({label: 'Refresh', size: 'sm'})}${uiButton({label: 'Close', size: 'sm'})}`
  },
  {
    id: 'one-element-state',
    title: 'One element per action; toggle its state',
    rationale: 'A control that changes state stays the same element and flips aria-pressed, swapping its icon and label: copy becomes a tick, play becomes stop, list and grid share a toggle. Never render two siblings and hide one.',
    check: 'State changes use ui.toggleIconButton() / ui.setPressed(), not hidden sibling controls.',
    good: () => `${uiToggleIconButton({name: 'play', activeName: 'stop', label: 'Start', activeLabel: 'Stop', variant: 'outline', attrs: {onclick: "ui.setPressed(this, this.getAttribute('aria-pressed') !== 'true')"}})}${uiToggleIconButton({label: 'Copy', copy: true, variant: 'outline'})}<span class="design-rule-note">Click to toggle in place</span>`,
    bad: () => `${uiButton({label: 'Start', icon: 'play', size: 'sm'})}${uiButton({label: 'Stop', icon: 'stop', variant: 'destructive', size: 'sm'})}<span class="design-rule-note">Two buttons, one hidden at a time</span>`
  },
  {
    id: 'icons-from-kit',
    title: 'Icons come from ui.icon() only',
    rationale: 'One Lucide set, 16px, stroke 2, currentColor. Text glyphs, emoji and hand-drawn paths drift in weight and alignment and cannot follow the theme.',
    check: 'Product files contain no glyph characters and no icon paths.',
    good: () => ['close', 'check', 'more', 'add', 'trash', 'edit'].map((name) => uiIconButton({name, label: name})).join(''),
    bad: () => `<span class="design-glyphs">&times; &#10003; &#8943; &#65291; &#128465; &#9998;</span>`
  },
  {
    id: 'overlays-via-kit',
    title: 'Overlays go through the kit',
    rationale: 'Dialogs use ui.dialog() and ui.openDialog(), confirmations ui.confirm(), menus ui.menu() and ui.openMenu(), notices ui.toast(). Native confirm/alert and hand-built menus look foreign and skip focus handling.',
    check: 'No createElement(\'dialog\'), window.confirm, window.alert or custom menu classes.',
    good: () => `<pre class="design-code">const ok = await ui.confirm({title: 'Remove member?', destructive: true});</pre>${uiButton({label: 'Try it', variant: 'outline', size: 'sm', attrs: {onclick: "ui.confirm({title: 'Remove Mamacita from the group?', description: 'The sandbox keeps running.', confirmLabel: 'Remove', destructive: true})"}})}`,
    bad: () => `<pre class="design-code">if (confirm('Remove member?')) remove();</pre>${uiButton({label: 'Native confirm', variant: 'outline', size: 'sm', attrs: {disabled: true}})}`
  },
  {
    id: 'tokens-not-hex',
    title: 'Colour and spacing come from tokens',
    rationale: 'Markup and component CSS reference var(--brand), var(--border), var(--muted-foreground) and the spacing scale, never raw hex or pixel one-offs, so the theme can change in one place.',
    check: 'No hex, rgb() or hsl() literals in ui-kit.js, components.css or the ui.html stylesheet.',
    good: () => `<span class="design-rule-swatch" style="background:var(--brand)"></span><code>var(--brand)</code><span class="design-rule-swatch" style="background:var(--secondary)"></span><code>var(--secondary)</code>`,
    bad: () => `<span class="design-rule-swatch" style="background:var(--brand)"></span><code>${'#' + '539cf3'}</code><span class="design-rule-swatch" style="background:var(--secondary)"></span><code>${'#' + '202023'}</code>`
  },
  {
    id: 'sentence-case',
    title: 'Sentence case everywhere',
    rationale: 'Headings, labels and buttons capitalise the first word and proper nouns only. Title Case and ALL CAPS shout and slow reading.',
    check: 'Labels in the kit and product markup are sentence case.',
    good: () => `${uiButton({label: 'Save group', variant: 'primary', size: 'sm'})}${uiButton({label: 'Add member', icon: 'add', variant: 'ghost', size: 'sm'})}`,
    bad: () => `${uiButton({label: 'Save Group', variant: 'primary', size: 'sm'})}${uiButton({label: 'ADD MEMBER', icon: 'add', variant: 'ghost', size: 'sm'})}`
  },
  {
    id: 'one-primary',
    title: 'One primary action per surface',
    rationale: 'A dialog, form or panel has at most one primary button. Everything else is outline, secondary or ghost so the eye lands on the main action.',
    check: 'No two primary buttons in the same dialog footer or form.',
    good: () => `${uiButton({label: 'Cancel', variant: 'outline', size: 'sm'})}${uiButton({label: 'Create group', variant: 'primary', size: 'sm'})}`,
    bad: () => `${uiButton({label: 'Cancel', variant: 'primary', size: 'sm'})}${uiButton({label: 'Create group', variant: 'primary', size: 'sm'})}`
  },
  {
    id: 'severity-colours',
    title: 'Dangerous actions carry a severity colour',
    rationale: 'Remove, delete, stop and cancel are tinted --destructive wherever they appear: a ghost button with danger: true, the destructive variant when it is the main action, menu items with danger: true. Neutral grey hides the risk.',
    check: 'Buttons and menu items labelled Remove, Delete or Stop set danger or the destructive variant.',
    good: () => `${uiButton({label: 'Remove', variant: 'ghost', size: 'xs', icon: 'close', danger: true})}${uiIconButton({name: 'trash', label: 'Delete routine', danger: true})}${uiButton({label: 'Delete sandbox', variant: 'destructive', size: 'sm'})}`,
    bad: () => `${uiButton({label: 'Remove', variant: 'ghost', size: 'xs', icon: 'close'})}${uiIconButton({name: 'trash', label: 'Delete routine'})}${uiButton({label: 'Delete sandbox', variant: 'secondary', size: 'sm'})}`
  },
  {
    id: 'consistent-gaps',
    title: 'One gap for stacked items',
    rationale: 'Every list of like rows (settings nav, design nav, sidebar, menus) uses --gap-list (2px); blocks use --gap-stack (8px); sections use --gap-section (16px). Other gaps stay on the 4px scale. A 1px gap next to a 2px gap reads as a mistake, not a choice.',
    check: 'Stacked nav lists use gap: var(--gap-list) or gap-(--gap-list); no gap of 1px, 3px, 5px, 6px, 7px, 9px, 10px or 14px anywhere in the CSS.',
    good: () => `<div class="design-gap-demo"><nav class="design-gap-nav" style="gap: var(--gap-list)">${uiButton({label: 'General', variant: 'ghost', size: 'sm', icon: 'settings'})}${uiButton({label: 'Design', variant: 'secondary', size: 'sm', icon: 'spark'})}</nav><nav class="design-gap-nav" style="gap: var(--gap-list)">${uiButton({label: 'Components', variant: 'ghost', size: 'sm', icon: 'grid'})}${uiButton({label: 'Rules', variant: 'secondary', size: 'sm', icon: 'check'})}</nav></div>`,
    bad: () => `<div class="design-gap-demo"><nav class="design-gap-nav" style="gap: 6px">${uiButton({label: 'General', variant: 'ghost', size: 'sm', icon: 'settings'})}${uiButton({label: 'Design', variant: 'secondary', size: 'sm', icon: 'spark'})}</nav><nav class="design-gap-nav" style="gap: 0">${uiButton({label: 'Components', variant: 'ghost', size: 'sm', icon: 'grid'})}${uiButton({label: 'Rules', variant: 'secondary', size: 'sm', icon: 'check'})}</nav></div>`
  },
  {
    id: 'aligned-settings',
    title: 'Settings rows share one grid',
    rationale: 'Label column has a fixed width and every control starts at the same x and fills the row; controls in settings are borderless dropdowns, not native selects.',
    check: 'Settings blocks use .setting-grid and ui.dropdown(); no <select class="select"> inside .setting-grid.',
    good: () => `<div class="design-rule-stack">${uiSettingGrid({rows: [
      {label: 'Agent', control: uiDropdown({label: 'Agent', value: 'codex-cua', options: [{value: 'codex-cua', label: 'Codex + Cua'}], disabled: true})},
      {label: 'Model', control: uiDropdown({label: 'Model', value: 'gpt-6-astra', options: [{value: 'gpt-6-astra', label: 'GPT-6 Astra'}]})},
      {label: 'Reasoning', control: uiDropdown({label: 'Reasoning', value: 'low', options: UI_REASONING_OPTIONS})}
    ]})}</div>`,
    bad: () => `<div class="design-rule-stack design-misaligned-settings"><label>Agent${uiSelect({label: 'Agent', options: ['Codex + Cua'], attrs: {disabled: true, style: 'width:60%'}})}</label><label>Model${uiSelect({label: 'Model', options: ['GPT-6 Astra'], attrs: {style: 'width:82%'}})}</label><label>Reasoning${uiSelect({label: 'Reasoning', options: ['Light', 'Medium', 'High'], attrs: {style: 'width:70%'}})}</label></div>`
  },
  {
    id: 'padded-fields',
    title: 'Text never touches a fill',
    rationale: 'Any element with a fill or border carries horizontal padding from the spacing scale (8px or 12px); text, carets and placeholders never sit on the edge. When a control is nested in a filled row, the row owns the padding and the control is flush and transparent.',
    check: 'Fields and filled rows use px-2/px-3; no .input with px-0 outside a padded row.',
    good: () => `<div class="design-rule-stack">${uiRecipientField({placeholder: 'Search or create a sandbox', inputLabel: 'Padded row, correct'})}<span class="design-rule-note">Row: fill + px-3. Input: transparent, px-0.</span></div>`,
    bad: () => `<div class="design-rule-stack">${uiRecipientField({placeholder: 'Search or create a sandbox', inputLabel: 'Filled input, wrong', className: 'design-bad-field'})}<span class="design-rule-note">Input carries its own fill but no padding: the caret sits on the edge.</span></div>`
  },
  {
    id: 'animate-layout',
    title: 'Panels slide, never pop',
    rationale: 'Showing or hiding a side panel animates width and transform over --duration-base with --ease-out so the neighbouring column and its composer resize smoothly. Reduced-motion users get the end state immediately.',
    check: 'Panel toggles use the motion tokens; no display:none flip without a transition.',
    good: () => `<div class="design-rule-stack">${uiMotionDemo({live: true})}<span class="design-rule-note">Track width and opacity transition over var(--duration-base) var(--ease-out); the composer widens with it.</span></div>`,
    bad: () => `<div class="design-rule-stack">${uiMotionDemo({hidden: true, pop: true})}<span class="design-rule-note">Toggled with display:none: the panel pops and the composer jumps to full width in one frame.</span></div>`
  },
  {
    id: 'icon-toggles',
    title: 'Panel toggles are icon-only and appear only when useful',
    rationale: 'A control that reveals a panel is an icon button (desktop for the screen, panel icon for details) and is shown only while the panel is hidden; the open panel carries its own close button.',
    check: 'No ui.button({label:"Screen"…}); the toggle is ui.iconButton and is not rendered while the panel is open.',
    good: () => `<div class="design-rule-stack">${uiMotionDemo({hidden: true})}<span class="design-rule-note">Panel hidden: ${uiIconButton({name: 'desktop', label: 'Show screen', size: 'icon-xs'})} ${uiIconButton({name: 'panelRight', label: 'Show details', size: 'icon-xs'})} reveal it. Panel open: only its own ${uiIconButton({name: 'chevronsRight', label: 'Hide panel', size: 'icon-xs'})} remains.</span></div>`,
    bad: () => `<div class="design-rule-stack"><div class="design-motion-demo design-motion-text-toggle" aria-label="Text toggle beside an open panel"><div class="design-motion-chat"><div class="design-motion-header">${uiButton({label: 'Screen', icon: 'desktop', variant: 'outline', size: 'xs', attrs: {disabled: true}})}</div><span class="design-motion-composer"></span></div><aside class="design-motion-panel"></aside></div><span class="design-rule-note">A text button labelled Screen stays visible while the panel is already open.</span></div>`
  }
];

/* ------------------------------------------------------------------------- */
/* Public API                                                                 */
/* ------------------------------------------------------------------------- */

const ui = {
  escape: uiEscape,
  attrs: uiAttrs,
  id: uiId,
  token: uiToken,
  icon: uiIcon,
  icons: uiIcons,
  iconNames: UI_ICON_NAMES,
  defaultAvatar: UI_DEFAULT_AVATAR,
  states: uiStates,
  colorTokens: uiColorTokens,
  typeScale: uiTypeScale,
  spacingScale: uiSpacingScale,
  radiusScale: uiRadiusScale,
  elevationScale: uiElevationScale,
  button: uiButton,
  iconButton: uiIconButton,
  toggleIconButton: uiToggleIconButton,
  setPressed: uiSetPressed,
  input: uiInput,
  textarea: uiTextarea,
  select: uiSelect,
  dropdown: uiDropdown,
  dropdownValue: uiDropdownValue,
  dropdownLabel: uiDropdownLabel,
  setDropdownValue: uiSetDropdownValue,
  settingGrid: uiSettingGrid,
  search: uiSearch,
  fieldCopy: uiFieldCopy,
  checkbox: uiCheckbox,
  switch: uiSwitch,
  field: uiField,
  recipientField: uiRecipientField,
  avatar: uiAvatar,
  dot: uiDot,
  runningText: uiRunningText,
  runningArrow: uiRunningArrow,
  lastMessageTime: uiLastMessageTime,
  navTime: uiNavTime,
  badge: uiBadge,
  leadBadge: uiLeadBadge,
  muted: uiMuted,
  kbd: uiKbd,
  tooltip: uiTooltip,
  empty: uiEmpty,
  alert: uiAlert,
  skeleton: uiSkeleton,
  toaster: uiToaster,
  toast: uiToast,
  navItem: uiNavItem,
  workspaceRow: uiWorkspaceRow,
  navLink: uiNavLink,
  tabs: uiTabs,
  chip: uiChip,
  settingItem: uiSettingItem,
  settingsGroup: uiSettingsGroup,
  card: uiCard,
  message: uiMessage,
  currentTask: uiCurrentTask,
  queueRow: uiQueueRow,
  composer: uiComposer,
  fileRow: uiFileRow,
  artifact: uiArtifact,
  memberRow: uiMemberRow,
  recentItem: uiRecentItem,
  dialog: uiDialog,
  openDialog: uiOpenDialog,
  confirm: uiConfirm,
  menu: uiMenu,
  menuItems: uiMenuItems,
  openMenu: uiOpenMenu,
  closeMenu: uiCloseMenu,
  components: UI_KIT,
  rules: UI_RULES
};

// Render known mentions only in text nodes, never inside link URLs or markup.
ui.reference = ({label,kind,detail,icon='link'}) => `<span class="chat-reference" tabindex="0" aria-label="${uiEscape(label+': '+kind+'. '+detail)}">${uiIcon(icon)}<span>${uiEscape(label)}</span><span class="chat-reference-preview" role="tooltip"><strong>${uiEscape(label)}</strong><small>${uiEscape(kind)}</small><span>${uiEscape(detail)}</span></span></span>`;
ui.renderReferences = (html, references) => {
 const template=document.createElement('template');template.innerHTML=html;
 const walker=document.createTreeWalker(template.content,NodeFilter.SHOW_TEXT),nodes=[];
 while(walker.nextNode())nodes.push(walker.currentNode);
 for(const node of nodes){
  if(node.parentElement?.closest('a,pre,.chat-reference'))continue;
  const text=node.textContent,pattern=/(?<![\w])`?@(?:\[([^\]\n]+)\]|([\w-]+))`?/g;let match,last=0,changed=false;const fragment=document.createDocumentFragment();
  while((match=pattern.exec(text))){const name=match[1]||match[2],ref=references.find(r=>r.label.toLowerCase()===name.toLowerCase()||r.alias?.toLowerCase()===name.toLowerCase());if(!ref)continue;
   fragment.append(document.createTextNode(text.slice(last,match.index)));const chip=document.createElement('template');chip.innerHTML=ui.reference(ref);fragment.append(chip.content);last=pattern.lastIndex;changed=true;
  }
  if(changed){fragment.append(document.createTextNode(text.slice(last)));node.replaceWith(fragment);}
 }
 return template.innerHTML;
};
window.ui = ui;
window.UI_KIT = UI_KIT;
window.UI_RULES = UI_RULES;
window.icon = uiIcon;
