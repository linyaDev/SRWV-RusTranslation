#!/usr/bin/env python3
"""
Parser for SRW V mission-recap file (KPACK_P4_LN file 0).

Record: tag[8] (ASCII, null-padded) + next[4] (uint32 LE absolute offset of
the next record; 0 on the last one) + pad[4] + null-terminated UTF-8 text,
record padded with \x00 to 16-byte alignment. File ends with a 16-byte
all-zero terminator record.

extract: ru_ln_recap.py extract in.dat out.json
rebuild: ru_ln_recap.py rebuild translated.json out.dat
"""
import json
import struct
import sys


def align16(v):
    return (v + 15) & ~15


def extract(in_path, out_path):
    d = open(in_path, 'rb').read()
    recs = []
    pos = 0
    while pos < len(d):
        tag = d[pos:pos + 8].rstrip(b'\x00').decode('ascii')
        end = d.find(b'\x00', pos + 16)
        if end < 0:
            end = len(d)
        text = d[pos + 16:end].decode('utf-8')
        if tag or text:
            recs.append({'tag': tag, 'text': text})
        pos = min(pos + align16(16 + (end - (pos + 16)) + 1), len(d))
    json.dump({'records': recs}, open(out_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'{len(recs)} records -> {out_path}')


def rebuild(json_path, out_path):
    recs = json.load(open(json_path, encoding='utf-8-sig'))['records']
    out = bytearray()
    for n, r in enumerate(recs):
        text = r['text'].encode('utf-8') + b'\x00'
        size = align16(16 + len(text))
        nxt = 0 if n == len(recs) - 1 else len(out) + size
        out += r['tag'].encode('ascii').ljust(8, b'\x00')
        out += struct.pack('<II', nxt, 0)
        out += text
        out += b'\x00' * (size - 16 - len(text))
    out += b'\x00' * 16
    open(out_path, 'wb').write(out)
    print(f'{len(recs)} records -> {out_path} ({len(out)} bytes)')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'extract':
        extract(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == 'rebuild':
        rebuild(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
