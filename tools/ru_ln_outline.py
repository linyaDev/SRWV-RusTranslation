#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ru_ln_outline.py — описания бонусных сценариев (KPACK_P4_LN, файл 2).

Формат (little-endian):
  +0x00 u32 count      число записей (51)
  +0x04 u32 rec_size   размер записи (136)
  +0x08 u32 rec_start  начало массива записей (16)
  +0x0c u32 pool       начало пула строк
  записи: key[8] «301»… + поля; на +0x70 — смещение строки от начала пула
  пул: \0-терминированные UTF-8 строки подряд (перевод строки — \n)

Пересборка с неизменным JSON даёт байт-в-байт оригинал.

  extract <in.dat> <out.json>
  rebuild <in.dat> <tr.json> <out.dat>
  verify  <in.dat>
"""
import json
import struct
import sys

PTR = 0x70


def read_header(data):
    return struct.unpack_from('<4I', data, 0)


def extract(in_path, out_path):
    data = open(in_path, 'rb').read()
    count, rsize, start, pool = read_header(data)
    items = []
    for k in range(count):
        s = start + k * rsize
        key = data[s:s + 8].rstrip(b'\x00').decode('ascii')
        off = struct.unpack_from('<I', data, s + PTR)[0]
        end = data.find(b'\x00', pool + off)
        text = data[pool + off:end].decode('utf-8')
        items.append({'key': key, 'en': text, 'ru': ''})
    json.dump({'items': items}, open(out_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'{count} описаний ({sum(len(i["en"]) for i in items)} символов) -> {out_path}')


def assemble(data, texts):
    """Исходный пул сохраняется как есть; изменённые строки дописываются в конец.

    Так пересборка без правок даёт байт-в-байт оригинал — выравнивающие
    пропуски между строками пула не теряются.
    """
    count, rsize, start, pool = read_header(data)
    out = bytearray(data)
    added = {}
    for k in range(count):
        s = start + k * rsize
        off = struct.unpack_from('<I', data, s + PTR)[0]
        end = data.find(b'\x00', pool + off)
        if texts[k] == data[pool + off:end].decode('utf-8'):
            continue
        t = texts[k]
        if t not in added:
            added[t] = len(out) - pool
            out += t.encode('utf-8') + b'\x00'
        struct.pack_into('<I', out, s + PTR, added[t])
    while len(out) % 16:
        out += b'\x00'
    return bytes(out)


def rebuild(in_path, json_path, out_path):
    data = open(in_path, 'rb').read()
    items = json.load(open(json_path, encoding='utf-8-sig'))['items']
    count = read_header(data)[0]
    if len(items) != count:
        raise SystemExit(f'ожидалось {count} записей, в JSON {len(items)}')
    texts = [(i.get('ru') or i['en']) for i in items]
    out = assemble(data, texts)
    open(out_path, 'wb').write(out)
    n = sum(1 for i in items if i.get('ru'))
    same = 'identical' if out == data else f'{len(data)} -> {len(out)} байт'
    print(f'{n}/{count} переведено -> {out_path} ({same})')


def verify(in_path):
    data = open(in_path, 'rb').read()
    count, rsize, start, pool = read_header(data)
    texts = []
    for k in range(count):
        off = struct.unpack_from('<I', data, start + k * rsize + PTR)[0]
        end = data.find(b'\x00', pool + off)
        texts.append(data[pool + off:end].decode('utf-8'))
    out = assemble(data, texts)
    ok = out == data
    print(f'round-trip: {"OK" if ok else "BROKEN"} ({len(data)} vs {len(out)} байт)')
    return ok


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
