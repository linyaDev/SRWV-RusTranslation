# -*- coding: utf-8 -*-
"""Собрать компактный глоссарий для агентов-переводчиков.

Вместо чтения мегабайтных cmn_tm.json / LT00_RU.json агент читает один
небольшой файл GLOSSARY.md с устоявшимися терминами и именами.
"""
import json
import os
import re
from collections import Counter

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
OUT = r"D:\games\SUPER ROBOT WARS V\_tools\GLOSSARY.md"

# 1. Имена говорящих (готовый глоссарий)
speakers = json.load(open(os.path.join(E, "dialogs_en", "_speakers_ru.json"),
                          encoding="utf-8-sig"))

# 2. Частотные русские термины из памяти боевых реплик
tm = json.load(open(os.path.join(E, "cmn_tm.json"), encoding="utf-8"))
TERMS = [
    "ньютайп", "мобильный доспех", "мобильная броня", "фин-фаннелы", "фаннелы",
    "бим-магнум", "I-поле", "AT-поле", "GN-", "Лямбда-драйвер", "псикоммю",
    "психорама", "частицы Миновского", "волновая пушка", "волновой двигатель",
    "главный калибр", "Геттер-луч", "Ракетный удар", "Брест Файр", "Мазин-Пауэр",
    "Стоунер Саншайн", "терронцы", "Империя Юпитера", "Кроссбоун-Вангард",
    "Нео-Зеон", "Лондо Белл", "Красная комета", "Однолетняя война", "Мятеж Чара",
    "Искандар", "Гамилас", "Мифрил", "Гардим", "ЗАФТ", "Селестиал Бин",
    "Воля", "боевой дух", "ТакО", "SR-очко", "Действие-Экс", "Приказ-Экс",
    "Крит. удар", "Мультиход", "Форсаж", "ответная атака", "атака поддержки",
]
found = {t: sum(1 for v in tm.values() if t in v) for t in TERMS}

# 3. Имена машин и кораблей в кавычках — самые частые
quoted = Counter()
for v in tm.values():
    for m in re.finditer(r"«([^»]{2,24})»", v):
        quoted[m.group(1)] += 1

lines = [
    "# Глоссарий русификатора SRW V",
    "",
    "Компактная выжимка для агентов-переводчиков: читать ЭТОТ файл,",
    "а не мегабайтные cmn_tm.json / LT00_RU.json.",
    "",
    "## Термины (устоявшийся перевод)",
    "",
    "| EN | RU |",
    "|---|---|",
    "| Newtype | ньютайп |",
    "| mobile suit / mobile armor | мобильный доспех / мобильная броня |",
    "| Fin Funnels / Funnels | фин-фаннелы / фаннелы |",
    "| Beam Magnum | бим-магнум |",
    "| I-Field / AT Field | I-поле / AT-поле |",
    "| Lambda Driver | Лямбда-драйвер |",
    "| Psycommu / Psychoframe | псикоммю / психорама |",
    "| Minovsky particles | частицы Миновского |",
    "| Wave Motion Gun / Engine | волновая пушка / волновой двигатель |",
    "| main cannon | главный калибр |",
    "| Getter Beam | Геттер-луч |",
    "| Rocket Punch / Breast Fire | Ракетный удар / Брест Файр |",
    "| Mazin Power | Мазин-Пауэр |",
    "| Terron / Terrons | Террон (Земля у гамиласцев) / терронцы |",
    "| Jupiter Empire / Jovians | Империя Юпитера / юпитерианцы |",
    "| Crossbone Vanguard | Кроссбоун-Вангард |",
    "| Neo Zeon / Londo Bell | Нео-Зеон / «Лондо Белл» |",
    "| Red Comet / Char | Красная комета / Чар |",
    "| One Year War / Char's Rebellion | Однолетняя война / Мятеж Чара |",
    "| Mithril / Gardim / ZAFT | «Мифрил» / Гардим / ЗАФТ |",
    "| Celestial Being | «Селестиал Бин» |",
    "",
    "## Интерфейс (как в установленном переводе)",
    "",
    "| EN | RU |",
    "|---|---|",
    "| Focus | Воля |",
    "| morale | боевой дух |",
    "| Spirit Commands | Умения (названия самих умений — ПО-АНГЛИЙСКИ: Accel, Valor, Soul, Foresee) |",
    "| Extra Action / Extra Order | Действие-Экс / Приказ-Экс |",
    "| ExC / Tac Points | ExC / ТакО |",
    "| SR Point | SR-очко |",
    "| Smash Hit / Multi Action | Крит. удар / Мультиход |",
    "| Boost Dash / Direct Attack | Форсаж / Прямая атака |",
    "| Return Attack / Support Attack | ответная атака / атака поддержки |",
    "| Stats / Suspend / End Phase | Статус / Отложить / Конец хода |",
    "| Squad List | Список |",
    "",
    "## Машины и корабли (канон)",
    "",
]
top = [q for q, c in quoted.most_common(60) if c >= 2]
for i in range(0, len(top), 6):
    lines.append("- " + " · ".join(f"«{x}»" for x in top[i:i + 6]))

lines += [
    "",
    "## Имена персонажей",
    "",
    f"Полный список ({len(speakers)} имён) — в `dialogs_en/_speakers_ru.json`.",
    "Читать его стоит только если нужного имени нет ниже.",
    "",
]
MAIN = ["Okita", "Kodai", "Shima", "Sanada", "Mori", "Yamamoto", "Nanbu", "Kato",
        "Starsha", "Dessler", "Domel", "Shultz", "Soji", "Chitose", "Nine",
        "Tobia", "Kincade", "Berah", "Zabine", "Amuro", "Char", "Kamille", "Judau",
        "Banagher", "Setsuna", "Kira", "Shinn", "Sousuke", "Kaname", "Ryoma",
        "Hayato", "Benkei", "Koji", "Tetsuya", "Maito", "Ange", "Tusk", "Akito",
        "Ruri", "Shinji", "Asuka", "Rei", "Misato", "Banjo", "Kappei"]
for name in MAIN:
    if name in speakers:
        lines.append(f"- {name} — {speakers[name]}")

open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
size = os.path.getsize(OUT)
print(f"{OUT}: {size/1024:.1f} КБ (≈{size/3.5:.0f} токенов)")
print(f"вместо cmn_tm.json (1054 КБ) + LT00_RU (187 КБ) + SysText_RU (143 КБ)")
