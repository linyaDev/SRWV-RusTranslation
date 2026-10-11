# -*- coding: utf-8 -*-
"""Проверить и влить статьи маршрута в общую базу энциклопедии.

Ключ записи — ПАРА (каталог, файл): имена файлов повторяются между
MtZkn_Pt_dec и MtZkn_Rt_dec, по одному имени статья о герое подменяется
статьёй о машине.
"""
import glob
import json
import os

E = r"D:\games\SUPER ROBOT WARS V\_extracted"

src = {}
for p in glob.glob(os.path.join(E, "zkan_r0*_route.json")):
    if "_tr_" in os.path.basename(p):
        continue
    for a in json.load(open(p, encoding="utf-8"))["articles"]:
        src[(a.get("dir"), a["file"])] = a

merged, errs = [], 0
for p in sorted(glob.glob(os.path.join(E, "zkan_tr_r0*_route.json"))):
    for b in json.load(open(p, encoding="utf-8-sig"))["articles"]:
        a = src.get((b.get("dir"), b["file"]))
        if a is None:
            print("  %s: %s не из этого набора" % (os.path.basename(p), b["file"]))
            errs += 1
            continue
        for k in a:
            if not k.endswith("_ru") and a[k] != b.get(k):
                print("  %s: поле %s изменено" % (b["file"], k)); errs += 1
            if k.endswith("_ru") and not b.get(k):
                print("  %s: пусто %s" % (b["file"], k)); errs += 1
        for fld in ("DSCR", "DSC2"):
            if a.get(fld, "").startswith("<srw-tag") and not b.get(fld + "_ru", "").startswith("<srw-tag"):
                print("  %s: потерян маркер в %s" % (b["file"], fld)); errs += 1
        for fld in ("DSCR_ru", "DSC2_ru"):
            for line in b.get(fld, "").split("\n"):
                if len(line) > 76:
                    print("  %s: строка %d симв. в %s" % (b["file"], len(line), fld))
                    errs += 1
                    break
        merged.append(b)

print("статей собрано: %d из %d | ошибок: %d" % (len(merged), len(src), errs))

p = os.path.join(E, "zkan_all_ru.json")
data = json.load(open(p, encoding="utf-8"))
have = {(a.get("dir"), a["file"]) for a in data["articles"]}
added = [a for a in merged if (a.get("dir"), a["file"]) not in have]
data["articles"] += added
json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("добавлено: %d | всего в базе: %d" % (len(added), len(data["articles"])))
