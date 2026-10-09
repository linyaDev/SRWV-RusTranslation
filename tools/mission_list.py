# -*- coding: utf-8 -*-
"""Полный список миссий игры: id сцены + название (таблица KPACK_LN, файл 4)."""
import re

p = r"D:\games\SUPER ROBOT WARS V\_extracted\KPACK_LN_dec\00000004.dat"
b = open(p, "rb").read()
strs = [(m.start(), m.group().decode("latin1"))
        for m in re.finditer(rb"[\x20-\x7e]{2,80}", b)]
by_off = dict(strs)
rows, seen = [], set()
for off, s in strs:
    if re.fullmatch(r"\d{3}[a-z]?", s) and s not in seen:
        seen.add(s)
        rows.append((s, by_off.get(off + 64, "")))

CH = [("001", "009", "Пролог и глава 1"), ("010", "020", "Глава 2"),
      ("021", "030", "Глава 3"), ("031", "040", "Глава 4"),
      ("041", "053", "Глава 5"), ("054", "070", "Глава 6"),
      ("071", "087", "Финал")]
cur = None
for sid, title in rows:
    num = sid[:3]
    if num.isdigit() and num[0] == "0":
        lab = next((c[2] for c in CH if c[0] <= num <= c[1]), None)
        if lab != cur:
            cur = lab
            print("\n=== %s" % lab)
        print("  %-6s %s" % (sid, title))
print("\nвсего записей:", len(rows))
