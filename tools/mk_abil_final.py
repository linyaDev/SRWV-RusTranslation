import json, os
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
TAIL, LIMIT = 72, 9304


def align4(v):
    return (v + 3) & ~3


def slot(t):
    return 4 + align4(len(t.encode("utf-8")) + 1)


descr = {i["en"]: i["ru"] for i in
         json.load(open(os.path.join(E, "ln_descr_ru.json"), encoding="utf-8-sig"))["items"]
         if i.get("ru")}
names = {i["en"]: i["ru"] for i in
         json.load(open(os.path.join(E, "ln_abilities_ru.json"), encoding="utf-8-sig"))["items"]
         if i.get("ru") and len(i["en"]) <= 40}

d = json.load(open(os.path.join(E, "ln_abilities_EN.json"), encoding="utf-8"))
items = d["items"]
for it in items:
    it["ru"] = descr.get(it["en"], "")
total = sum(slot(i["ru"] or i["en"]) for i in items) + TAIL
print("с русскими описаниями: %d байт (предел %d, запас %d)" % (total, LIMIT, LIMIT - total))

# добираем названия, начиная с самых дешёвых
order = sorted((k for k in names), key=lambda k: slot(names[k]) - slot(k))
added = 0
for k in order:
    grow = (slot(names[k]) - slot(k)) * sum(1 for i in items if i["en"] == k)
    if total + grow > LIMIT:
        continue
    for i in items:
        if i["en"] == k:
            i["ru"] = names[k]
    total += grow
    added += 1
print("плюс названий: %d из %d, итог %d байт" % (added, len(names), total))
d["items"] = items
json.dump(d, open(os.path.join(E, "ln_abilities_final.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nкакие названия влезли:")
print("  " + ", ".join(sorted({i["ru"] for i in items if i["ru"] and len(i["en"]) <= 40})))
