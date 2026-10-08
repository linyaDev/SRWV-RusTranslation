import json, os, glob
E = r"D:\games\SUPER ROBOT WARS V\_extracted"
src = json.load(open(os.path.join(E, "rpw_jstr_EN.json"), encoding="utf-8"))
tr = {}
for f in sorted(glob.glob(os.path.join(E, "jstr_tr_?.json"))):
    d = json.load(open(f, encoding="utf-8-sig"))
    n = 0
    for it in d["items"]:
        if it.get("ru"): tr[it["idx"]] = it["ru"]; n += 1
    print("%-18s +%d" % (os.path.basename(f), n))
out = json.loads(json.dumps(src))
hit = 0
for s in out["strings"]:
    if s["idx"] in tr:
        s["text"] = tr[s["idx"]]; hit += 1
json.dump(out, open(os.path.join(E, "rpw_jstr_RU.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("подставлено строк:", hit, "из", len(out["strings"]))
