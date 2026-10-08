#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ru_cmn_subs.py — extract/rebuild строк из контейнера CMN00 (00000001.dat)
Super Robot Wars V (боевые субтитры, названия барьеров, спирит-эффекты).

Формат контейнера (little-endian, см. CMN00_FORMAT.md):
  +0x00 u32 nSections
  +0x04 u32 fenceTableOffset (обычно 0x10)
  +0x08 u32 dataBase         (обычно 0x30)
  +0x0C u32 0
  +fenceTableOffset: (nSections+1) x u32 — "заборные" смещения секций
        относительно dataBase; последнее = размер данных (EOF - dataBase).
  далее нули до dataBase.

Секция (в 00000001.dat каждая — таблица строк):
  +0x00 u32 count
  +0x04 u32 off[count]   — смещения строк от начала пула, off[0]==0,
                           строки лежат подряд без дыр и дедупликации
  затем пул: count null-terminated UTF-8 строк подряд,
  затем нулевое выравнивание конца секции до кратного 16.

Переносы строк в репликах хранятся как ЛИТЕРАЛЬНЫЕ два символа '\\'+'n'.

Использование:
  python ru_cmn_subs.py extract <in.dat> <out.json>
  python ru_cmn_subs.py rebuild <in.dat> <translated.json> <out.dat>

rebuild с неизменённым json даёт байт-в-байт оригинал.
"""
import json
import struct
import sys

SECTION_NAMES = {
    0: "barrier_misc",      # доп. названия брони/покрытий (VPS Armor, Beam Coat)
    1: "barrier_names",     # названия барьеров/полей (24 шт.)
    2: "defend_labels",     # подписи защиты (Defend, Shield Defend)
    3: "evade_abilities",   # способности уклонения (Shadow, Quantization...)
    4: "spirit_effects",    # эффекты спиритов (... Up)
    5: "battle_lines",      # боевые реплики пилотов, индекс = voice id (34279)
}

ALIGN = 16


def _align(n, a=ALIGN):
    return (n + a - 1) // a * a


def parse_container(data):
    """-> (nSections, fenceOff, dataBase, [абс. границы секций len=n+1])"""
    n, fence_off, data_base, pad = struct.unpack_from("<4I", data, 0)
    if pad != 0:
        raise ValueError("header +0x0C != 0: не тот формат?")
    fences = struct.unpack_from("<%dI" % (n + 1), data, fence_off)
    if data_base + fences[-1] != len(data):
        raise ValueError("последний fence не равен размеру данных: не тот формат?")
    tbl_end = fence_off + 4 * (n + 1)
    if data[tbl_end:data_base].strip(b"\0"):
        raise ValueError("мусор между таблицей смещений и dataBase")
    return n, fence_off, data_base, [data_base + f for f in fences]


def parse_section(data, start, end):
    """Таблица строк -> list[bytes] (без завершающего нуля)."""
    cnt, = struct.unpack_from("<I", data, start)
    offs = struct.unpack_from("<%dI" % cnt, data, start + 4)
    pool = start + 4 + 4 * cnt
    if pool > end:
        raise ValueError(f"section @{start:#x}: count={cnt} не влезает")
    out = []
    prev_end = 0
    for j, o in enumerate(offs):
        if o != prev_end:
            raise ValueError(f"section @{start:#x} str {j}: offset {o:#x} != {prev_end:#x} (дыра/дедуп)")
        z = data.index(b"\0", pool + o, end)
        out.append(data[pool + o:z])
        prev_end = z + 1 - pool
    tail = data[pool + prev_end:end]
    if tail.strip(b"\0"):
        raise ValueError(f"section @{start:#x}: ненулевой хвост после строк")
    return out


def build_section(strings_bytes):
    """list[bytes] -> bytes секции (с выравниванием до 16)."""
    offs = []
    pos = 0
    for s in strings_bytes:
        if b"\0" in s:
            raise ValueError("строка содержит NUL")
        offs.append(pos)
        pos += len(s) + 1
    body = struct.pack("<I", len(strings_bytes))
    body += struct.pack("<%dI" % len(offs), *offs)
    body += b"\0".join(strings_bytes) + b"\0"
    return body + b"\0" * (_align(len(body)) - len(body))


def build_container(sections_bytes, fence_off=0x10, data_base=None):
    n = len(sections_bytes)
    if data_base is None:
        data_base = _align(fence_off + 4 * (n + 1))
    fences = [0]
    for sb in sections_bytes:
        if len(sb) % ALIGN:
            raise ValueError("секция не выровнена")
        fences.append(fences[-1] + len(sb))
    hdr = struct.pack("<4I", n, fence_off, data_base, 0)
    hdr += struct.pack("<%dI" % (n + 1), *fences)
    hdr += b"\0" * (data_base - len(hdr))
    return hdr + b"".join(sections_bytes)


def load_dat(path):
    data = open(path, "rb").read()
    n, fence_off, data_base, bounds = parse_container(data)
    secs = [parse_section(data, bounds[i], bounds[i + 1]) for i in range(n)]
    return data, fence_off, data_base, secs


def cmd_extract(in_dat, out_json):
    _, _, _, secs = load_dat(in_dat)
    doc = {"source": in_dat, "sections": []}
    total = 0
    for i, strs in enumerate(secs):
        doc["sections"].append({
            "id": i,
            "name": SECTION_NAMES.get(i, "section_%d" % i),
            "count": len(strs),
            "strings": [s.decode("utf-8") for s in strs],
        })
        total += len(strs)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"extract: {total} строк в {len(secs)} секциях -> {out_json}")


def cmd_rebuild(in_dat, json_path, out_dat):
    orig_data, fence_off, data_base, secs = load_dat(in_dat)
    doc = json.load(open(json_path, encoding="utf-8"))
    jsecs = doc["sections"]
    if len(jsecs) != len(secs):
        raise SystemExit(f"число секций: json {len(jsecs)} != dat {len(secs)}")
    new_sections = []
    changed = 0
    for i, js in enumerate(jsecs):
        if js["id"] != i:
            raise SystemExit(f"section id {js['id']} на позиции {i}")
        strs = js["strings"]
        if len(strs) != len(secs[i]):
            raise SystemExit(
                f"секция {i}: число строк {len(strs)} != {len(secs[i])} "
                "(число записей менять нельзя)")
        enc = [s.encode("utf-8") for s in strs]
        changed += sum(1 for a, b in zip(enc, secs[i]) if a != b)
        new_sections.append(build_section(enc))
    out = build_container(new_sections, fence_off, data_base)
    open(out_dat, "wb").write(out)
    same = " (байт-в-байт оригинал)" if out == orig_data else ""
    print(f"rebuild: {changed} строк изменено, {len(out)} байт -> {out_dat}{same}")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "extract" and len(sys.argv) == 4:
        cmd_extract(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 2 and sys.argv[1] == "rebuild" and len(sys.argv) == 5:
        cmd_rebuild(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
