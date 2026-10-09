# -*- coding: utf-8 -*-
"""Нарезать непереведённые реплики диапазона на файлы по N строк."""
import json, os, sys
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
start, end, chunk, prefix = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
src = json.load(open(os.path.join(E, "cmn_subs_EN.json"), encoding="utf-8"))
bl = next(s for s in src["sections"] if s["name"] == "battle_lines")["strings"]
tm = json.load(open(os.path.join(E, "cmn_tm.json"), encoding="utf-8"))
todo, seen = [], set()
for s in bl[start:end+1]:
    if not s.strip() or s in ("-", "...", "\u2026") or s in tm or s in seen:
        continue
    seen.add(s); todo.append(s)
n = 0
for k in range(0, len(todo), chunk):
    n += 1
    part = todo[k:k+chunk]
    p = os.path.join(E, "%s%02d.json" % (prefix, n))
    json.dump({"items": [{"en": s, "ru": ""} for s in part]},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%s%02d.json  %3d строк  %5d симв." % (prefix, n, len(part), sum(len(s) for s in part)))
print("всего непереведённых:", len(todo), "| кусков:", n)
