# -*- coding: utf-8 -*-
"""Подготовить главу 3 к сборке STGEST: условия миссий и копии оригиналов."""
import json
import os
import re
import shutil

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
SRC = os.path.join(E, "story_ch3")
NEW = sorted({re.search(r"(\d{8})", f).group(1)
              for f in os.listdir(SRC) if f.startswith("ru_c")})

tr = {}
for f in ("qstrings_ru.json", "qstrings_ru2.json"):
    for it in json.load(open(os.path.join(E, f), encoding="utf-8-sig"))["items"]:
        if it.get("ru"):
            tr[it["en"]] = it["ru"]

missing = []
for n in NEW:
    shutil.copy(os.path.join(E, "dialogs_en_v3", n + ".json"),
                os.path.join(E, "dialogs_en", n + ".json"))
    qs = json.load(open(os.path.join(E, "dialogs_en_v3", n + ".json"),
                        encoding="utf-8")).get("qstrings", [])
    if not qs:
        continue
    rp = os.path.join(E, "dialogs_ru", n + ".json")
    ru = json.load(open(rp, encoding="utf-8-sig"))
    out = []
    for q in qs:
        r = tr.get(q["q"], "")
        if not r:
            missing.append(q["q"])
        out.append({"q": q["q"], "ru": r})
    ru["qstrings"] = out
    json.dump(ru, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("файлов подготовлено:", len(NEW))
print("условий без перевода:", len(missing))
for q in dict.fromkeys(missing):
    print("   ", q)
