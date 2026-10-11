# -*- coding: utf-8 -*-
"""Что осталось непереведённым для состава миссий 012, 013, 018, 019, 020."""
import collections
import json
import os

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
FILES = ("00000116", "00000117", "00000122", "00000123", "00000158",
         "00000159", "00000164", "00000165", "00000170", "00000171",
         "00000176", "00000177")

cast = collections.Counter()
for n in FILES:
    for b in json.load(open(os.path.join(E, "dialogs_en_v3", n + ".json"),
                            encoding="utf-8"))["blocks"]:
        s = b.get("speaker", "").strip()
        if s:
            cast[s] += 1
print("говорящих в этих миссиях:", len(cast))

idx = json.load(open(os.path.join(E, "zkan_index.json"), encoding="utf-8"))["entries"]
done = {(a.get("dir"), a["file"]) for a in
        json.load(open(os.path.join(E, "zkan_all_ru.json"), encoding="utf-8"))["articles"]}

need = []
for e in idx:
    if e["type"] != "CHAR" or (e["dir"], e["file"]) in done:
        continue
    short, full = e.get("short_name", ""), e.get("name", "")
    for sp, cnt in cast.items():
        if sp and (sp == short or sp == full or (" " in full and sp == full.split()[0])):
            need.append((cnt, sp, full, e["file"], e["dir"], e["text_chars"]))
            break
need.sort(reverse=True)
print("\nстатей о персонажах без перевода: %d (%d символов)" %
      (len(need), sum(x[5] for x in need)))
for cnt, sp, full, f, d, ch in need:
    print("   %-22s %5d симв., реплик %d" % (full, ch, cnt))

json.dump({"items": [{"file": x[3], "dir": x[4]} for x in need]},
          open(os.path.join(E, "zkan_need_route.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
