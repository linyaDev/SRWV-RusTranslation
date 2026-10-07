#!/usr/bin/env python3
"""
Patcher for ITOC-based CPK archives (SRW V).

Replaces file data by ID (stored uncompressed) and REBUILDS the ITOC:
files are re-partitioned between DataL (uint16 sizes) and DataH (uint32
sizes) when a replacement outgrows the 16-bit fields, FilesL/FilesH and
the CPK header stats are updated, and ContentOffset shifts if the ITOC
grows beyond its original slack. Layout matches the game's reader:
files laid out sequentially from ContentOffset, aligned to Align.

Usage: ru_cpk_patch.py input.cpk output.cpk ID=newfile [ID=newfile ...]
"""
import struct
import sys

STORAGE_MASK, STORAGE_PERROW, STORAGE_CONSTANT, STORAGE_ZERO = 0xF0, 0x50, 0x30, 0x10
TYPE_MASK = 0x0F
TYPE_FMT = {0x0B: '>LL', 0x0A: '>L', 0x08: '>f', 0x07: '>q', 0x06: '>Q',
            0x05: '>l', 0x04: '>L', 0x03: '>h', 0x02: '>H', 0x01: '>b', 0x00: '>B'}


def xor_crypt(data: bytes) -> bytes:
    c, m = 0x5F, 0x15
    out = bytearray(data)
    for i in range(len(out)):
        out[i] ^= c & 0xFF
        c = (c * m) & 0xFF
    return bytes(out)


class UTF:
    """Parses a @UTF blob; records value offsets so fields can be patched."""

    def __init__(self, blob: bytes):
        assert blob[:4] == b'@UTF', blob[:4]
        self.blob = bytearray(blob)
        (self.rows_off, self.str_off, self.data_off, name_off,
         self.ncols, self.row_width, self.nrows) = struct.unpack_from('>LLLLHHL', blob, 8)
        self.base = 8
        pos = 8 + 0x18
        self.columns = []
        for _ in range(self.ncols):
            type_id, noff = struct.unpack_from('>BL', blob, pos)
            pos += 5
            storage, ftype = type_id & STORAGE_MASK, type_id & TYPE_MASK
            const_off = None
            if storage == STORAGE_CONSTANT:
                const_off = pos
                pos += struct.calcsize(TYPE_FMT[ftype])
            self.columns.append({'name': self._str(noff), 'storage': storage,
                                 'ftype': ftype, 'const_off': const_off})
        self.schema_end = pos  # abs offset where schema region ends

    def _str(self, off):
        start = self.base + self.str_off + off
        end = self.blob.index(b'\x00', start)
        return self.blob[start:end].decode('utf-8')

    def locate(self, row: int, colname: str):
        pos = self.base + self.rows_off + row * self.row_width
        for col in self.columns:
            fmt = TYPE_FMT[col['ftype']]
            if col['name'] == colname:
                if col['storage'] == STORAGE_PERROW:
                    return pos, fmt
                if col['storage'] == STORAGE_CONSTANT:
                    return col['const_off'], fmt
                raise KeyError(f'{colname}: storage {col["storage"]:#x} not patchable')
            if col['storage'] == STORAGE_PERROW:
                pos += struct.calcsize(fmt)
        raise KeyError(colname)

    def value(self, row: int, colname: str):
        for col in self.columns:
            if col['name'] == colname:
                if col['storage'] == STORAGE_ZERO:
                    return 0
                off, fmt = self.locate(row, colname)
                v = struct.unpack_from(fmt, self.blob, off)
                return v if len(v) > 1 else v[0]
        raise KeyError(colname)

    def set(self, row: int, colname: str, value):
        off, fmt = self.locate(row, colname)
        vals = value if isinstance(value, tuple) else (value,)
        struct.pack_into(fmt, self.blob, off, *vals)

    def has(self, colname: str):
        return any(c['name'] == colname for c in self.columns)

    def rebuild_rows(self, rows: list) -> bytes:
        """Return a new blob with the same schema/strings but new per-row data.

        rows: list of dicts {colname: value} for PERROW columns.
        Data (0x0B) columns are not supported in rebuilt rows.
        """
        head = bytes(self.blob[self.base:self.schema_end])  # header + schema
        new_rows = bytearray()
        for r in rows:
            for col in self.columns:
                if col['storage'] != STORAGE_PERROW:
                    continue
                fmt = TYPE_FMT[col['ftype']]
                v = r[col['name']]
                vals = v if isinstance(v, tuple) else (v,)
                new_rows += struct.pack(fmt, *vals)
        strings_and_data = bytes(self.blob[self.base + self.str_off:])
        rows_off = self.rows_off  # header+schema size unchanged
        str_off = rows_off + len(new_rows)
        data_off = str_off + (self.data_off - self.str_off)
        content = bytearray(head + bytes(new_rows) + strings_and_data)
        struct.pack_into('>LLL', content, 0, rows_off, str_off, data_off)
        struct.pack_into('>L', content, 16 + 4, len(rows))  # nrows at +0x14
        return b'@UTF' + struct.pack('>L', len(content)) + bytes(content)


