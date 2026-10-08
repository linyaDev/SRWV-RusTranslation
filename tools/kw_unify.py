# -*- coding: utf-8 -*-
"""Привести названия терминов ($kwb…$kwe) к единому виду в диалогах и статьях."""
import json

RU = r"D:\games\SUPER ROBOT WARS V\_extracted\dialogs_ru"

DIALOG_FIX = {
    "00000033.json": {12: (
        "「Во время Юпитерианской войны я ещё учился в\n"
        "\u3000офицерской школе, но слышал о подвигах\n"
        "\u3000$kwbкосмических пиратов Кроссбоун-Вангард$kwe.」")},
    "00000045.json": {
        25: "「$kwbСто лет назад$kwe — это же времена Однолетней войны!」",
        71: "「$kwbСто лет назад$kwe — это же времена Однолетней войны!」",
    },
}

for fname, fixes in DIALOG_FIX.items():
    p = f"{RU}\\{fname}"
    d = json.load(open(p, encoding="utf-8-sig"))
    for b in d["blocks"]:
        if b["i"] in fixes:
            print(f'{fname}[{b["i"]}]')
            print("  было:", b["text"].replace("\n", " / "))
            b["text"] = fixes[b["i"]]
            print("  стало:", b["text"].replace("\n", " / "))
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# статьи
kp = r"D:\games\SUPER ROBOT WARS V\_extracted\keywords_ru.json"
k = json.load(open(kp, encoding="utf-8"))
RENAME = {"Jupiter War": "Юпитерианская война", "Axis Shock": "Шок Аксиса",
          "100 Years Ago": "Сто лет назад"}
for a in k["articles"]:
    if a["term_en"] in RENAME:
        old = a["term_ru"]
        a["term_ru"] = RENAME[a["term_en"]]
        if old != a["term_ru"]:
            print(f'статья: {old} -> {a["term_ru"]}')
    a["text_ru"] = (a["text_ru"]
                    .replace("Война, вспыхнувшая", "Война, вспыхнувшая")
                    .replace("Кроссбоун-Вангард", "Кроссбоун-Вангард"))
json.dump(k, open(kp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("готово")
