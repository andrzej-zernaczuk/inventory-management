---
name: vue-optimize
description: Analyze Vue 3 component structure and suggest performance and code-reuse optimizations, with file:line findings ranked by impact. Use this skill whenever the user asks to review, audit, optimize, refactor, slim down or find duplication in Vue components, views, composables or .vue files, or asks things like "why is this page slow", "is this component too big", "what can be extracted", or "what's duplicated across views" - even if they do not say "optimize". Report-only by default; fixes go through the vue-expert agent.
---

# Vue Component Optimization Review

Find the changes that make the Vue client faster to render, smaller, and less duplicated, then report them so the user can choose what to fix. This project is a Vue 3 Composition API app in `client/src` (`views/`, `components/`, `composables/`, `utils/`); its conventions are in `client/CLAUDE.md`, so read that first and treat it as the standard findings are measured against.

## Workflow

1. **Pick the target.** Use the files or directories the user names. With no target, use the changed `.vue`/`.js` files from `git diff --name-only main...HEAD` plus uncommitted changes. A narrow target keeps the report useful; only scan all of `client/src` when asked or when the user wants cross-file duplication.
2. **Run the metrics script** for a deterministic first pass:
   `python3 -I .claude/skills/vue-optimize/scripts/vue_metrics.py <paths>`
   It reports section sizes against the `client/CLAUDE.md` extraction thresholds, weak or missing `v-for` keys, function calls inside templates, unvalidated `new Date(` use, Options/Composition mixing, and helpers defined in more than one file. These are candidates, not verdicts: a helper with the same name in two files may differ, and a template call may be cheap. Read the flagged code before reporting it.
3. **Read the components** the script flagged, plus any target file it did not. Use `references/checklist.md` for what to look for in each category and what is a false positive.
4. **Cross-check reuse** against what already exists before suggesting a new abstraction: `client/src/utils/currency.js`, `client/src/composables/*`, and existing components. Recommending `formatCurrencyWithDecimals` when it already exists beats proposing a new helper.
5. **Write the report** in the format below, then offer to fix.

## Categories

- **Performance**: work that reruns needlessly or scales badly (methods called from templates instead of computed, recomputation in render, missing debounce on input-driven requests, `v-if` on frequently toggled blocks, index keys, large lists with no virtualization or pagination, chart data rebuilt each render).
- **Structure**: components past the thresholds (template over 100 lines, script over 150), mixed concerns, prop mutation, Options API mixed into Composition API.
- **Reuse**: logic or markup that exists in more than one place and should live in `utils/`, a composable, or a shared component (formatters, load/error/loading boilerplate, repeated modal chrome, repeated table or card markup).
- **Conventions**: gaps against `client/CLAUDE.md` and the root `CLAUDE.md` - unique keys, validated dates, loading and error states, no emojis in UI, design-system colors.

Weight findings by impact, not by count. One index key on a 5-row static table matters less than a 1,000-line view that refetches on every keystroke. Say so when something is minor, and say when a file is fine.

## Report format

Use this structure so reports are comparable across runs:

```
# Vue optimization report: <target>

## Summary
<2-3 sentences: overall state, the one or two changes worth doing first>

## Findings
### 1. <short title> - <High|Medium|Low> - <Performance|Structure|Reuse|Conventions>
- Where: `client/src/views/X.vue:123` (and other locations)
- Problem: <what is wrong and why it costs something>
- Suggestion: <the concrete change; name the target file or composable>
- Effort: <S|M|L>

## Cross-file duplication
<helpers/markup found in multiple files, with the files and a proposed home>

## Not worth changing
<flagged by the script or checklist but fine, and why>
```

Order findings by impact, highest first. Every finding needs a real `file:line`; if you cannot point at the code, drop the finding.

## After the report

Ask which findings to apply. Do not edit files during the review. Project rules say any significant `.vue` change must go to the `vue-expert` agent, so hand the chosen findings to it with the file paths and the exact suggestion. Small edits to plain `.js` files (utils, composables) can be made directly. After fixes, rerun the metrics script on the touched files and report what changed.

## Why these constraints

- Report first, because refactors like extracting a modal base component or moving `formatDate` into `utils/` touch many files and the user should pick the trade-offs.
- Read before reporting, because the script is regex-based and will flag things that are fine.
- Check existing utilities first, because the most common reuse mistake is adding a second helper next to an unused first one.
