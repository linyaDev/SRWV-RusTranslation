#!/usr/bin/env python3
"""
ru_zkan.py -- parser / rebuilder for the ZKAN encyclopedia record format
used by Super Robot Wars V (Steam).

The records live inside CommonData/MtData/<LANG>/MtZkn_Pt.cpk (characters),
MtZkn_Rt.cpk (robots) and MtZkn_Nm.cpk (terms / story digests).  Each CPK
entry is one record, Blowfish-encrypted (see srwv_decrypt.py / srwv_encrypt.py).
Once Blowfish is removed the record is still byte-obfuscated: see OBFUSCATION
below.  This tool handles the obfuscation internally, so the files it reads and
writes are exactly what srwv_decrypt.py produces / srwv_encrypt.py consumes.

OBFUSCATION
    plain[i] = raw[i] ^ 0x5E,  except raw[i] in (0x00, 0x5E) which pass through
    unchanged.  The mapping is an involution, so the same function encodes and
    decodes.  Consequence: the byte 0x5E ('^') and 0x00 are literal in both
    views; '^' therefore never appears in game text (and must not be used in
    translations -- see ZKAN_FORMAT.md).

LAYOUT (after de-obfuscation)
    0x00  char[4]  'ZKAN'
    0x04  char[4]  record type: 'CHAR' | 'ROBO' | 'PDNM'
    0x08  u32      version (always 0x00000100)
    0x0C  u32      always 12
    0x10  ...      chunk stream

    chunk = char[4] tag + u32 size (LE) + payload[size]
    'DSIZ' and 'DATA' are *containers*: their size counts every byte that
    follows the chunk header, i.e. DSIZ.size == filesize-24 and
    DATA.size == filesize-32.  They carry no payload of their own.
    Every other chunk is a leaf whose payload is `size` bytes long.
    Strings are UTF-8, NOT NUL-terminated, and there is no padding or
    alignment anywhere -- chunks are packed back to back and the last chunk
    ends exactly at EOF.

USAGE
    ru_zkan.py extract      <in.dat>  <out.json>
    ru_zkan.py rebuild      <in.dat>  <translated.json>  <out.dat>
    ru_zkan.py extract-dir  <in_dir>  <out_json_dir>
    ru_zkan.py rebuild-dir  <in_dir>  <json_dir>  <out_dir>
    ru_zkan.py roundtrip    <in_dir> [<in_dir> ...]        # byte-exact selftest
    ru_zkan.py index        <out.json> <in_dir> [<in_dir> ...]
    ru_zkan.py dump         <in.dat>                       # human-readable peek

`rebuild` only needs the fields you want to change: anything missing from the
JSON is taken from <in.dat>, so a JSON holding just {"fields":[{"tag":"DSCR",
"text":"..."}]} is a valid translation patch.  Text of arbitrary length is
fine: DSIZ/DATA and every chunk size are recomputed.
"""

import base64
import json
import os
import struct
import sys

MAGIC = b'ZKAN'
TYPES = (b'CHAR', b'ROBO', b'PDNM')
CONTAINER_TAGS = ('DSIZ', 'DATA')

# Leaf chunks holding UTF-8 text.
TEXT_TAGS = {
    # CHAR
    'CHFN': 'full name',
    'CHNN': 'short name',
    'ACTR': 'voice actor',
    'KANA': 'japanese reading (always the placeholder in western builds)',
    # ROBO
    'RBTN': 'robot name',
    'RBN2': 'robot name (long / alternate)',
    'PLTN': 'pilot(s), fullwidth digits',
    'HEIT': 'height, fullwidth digits + fullwidth m',
    'WEIT': 'weight, fullwidth digits + fullwidth t',
    # shared
    'PRDC': 'source series',
    'DSCR': 'description (multi-line, \\n separated)',
    'DSC2': 'post-clear description; placeholder <srw-tag=before-clear-text-here>',
}

# Leaf chunks holding binary data (arrays of LE u32).
BIN_TAGS = {
    'VOIC': 'voice clip ids (u32[])',
    'LOOK': 'portrait / expression ids (u32[])',
    'LorR': 'u32 flag, always 0',
}

NAME_TAG = {'CHAR': 'CHFN', 'ROBO': 'RBTN', 'PDNM': None}


# --------------------------------------------------------------------------
# obfuscation layer
# --------------------------------------------------------------------------

_XOR = bytes(b if b in (0x00, 0x5E) else b ^ 0x5E for b in range(256))


def deobf(data):
    """De-obfuscate (and, being an involution, obfuscate) a whole record."""
    return bytes(data).translate(_XOR)


