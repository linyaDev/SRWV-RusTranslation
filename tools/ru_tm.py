#!/usr/bin/env python3
"""
Translation-memory tooling for SRW V stage dialogs.

make-todo <id> [<id>...]  — build dialogs_todo/<id>.json with blocks NOT
    covered by the TM (collected from every dialogs_ru/*.json) and all
    untranslated qstrings. Prints per-file stats.
merge <id> [<id>...]      — combine TM + dialogs_tr/<id>.json (agent output
    for the todo) into final dialogs_ru/<id>.json; validates coverage.
"""
import glob
import json
import os
import sys

BASE = r'D:\games\SUPER ROBOT WARS V\_extracted'
EN = os.path.join(BASE, 'dialogs_en')
RU = os.path.join(BASE, 'dialogs_ru')
TODO = os.path.join(BASE, 'dialogs_todo')
TR = os.path.join(BASE, 'dialogs_tr')


def load_tm():
    tm = {}
    qtm = {}
    for p in glob.glob(os.path.join(RU, '0*.json')):
        d = json.load(open(p, encoding='utf-8-sig'))
        for b in d['blocks']:
            tm[b['orig']] = (b['speaker'], b['text'])
        for q in d.get('qstrings', []):
            if q.get('ru'):
                qtm[q['q']] = q['ru']
    return tm, qtm


def make_todo(ids):
    tm, qtm = load_tm()
    os.makedirs(TODO, exist_ok=True)
    total_new = total_hit = 0
    for fid in ids:
        name = f'{fid:08d}'
        en = json.load(open(os.path.join(EN, name + '.json'), encoding='utf-8'))
        todo_b = [b for b in en['blocks'] if b['orig'] not in tm]
        todo_q = [q for q in en.get('qstrings', []) if q['q'] not in qtm]
        hit = len(en['blocks']) - len(todo_b)
        total_new += len(todo_b)
        total_hit += hit
        out = {'blocks': todo_b}
        if todo_q:
            out['qstrings'] = todo_q
        path = os.path.join(TODO, name + '.json')
        if todo_b or todo_q:
            json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print(f'{name}: todo {len(todo_b)} blocks (+{len(todo_q)} q), TM hits {hit}')
        else:
            if os.path.exists(path):
                os.remove(path)
            print(f'{name}: fully covered by TM ({hit})')
    print(f'TOTAL: new {total_new}, from TM {total_hit}')


def merge(ids):
    tm, qtm = load_tm()
    # agent output extends the TM
    for fid in ids:
        p = os.path.join(TR, f'{fid:08d}.json')
        if os.path.exists(p):
            d = json.load(open(p, encoding='utf-8-sig'))
            for b in d['blocks']:
                tm[b['orig']] = (b['speaker'], b['text'])
            for q in d.get('qstrings', []):
                if q.get('ru'):
                    qtm[q['q']] = q['ru']
    errs = []
    for fid in ids:
        name = f'{fid:08d}'
        en = json.load(open(os.path.join(EN, name + '.json'), encoding='utf-8'))
        blocks = []
        for b in en['blocks']:
            if b['orig'] not in tm:
                errs.append(f'{name}[{b["i"]}]: no translation')
                continue
            sp, tx = tm[b['orig']]
            blocks.append({'i': b['i'], 'speaker': sp, 'text': tx, 'orig': b['orig']})
        qs = []
        for q in en.get('qstrings', []):
            if q['q'] not in qtm:
                errs.append(f'{name} qstring untranslated: {q["q"]!r}')
                continue
            qs.append({'q': q['q'], 'ru': qtm[q['q']]})
        out = {'blocks': blocks}
        if qs:
            out['qstrings'] = qs
        json.dump(out, open(os.path.join(RU, name + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'{name}: merged {len(blocks)} blocks, {len(qs)} qstrings')
    if errs:
        print(f'{len(errs)} MISSING:')
        for e in errs[:30]:
            print('  ' + e)
        sys.exit(1)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    ids = [int(x) for x in sys.argv[2:]]
    if cmd == 'make-todo' and ids:
        make_todo(ids)
    elif cmd == 'merge' and ids:
        merge(ids)
    else:
        print(__doc__)
