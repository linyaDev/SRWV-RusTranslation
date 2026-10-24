# -*- coding: utf-8 -*-
"""Свести транслитерации имён по ВСЕМУ корпусу переводов сразу.

Канон выбран вручную: внутри одной партии большинство может расходиться
с тем, что уже стоит в игре, а иногда ошибочны оба большинства
(«Сабина» для мужского персонажа Забине).

Замена идёт и в поле speaker, и внутри реплик — по границам слова,
с учётом русских падежных окончаний.
"""
import collections
import glob
import json
import os
import re
import sys

E = r"D:\games\SUPER ROBOT WARS V\_extracted"

# английское имя -> канонический русский вариант
CANON = {
    "Ashura": "Ашура",
    "Battle Bomber": "Бэттл Бомбер",
    "Colasour": "Коласур",
    "Djibril": "Джибрил",
    "Elle": "Элль",
    "Embryo": "Эмбрио",
    "Feldt": "Фельдт",
    "Frontal": "Фронталь",
    "Hallelujah": "Халлилуйя",
    "Hathaway": "Хатауэй",
    "Lacus": "Лакус",
    "Lane": "Лэйн",
    "Maya": "Майя",
    "Mycenae God": "Микенский бог",
    "Ple": "Пуру",
    "Ple Two": "Пуру Два",
    "Riddhe": "Ридде",
    "Sabine": "Забине",          # Zabine Chareux — мужчина, «Сабина» ошибка
    "Salamandinay": "Саламандинай",
    "Velt": "Вельт",
    "Zinnerman": "Циннерман",
}

# варианты, которые надо заменить в тексте реплик (не только в speaker)
TEXT_FIX = {
    "Асура": "Ашура", "Коласаур": "Коласур", "Колласур": "Коласур",
    "Колясур": "Коласур", "Джибриль": "Джибрил", "Эмбрион": "Эмбрио",
    "Фельт": "Фельдт", "Фронтал": "Фронталь", "Халлелуйя": "Халлилуйя",
    "Хатуэй": "Хатауэй", "Хэтэуэй": "Хатауэй", "Хасуэй": "Хатауэй",
    "Хэсэвэй": "Хатауэй", "Лакс": "Лакус", "Лейн": "Лэйн", "Мая": "Майя",
    "Пле Два": "Пуру Два", "Пуру Вторая": "Пуру Два", "Пуру Ту": "Пуру Два",
    "Пуру-Ту": "Пуру Два", "Риди": "Ридде", "Риддхе": "Ридде",
    "Ридэ": "Ридде", "Риддэ": "Ридде", "Сабина": "Забине", "Сабин": "Забине",
    "Саламандиней": "Саламандинай", "Велт": "Вельт", "Зиннерман": "Циннерман",
    "Бог Микены": "Микенский бог", "Бог Микенэ": "Микенский бог",
    "Баттл Бомбер": "Бэттл Бомбер", "Бэтл Бомбер": "Бэттл Бомбер",
    "«Мазингер ЗЕРО»": "«Мазингер Зеро»",
    "«Мазингера ЗЕРО»": "«Мазингера Зеро»",
    "«Мазингером ЗЕРО»": "«Мазингером Зеро»",
    "«ЗЕРО»": "«Зеро»", "«Дайтарн-3»": "«Дайтарн 3»",
    "«Космо Реверсе»": "«Космо-Реверсе»",
    "«Геттер Роботов»": "«Геттер-роботов»",
}
CYR = "\u0410-\u044f\u0401\u0451"
# «Пле» отдельно: короткое и встречается внутри других слов
SHORT = {"Пле": "Пуру", "Эль": "Элль"}


def process(pairs):
    n_sp = n_txt = 0
    changed_files = 0
    for p, en in pairs:
        j = json.load(open(p, encoding="utf-8-sig"))
        blocks = j.get("blocks", []) if isinstance(j, dict) else j
        ch = False
        for b in blocks:
            o = en.get(b["i"])
            if o:
                want = CANON.get(o["speaker"])
                if want and b.get("speaker") != want:
                    b["speaker"] = want
                    n_sp += 1
                    ch = True
            t = b.get("text", "")
            new = t
            for bad, good in TEXT_FIX.items():
                if bad in new:
                    new = re.sub(r"(?<![%s])%s(?![%s])" % (CYR, re.escape(bad), CYR),
                                 good, new)
            for bad, good in SHORT.items():
                new = re.sub(r"(?<![%s])%s(?![%s])" % (CYR, bad, CYR), good, new)
            if new != t:
                b["text"] = new
                n_txt += 1
                ch = True
        if ch:
            json.dump(j, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            changed_files += 1
    return changed_files, n_sp, n_txt


pairs = []
for src_dir, en_dir, pat in (
        (sys.argv[1] if len(sys.argv) > 1 else os.path.join(E, "story_b5"), None, "ru_c*.json"),
        (os.path.join(E, "dialogs_ru"), os.path.join(E, "dialogs_en_v3"), "*.json")):
    for p in glob.glob(os.path.join(src_dir, pat)):
        if en_dir:
            ep = os.path.join(en_dir, os.path.basename(p))
        else:
            ep = os.path.join(src_dir, os.path.basename(p)[3:])
        if not os.path.exists(ep):
            continue
        en = {b["i"]: b for b in json.load(open(ep, encoding="utf-8"))["blocks"]}
        pairs.append((p, en))

f, sp, txt = process(pairs)
print("файлов изменено: %d | имён в speaker: %d | реплик с правкой: %d" % (f, sp, txt))
