# -*- coding: utf-8 -*-
"""
Batch pipeline for CMN00 battle subtitles.

make-todo N  — выбрать N самых частотных ещё не переведённых уникальных строк
               (+ все строки малых секций в первый заход) → cmn_todo.json
merge        — влить cmn_tr.json (перевод todo) в память переводов cmn_tm.json
build OUT    — собрать переведённый 00000001.dat: каждая строка заменяется по
               TM, непереведённые остаются английскими
stats        — прогресс
"""
import collections
import json
import os
import sys

E = r'D:\games\SUPER ROBOT WARS V\_extracted'
SRC = os.path.join(E, 'cmn_subs_EN.json')
TM = os.path.join(E, 'cmn_tm.json')
TODO = os.path.join(E, 'cmn_todo.json')
TR = os.path.join(E, 'cmn_tr.json')


def load_src():
    return json.load(open(SRC, encoding='utf-8'))


def load_tm():
    if os.path.exists(TM):
        return json.load(open(TM, encoding='utf-8'))
    return {}


def make_todo_range(start, end, n):
    src = load_src()
    tm = load_tm()
    bl = next(s for s in src['sections'] if s['name'] == 'battle_lines')['strings']
    todo = []
    seen = set()
    for s in bl[start:end + 1]:
        if len(todo) >= n:
            break
        if not s.strip() or s in ('-', '...', '…') or s in tm or s in seen:
            continue
        seen.add(s)
        todo.append(s)
    json.dump({'items': [{'en': s, 'ru': ''} for s in todo]},
              open(TODO, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'todo: {len(todo)} строк из диапазона [{start}:{end}] -> {TODO}')


def make_todo(n):
    src = load_src()
    tm = load_tm()
    freq = collections.Counter()
    small = []
    for sec in src['sections']:
        for s in sec['strings']:
            if not s.strip() or s in ('-', '...', '…'):
                continue
            if sec['name'] == 'battle_lines':
                freq[s] += 1
            elif s not in tm:
                small.append(s)
    todo = [s for s in small]
    for s, _ in freq.most_common():
        if len(todo) >= n:
            break
        if s not in tm:
            todo.append(s)
    json.dump({'items': [{'en': s, 'ru': ''} for s in todo]},
              open(TODO, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'todo: {len(todo)} строк -> {TODO}')


def merge():
    tm = load_tm()
    tr = json.load(open(TR, encoding='utf-8-sig'))
    added = bad = 0
    for it in tr['items']:
        en, ru = it['en'], it.get('ru', '')
        if not ru:
            bad += 1
            continue
        if en.count('\\n') != ru.count('\\n'):
            print('WARN \\n mismatch:', repr(en[:50]))
        if len(ru.encode('utf-8')) > max(147, len(en.encode('utf-8')) * 2 + 20):
            print('WARN too long:', repr(ru[:60]))
        tm[en] = ru
        added += 1
    json.dump(tm, open(TM, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'TM: +{added} (пустых {bad}), всего {len(tm)}')


def build(out_json):
    src = load_src()
    tm = load_tm()
    hit = miss = 0
    for sec in src['sections']:
        new = []
        for s in sec['strings']:
            if s in tm:
                new.append(tm[s])
                hit += 1
            else:
                new.append(s)
                miss += 1
        sec['strings'] = new
    json.dump(src, open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'build: переведено {hit}, осталось EN {miss} -> {out_json}')


def stats():
    src = load_src()
    tm = load_tm()
    uniq = set()
    total = 0
    for sec in src['sections']:
        for s in sec['strings']:
            if s.strip() and s not in ('-', '...', '…'):
                uniq.add(s)
                total += 1
    done = sum(1 for s in uniq if s in tm)
    inst = sum(1 for sec in src['sections'] for s in sec['strings'] if s in tm)
    print(f'уникальных: {len(uniq)}, в TM: {done} ({done*100//max(1,len(uniq))}%), '
          f'покрытие вхождений: {inst}/{total}')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'make-todo':
        make_todo(int(sys.argv[2]))
    elif cmd == 'make-todo-range':
        make_todo_range(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    elif cmd == 'merge':
        merge()
    elif cmd == 'build':
        build(sys.argv[2])
    elif cmd == 'stats':
        stats()
    else:
        print(__doc__)
