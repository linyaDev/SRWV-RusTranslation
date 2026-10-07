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


def iter_blocks(src: str):
    """Yield (match, is_comment) for every [[...]] long string."""
    for m in BLOCK.finditer(src):
        pre = src[max(0, m.start() - 2):m.start()]
        yield m, pre == '--'


def extract(in_path, out_path):
    src = open(in_path, encoding='utf-8').read()
    blocks = []
    idx = 0
    for m, is_comment in iter_blocks(src):
        if is_comment:
            idx += 1
            continue
        body = m.group(1)
        if '「' in body:
            first, _, rest = body.partition('\n')
            blocks.append({'i': idx, 'speaker': first, 'text': rest, 'orig': body})
        idx += 1
    json.dump({'blocks': blocks}, open(out_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'{len(blocks)} blocks -> {out_path}')


def inject(in_path, json_path, out_path):
    src = open(in_path, encoding='utf-8').read()
    tr = {b['i']: b for b in json.load(open(json_path, encoding='utf-8'))['blocks']}
    out = []
    pos = 0
    idx = 0
    replaced = 0
    for m, is_comment in iter_blocks(src):
        if not is_comment and idx in tr:
            b = tr[idx]
            if m.group(1) != b['orig']:
                raise SystemExit(f'block {idx}: original text mismatch, refusing to inject')
            new_body = b['speaker'] + '\n' + b['text']
            out.append(src[pos:m.start()])
            out.append('[[' + new_body + ']]')
            pos = m.end()
            replaced += 1
        idx += 1
    out.append(src[pos:])
    open(out_path, 'w', encoding='utf-8', newline='').write(''.join(out))
    print(f'{replaced}/{len(tr)} blocks injected -> {out_path}')
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
