#!/usr/bin/env python3
"""
In-place patcher for ITOC-based CPK archives (SRW V).

Replaces file data by ID, stores replacements uncompressed, fixes
FileSize/ExtractSize in the ITOC DataL/DataH sub-tables and the stats
fields in the CPK header. Layout matches the game's reader: files laid
out sequentially from ContentOffset, each aligned to the CPK Align value.

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
    """Parses a @UTF blob and records the absolute byte offset of every value."""

    def __init__(self, blob: bytes):
        assert blob[:4] == b'@UTF', blob[:4]
        self.blob = bytearray(blob)
        (self.rows_off, self.str_off, self.data_off, name_off,
         self.ncols, self.row_width, self.nrows) = struct.unpack_from('>LLLLHHL', blob, 8)
        self.base = 8  # table_content starts after '@UTF' + size
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

    def _str(self, off):
        start = self.base + self.str_off + off
        end = self.blob.index(b'\x00', start)
        return self.blob[start:end].decode('utf-8')

    def locate(self, row: int, colname: str):
        """Return (abs_offset_in_blob, fmt) of the value for row/col."""
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

    def set(self, row: int, colname: str, value: int):
        off, fmt = self.locate(row, colname)
        struct.pack_into(fmt, self.blob, off, value)

    def has(self, colname: str):
        return any(c['name'] == colname for c in self.columns)


def read_frame(data: bytes, offset: int):
    """Read a CPK frame (CPK /ITOC/...) -> (utf_blob_plain, utf_pos, utf_size, was_encrypted)."""
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

    subs = {}   # name -> (UTF, abs_offset_of_sub_blob_within_itoc_blob)
    files = {}  # id -> {'size':, 'xsize':, 'sub':, 'row':}
    for name in ('DataL', 'DataH'):
        if not itoc.has(name):
            continue
        off, size = itoc.value(0, name)
        if not size:
            continue
        sub_abs = itoc.base + itoc.data_off + off
        sub = UTF(bytes(itoc.blob[sub_abs:sub_abs + size]))
        subs[name] = (sub, sub_abs)
        for r in range(sub.nrows):
            fid = sub.value(r, 'ID')
            files[fid] = {'size': sub.value(r, 'FileSize'),
                          'xsize': sub.value(r, 'ExtractSize') if sub.has('ExtractSize') else sub.value(r, 'FileSize'),
                          'sub': name, 'row': r}

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

    # --- build new content, patch sizes ---
    out_content = bytearray()
    for fid in ids:
        pad = align_up(content_off + len(out_content), align) - (content_off + len(out_content))
        out_content += b'\x00' * pad
        info = files[fid]
        if fid in repl:
            newbytes = repl[fid]
            sub, sub_abs = subs[info['sub']]
            fmt = sub.locate(info['row'], 'FileSize')[1]
            limit = 2 ** (8 * struct.calcsize(fmt)) - 1
            assert len(newbytes) <= limit, f'ID {fid}: {len(newbytes)} exceeds {info["sub"]} field width'
            sub.set(info['row'], 'FileSize', len(newbytes))
            if sub.has('ExtractSize'):
                sub.set(info['row'], 'ExtractSize', len(newbytes))
            print(f'ID {fid}: {info["size"]}/{info["xsize"]} -> {len(newbytes)} (stored raw)')
            out_content += newbytes
        else:
            out_content += data[info['offset']:info['offset'] + info['size']]

    # write patched sub-tables back into the ITOC blob
    for name, (sub, sub_abs) in subs.items():
        itoc.blob[sub_abs:sub_abs + len(sub.blob)] = sub.blob

    # --- header stats (best effort, same field widths) ---
    new_total = sum(len(repl[f]) if f in repl else files[f]['size'] for f in ids)
    new_xtotal = sum(len(repl[f]) if f in repl else files[f]['xsize'] for f in ids)
    for field, val in (('EnabledPackedSize', new_total), ('EnabledDataSize', new_xtotal),
                       ('ContentSize', len(out_content))):
        if hdr.has(field):
            try:
                hdr.set(0, field, val)
                print(f'header {field} = {val}')
            except KeyError as e:
                print(f'header {field}: skipped ({e})')

    # --- assemble ---
    out = bytearray(data[:content_off])
    blob = bytes(hdr.blob)
    out[hdr_pos:hdr_pos + hdr_size] = xor_crypt(blob) if hdr_enc else blob
    blob = bytes(itoc.blob)
    out[itoc_pos:itoc_pos + itoc_size] = xor_crypt(blob) if itoc_enc else blob
    out += out_content
    open(out_path, 'wb').write(out)
    print(f'OK: {out_path} ({len(out)} bytes, content @ {content_off:#x})')


if __name__ == '__main__':
    main()
