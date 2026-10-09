# -*- coding: utf-8 -*-
"""Нарезать непереведённые реплики блока из карты персонажей на куски."""
import json
import os
import sys

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
block, chunk, prefix = sys.argv[1], int(sys.argv[2]), sys.argv[3]
bl = next(s for s in json.load(open(os.path.join(E, "cmn_subs_EN.json"), encoding="utf-8"))["sections"]
          if s["name"] == "battle_lines")["strings"]
tm = json.load(open(os.path.join(E, "cmn_tm.json"), encoding="utf-8"))
bm = json.load(open(os.path.join(E, "cmn_block_map.json"), encoding="utf-8"))
rngs = next(v for k, v in bm.items() if block.lower() in k.lower())
todo, seen = [], set()
for a, b in rngs:
    for s in bl[a:b + 1]:
        if not s.strip() or s in ("-", "...", "\u2026", "dummy") or s in tm or s in seen:
            continue
        seen.add(s)
        todo.append(s)
n = 0
for k in range(0, len(todo), chunk):
    n += 1
    part = todo[k:k + chunk]
    p = os.path.join(E, "%s%02d.json" % (prefix, n))
    json.dump({"items": [{"en": s, "ru": ""} for s in part]},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%s%02d.json  %3d строк  %5d симв." % (prefix, n, len(part), sum(len(s) for s in part)))
print("блок:", block, "| непереведённых:", len(todo), "| кусков:", n)
