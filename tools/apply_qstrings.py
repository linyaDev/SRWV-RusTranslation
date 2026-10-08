# -*- coding: utf-8 -*-
"""Разложить переведённые условия миссий по всем файлам dialogs_ru.

Для файлов, где перевода диалогов ещё нет, создаёт запись только с qstrings —
тогда экран целей будет русским даже в непереведённых миссиях.
"""
import glob
import json
import os

EN = r"D:\games\SUPER ROBOT WARS V\_extracted\dialogs_en"
RU = r"D:\games\SUPER ROBOT WARS V\_extracted\dialogs_ru"

tr = {it["en"]: it["ru"] for it in
      json.load(open(r"D:\games\SUPER ROBOT WARS V\_extracted\qstrings_ru.json",
                     encoding="utf-8-sig"))["items"] if it.get("ru")}
print("переводов условий:", len(tr))

touched = created = filled = 0
for p in sorted(glob.glob(os.path.join(EN, "0*.json"))):
    en = json.load(open(p, encoding="utf-8"))
    qs = en.get("qstrings", [])
    if not qs:
        continue
    name = os.path.basename(p)
    rp = os.path.join(RU, name)
    if os.path.exists(rp):
        ru = json.load(open(rp, encoding="utf-8-sig"))
    else:
        ru = {"blocks": []}
        created += 1
    have = {q["q"]: q for q in ru.get("qstrings", [])}
    out = []
    for q in qs:
        cur = have.get(q["q"], {}).get("ru", "")
        new = cur or tr.get(q["q"], "")
        if new and not cur:
            filled += 1
        out.append({"q": q["q"], "ru": new})
    ru["qstrings"] = out
    json.dump(ru, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    touched += 1

print(f"файлов обновлено: {touched} (из них создано новых: {created})")
print(f"условий заполнено: {filled}")
