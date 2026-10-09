#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ru_kpack_tbl.py — таблица «ключ → строка» из KPACK_P4_LN (файлы 1-4).

Формат (little-endian):
  +0x00 u32 count — число записей, далее записи подряд с 0x10.

  Запись:
    +0x00 key[8]   ASCII, добита нулями (id сцены: «001a», «303»…)
    +0x08 u32 idx  внутренний номер сценария
    +0x0c u32 ?    обычно 1
    +0x10 u32 ?    обычно 100
    +0x14 .. +0x2f нули
    +0x30 u32 gid  номер строки (у записей с одинаковым текстом совпадает)
    +0x34 u32 0
    +0x38 u32 type 0x30 у первого вхождения строки, 0x10 у повторов
    +0x3c u32 size длина поля строки = align4(len(utf8) + 1)
    +0x40 строка, дополнена нулями до size
    далее 8 нулевых байт — конец списка полей записи.

  Размер записи = 0x40 + size + 8.

Пересборка с неизменным JSON даёт байт-в-байт оригинал.

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
    count = struct.unpack_from('<I', data, 0)[0]
    recs = []
    pos = 16
    for _ in range(count):
        key = data[pos:pos + 8].rstrip(b'\x00').decode('ascii')
        head = data[pos + 8:pos + 0x30].hex()
        p = pos + 0x30
        meta = data[p:p + 12].hex()          # A, B, type
        p += 12
        texts = []
        while True:
            size = struct.unpack_from('<I', data, p)[0]
            if size == 0:
                p += 4
                break
            raw = data[p + 4:p + 4 + size]
            texts.append(raw.split(b'\x00', 1)[0].decode('utf-8'))
            p += 4 + size
        p = (p + 7) & ~7                      # запись выровнена по 8
        recs.append({'key': key, 'head_hex': head, 'meta_hex': meta, 'texts': texts})
        pos = p
    return count, recs, pos


def build(recs):
    out = bytearray(struct.pack('<I', len(recs)) + b'\x00' * 12)
    for r in recs:
        start = len(out)
        out += r['key'].encode('ascii').ljust(8, b'\x00')
        out += bytes.fromhex(r['head_hex'])
        out += bytes.fromhex(r['meta_hex'])
        for t in r['texts']:
            body = t.encode('utf-8') + b'\x00'
            size = align4(len(body))
            out += struct.pack('<I', size)
            out += body.ljust(size, b'\x00')
        out += b'\x00' * 4
        out += b'\x00' * ((8 - (len(out) % 8)) % 8)
    return bytes(out)


def extract(in_path, out_path):
    data = open(in_path, 'rb').read()
    count, recs, end = parse(data)
    tail = data[end:]
    json.dump({'records': recs, 'tail_hex': tail.hex()},
              open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{count} records ({end} of {len(data)} bytes) -> {out_path}')


def rebuild(in_path, json_path, out_path):
    src = open(in_path, 'rb').read()
    d = json.load(open(json_path, encoding='utf-8-sig'))
    out = build(d['records']) + bytes.fromhex(d.get('tail_hex', ''))
    open(out_path, 'wb').write(out)
    same = 'identical' if out == src else f'{len(src)} -> {len(out)} bytes'
    print(f'{len(d["records"])} records -> {out_path} ({same})')


def verify(in_path):
    data = open(in_path, 'rb').read()
    count, recs, end = parse(data)
    out = build(recs) + data[end:]
    ok = out == data
    print(f'{in_path}: {count} records, round-trip {"OK" if ok else "BROKEN"}')
    if not ok:
        for i, (a, b) in enumerate(zip(data, out)):
            if a != b:
                print(f'  первое расхождение на байте {i}: {a:02x} != {b:02x}')
                break
        print(f'  размеры: {len(data)} vs {len(out)}')
    return ok


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'extract' and len(sys.argv) == 4:
        extract(sys.argv[2], sys.argv[3])
    elif cmd == 'rebuild' and len(sys.argv) == 5:
        rebuild(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'verify' and len(sys.argv) >= 3:
        ok = all(verify(p) for p in sys.argv[2:])
        sys.exit(0 if ok else 1)
    else:
        print(__doc__)
        sys.exit(1)
