# -*- coding: utf-8 -*-
"""Нарезать статьи справки KeyWord (MTFL) на порции для перевода.

Уже переведённые восемь статей подставляются из keywords_ru.json, чтобы
не переводить их заново и не плодить разночтений.
"""
import json
import os

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
PER_CHUNK = 6

old = {}
for a in json.load(open(os.path.join(E, "keywords_ru.json"), encoding="utf-8-sig"))["articles"]:
    if a.get("text_ru"):
        old[a["term_en"]] = a

arts = json.load(open(os.path.join(E, "keywords_all_EN.json"), encoding="utf-8"))["articles"]
todo, ready = [], []
for a in arts:
    rec = {"idx": a["idx"], "term": a["term"], "series": a["series"],
           "desc": a["desc"], "desc2": a["desc2"],
           "term_ru": "", "series_ru": "", "desc_ru": "", "desc2_ru": ""}
    o = old.get(a["term"])
    if o:
        rec["term_ru"] = o.get("term_ru", "")
        rec["series_ru"] = o.get("series_ru", "")
        rec["desc_ru"] = o.get("text_ru", "")
        ready.append(rec)
    else:
        todo.append(rec)

print("статей всего %d | уже переведено %d | к переводу %d" %
      (len(arts), len(ready), len(todo)))
print("символов к переводу:", sum(len(r["desc"]) + len(r["desc2"]) for r in todo))

json.dump({"articles": ready}, open(os.path.join(E, "kw_ready.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
n = 0
for k in range(0, len(todo), PER_CHUNK):
    n += 1
    part = todo[k:k + PER_CHUNK]
    json.dump({"articles": part},
              open(os.path.join(E, "kw_%02d.json" % n), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
print("кусков по %d статей: %d" % (PER_CHUNK, n))
