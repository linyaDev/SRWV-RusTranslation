# The `<mt>` container (Super Robot Wars V)

Reverse-engineered from the decrypted payloads of `rpw_jstr.cpk`, `lega_zkn.cpk`
and `rpw_data`, plus the two loose authoring-tool `.bin` files shipped in
`CommonData/MtData/EN/`. Tooling: `_tools/ru_mt_jstr.py`.

All integers are little-endian. All offsets below are absolute file offsets
unless stated otherwise.

Pipeline to reach an `<mt>` file:

```
python _tools/cpk_extract.py   <x.cpk> <dir>        # CRI CPK -> 000000NN.dat
python _tools/srwv_decrypt.py  <dir>   <dir>_dec    # Blowfish-BE, key "SRVW Steam Game"
python _tools/ru_mt_jstr.py    probe   <dir>_dec    # identify container type
```

---

## 1. File layout

```
+0x00  header            40 bytes (0x28)
+0x28  chunk record 0    variable
       chunk record 1
       ...
       chunk record N-1
       file footer record
       (EOF)
```

There is no chunk count and no chunk directory: the reader walks the chain by
adding each record's size field, and stops when the 12-byte tag at the current
offset is `<file--foot>` instead of `<chunk-head>`.

### 1.1 Header (0x28 bytes)

| off | size | content |
|-----|------|---------|
| 0x00 | 8 | `"<mt>\0\0\0\0"` magic |
| 0x08 | 8 | producer tag, NUL-padded — `"prod#1"` (shipped) or `"z3of1"` (authoring tool) |
| 0x10 | 8 | data-set tag, NUL-padded — `"data#1"` or `"rpw-all"` |
| 0x18 | 8 | version string, NUL-padded — `"1.00"` |
| 0x20 | 4 | **A** = `file_footer_offset + file_footer_recsize` |
| 0x24 | 4 | **B** = `file_footer_offset - 0x28`, i.e. total size of the chunk area |

`B` equals the sum of all chunk record sizes. `A` is the end of the file footer
record; the shipped files then have 4 more zero bytes, so `A == filesize - 4`
there, while the authoring-tool `.bin` files have `A == filesize`. Treat `A`
purely as `footer_offset + recsize`, never as a function of file size.

### 1.2 Chunk record

```
off (rel. to chunk start)
 +0x00  12   "<chunk-head>"
 +0x0C   4   0
 +0x10   8   chunk name, ASCII, NUL-padded to 8 bytes
 +0x18   4   C = size of this whole record (== offset of the next <chunk-head>)
 +0x1C   4   D = payload size in bytes
 +0x20   D   payload
 +0x20+D 12  "<chunk-foot>"
        +4   0
        +4   R = size of the footer part, from "<chunk-foot>" to the next record
        +4   0
        +k   0x2A ('*') padding, k = 0..7
        12   "<endofchunk>"
         4   0
```

Derived rules, all verified byte-exactly against every known file:

* `payload_start = chunk_start + 0x20`
* `foot = payload_start + D` (the footer is **not** aligned)
* `k = align8(foot + 24) - (foot + 24)` — i.e. `<endofchunk>` always lands on an
  8-byte boundary, and the gap between the footer's three u32 fields and
  `<endofchunk>` is filled with `'*'`
* `R = 12 + 12 + k + 16 = 40 + k`
* `C = (foot + R) - chunk_start`
* the next `<chunk-head>` (or the `<file--foot>`) sits at `chunk_start + C`,
  which is always 8-byte aligned

So the only free parameter is `D`; everything else follows.

### 1.3 File footer record

```
 +0x00  12   "<file--foot>"
 +0x0C   4   0
 +0x10   4   R_file  (0x28 in the shipped files)
 +0x14   4   0
 +0x18   ..  optional producer blob (build date string in the .bin files)
        ..   '*' padding
        12   "<end-of-mt>."     (appears as "****<end-of-mt>." when k = 4)
         4   0
```

In the shipped CPK files this is exactly 44 bytes: tag, `0`, `0x28`, `0`,
`"****<end-of-mt>."`, `0`. The authoring-tool `.bin` files put a build
timestamp between the u32 fields and the `'*'` run, which makes the record much
longer (0xC4 bytes). `ru_mt_jstr.py` therefore treats everything from
`<file--foot>` to EOF as an opaque trailer and only rewrites `A`/`B`.

