# -*- coding: utf-8 -*-
"""Свести переводы статей справки KeyWord и подготовить файл для ru_mtfl.py."""
import glob
import json
import os

E = r"D:\games\SUPER ROBOT WARS V\_extracted"

src = {}
for p in glob.glob(os.path.join(E, "kw_??.json")):
    for a in json.load(open(p, encoding="utf-8"))["articles"]:
        src[a["idx"]] = a

tr = {}
for p in sorted(glob.glob(os.path.join(E, "kw_tr_??.json"))) + \
        [os.path.join(E, "kw_ready.json")]:
    if not os.path.exists(p):
        continue
    for a in json.load(open(p, encoding="utf-8-sig"))["articles"]:
        tr[a["idx"]] = a

arts = json.load(open(os.path.join(E, "keywords_all_EN.json"), encoding="utf-8"))["articles"]
errs = missing = 0
out = []
for a in arts:
    b = tr.get(a["idx"])
    if b is None:
        missing += 1
        print("  нет перевода: idx %d %r" % (a["idx"], a["term"]))
        out.append(dict(a))
        continue
    for fld, ru in (("term", "term_ru"), ("series", "series_ru"),
                    ("desc", "desc_ru"), ("desc2", "desc2_ru")):
        if b.get(fld) is not None and b[fld] != a[fld]:
            print("  idx %d: поле %s изменено" % (a["idx"], fld))
            errs += 1
        if a[fld] and not b.get(ru):
            print("  idx %d (%s): пусто %s" % (a["idx"], a["term"], ru))
            errs += 1
        if a[fld].count("\n") != (b.get(ru) or "").count("\n") and a[fld]:
            print("  idx %d (%s): разметка строк в %s" % (a["idx"], a["term"], ru))
            errs += 1
    rec = dict(a)
    rec["term"] = b.get("term_ru") or a["term"]
    rec["series"] = b.get("series_ru") or a["series"]
    rec["desc"] = b.get("desc_ru") or a["desc"]
    rec["desc2"] = b.get("desc2_ru") or a["desc2"]
    out.append(rec)

print("статей: %d | без перевода: %d | замечаний: %d" % (len(arts), missing, errs))
json.dump({"articles": out}, open(os.path.join(E, "keywords_ru_all.json"), "w",
                                  encoding="utf-8"), ensure_ascii=False, indent=1)
print("-> keywords_ru_all.json")
