# -*- coding: utf-8 -*-
"""Вернуть английские названия умений духа ВНУТРИ описаний.

Карта строится только из названий, которые в игре реально показываются
по-английски. Замена — лишь там, где английское название есть в оригинале,
и только по границам слова, иначе «Анализер» превращается в «Analyzeер».
"""
import glob
import json
import os
import re

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
en = {x["idx"]: x["text"] for x in
      json.load(open(os.path.join(E, "rpw_jstr_EN.json"), encoding="utf-8"))["strings"]}
data = json.load(open(os.path.join(E, "rpw_jstr_RU.json"), encoding="utf-8"))
cur = {s["idx"]: s["text"] for s in data["strings"]}

ru_old = {}
for p in sorted(glob.glob(os.path.join(E, "jstr_tr_*.json"))):
    for s in json.load(open(p, encoding="utf-8-sig"))["items"]:
        i, t = s.get("idx"), s.get("ru") or s.get("text") or ""
        if i is not None and t:
            ru_old.setdefault(i, t)

name_map = {}
for i in range(4399, 4491):
    e, r = en.get(i, ""), ru_old.get(i, "")
    if not e or not r or r == e or len(e) > 18 or "\n" in e or len(r) < 4:
        continue
    if cur.get(i) != e:          # показывается не по-английски — не трогаем
        continue
    name_map[e] = r
print("названий в карте:", len(name_map))

WORD = r"(?<![А-Яа-яЁё])%s(?![А-Яа-яЁё])"
ENWORD = r"(?<![A-Za-z])%s(?![A-Za-z])"
order = sorted(name_map, key=lambda x: -len(name_map[x]))

fixed = 0
for s in data["strings"]:
    e, t = en.get(s["idx"], ""), s["text"]
    if not e:
        continue
    new = t
    for name in order:
        if not re.search(ENWORD % re.escape(name), e):
            continue
        new = re.sub(WORD % re.escape(name_map[name]), name, new)
    if new != t:
        s["text"] = new
        fixed += 1
        if fixed <= 14:
            print("  %-5d %s" % (s["idx"], new.replace("\n", " / ")[:95]))

json.dump(data, open(os.path.join(E, "rpw_jstr_RU.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("строк исправлено:", fixed)

bad = [(s["idx"], s["text"]) for s in data["strings"]
       if re.search(r"[A-Za-z][А-Яа-яЁё]|[А-Яа-яЁё][A-Za-z]", s["text"])]
print("склеенных латиница+кириллица:", len(bad))
for i, t in bad[:10]:
    print("   %-5d %s" % (i, t.replace("\n", " / ")[:70]))
