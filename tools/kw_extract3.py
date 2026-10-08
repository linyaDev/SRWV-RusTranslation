# -*- coding: utf-8 -*-
"""Достать конкретные статьи KeyWord, восстановив букву z, съеденную разделителем."""
import re

x = open(r"D:\games\SUPER ROBOT WARS V\_extracted\MtV_kw_xor7a.bin", "rb").read()
parts = x.split(b"\x00")

# Восстановление: \0 между двумя буквами внутри слова — это 'z'
merged = []
cur = b""
for i, p in enumerate(parts):
    if cur and p and cur[-1:].isalpha() and p[:1].islower():
        cur += b"z" + p          # 'z' внутри слова
    else:
        if cur:
            merged.append(cur)
        cur = p
if cur:
    merged.append(cur)

texts = []
for m in merged:
    try:
        texts.append(m.decode("utf-8"))
    except UnicodeDecodeError:
        texts.append("")

WANT = ("Jupiter War", "Axis Shock", "100 Years Ago")
for i, t in enumerate(texts):
    if t.strip() in WANT:
        print("=" * 70)
        print("ТЕРМИН:", t.strip())
        for j in range(i + 1, min(i + 4, len(texts))):
            s = texts[j]
            if not s:
                continue
            tag = "СЕРИЯ " if len(s) < 70 and j == i + 1 else "ТЕКСТ "
            print(f"--- {tag}[{j}] ({len(s)} симв)")
            print(s)
            if tag == "ТЕКСТ ":
                break
