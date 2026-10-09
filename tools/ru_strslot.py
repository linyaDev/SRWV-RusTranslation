#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ru_strslot.py — перевод строк в контейнерах вида «u32 длина + строка».

Структуру записей разбирать не требуется: находим в файле все слоты
    u32 size; char text[size]   (text — UTF-8, \0-терминирован, хвост нулевой)
и заменяем только их. Всё остальное копируется байт в байт.

Новый размер слота считается по тому же правилу, что и в оригинале:
    new_size = align4(len(utf8) + 1)
Записи в файле выровнены по 4 байта (запись может начинаться на 284),
поэтому дополнительного выравнивания не требуется.

Так устроены таблицы KPACK_P4_LN (названия миссий, описания сценариев,
названия интермиссий, названия барьеров).

  extract <in.dat> <out.json>
  rebuild <in.dat> <tr.json> <out.dat>
  verify  <in.dat> [...]            — пересборка без правок = оригинал
"""
import json
import re
import struct
import sys

MIN_SIZE, MAX_SIZE = 4, 1024
TEXT_OK = re.compile(r'^[^\x00-\x08\x0b\x0c\x0e-\x1f]+$')


def align4(v):
    return (v + 3) & ~3


def find_slots(data):
    """Вернуть список (offset, size, text), не пересекающихся, слева направо."""
    slots = []
    pos = 0
    n = len(data)
    while pos + 8 <= n:
        size = struct.unpack_from('<I', data, pos)[0]
        if MIN_SIZE <= size <= MAX_SIZE and size % 4 == 0 and pos + 4 + size <= n:
            raw = data[pos + 4:pos + 4 + size]
            z = raw.find(b'\x00')
            if z > 0 and raw[z:] == b'\x00' * (size - z) and align4(z + 1) == size:
                try:
                    text = raw[:z].decode('utf-8')
                except UnicodeDecodeError:
                    text = None
                if text and TEXT_OK.match(text):
                    slots.append((pos, size, text))
                    pos += 4 + size
                    continue
        pos += 4
    return slots


def extract(in_path, out_path):
    data = open(in_path, 'rb').read()
    slots = find_slots(data)
    items = [{'off': o, 'size': s, 'en': t, 'ru': ''} for o, s, t in slots]
    json.dump({'file_size': len(data), 'items': items},
              open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(items)} строк ({sum(len(i["en"]) for i in items)} символов) -> {out_path}')


def rebuild(in_path, json_path, out_path):
    data = open(in_path, 'rb').read()
    d = json.load(open(json_path, encoding='utf-8-sig'))
    if d.get('file_size') != len(data):
        raise SystemExit('исходный файл не тот: размер не совпадает')
    out = bytearray()
    pos = 0
    changed = grown = 0
    for it in d['items']:
        o, size = it['off'], it['size']
        if data[o:o + 4] != struct.pack('<I', size):
            raise SystemExit(f'слот {o}: размер в файле не совпадает с JSON')
        out += data[pos:o]
        text = it.get('ru') or it['en']
        body = text.encode('utf-8') + b'\x00'
        new_size = align4(len(body))
        out += struct.pack('<I', new_size)
        out += body.ljust(new_size, b'\x00')
        if text != it['en']:
            changed += 1
        if new_size != size:
            grown += 1
        pos = o + 4 + size
    out += data[pos:]
    open(out_path, 'wb').write(bytes(out))
    same = 'identical' if bytes(out) == data else f'{len(data)} -> {len(out)} байт'
    print(f'{changed} строк переведено, {grown} слотов расширено -> {out_path} ({same})')


def verify(in_path):
    data = open(in_path, 'rb').read()
    slots = find_slots(data)
    out = bytearray()
    pos = 0
    for o, size, text in slots:
        out += data[pos:o]
        body = text.encode('utf-8') + b'\x00'
        out += struct.pack('<I', size) + body.ljust(size, b'\x00')
        pos = o + 4 + size
    out += data[pos:]
    ok = bytes(out) == data
    print(f'{in_path.split(chr(92))[-1]}: слотов {len(slots)}, '
          f'round-trip {"OK" if ok else "BROKEN"}')
    return ok


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'extract' and len(sys.argv) == 4:
        extract(sys.argv[2], sys.argv[3])
    elif cmd == 'rebuild' and len(sys.argv) == 5:
        rebuild(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'verify' and len(sys.argv) >= 3:
        sys.exit(0 if all([verify(p) for p in sys.argv[2:]]) else 1)
    else:
        print(__doc__)
        sys.exit(1)
