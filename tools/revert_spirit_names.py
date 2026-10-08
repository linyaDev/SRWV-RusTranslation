# -*- coding: utf-8 -*-
"""Вернуть английские названия умений духа (не влезают в узкое поле),
описания эффектов оставить русскими."""
import json
import os
import re

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
en = {x["idx"]: x["text"] for x in
      json.load(open(os.path.join(E, "rpw_jstr_EN.json"), encoding="utf-8"))["strings"]}
data = json.load(open(os.path.join(E, "rpw_jstr_RU.json"), encoding="utf-8"))

# диапазон умений духа: названия, их двухбуквенные сокращения и «－»
LO, HI = 4399, 4490
reverted = 0
for s in data["strings"]:
    i = s["idx"]
    if not (LO <= i <= HI):
        continue
    e = en.get(i, "")
    # описание эффекта — длинная фраза с пробелами и точкой: оставляем русским
    if len(e) > 18 or (" " in e and e.endswith(".")):
        continue
    if s["text"] != e:
        print(f'  idx {i:<5} {s["text"]!r} -> {e!r}')
        s["text"] = e
        reverted += 1

json.dump(data, open(os.path.join(E, "rpw_jstr_RU.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"возвращено английских названий: {reverted}")
