#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ru_mtfl.py -- parser/rebuilder for the MTFL "kwrb" container used by
Super Robot Wars V for the in-game KeyWord (glossary) window.

Target file: MtV_all_keyword_def.cpk -> 00000000.dat (after CPK unpack +
Blowfish decryption with srwv_decrypt.py).

Commands
--------
  extract <in.dat> <out.json>
        Dump every keyword article to JSON (UTF-8, human editable).

  apply <extracted.json> <ru.json> <out.json>
        Convenience merge: takes the output of `extract` and a translation
        file keyed by the English term (term_en / term_ru / series_ru /
        text_ru / text2_ru) and produces a translated JSON for `rebuild`.

  rebuild <in.dat> <translated.json> <out.dat>
        Rebuild the .dat using the structure of <in.dat> and the texts from
        <translated.json>.  Strings may be of ANY length: the string pool is
        re-laid-out and all offsets / codepoint counts / section sizes are
        recomputed.  Obfuscation is applied internally.

  info <in.dat>
        Print the container layout.

Round-trip guarantee
--------------------
  extract X.dat tmp.json && rebuild X.dat tmp.json Y.dat   =>  Y.dat == X.dat
(verified byte-exact on both the EN and the JP file)

See MTFL_FORMAT.md for the full format description.
"""

import sys
import os
import json
import struct
import hashlib

MAGIC = b'MTFLz2_2'
FILE_HDR_SIZE = 0x20
SEC_HDR_MIN = 16
ENTRY_SIZE = 40          # 10 x uint32
TAIL_MAGIC = b'ENDoMTFL'

# "before clear" marker that prefixes the post-clear description string
MARK = '<srw-tag=before-clear-text-here>'

# ---------------------------------------------------------------------------
# Text obfuscation
# ---------------------------------------------------------------------------
# The string pool is scrambled with XOR 0x7A, BUT the two bytes that the XOR
# would swap with each other -- 0x00 (the C string terminator) and 0x7A (the
# ASCII letter 'z') -- are left untouched.  That keeps the pool a valid
# NUL-terminated C string pool while still looking like noise.
#
# It is an involution, so the same table encodes and decodes.
#
# Consequence: the letter 'z' is NOT a problem at all.  Naive "XOR everything"
# turns a real 'z' into 0x00 and the terminator into 'z', which is what makes
# words like "Gaizok" / "realized" look like they contain a separator.
_XOR_TABLE = bytes((c if c in (0x00, 0x7A) else c ^ 0x7A) for c in range(256))


def scramble(data: bytes) -> bytes:
    """Encode or decode the string pool (involution)."""
    return data.translate(_XOR_TABLE)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def u32(buf, off):
    return struct.unpack_from('<I', buf, off)[0]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MtflError(Exception):
    pass


# ---------------------------------------------------------------------------
# container parsing
# ---------------------------------------------------------------------------
class Section(object):
    __slots__ = ('tag', 'pos', 'total', 'hdr', 'payload', 'extra')

    def __init__(self, tag, pos, total, hdr, payload, extra):
        self.tag = tag
        self.pos = pos
        self.total = total
        self.hdr = hdr
        self.payload = payload
        self.extra = extra          # raw bytes of header beyond the first 16

    @property
    def data_off(self):
        return self.pos + self.hdr


def read_section(buf, pos):
    tag = buf[pos:pos + 4]
    total, hdr, payload = struct.unpack_from('<III', buf, pos + 4)
    if hdr < SEC_HDR_MIN or total != hdr + payload:
        raise MtflError('bad section %r at 0x%X (total=%d hdr=%d payload=%d)'
                        % (tag, pos, total, hdr, payload))
    extra = bytes(buf[pos + SEC_HDR_MIN:pos + hdr])
    return Section(tag, pos, total, hdr, payload, extra)


class Mtfl(object):
    """Parsed MTFL/kwrb keyword file."""

    def __init__(self, data: bytes):
        self.raw = data
        if data[:8] != MAGIC:
            raise MtflError('not an MTFL file (magic %r)' % data[:8])
        self.hdr_size = u32(data, 8)
        if self.hdr_size != FILE_HDR_SIZE:
            raise MtflError('unexpected file header size %d' % self.hdr_size)
        self.version = data[0x0C:0x10].decode('ascii')
        self.content_size = u32(data, 0x10)
        self.hdr_reserved = bytes(data[0x14:FILE_HDR_SIZE])

        content_end = FILE_HDR_SIZE + self.content_size
        if content_end > len(data):
            raise MtflError('content size overruns file')
        self.tail = bytes(data[content_end:])
        if self.tail[:8] != TAIL_MAGIC:
            raise MtflError('missing %r trailer' % TAIL_MAGIC)

        # top level: a single 'kwrb' section
        self.kwrb = read_section(data, FILE_HDR_SIZE)
        if self.kwrb.tag != b'kwrb':
            raise MtflError('expected kwrb, got %r' % self.kwrb.tag)
        if self.kwrb.total != self.content_size:
            raise MtflError('kwrb size != content size')

        # children of kwrb
        self.children = []
        p = self.kwrb.data_off
        end = self.kwrb.pos + self.kwrb.total
        while p < end:
            s = read_section(data, p)
            self.children.append(s)
            p += s.total
        if p != end:
            raise MtflError('child sections overrun kwrb')

        tags = [s.tag for s in self.children]
        if tags != [b'lkke', b'jstr']:
            raise MtflError('unexpected child layout %r' % tags)
        self.lkke, self.jstr = self.children

        # --- lkke : keyword index table -----------------------------------
        if self.lkke.hdr != 20:
            raise MtflError('unexpected lkke header size %d' % self.lkke.hdr)
        self.entry_count = u32(data, self.lkke.pos + 16)
        if self.entry_count * ENTRY_SIZE != self.lkke.payload:
            raise MtflError('lkke payload != count*%d' % ENTRY_SIZE)
        self.entries = []
        eo = self.lkke.data_off
        for i in range(self.entry_count):
            self.entries.append(list(struct.unpack_from('<10I', data,
                                                        eo + i * ENTRY_SIZE)))

        # --- jstr : scrambled NUL separated string pool ---------------------
        pool = scramble(bytes(data[self.jstr.data_off:
                                   self.jstr.data_off + self.jstr.payload]))
        self.pool_trailing_nul = bool(pool) and pool[-1] == 0

        self.slots = []        # list[str]   -- pool strings, in pool order
        self.slot_at = {}      # byte offset -> slot index
        off = 0
        while off < len(pool):
            nul = pool.find(b'\x00', off)
            if nul < 0:
                nul = len(pool)
            self.slot_at[off] = len(self.slots)
            self.slots.append(pool[off:nul].decode('utf-8'))
            off = nul + 1
        if self.pool_trailing_nul:
            # join() model below assumes no trailing separator; keep a flag
            pass

        # every entry field must point at a slot start
        self.fields = []       # per entry: [term, series, desc, desc2] slot ids
        for i, e in enumerate(self.entries):
            f = []
            for k in range(4):
                o = e[k * 2]
                if o not in self.slot_at:
                    raise MtflError('entry %d field %d offset %d is not a '
                                    'string start' % (i, k, o))
                si = self.slot_at[o]
                if len(self.slots[si]) != e[k * 2 + 1]:
                    raise MtflError('entry %d field %d length mismatch '
                                    '(%d stored vs %d codepoints)'
                                    % (i, k, e[k * 2 + 1],
                                       len(self.slots[si])))
                f.append(si)
            self.fields.append(f)

    # -- article view -------------------------------------------------------
    def articles(self):
        out = []
        for i, e in enumerate(self.entries):
            ft, fs, fd, fd2 = self.fields[i]
            desc = self.slots[fd]
            raw2 = self.slots[fd2]
            if fd2 == fd:
                mode, desc2 = 'shared', ''
            elif raw2 == MARK:
                mode, desc2 = 'same', ''
            elif raw2.startswith(MARK):
                mode, desc2 = 'append', raw2[len(MARK):]
            else:
                mode, desc2 = 'full', raw2
            out.append({
                'idx': i,
                'id': e[9],
                'flag': e[8],
                'term': self.slots[ft],
                'series': self.slots[fs],
                'desc': desc,
                'desc2': desc2,
                'desc2_mode': mode,
            })
        return out


def field_texts_from_article(a):
    """article dict -> (term, series, desc, desc2_raw)"""
    mode = a.get('desc2_mode', 'same')
    desc = a['desc']
    if 'desc2_raw' in a:
        raw2 = a['desc2_raw']
    elif mode == 'shared':
        raw2 = desc
    elif mode == 'same':
        raw2 = MARK
    elif mode == 'append':
        raw2 = MARK + a.get('desc2', '')
    elif mode == 'full':
        raw2 = a.get('desc2', '')
    else:
        raise MtflError('unknown desc2_mode %r' % mode)
    return a['term'], a['series'], desc, raw2


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_info(path):
    data = open(path, 'rb').read()
    m = Mtfl(data)
    print('file          : %s' % path)
    print('size          : %d bytes   sha256 %s' % (len(data), sha256(data)))
    print('magic/version : %s %s   header %d bytes' %
          (MAGIC.decode(), m.version, m.hdr_size))
    print('content size  : %d  (trailer %d bytes)' %
          (m.content_size, len(m.tail)))
    print('  0x%06X kwrb  total=%-7d hdr=%d payload=%d' %
          (m.kwrb.pos, m.kwrb.total, m.kwrb.hdr, m.kwrb.payload))
    for s in m.children:
        print('    0x%06X %s  total=%-7d hdr=%-2d payload=%-7d extra=%s' %
              (s.pos, s.tag.decode(), s.total, s.hdr, s.payload,
               s.extra.hex() if s.extra else '-'))
    print('entries       : %d   pool strings: %d   trailing NUL: %s' %
          (m.entry_count, len(m.slots), m.pool_trailing_nul))
    refd = set()
    for f in m.fields:
        refd.update(f)
    print('referenced    : %d slots (%d orphan)' %
          (len(refd), len(m.slots) - len(refd)))
    cps = sum(len(s) for s in m.slots)
    print('pool          : %d bytes, %d codepoints' %
          (m.jstr.payload, cps))


def cmd_extract(src, dst):
    data = open(src, 'rb').read()
    m = Mtfl(data)
    arts = m.articles()
    doc = {
        'format': 'MTFL/kwrb keyword table',
        'source': os.path.basename(src),
        'source_sha256': sha256(data),
        'version': m.version,
        'entry_count': m.entry_count,
        'note': ('desc2_mode: same = post-clear text equals desc; '
                 'append = desc2 is appended after desc once the scenario is '
                 'cleared; full = desc2 replaces desc; shared = desc2 points '
                 'at the very same pool string as desc. '
                 'Edit term/series/desc/desc2 freely, any length.'),
        'articles': arts,
    }
    with open(dst, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    tr = sum(len(a['term']) + len(a['series']) + len(a['desc']) +
             len(a['desc2']) for a in arts)
    uniq = set()
    for a in arts:
        uniq.update((a['term'], a['series'], a['desc']))
        if a['desc2']:
            uniq.add(a['desc2'])
    print('extracted %d articles -> %s' % (len(arts), dst))
    print('  %d codepoints total, %d unique strings / %d codepoints unique'
          % (tr, len(uniq), sum(len(s) for s in uniq)))


def cmd_apply(base_json, ru_json, out_json):
    doc = json.load(open(base_json, encoding='utf-8'))
    ru = json.load(open(ru_json, encoding='utf-8'))
    ru_items = ru['articles'] if isinstance(ru, dict) else ru
    by_term = {}
    for r in ru_items:
        key = r.get('term_en') or r.get('term')
        if key:
            by_term[key] = r
    hit = 0
    for a in doc['articles']:
        r = by_term.get(a['term'])
        if not r:
            continue
        hit += 1
        if r.get('term_ru'):
            a['term'] = r['term_ru']
        if r.get('series_ru'):
            a['series'] = r['series_ru']
        if r.get('text_ru'):
            a['desc'] = r['text_ru']
        if r.get('text2_ru'):
            txt2 = r['text2_ru']
            if a['desc2_mode'] in ('same', 'append'):
                # the stored extra text starts right after the marker; the
                # original files begin it with a newline
                a['desc2_mode'] = 'append'
                a['desc2'] = txt2 if txt2.startswith('\n') else '\n' + txt2
            else:
                a['desc2'] = txt2
    with open(out_json, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print('applied %d/%d translations -> %s' % (hit, len(by_term), out_json))


def build_pool(m, texts):
    """texts: list per entry of (term, series, desc, desc2_raw) strings.

    Returns (slot_texts, fields) keeping the original slot order; strings that
    changed in a way that conflicts with slot sharing get appended at the end.
    """
    slots = list(m.slots)
    fields = [list(f) for f in m.fields]

    # collect the wanted text of every slot
    wanted = {}
    for i, t4 in enumerate(texts):
        for k in range(4):
            wanted.setdefault(fields[i][k], []).append((i, k, t4[k]))

    for si, uses in wanted.items():
        variants = []
        for (_, _, txt) in uses:
            if txt not in variants:
                variants.append(txt)
        if len(variants) == 1:
            slots[si] = variants[0]
            continue
        # keep the original text in place when it is still used, otherwise the
        # first variant; move the rest to fresh slots at the end of the pool
        primary = m.slots[si] if m.slots[si] in variants else variants[0]
        slots[si] = primary
        extra = {}
        for (i, k, txt) in uses:
            if txt == primary:
                continue
            if txt not in extra:
                slots.append(txt)
                extra[txt] = len(slots) - 1
            fields[i][k] = extra[txt]
    return slots, fields


def cmd_rebuild(src, tr_json, dst):
    data = open(src, 'rb').read()
    m = Mtfl(data)
    doc = json.load(open(tr_json, encoding='utf-8'))
    arts = doc['articles'] if isinstance(doc, dict) else doc
    if len(arts) != m.entry_count:
        raise MtflError('json has %d articles, file has %d entries'
                        % (len(arts), m.entry_count))

    by_idx = {}
    for a in arts:
        by_idx[a['idx']] = a
    texts = []
    for i in range(m.entry_count):
        a = by_idx.get(i)
        if a is None:
            raise MtflError('json is missing article idx=%d' % i)
        t4 = field_texts_from_article(a)
        for k, s in enumerate(t4):
            if '\x00' in s:
                raise MtflError('entry %d field %d contains NUL' % (i, k))
        texts.append(t4)

    slots, fields = build_pool(m, texts)

    # --- lay the pool out -------------------------------------------------
    enc = [s.encode('utf-8') for s in slots]
    offsets = []
    pos = 0
    for b in enc:
        offsets.append(pos)
        pos += len(b) + 1
    pool = b'\x00'.join(enc)
    if m.pool_trailing_nul:
        pool += b'\x00'
    else:
        pos -= 1                       # last string has no terminator
    assert len(pool) == pos, (len(pool), pos)

    # --- patch the entry table -------------------------------------------
    lkke_bytes = bytearray(data[m.lkke.pos:m.lkke.pos + m.lkke.total])
    for i in range(m.entry_count):
        e = list(m.entries[i])
        for k in range(4):
            si = fields[i][k]
            e[k * 2] = offsets[si]
            e[k * 2 + 1] = len(slots[si])
        struct.pack_into('<10I', lkke_bytes,
                         m.lkke.hdr + i * ENTRY_SIZE, *e)

    # --- reassemble --------------------------------------------------------
    jstr_payload = scramble(pool)
    jstr_hdr = bytearray(data[m.jstr.pos:m.jstr.pos + m.jstr.hdr])
    struct.pack_into('<III', jstr_hdr, 4,
                     m.jstr.hdr + len(jstr_payload), m.jstr.hdr,
                     len(jstr_payload))

    kwrb_payload_len = len(lkke_bytes) + len(jstr_hdr) + len(jstr_payload)
    kwrb_hdr = bytearray(data[m.kwrb.pos:m.kwrb.pos + m.kwrb.hdr])
    struct.pack_into('<III', kwrb_hdr, 4,
                     m.kwrb.hdr + kwrb_payload_len, m.kwrb.hdr,
                     kwrb_payload_len)
    content_size = m.kwrb.hdr + kwrb_payload_len

    file_hdr = bytearray(data[:FILE_HDR_SIZE])
    struct.pack_into('<I', file_hdr, 0x10, content_size)

    out = bytes(file_hdr) + bytes(kwrb_hdr) + bytes(lkke_bytes) + \
        bytes(jstr_hdr) + jstr_payload + m.tail

    with open(dst, 'wb') as fh:
        fh.write(out)

    # sanity: the result must parse again
    chk = Mtfl(out)
    chk.articles()

    print('rebuilt -> %s' % dst)
    print('  %d bytes (orig %d, delta %+d), pool %d slots / %d bytes'
          % (len(out), len(data), len(out) - len(data), len(slots), len(pool)))
    print('  sha256 %s' % sha256(out))
    if out == data:
        print('  IDENTICAL to source')


# ---------------------------------------------------------------------------
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    try:
        if cmd == 'extract' and len(argv) == 4:
            cmd_extract(argv[2], argv[3])
        elif cmd == 'rebuild' and len(argv) == 5:
            cmd_rebuild(argv[2], argv[3], argv[4])
        elif cmd == 'apply' and len(argv) == 5:
            cmd_apply(argv[2], argv[3], argv[4])
        elif cmd == 'info' and len(argv) == 3:
            cmd_info(argv[2])
        else:
            print(__doc__)
            return 2
    except MtflError as exc:
        sys.stderr.write('error: %s\n' % exc)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