obf = deobf


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

class ZkanError(Exception):
    pass


def _u32(buf, off):
    return struct.unpack_from('<I', buf, off)[0]


def parse(raw):
    """raw = on-disk (post-Blowfish) bytes -> dict record."""
    x = deobf(raw)
    if len(x) < 16:
        raise ZkanError('too short (%d bytes)' % len(x))
    if x[0:4] != MAGIC:
        raise ZkanError('bad magic %r' % x[0:4])
    rtype = x[4:8]
    if rtype not in TYPES:
        raise ZkanError('unknown record type %r' % rtype)

    rec = {
        'format': 'ZKAN',
        'type': rtype.decode('ascii'),
        'version': _u32(x, 8),
        'header_unk12': _u32(x, 12),
        'containers': [],
        'fields': [],
    }

    off = 16
    while off < len(x):
        if off + 8 > len(x):
            raise ZkanError('truncated chunk header at 0x%X' % off)
        tag = x[off:off + 4].decode('latin-1')
        size = _u32(x, off + 4)
        if tag in CONTAINER_TAGS:
            off += 8
            if off + size != len(x):
                raise ZkanError('%s size %d does not reach EOF '
                                '(payload starts 0x%X, file %d)' % (tag, size, off, len(x)))
            rec['containers'].append(tag)
            continue
        off += 8
        if off + size > len(x):
            raise ZkanError('%s payload overruns EOF' % tag)
        payload = x[off:off + size]
        off += size
        rec['fields'].append(_leaf_to_json(tag, payload))

    if off != len(x):
        raise ZkanError('trailing %d bytes' % (len(x) - off))
    if rec['containers'] != list(CONTAINER_TAGS):
        raise ZkanError('unexpected container layout %r' % rec['containers'])
    return rec