---

## 2. Chunk payload kinds

Chunk names are purely descriptive; the payload kind has to be inferred.
`ru_mt_jstr.py` classifies each chunk as `pool`, `index` or `opaque`.

### 2.1 String pool (`pool`)

A flat concatenation of NUL-terminated UTF-8 strings; the payload always ends
with a NUL, so `payload.split(b"\x00")[:-1]` reproduces the record list exactly.
A string is addressed by its **byte offset** inside the pool. Duplicate texts
do occur (rpw_jstr: 5302 slots / 5109 distinct texts) and only one copy is
usually referenced.

Detection is content-based (ends with NUL, >= 8 NULs, >= 98 % of bytes are
NUL / printable ASCII / >= 0x80, every record is valid UTF-8, mean record
length < 512). Name-based detection does **not** work: `jstr-i2i` is a binary
table despite the `jstr` prefix.

Two kinds of strings share one pool:

* **values** — displayed text (glossary entries, unit and pilot names, ...)
* **keys** — ASCII identifiers such as `rid_…`, `pid_…`, `kw_…`. These must
  never be translated. The tool flags them with `is_key`, using
  `^[a-z]+_[A-Za-z0-9_]+$`.

### 2.2 Offset table (`index`)

A regular lane of pool offsets inside the payload, described by
`(width, stride, phase)`: slot *i* is a `width`-byte little-endian integer at
byte `phase + i*stride`. A lane is accepted only when **every** slot holds a
valid string start, at least half the slots are non-zero and there are >= 4
distinct non-zero values — which keeps handle/ID tables (whose values
occasionally collide with a string start) out.

When `stride == 2*width` the companion lane at the other phase is checked for
uniqueness; if it is unique and positive it is recorded as `key_phase` and its
values are reported as the string's `ids`.

Observed lanes:

| file | chunk | lane | meaning |
|---|---|---|---|
| rpw_jstr | `jstr-i2i` | w4 stride 8 phase 4, keys@0 | 14802 `(u32 id, u32 offset)` pairs; `id` is simply `0..14801` |
| lega_zkn | `pid_prs` | w8 stride 16 phase 8, keys@0 | 924 `(u64 pid, u64 offset)` pairs |
| lega_zkn | `pids_prs` | w8 stride 8 phase 0 | 1848 `u64` offsets |
| lega_zkn | `prdnm_p`, `prdnm_r`, `prdnm_kw` | w8 stride 8 phase 0 | 29 `u64` offsets each |
| lega_zkn | `kw_name` | w8 stride 8 phase 0 | 147 `u64` offsets |
| lega_zkn | `prdnm2id` | w8 stride 8 phase 0 | 19 `u64` offsets |

### 2.3 Opaque (`opaque`)

Everything else is copied verbatim. Known opaque chunks:

* **lega_zkn** (14): `rid_ency`, `rid_pro`, `rid2idx`, `pid_ency`, `pid_pro`,
  `pid2idx`, `pid2pdid`, `rid2pdid`, `kid2pdid`, `kid_pro`, `kid2idx`,
  `kid_ord`, `constzkn`, `nmid_ord`. These are packed ID/handle tables
  (u32 `0xRRRRTTNN`-style records and u16 ordinal arrays). They contain no pool
  offsets, so resizing strings does not disturb them.
* **rpw_data** (23): `pilot`, `robot`, `weapon`, `skill`, `spirit`, `grow`,
  `deadmsg`, `boost-p`, `pidividx`, … — fixed-size record tables.

### 2.4 Coverage, and why `rpw_data` is not safely editable

After detection the tool computes, per pool, the fraction of *distinct* strings
reachable through some detected lane:

| file | pool | slots | distinct | coverage |
|---|---|---|---|---|
| rpw_jstr | `j-string` | 5302 | 5109 | **100 %** |
| lega_zkn | `jstr-zkn` | 1746 | 1745 | **100 %** |
| rpw_data | `j-string` | 6074 | 6074 | **0 %** |

