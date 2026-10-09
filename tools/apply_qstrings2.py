# -*- coding: utf-8 -*-
"""Разложить ВСЕ переводы условий (обе волны) по файлам dialogs_ru,
используя новое извлечение dialogs_en_v3 (на 144 строки полнее)."""
import glob
import json
import os

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
EN3 = os.path.join(E, "dialogs_en_v3")
RU = os.path.join(E, "dialogs_ru")

tr = {}
for f in ("qstrings_ru.json", "qstrings_ru2.json"):
    for it in json.load(open(os.path.join(E, f), encoding="utf-8-sig"))["items"]:
        if it.get("ru"):
            tr[it["en"]] = it["ru"]
print("переводов условий:", len(tr))

touched = created = filled = missing = 0
for p in sorted(glob.glob(os.path.join(EN3, "0*.json"))):
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
    have = {q["q"]: q.get("ru", "") for q in ru.get("qstrings", [])}
    out = []
    for q in qs:
        cur = have.get(q["q"], "")
        new = cur or tr.get(q["q"], "")
        if new and not cur:
            filled += 1
        if not new:
            missing += 1
        out.append({"q": q["q"], "ru": new})
    ru["qstrings"] = out
    json.dump(ru, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    touched += 1

print(f"файлов обновлено: {touched} (новых: {created})")
print(f"условий заполнено сейчас: {filled}, осталось без перевода: {missing}")
