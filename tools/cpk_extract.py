#!/usr/bin/env python3
"""
CPK archive extractor with CRILAYLA decompression support.
Handles CRI Middleware CPK archives (TOC and ITOC formats).

Usage: python cpk_extract.py input.cpk output_dir
"""

import struct
import os
import sys
from io import BytesIO


# --- @UTF Table Constants ---

COLUMN_STORAGE_MASK       = 0xF0
COLUMN_STORAGE_PERROW     = 0x50
COLUMN_STORAGE_CONSTANT   = 0x30
COLUMN_STORAGE_ZERO       = 0x10

COLUMN_TYPE_MASK          = 0x0F
COLUMN_TYPE_DATA          = 0x0B
COLUMN_TYPE_STRING        = 0x0A
COLUMN_TYPE_FLOAT         = 0x08
COLUMN_TYPE_8BYTE2        = 0x07
COLUMN_TYPE_8BYTE         = 0x06
COLUMN_TYPE_4BYTE2        = 0x05
COLUMN_TYPE_4BYTE         = 0x04
COLUMN_TYPE_2BYTE2        = 0x03
COLUMN_TYPE_2BYTE         = 0x02
COLUMN_TYPE_1BYTE2        = 0x01
COLUMN_TYPE_1BYTE         = 0x00

COLUMN_TYPE_FORMATS = {
    COLUMN_TYPE_DATA:    '>LL',
    COLUMN_TYPE_STRING:  '>L',
    COLUMN_TYPE_FLOAT:   '>f',
    COLUMN_TYPE_8BYTE2:  '>q',
    COLUMN_TYPE_8BYTE:   '>Q',
    COLUMN_TYPE_4BYTE2:  '>l',
    COLUMN_TYPE_4BYTE:   '>L',
    COLUMN_TYPE_2BYTE2:  '>h',
    COLUMN_TYPE_2BYTE:   '>H',
    COLUMN_TYPE_1BYTE2:  '>b',
    COLUMN_TYPE_1BYTE:   '>B',
}


def utf_decrypt(data: bytes) -> bytes:
    """Decrypt XOR-encrypted @UTF table data."""
    c, m = 0x5F, 0x15
    result = bytearray(data)
    for i in range(len(result)):
        result[i] ^= (c & 0xFF)
        c = (c * m) & 0xFF
    return bytes(result)


class UTFTable:
    """Parser for CRI @UTF tables."""

    def __init__(self, data: bytes):
        if data[:4] == b'\x1F\x9E\xF3\xF5':
            data = utf_decrypt(data)

        f = BytesIO(data)
        marker = f.read(4)
        if marker != b'@UTF':
            raise ValueError(f"Expected @UTF marker, got {marker!r}")

        table_size, = struct.unpack('>L', f.read(4))
        self.table_content = f.read(table_size)
        self._full_data = data  # keep for sub-table extraction

        tc = self.table_content
        tf = BytesIO(tc)

        (
            self.rows_offset,
            self.string_table_offset,
            self.data_offset,
            table_name_offset,
            self.column_count,
            self.row_width,
            self.row_count,
        ) = struct.unpack('>LLLLHHL', tf.read(0x18))

        self.table_name = self._read_string(table_name_offset)

        # Read column schema
        self.columns = []
        self.col_names = {}

        for i in range(self.column_count):
            type_id, name_offset = struct.unpack('>BL', tf.read(5))
            name = self._read_string(name_offset)
            storage = type_id & COLUMN_STORAGE_MASK
            field_type = type_id & COLUMN_TYPE_MASK

            constant_value = None
            if storage == COLUMN_STORAGE_CONSTANT:
                fmt = COLUMN_TYPE_FORMATS[field_type]
                size = struct.calcsize(fmt)
                raw = struct.unpack(fmt, tf.read(size))
                if field_type == COLUMN_TYPE_STRING:
                    constant_value = self._read_string(raw[0])
                elif field_type == COLUMN_TYPE_DATA:
                    constant_value = raw  # (offset, size) tuple
                elif len(raw) == 1:
                    constant_value = raw[0]
                else:
                    constant_value = raw

            col = {
                'type_id': type_id,
                'name': name,
                'storage': storage,
                'field_type': field_type,
                'constant': constant_value,
            }
            self.columns.append(col)
            self.col_names[name] = i

        # Read rows
        self.rows = []
        tf.seek(self.rows_offset)

        for _ in range(self.row_count):
            row = {}
            for col in self.columns:
                name = col['name']
                storage = col['storage']
                field_type = col['field_type']

                if storage == COLUMN_STORAGE_ZERO:
                    row[name] = "" if field_type == COLUMN_TYPE_STRING else 0
                elif storage == COLUMN_STORAGE_CONSTANT:
                    row[name] = col['constant']
                elif storage == COLUMN_STORAGE_PERROW:
                    fmt = COLUMN_TYPE_FORMATS[field_type]
                    size = struct.calcsize(fmt)
                    raw = struct.unpack(fmt, tf.read(size))
                    if field_type == COLUMN_TYPE_STRING:
                        row[name] = self._read_string(raw[0])
                    elif field_type == COLUMN_TYPE_DATA:
                        # Store as (offset_in_data_section, size)
                        row[name] = raw
                    elif len(raw) == 1:
                        row[name] = raw[0]
                    else:
                        row[name] = raw
                else:
                    row[name] = 0

            self.rows.append(row)

    def _read_string(self, offset: int) -> str:
        start = self.string_table_offset + offset
        end = start
        tc = self.table_content
        while end < len(tc) and tc[end] != 0:
            end += 1
        return tc[start:end].decode('utf-8', errors='replace')

    def get(self, key: str, row: int = 0):
        return self.rows[row][key]

    def get_data_bytes(self, key: str, row: int = 0) -> bytes:
        """Get raw bytes for a DATA-type column value."""
        offset, size = self.rows[row][key]
        abs_offset = self.data_offset + offset
        return self.table_content[abs_offset:abs_offset + size]

    def has(self, key: str) -> bool:
        return key in self.col_names


