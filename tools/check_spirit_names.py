# -*- coding: utf-8 -*-
"""Проверка: не осталось ли русских названий умений духа в описаниях."""
import json
import os
import re
import sys

sys.path.insert(0, r"D:\games\SUPER ROBOT WARS V\_tools")
from fix_spirit_bltu import NAMES, CYR

E = r"D:\games\SUPER ROBOT WARS V\_extracted"


def scan_bltu(ru_path, en_path, label):
    ru = json.load(open(ru_path, encoding="utf-8-sig"))
    src = {e["key"]: e["values"] for e in
           json.load(open(en_path, encoding="utf-8-sig"))["entries"]}
    left = []
    for ent in ru["entries"]:
        s = src.get(ent["key"])
        if not s:
            continue
        for vi, val in enumerate(ent["values"]):
            if vi >= len(s):
                break
            for eng, forms in NAMES.items():
                if not re.search(r"(?<![A-Za-z])" + re.escape(eng) + r"(?![A-Za-z])", s[vi]):
                    continue
                for form in forms:
                    f = re.escape(form)
                    if re.search("\u00ab" + f + "\u00bb", val) or \
                       re.search(r"(?:умени|команд)\w*\s+" + f + r"(?![" + CYR + r"])", val):
                        left.append((ent["key"], eng, form, val.strip()[:70]))
    print("%s: осталось %d" % (label, len(left)))
    for x in left[:10]:
        print("   %-26s [%s<-%s] %s" % x)


def scan_jstr():
    en = {x["idx"]: x["text"] for x in
          json.load(open(os.path.join(E, "rpw_jstr_EN.json"), encoding="utf-8"))["strings"]}
    left = []
    for s in json.load(open(os.path.join(E, "rpw_jstr_RU.json"), encoding="utf-8"))["strings"]:
        e, t = en.get(s["idx"], ""), s["text"]
        for eng, forms in NAMES.items():
            if not re.search(r"(?<![A-Za-z])" + re.escape(eng) + r"(?![A-Za-z])", e):
                continue
            for form in forms:
                f = re.escape(form)
                if re.search("\u00ab" + f + "\u00bb", t) or \
                   re.search(r"(?:умени|команд)\w*\s+" + f + r"(?![" + CYR + r"])", t):
                    left.append((s["idx"], eng, form, t.replace("\n", " / ")[:70]))
    print("rpw_jstr: осталось %d" % len(left))
    for x in left[:10]:
        print("   %-6d [%s<-%s] %s" % x)


scan_bltu(os.path.join(E, "json", "LT00_RU.json"), os.path.join(E, "json", "LT00_EN.json"), "LT00")
scan_bltu(os.path.join(E, "json", "SysText_RU.json"), os.path.join(E, "json", "SysText_EN.json"), "SysText")
scan_jstr()
