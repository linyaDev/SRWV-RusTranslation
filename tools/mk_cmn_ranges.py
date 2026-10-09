# -*- coding: utf-8 -*-
"""Нарезать непереведённые реплики из нескольких диапазонов разом."""
import json
import os
import sys

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
prefix = sys.argv[1]
chunk = int(sys.argv[2])
ranges = [tuple(int(x) for x in a.split("-")) for a in sys.argv[3:]]
bl = next(s for s in json.load(open(os.path.join(E, "cmn_subs_EN.json"), encoding="utf-8"))["sections"]
          if s["name"] == "battle_lines")["strings"]
tm = json.load(open(os.path.join(E, "cmn_tm.json"), encoding="utf-8"))
todo, seen = [], set()
for a, b in ranges:
    for s in bl[a:b + 1]:
        if not s.strip() or s in ("-", "...", "\u2026", "dummy") or s in tm or s in seen:
            continue
        seen.add(s)
        todo.append(s)
n = 0
for k in range(0, len(todo), chunk):
    n += 1
    part = todo[k:k + chunk]
    json.dump({"items": [{"en": s, "ru": ""} for s in part]},
              open(os.path.join(E, "%s%02d.json" % (prefix, n)), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
print("непереведённых: %d | кусков по %d: %d" % (len(todo), chunk, n))