`rpw_data` has a 6074-slot pool but none of its 23 tables stores an offset into
it — an exhaustive scan over every width 4/8 and every stride that divides the
payload size (up to 1024) finds no lane. Its strings must be addressed by some
other mechanism (slot ordinal, or a lookup through `rpw_jstr`'s `jstr-i2i`
ids). Consequently `rebuild` **refuses** to change string lengths in a pool
whose coverage is below 95 %; `--force` overrides this, but the resulting file
is only safe if the references really are index-based.

---

## 3. Rebuilding

`rebuild` performs, in order:

1. Replace each pool slot's bytes with the (possibly longer) translated UTF-8
   text, keeping the slot **order and count** unchanged.
2. Build `old_offset -> new_offset` per pool from the new record lengths.
3. Remap every value of every detected lane through that map.
4. Re-emit all chunks, recomputing `D`, `k`, `R` and `C` from the rules in §1.2.
5. Copy the file trailer verbatim and patch `A` and `B`.

Because the slot count never changes, `jstr-i2i`-style `id` lanes and all
opaque ordinal tables stay valid. Round-trip with no edits reproduces the input
byte for byte (`ru_mt_jstr.py verify`).

### JSON interchange format

```json
{
  "meta": {
    "format": "srwv-mt/1",
    "source": "00000000.dat",
    "size": 245052,
    "pools":  [{"chunk": "j-string", "slots": 5302, "unique": 5109,
                "referenced_slots": 5109, "referenced_unique": 5109,
                "coverage": 1.0, "bytes": 126408}],
    "chunks": [{"name": "jstr-i2i", "bytes": 118416, "kind": "index",
                "lanes": [{"width": 4, "stride": 8, "phase": 4,
                           "count": 14802, "pool": "j-string",
                           "key_phase": 0}]}],
    "translatable": 3402
  },
  "strings": [
    {"idx": 0, "pool": "j-string", "text": "...", "ids": [4, 5, 7],
     "is_key": false, "slots": [0]}
  ]
}
```

* `idx` — ordinal of the distinct text in this list (stable key for a TM).
* `text` — edit this. `text_ru` or `ru`, if present, take precedence.
* `ids` — numeric ids when the lane has a key companion, otherwise
  `"chunk[i]"` references.
* `is_key` — identifier string, do not translate.
* `slots` — pool slot indices this text occupies; required by `rebuild`,
  do not edit.

---

## 4. Neighbouring formats in `CommonData/MtData/EN`

Not every file in the MtData folder is an `<mt>` container. After CPK extraction
and Blowfish decryption:

| source | container | notes |
|---|---|---|
| `rpw_jstr.cpk` | `<mt>` | 2 chunks: `j-string`, `jstr-i2i`. The glossary string pool. |
| `lega_zkn.cpk` | `<mt>` | 22 chunks: `jstr-zkn` pool + 7 offset tables + 14 opaque ID tables. |
| `rpw_jstr.bin`, `new_rpw_joined_string_only.bin`, `new_rpw_joined_string_index_2_index.bin` | `<mt>` | Loose authoring-tool outputs, producer tag `z3of1`/`rpw-all`, build date in the file footer. The `index_2_index` one has only `jstr-i2i` and no pool. |
| `MtZkn_Nm.cpk`, `MtZkn_Pt.cpk`, `MtZkn_Rt.cpk` | **not `<mt>`** | One record per CPK entry (19 / 392 / 273 files). The whole file is XOR 0x5E. After XOR: magic `ZKANPDNM`, then 4-char tagged sections `DSIZ` / `DATA` / `DSCR`, each followed by a 16-bit size/offset field; the filler byte is `0x5E` (`'^'`), the same role `'*'` plays in `<mt>`. `DSCR` holds the UTF-8 description text and the file ends with a `<srw-tag=before-clear-text-here>` marker. Needs its own parser — the exact field semantics are not nailed down yet. |
| `MtV_all_keyword_def.cpk` | **not `<mt>`** | Magic `MTFLz2_2`, version `0.94`, then a chain of 4-char tagged section descriptors (`kwrb`, `lkke`, …) of the form `tag + u32 total + u32 header_size + u32 payload_size` with `total == header_size + payload_size` (verified), and a trailing build source-path string. Needs its own parser. |

`ru_mt_jstr.py probe <dir>` reports these four kinds (`mt`, `zkan`, `mtfl`,
`cpk`, `unknown`).
