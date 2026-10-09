# -*- coding: utf-8 -*-
"""Собрать файл 3 KPACK_LN с переводом, укладывающимся в заданный размер.

Игра падает, если файл вырастает слишком сильно: при 9920 байт запускается,
при 14572 — нет. Поэтому перевод добирается по частям: сначала короткие
названия способностей (их видно в карточке юнита), затем описания эффектов
по возрастанию прироста — пока не упрёмся в предел.

  mk_abil_fit.py <предел_байт> <имя_выходного_json>
"""
import json
import os
import sys

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
limit = int(sys.argv[1])
out_name = sys.argv[2]
TAIL = 72          # хвост файла за последней записью


def align4(v):
    return (v + 3) & ~3


def slot(text):
    return 4 + align4(len(text.encode("utf-8")) + 1)


d = json.load(open(os.path.join(E, "ln_abilities_slots_ru.json"), encoding="utf-8"))
items = [dict(i) for i in d["items"]]
for i in items:
    i["_ru"] = i["ru"]
    i["ru"] = ""
total = sum(slot(i["en"]) for i in items) + TAIL

order = sorted(range(len(items)),
               key=lambda k: (len(items[k]["en"]) > 40,
                              slot(items[k]["_ru"]) - slot(items[k]["en"])))
taken = 0
for k in order:
    it = items[k]
    if not it["_ru"]:
        continue
    grow = slot(it["_ru"]) - slot(it["en"])
    if total + grow > limit:
        continue
    it["ru"] = it["_ru"]
    total += grow
    taken += 1

for i in items:
    del i["_ru"]
d["items"] = items
json.dump(d, open(os.path.join(E, out_name), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
names = sum(1 for i in items if i["ru"] and len(i["en"]) <= 40)
descr = sum(1 for i in items if i["ru"] and len(i["en"]) > 40)
print("переведено: названий %d, описаний %d (всего %d из %d)" %
      (names, descr, taken, len(items)))
print("расчётный размер %d при пределе %d" % (total, limit))
