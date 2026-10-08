# ZKAN — encyclopedia (Mecha & Character Encyclopedia) record format, SRW V

Reverse-engineered from the Steam build. Status: **fully understood** —
684/684 records parse and re-serialize byte-for-byte identically.

Tool: [`ru_zkan.py`](ru_zkan.py).

## 1. Where the records live

| CPK (per language, e.g. `CommonData/MtData/EN/`) | Record type | Records | Content |
|---|---|---|---|
| `MtZkn_Pt.cpk` | `ZKANCHAR` | 392 | characters (*Pt* = person) |
| `MtZkn_Rt.cpk` | `ZKANROBO` | 273 | units / robots |
| `MtZkn_Nm.cpk` | `ZKANPDNM` | 19 | series digests / terms |

Each CPK is an ITOC-only archive whose entries have no names, only numeric
IDs `0..N-1`; `cpk_extract.py` writes them as `%08d.dat`, so
**file number == CPK file ID**. Every entry is one ZKAN record,
Blowfish-ECB encrypted (`srwv_decrypt.py` / `srwv_encrypt.py`,
key `SRVW Steam Game`, big-endian word order).

Full pipeline:

```
MtZkn_Pt.cpk --cpk_extract--> 00000000.dat (encrypted)
             --srwv_decrypt--> 00000000.dat (ZKAN, byte-obfuscated)  <-- ru_zkan.py works here
             --ru_zkan extract--> 00000000.json
             --ru_zkan rebuild--> 00000000.dat
             --srwv_encrypt--> 00000000.enc
             --ru_cpk_patch--> MtZkn_Pt.cpk
```

## 2. Byte obfuscation

On top of Blowfish every record byte is obfuscated:

```python
plain[i] = raw[i] if raw[i] in (0x00, 0x5E) else raw[i] ^ 0x5E
```

The transform is an **involution** — the same function encodes and decodes.
A naive unconditional `^ 0x5E` over the whole file makes the ASCII readable
but corrupts chunk sizes: 11 of the 684 records have a size byte whose value
is exactly `0x5E` (e.g. `DATA size = 0x15E`), and those only validate under
the conditional rule. The `0x00` pass-through is what keeps the high bytes
of every `u32` at zero.

Practical consequence: the bytes `0x00` and `0x5E` (`^`) are literal in both
views. The original data contains no `^` at all in any text field (0 of
628 234 characters), but since the mapping is an involution a `^` would in
fact survive a round-trip. `ru_zkan.py` handles the layer internally — the
files it reads and writes are the post-Blowfish, still-obfuscated ones.

## 3. File layout (de-obfuscated)

```
offset  size  field
0x00    4     'ZKAN'
0x04    4     record type: 'CHAR' | 'ROBO' | 'PDNM'
0x08    4     u32 version — always 0x00000100
0x0C    4     u32 — always 12 (constant; purpose unknown, preserved verbatim)
0x10    ...   chunk stream
```

Chunk:

```
0x00    4     char[4] tag
0x04    4     u32 size (little-endian)
0x08    size  payload
```

`DSIZ` and `DATA` are **containers**: they carry no payload of their own, and
their `size` counts every byte that follows their own 8-byte header:

```
DSIZ.size == filesize - 24      (covers the DATA chunk and everything in it)
DATA.size == filesize - 32      (covers the leaf chunks)
```

All remaining chunks are leaves. There is **no padding, no alignment and no
NUL terminator anywhere** — leaves are packed back to back, string sizes are
the exact UTF-8 byte length, and the last chunk ends exactly at EOF.
Verified on all 684 records.

So rebuilding only requires: concatenate the leaf chunks, wrap in `DATA`,
wrap that in `DSIZ`. `ru_zkan.py rebuild` recomputes all three size levels,
which is why translated text may be of arbitrary length.

## 4. Chunk inventory

Chunk order is fixed per record type.

### `ZKANCHAR` (392 records)

`DSIZ DATA CHFN CHNN PRDC ACTR [VOIC] LOOK DSCR DSC2 KANA`

| Tag | Kind | Size range | Meaning | Translate |
|---|---|---|---|---|
| `CHFN` | UTF-8 | 2–25 | full name ("Kappei Jin") | yes |
| `CHNN` | UTF-8 | 2–25 | short name used in lists ("Kappei") | yes |
| `PRDC` | UTF-8 | 8–69 | source series ("Super Machine Zambot 3") | yes |
| `ACTR` | UTF-8 | 3–30 | voice actor | yes |
| `VOIC` | binary | 4/8/12/16 | `u32[]` voice-clip ids; present in 209/392 records | no |
| `LOOK` | binary | 4/8/12/16 | `u32[]` portrait / expression ids, first entry always 0 | no |
| `DSCR` | UTF-8 | 64–2233 | description, `\n`-separated, hard-wrapped | yes |
| `DSC2` | UTF-8 | 32–2349 | post-clear description (see §5) | yes |
| `KANA` | UTF-8 | 18 | japanese reading; in western builds always the placeholder `読み仮名無し` ("no reading given"), identical in all 392 records | no (leave as is) |

### `ZKANROBO` (273 records)

`DSIZ DATA PRDC LorR RBTN RBN2 PLTN HEIT WEIT DSCR DSC2`

