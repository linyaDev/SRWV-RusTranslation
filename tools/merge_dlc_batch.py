# -*- coding: utf-8 -*-
"""Склеить переводы DLC-миссии, проверить и собрать файлы для вставки.

  merge_dlc_batch.py <номер> [<номер> ...]
"""
import glob
import json
import os
import re
import sys

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
MARK = re.compile(r"\$kw[be]")
LIMIT, MAXL = 66, 3

for num in sys.argv[1:]:
    d = os.path.join(E, "dlc" + num + "_en")
    groups = {}
    for p in sorted(glob.glob(os.path.join(d, "ru_p*_*.json"))):
        fid = re.search(r"_(\d{8})\.json$", p).group(1)
        groups.setdefault(fid, []).append(p)

    errs = 0
    for fid, parts in sorted(groups.items()):
        orig = json.load(open(os.path.join(d, fid + ".json"), encoding="utf-8"))
        by_i = {b["i"]: b for b in orig["blocks"]}
        merged = []
        for p in parts:
            merged += json.load(open(p, encoding="utf-8-sig"))["blocks"]
        if len(merged) != len(orig["blocks"]):
            print("  %s: блоков %d, ожидалось %d" % (fid, len(merged), len(orig["blocks"])))
            errs += 1
        for b in merged:
            o = by_i.get(b["i"])
            if o is None:
                print("  %s: нет блока i=%s" % (fid, b["i"])); errs += 1; continue
            if b.get("orig") != o["orig"]:
                print("  %s i=%s: orig изменён" % (fid, b["i"])); errs += 1
            if not b.get("text", "").strip():
                print("  %s i=%s: пустой перевод" % (fid, b["i"])); errs += 1
            lines = b.get("text", "").split("\n")
            if len(lines) > max(len(o["text"].split("\n")), MAXL):
                print("  %s i=%s: строк %d" % (fid, b["i"], len(lines))); errs += 1
            for ln in lines:
                if len(MARK.sub("", ln)) > LIMIT:
                    print("  %s i=%s: строка %d знаков" % (fid, b["i"],
                          len(MARK.sub("", ln)))); errs += 1
                    break
        json.dump({"blocks": sorted(merged, key=lambda x: x["i"])},
                  open(os.path.join(d, "ru_" + fid + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("dlc%s: файлов %d | ошибок %d" % (num, len(groups), errs))