def read_utf_at(f, offset: int) -> UTFTable:
    """Read a @UTF table from a file at the given offset (after the frame header)."""
    f.seek(offset)
    frame_magic = f.read(4)  # e.g. "CPK ", "TOC ", "ITOC", "ETOC"
    f.read(4)  # 0xFF padding
    utf_size, = struct.unpack('<L', f.read(4))
    f.read(4)  # padding
    utf_data = f.read(utf_size)
    return UTFTable(utf_data)


# --- CRILAYLA Decompression ---

def decompress_crilayla(data: bytes) -> bytes:
    """
    Decompress CRILAYLA compressed data.

    Format:
      [0x00..0x07] "CRILAYLA" magic
      [0x08..0x0B] uncompressed data size (LE uint32)
      [0x0C..0x0F] compressed data size (LE uint32)
      [0x10..0x10+comp_size] compressed bitstream (read in reverse byte order)
      [0x10+comp_size..+0x100] raw header (prepended to decompressed output)
    """
    if data[:8] != b'CRILAYLA':
        raise ValueError(f"Not CRILAYLA data: {data[:8]!r}")

    uncomp_size, comp_size = struct.unpack('<LL', data[8:16])
    compressed = data[0x10:0x10 + comp_size]
    raw_header = data[0x10 + comp_size:0x10 + comp_size + 0x100]

    # Build bit array from reversed compressed bytes
    reversed_bytes = compressed[::-1]
    bits = bytearray()
    for b in reversed_bytes:
        for shift in range(7, -1, -1):
            bits.append((b >> shift) & 1)

    bit_pos = 0
    total_bits = len(bits)

    def read_bits(n):
        nonlocal bit_pos
        if bit_pos + n > total_bits:
            return -1
        val = 0
        for i in range(n):
            val = (val << 1) | bits[bit_pos]
            bit_pos += 1
        return val

    result = bytearray()

    while len(result) < uncomp_size:
        if bit_pos >= total_bits:
            break

        flag = read_bits(1)
        if flag < 0:
            break

        if flag:
            # Back-reference
            offset = read_bits(13) + 3
            ref_count = 3

            for level in _deflate_levels():
                extra = read_bits(level)
                if extra < 0:
                    break
                ref_count += extra
                if extra < (1 << level) - 1:
                    break

            for _ in range(ref_count):
                if len(result) >= uncomp_size:
                    break
                result.append(result[-offset])
        else:
            byte_val = read_bits(8)
            if byte_val < 0:
                break
            result.append(byte_val)

    # Output is built in reverse
    result = bytes(result[:uncomp_size][::-1])
    return raw_header + result


def _deflate_levels():
    for v in [2, 3, 5, 8]:
        yield v
    while True:
        yield 8


# --- CPK Archive ---

