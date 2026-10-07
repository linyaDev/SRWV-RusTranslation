#!/usr/bin/env python
"""
BLTU (Binary Lookup Table) parser for Super Robot Wars V.

Format:
  Header (48 bytes / 0x30):
    0x00  4B  magic         "BLTU"
    0x04  4B  language       e.g. "EN\0\0", "\0\0\0\0"
    0x08  4B  version        uint32 LE (always 1)
    0x0C 12B  reserved       3x uint32 LE (zeros)
    0x18  4B  strings_offset uint32 LE - offset to null-terminated UTF-8 string blob
    0x1C  4B  strings_size   uint32 LE - size of string blob in bytes
    0x20  4B  index_offset   uint32 LE - offset to string offset table
    0x24  4B  index_count    uint32 LE - number of entries in string offset table
    0x28  4B  records_offset uint32 LE - offset to entry records
    0x2C  4B  record_count   uint32 LE - number of entry records

  String blob (at strings_offset, strings_size bytes):
    Consecutive null-terminated UTF-8 strings.
    Contains both key names and value strings.

  String offset table (at index_offset, index_count * 4 bytes):
    Array of uint32 LE offsets into the string blob.
    First record_count entries are keys, remaining are values.

  Entry records (at records_offset, record_count * 32 bytes):
    Each record is 32 bytes (8 x uint32 LE):
      [0] key_string_index     - index into string offset table for the key name
      [1] value_count          - number of value strings for this key
      [2] first_value_index    - index into string offset table for the first value
      [3] extra_field_1        - unknown (usually 0)
      [4] extra_field_2        - unknown (usually 0)
      [5] extra_field_3        - unknown (usually 0)
      [6] reserved_1           - always 0
      [7] reserved_2           - always 0

  Sections are padded with null bytes to 8-byte alignment.

Usage:
  python bltu_parser.py extract input.dat output.json
  python bltu_parser.py rebuild original.dat translated.json output.dat
"""

import struct
import json
import sys
import os

HEADER_SIZE = 0x30
RECORD_SIZE = 32
MAGIC = b"BLTU"


def align8(offset):
    """Round up to next 8-byte boundary."""
    return (offset + 7) & ~7


def read_cstring(blob, offset):
    """Read a null-terminated UTF-8 string from blob at offset."""
    end = blob.index(b"\x00", offset)
    return blob[offset:end].decode("utf-8")


def parse_bltu(filepath):
    """Parse a BLTU file and return its structured contents."""
    with open(filepath, "rb") as f:
        data = f.read()

    # -- Header --
    magic = data[0:4]
    if magic != MAGIC:
        raise ValueError(f"Bad magic: {magic!r}, expected {MAGIC!r}")

    lang = data[4:8]
    version = struct.unpack_from("<I", data, 0x08)[0]
    reserved = struct.unpack_from("<3I", data, 0x0C)

    strings_offset = struct.unpack_from("<I", data, 0x18)[0]
    strings_size = struct.unpack_from("<I", data, 0x1C)[0]
    index_offset = struct.unpack_from("<I", data, 0x20)[0]
    index_count = struct.unpack_from("<I", data, 0x24)[0]
    records_offset = struct.unpack_from("<I", data, 0x28)[0]
    record_count = struct.unpack_from("<I", data, 0x2C)[0]

    # -- String blob --
    strings_blob = data[strings_offset : strings_offset + strings_size]

    # -- String offset table --
    string_offsets = []
    for i in range(index_count):
        off = struct.unpack_from("<I", data, index_offset + i * 4)[0]
        string_offsets.append(off)

    # -- Read all strings --
    strings = []
    for off in string_offsets:
        s = read_cstring(strings_blob, off)
        strings.append(s)

    # -- Entry records --
    records = []
    for i in range(record_count):
        base = records_offset + i * RECORD_SIZE
        fields = struct.unpack_from("<8I", data, base)
        records.append(fields)

    return {
        "lang": lang,
        "version": version,
        "reserved": reserved,
        "strings_offset": strings_offset,
        "strings_size": strings_size,
        "index_offset": index_offset,
        "index_count": index_count,
        "records_offset": records_offset,
        "record_count": record_count,
        "string_offsets": string_offsets,
        "strings": strings,
        "records": records,
        "raw_data": data,
    }


def extract(input_path, output_path):
    """Extract all key-value pairs to JSON."""
    parsed = parse_bltu(input_path)
    strings = parsed["strings"]
    records = parsed["records"]
    record_count = parsed["record_count"]

    entries = []
    for rec in records:
        key_idx, val_count, first_val_idx, ef1, ef2, ef3, r1, r2 = rec
        key = strings[key_idx]

        values = []
        for vi in range(val_count):
            values.append(strings[first_val_idx + vi])

        entry = {"key": key, "values": values}

        # Preserve non-zero extra fields so rebuild is lossless
        if ef1 != 0 or ef2 != 0 or ef3 != 0:
            entry["extra"] = [ef1, ef2, ef3]

        entries.append(entry)

    # Also store language tag for rebuild
    lang_bytes = parsed["lang"]
    lang_str = lang_bytes.rstrip(b"\x00").decode("ascii", errors="replace")

    output = {
        "_format": "BLTU",
        "_language": lang_str,
        "_version": parsed["version"],
        "_reserved": list(parsed["reserved"]),
        "_entry_count": len(entries),
        "entries": entries,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(entries)} entries ({sum(len(e['values']) for e in entries)} value strings) to {output_path}")


