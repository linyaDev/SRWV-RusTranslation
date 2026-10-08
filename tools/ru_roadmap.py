# -*- coding: utf-8 -*-
"""Generate per-mission progress tree and update the repo ROADMAP.md section
between <!-- missions:start --> and <!-- missions:end --> markers."""
import glob
import json
import os
import re

G = r'D:\games\SUPER ROBOT WARS V'
ROADMAP = r'D:\Mods\SRV5Rus\ROADMAP.md'

smap = json.load(open(G + r'\_build\stage_map.json'))
en_dir = G + r'\_extracted\dialogs_en'
ru_dir = G + r'\_extracted\dialogs_ru'

# привязка файлов к стадиям: имя stageXXX[preset].lua действует до следующего
stage_files = {}
cur = None
order = []
for r in smap:
    name = r['lua'] or ''
    m = re.match(r'stage(\w+?)(preset)?\.lua', name)
    if m:
        if m.group(1) != cur:
            cur = m.group(1)
            if cur not in stage_files:
                stage_files[cur] = []
                order.append(cur)
    if cur is not None:
        stage_files[cur].append(r['id'])

def file_info(fid):
    p = os.path.join(en_dir, '%08d.json' % fid)
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding='utf-8'))
    blocks = len(d['blocks'])
    qs = len(d.get('qstrings', []))
    done = os.path.exists(os.path.join(ru_dir, '%08d.json' % fid))
    return blocks, qs, done

lines = []
total_done_files = total_files = 0
for st in order:
    infos = [(fid, file_info(fid)) for fid in stage_files[st]]
    infos = [(fid, i) for fid, i in infos if i]
    if not infos:
        continue
    blocks = sum(i[0] for _, i in infos)
    qs = sum(i[1] for _, i in infos)
    ndone = sum(1 for _, i in infos if i[2])
    total_files += len(infos)
    total_done_files += ndone
    if ndone == len(infos):
        mark = '✅'
    elif ndone:
        mark = '🔄'
    else:
        mark = '⬜'
    extra = ''
    if 0 < ndone < len(infos):
        missing = [str(fid) for fid, i in infos if not i[2]]
        extra = f' — осталось: {", ".join(missing)}'
    qtxt = f' +{qs}усл' if qs else ''
    lines.append(f'{mark} {st:<5} {len(infos)} файл(а), {blocks} реплик{qtxt}'
                 f' [{ndone}/{len(infos)}]{extra}')

tree = ['```text', f'Миссии: файлов готово {total_done_files}/{total_files}', '']
tree += lines + ['```']
block = '\n'.join(tree)

md = open(ROADMAP, encoding='utf-8').read()
START, END = '<!-- missions:start -->', '<!-- missions:end -->'
if START in md:
    md = re.sub(re.escape(START) + '.*?' + re.escape(END),
                START + '\n' + block + '\n' + END, md, flags=re.S)
else:
    md += f'\n## Сюжет по миссиям\n\n{START}\n{block}\n{END}\n'
open(ROADMAP, 'w', encoding='utf-8').write(md)
print(f'updated: {total_done_files}/{total_files} files, {len(lines)} missions')