class CPKArchive:
    """Parser and extractor for CRI CPK archives."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.f = open(filepath, 'rb')
        self.entries = []
        self._parse()

    def _parse(self):
        f = self.f

        # Read CPK header
        cpk_utf = read_utf_at(f, 0)

        self.content_offset = cpk_utf.get('ContentOffset')
        self.toc_offset = cpk_utf.get('TocOffset') if cpk_utf.has('TocOffset') else 0
        self.itoc_offset = cpk_utf.get('ItocOffset') if cpk_utf.has('ItocOffset') else 0
        self.etoc_offset = cpk_utf.get('EtocOffset') if cpk_utf.has('EtocOffset') else 0
        self.file_count = cpk_utf.get('Files') if cpk_utf.has('Files') else 0
        self.align = cpk_utf.get('Align') if cpk_utf.has('Align') else 0

        # Parse TOC (named files with directories)
        if self.toc_offset:
            self._parse_toc()
        # Parse ITOC (index-based, sequential files)
        elif self.itoc_offset:
            self._parse_itoc()

    def _parse_toc(self):
        """Parse standard TOC with DirName/FileName/FileOffset entries."""
        toc_utf = read_utf_at(self.f, self.toc_offset)

        # Base offset for file data
        base = min(self.toc_offset, self.content_offset) if self.content_offset else self.toc_offset

        for i in range(toc_utf.row_count):
            row = toc_utf.rows[i]
            dir_name = row.get('DirName', '')
            file_name = row.get('FileName', f'{i:08d}.dat')
            file_size = row.get('FileSize', 0)
            extract_size = row.get('ExtractSize', 0)
            file_offset = row.get('FileOffset', 0)

            abs_offset = file_offset + base
            if self.align and (abs_offset % self.align):
                abs_offset += self.align - (abs_offset % self.align)

            self.entries.append({
                'dir_name': dir_name,
                'file_name': file_name,
                'file_size': file_size,
                'extract_size': extract_size,
                'offset': abs_offset,
                'id': row.get('ID', i),
            })

    def _parse_itoc(self):
        """Parse ITOC (index-based TOC) with DataL/DataH sub-tables."""
        itoc_utf = read_utf_at(self.f, self.itoc_offset)

        # Collect file entries from DataL and DataH sub-tables
        file_map = {}  # id -> {file_size, extract_size}

        for sub_key in ('DataL', 'DataH'):
            if not itoc_utf.has(sub_key):
                continue
            sub_data = itoc_utf.get_data_bytes(sub_key)
            if not sub_data:
                continue
            sub_utf = UTFTable(sub_data)
            for i in range(sub_utf.row_count):
                row = sub_utf.rows[i]
                fid = row.get('ID', i)
                file_map[fid] = {
                    'file_size': row.get('FileSize', 0),
                    'extract_size': row.get('ExtractSize', 0),
                }

        # Files are laid out sequentially from content_offset, ordered by ID
        # Each file is aligned to self.align
        content_start = self.content_offset

        sorted_ids = sorted(file_map.keys())
        current_offset = content_start

        for fid in sorted_ids:
            info = file_map[fid]
            file_size = info['file_size']
            extract_size = info['extract_size']

            # Align current offset
            if self.align and (current_offset % self.align):
                current_offset += self.align - (current_offset % self.align)

            self.entries.append({
                'dir_name': '',
                'file_name': f'{fid:08d}.dat',
                'file_size': file_size,
                'extract_size': extract_size,
                'offset': current_offset,
                'id': fid,
            })

            current_offset += file_size

    def extract_all(self, output_dir: str):
        """Extract all files from the CPK archive to output_dir."""
        os.makedirs(output_dir, exist_ok=True)

        total = len(self.entries)
        for i, entry in enumerate(self.entries):
            dir_name = entry['dir_name']
            file_name = entry['file_name']
            file_size = entry['file_size']
            extract_size = entry['extract_size']
            offset = entry['offset']

            if dir_name:
                out_dir = os.path.join(output_dir, dir_name)
            else:
                out_dir = output_dir
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, file_name)

            self.f.seek(offset)
            raw_data = self.f.read(file_size)

            compressed = extract_size > file_size and file_size > 0
            status = "CRILAYLA" if compressed else "raw"

            print(f"  [{i+1}/{total}] {file_name}  "
                  f"size={file_size}  extract={extract_size}  offset={offset:#x}  ({status})")

            if compressed:
                try:
                    data = decompress_crilayla(raw_data)
                    data = data[:extract_size]
                except Exception as e:
                    print(f"    ERROR decompressing: {e}", file=sys.stderr)
                    data = raw_data
            else:
                data = raw_data

            with open(out_path, 'wb') as out_f:
                out_f.write(data)

        print(f"\nExtracted {total} files to {output_dir}")

    def close(self):
        self.f.close()


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.cpk> <output_dir>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Opening {input_path}...")
    cpk = CPKArchive(input_path)
    print(f"Found {len(cpk.entries)} entries")

    cpk.extract_all(output_dir)
    cpk.close()


if __name__ == '__main__':
    main()