def read_frame(data: bytes, offset: int):
    utf_size, = struct.unpack_from('<L', data, offset + 8)
    utf_pos = offset + 16
    blob = bytes(data[utf_pos:utf_pos + utf_size])
    enc = blob[:4] != b'@UTF'
    if enc:
        blob = xor_crypt(blob)
        assert blob[:4] == b'@UTF', 'bad UTF after decrypt'
    return blob, utf_pos, utf_size, enc


def align_up(v, a):
    return v if (a == 0 or v % a == 0) else v + a - (v % a)


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    in_path, out_path = sys.argv[1], sys.argv[2]
    repl = {}
    for arg in sys.argv[3:]:
        fid, path = arg.split('=', 1)
        repl[int(fid)] = open(path, 'rb').read()

    data = bytearray(open(in_path, 'rb').read())

    # --- CPK header ---
    hdr_blob, hdr_pos, hdr_size, hdr_enc = read_frame(data, 0)
    hdr = UTF(hdr_blob)
    content_off = hdr.value(0, 'ContentOffset')
    itoc_off = hdr.value(0, 'ItocOffset')
    align = hdr.value(0, 'Align') if hdr.has('Align') else 0
    toc_off = hdr.value(0, 'TocOffset') if hdr.has('TocOffset') else 0
    assert itoc_off and not toc_off, 'only pure ITOC CPKs supported'

    # --- ITOC ---
    itoc_blob, itoc_pos, itoc_size, itoc_enc = read_frame(data, itoc_off)
    itoc = UTF(itoc_blob)

    subs = {}
    files = {}  # id -> {'size','xsize'}
    for name in ('DataL', 'DataH'):
        off, size = itoc.value(0, name) if itoc.has(name) else (0, 0)
        if not size:
            continue
        sub_abs = itoc.base + itoc.data_off + off
        sub = UTF(bytes(itoc.blob[sub_abs:sub_abs + size]))
        subs[name] = sub
        for r in range(sub.nrows):
            fid = sub.value(r, 'ID')
            fs = sub.value(r, 'FileSize')
            xs = sub.value(r, 'ExtractSize') if sub.has('ExtractSize') else fs
            files[fid] = {'size': fs, 'xsize': xs}
    assert 'DataL' in subs and 'DataH' in subs, 'need both DataL and DataH schemas'

    # --- original layout ---
    ids = sorted(files)
    pos = content_off
    for fid in ids:
        pos = align_up(pos, align)
        files[fid]['offset'] = pos
        pos += files[fid]['size']
    content_end = pos
    tail = bytes(data[content_end:])
    if tail.strip(b'\x00'):
        raise SystemExit(f'unexpected {len(tail)} non-zero bytes after content end {content_end:#x}')

    # --- new sizes ---
    for fid in ids:
        info = files[fid]
        if fid in repl:
            info['new_size'] = info['new_xsize'] = len(repl[fid])
            print(f'ID {fid}: {info["size"]}/{info["xsize"]} -> {len(repl[fid])} (stored raw)')
        else:
            info['new_size'], info['new_xsize'] = info['size'], info['xsize']

    # --- rebuild ITOC: re-partition DataL / DataH ---
    rows_l, rows_h = [], []
    for fid in ids:
        info = files[fid]
        if max(info['new_size'], info['new_xsize']) <= 0xFFFF:
            rows_l.append({'ID': fid, 'FileSize': info['new_size'], 'ExtractSize': info['new_xsize']})
        else:
            rows_h.append({'ID': fid, 'FileSize': info['new_size'], 'ExtractSize': info['new_xsize']})
    sub_l = subs['DataL'].rebuild_rows(rows_l)
    sub_h = subs['DataH'].rebuild_rows(rows_h)
    pad_l = align_up(len(sub_l), 8) - len(sub_l)
    new_data_section = sub_l + b'\x00' * pad_l + sub_h
    itoc.set(0, 'FilesL', len(rows_l))
    itoc.set(0, 'FilesH', len(rows_h))
    itoc.set(0, 'DataL', (0, len(sub_l)))
    itoc.set(0, 'DataH', (len(sub_l) + pad_l, len(sub_h)))
    # splice new data section into the ITOC blob
    itoc_content = bytearray(itoc.blob[itoc.base:itoc.base + itoc.data_off]) + new_data_section
    new_itoc_blob = b'@UTF' + struct.pack('>L', len(itoc_content)) + bytes(itoc_content)
    print(f'ITOC: DataL {subs["DataL"].nrows}->{len(rows_l)} rows, '
          f'DataH {subs["DataH"].nrows}->{len(rows_h)} rows, '
          f'blob {len(itoc_blob)}->{len(new_itoc_blob)} bytes')

    # --- place ITOC and content ---
    new_itoc_end = itoc_pos + len(new_itoc_blob)
    new_content_off = max(content_off, align_up(new_itoc_end, 0x10))
    if new_content_off != content_off:
        print(f'ContentOffset: {content_off:#x} -> {new_content_off:#x}')

    # --- new content ---
    out_content = bytearray()
    for fid in ids:
        pad = align_up(new_content_off + len(out_content), align) - (new_content_off + len(out_content))
        out_content += b'\x00' * pad
        info = files[fid]
        if fid in repl:
            out_content += repl[fid]
        else:
            out_content += data[info['offset']:info['offset'] + info['size']]

    # --- header fields ---
    new_total = sum(files[f]['new_size'] for f in ids)
    new_xtotal = sum(files[f]['new_xsize'] for f in ids)
    old_itoc_size_field = hdr.value(0, 'ItocSize') if hdr.has('ItocSize') else 0
    updates = [('EnabledPackedSize', new_total), ('EnabledDataSize', new_xtotal),
               ('ContentSize', len(out_content)), ('ContentOffset', new_content_off)]
    if old_itoc_size_field:
        updates.append(('ItocSize', old_itoc_size_field + len(new_itoc_blob) - itoc_size))
    for field, val in updates:
        if hdr.has(field):
            try:
                hdr.set(0, field, val)
            except KeyError as e:
                print(f'header {field}: skipped ({e})')

    # --- assemble ---
    out = bytearray(data[:itoc_pos - 16])
    blob = bytes(hdr.blob)
    out[hdr_pos:hdr_pos + hdr_size] = xor_crypt(blob) if hdr_enc else blob
    # ITOC frame: magic(4) 'ITOC', 0xff pad(4), size(4 LE), pad(4)
    frame = bytes(data[itoc_off:itoc_off + 8]) + struct.pack('<L', len(new_itoc_blob)) + bytes(data[itoc_off + 12:itoc_off + 16])
    out += frame
    out += xor_crypt(new_itoc_blob) if itoc_enc else new_itoc_blob
    out += b'\x00' * (new_content_off - len(out))
    out += out_content
    open(out_path, 'wb').write(out)
    print(f'OK: {out_path} ({len(out)} bytes, content @ {new_content_off:#x})')


if __name__ == '__main__':
    main()
