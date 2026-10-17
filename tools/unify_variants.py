# -*- coding: utf-8 -*-
"""Свести разнобой транслитераций к одному варианту.

За канон берётся самый частый вариант, кроме случаев в OVERRIDE — там
большинство ошибочно и выбран правильный вид.

В поле `speaker` замена точная (строка целиком), в тексте — по границам
слова, чтобы короткие имена вроде «Ал» не portили другие слова.
"""
import collections
import glob
import json
import os
import re
import sys

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(E, "story_b4")

OVERRIDE = {
    "Battle Bomber": "Бэттл Бомбер",   # устоявшийся вид названия
    "Dr. Hell": "Доктор Хелл",         # как в глоссарии и энциклопедии
    "Kensuke": "Кэнсукэ",
    "Peries": "Пьерис",                # Сома Пьерис — как в статьях энциклопедии
    "Django": "Джанго",
}
TERMS = {
    "«Де Данаан»": "«де Данаан»",
    "«Индастриал-7»": "«Индастриал 7»",
    "«Птолемей-2»": "«Птолемей 2»",
}
CYR = "\u0410-\u044f\u0401\u0451"

by_en = collections.defaultdict(collections.Counter)
pairs = []
for p in glob.glob(os.path.join(SRC, "ru_c*.json")):
    src = os.path.join(SRC, os.path.basename(p)[3:])
    if not os.path.exists(src):
        continue
    en = {b["i"]: b for b in json.load(open(src, encoding="utf-8"))["blocks"]}
    pairs.append((p, en))
    for b in json.load(open(p, encoding="utf-8-sig"))["blocks"]:
        o = en.get(b["i"])
        if o and o["speaker"].strip():
            by_en[o["speaker"]][b["speaker"]] += 1

canon = {}
for en_name, variants in by_en.items():
    if len(variants) < 2 and en_name not in OVERRIDE:
        continue
    best = OVERRIDE.get(en_name) or variants.most_common(1)[0][0]
    for v in variants:
        if v != best:
            canon[v] = best

print("вариантов к замене: %d" % len(canon))
for k, v in sorted(canon.items()):
    print("   %-18s -> %s" % (k, v))

n_sp = n_txt = n_term = 0
for p, en in pairs:
    d = json.load(open(p, encoding="utf-8-sig"))
    ch = False
    for b in d["blocks"]:
        o = en.get(b["i"])
        if o and o["speaker"].strip():
            best = OVERRIDE.get(o["speaker"]) or (
                by_en[o["speaker"]].most_common(1)[0][0] if by_en[o["speaker"]] else None)
            if best and b["speaker"] != best and len(by_en[o["speaker"]]) > 1 or \
               (best and o["speaker"] in OVERRIDE and b["speaker"] != best):
                b["speaker"] = best
                n_sp += 1
                ch = True
        t = b.get("text", "")
        new = t
        for bad, good in canon.items():
            if len(bad) >= 4 and bad in new:
                new = re.sub(r"(?<![%s])%s(?![%s])" % (CYR, re.escape(bad), CYR), good, new)
        for bad, good in TERMS.items():
            if bad in new:
                new = new.replace(bad, good)
                n_term += 1
        if new != t:
            b["text"] = new
            n_txt += 1
            ch = True
    if ch:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("\nимён в поле speaker: %d | реплик с правкой текста: %d | терминов: %d"
      % (n_sp, n_txt, n_term))
