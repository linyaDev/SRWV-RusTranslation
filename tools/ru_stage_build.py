#!/usr/bin/env python3
"""
Validate translated dialog JSONs, inject into stage Lua files, encrypt and
patch STGEST_EN.CPK in one pass.

Usage: ru_stage_build.py <game_dir> <out_cpk> <id> [<id> ...]

For each id NNNNNNNN: needs
  _extracted/STAGE_EN_dec/<id>.dat   (decrypted original Lua)
  _extracted/dialogs_en/<id>.json    (extracted EN blocks)
  _extracted/dialogs_ru/<id>.json    (translated blocks)
Source CPK: Data/STAGE/STGEST_EN.CPK(.bak if present).
"""
import json
import os
import re
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from ru_lua_dialog import inject  # noqa: E402

PLACEHOLDER = re.compile(r'\$kwb|\$kwe|\$n|\$l|\$c|\$r|\$F')


def validate(en_path, ru_path):
    en = {b['i']: b for b in json.load(open(en_path, encoding='utf-8'))['blocks']}
    ru = json.load(open(ru_path, encoding='utf-8-sig'))['blocks']
    errs = []
    if len(ru) != len(en):
        errs.append(f'block count {len(ru)} != {len(en)}')
    for b in ru:
        i = b['i']
        if i not in en:
            errs.append(f'[{i}] unknown block index')
            continue
        o = en[i]
        if b['orig'] != o['orig']:
            errs.append(f'[{i}] orig modified')
        if sorted(PLACEHOLDER.findall(o['text'])) != sorted(PLACEHOLDER.findall(b['text'])):
            errs.append(f'[{i}] placeholders differ')
        if '「' in o['text'] and ('「' not in b['text'] or '」' not in b['text']):
            errs.append(f'[{i}] quote brackets lost')
        olines = o['text'].split('\n')
        maxlen = max(len(l) for l in olines)
        for ln in b['text'].split('\n'):
            if len(ln) > maxlen + 4:
                errs.append(f'[{i}] line too long ({len(ln)} > {maxlen}+4): {ln[:40]}...')
    return errs


def main():
    game_dir, out_cpk = sys.argv[1], sys.argv[2]
    ids = [int(x) for x in sys.argv[3:]]
    ex = os.path.join(game_dir, '_extracted')
    work = os.path.join(game_dir, '_build', 'stage_work')
    os.makedirs(work, exist_ok=True)

    all_errs = []
    repl_args = []
    for fid in ids:
        name = f'{fid:08d}'
        en_j = os.path.join(ex, 'dialogs_en', name + '.json')
        ru_j = os.path.join(ex, 'dialogs_ru', name + '.json')
        lua = os.path.join(ex, 'STAGE_EN_dec', name + '.dat')
        errs = validate(en_j, ru_j)
        if errs:
            all_errs += [f'{name}: {e}' for e in errs]
            continue
        out_lua = os.path.join(work, name + '_ru.dat')
        inject(lua, ru_j, out_lua)
        enc = os.path.join(work, name + '_ru_enc.dat')
        subprocess.run([sys.executable, os.path.join(TOOLS, 'srwv_encrypt.py'),
                        out_lua, enc], check=True, capture_output=True)
        repl_args.append(f'{fid}={enc}')

    if all_errs:
        print(f'{len(all_errs)} VALIDATION ERRORS:')
        for e in all_errs[:40]:
            print('  ' + e)
        sys.exit(1)

    src_cpk = os.path.join(game_dir, 'Data', 'STAGE', 'STGEST_EN.CPK')
    if os.path.exists(src_cpk + '.bak'):
        src_cpk += '.bak'
    cmd = [sys.executable, os.path.join(TOOLS, 'ru_cpk_patch.py'), src_cpk, out_cpk] + repl_args
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout[-2000:])
    if r.returncode:
        print(r.stderr[-2000:])
        sys.exit(1)
    print(f'DONE: {out_cpk} ({len(repl_args)} files replaced)')


if __name__ == '__main__':
    main()
