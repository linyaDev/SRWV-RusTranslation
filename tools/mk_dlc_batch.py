# -*- coding: utf-8 -*-
"""Подготовить DLC-миссии к переводу: куски диалогов и условия победы.

  mk_dlc_batch.py <номер> [<номер> ...]
"""
import collections
import json
import os
import shutil
import sys

G = r"D:\games\SUPER ROBOT WARS V"
B, E = os.path.join(G, "_build", "dlc"), os.path.join(G, "_extracted")
PER = 55

for num in sys.argv[1:]:
    dec = os.path.join(B, num + "_dec")
    out = os.path.join(E, "dlc" + num + "_en")
    os.makedirs(out, exist_ok=True)
    cast = collections.Counter()
    n = 0
    for f in sorted(os.listdir(dec)):
        if not f.endswith(".json"):
            continue
        d = json.load(open(os.path.join(dec, f), encoding="utf-8"))
        b, q = d.get("blocks", []), d.get("qstrings", [])
        base = f[:-5]
        shutil.copy(os.path.join(dec, f), os.path.join(out, f))
        if q:
            print("  %s условий %d: %s" % (base, len(q), "; ".join(i["q"] for i in q)[:90]))
        if not b:
            continue
        for x in b:
            s = x.get("speaker", "").strip()
            if s:
                cast[s] += 1
        for k in range(0, len(b), PER):
            n += 1
            json.dump({"blocks": b[k:k + PER]},
                      open(os.path.join(out, "p%02d_%s.json" % (n, base)), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)
    print("dlc%s: кусков %d | состав: %s" %
          (num, n, ", ".join(k for k, _ in cast.most_common(14))))
