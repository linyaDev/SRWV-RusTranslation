#!/usr/bin/env python3
"""
Extract / inject dialog blocks in SRW V stage Lua scripts.

Dialog blocks are Lua long strings:
    [[Speaker
    「Line 1
    　Line 2」]]
Comment blocks --[[ ... ]] are skipped. Only blocks containing 「 count.

extract: ru_lua_dialog.py extract <in.lua> <out.json>
    JSON: {"blocks": [{"i": idx, "speaker": str, "text": str, "orig": str}]}
    idx = index among ALL non-comment long-bracket strings in the file.
inject:  ru_lua_dialog.py inject <in.lua> <translated.json> <out.lua>
    Replaces block idx with "speaker\ntext"; verifies "orig" still matches.
"""
import json
import re
import sys

BLOCK = re.compile(r'\[\[(.*?)\]\]', re.S)
QSTR = re.compile(r'"([^"\n]{2,90})"')
CODEISH = re.compile(r'[_()\\\\{}=<>;]|\.lua|\.dat|^[A-Z0-9 .:-]+$')


def is_text_block(body: str) -> bool:
    """Game text: dialog 「」, thoughts （）, location cards, narration."""
    if '「' in body or '（' in body:
        return True
    return bool(re.search(r'[A-Za-z]{2}', body))


def is_text_qstring(q: str) -> bool:
    """Win/lose conditions, choices, DVE lines — not identifiers."""
    if not re.search(r'[a-z] [a-z]', q) and not re.search(r'[a-z].*[.!?]$', q):
        return False
    return not CODEISH.search(q)


def iter_blocks(src: str):
    """Yield (match, is_comment) for every [[...]] long string."""
    for m in BLOCK.finditer(src):
        pre = src[max(0, m.start() - 2):m.start()]
        yield m, pre == '--'


def extract(in_path, out_path):
    src = open(in_path, encoding='utf-8').read()
    blocks = []
    idx = 0
    spans = []
    for m, is_comment in iter_blocks(src):
        if not is_comment:
            spans.append((m.start(), m.end()))
            body = m.group(1)
            if is_text_block(body):
                first, _, rest = body.partition('\n')
                if '「' in rest or '（' in rest or ('「' not in first and '（' not in first and rest):
                    blocks.append({'i': idx, 'speaker': first, 'text': rest, 'orig': body})
                else:
                    blocks.append({'i': idx, 'speaker': '', 'text': body, 'orig': body})
        idx += 1
    qstrings = []
    seen = set()
    for m in QSTR.finditer(src):
        if any(a <= m.start() < b for a, b in spans):
            continue
        q = m.group(1)
        if q not in seen and is_text_qstring(q):
            seen.add(q)
            qstrings.append({'q': q, 'ru': ''})
    out = {'blocks': blocks}
    if qstrings:
        out['qstrings'] = qstrings
    json.dump(out, open(out_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'{len(blocks)} blocks, {len(qstrings)} qstrings -> {out_path}')


def inject(in_path, json_path, out_path):
    src = open(in_path, encoding='utf-8').read()
    data = json.load(open(json_path, encoding='utf-8'))
    tr = {b['i']: b for b in data['blocks']}
    out = []
    pos = 0
    idx = 0
    replaced = 0
    for m, is_comment in iter_blocks(src):
        if not is_comment and idx in tr:
            b = tr[idx]
            if m.group(1) != b['orig']:
                raise SystemExit(f'block {idx}: original text mismatch, refusing to inject')
            new_body = (b['speaker'] + '\n' + b['text']) if b['speaker'] else b['text']
            out.append(src[pos:m.start()])
            out.append('[[' + new_body + ']]')
            pos = m.end()
            replaced += 1
        idx += 1
    out.append(src[pos:])
    result = ''.join(out)
    qdone = 0
    for item in data.get('qstrings', []):
        if not item.get('ru') or item['ru'] == item['q']:
            continue
        needle = '"' + item['q'] + '"'
        if needle not in result:
            raise SystemExit(f'qstring not found: {item["q"]!r}')
        result = result.replace(needle, '"' + item['ru'] + '"')
        qdone += 1
    open(out_path, 'w', encoding='utf-8', newline='').write(result)
    print(f'{replaced}/{len(tr)} blocks, {qdone} qstrings injected -> {out_path}')
    if replaced != len(tr):
        raise SystemExit('some translated blocks were not found')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'extract' and len(sys.argv) == 4:
        extract(sys.argv[2], sys.argv[3])
    elif cmd == 'inject' and len(sys.argv) == 5:
        inject(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
        sys.exit(1)
