# -*- coding: utf-8 -*-
"""Склеить переведённые куски сюжета обратно по исходным файлам, проверить
и свести разнобой в терминах между агентами."""
import glob
import json
import os
import re

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
SRC = os.path.join(E, "story_route")
DEN = os.path.join(E, "dialogs_en_v3")
OUT = os.path.join(E, "dialogs_ru")

# один и тот же термин разные агенты перевели по-разному
UNIFY = [
    ("отряд «Брейв Экспресс»", "отряд «Отважный экспресс»"),
    ("«Брейв Экспресс»", "«Отважный экспресс»"),
    ("Брейв Экспресс", "Отважный экспресс"),
    ("отряд «Храбрый экспресс»", "отряд «Отважный экспресс»"),
    ("«Храбрый экспресс»", "«Отважный экспресс»"),
    ("Храбрый экспресс", "Отважный экспресс"),
    ("война с Ящерами", "Война с ящерами"),
    ("Войной с Ящерами", "Войной с ящерами"),
]

groups = {}
for p in sorted(glob.glob(os.path.join(SRC, "ru_s*_*.json"))):
    fid = re.search(r"_(\d{8})\.json$", p).group(1)
    groups.setdefault(fid, []).append(p)

errs = fixed = 0
for fid, parts in sorted(groups.items()):
    orig = json.load(open(os.path.join(DEN, fid + ".json"), encoding="utf-8"))
    by_i = {b["i"]: b for b in orig["blocks"]}
    merged = []
    for p in parts:
        merged += json.load(open(p, encoding="utf-8-sig"))["blocks"]
    if len(merged) != len(orig["blocks"]):
        print("%s: блоков %d, ожидалось %d" % (fid, len(merged), len(orig["blocks"])))
        errs += 1
    for b in merged:
        o = by_i.get(b["i"])
        if o is None:
            print("  %s: нет блока i=%s" % (fid, b["i"])); errs += 1; continue
        if b.get("orig") != o["orig"]:
            print("  %s i=%s: orig изменён" % (fid, b["i"])); errs += 1
        if not b.get("text", "").strip():
            print("  %s i=%s: пустой перевод" % (fid, b["i"])); errs += 1
        for key in ("speaker", "text"):
            for a, bb in UNIFY:
                if a in b.get(key, ""):
                    b[key] = b[key].replace(a, bb)
                    fixed += 1
        lim = max((len(x) for x in o["text"].split("\n")), default=0) + 2
        for line in b.get("text", "").split("\n"):
            if len(line) > lim:
                print("  %s i=%s: строка %d симв., лимит %d" % (fid, b["i"], len(line), lim))
                errs += 1
                break
    res = {"blocks": sorted(merged, key=lambda x: x["i"])}
    q = os.path.join(SRC, "q_" + fid + ".json")
    if os.path.exists(q):
        res["qstrings"] = json.load(open(q, encoding="utf-8"))["qstrings"]
    json.dump(res, open(os.path.join(OUT, fid + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

print("файлов собрано: %d | правок терминов: %d | ошибок: %d" % (len(groups), fixed, errs))
