# -*- coding: utf-8 -*-
"""Сравнить варианты имён в новой партии с уже установленным корпусом.

Внутри одной партии большинство может быть одним, а в игре уже стоит другое —
тогда канон берётся из корпуса, иначе одно имя будет звучать по-разному
в разных главах.
"""
import collections
import glob
import json
import os
import sys

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(E, "story_b5")
RU, EN = os.path.join(E, "dialogs_ru"), os.path.join(E, "dialogs_en_v3")

NAMES = sys.argv[2:] or [
    "Ashura", "Battle Bomber", "Colasour", "Djibril", "Elle", "Embryo",
    "Feldt", "Frontal", "Hallelujah", "Hathaway", "Lacus", "Lane", "Maya",
    "Mycenae God", "Ple", "Ple Two", "Riddhe", "Sabine", "Salamandinay",
    "Velt", "Zinnerman",
]

corpus = collections.defaultdict(collections.Counter)
for p in glob.glob(os.path.join(RU, "*.json")):
    name = os.path.basename(p)
    ep = os.path.join(EN, name)
    if not os.path.exists(ep):
        continue
    en = {b["i"]: b for b in json.load(open(ep, encoding="utf-8"))["blocks"]}
    j = json.load(open(p, encoding="utf-8-sig"))
    for b in (j.get("blocks", []) if isinstance(j, dict) else j):
        o = en.get(b["i"])
        if o and o["speaker"] in NAMES:
            corpus[o["speaker"]][b["speaker"]] += 1

batch = collections.defaultdict(collections.Counter)
for p in glob.glob(os.path.join(SRC, "ru_c*.json")):
    src = os.path.join(SRC, os.path.basename(p)[3:])
    if not os.path.exists(src):
        continue
    en = {b["i"]: b for b in json.load(open(src, encoding="utf-8"))["blocks"]}
    for b in json.load(open(p, encoding="utf-8-sig"))["blocks"]:
        o = en.get(b["i"])
        if o and o["speaker"] in NAMES:
            batch[o["speaker"]][b["speaker"]] += 1

print("%-16s %-34s %s" % ("имя", "в установленном корпусе", "в новой партии"))
for n in NAMES:
    c = ", ".join("%s(%d)" % kv for kv in corpus[n].most_common()) or "—"
    b = ", ".join("%s(%d)" % kv for kv in batch[n].most_common()) or "—"
    flag = ""
    if corpus[n] and batch[n]:
        if corpus[n].most_common(1)[0][0] != batch[n].most_common(1)[0][0]:
            flag = "  ← РАСХОЖДЕНИЕ"
    print("%-16s %-34s %s%s" % (n, c, b, flag))