def _leaf_to_json(tag, payload):
    if tag in TEXT_TAGS:
        try:
            return {'tag': tag, 'kind': 'text', 'text': payload.decode('utf-8')}
        except UnicodeDecodeError:
            pass  # fall through to binary, keeps round-trip exact
    item = {'tag': tag, 'kind': 'bin', 'hex': payload.hex()}
    if len(payload) % 4 == 0 and payload:
        item['u32'] = list(struct.unpack('<%dI' % (len(payload) // 4), payload))
    item['base64'] = base64.b64encode(payload).decode('ascii')
    return item


def _leaf_payload(item):
    """JSON field -> raw payload bytes."""
    if 'text' in item and item.get('kind', 'text') != 'bin':
        return item['text'].encode('utf-8')
    if 'hex' in item:
        return bytes.fromhex(item['hex'])
    if 'base64' in item:
        return base64.b64decode(item['base64'])
    if 'u32' in item:
        return struct.pack('<%dI' % len(item['u32']), *item['u32'])
    raise ZkanError('field %r has no payload' % item.get('tag'))


# --------------------------------------------------------------------------
# building
# --------------------------------------------------------------------------

def build(rec):
    """dict record -> on-disk (post-Blowfish, pre-Blowfish-encrypt) bytes."""
    rtype = rec['type'].encode('ascii')
    if rtype not in TYPES:
        raise ZkanError('unknown record type %r' % rec['type'])

    body = bytearray()
    for item in rec['fields']:
        tag = item['tag']
        if len(tag.encode('latin-1')) != 4:
            raise ZkanError('tag %r is not 4 bytes' % tag)
        payload = _leaf_payload(item)
        body += tag.encode('latin-1') + struct.pack('<I', len(payload)) + payload

    out = bytearray()
    out += MAGIC + rtype
    out += struct.pack('<II', rec.get('version', 0x100), rec.get('header_unk12', 12))
    # DATA wraps the leaf stream, DSIZ wraps the DATA chunk.
    data_chunk = b'DATA' + struct.pack('<I', len(body)) + bytes(body)
    out += b'DSIZ' + struct.pack('<I', len(data_chunk))
    out += data_chunk
    return obf(bytes(out))


def merge(base, patch):
    """Overlay a (possibly partial) translation JSON onto a parsed record.

    Matching is by tag; the n-th occurrence of a tag in `patch` updates the
    n-th occurrence in `base`.  Tags absent from `patch` keep their original
    bytes.  A field may also carry "drop": true to remove it, and brand new
    tags are appended at the end (needed only for exotic edits).
    """
    rec = json.loads(json.dumps(base))  # deep copy
    if patch.get('type') and patch['type'] != rec['type']:
        raise ZkanError('type mismatch: json %r vs record %r'
                        % (patch['type'], rec['type']))
    for key in ('version', 'header_unk12'):
        if key in patch:
            rec[key] = patch[key]

    used = {}
    for item in patch.get('fields', []):
        tag = item['tag']
        n = used.get(tag, 0)
        used[tag] = n + 1
        hits = [i for i, f in enumerate(rec['fields']) if f['tag'] == tag]
        if n < len(hits):
            idx = hits[n]
            if item.get('drop'):
                rec['fields'][idx] = None
            else:
                new = dict(rec['fields'][idx])
                if 'text' in item:
                    new = {'tag': tag, 'kind': 'text', 'text': item['text']}
                elif 'hex' in item:
                    new = {'tag': tag, 'kind': 'bin', 'hex': item['hex']}
                elif 'base64' in item:
                    new = {'tag': tag, 'kind': 'bin', 'base64': item['base64']}
                elif 'u32' in item:
                    new = {'tag': tag, 'kind': 'bin', 'u32': item['u32']}
                rec['fields'][idx] = new
        elif not item.get('drop'):
            rec['fields'].append(item)
    rec['fields'] = [f for f in rec['fields'] if f is not None]
    return rec


# --------------------------------------------------------------------------
# file helpers
# --------------------------------------------------------------------------

def read_record(path):
    with open(path, 'rb') as fh:
        return parse(fh.read())


def write_json(path, obj):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write('\n')


def load_json(path):
    with open(path, 'r', encoding='utf-8-sig') as fh:
        return json.load(fh)


def dat_files(d):
    return sorted(f for f in os.listdir(d)
                  if os.path.isfile(os.path.join(d, f))
                  and f.lower().endswith(('.dat', '.bin')))


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_extract(argv):
    inp, out = argv
    rec = read_record(inp)
    rec['source'] = os.path.basename(inp)
    write_json(out, rec)
    nt = sum(len(f['text']) for f in rec['fields'] if f['kind'] == 'text')
    print('%s -> %s  (%s, %d fields, %d text chars)'
          % (inp, out, rec['type'], len(rec['fields']), nt))


def cmd_rebuild(argv):
    inp, jsonp, out = argv
    base = read_record(inp)
    rec = merge(base, load_json(jsonp))
    data = build(rec)
    d = os.path.dirname(out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out, 'wb') as fh:
        fh.write(data)
    with open(inp, 'rb') as fh:
        orig = fh.read()
    tag = 'identical' if data == orig else '%+d bytes' % (len(data) - len(orig))
    print('%s + %s -> %s  (%d bytes, %s)' % (inp, jsonp, out, len(data), tag))


def cmd_extract_dir(argv):
    ind, outd = argv
    os.makedirs(outd, exist_ok=True)
    n = 0
    for f in dat_files(ind):
        rec = read_record(os.path.join(ind, f))
        rec['source'] = f
        write_json(os.path.join(outd, os.path.splitext(f)[0] + '.json'), rec)
        n += 1
    print('extracted %d records: %s -> %s' % (n, ind, outd))


def cmd_rebuild_dir(argv):
    ind, jsond, outd = argv
    os.makedirs(outd, exist_ok=True)
    n = changed = 0
    for f in dat_files(ind):
        src = os.path.join(ind, f)
        jp = os.path.join(jsond, os.path.splitext(f)[0] + '.json')
        base = read_record(src)
        rec = merge(base, load_json(jp)) if os.path.exists(jp) else base
        data = build(rec)
        with open(src, 'rb') as fh:
            orig = fh.read()
        if data != orig:
            changed += 1
        with open(os.path.join(outd, f), 'wb') as fh:
            fh.write(data)
        n += 1
    print('rebuilt %d records (%d differ from original) -> %s' % (n, changed, outd))


def cmd_roundtrip(argv):
    grand_ok = grand_bad = 0
    for ind in argv:
        ok = bad = 0
        for f in dat_files(ind):
            p = os.path.join(ind, f)
            with open(p, 'rb') as fh:
                orig = fh.read()
            try:
                rec = parse(orig)
                # go through JSON so the on-disk representation is exercised too
                rec = json.loads(json.dumps(rec, ensure_ascii=False))
                rebuilt = build(merge(rec, {}))
            except Exception as exc:          # noqa: BLE001
                print('  FAIL %s: %s' % (f, exc))
                bad += 1
                continue
            if rebuilt == orig:
                ok += 1
            else:
                bad += 1
                print('  DIFF %s (%d vs %d bytes)' % (f, len(rebuilt), len(orig)))
        print('%-40s %4d/%4d byte-identical%s'
              % (os.path.basename(ind.rstrip('\\/')), ok, ok + bad,
                 '' if not bad else '   <-- %d FAILED' % bad))
        grand_ok += ok
        grand_bad += bad
    print('TOTAL %d/%d byte-identical, %d failures'
          % (grand_ok, grand_ok + grand_bad, grand_bad))
    return 1 if grand_bad else 0


def _field(rec, tag):
    for f in rec['fields']:
        if f['tag'] == tag:
            return f.get('text', '')
    return ''


def cmd_index(argv):
    out, dirs = argv[0], argv[1:]
    entries = []
    totals = {}
    for ind in dirs:
        label = os.path.basename(ind.rstrip('\\/'))
        for f in dat_files(ind):
            rec = read_record(os.path.join(ind, f))
            name = _field(rec, NAME_TAG[rec['type']] or '')
            dscr = _field(rec, 'DSCR')
            dsc2 = _field(rec, 'DSC2')
            if rec['type'] == 'PDNM' and not name:
                name = dscr.split('\n', 1)[0][:48].strip()
            e = {
                'dir': label,
                'file': f,
                'type': rec['type'],
                'name': name,
                'short_name': _field(rec, 'CHNN') or _field(rec, 'RBN2'),
                'series': _field(rec, 'PRDC'),
                'actor': _field(rec, 'ACTR'),
                'desc_chars': len(dscr),
                'desc2_chars': len(dsc2),
                'desc2_is_placeholder': dsc2 == '<srw-tag=before-clear-text-here>',
                'text_chars': sum(len(x['text']) for x in rec['fields']
                                  if x['kind'] == 'text'),
            }
            entries.append(e)
            t = totals.setdefault(label, {'records': 0, 'desc_chars': 0,
                                          'desc2_chars': 0, 'text_chars': 0})
            t['records'] += 1
            t['desc_chars'] += e['desc_chars']
            t['desc2_chars'] += e['desc2_chars']
            t['text_chars'] += e['text_chars']
    write_json(out, {'records': len(entries), 'by_dir': totals, 'entries': entries})
    print('index: %d records -> %s' % (len(entries), out))
    for k, v in totals.items():
        print('  %-18s %4d records, DSCR %7d ch, DSC2 %7d ch, all text %7d ch'
              % (k, v['records'], v['desc_chars'], v['desc2_chars'], v['text_chars']))
    print('  %-18s %4d records, DSCR %7d ch, DSC2 %7d ch, all text %7d ch'
          % ('TOTAL', len(entries),
             sum(v['desc_chars'] for v in totals.values()),
             sum(v['desc2_chars'] for v in totals.values()),
             sum(v['text_chars'] for v in totals.values())))


def _say(line):
    """print() that survives a legacy console codepage (cp1251/cp866)."""
    enc = sys.stdout.encoding or 'utf-8'
    try:
        print(line)
    except UnicodeEncodeError:
        sys.stdout.write(line.encode(enc, 'backslashreplace').decode(enc) + '\n')


def cmd_dump(argv):
    rec = read_record(argv[0])
    _say('ZKAN%s  version 0x%X  unk12 %d  containers %s'
         % (rec['type'], rec['version'], rec['header_unk12'],
            '/'.join(rec['containers'])))
    for f in rec['fields']:
        if f['kind'] == 'text':
            _say('  %-4s text %5d  %s' % (f['tag'], len(f['text'].encode('utf-8')),
                                          f['text'].replace('\n', '\\n')))
        else:
            _say('  %-4s bin  %5d  %s%s'
                 % (f['tag'], len(f['hex']) // 2, f['hex'],
                    '  u32=%s' % f['u32'] if 'u32' in f else ''))


COMMANDS = {
    'extract': (cmd_extract, 2, '<in.dat> <out.json>'),
    'rebuild': (cmd_rebuild, 3, '<in.dat> <translated.json> <out.dat>'),
    'extract-dir': (cmd_extract_dir, 2, '<in_dir> <out_json_dir>'),
    'rebuild-dir': (cmd_rebuild_dir, 3, '<in_dir> <json_dir> <out_dir>'),
    'roundtrip': (cmd_roundtrip, -1, '<in_dir> [<in_dir> ...]'),
    'index': (cmd_index, -2, '<out.json> <in_dir> [<in_dir> ...]'),
    'dump': (cmd_dump, 1, '<in.dat>'),
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__.strip())
        return 2
    fn, nargs, usage = COMMANDS[argv[1]]
    args = argv[2:]
    if (nargs >= 0 and len(args) != nargs) or (nargs < 0 and len(args) < -nargs):
        print('usage: ru_zkan.py %s %s' % (argv[1], usage))
        return 2
    return fn(args) or 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
