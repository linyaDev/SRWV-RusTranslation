# -*- coding: utf-8 -*-
"""Склейка и проверка перевода DLC-миссии: ru_part*.json -> ru_<src>.json."""
import glob
import json
import os
import re
import sys

E = sys.argv[1]
groups = {}
for p in sorted(glob.glob(os.path.join(E, "ru_part*_*.json"))):
    src = re.search(r"_(\d{8})\.json$", p).group(1)
    groups.setdefault(src, []).append(p)

errs = 0
for src, parts in sorted(groups.items()):
    orig = json.load(open(os.path.join(E, src + ".json"), encoding="utf-8"))
    by_i = {b["i"]: b for b in orig["blocks"]}
    merged = []
    for p in parts:
        merged += json.load(open(p, encoding="utf-8-sig"))["blocks"]
    print("%s: частей %d, блоков %d (ожидалось %d)" % (src, len(parts), len(merged), len(orig["blocks"])))
    for b in merged:
        o = by_i.get(b["i"])
        if o is None:
            print("   нет блока i=%s" % b["i"]); errs += 1; continue
        if b.get("orig") != o["orig"]:
            print("   i=%s: orig изменён" % b["i"]); errs += 1
        if not b.get("text", "").strip():
            print("   i=%s: пустой перевод" % b["i"]); errs += 1
        lim = max((len(x) for x in o["text"].split("\n")), default=0) + 2
        for line in b.get("text", "").split("\n"):
            if len(line) > lim:
                print("   i=%s: строка %d симв., лимит %d" % (b["i"], len(line), lim)); errs += 1
                break
    json.dump({"blocks": sorted(merged, key=lambda x: x["i"])},
              open(os.path.join(E, "ru_" + src + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
print("\nошибок:", errs)
