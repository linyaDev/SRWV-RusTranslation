# -*- coding: utf-8 -*-
"""Re-wrap overlong translated lines in dialogs_tr within original block limits.

For blocks where some line exceeds (max original line length + 4):
strip 「」/（） brackets and U+3000 indents, join words, greedily re-wrap to
the original max width, restore brackets/indents. Keeps line count <= original.
Prints blocks it cannot fix (text too long to fit).
"""
import json
import os
import re

TODO = r'D:\games\SUPER ROBOT WARS V\_extracted\dialogs_todo'
TR = r'D:\games\SUPER ROBOT WARS V\_extracted\dialogs_tr'
IND = '\u3000'


def rewrap(tr_text, orig_text):
    olines = orig_text.split('\n')
    maxlen = max(len(ln) for ln in olines)
    open_br = close_br = ''
    body = tr_text
    for o, c in (('「', '」'), ('（', '）')):
        if body.startswith(o):
            open_br, close_br = o, c
            body = body[len(o):]
            if body.endswith(c):
                body = body[:-len(c)]
            break
    words = ' '.join(ln.strip(IND).strip() for ln in body.split('\n')).split()
    for width in (maxlen, maxlen + 2, maxlen + 4):
        lines = []
        cur = open_br
        base = len(open_br)
        for w in words:
            cand = cur + (' ' if len(cur) > base and not cur.endswith(IND) else '') + w
            if len(cand) <= width or len(cur) <= base:
                cur = cand
            else:
                lines.append(cur)
                cur = IND + w
                base = 1
        cur += close_br
        lines.append(cur)
        if len(lines) <= len(olines) and all(len(ln) <= width for ln in lines):
            return '\n'.join(lines)
    return None


def main():
    total_fixed = total_fail = 0
    for name in sorted(os.listdir(TR)):
        todo = {b['i']: b for b in json.load(open(os.path.join(TODO, name), encoding='utf-8'))['blocks']}
        path = os.path.join(TR, name)
        tr = json.load(open(path, encoding='utf-8-sig'))
        changed = False
        for b in tr['blocks']:
            o = todo.get(b['i'])
            if not o:
                continue
            maxlen = max(len(ln) for ln in o['text'].split('\n'))
            if all(len(ln) <= maxlen + 4 for ln in b['text'].split('\n')):
                continue
            if '-' in b['text'] and IND * 2 in b['text']:
                print(f'{name}[{b["i"]}]: location card, skip')
                continue
            new = rewrap(b['text'], o['text'])
            if new:
                b['text'] = new
                changed = True
                total_fixed += 1
            else:
                total_fail += 1
                print(f'{name}[{b["i"]}]: cannot fit, needs manual shortening:')
                print('   ' + b['text'].replace('\n', ' / '))
                print(f'   limit {maxlen}+4, lines {len(o["text"].splitlines())}')
        if changed:
            json.dump(tr, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'fixed: {total_fixed}, manual: {total_fail}')


if __name__ == '__main__':
    main()
