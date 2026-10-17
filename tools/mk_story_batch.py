# -*- coding: utf-8 -*-
"""Подготовить к переводу произвольный набор стадий.

  mk_story_batch.py <каталог> <стадия> [<стадия> ...]

Для каждой стадии берутся все её файлы, диалоги извлекаются (если ещё нет),
режутся по 55 блоков, условия миссий складываются отдельно.
"""
import json
import os
import re
import subprocess
import sys

G = r"D:\games\SUPER ROBOT WARS V"
E, T = G + r"\_extracted", G + r"\_tools"
outdir = sys.argv[1]
STAGES = sys.argv[2:]

smap = json.load(open(os.path.join(G, "_build", "stage_map.json")))
cur, st = None, {}
for r in smap:
    m = re.match(r"stage(\w+?)(preset)?\.lua$", r["lua"])
    if m:
        cur = m.group(1)
    if cur:
        st.setdefault(cur, []).append(r["id"])

missing = [s for s in STAGES if s not in st]
if missing:
    print("нет таких стадий:", missing)

den = os.path.join(E, "dialogs_en_v3")
for stage in STAGES:
    for fid in st.get(stage, []):
        src = os.path.join(E, "STAGE_EN_dec", "%08d.dat" % fid)
        dst = os.path.join(den, "%08d.json" % fid)
        if os.path.exists(src) and not os.path.exists(dst):
            subprocess.run([sys.executable, os.path.join(T, "ru_lua_dialog.py"),
                            "extract", src, dst], capture_output=True, text=True)

OUT = os.path.join(E, outdir)
os.makedirs(OUT, exist_ok=True)
n = qs = total = 0
for stage in STAGES:
    tot = 0
    for fid in st.get(stage, []):
        p = os.path.join(den, "%08d.json" % fid)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        b, q = d.get("blocks", []), d.get("qstrings", [])
        if q:
            qs += len(q)
            json.dump({"qstrings": q},
                      open(os.path.join(OUT, "q_%08d.json" % fid), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        tot += len(b)
        for k in range(0, len(b), 55):
            n += 1
            json.dump({"blocks": b[k:k + 55]},
                      open(os.path.join(OUT, "c%03d_%08d.json" % (n, fid)), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)
    total += tot
    print("%-5s блоков %4d" % (stage, tot))
print("ИТОГО блоков %d | кусков %d | условий миссий %d" % (total, n, qs))
