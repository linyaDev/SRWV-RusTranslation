#!/usr/bin/env python3
"""
Append-патчер для TOC-based CPK (SRW V, напр. BTLC/*/OP_PC.CPK).

Заменяемые файлы дописываются в конец архива (raw, без сжатия), а в TOC
правятся FileOffset/FileSize на месте. ExtractSize с constant-storage не
трогается — замена обязана распаковываться ровно в тот же размер.

Usage: ru_cpk_patch_toc.py input.cpk output.cpk NAME=newfile [NAME=newfile ...]
       NAME — имя файла внутри CPK (FileName из TOC).
"""
import struct
import sys

sys.path.insert(0, __file__.rsplit('\\', 1)[0] if '\\' in __file__ else '.')
from ru_cpk_patch import read_frame, UTF, xor_crypt, align_up  # noqa: E402


def main():
    in_path, out_path = sys.argv[1], sys.argv[2]
    repl = {}
    for arg in sys.argv[3:]:
        name, path = arg.split('=', 1)
        repl[name] = open(path, 'rb').read()

    data = bytearray(open(in_path, 'rb').read())

    hdr_blob, hdr_pos, hdr_size, hdr_enc = read_frame(data, 0)
    hdr = UTF(hdr_blob)
    toc_off = hdr.value(0, 'TocOffset')
    content_off = hdr.value(0, 'ContentOffset')
    assert toc_off, 'no TOC in this CPK'
    base = min(toc_off, content_off) if content_off else toc_off

    toc_blob, toc_pos, toc_size, toc_enc = read_frame(data, toc_off)
    toc = UTF(toc_blob)

    append_at = align_up(len(data), 16)
    out = bytearray(data) + b'\x00' * (append_at - len(data))
    done = set()
    for r in range(toc.nrows):
        fname = toc._str(toc.value(r, 'FileName'))
        if fname not in repl:
            continue
        newbytes = repl[fname]
        xsize = toc.value(r, 'ExtractSize')
        assert len(newbytes) == xsize, \
            f'{fname}: new size {len(newbytes)} != ExtractSize {xsize} (raw must match)'
        toc.set(r, 'FileSize', len(newbytes))
        toc.set(r, 'FileOffset', len(out) - base)
        out += newbytes
        out += b'\x00' * (align_up(len(out), 16) - len(out))
        done.add(fname)
        print(f'{fname}: appended at {len(out) - len(newbytes):#x}, size {len(newbytes)}')

    missing = set(repl) - done
    if missing:
        raise SystemExit(f'not found in TOC: {missing}')

    blob = bytes(toc.blob)
    out[toc_pos:toc_pos + toc_size] = xor_crypt(blob) if toc_enc else blob
    open(out_path, 'wb').write(out)
    print(f'OK: {out_path} ({len(out)} bytes, {len(done)} replaced)')


if __name__ == '__main__':
    main()
