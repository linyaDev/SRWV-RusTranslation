#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ru_ln_ability.py — названия спецспособностей и барьеров (KPACK_P4_LN, файл 3).

Весь файл — подряд идущие записи:
    u32 total; char text[total - 4]
где text — \0-терминированная UTF-8 строка, добитая нулями.
total ВКЛЮЧАЕТ сами 4 байта длины — этим формат отличается от таблицы
названий миссий (файл 4), где длина считает только строку.

I-Field, Psycho Field, Positron Reflector, VPS Armor, GN Sword Bits,
GN Holster Bits и т. д. — то, что игра показывает в списке способностей юнита.

Пересборка без правок даёт байт-в-байт оригинал.

  extract <in.dat> <out.json>
  rebuild <in.dat> <tr.json> <out.dat>
  verify  <in.dat>
"""
import json
import struct
import sys


def align4(v):
    return (v + 3) & ~3


def parse(data):
    items = []
    pos = 0
    while pos + 4 <= len(data):
        total = struct.unpack_from('<I', data, pos)[0]
        if total < 8 or pos + total > len(data):
            break
        raw = data[pos + 4:pos + total]
        z = raw.find(b'\x00')
        if z < 0:
            break
        items.append({'off': pos, 'size': total, 'en': raw[:z].decode('utf-8'), 'ru': ''})
        pos += total
    return items, pos


def assemble(data, items):
    out = bytearray()
    for it in items:
        body = (it.get('ru') or it['en']).encode('utf-8') + b'\x00'
        total = 4 + align4(len(body))
        out += struct.pack('<I', total)
        out += body.ljust(total - 4, b'\x00')
    return bytes(out) + data[sum(i['size'] for i in items):]


def extract(in_path, out_path):
    data = open(in_path, 'rb').read()
    items, end = parse(data)
    json.dump({'file_size': len(data), 'parsed_to': end, 'items': items},
              open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    uniq = len({i['en'] for i in items})
    print(f'{len(items)} записей ({uniq} уникальных, {end} из {len(data)} байт) -> {out_path}')


def rebuild(in_path, json_path, out_path):
    data = open(in_path, 'rb').read()
    d = json.load(open(json_path, encoding='utf-8-sig'))
    if d.get('file_size') != len(data):
        raise SystemExit('исходный файл не тот: размер не совпадает')
    out = assemble(data, d['items'])
    open(out_path, 'wb').write(out)
    n = sum(1 for i in d['items'] if i.get('ru'))
    same = 'identical' if out == data else f'{len(data)} -> {len(out)} байт'
    print(f'{n}/{len(d["items"])} переведено -> {out_path} ({same})')


def verify(in_path):
    data = open(in_path, 'rb').read()
    items, end = parse(data)
    ok = assemble(data, items) == data
    print(f'{len(items)} записей, разобрано {end}/{len(data)} байт, '
          f'round-trip {"OK" if ok else "BROKEN"}')
    return ok and end == len(data)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'extract' and len(sys.argv) == 4:
        extract(sys.argv[2], sys.argv[3])
    elif cmd == 'rebuild' and len(sys.argv) == 5:
        rebuild(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'verify' and len(sys.argv) == 3:
        sys.exit(0 if verify(sys.argv[2]) else 1)
    else:
        print(__doc__)
        sys.exit(1)
