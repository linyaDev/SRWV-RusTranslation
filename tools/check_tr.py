# -*- coding: utf-8 -*-
"""Validate dialogs_tr against dialogs_todo: coverage, orig, placeholders, line length."""
import json
import os
import re

TODO = r'D:\games\SUPER ROBOT WARS V\_extracted\dialogs_todo'
TR = r'D:\games\SUPER ROBOT WARS V\_extracted\dialogs_tr'
PLACE = re.compile(r'\$kwb|\$kwe|\$n|\$l|\$c|\$r|\$F')

ok_files, errs = [], []
for name in sorted(os.listdir(TR)):
    todo = json.load(open(os.path.join(TODO, name), encoding='utf-8'))
    tr = json.load(open(os.path.join(TR, name), encoding='utf-8-sig'))
    t_by_i = {b['i']: b for b in tr['blocks']}
    ferr = []
    for b in todo['blocks']:
        tb = t_by_i.get(b['i'])
        if not tb:
            ferr.append('missing block %d' % b['i'])
            continue
        if tb['orig'] != b['orig']:
            ferr.append('orig diff %d' % b['i'])
        if sorted(PLACE.findall(b['text'])) != sorted(PLACE.findall(tb['text'])):
            ferr.append('placeholder %d' % b['i'])
        maxlen = max(len(ln) for ln in b['text'].split('\n'))
        for ln in tb['text'].split('\n'):
            if len(ln) > maxlen + 4:
                ferr.append('long line %d (%d>%d)' % (b['i'], len(ln), maxlen))
                break
        ru = any('а' <= c.lower() <= 'я' for c in tb['text']) or not re.search(r'[A-Za-z]{3}', b['text'])
        if not ru:
            ferr.append('not translated %d' % b['i'])
    tq_by_q = {q['q']: q for q in tr.get('qstrings', [])}
    for q in todo.get('qstrings', []):
        tq = tq_by_q.get(q['q'])
        if not tq or not tq.get('ru'):
            ferr.append('qstring empty: %r' % q['q'][:40])
    if ferr:
        errs.append((name[:8], len(ferr), ferr[:5]))
    else:
        ok_files.append(name[:8])

print('OK files:', len(ok_files), ok_files)
for fid, n, sample in errs:
    print('ISSUES', fid, 'count', n, sample)
