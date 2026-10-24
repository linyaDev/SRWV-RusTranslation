import glob, json, os, re
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
SRC = os.path.join(E, "story_bonus")
DEN = os.path.join(E, "dialogs_en_v3")
OUT = os.path.join(E, "dialogs_ru")
MARK = re.compile(r"\$kw[be]")
LIMIT, MAXL = 66, 3

groups = {}
for p in sorted(glob.glob(os.path.join(SRC, "ru_c*_*.json"))):
    fid = re.search(r"_(\d{8})\.json$", p).group(1)
    groups.setdefault(fid, []).append(p)

errs = 0
for fid, parts in sorted(groups.items()):
    orig = json.load(open(os.path.join(DEN, fid + ".json"), encoding="utf-8"))
    by_i = {b["i"]: b for b in orig["blocks"]}
    merged = []
    for p in parts:
        merged += json.load(open(p, encoding="utf-8-sig"))["blocks"]
    if len(merged) != len(orig["blocks"]):
        print("  %s: блоков %d, ожидалось %d" % (fid, len(merged), len(orig["blocks"]))); errs += 1
    for b in merged:
        o = by_i.get(b["i"])
        if o is None or b.get("orig") != o["orig"]:
            print("  %s i=%s: orig не совпал" % (fid, b["i"])); errs += 1; continue
        if not b.get("text", "").strip():
            print("  %s i=%s: пусто" % (fid, b["i"])); errs += 1
        lines = b["text"].split("\n")
        if len(lines) > max(len(o["text"].split("\n")), MAXL):
            print("  %s i=%s: строк %d" % (fid, b["i"], len(lines))); errs += 1
        for ln in lines:
            if len(MARK.sub("", ln)) > LIMIT:
                print("  %s i=%s: %d знаков" % (fid, b["i"], len(MARK.sub("", ln)))); errs += 1
                break
    json.dump({"blocks": sorted(merged, key=lambda x: x["i"])},
              open(os.path.join(OUT, fid + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    import shutil
    shutil.copy(os.path.join(DEN, fid + ".json"), os.path.join(E, "dialogs_en", fid + ".json"))
print("файлов: %d | ошибок: %d" % (len(groups), errs))