def rebuild(original_path, json_path, output_path):
    """Rebuild a BLTU file from original + translated JSON."""
    # Parse original to get exact binary layout info
    orig = parse_bltu(original_path)

    with open(json_path, "r", encoding="utf-8") as f:
        translated = json.load(f)

    entries = translated["entries"]
    record_count = len(entries)

    # Determine language bytes
    lang_str = translated.get("_language", "")
    lang_bytes = lang_str.encode("ascii")
    # Pad to 4 bytes
    lang_bytes = lang_bytes.ljust(4, b"\x00")[:4]

    version = translated.get("_version", 1)
    reserved = tuple(translated.get("_reserved", [0, 0, 0]))

    # --- Build string blob and offset table ---
    # Order: first all key strings (one per record), then all value strings
    all_strings = []  # (string, is_key, record_index, value_index_within_record)

    # Keys first
    for i, entry in enumerate(entries):
        all_strings.append(entry["key"])

    # Then values
    for i, entry in enumerate(entries):
        for val in entry["values"]:
            all_strings.append(val)

    # Build the blob: each string is null-terminated UTF-8
    string_offsets = []
    blob_parts = []
    current_offset = 0
    for s in all_strings:
        string_offsets.append(current_offset)
        encoded = s.encode("utf-8") + b"\x00"
        blob_parts.append(encoded)
        current_offset += len(encoded)

    strings_blob = b"".join(blob_parts)
    strings_size = len(strings_blob)

    # --- Calculate section offsets ---
    strings_offset = HEADER_SIZE  # 0x30

    # Pad strings blob to 4-byte alignment
    strings_blob_padded = strings_blob + b"\x00" * (align8(len(strings_blob)) - len(strings_blob))

    index_offset = strings_offset + len(strings_blob_padded)
    index_count = len(string_offsets)

    # Index table
    index_data = struct.pack(f"<{index_count}I", *string_offsets)
    index_data_padded = index_data + b"\x00" * (align8(len(index_data)) - len(index_data))

    records_offset = index_offset + len(index_data_padded)

    # --- Build entry records ---
    records_data = bytearray()
    value_cursor = record_count  # Values start after all keys in the string table

    for i, entry in enumerate(entries):
        key_string_index = i  # Key i is at string_offsets[i]
        val_count = len(entry["values"])
        first_val_index = value_cursor

        extra = entry.get("extra", [0, 0, 0])
        ef1 = extra[0] if len(extra) > 0 else 0
        ef2 = extra[1] if len(extra) > 1 else 0
        ef3 = extra[2] if len(extra) > 2 else 0

        rec = struct.pack("<8I", key_string_index, val_count, first_val_index, ef1, ef2, ef3, 0, 0)
        records_data.extend(rec)
        value_cursor += val_count

    # --- Assemble the file ---
    header = bytearray(HEADER_SIZE)
    header[0:4] = MAGIC
    header[4:8] = lang_bytes
    struct.pack_into("<I", header, 0x08, version)
    struct.pack_into("<3I", header, 0x0C, *reserved)
    struct.pack_into("<I", header, 0x18, strings_offset)
    struct.pack_into("<I", header, 0x1C, strings_size)
    struct.pack_into("<I", header, 0x20, index_offset)
    struct.pack_into("<I", header, 0x24, index_count)
    struct.pack_into("<I", header, 0x28, records_offset)
    struct.pack_into("<I", header, 0x2C, record_count)

    output_data = bytes(header) + strings_blob_padded + index_data_padded + bytes(records_data)

    with open(output_path, "wb") as f:
        f.write(output_data)

    print(f"Rebuilt {record_count} entries ({value_cursor - record_count} value strings) -> {output_path}")
    print(f"Output size: {len(output_data)} bytes")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Commands:")
        print("  extract <input.dat> <output.json>")
        print("  rebuild <original.dat> <translated.json> <output.dat>")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "extract":
        if len(sys.argv) != 4:
            print("Usage: bltu_parser.py extract <input.dat> <output.json>")
            sys.exit(1)
        extract(sys.argv[2], sys.argv[3])

    elif cmd == "rebuild":
        if len(sys.argv) != 5:
            print("Usage: bltu_parser.py rebuild <original.dat> <translated.json> <output.dat>")
            sys.exit(1)
        rebuild(sys.argv[2], sys.argv[3], sys.argv[4])

    else:
        print(f"Unknown command: {cmd}")
        print("Use 'extract' or 'rebuild'")
        sys.exit(1)


if __name__ == "__main__":
    main()
