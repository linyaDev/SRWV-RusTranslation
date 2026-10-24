import json, os, sys
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
tr = {}
for f in ("qstrings_ru.json", "qstrings_ru2.json"):
    for it in json.load(open(os.path.join(E, f), encoding="utf-8-sig"))["items"]:
        if it.get("ru"):
            tr[it["en"]] = it["ru"]
EXTRA = {
    "SR points are not included in download contents.":
        "В загружаемом контенте SR-очки не начисляются.",
    "Yatenko's HP falls below 5,000.": "HP Ятэнко ниже 5000.",
}
tr.update(EXTRA)
for num in ("304", "305"):
    d = os.path.join(E, "dlc" + num + "_en")
    for f in sorted(os.listdir(d)):
        if not f.startswith("000000") or not f.endswith(".json"):
            continue
        j = json.load(open(os.path.join(d, f), encoding="utf-8"))
        qs = j.get("qstrings", [])
        if not qs:
            continue
        out = []
        for q in qs:
            r = tr.get(q["q"], "")
            mark = " " if r else " НЕТ ПЕРЕВОДА"
            print("dlc%s %s:%s %-52s -> %s" % (num, f[:-5], mark, q["q"], r))
            out.append({"q": q["q"], "ru": r})
        json.dump({"qstrings": out},
                  open(os.path.join(d, "ru_" + f), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
