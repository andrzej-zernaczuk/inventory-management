# Vue optimization checklist

Read the section for each category you are reviewing. Each item says what to look for and when it is a false positive, so you do not pad the report.

## Performance

- **Function calls in templates** (`{{ fmt(row.x) }}`, `v-for="x in getRows()"`): called on every render of that component. Cheap pure formatters on a short list are fine. Flag when the call filters, sorts, or aggregates, or runs inside a long list. Fix: a `computed` that returns the derived array, or precompute fields once.
- **Heavy work in methods vs computed**: anything derived from refs that is read in the template should be `computed` (cached). Flag methods that loop over `allOrders`-sized arrays and are called from the template.
- **Input-driven requests without debounce**: sliders, search boxes and filters that call `api.*` on every event. Look for `@input`/`watch` firing a request directly. Fix: debounce plus dropping stale responses (see `Restocking.vue` for the pattern used here).
- **Watchers refetching on every filter change**: several watchers or `watch` on multiple refs each triggering a full reload. Flag when one change causes duplicate requests.
- **`v-if` vs `v-show`**: `v-if` on a block that is toggled often (tabs, dropdowns, charts) recreates it each time. `v-if` for rarely shown content is correct.
- **Index or missing `v-for` keys**: `:key="index"` or no key. Use `sku`, `id`, `month` etc. A static list that never reorders is low impact.
- **Large unpaginated lists**: tables rendering hundreds of rows (the orders table shows all 250). Suggest pagination or virtualization only if the list can realistically grow.
- **Chart data rebuilt each render**: SVG chart coordinates computed in the template or a method instead of a computed property.
- **Sequential awaits that could be parallel**: independent `await api.*` calls in a row; `Promise.all` fixes it.

## Structure

- **Size thresholds** (from `client/CLAUDE.md`): template over 100 lines, script over 150 lines, reused in more than one place, or a distinct responsibility. A long but flat template (one big table) is lower priority than a component mixing data loading, formatting and several panels.
- **Mixed concerns**: data fetching, formatting and presentation in one view. Candidates for a composable (loading) and child components (panels).
- **Prop mutation**: assigning to `props.x` or mutating a prop object. Fix: emit an update event.
- **Options API mixed with Composition API**: `data()`/`methods` alongside `setup()`.
- **Giant `return {}` from setup**: a symptom of too many responsibilities; mention only alongside a size finding.

## Reuse

- **Formatters redefined per file**: `formatDate`, `formatCurrency`, `translateCategory`, stock-status helpers. First check `utils/currency.js` and `composables/useI18n.js`; suggest moving to `utils/` or the composable if not already there.
- **Load/error/loading boilerplate**: the same `loading`/`error` refs plus try/catch/finally in many views. A `useAsyncData`-style composable is worth it only when three or more views share the exact shape.
- **Repeated modal chrome**: overlay, header, close button, escape handling copied across `*DetailModal.vue`. A shared base modal component is the usual fix; check whether the markup and styles actually match before proposing it.
- **Repeated table/card/KPI markup and CSS**: the same classes and structure in several views. Propose a component only if the variation can be expressed with props or slots.
- **Duplicated scoped CSS**: large identical style blocks across modals; move shared rules to `App.vue` global styles or a shared component.
- **Do not over-abstract**: two similar-looking snippets are not duplication if they will diverge. Say "leave as is" for those.

## Conventions

- Unique `v-for` keys (never index).
- Dates validated (`isNaN(date.getTime())`) before `getMonth()` and similar.
- Loading and error states shown for every async load.
- No emojis in UI.
- Colors from the design system (slate/gray `#0f172a`, `#64748b`, `#e2e8f0`; status green/blue/yellow/red); charts as custom SVG, layouts via CSS Grid.
- Pydantic/JSON changes are out of scope here; this skill covers the client only.