| Tag | Kind | Size range | Meaning | Translate |
|---|---|---|---|---|
| `PRDC` | UTF-8 | 8–69 | source series | yes |
| `LorR` | binary | 4 | `u32`, always `0` in every record | no |
| `RBTN` | UTF-8 | 3–31 | unit name ("Zambot 3") | yes |
| `RBN2` | UTF-8 | 3–128 | long / alternate unit name | yes |
| `PLTN` | UTF-8 | 3 or 9 | pilot field, in practice the fullwidth placeholder `－－－` / `－` | rarely |
| `HEIT` | UTF-8 | 9–18 | height, fullwidth digits + fullwidth `ｍ` (e.g. `６０．０ｍ`), `－－－` when unknown | unit only |
| `WEIT` | UTF-8 | 9–18 | weight, fullwidth digits + fullwidth `ｔ` (e.g. `７００．０ｔ`) | unit only |
| `DSCR` | UTF-8 | 64–2233 | description | yes |
| `DSC2` | UTF-8 | 32–2349 | post-clear description | yes |

`HEIT`/`WEIT`/`PLTN` use **fullwidth** characters (`U+FF10..U+FF19`, `U+FF0E`,
`U+FF0D`, `U+FF4D`, `U+FF54`) because the encyclopedia renders them in a
fixed-pitch column; keep the fullwidth forms if you touch them.

### `ZKANPDNM` (19 records)

`DSIZ DATA DSCR DSC2` — long multi-paragraph series digests, no name fields.
Pick them out of the index by the first line of `DSCR`.

## 5. `DSCR` vs `DSC2`

`DSCR` is the description shown normally. `DSC2` is the variant shown once the
relevant scenario / the game has been cleared. All 684 records carry a
`DSC2`; its content falls into four groups:

| `DSC2` content | Records |
|---|---|
| exactly `<srw-tag=before-clear-text-here>` — nothing extra after clearing | 339 |
| `<srw-tag=before-clear-text-here>` + extra paragraph(s) appended to `DSCR` | 241 |
| standalone replacement text, no marker | 103 |
| marker somewhere in the middle | 1 |

So `<srw-tag=before-clear-text-here>` is a literal in-text marker meaning
"everything before this point is the pre-clear text" — i.e. when the marker
is present the game concatenates `DSCR` with whatever follows the marker.
**Keep the marker verbatim** (byte-for-byte, including case) when translating
`DSC2`; translate only the text around it.

## 6. Line breaks

`\n` (0x0A) is the only control character used in any text field (8005
occurrences). The game does **not** word-wrap — the original English text is
hard-wrapped by hand, ~72–76 half-width columns per line. Russian text must
be wrapped manually too; see `ru_font_metrics.py` / `TRANSLATE_RULES.md` for
the Cyrillic width data used elsewhere in this project.

## 7. JSON schema used by the tool

```json
{
  "format": "ZKAN",
  "type": "CHAR",
  "version": 256,
  "header_unk12": 12,
  "containers": ["DSIZ", "DATA"],
  "source": "00000000.dat",
  "fields": [
    { "tag": "CHFN", "kind": "text", "text": "Kappei Jin" },
    { "tag": "VOIC", "kind": "bin",
      "hex": "de7f0000b80600000a07000009070000",
      "u32": [32734, 1720, 1802, 1801],
      "base64": "3n8AALgGAAAKBwAACQcAAA==" }
  ]
}
```

* `fields` is an **ordered** list, so tag order and duplicates survive.
* Text payloads live in `text`, binary payloads in `hex` (authoritative) with
  `u32`/`base64` added for convenience; `rebuild` prefers `text`, then `hex`,
  then `base64`, then `u32`.
* `rebuild` **merges**: a JSON holding only the fields you changed is enough,
  everything else is taken from the original `.dat`. The n-th occurrence of a
  tag in the patch updates the n-th occurrence in the record; `"drop": true`
  removes a field, and an unknown tag is appended.

## 8. Commands

```
ru_zkan.py extract      <in.dat> <out.json>
ru_zkan.py rebuild      <in.dat> <translated.json> <out.dat>
ru_zkan.py extract-dir  <in_dir> <out_json_dir>
ru_zkan.py rebuild-dir  <in_dir> <json_dir> <out_dir>
ru_zkan.py roundtrip    <in_dir> [...]            # byte-exact selftest
ru_zkan.py index        <out.json> <in_dir> [...] # summary of all records
ru_zkan.py dump         <in.dat>                  # human-readable peek
```

Selftest result (`roundtrip`):

```
MtZkn_Pt_dec                              392/ 392 byte-identical
MtZkn_Rt_dec                              273/ 273 byte-identical
MtZkn_Nm_dec                               19/  19 byte-identical
TOTAL 684/684 byte-identical, 0 failures
```

## 9. Translation volume

From `_extracted/zkan_index.json`:

| Set | Records | `DSCR` chars | `DSC2` chars | all text chars |
|---|---|---|---|---|
| `MtZkn_Pt` (CHAR) | 392 | 221 885 | 132 489 | 379 369 |
| `MtZkn_Rt` (ROBO) | 273 | 152 885 | 40 986 | 213 502 |
| `MtZkn_Nm` (PDNM) | 19 | 18 121 | 17 242 | 35 363 |
| **total** | **684** | **392 891** | **190 717** | **628 234** |

Minus the untranslatable placeholders (339 × 32 chars of bare
`<srw-tag=before-clear-text-here>` plus 392 × 6 chars of `KANA`),
**≈615 034 characters** are actually translatable.
