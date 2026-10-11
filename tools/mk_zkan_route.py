# -*- coding: utf-8 -*-
"""Нарезать статьи о персонажах маршрута на порции для перевода."""
import json
import os

E = r"D:\games\SUPER ROBOT WARS V\_extracted"
need = json.load(open(os.path.join(E, "zkan_need_route.json"), encoding="utf-8"))["items"]
idx = {(e["dir"], e["file"]): e for e in
       json.load(open(os.path.join(E, "zkan_index.json"), encoding="utf-8"))["entries"]}
TAGS = ("CHFN", "CHNN", "PRDC", "ACTR", "DSCR", "DSC2")


def load(it):
    rec = idx[(it["dir"], it["file"])]
    jd = "zkan_pt_json" if rec["dir"] == "MtZkn_Pt_dec" else "zkan_rt_json"
    d = json.load(open(os.path.join(E, jd, rec["file"].replace(".dat", ".json")),
                       encoding="utf-8"))
    out = {"file": rec["file"], "dir": rec["dir"]}
    for fl in d["fields"]:
        if fl["tag"] in TAGS and fl.get("text"):
            out[fl["tag"]] = fl["text"]
            out[fl["tag"] + "_ru"] = ""
    return out


arts = [load(x) for x in need]
n = 0
for k in range(0, len(arts), 8):
    n += 1
    part = arts[k:k + 8]
    json.dump({"articles": part},
              open(os.path.join(E, "zkan_r%02d_route.json" % n), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("zkan_r%02d_route.json  %d статей  %5d симв." %
          (n, len(part), sum(len(a.get("DSCR", "")) + len(a.get("DSC2", "")) for a in part)))
print("всего статей:", len(arts), "| порций:", n)
