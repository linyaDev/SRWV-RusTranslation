# -*- coding: utf-8 -*-
"""Названия умений духа внутри описаний — вернуть английские (BLTU-базы).

Замена срабатывает, если русское название стоит в кавычках «…» либо после
слова «умени…/команд…» — это отличает ссылку на умение от обычного слова и от
самостоятельных имён навыков («Стойкость духа»). Плюс обязательное условие:
в английском оригинале той же записи есть это английское имя.

Один и тот же термин разные агенты переводили по-разному (Valor = «Горячая
кровь» и «Отвага»), поэтому для каждого имени список вариантов и падежей.
"""
import json
import os
import re

E = r"D:\games\SUPER ROBOT WARS V\_extracted"

NAMES = {
    "Valor": ["Горячая кровь", "Горячей кровью", "Горячую кровь", "Горячей крови",
              "Отвага", "Отвагу", "Отваги", "Отвагой"],
    "Bravery": ["Отвага", "Отвагу", "Отваги", "Отвагой", "Смелость", "Храбрость"],
    "Soul": ["Душа", "Душой", "Душу", "Души"],
    "Flicker": ["Чутьё", "Чутье", "Чутья", "Проблеск"],
    "Persist": ["Стойкость", "Стойкости", "Упорство"],
    "Iron Wall": ["Железная стена", "Железной стены", "Железную стену"],
    "Zero-in": ["Сосредоточение", "Сосредоточения"],
    "Bullseye": ["Меткость", "Меткости", "Точность"],
    "Attune": ["Созвучие", "Созвучия"],
    "Intuition": ["Интуиция", "Интуицию", "Интуиции"],
    "Accel": ["Ускорение", "Ускорения", "Ускорением"],
    "Zeal": ["Пробуждение", "Пробуждения", "Рвение"],
    "Grit": ["Кураж", "Куража"],
    "Guts": ["Сверхкураж", "Сверхкуража", "Стойкость духа"],
    "Trust": ["Доверие", "Доверия"],
    "Faith": ["Вера", "Веры", "Веру"],
    "Spirit": ["Настрой", "Настроя"],
    "Drive": ["Натиск", "Натиска"],
    "Rouse": ["Ободрение", "Ободрения"],
    "Mercy": ["Милость", "Милости"],
    "Snipe": ["Снайпер", "Снайпера"],
    "Charge": ["Штурм", "Штурма"],
    "Haze": ["Помеха", "Помехи"],
    "Agitate": ["Угроза", "Угрозы", "Агитация", "Агитацию", "Агитации"],
    "Love": ["Любовь", "Любви"],
    "Fortune": ["Удача", "Удачу", "Удачи", "Удачей"],
    "Bless": ["Благословение", "Благословения"],
    "Gain": ["Опыт", "Опыта", "Опытом", "Прирост", "Прироста"],
    "Cheer": ["Поддержка", "Поддержки", "Поддержку"],
    "Analyze": ["Анализ", "Анализа", "Анализом"],
    "Bonds": ["Узы", "Уз"],
    "Prospect": ["Надежда", "Надежды", "Надежду"],
    "Foresee": ["Предвидение", "Предвидения"],
    "Wish": ["Желание", "Желания"],
    "Resupply": ["Пополнение", "Пополнения", "Снабжение", "Снабжения"],
}
CYR = "\u0410-\u044f\u0401\u0451"


def fix(ru_path, en_path, label):
    ru = json.load(open(ru_path, encoding="utf-8-sig"))
    en = json.load(open(en_path, encoding="utf-8-sig"))
    src_by_key = {e["key"]: e["values"] for e in en["entries"]}
    fixed = 0
    for ent in ru["entries"]:
        src = src_by_key.get(ent["key"])
        if not src:
            continue
        for vi, val in enumerate(ent["values"]):
            if vi >= len(src):
                break
            e, new = src[vi], ent["values"][vi]
            for eng, forms in NAMES.items():
                if not re.search(r"(?<![A-Za-z])" + re.escape(eng) + r"(?![A-Za-z])", e):
                    continue
                for form in sorted(forms, key=len, reverse=True):
                    f = re.escape(form)
                    new = re.sub("\u00ab" + f + "\u00bb", "\u00ab" + eng + "\u00bb", new)
                    new = re.sub(r"((?:умени|команд)\w*\s+)" + f + r"(?![" + CYR + r"])",
                                 r"\1" + eng, new)
            if new != val:
                ent["values"][vi] = new
                fixed += 1
                if fixed <= 8:
                    print("   %-26s %s" % (ent["key"], new.replace("\n", " / ").strip()[:78]))
    json.dump(ru, open(ru_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%s: строк исправлено %d" % (label, fixed))


fix(os.path.join(E, "json", "LT00_RU.json"), os.path.join(E, "json", "LT00_EN.json"), "LT00")
fix(os.path.join(E, "json", "SysText_RU.json"), os.path.join(E, "json", "SysText_EN.json"), "SysText")
