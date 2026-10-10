# -*- coding: utf-8 -*-
"""Уложить перевод в реальную ширину плашки.

Ширина проверена на установленных переводах главы 1: строки до 58 символов
отображаются нормально (в английских оригиналах встречается до 69).
Маркеры $kwb/$kwe на экране не видны, их длина из счёта вычитается.
Число строк в блоке не должно превышать оригинал.
"""
import json
import os
import re

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
RU, EN = os.path.join(E, "dialogs_ru"), os.path.join(E, "dialogs_en_v3")
NEW = ("00000116", "00000117", "00000122", "00000123", "00000158", "00000159",
       "00000164", "00000165", "00000170", "00000171", "00000176", "00000177")
LIMIT = 66
IND = "\u3000"
MARK = re.compile(r"\$kw[be]")


def vis(s):
    return len(MARK.sub("", s))


def rewrap(text, max_lines):
    open_br = close_br = ""
    body = text
    for o, c in (("\u300c", "\u300d"), ("\uff08", "\uff09")):
        if body.startswith(o):
            open_br, close_br = o, c
            body = body[len(o):]
            if body.endswith(c):
                body = body[:-len(c)]
            break
    words = " ".join(ln.strip(IND).strip() for ln in body.split("\n")).split()
    for width in range(LIMIT, 39, -2):
        lines, cur, base = [], open_br, len(open_br)
        for w in words:
            cand = cur + (" " if len(cur) > base and not cur.endswith(IND) else "") + w
            if vis(cand) <= width or len(cur) <= base:
                cur = cand
            else:
                lines.append(cur)
                cur, base = IND + w, 1
        lines.append(cur + close_br)
        if len(lines) <= max_lines and all(vis(l) <= LIMIT for l in lines):
            return "\n".join(lines)
    return None


fixed = fail = 0
for n in NEW:
    rp = os.path.join(RU, n + ".json")
    ru = json.load(open(rp, encoding="utf-8-sig"))
    en = {b["i"]: b for b in json.load(open(os.path.join(EN, n + ".json"),
                                            encoding="utf-8")) ["blocks"]}
    changed = False
    for b in ru["blocks"]:
        o = en[b["i"]]
        olines = len(o["text"].split("\n"))
        lines = b["text"].split("\n")
        if len(lines) <= olines and all(vis(l) <= LIMIT for l in lines):
            continue
        if "-" in b["text"] and IND * 2 in b["text"]:
            continue                        # карточка локации — центровку не трогаем
        new = rewrap(b["text"], olines)
        if new:
            b["text"] = new
            changed = True
            fixed += 1
        else:
            fail += 1
            print("%s[%s] вручную: %s" % (n, b["i"], b["text"].replace("\n", " / ")[:100]))
    if changed:
        json.dump(ru, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("исправлено: %d | осталось вручную: %d" % (fixed, fail))

