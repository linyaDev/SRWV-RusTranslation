# -*- coding: utf-8 -*-
"""Найти разнобой в транслитерации между агентами.

Сравниваются русские варианты, привязанные к одному и тому же английскому
говорящему, плюс ищутся похожие написания терминов в кавычках «…».
"""
import collections
import glob
import json
import os
import sys

E = r"D:\games\SUPER ROBOT WARS X\_extracted"
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(E, "story_b4")

# 1. один английский говорящий -> разные русские варианты
by_en = collections.defaultdict(collections.Counter)
for p in glob.glob(os.path.join(SRC, "ru_c*.json")):
    src = os.path.join(SRC, os.path.basename(p)[3:])
    if not os.path.exists(src):
        continue
    en = {b["i"]: b for b in json.load(open(src, encoding="utf-8"))["blocks"]}
    for b in json.load(open(p, encoding="utf-8-sig"))["blocks"]:
        o = en.get(b["i"])
        if o and o["speaker"].strip():
            by_en[o["speaker"]][b["speaker"]] += 1

print("=== говорящие с разными вариантами перевода")
n = 0
for en_name, variants in sorted(by_en.items()):
    if len(variants) > 1:
        n += 1
        tot = sum(variants.values())
        best = variants.most_common(1)[0][0]
        print("  %-22s -> %s" % (en_name, ", ".join(
            "%s(%d)%s" % (k, v, "" if k != best else " ←") for k, v in variants.most_common())))
print("всего имён с разнобоем:", n)

# 2. термины в кавычках-ёлочках
quoted = collections.Counter()
for p in glob.glob(os.path.join(SRC, "ru_c*.json")):
    for b in json.load(open(p, encoding="utf-8-sig"))["blocks"]:
        t = b.get("text", "")
        i = 0
        while True:
            a = t.find("\u00ab", i)
            if a < 0:
                break
            z = t.find("\u00bb", a)
            if z < 0:
                break
            quoted[t[a + 1:z]] += 1
            i = z + 1


def key(s):
    return s.lower().replace("ё", "е").replace("-", "").replace(" ", "")


groups = collections.defaultdict(list)
for term, cnt in quoted.items():
    groups[key(term)].append((cnt, term))
print("\n=== термины в кавычках с разными написаниями")
m = 0
for k, lst in sorted(groups.items()):
    if len(lst) > 1:
        m += 1
        lst.sort(reverse=True)
        print("  " + ", ".join("«%s»(%d)" % (t, c) for c, t in lst))
print("всего терминов с разнобоем:", m)
