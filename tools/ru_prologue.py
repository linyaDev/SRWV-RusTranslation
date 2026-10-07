#!/usr/bin/env python3
"""
ru_prologue.py — extract/rebuild tool for Super Robot Wars V (PC) prologue
narration files (AIDDATA/*/Prologue.cpk -> decrypted *.dat).

File format (see PROLOGUE_FORMAT.md for details):

  Header, 24 bytes:
    0x00 u16  record_count
    0x02 u8   text_field_size F  (== max string length + 3, see below)
    0x03 u8   unknown (layout/style; 9/2/1/0; identical in JP and EN)
    0x04-0x09 six bytes, layout params (differ JP vs EN, text-independent)
    0x0A u16  timing param (0x78 / 0xF0)
    0x0C u32  unknown (0/1/2/4)
    0x10 f32  scale/spacing (1.0723; credits file: 1.9268)
    0x14-0x17 extra params (zero except credits file: 720, 500)

  Then record_count records, each (F + 30) bytes:
    +0   text[F]  NUL-terminated UTF-8 string; bytes after the NUL are
                  stale garbage from the packing tool and are ignored
                  by the game. Empty string = blank tick (pause).
    +F   meta[30] timing/effect commands; completely text-independent
                  (byte-identical between JP and EN versions).

  F is per-file and always equals max(len(utf8_string)) + 3
  (string + NUL + 2 spare bytes). The JP and EN releases of the same
  file use different F, so the game reads F from the header and strings
  MAY change length: rebuild recomputes F (never shrinking it) and
  resizes every record. F is a single byte => hard cap:
  max string length = 252 bytes of UTF-8.

Commands:
  extract <in.dat> <out.json>              dump strings for translation
  rebuild <in.dat> <translated.json> <out.dat>   repack with new strings
  test    <dir> [...dirs]                  round-trip check: for every
                                           *.dat, extract+rebuild with
                                           unchanged text must be
                                           byte-identical (sha256)

JSON format:
  {
    "source_file": "00000001.dat",
    "record_count": 47,
    "text_field_size": 63,
    "max_text_bytes": 252,          # hard limit per line (UTF-8 bytes)
    "lines": [                      # only non-empty records
      {"idx": 3, "text": "The Earth Federation, ..."},
      ...
    ]
  }
  Translate the "text" values in place. "idx" is the record index and
  must not be changed. Records absent from "lines" stay empty.
"""

import sys
import os
import json
import glob
import hashlib

HEADER_SIZE = 24
META_SIZE = 30
SPARE = 3          # field size = max string length + NUL + 2 spare
MAX_FIELD = 255    # field size is a u8
MAX_TEXT = MAX_FIELD - SPARE  # 252 bytes of UTF-8 per line


class FormatError(Exception):
    pass


def parse(data, name='<data>'):
    """Parse a decrypted prologue .dat. Returns dict with header bytes and
    per-record (string_bytes, field_bytes, meta_bytes)."""
    if len(data) < HEADER_SIZE:
        raise FormatError(f'{name}: file too small ({len(data)} bytes)')
    count = int.from_bytes(data[0:2], 'little')
    fsize = data[2]
    rec_size = fsize + META_SIZE
    expected = HEADER_SIZE + count * rec_size
    if expected != len(data):
        raise FormatError(
            f'{name}: size mismatch: header says {count} records of '
            f'{rec_size} bytes -> {expected}, actual {len(data)}')
    records = []
    for i in range(count):
        base = HEADER_SIZE + i * rec_size
        field = data[base:base + fsize]
        z = field.find(b'\x00')
        if z < 0:
            raise FormatError(f'{name}: record {i}: string not NUL-terminated '
                              f'inside its {fsize}-byte text field')
        meta = data[base + fsize:base + rec_size]
        records.append({'str': field[:z], 'field': field, 'meta': meta})
    return {
        'header': bytearray(data[:HEADER_SIZE]),
        'count': count,
        'fsize': fsize,
        'records': records,
    }


def cmd_extract(in_dat, out_json):
    data = open(in_dat, 'rb').read()
    p = parse(data, os.path.basename(in_dat))
    lines = []
    for i, r in enumerate(p['records']):
        if r['str']:
            lines.append({'idx': i, 'text': r['str'].decode('utf-8')})
    doc = {
        'source_file': os.path.basename(in_dat),
        'record_count': p['count'],
        'text_field_size': p['fsize'],
        'max_text_bytes': MAX_TEXT,
        'lines': lines,
    }
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f'{in_dat}: {p["count"]} records, {len(lines)} text lines -> {out_json}')


