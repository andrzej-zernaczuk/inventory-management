#!/usr/bin/env python3
"""Static metrics for Vue single-file components.

Gives the vue-optimize skill a cheap, deterministic first pass: where the
big components are, which lists have weak keys, and which helpers are
defined in more than one file. It flags *candidates*; the skill still has
to read the code to decide whether a candidate is a real problem.

Usage: vue_metrics.py <file-or-dir> [<file-or-dir> ...]
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# client/CLAUDE.md "When to extract component" thresholds
TEMPLATE_LINE_LIMIT = 100
SCRIPT_LINE_LIMIT = 150

EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
SECTION = re.compile(r'<(template|script|style)\b[^>]*>(.*?)</\1>', re.S)
VFOR = re.compile(r'<[^>]*\sv-for="([^"]+)"[^>]*>', re.S)
KEY = re.compile(r':key="([^"]+)"')
# call expressions inside {{ }} or v-bind/v-if, e.g. {{ fmt(x) }}; these rerun every render
TEMPLATE_CALL = re.compile(r'\{\{[^}]*?\b([A-Za-z_]\w*)\s*\(')
# local helper definitions: `const formatX = (...) =>`, `function formatX(`, or
# `const currencySymbol = computed(` (copy-pasted computeds are duplication too)
HELPER_DEF = re.compile(
    r'(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>'
    r'|function\s+(\w+)\s*\('
    r'|(?:const|let)\s+(\w+)\s*=\s*computed\(')
# names too generic to count as copy-pasted duplicates
IGNORED_HELPERS = {'setup', 'onMounted', 'data', 'mounted'}


def collect(paths):
    files = []
    for raw in paths:
        p = Path(raw)
        files.extend(sorted(p.rglob('*.vue')) if p.is_dir() else [p])
    return files


def analyze(path):
    text = path.read_text(encoding='utf-8')
    sections = {name: body for name, body in SECTION.findall(text)}
    lines = {name: body.strip('\n').count('\n') + 1 if body.strip() else 0
             for name, body in sections.items()}
    template = sections.get('template', '')
    script = sections.get('script', '')

    weak_keys, missing_keys = [], []
    for match in VFOR.finditer(template):
        tag = match.group(0)
        line = text[:text.index(tag)].count('\n') + 1
        key = KEY.search(tag)
        if not key:
            missing_keys.append(line)
            continue
        # the second v-for variable is the index; keying on it breaks DOM reuse
        loop_vars = re.match(r'\s*\(([^)]*)\)', match.group(1))
        index_name = loop_vars.group(1).split(',')[1].strip() if loop_vars and ',' in loop_vars.group(1) else None
        if key.group(1).strip() in {'index', 'i', 'idx'} or (index_name and key.group(1).strip() == index_name):
            weak_keys.append(line)

    template_calls = sorted({m.group(1) for m in TEMPLATE_CALL.finditer(template)})
    helpers = sorted({a or b or c for a, b, c in HELPER_DEF.findall(script)} - IGNORED_HELPERS)

    return {
        'file': str(path),
        'lines': lines,
        'oversized': [
            label for label, over in (
                ('template', lines.get('template', 0) > TEMPLATE_LINE_LIMIT),
                ('script', lines.get('script', 0) > SCRIPT_LINE_LIMIT),
            ) if over
        ],
        'v_for_index_key_lines': weak_keys,
        'v_for_missing_key_lines': missing_keys,
        'template_function_calls': template_calls,
        # setup() alongside data()/methods mixes the two APIs; client/CLAUDE.md forbids it
        'uses_options_and_composition': 'setup(' in script and bool(re.search(r'\b(data\s*\(\)|methods\s*:)', script)),
        'unvalidated_date_parse': bool(re.search(r'new Date\(', script)) and 'isNaN' not in script,
        'has_loading_state': bool(re.search(r'\bloading\b', script)),
        'has_error_state': bool(re.search(r'\berror\b', script)),
        'emoji_in_template': bool(EMOJI.search(template)),
        'local_helpers': helpers,
        'watchers': len(re.findall(r'\bwatch(?:Effect)?\(', script)),
        'debounced': 'debounce' in script.lower() or 'setTimeout' in script,
    }


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    results = [analyze(f) for f in collect(argv)]

    owners = defaultdict(list)
    for r in results:
        for name in r['local_helpers']:
            owners[name].append(r['file'])
    duplicated = {name: files for name, files in sorted(owners.items()) if len(files) > 1}

    print(json.dumps({'files': results, 'helpers_defined_in_multiple_files': duplicated}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