def rebuild_bytes(data, doc, name='<data>'):
    """Core of rebuild: original file bytes + translation doc -> new bytes."""
    p = parse(data, name)
    if doc.get('record_count', p['count']) != p['count']:
        raise FormatError(f'{name}: record_count in JSON '
                          f'({doc.get("record_count")}) != file ({p["count"]})')

    # new string bytes per record (default: keep original)
    new_strs = [r['str'] for r in p['records']]
    for ln in doc['lines']:
        i = ln['idx']
        if not 0 <= i < p['count']:
            raise FormatError(f'{name}: line idx {i} out of range 0..{p["count"]-1}')
        s = ln['text'].encode('utf-8')
        if b'\x00' in s:
            raise FormatError(f'{name}: line idx {i}: text contains NUL')
        if len(s) > MAX_TEXT:
            raise FormatError(
                f'{name}: line idx {i}: text is {len(s)} UTF-8 bytes, '
                f'hard limit is {MAX_TEXT} (text field size is a single byte '
                f'in the header). Shorten the line:\n  {ln["text"]!r}')
        new_strs[i] = s

    # field size: original rule is max(strlen)+3; never shrink below the
    # original so an unchanged file stays byte-identical
    need = max((len(s) for s in new_strs), default=0) + SPARE
    new_fsize = max(p['fsize'], need)
    if new_fsize > MAX_FIELD:
        raise FormatError(f'{name}: required text field size {new_fsize} '
                          f'exceeds u8 limit {MAX_FIELD}')

    header = bytearray(p['header'])
    header[2] = new_fsize
    out = bytearray(header)
    for i, r in enumerate(p['records']):
        field = bytearray(r['field']) + b'\x00' * (new_fsize - p['fsize'])
        s = new_strs[i]
        field[0:len(s) + 1] = s + b'\x00'
        # bytes after the NUL keep whatever the original field had there
        # (the game ignores them); grown area is zero-filled
        out += field
        out += r['meta']
    return bytes(out)


def cmd_rebuild(in_dat, in_json, out_dat):
    data = open(in_dat, 'rb').read()
    with open(in_json, encoding='utf-8') as f:
        doc = json.load(f)
    out = rebuild_bytes(data, doc, os.path.basename(in_dat))
    with open(out_dat, 'wb') as f:
        f.write(out)
    identical = hashlib.sha256(out).digest() == hashlib.sha256(data).digest()
    note = 'byte-identical to input' if identical else \
        f'field size {data[2]} -> {out[2]}, size {len(data)} -> {len(out)}'
    print(f'{out_dat}: {len(out)} bytes ({note})')


def cmd_test(dirs):
    total = ok = 0
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, '*.dat'))):
            total += 1
            data = open(path, 'rb').read()
            name = os.path.basename(path)
            try:
                p = parse(data, name)
                doc = {
                    'record_count': p['count'],
                    'lines': [{'idx': i, 'text': r['str'].decode('utf-8')}
                              for i, r in enumerate(p['records']) if r['str']],
                }
                out = rebuild_bytes(data, doc, name)
            except (FormatError, UnicodeDecodeError) as e:
                print(f'FAIL {path}: {e}')
                continue
            h1 = hashlib.sha256(data).hexdigest()
            h2 = hashlib.sha256(out).hexdigest()
            if h1 == h2:
                ok += 1
                print(f'OK   {path}  sha256={h1[:16]}...')
            else:
                print(f'FAIL {path}: round-trip differs '
                      f'(orig {h1[:16]}..., rebuilt {h2[:16]}...)')
    print(f'\n{ok}/{total} files round-trip byte-identical')
    return 0 if ok == total and total > 0 else 1


def main(argv):
    if len(argv) >= 4 and argv[1] == 'extract':
        cmd_extract(argv[2], argv[3])
    elif len(argv) >= 5 and argv[1] == 'rebuild':
        cmd_rebuild(argv[2], argv[3], argv[4])
    elif len(argv) >= 3 and argv[1] == 'test':
        return cmd_test(argv[2:])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
